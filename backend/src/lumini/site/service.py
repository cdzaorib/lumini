"""Site content: validated input, single versioned row, audit with ids only."""

import uuid
from datetime import date, datetime
from typing import Annotated, Any, Literal, Self
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lumini.ai.guardrails import publicity_problem
from lumini.auth import AdminPrincipal
from lumini.catalog.schemas import InputModel
from lumini.catalog.service import CATALOG_LOCK_KEY
from lumini.leads.service import brazilian_phone
from lumini.models import CatalogAuditEvent, Professional, SiteSettings
from lumini.whatsapp import texts
from lumini.whatsapp.conversations import discard_pending_replies

SITE_ENTITY_ID = uuid.uuid5(uuid.NAMESPACE_URL, "lumini:site-settings")

Line = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Paragraph = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class SiteConflict(Exception):
    pass


class SiteForbidden(Exception):
    pass


class Address(InputModel):
    street: Line
    city: Line
    maps_url: Annotated[str, StringConstraints(max_length=500, pattern=r"^https://\S+$")] | None = (
        None
    )


class FaqItem(InputModel):
    question: Line
    answer: Paragraph


class Testimonial(InputModel):
    quote: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=400)]
    author: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    authorized_on: date
    authorization_confirmed: Literal[True]  # written authorization kept by the clinic


class Photo(InputModel):
    url: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]
    alt: Line
    width: Annotated[int, Field(strict=True, ge=100, le=6000)]
    height: Annotated[int, Field(strict=True, ge=100, le=6000)]
    authorized_on: date
    authorization_confirmed: Literal[True]

    @field_validator("url")
    @classmethod
    def safe_external_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.hostname in {"localhost", "127.0.0.1", "::1"}
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or any(char.isspace() for char in value)
            or "\\" in value
        ):
            raise ValueError("Photo URL must be external HTTPS without credentials or parameters")
        return value


class SiteContent(InputModel):
    address: Address | None = None
    hours: list[Line] = Field(default_factory=list, max_length=10)
    whatsapp: str | None = None
    instagram: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9._]{1,30}$")] | None = None
    differentiators: list[Line] = Field(default_factory=list, max_length=8)
    faq: list[FaqItem] = Field(default_factory=list, max_length=20)
    testimonials: list[Testimonial] = Field(default_factory=list, max_length=10)
    legal_contact: Line | None = None
    # Sent by the bot after a reservation (e.g. Pix key and holder). Never on the public site.
    deposit_instructions: Paragraph | None = None
    photos: list[Photo] = Field(default_factory=list, max_length=12)
    bot_texts: dict[str, Paragraph] = Field(default_factory=dict, max_length=len(texts.OPERATIONAL))

    @field_validator("whatsapp")
    @classmethod
    def phone(cls, value: str | None) -> str | None:
        return brazilian_phone(value) if value else None

    @model_validator(mode="after")
    def advertising_rules(self) -> Self:
        content_texts = [
            *self.differentiators,
            *(f"{item.question} {item.answer}" for item in self.faq),
            *(item.quote for item in self.testimonials),
            *(item.alt for item in self.photos),
            *self.bot_texts.values(),
        ]
        for text in content_texts:
            problem = publicity_problem(text)
            if problem is not None:
                raise ValueError(f"Advertising rule: avoid promising results ({problem})")
        for key, template in self.bot_texts.items():
            texts.validate_operational(key, template)
        return self


class SiteUpdate(InputModel):
    expected_revision: Annotated[int, Field(strict=True, ge=0)]
    content: SiteContent


class SiteVersion(InputModel):
    expected_revision: Annotated[int, Field(strict=True, ge=1)]


class SitePublish(SiteVersion):
    professional_id: uuid.UUID
    review_confirmed: Literal[True]


class SiteReviewer(BaseModel):
    professional_id: uuid.UUID
    display_name: str
    approved: bool = False


class BotTextOption(BaseModel):
    key: str
    label: str
    default: str
    placeholders: list[str]


class SiteView(BaseModel):
    revision: int
    content: SiteContent
    updated_at: datetime | None
    status: Literal["draft", "approved", "published"] = "draft"
    published_at: datetime | None = None
    reviewer_professional_id: uuid.UUID | None = None
    eligible_reviewers: list[SiteReviewer] = Field(default_factory=list)
    required_reviewers: list[SiteReviewer] = Field(default_factory=list)
    media_origins: list[str] = Field(default_factory=list)
    bot_text_options: list[BotTextOption] = Field(default_factory=list)


class PublicTestimonial(BaseModel):
    quote: str
    author: str


class PublicPhoto(BaseModel):
    url: str
    alt: str
    width: int
    height: int


class PublicSite(BaseModel):
    """What the website may show: never the deposit instructions or authorization records."""

    address: Address | None
    hours: list[str]
    whatsapp: str | None
    instagram: str | None
    differentiators: list[str]
    faq: list[FaqItem]
    testimonials: list[PublicTestimonial]
    legal_contact: str | None
    photos: list[PublicPhoto]


