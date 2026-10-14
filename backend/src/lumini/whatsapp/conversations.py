"""Conversation bookkeeping: webhook intake, human mode and guarded automatic sends (ADR-017).

Who wrote a `fromMe` message? Evolution reports messages sent through the API exactly like the
ones typed on the clinic's phone, so `fromMe` alone proves nothing (ADR-008). A `fromMe` message
is the bot's only if its id is one we got back from our own send; otherwise it is staff, and the
conversation enters human mode. While one of our sends is still in flight the message is held as
`unknown` and settled after a grace period, and automatic sends wait meanwhile.

Text: client text is kept only until it is handled; outgoing text is never stored; nothing here
logs ids, phone numbers or message content.
"""

import re
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import object_session

from lumini.models import Conversation, IntegrationState, WhatsAppMessage
from lumini.whatsapp.evolution import WhatsAppRejected, WhatsAppSender, WhatsAppUnavailable
from lumini.whatsapp.history import remember

HISTORY_CUTOFF = timedelta(hours=24)  # older webhook replays (history sync) are ignored
SEND_GRACE = timedelta(seconds=60)  # longer than a send can take (client timeout ~18 s)
MAX_TEXT = 2000
RESUME = "#bot"
PAUSE = {"#pausa", "#humano"}

_PERSONAL = re.compile(r"(\d{8,15})@s\.whatsapp\.net")
_SKIPPED_SUFFIXES = ("@g.us", "@broadcast", "@newsletter")


@dataclass(frozen=True)
class Incoming:
    provider_id: str
    chat_id: str
    phone: str | None
    from_me: bool
    text: str | None  # None for media, stickers, reactions...
    occurred_at: datetime


def _text(message: Any) -> str | None:
    if not isinstance(message, dict):
        return None
    for value in (
        message.get("conversation"),
        (message.get("extendedTextMessage") or {}).get("text")
        if isinstance(message.get("extendedTextMessage"), dict)
        else None,
    ):
        if isinstance(value, str) and value.strip():
            return value.strip()[:MAX_TEXT]
    return None


def _phone(*jids: Any) -> str | None:
    for jid in jids:
        match = _PERSONAL.fullmatch(jid) if isinstance(jid, str) else None
        if match:
            return f"+{match.group(1)}"
    return None


def parse_messages(data: Any, *, now: datetime) -> list[Incoming]:
    """Tolerant reading of messages.upsert / send.message `data` (object or list)."""
    items = data if isinstance(data, list) else [data]
    result: list[Incoming] = []
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("key"), dict):
            continue
        key = item["key"]
        chat_id, provider_id = key.get("remoteJid"), key.get("id")
        if (
            not isinstance(chat_id, str)
            or not isinstance(provider_id, str)
            or not 1 <= len(provider_id) <= 128
            or not 3 <= len(chat_id) <= 80
            or chat_id.endswith(_SKIPPED_SUFFIXES)
            or chat_id.startswith("status@")
        ):
            continue
        stamp = item.get("messageTimestamp")
        try:
            occurred = datetime.fromtimestamp(int(stamp), UTC) if stamp is not None else now
        except (TypeError, ValueError, OverflowError):
            occurred = now
        result.append(
            Incoming(
                provider_id=provider_id,
                chat_id=chat_id,
                phone=_phone(chat_id, key.get("senderPn"), key.get("remoteJidAlt")),
                from_me=key.get("fromMe") is True,
                text=_text(item.get("message")),
                occurred_at=min(occurred, now),
            )
        )
    return result


