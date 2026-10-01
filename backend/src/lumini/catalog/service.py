"""Catalog workflow rules. Callers own the transaction; every mutation takes the catalog lock first.

Errors carry fixed messages only: never input values, clinical text, e-mails or credentials.
"""

import uuid
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lumini.auth import AdminPrincipal
from lumini.catalog.schemas import (
    ApprovalRequest,
    ApprovalView,
    ProfessionalCreate,
    ProfessionalUpdate,
    ProfessionalView,
    PublicContent,
    PublicProfessional,
    PublicService,
    ServiceContent,
    ServiceCreate,
    ServiceUpdate,
    ServiceView,
    VersionRequest,
)
from lumini.models import (
    CatalogAuditEvent,
    Professional,
    ProfessionalService,
    Service,
    ServiceApproval,
)

# Low-volume administrative writes are serialized so credential changes, edits and
# publication never interleave. Booking/agenda paths must not reuse this lock.
CATALOG_LOCK_KEY = 0x4C554D494E49  # "LUMINI"
_CENTS = Decimal("0.01")
_SERVICE_FIELDS = (
    "slug",
    "name",
    "category",
    "description",
    "duration_minutes",
    "buffer_minutes",
    "booking_mode",
    "price_brl",
    "deposit_brl",
)
_PROFESSIONAL_FIELDS = ("display_name", "category", "council_registration")


class CatalogError(Exception):
    """Base for workflow refusals; the message is safe to return to an administrator."""


class CatalogNotFound(CatalogError):
    pass


class CatalogForbidden(CatalogError):
    pass


class CatalogConflict(CatalogError):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


async def _lock(session: AsyncSession) -> None:
    await session.execute(select(func.pg_advisory_xact_lock(CATALOG_LOCK_KEY)))


def _audit(
    session: AsyncSession,
    actor: AdminPrincipal,
    entity_type: str,
    target_id: uuid.UUID,
    action: str,
    revision: int,
) -> None:
    session.add(
        CatalogAuditEvent(
            id=uuid.uuid4(),
            actor_subject=actor.subject,
            entity_type=entity_type,
            target_id=target_id,
            action=action,
            revision=revision,
        )
    )


def _check_revision(current: int, request: VersionRequest) -> None:
    if current != request.expected_revision:
        raise CatalogConflict("The item changed; reload before retrying")


# Professionals


def _professional_view(item: Professional) -> ProfessionalView:
    return ProfessionalView.model_validate(
        {
            "id": item.id,
            "display_name": item.display_name,
            "category": item.category,
            "council_registration": item.council_registration,
            "credentials_verified_at": item.credentials_verified_at,
            "revision": item.revision,
        }
    )


async def _get_professional(session: AsyncSession, professional_id: uuid.UUID) -> Professional:
    item = await session.get(Professional, professional_id)
    if item is None:
        raise CatalogNotFound("Professional not found")
    return item


async def list_professionals(session: AsyncSession) -> list[ProfessionalView]:
    rows = await session.scalars(
        select(Professional).order_by(Professional.display_name, Professional.id)
    )
    return [_professional_view(item) for item in rows]


async def create_professional(
    session: AsyncSession, actor: AdminPrincipal, data: ProfessionalCreate
) -> ProfessionalView:
    await _lock(session)
    item = Professional(
        id=uuid.uuid4(),
        display_name=data.display_name,
        category=data.category,
        council_registration=data.council_registration,
        credentials_verified_at=None,
        credentials_verified_by=None,
        revision=1,
    )
    session.add(item)
    _audit(session, actor, "professional", item.id, "professional.created", item.revision)
    await session.flush()
    return _professional_view(item)


