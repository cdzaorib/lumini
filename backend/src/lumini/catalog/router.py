"""Catalog HTTP boundary. Every /api/admin route authenticates before a database session opens."""

from collections.abc import Awaitable, Callable
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from lumini.auth import AdminPrincipal, require_admin
from lumini.catalog import service as catalog
from lumini.catalog.schemas import (
    ApprovalRequest,
    ProfessionalCreate,
    ProfessionalUpdate,
    ProfessionalView,
    PublicService,
    ServiceCreate,
    ServiceUpdate,
    ServiceView,
    VersionRequest,
)
from lumini.deps import NO_STORE, get_session, no_store

Admin = Annotated[AdminPrincipal, Depends(require_admin)]
Session = Annotated[AsyncSession, Depends(get_session)]

_ERRORS: tuple[tuple[type[Exception], int, str | None], ...] = (
    (catalog.CatalogNotFound, 404, None),
    (catalog.CatalogForbidden, 403, None),
    (catalog.CatalogConflict, 409, None),
    (IntegrityError, 409, "Conflicting catalog change"),
    # Driver exceptions may contain SQL or connection details; never echo them.
    (SQLAlchemyError, 503, "Catalog unavailable"),
)


async def _transaction[T](session: AsyncSession, operation: Callable[[], Awaitable[T]]) -> T:
    """Run inside one transaction; any refusal rolls back every partial change."""
    try:
        async with session.begin():
            return await operation()
    except Exception as error:
        for error_type, status, message in _ERRORS:
            if isinstance(error, error_type):
                detail = message if message is not None else str(error)
                raise HTTPException(status, detail, headers=NO_STORE) from None
        raise


admin_router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin), Depends(no_store)],
)
public_router = APIRouter(prefix="/api/catalog", tags=["catalog"])


class AdminIdentity(BaseModel):
    subject: str
    email: str
    reviewer_professional_ids: list[UUID]


@admin_router.get("/me", response_model=AdminIdentity)
async def me(actor: Admin) -> AdminIdentity:
    return AdminIdentity(
        subject=actor.subject,
        email=actor.email,
        reviewer_professional_ids=list(actor.reviewer_professional_ids),
    )


@admin_router.get("/professionals", response_model=list[ProfessionalView])
async def list_professionals(actor: Admin, session: Session) -> list[ProfessionalView]:
    return await _transaction(session, lambda: catalog.list_professionals(session))


@admin_router.post("/professionals", status_code=201, response_model=ProfessionalView)
async def create_professional(
    actor: Admin, session: Session, data: ProfessionalCreate
) -> ProfessionalView:
    return await _transaction(session, lambda: catalog.create_professional(session, actor, data))


@admin_router.patch("/professionals/{professional_id}", response_model=ProfessionalView)
async def update_professional(
    actor: Admin, session: Session, professional_id: UUID, data: ProfessionalUpdate
) -> ProfessionalView:
    return await _transaction(
        session, lambda: catalog.update_professional(session, actor, professional_id, data)
    )


@admin_router.post("/professionals/{professional_id}/{action}", response_model=ProfessionalView)
async def change_professional_verification(
    actor: Admin,
    session: Session,
    professional_id: UUID,
    action: Literal["verify", "revoke"],
    data: VersionRequest,
) -> ProfessionalView:
    operation = catalog.verify_professional if action == "verify" else catalog.revoke_professional
    return await _transaction(session, lambda: operation(session, actor, professional_id, data))


@admin_router.get("/services", response_model=list[ServiceView])
async def list_services(actor: Admin, session: Session) -> list[ServiceView]:
    return await _transaction(session, lambda: catalog.list_services(session))


@admin_router.post("/services", status_code=201, response_model=ServiceView)
async def create_service(actor: Admin, session: Session, data: ServiceCreate) -> ServiceView:
    return await _transaction(session, lambda: catalog.create_service(session, actor, data))


@admin_router.patch("/services/{service_id}", response_model=ServiceView)
async def update_service(
    actor: Admin, session: Session, service_id: UUID, data: ServiceUpdate
) -> ServiceView:
    return await _transaction(
        session, lambda: catalog.update_service(session, actor, service_id, data)
    )


@admin_router.post("/services/{service_id}/approve", response_model=ServiceView)
async def approve_service(
    actor: Admin, session: Session, service_id: UUID, data: ApprovalRequest
) -> ServiceView:
    return await _transaction(
        session, lambda: catalog.approve_service(session, actor, service_id, data)
    )


@admin_router.post("/services/{service_id}/{action}", response_model=ServiceView)
async def change_service_publication(
    actor: Admin,
    session: Session,
    service_id: UUID,
    action: Literal["publish", "unpublish"],
    data: VersionRequest,
) -> ServiceView:
    operation = catalog.publish_service if action == "publish" else catalog.unpublish_service
    return await _transaction(session, lambda: operation(session, actor, service_id, data))


@public_router.get("/services", response_model=list[PublicService])
async def public_services(response: Response, session: Session) -> list[PublicService]:
    response.headers.update(NO_STORE)
    return await _transaction(session, lambda: catalog.list_public_services(session))
