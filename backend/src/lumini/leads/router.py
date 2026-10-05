"""Public lead form and the panel's lead list."""

import hashlib
import uuid
from datetime import datetime
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from lumini.auth import require_admin
from lumini.deps import NO_STORE, get_now, get_session, no_store
from lumini.leads.service import (
    LeadCreate,
    LeadStatus,
    LeadView,
    Status,
    create_lead,
    list_leads,
    set_status,
)
from lumini.ratelimit import allow
from lumini.resources import Resources

Session = Annotated[AsyncSession, Depends(get_session)]
Now = Annotated[datetime, Depends(get_now)]
FORM_LIMIT = 5  # per client address, per 10 minutes

public_router = APIRouter(prefix="/api/public", tags=["public"], dependencies=[Depends(no_store)])
admin_router = APIRouter(
    prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin), Depends(no_store)]
)


def _unavailable() -> HTTPException:
    return HTTPException(503, "Leads unavailable", headers=NO_STORE)


async def _limited(request: Request) -> None:
    """Behind the platform proxy every request may share an address; the limit is a speed bump
    against floods, not identification. Only a hash is kept."""
    resources = cast(Resources | None, getattr(request.app.state, "resources", None))
    client = request.client.host if request.client else "unknown"
    key = hashlib.sha256(client.encode()).hexdigest()
    redis = resources.redis_client if resources is not None else None
    if not await allow(redis, "lead-form", key, limit=FORM_LIMIT, window_seconds=600):
        raise HTTPException(429, "Too many requests", headers=NO_STORE)


@public_router.post("/leads", status_code=201)
async def submit(request: Request, session: Session, now: Now, data: LeadCreate) -> dict[str, bool]:
    await _limited(request)
    try:
        await create_lead(session, data, source="site_form", now=now)
    except SQLAlchemyError:
        raise _unavailable() from None
    return {"ok": True}  # same answer for kept, refreshed and trapped submissions


@admin_router.get("/leads", response_model=list[LeadView])
async def leads(session: Session, status: Status | None = "new") -> list[LeadView]:
    try:
        return await list_leads(session, status)
    except SQLAlchemyError:
        raise _unavailable() from None


@admin_router.post("/leads/{lead_id}/status", status_code=204)
async def change_status(
    session: Session, now: Now, lead_id: uuid.UUID, data: LeadStatus
) -> Response:
    try:
        found = await set_status(session, lead_id, data.status, now=now)
    except SQLAlchemyError:
        raise _unavailable() from None
    if not found:
        raise HTTPException(404, "Lead not found", headers=NO_STORE)
    return Response(status_code=204, headers=NO_STORE)