async def update_professional(
    session: AsyncSession,
    actor: AdminPrincipal,
    professional_id: uuid.UUID,
    data: ProfessionalUpdate,
) -> ProfessionalView:
    await _lock(session)
    item = await _get_professional(session, professional_id)
    _check_revision(item.revision, data)
    changes = {
        field: getattr(data, field)
        for field in _PROFESSIONAL_FIELDS
        if field in data.model_fields_set and getattr(data, field) != getattr(item, field)
    }
    if not changes:
        return _professional_view(item)
    for field, value in changes.items():
        setattr(item, field, value)
    item.revision += 1
    item.credentials_verified_at = None
    item.credentials_verified_by = None
    _audit(session, actor, "professional", item.id, "professional.updated", item.revision)
    await _invalidate_linked_services(session, actor, item.id)
    await session.flush()
    return _professional_view(item)


async def verify_professional(
    session: AsyncSession,
    actor: AdminPrincipal,
    professional_id: uuid.UUID,
    data: VersionRequest,
) -> ProfessionalView:
    """Records a human documentary check. It never queries a council automatically."""
    await _lock(session)
    item = await _get_professional(session, professional_id)
    _check_revision(item.revision, data)
    if item.credentials_verified_at is not None:
        return _professional_view(item)
    if not (item.display_name and item.category and item.council_registration):
        raise CatalogConflict("Name, category and council registration are required")
    item.credentials_verified_at = _now()
    item.credentials_verified_by = actor.subject
    _audit(session, actor, "professional", item.id, "professional.verified", item.revision)
    await session.flush()
    return _professional_view(item)


async def revoke_professional(
    session: AsyncSession,
    actor: AdminPrincipal,
    professional_id: uuid.UUID,
    data: VersionRequest,
) -> ProfessionalView:
    await _lock(session)
    item = await _get_professional(session, professional_id)
    _check_revision(item.revision, data)
    if item.credentials_verified_at is not None:
        item.credentials_verified_at = None
        item.credentials_verified_by = None
        _audit(session, actor, "professional", item.id, "professional.revoked", item.revision)
    # Conservative even when already unverified: no linked service may stay approved.
    await _invalidate_linked_services(session, actor, item.id)
    await session.flush()
    return _professional_view(item)


# Services


def _cents(value: Decimal | None) -> Decimal | None:
    return None if value is None else value.quantize(_CENTS)


async def _links(
    session: AsyncSession, service_ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, list[uuid.UUID]]:
    ids = list(service_ids)
    result: dict[uuid.UUID, list[uuid.UUID]] = {service_id: [] for service_id in ids}
    rows = await session.execute(
        select(ProfessionalService.service_id, ProfessionalService.professional_id)
        .where(ProfessionalService.service_id.in_(ids))
        .order_by(ProfessionalService.professional_id)
    )
    for service_id, professional_id in rows:
        result[service_id].append(professional_id)
    return result


async def _current_approvals(
    session: AsyncSession, services: Sequence[Service]
) -> dict[uuid.UUID, list[ServiceApproval]]:
    revisions = {item.id: item.revision for item in services}
    result: dict[uuid.UUID, list[ServiceApproval]] = {service_id: [] for service_id in revisions}
    rows = await session.scalars(
        select(ServiceApproval)
        .where(ServiceApproval.service_id.in_(revisions))
        .order_by(ServiceApproval.professional_id)
    )
    for approval in rows:
        if approval.revision == revisions[approval.service_id]:
            result[approval.service_id].append(approval)
    return result


async def _service_views(session: AsyncSession, services: Sequence[Service]) -> list[ServiceView]:
    links = await _links(session, (item.id for item in services))
    approvals = await _current_approvals(session, services)
    return [
        ServiceView.model_validate(
            {
                "id": item.id,
                "slug": item.slug,
                "name": item.name,
                "category": item.category,
                "description": item.description,
                "content": item.content,
                "duration_minutes": item.duration_minutes,
                "buffer_minutes": item.buffer_minutes,
                "booking_mode": item.booking_mode,
                "price_brl": _cents(item.price_brl),
                "deposit_brl": _cents(item.deposit_brl),
                "professional_ids": links[item.id],
                "status": item.status,
                "revision": item.revision,
                "approved_at": item.approved_at,
                "published_at": item.published_at,
                "approvals": [
                    ApprovalView(professional_id=a.professional_id, approved_at=a.approved_at)
                    for a in approvals[item.id]
                ],
            }
        )
        for item in services
    ]


