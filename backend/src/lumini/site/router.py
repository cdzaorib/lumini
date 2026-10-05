"""Panel editing of site content and the public read used by the website."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from lumini.auth import AdminPrincipal, require_admin
from lumini.deps import NO_STORE, get_now, get_session, no_store
from lumini.site.service import (
    PublicSite,
    SiteConflict,
    SiteUpdate,
    SiteView,
    get_site,
    public_site,
    put_site,
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
async def read(session: Session) -> SiteView:
    try:
        return await get_site(session)
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


@public_router.get("/site", response_model=PublicSite)
async def public(response: Response, session: Session) -> PublicSite:
    # Shared facts only; a short cache keeps the landing fast without hiding edits for long.
    response.headers["Cache-Control"] = "public, max-age=60"
    try:
        return await public_site(session)
    except SQLAlchemyError:
        raise _unavailable() from None