def _content(raw: dict[str, Any] | None) -> SiteContent:
    return SiteContent.model_validate(raw or {})


async def _required_reviewers(session: AsyncSession) -> list[Professional]:
    # Site FAQ is global, without a clinical scope per item: every verified professional
    # must review it. No professional may approve another professional's contribution.
    return list(
        await session.scalars(
            select(Professional)
            .where(Professional.credentials_verified_at.is_not(None))
            .order_by(Professional.display_name, Professional.id)
            .execution_options(populate_existing=True)
        )
    )


def _approved_by(row: SiteSettings | None, reviewer: Professional) -> bool:
    approval = (row.approvals or {}).get(str(reviewer.id)) if row else None
    return bool(
        isinstance(approval, dict)
        and row is not None
        and approval.get("revision") == row.revision
        and approval.get("professional_revision") == reviewer.revision
    )


async def _reviewed(session: AsyncSession, row: SiteSettings | None) -> bool:
    required = await _required_reviewers(session)
    required_ids = {str(reviewer.id) for reviewer in required}
    return bool(required and row is not None and set(row.approvals or {}) == required_ids) and all(
        _approved_by(row, reviewer) for reviewer in required
    )


async def _published(session: AsyncSession, row: SiteSettings | None) -> bool:
    if row is None or row.published_revision != row.revision or row.published_at is None:
        return False
    reviewer = await session.get(Professional, row.reviewer_professional_id, populate_existing=True)
    return bool(
        reviewer is not None
        and reviewer.credentials_verified_at is not None
        and reviewer.revision == row.reviewer_professional_revision
    ) and await _reviewed(session, row)


async def get_site(
    session: AsyncSession,
    actor: AdminPrincipal | None = None,
    *,
    media_origins: list[str] | None = None,
) -> SiteView:
    async with session.begin():
        row = await session.get(SiteSettings, 1, populate_existing=True)
        published = await _published(session, row)
        required = await _required_reviewers(session)
        reviewed = bool(
            required
            and row is not None
            and set(row.approvals or {}) == {str(item.id) for item in required}
        ) and all(_approved_by(row, item) for item in required)
        reviewers = [
            item
            for item in required
            if actor is not None and item.id in actor.reviewer_professional_ids
        ]
    return SiteView(
        revision=row.revision if row else 0,
        content=_content(row.content) if row else SiteContent(),
        updated_at=row.updated_at if row else None,
        status="published" if published else "approved" if reviewed else "draft",
        published_at=row.published_at if published and row else None,
        reviewer_professional_id=row.reviewer_professional_id if published and row else None,
        eligible_reviewers=[
            SiteReviewer(
                professional_id=item.id,
                display_name=item.display_name,
                approved=_approved_by(row, item),
            )
            for item in reviewers
        ],
        required_reviewers=[
            SiteReviewer(
                professional_id=item.id,
                display_name=item.display_name,
                approved=_approved_by(row, item),
            )
            for item in required
        ],
        media_origins=media_origins or [],
        bot_text_options=[
            BotTextOption(
                key=key,
                label=texts.OPERATIONAL_LABELS[key],
                default=template,
                placeholders=sorted(texts.placeholders(template)),
            )
            for key, template in texts.OPERATIONAL.items()
        ],
    )


def _clear_publication(row: SiteSettings) -> None:
    row.published_revision = None
    row.published_by = None
    row.published_at = None
    row.reviewer_professional_id = None
    row.reviewer_professional_revision = None


def _revoke(row: SiteSettings) -> None:
    _clear_publication(row)
    row.approvals = {}


def _audit(session: AsyncSession, actor: AdminPrincipal, action: str, revision: int) -> None:
    session.add(
        CatalogAuditEvent(
            id=uuid.uuid4(),
            actor_subject=actor.subject,
            entity_type="site",
            target_id=SITE_ENTITY_ID,
            action=action,
            revision=revision,
        )
    )


async def put_site(
    session: AsyncSession, actor: AdminPrincipal, data: SiteUpdate, *, now: datetime
) -> SiteView:
    async with session.begin():
        await session.execute(select(func.pg_advisory_xact_lock(CATALOG_LOCK_KEY)))
        row = await session.get(SiteSettings, 1, with_for_update=True, populate_existing=True)
        current = row.revision if row else 0
        if current != data.expected_revision:
            raise SiteConflict("The site content changed; reload before saving")
        if row is None:
            row = SiteSettings(id=1, revision=0)
            session.add(row)
        row.content = data.content.model_dump(mode="json")
        row.revision = current + 1
        row.updated_at = now
        _revoke(row)
        await discard_pending_replies(session)
        _audit(session, actor, "site.updated", row.revision)
        revision = row.revision
    return SiteView(revision=revision, content=data.content, updated_at=now)


