"""Web chat (plan §10 widget and attendance page).

A session is a random token kept by the browser in memory; the server stores only its hash as the
conversation id. Client text is never stored: each message runs the flow and the answer goes back
in the response. People asking for the team are sent to the contact form, since nobody watches
this channel live. Abandoned sessions are deleted by the worker after a day.
"""

import hashlib
import re
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlalchemy import and_, delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from lumini.deps import NO_STORE, get_now, get_session, no_store
from lumini.models import Conversation, WhatsAppMessage
from lumini.ratelimit import allow
from lumini.resources import Resources
from lumini.settings import Settings
from lumini.whatsapp import flow, texts

PREFIX = "web:"
SESSION_TTL = timedelta(hours=24)
SESSION_LIMIT = 20  # new sessions per client address, per 10 minutes
MESSAGE_LIMIT = 60  # messages per session, per 10 minutes
_TOKEN = re.compile(r"[A-Za-z0-9_-]{43}")
_bearer = HTTPBearer(auto_error=False)

WEB_HANDOFF = (
    "Esse assunto é com a equipe da Lumini. Deixe seu nome e WhatsApp em “Fale com a clínica” "
    "nesta página e a equipe chama você, sem precisar contar detalhes por aqui."
)
WEB_HEALTH_HANDOFF = (
    "Obrigada por avisar. Assuntos de saúde são conversados diretamente com a profissional. "
    "Deixe seu nome e WhatsApp em “Fale com a clínica” nesta página e a equipe chama você."
)

Session = Annotated[AsyncSession, Depends(get_session)]
Now = Annotated[datetime, Depends(get_now)]
router = APIRouter(prefix="/api/public/chat", tags=["public"], dependencies=[Depends(no_store)])


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    text: Annotated[str, StringConstraints(min_length=1, max_length=1000)]


class ChatReply(BaseModel):
    replies: list[str]
    options: list[str]  # quick replies: the numbered options of the last answer


class ChatSession(ChatReply):
    token: str


def _chat_id(token: str) -> str:
    return PREFIX + hashlib.sha256(token.encode()).hexdigest()[:40]


def _options(text: str) -> list[str]:
    return re.findall(r"^\d{1,2}\. (.+)$", text, flags=re.MULTILINE)


def _refuse(status: int, code: str) -> HTTPException:
    return HTTPException(status, {"code": code}, headers=NO_STORE)


async def _limited(request: Request, scope: str, identifier: str, limit: int) -> None:
    resources = cast(Resources | None, getattr(request.app.state, "resources", None))
    redis = resources.redis_client if resources is not None else None
    if not await allow(redis, scope, identifier, limit=limit, window_seconds=600):
        raise _refuse(429, "rate_limited")


@router.post("/session", status_code=201, response_model=ChatSession)
async def start(request: Request, session: Session, now: Now) -> ChatSession:
    client = request.client.host if request.client else "unknown"
    await _limited(
        request, "chat-session", hashlib.sha256(client.encode()).hexdigest(), SESSION_LIMIT
    )
    token = secrets.token_urlsafe(32)
    try:
        async with session.begin():
            session.add(
                Conversation(
                    id=uuid.uuid4(),
                    chat_id=_chat_id(token),
                    phone_e164=None,
                    state={"step": "menu"},
                    created_at=now,
                )
            )
    except SQLAlchemyError:
        raise _refuse(503, "chat_unavailable") from None
    return ChatSession(token=token, replies=[texts.MENU], options=_options(texts.MENU))


async def session_token(
    request: Request,
    authorization: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> str:
    """Resolved before any other dependency: a malformed token never reaches the database."""
    token = authorization.credentials if authorization else ""
    if not _TOKEN.fullmatch(token):
        raise _refuse(404, "session_invalid")
    await _limited(request, "chat-message", token, MESSAGE_LIMIT)
    return token


@router.post("/messages", response_model=ChatReply)
async def message(
    token: Annotated[str, Depends(session_token)],
    request: Request,
    session: Session,
    now: Now,
    data: ChatMessage,
) -> ChatReply:
    try:
        async with session.begin():
            conversation = await session.scalar(
                select(Conversation)
                .where(Conversation.chat_id == _chat_id(token))
                .execution_options(populate_existing=True)
            )
            if conversation is None or conversation.created_at < now - SESSION_TTL:
                raise _refuse(404, "session_invalid")
            conversation_id, version = conversation.id, conversation.version
            state = dict(conversation.state)
        settings = cast(Settings, request.app.state.settings)
        reply = await flow.step(
            flow.Context(
                session,
                getattr(request.app.state, "calendar", None),
                conversation_id,
                None,
                now,
                assistant=getattr(request.app.state, "assistant", None),
                high_confidence=settings.ai_high_confidence,
                medium_confidence=settings.ai_medium_confidence,
            ),
            state,
            data.text,
        )
        text, new_state = reply.text, reply.state
        if reply.handoff is not None:  # nobody watches this channel live: point to the form
            text = WEB_HEALTH_HANDOFF if reply.handoff == "health_condition" else WEB_HANDOFF
            new_state = {"step": "menu"}
        async with session.begin():
            current = await session.get(
                Conversation, conversation_id, with_for_update=True, populate_existing=True
            )
            if current is None or current.version != version:
                raise _refuse(409, "stale")  # two messages at once: the page resends
            current.state = new_state
            current.version += 1
    except SQLAlchemyError:
        raise _refuse(503, "chat_unavailable") from None
    return ChatReply(replies=[text], options=_options(text))


async def purge_sessions(session: AsyncSession, *, now: datetime) -> int:
    """Web sessions may hold a typed name until the hold is created; they expire a day after
    they start, so they are deleted then."""
    async with session.begin():
        result = await session.execute(
            delete(Conversation)
            .where(
                and_(
                    Conversation.chat_id.startswith(PREFIX),
                    Conversation.created_at < now - SESSION_TTL,
                    ~select(WhatsAppMessage.id)
                    .where(WhatsAppMessage.conversation_id == Conversation.id)
                    .exists(),
                )
            )
            .returning(Conversation.id)
        )
        return len(result.all())
