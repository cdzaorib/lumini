"""Answer client messages: read pending text, run the flow, revalidate, send (ADR-017)."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lumini.booking.calendar import CalendarAdapter
from lumini.models import Conversation, WhatsAppMessage
from lumini.settings import Settings
from lumini.whatsapp import flow
from lumini.whatsapp.conversations import SendResult, send_automatic, set_mode
from lumini.whatsapp.evolution import WhatsAppSender


@dataclass(frozen=True)
class Channel:
    sender: WhatsAppSender
    calendar: CalendarAdapter | None
    settings: Settings


async def handle(
    session: AsyncSession, channel: Channel, conversation_id: uuid.UUID, *, now: datetime
) -> SendResult | str:
    async with session.begin():
        conversation = await session.get(
            Conversation, conversation_id, with_for_update=True, populate_existing=True
        )
        if conversation is None:
            return "missing"
        pending = list(
            await session.scalars(
                select(WhatsAppMessage)
                .where(
                    WhatsAppMessage.conversation_id == conversation_id,
                    WhatsAppMessage.origin == "client",
                    WhatsAppMessage.status == "pending",
                )
                .order_by(WhatsAppMessage.occurred_at, WhatsAppMessage.created_at)
            )
        )
        if not pending:
            return "nothing"
        latest = pending[-1].body or None
        version, mode = conversation.version, conversation.mode
        state, phone = dict(conversation.state), conversation.phone_e164
        for row in pending:  # client text is not kept once read
            row.status, row.body = "handled", None
    if mode == "human":
        return "skipped_human"  # the team is talking; nothing automatic is said

    reply = await flow.step(
        flow.Context(session, channel.calendar, conversation_id, phone, now), state, latest
    )

    async with session.begin():
        conversation = await session.get(
            Conversation, conversation_id, with_for_update=True, populate_existing=True
        )
        if conversation is None or conversation.version != version or conversation.mode != "bot":
            return "skipped_stale"  # a newer message or the team took over meanwhile
        conversation.state = reply.state
        if reply.opt_out:
            conversation.marketing_opt_out_at = now
        if reply.handoff is not None:
            set_mode(conversation, "human", reply.handoff, now)
        send_version = conversation.version
    return await send_automatic(
        session,
        channel.sender,
        conversation_id,
        reply.text,
        purpose="reply",
        dedupe_key=f"reply:{conversation_id}:{version}",
        now=now,
        expected_version=send_version,
        allow_human=reply.handoff is not None,  # the handoff notice itself still goes out
        keep_text=True,
    )


STALE_PENDING = timedelta(seconds=30)


async def pending_conversations(
    session: AsyncSession, *, now: datetime, limit: int = 50
) -> list[uuid.UUID]:
    """Safety net for the webhook fast path: conversations with unread client text."""
    async with session.begin():
        rows = await session.scalars(
            select(WhatsAppMessage.conversation_id)
            .where(
                WhatsAppMessage.origin == "client",
                WhatsAppMessage.status == "pending",
                WhatsAppMessage.created_at <= now - STALE_PENDING,
            )
            .distinct()
            .limit(limit)
        )
        return list(rows)