async def _service_view(session: AsyncSession, item: Service) -> ServiceView:
    await session.flush()
    return (await _service_views(session, [item]))[0]


async def _get_service(session: AsyncSession, service_id: uuid.UUID) -> Service:
    item = await session.get(Service, service_id)
    if item is None:
        raise CatalogNotFound("Service not found")
    return item


async def _require_unique_slug(
    session: AsyncSession, slug: str, service_id: uuid.UUID | None
) -> None:
    query = select(Service.id).where(Service.slug == slug)
    if service_id is not None:
        query = query.where(Service.id != service_id)
    if (await session.scalar(query.limit(1))) is not None:
        raise CatalogConflict("Slug already in use")


async def _require_professionals(session: AsyncSession, ids: Sequence[uuid.UUID]) -> None:
    if not ids:
        return
    found = set(await session.scalars(select(Professional.id).where(Professional.id.in_(ids))))
    if found != set(ids):
        raise CatalogConflict("Unknown professional")


async def _replace_links(
    session: AsyncSession, service_id: uuid.UUID, professional_ids: Sequence[uuid.UUID]
) -> None:
    await session.execute(
        delete(ProfessionalService).where(ProfessionalService.service_id == service_id)
    )
    session.add_all(
        ProfessionalService(professional_id=professional_id, service_id=service_id)
        for professional_id in professional_ids
    )


async def _reset_workflow(session: AsyncSession, item: Service) -> None:
    await session.execute(delete(ServiceApproval).where(ServiceApproval.service_id == item.id))
    item.status = "draft"
    item.approved_at = None
    item.approved_by = None
    item.published_at = None


async def _invalidate_linked_services(
    session: AsyncSession, actor: AdminPrincipal, professional_id: uuid.UUID
) -> None:
    service_ids = select(ProfessionalService.service_id).where(
        ProfessionalService.professional_id == professional_id
    )
    services = list(await session.scalars(select(Service).where(Service.id.in_(service_ids))))
    approvals = await _current_approvals(session, services)
    for item in services:
        if item.status != "draft" or approvals[item.id]:
            await _reset_workflow(session, item)
            _audit(session, actor, "service", item.id, "service.invalidated", item.revision)


def _is_complete(item: Service, content: ServiceContent) -> bool:
    """Content gate for approval and publication; drafts may be incomplete."""
    if content.price_kind == "on_evaluation":
        price_ok = item.price_brl is None
    else:
        price_ok = item.price_brl is not None
    deposit_ok = item.deposit_brl is not None and (
        item.price_brl is None or item.deposit_brl <= item.price_brl
    )
    return bool(
        item.description
        and content.objectives
        and content.audience
        and content.preparation
        and content.aftercare
        and content.human_guidance
        and item.duration_minutes
        and item.buffer_minutes >= 15
        and item.booking_mode
        and price_ok
        and deposit_ok
    )


async def _verified(session: AsyncSession, ids: Sequence[uuid.UUID]) -> set[uuid.UUID]:
    if not ids:
        return set()
    return set(
        await session.scalars(
            select(Professional.id).where(
                Professional.id.in_(ids), Professional.credentials_verified_at.is_not(None)
            )
        )
    )


async def list_services(session: AsyncSession) -> list[ServiceView]:
    rows = await session.scalars(select(Service).order_by(Service.category, Service.name))
    return await _service_views(session, list(rows))


