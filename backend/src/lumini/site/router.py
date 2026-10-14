"""Panel editing of site content and the public read used by the website."""

from datetime import datetime
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from lumini.auth import AdminPrincipal, require_admin
from lumini.deps import NO_STORE, get_now, get_session, no_store
from lumini.settings import Settings
from lumini.site.service import (
    PublicSite,
    SiteConflict,
    SiteForbidden,
    SitePublish,
    SiteUpdate,
    SiteVersion,
    SiteView,
    approve_site,
    get_site,
    public_site,
    publish_site,
    put_site,
    unpublish_site,
)

Session = Annotated[AsyncSession, Depends(get_session)]
Admin = Annotated[AdminPrincipal, Depends(require_admin)]
Now = Annotated[datetime, Depends(get_now)]

admin_router = APIRouter(
    prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin), Depends(no_store)]
)
public_router = APIRouter(prefix="/api/public", tags=["public"])


def _unavailable() -> HTTPException:
    return HTTPException(503, "Site content unavailable", headers=NO_STORE)


@admin_router.get("/site", response_model=SiteView)
async def read(actor: Admin, request: Request, session: Session) -> SiteView:
    try:
        settings = cast(Settings, request.app.state.settings)
        return await get_site(session, actor, media_origins=settings.media_origins)
    except SQLAlchemyError:
        raise _unavailable() from None


@admin_router.put("/site", response_model=SiteView)
async def save(actor: Admin, session: Session, now: Now, data: SiteUpdate) -> SiteView:
    try:
        return await put_site(session, actor, data, now=now)
    except SiteConflict:
        raise HTTPException(409, "The site content changed; reload", headers=NO_STORE) from None
    except SQLAlchemyError:
        raise _unavailable() from None


@admin_router.post("/site/publish", response_model=SiteView)
async def publish(
    actor: Admin, request: Request, session: Session, now: Now, data: SitePublish
) -> SiteView:
    try:
        settings = cast(Settings, request.app.state.settings)
        return await publish_site(
            session, actor, data, now=now, media_origins=settings.media_origins
        )
    except SiteForbidden:
        raise HTTPException(403, "Reviewer assignment required", headers=NO_STORE) from None
    except SiteConflict as exc:
        raise HTTPException(409, str(exc), headers=NO_STORE) from None
    except SQLAlchemyError:
        raise _unavailable() from None


@admin_router.post("/site/approve", response_model=SiteView)
async def approve(
    actor: Admin, request: Request, session: Session, now: Now, data: SitePublish
) -> SiteView:
    try:
        settings = cast(Settings, request.app.state.settings)
        return await approve_site(
            session, actor, data, now=now, media_origins=settings.media_origins
        )
    except SiteForbidden:
        raise HTTPException(403, "Reviewer assignment required", headers=NO_STORE) from None
    except SiteConflict as exc:
        raise HTTPException(409, str(exc), headers=NO_STORE) from None
    except SQLAlchemyError:
        raise _unavailable() from None


@admin_router.post("/site/unpublish", response_model=SiteView)
async def withdraw(actor: Admin, session: Session, data: SiteVersion) -> SiteView:
    try:
        return await unpublish_site(session, actor, data)
    except SiteConflict:
        raise HTTPException(409, "The site content changed; reload", headers=NO_STORE) from None
    except SQLAlchemyError:
        raise _unavailable() from None


@public_router.get("/site", response_model=PublicSite)
async def public(response: Response, session: Session) -> PublicSite:
    # Credential changes or edits revoke review immediately; do not cache revoked content.
    response.headers.update(NO_STORE)
    try:
        return await public_site(session)
    except SQLAlchemyError:
        raise _unavailable() from None