async def conversation_for(session: AsyncSession, chat_id: str, phone: str | None) -> Conversation:
    """Existing or new conversation, locked for this transaction."""
    await session.execute(
        insert(Conversation)
        .values(id=uuid.uuid4(), chat_id=chat_id, phone_e164=phone, state={})
        .on_conflict_do_nothing(index_elements=[Conversation.chat_id])
    )
    found = await session.scalar(
        select(Conversation)
        .where(Conversation.chat_id == chat_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if found is None:  # pragma: no cover - inserted above
        raise RuntimeError("conversation missing")
    if phone and not found.phone_e164:
        found.phone_e164 = phone
    return found


def set_mode(
    conversation: Conversation, mode: Literal["bot", "human"], reason: str | None, now: datetime
) -> None:
    """Every switch bumps the version, so text queued for the old mode is never sent."""
    if conversation.mode == mode:
        return
    conversation.mode = mode
    conversation.mode_reason = reason
    conversation.mode_changed_at = now
    conversation.version += 1
    session = object_session(conversation)
    if session is not None:
        remember(session, conversation, mode, now, reason=reason)


async def _send_in_flight(session: AsyncSession, conversation_id: uuid.UUID, now: datetime) -> bool:
    found = await session.scalar(
        select(WhatsAppMessage.id)
        .where(
            WhatsAppMessage.conversation_id == conversation_id,
            WhatsAppMessage.direction == "out",
            WhatsAppMessage.status == "sending",
            WhatsAppMessage.occurred_at > now - SEND_GRACE,
        )
        .limit(1)
    )
    return found is not None


async def record(
    session: AsyncSession, items: Iterable[Incoming], *, now: datetime
) -> set[uuid.UUID]:
    """Store webhook messages once each; returns conversations with new client text to handle."""
    to_handle: set[uuid.UUID] = set()
    async with session.begin():
        for item in items:
            if item.occurred_at < now - HISTORY_CUTOFF:
                continue
            try:
                # One savepoint per message: a race with our own send's echo drops only it.
                async with session.begin_nested():
                    handled = await _record_one(session, item, now)
            except IntegrityError:
                continue  # same provider id stored concurrently: already accounted for
            if handled is not None:
                to_handle.add(handled)
    return to_handle


async def _record_one(session: AsyncSession, item: Incoming, now: datetime) -> uuid.UUID | None:
    known = await session.scalar(
        select(WhatsAppMessage.id).where(WhatsAppMessage.provider_id == item.provider_id)
    )
    if known is not None:
        return None  # webhook retry, or the echo of a message we sent
    conversation = await conversation_for(session, item.chat_id, item.phone)
    command = (item.text or "").strip().lower()
    if item.from_me:
        origin, status = "staff", "handled"
        if command == RESUME:
            set_mode(conversation, "bot", None, now)
            conversation.state = {}
        elif command in PAUSE:
            set_mode(conversation, "human", "pause_command", now)
        elif await _send_in_flight(session, conversation.id, now):
            origin, status = "unknown", "pending"  # maybe our own echo: settle later
        else:
            set_mode(conversation, "human", "manual_reply", now)
        session.add(_row(conversation, item, now, origin=origin, status=status, body=None))
        await session.flush()
        return None
    conversation.version += 1  # newer client text makes queued replies stale
    session.add(
        _row(
            conversation,
            item,
            now,
            origin="client",
            status="pending",
            body=item.text if item.text is not None else "",
        )
    )
    await session.flush()
    return conversation.id


def _row(
    conversation: Conversation,
    item: Incoming,
    now: datetime,
    *,
    origin: str,
    status: str,
    body: str | None,
) -> WhatsAppMessage:
    return WhatsAppMessage(
        id=uuid.uuid4(),
        conversation_id=conversation.id,
        provider_id=item.provider_id,
        direction="in",
        origin=origin,
        body=body,
        conversation_version=conversation.version,
        status=status,
        occurred_at=item.occurred_at,
        created_at=now,  # receipt time on the application clock (grace periods use it)
    )


async def settle_unknown(session: AsyncSession, *, now: datetime) -> int:
    """`fromMe` messages that never matched one of our sends were typed by staff."""
    async with session.begin():
        rows = list(
            await session.scalars(
                select(WhatsAppMessage)
                .where(
                    WhatsAppMessage.origin == "unknown",
                    WhatsAppMessage.created_at <= now - SEND_GRACE,
                )
                .with_for_update(skip_locked=True)
            )
        )
        for row in rows:
            conversation = await session.get(
                Conversation, row.conversation_id, with_for_update=True
            )
            row.origin, row.status = "staff", "handled"
            if conversation is not None:
                set_mode(conversation, "human", "manual_reply", now)
    return len(rows)


SendResult = Literal[
    "sent", "skipped_human", "skipped_stale", "skipped_wait", "duplicate", "rejected"
]


async def send_automatic(
    session: AsyncSession,
    sender: WhatsAppSender,
    conversation_id: uuid.UUID,
    text: str,
    *,
    purpose: str,
    dedupe_key: str,
    now: datetime,
    expected_version: int | None = None,
    allow_human: bool = False,
    keep_text: bool = False,
) -> SendResult:
    """Revalidate mode/version right before sending (ADR-008), then remember the provider id.

    Raises WhatsAppUnavailable for transient failures so callers can retry with the same key.
    """
    async with session.begin():
        conversation = await session.get(
            Conversation, conversation_id, with_for_update=True, populate_existing=True
        )
        if conversation is None:
            return "skipped_stale"
        if conversation.mode == "human" and not allow_human:
            return "skipped_human"
        if expected_version is not None and conversation.version != expected_version:
            return "skipped_stale"
        waiting = await session.scalar(
            select(WhatsAppMessage.id)
            .where(
                WhatsAppMessage.conversation_id == conversation_id,
                WhatsAppMessage.origin == "unknown",
            )
            .limit(1)
        )
        if waiting is not None and not allow_human:
            return "skipped_wait"  # someone may be typing on the clinic's phone right now
        existing = await session.scalar(
            select(WhatsAppMessage)
            .where(WhatsAppMessage.dedupe_key == dedupe_key)
            .with_for_update()
        )
        if existing is not None and existing.status in ("sent", "sending"):
            return "duplicate"
        if existing is not None and keep_text and existing.status == "skipped":
            return "skipped_stale"  # withdrawn reviewed content must never be resurrected
        if existing is None:
            existing = WhatsAppMessage(
                id=uuid.uuid4(),
                conversation_id=conversation_id,
                dedupe_key=dedupe_key,
                direction="out",
                origin="bot",
                purpose=purpose,
                conversation_version=conversation.version,
                status="sending",
                occurred_at=now,
            )
            session.add(existing)
        else:
            existing.status, existing.occurred_at = "sending", now
        existing.body = text if keep_text else None  # a reply waits here for a retry
        outgoing_id, chat_id = existing.id, conversation.chat_id
    try:
        provider_id = await sender.send_text(chat_id, text)
    except WhatsAppRejected:
        await _finish(session, outgoing_id, now, status="failed", keep_body=False)  # no retry
        return "rejected"
    except WhatsAppUnavailable:
        await _finish(session, outgoing_id, now, status="failed")
        raise
    await _finish(session, outgoing_id, now, status="sent", provider_id=provider_id)
    return "sent"


async def _finish(
    session: AsyncSession,
    outgoing_id: uuid.UUID,
    now: datetime,
    *,
    status: str,
    provider_id: str | None = None,
    keep_body: bool = True,
) -> None:
    async with session.begin():
        if provider_id is not None:
            # Its webhook echo may already be stored as `unknown`: it was ours after all.
            await session.execute(
                delete(WhatsAppMessage).where(
                    WhatsAppMessage.provider_id == provider_id,
                    WhatsAppMessage.direction == "in",
                    WhatsAppMessage.origin == "unknown",
                )
            )
        values: dict[str, Any] = {"status": status, "provider_id": provider_id}
        if status != "failed" or not keep_body:
            values["body"] = None
        await session.execute(
            update(WhatsAppMessage).where(WhatsAppMessage.id == outgoing_id).values(**values)
        )
        if status == "sent":
            await _settle_after_send(session, outgoing_id, now)


async def _settle_after_send(session: AsyncSession, outgoing_id: uuid.UUID, now: datetime) -> None:
    """Our send is done and its echo is accounted for: if no other send of ours is in flight,
    the remaining `unknown` messages cannot be ours, so staff typed them. No need to wait."""
    conversation_id = await session.scalar(
        select(WhatsAppMessage.conversation_id).where(WhatsAppMessage.id == outgoing_id)
    )
    if conversation_id is None:
        return
    other = await session.scalar(
        select(WhatsAppMessage.id)
        .where(
            WhatsAppMessage.conversation_id == conversation_id,
            WhatsAppMessage.direction == "out",
            WhatsAppMessage.status == "sending",
        )
        .limit(1)
    )
    if other is not None:
        return
    unknown = list(
        await session.scalars(
            select(WhatsAppMessage)
            .where(
                WhatsAppMessage.conversation_id == conversation_id,
                WhatsAppMessage.origin == "unknown",
            )
            .with_for_update()
        )
    )
    if not unknown:
        return
    conversation = await session.get(
        Conversation, conversation_id, with_for_update=True, populate_existing=True
    )
    for row in unknown:
        row.origin, row.status = "staff", "handled"
    if conversation is not None:
        set_mode(conversation, "human", "manual_reply", now)


REPLY_RETRY_WINDOW = timedelta(minutes=30)


async def discard_pending_replies(session: AsyncSession) -> None:
    """Inside the content mutation's transaction, withdraw queued replies conservatively.

    Responses can include approved catalog facts as well as site templates. A content or
    credential change discards all failed/pending replies; the next client message uses the
    current reviewed content. Bumping versions also invalidates replies still being generated.
    Notifications are reconstructed from the current state. Modes remain unchanged.
    """
    await session.execute(update(Conversation).values(version=Conversation.version + 1))
    await session.execute(
        update(WhatsAppMessage)
        .where(
            WhatsAppMessage.direction == "out",
            WhatsAppMessage.purpose == "reply",
            WhatsAppMessage.status.in_(("failed", "pending")),
            WhatsAppMessage.body.is_not(None),
        )
        .values(status="skipped", body=None)
    )


async def retry_failed_replies(
    session: AsyncSession, sender: WhatsAppSender, *, now: datetime
) -> int:
    """Resend replies that failed during an outage, only if the conversation did not move on."""
    async with session.begin():
        rows = (
            await session.execute(
                select(
                    WhatsAppMessage.conversation_id,
                    WhatsAppMessage.dedupe_key,
                    WhatsAppMessage.body,
                    WhatsAppMessage.conversation_version,
                    WhatsAppMessage.occurred_at,
                    WhatsAppMessage.id,
                ).where(
                    WhatsAppMessage.direction == "out",
                    WhatsAppMessage.purpose == "reply",
                    WhatsAppMessage.status == "failed",
                    WhatsAppMessage.body.is_not(None),
                )
            )
        ).all()
    sent = 0
    for conversation_id, dedupe_key, body, version, occurred_at, row_id in rows:
        if occurred_at < now - REPLY_RETRY_WINDOW or dedupe_key is None or body is None:
            async with session.begin():
                await session.execute(
                    update(WhatsAppMessage)
                    .where(WhatsAppMessage.id == row_id)
                    .values(status="skipped", body=None)
                )
            continue
        try:
            result = await send_automatic(
                session,
                sender,
                conversation_id,
                body,
                purpose="reply",
                dedupe_key=dedupe_key,
                now=now,
                expected_version=version,
                keep_text=True,
            )
        except WhatsAppUnavailable:
            break  # still down: try again next cycle
        if result == "sent":
            sent += 1
        elif result in ("skipped_human", "skipped_stale"):
            async with session.begin():
                await session.execute(
                    update(WhatsAppMessage)
                    .where(WhatsAppMessage.id == row_id)
                    .values(status="skipped", body=None)
                )
    return sent


async def set_connection_state(
    session: AsyncSession, state: str, *, now: datetime, detail: str | None = None
) -> None:
    """open → healthy; anything else needs a person (reconnect or scan a new QR code)."""
    normalized = state if state in ("open", "close", "connecting", "qr_required") else "unknown"
    attention = normalized != "open"
    async with session.begin():
        await session.execute(
            insert(IntegrationState)
            .values(
                name="whatsapp",
                state=normalized,
                detail=detail,
                needs_attention=attention,
                changed_at=now,
            )
            .on_conflict_do_update(
                index_elements=[IntegrationState.name],
                set_={
                    "state": normalized,
                    "detail": detail,
                    "needs_attention": attention,
                    "changed_at": now,
                },
            )
        )