async def create_service(
    session: AsyncSession, actor: AdminPrincipal, data: ServiceCreate
) -> ServiceView:
    await _lock(session)
    await _require_unique_slug(session, data.slug, None)
    await _require_professionals(session, data.professional_ids)
    item = Service(
        id=uuid.uuid4(),
        slug=data.slug,
        name=data.name,
        category=data.category,
        description=data.description,
        content=data.content.model_dump(mode="json"),
        duration_minutes=data.duration_minutes,
        buffer_minutes=data.buffer_minutes,
        booking_mode=data.booking_mode,
        price_brl=data.price_brl,
        deposit_brl=data.deposit_brl,
        status="draft",
        revision=1,
        approved_by=None,
        approved_at=None,
        published_at=None,
    )
    session.add(item)
    await session.flush()
    await _replace_links(session, item.id, data.professional_ids)
    _audit(session, actor, "service", item.id, "service.created", item.revision)
    return await _service_view(session, item)


async def update_service(
    session: AsyncSession, actor: AdminPrincipal, service_id: uuid.UUID, data: ServiceUpdate
) -> ServiceView:
    """Any real content change creates a new revision and revokes approvals and publication."""
    await _lock(session)
    item = await _get_service(session, service_id)
    _check_revision(item.revision, data)
    provided = data.model_fields_set
    changes: dict[str, Any] = {}
    for field in _SERVICE_FIELDS:
        value = getattr(data, field)
        if field in provided and value != getattr(item, field):
            changes[field] = value
    if data.content is not None:
        content = data.content.model_dump(mode="json")
        if content != item.content:
            changes["content"] = content
    new_links: list[uuid.UUID] | None = None
    if data.professional_ids is not None:
        current = (await _links(session, [item.id]))[item.id]
        if set(data.professional_ids) != set(current):
            new_links = data.professional_ids
    if not changes and new_links is None:
        return await _service_view(session, item)
    if "slug" in changes:
        await _require_unique_slug(session, changes["slug"], item.id)
    if new_links is not None:
        await _require_professionals(session, new_links)
        await _replace_links(session, item.id, new_links)
    for field, value in changes.items():
        setattr(item, field, value)
    item.revision += 1
    await _reset_workflow(session, item)
    _audit(session, actor, "service", item.id, "service.updated", item.revision)
    return await _service_view(session, item)


async def approve_service(
    session: AsyncSession, actor: AdminPrincipal, service_id: uuid.UUID, data: ApprovalRequest
) -> ServiceView:
    """One professional's approval of the current revision, by an identity assigned to them."""
    if data.professional_id not in actor.reviewer_professional_ids:
        raise CatalogForbidden("Reviewer is not assigned to this professional")
    await _lock(session)
    item = await _get_service(session, service_id)
    _check_revision(item.revision, data)
    linked = (await _links(session, [item.id]))[item.id]
    if data.professional_id not in linked:
        raise CatalogConflict("Professional is not linked to this service")
    if data.professional_id not in await _verified(session, [data.professional_id]):
        raise CatalogConflict("Professional credentials are not verified")
    if not _is_complete(item, ServiceContent.model_validate(item.content)):
        raise CatalogConflict("Service content is incomplete")
    approvals = (await _current_approvals(session, [item]))[item.id]
    approved = {approval.professional_id for approval in approvals}
    if data.professional_id in approved:
        return await _service_view(session, item)
    await session.execute(
        delete(ServiceApproval).where(
            ServiceApproval.service_id == item.id,
            ServiceApproval.professional_id == data.professional_id,
        )
    )
    session.add(
        ServiceApproval(
            service_id=item.id,
            professional_id=data.professional_id,
            revision=item.revision,
            approved_by=actor.subject,
            approved_at=_now(),
        )
    )
    _audit(session, actor, "service", item.id, "service.approved", item.revision)
    if set(linked) <= approved | {data.professional_id} and item.status == "draft":
        item.status = "approved"
        item.approved_at = _now()
        item.approved_by = actor.subject
    return await _service_view(session, item)


