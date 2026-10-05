"""Evolution webhook and the panel's integration status (ADR-017).

The webhook is authenticated by a token Evolution sends in a custom header configured on the
instance (`Authorization: Bearer ...`); the instance name must match. Payloads are untrusted:
bounded size, tolerant parsing, nothing logged. Answering is fast; client messages are handled
in the background and swept by the worker if that fails.
"""

import hmac
import json
import logging
import uuid
from datetime import datetime
from typing import Annotated, Any, cast

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lumini.auth import require_admin
from lumini.deps import NO_STORE, get_now, get_sessions, no_store
from lumini.models import Conversation, IntegrationState
from lumini.settings import Settings
from lumini.whatsapp.bot import Channel, handle
from lumini.whatsapp.conversations import parse_messages, record, set_connection_state

logger = logging.getLogger(__name__)

MAX_BODY_BYTES = 1_000_000
Now = Annotated[datetime, Depends(get_now)]
Sessions = Annotated[async_sessionmaker[AsyncSession], Depends(get_sessions)]

webhook_router = APIRouter(
    prefix="/api/webhooks", tags=["webhooks"], dependencies=[Depends(no_store)]
)
admin_router = APIRouter(
    prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin), Depends(no_store)]
)


def _refuse(status: int) -> HTTPException:
    return HTTPException(status, "Webhook refused", headers=NO_STORE)


def _authenticate(request: Request, settings: Settings) -> None:
    token = settings.evolution_webhook_token
    header = request.headers.get("authorization", "")
    scheme, _, presented = header.partition(" ")
    if (
        token is None
        or scheme.lower() != "bearer"
        or not hmac.compare_digest(presented.encode(), token.get_secret_value().encode())
    ):
        raise _refuse(401)


async def _handle_later(
    app: FastAPI,
    sessions: async_sessionmaker[AsyncSession],
    conversation_ids: set[uuid.UUID],
    now: datetime,
) -> None:
    sender = getattr(app.state, "whatsapp", None)
    if sender is None:
        return
    channel = Channel(sender, getattr(app.state, "calendar", None), app.state.settings)
    for conversation_id in conversation_ids:
        try:
            async with sessions() as session:
                await handle(session, channel, conversation_id, now=now)
        except Exception as error:  # the worker sweep retries pending conversations
            logger.warning("whatsapp reply deferred: %s", type(error).__name__)


async def webhook_payload(request: Request) -> dict[str, Any]:
    """Everything about trusting the call happens here, before any other dependency."""
    settings = cast(Settings, request.app.state.settings)
    if not settings.whatsapp_configured():
        raise _refuse(404)
    _authenticate(request, settings)
    declared = request.headers.get("content-length", "0")
    if not declared.isdigit() or int(declared) > MAX_BODY_BYTES:
        raise _refuse(413)
    raw = await request.body()
    if len(raw) > MAX_BODY_BYTES:
        raise _refuse(413)
    try:
        payload: Any = json.loads(raw)
    except ValueError:
        raise _refuse(400) from None
    if not isinstance(payload, dict):
        raise _refuse(400)
    instance = payload.get("instance")
    if instance is not None and instance != settings.evolution_instance:
        raise _refuse(403)
    return payload


@webhook_router.post("/evolution")
async def evolution_webhook(
    payload: Annotated[dict[str, Any], Depends(webhook_payload)],
    request: Request,
    background: BackgroundTasks,
    sessions: Sessions,
    now: Now,
) -> dict[str, bool]:
    event = str(payload.get("event", "")).lower().replace("_", ".")
    data = payload.get("data")
    to_handle: set[uuid.UUID] = set()
    try:
        async with sessions() as session:
            if event in ("messages.upsert", "send.message"):
                to_handle = await record(session, parse_messages(data, now=now), now=now)
            elif event == "connection.update" and isinstance(data, dict):
                state = data.get("state")
                await set_connection_state(
                    session, state if isinstance(state, str) else "unknown", now=now
                )
            elif event == "qrcode.updated":
                await set_connection_state(session, "qr_required", now=now)
    except SQLAlchemyError:
        raise HTTPException(503, "Webhook unavailable", headers=NO_STORE) from None
    if to_handle:
        background.add_task(_handle_later, request.app, sessions, to_handle, now)
    return {"ok": True}


class WhatsAppStatus(BaseModel):
    configured: bool
    state: str | None
    needs_attention: bool
    changed_at: datetime | None
    human_mode_conversations: int


class IntegrationsView(BaseModel):
    whatsapp: WhatsAppStatus
    calendar_configured: bool
    self_service_configured: bool


@admin_router.get("/integrations", response_model=IntegrationsView)
async def integrations(request: Request, sessions: Sessions) -> IntegrationsView:
    settings = cast(Settings, request.app.state.settings)
    try:
        async with sessions() as session, session.begin():
            state = await session.get(IntegrationState, "whatsapp")
            human = await session.scalar(
                select(func.count()).select_from(Conversation).where(Conversation.mode == "human")
            )
    except SQLAlchemyError:
        raise HTTPException(503, "Status unavailable", headers=NO_STORE) from None
    configured = settings.whatsapp_configured()
    return IntegrationsView(
        whatsapp=WhatsAppStatus(
            configured=configured,
            state=state.state if state else None,
            # Configured but never heard from: someone must connect the instance.
            needs_attention=(state.needs_attention if state else configured),
            changed_at=state.changed_at if state else None,
            human_mode_conversations=int(human or 0),
        ),
        calendar_configured=getattr(request.app.state, "calendar", None) is not None,
        self_service_configured=settings.manage_link_secret is not None
        and settings.public_site_url is not None,
    )