async def approve_site(
    session: AsyncSession,
    actor: AdminPrincipal,
    data: SitePublish,
    *,
    now: datetime,
    media_origins: list[str],
) -> SiteView:
    if data.professional_id not in actor.reviewer_professional_ids:
        raise SiteForbidden("Reviewer is not assigned to this professional")
    async with session.begin():
        await session.execute(select(func.pg_advisory_xact_lock(CATALOG_LOCK_KEY)))
        row = await session.get(SiteSettings, 1, with_for_update=True, populate_existing=True)
        if row is None or row.revision != data.expected_revision:
            raise SiteConflict("The site content changed; reload before approving")
        reviewer = await session.get(Professional, data.professional_id, populate_existing=True)
        if reviewer is None or reviewer.credentials_verified_at is None:
            raise SiteConflict("Professional credentials are not verified")
        content = _content(row.content)
        if any(
            f"https://{urlsplit(photo.url).netloc}" not in media_origins for photo in content.photos
        ):
            raise SiteConflict("Photo origin is not configured for publication")
        if any(
            authorized_on > now.date()
            for authorized_on in [
                *(item.authorized_on for item in content.photos),
                *(item.authorized_on for item in content.testimonials),
            ]
        ):
            raise SiteConflict("Authorization date cannot be in the future")
        required_ids = {str(item.id) for item in await _required_reviewers(session)}
        retained = {
            key: value for key, value in (row.approvals or {}).items() if key in required_ids
        }
        if not _approved_by(row, reviewer) or retained != (row.approvals or {}):
            # A new/renewed review never republishes content implicitly.
            _clear_publication(row)
            row.approvals = {
                **retained,
                str(reviewer.id): {
                    "revision": row.revision,
                    "professional_revision": reviewer.revision,
                    "approved_by": actor.subject,
                    "approved_at": now.isoformat(),
                },
            }
            _audit(session, actor, "site.approved", row.revision)
    return await get_site(session, actor, media_origins=media_origins)


async def publish_site(
    session: AsyncSession,
    actor: AdminPrincipal,
    data: SitePublish,
    *,
    now: datetime,
    media_origins: list[str],
) -> SiteView:
    if data.professional_id not in actor.reviewer_professional_ids:
        raise SiteForbidden("Reviewer is not assigned to this professional")
    async with session.begin():
        await session.execute(select(func.pg_advisory_xact_lock(CATALOG_LOCK_KEY)))
        row = await session.get(SiteSettings, 1, with_for_update=True, populate_existing=True)
        if row is None or row.revision != data.expected_revision:
            raise SiteConflict("The site content changed; reload before publishing")
        reviewer = await session.get(Professional, data.professional_id, populate_existing=True)
        if reviewer is None or reviewer.credentials_verified_at is None:
            raise SiteConflict("Professional credentials are not verified")
        if not await _reviewed(session, row):
            raise SiteConflict("Every verified professional must approve the current revision")
        content = _content(row.content)
        if any(
            f"https://{urlsplit(photo.url).netloc}" not in media_origins for photo in content.photos
        ):
            raise SiteConflict("Photo origin is not configured for publication")
        if any(
            authorized_on > now.date()
            for authorized_on in [
                *(item.authorized_on for item in content.photos),
                *(item.authorized_on for item in content.testimonials),
            ]
        ):
            raise SiteConflict("Authorization date cannot be in the future")
        row.published_revision = row.revision
        row.published_by = actor.subject
        row.published_at = now
        row.reviewer_professional_id = reviewer.id
        row.reviewer_professional_revision = reviewer.revision
        _audit(session, actor, "site.published", row.revision)
    return await get_site(session, actor, media_origins=media_origins)


async def unpublish_site(
    session: AsyncSession, actor: AdminPrincipal, data: SiteVersion
) -> SiteView:
    async with session.begin():
        await session.execute(select(func.pg_advisory_xact_lock(CATALOG_LOCK_KEY)))
        row = await session.get(SiteSettings, 1, with_for_update=True, populate_existing=True)
        if row is None or row.revision != data.expected_revision:
            raise SiteConflict("The site content changed; reload before withdrawing")
        _revoke(row)
        await discard_pending_replies(session)
        _audit(session, actor, "site.unpublished", row.revision)
    return await get_site(session, actor)


async def approved_content(session: AsyncSession) -> SiteContent:
    async with session.begin():
        row = await session.get(SiteSettings, 1, populate_existing=True)
        return _content(row.content) if await _published(session, row) and row else SiteContent()


async def public_site(session: AsyncSession) -> PublicSite:
    content = await approved_content(session)
    return PublicSite(
        address=content.address,
        hours=content.hours,
        whatsapp=content.whatsapp,
        instagram=content.instagram,
        differentiators=content.differentiators,
        faq=content.faq,
        testimonials=[
            PublicTestimonial(quote=item.quote, author=item.author) for item in content.testimonials
        ],
        legal_contact=content.legal_contact,
        photos=[
            PublicPhoto(url=item.url, alt=item.alt, width=item.width, height=item.height)
            for item in content.photos
        ],
    )


async def deposit_instructions(session: AsyncSession) -> str | None:
    return (await approved_content(session)).deposit_instructions