async def publish_service(
    session: AsyncSession, actor: AdminPrincipal, service_id: uuid.UUID, data: VersionRequest
) -> ServiceView:
    await _lock(session)
    item = await _get_service(session, service_id)
    _check_revision(item.revision, data)
    if item.status == "published":
        return await _service_view(session, item)
    if item.status != "approved":
        raise CatalogConflict("Every linked professional must approve the current revision")
    linked = (await _links(session, [item.id]))[item.id]
    approved = {a.professional_id for a in (await _current_approvals(session, [item]))[item.id]}
    if (
        not linked
        or not set(linked) <= approved
        or await _verified(session, linked) != set(linked)
        or not _is_complete(item, ServiceContent.model_validate(item.content))
    ):
        raise CatalogConflict("Approvals, credentials or content are no longer valid")
    item.status = "published"
    item.published_at = _now()
    _audit(session, actor, "service", item.id, "service.published", item.revision)
    return await _service_view(session, item)


async def unpublish_service(
    session: AsyncSession, actor: AdminPrincipal, service_id: uuid.UUID, data: VersionRequest
) -> ServiceView:
    """Back to draft; republication requires fresh approvals (conservative)."""
    await _lock(session)
    item = await _get_service(session, service_id)
    _check_revision(item.revision, data)
    if item.status == "draft":
        return await _service_view(session, item)
    await _reset_workflow(session, item)
    _audit(session, actor, "service", item.id, "service.unpublished", item.revision)
    return await _service_view(session, item)


async def _eligible_published(
    session: AsyncSession, service_ids: Sequence[uuid.UUID] | None = None
) -> tuple[list[Service], dict[uuid.UUID, list[uuid.UUID]], dict[uuid.UUID, Professional]]:
    """Published services whose approvals, credentials and content are still valid.

    Single source of truth for the public catalog and for booking eligibility.
    """
    query = select(Service).where(Service.status == "published")
    if service_ids is not None:
        query = query.where(Service.id.in_(service_ids))
    services = list(await session.scalars(query.order_by(Service.category, Service.name)))
    links = await _links(session, (item.id for item in services))
    approvals = await _current_approvals(session, services)
    ids = {professional_id for linked in links.values() for professional_id in linked}
    professionals = {
        item.id: item
        for item in await session.scalars(
            select(Professional).where(
                Professional.id.in_(ids), Professional.credentials_verified_at.is_not(None)
            )
        )
    }
    eligible: list[Service] = []
    for item in services:
        linked = links[item.id]
        approved = {approval.professional_id for approval in approvals[item.id]}
        if (
            linked
            and set(linked) <= approved
            and set(linked) <= professionals.keys()
            and _is_complete(item, ServiceContent.model_validate(item.content))
        ):
            eligible.append(item)
    return eligible, links, professionals


async def bookable_service(
    session: AsyncSession, service_id: uuid.UUID
) -> tuple[Service, list[uuid.UUID]] | None:
    """The service and its linked professionals, only while publicly eligible."""
    services, links, _ = await _eligible_published(session, [service_id])
    return (services[0], links[service_id]) if services else None


async def list_public_services(session: AsyncSession) -> list[PublicService]:
    """Published services whose approvals, credentials and content are still valid."""
    services, links, professionals = await _eligible_published(session)
    result: list[PublicService] = []
    for item in services:
        linked = links[item.id]
        content = ServiceContent.model_validate(item.content)
        result.append(
            PublicService.model_validate(
                {
                    "id": item.id,
                    "slug": item.slug,
                    "name": item.name,
                    "category": item.category,
                    "description": item.description,
                    "content": PublicContent.model_validate(
                        content.model_dump(exclude={"communication_restrictions"})
                    ),
                    "duration_minutes": item.duration_minutes,
                    "buffer_minutes": item.buffer_minutes,
                    "booking_mode": item.booking_mode,
                    "price_brl": _cents(item.price_brl),
                    "deposit_brl": _cents(item.deposit_brl),
                    "professionals": [
                        PublicProfessional(
                            id=professionals[pid].id,
                            display_name=professionals[pid].display_name,
                            category=professionals[pid].category or "",
                            council_registration=professionals[pid].council_registration or "",
                        )
                        for pid in linked
                    ],
                }
            )
        )
    return result
