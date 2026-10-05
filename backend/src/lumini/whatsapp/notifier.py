"""Booking notifications over WhatsApp: the outbox's Notifier (ADR-017).

Each message is rebuilt from the booking right before sending and revalidated against the
conversation: in human mode nothing automatic is sent (the team is talking).
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from lumini.booking.dispatch import NotifierUnavailable
from lumini.booking.links import manage_url
from lumini.models import Booking, Contact, Conversation, Professional, Service
from lumini.settings import Settings
from lumini.site.service import deposit_instructions
from lumini.whatsapp import texts
from lumini.whatsapp.conversations import conversation_for, send_automatic, set_mode
from lumini.whatsapp.evolution import WhatsAppSender, WhatsAppUnavailable


def phone_variants(phone: str) -> list[str]:
    """Brazilian mobiles may be registered on WhatsApp with or without the ninth digit."""
    digits = phone.lstrip("+")
    variants = [phone]
    if digits.startswith("55") and len(digits) == 13 and digits[4] == "9":
        variants.append(f"+{digits[:4]}{digits[5:]}")
    elif digits.startswith("55") and len(digits) == 12:
        variants.append(f"+{digits[:4]}9{digits[4:]}")
    return variants


class WhatsAppNotifier:
    def __init__(
        self, session: AsyncSession, sender: WhatsAppSender, settings: Settings, *, now: datetime
    ) -> None:
        self._session = session
        self._sender = sender
        self._settings = settings
        self._now = now

    async def _conversation(self, phone: str) -> uuid.UUID:
        async with self._session.begin():
            existing = await self._session.scalar(
                select(Conversation.id)
                .where(or_(*(Conversation.phone_e164 == item for item in phone_variants(phone))))
                .order_by(Conversation.updated_at.desc())
                .limit(1)
            )
            if existing is not None:
                return existing
            created = await conversation_for(
                self._session, f"{phone.lstrip('+')}@s.whatsapp.net", phone
            )
            return created.id

    async def send(self, event: str, booking_id: uuid.UUID) -> str | None:
        """None when delivered; otherwise a short note for the outbox (never retried)."""
        async with self._session.begin():
            row = (
                (
                    await self._session.execute(
                        select(
                            Booking,
                            Contact.phone_e164,
                            Service.name,
                            Service.content,
                            Professional.display_name,
                        )
                        .join(Contact, Contact.id == Booking.contact_id)
                        .join(Service, Service.id == Booking.service_id)
                        .join(Professional, Professional.id == Booking.professional_id)
                        .where(Booking.id == booking_id)
                        .execution_options(populate_existing=True)
                    )
                )
                .tuples()
                .first()
            )
        if row is None:
            return "missing"
        booking, phone, service_name, content, professional_name = row
        values: dict[str, Any] = {
            "service": service_name,
            "professional": professional_name,
            "day": texts.day(booking.starts_at),
            "time": texts.time(booking.starts_at),
            "deadline": texts.time(booking.expires_at) if booking.expires_at else "",
            "deposit": texts.money(booking.deposit_brl),
        }
        if event == "manage_link":
            link = manage_url(self._settings, booking)
            if link is None:
                return "links_not_configured"
            values["link"] = link
        if event == "aftercare":
            # Only the approved aftercare of the published content; nothing generated.
            items = content.get("aftercare") if isinstance(content, dict) else None
            if not items:
                return "no_aftercare"
            values["aftercare"] = "\n".join(f"• {item}" for item in items)
        if event == "deposit_instructions":
            instructions = await deposit_instructions(self._session)
            if instructions:
                values["instructions"] = instructions
        key = (
            "deposit_instructions_configured"
            if event == "deposit_instructions" and "instructions" in values
            else event
        )
        template = texts.NOTIFICATIONS.get(key)
        if template is None:
            return "unknown_event"
        conversation_id = await self._conversation(phone)
        try:
            result = await send_automatic(
                self._session,
                self._sender,
                conversation_id,
                template.format(**values),
                purpose=event,
                dedupe_key=f"notify:{event}:{booking_id}",
                now=self._now,
            )
        except WhatsAppUnavailable:
            raise NotifierUnavailable("whatsapp_unavailable") from None
        if result == "skipped_wait":
            raise NotifierUnavailable("possible_human_reply")  # retry after it settles
        if result in ("sent", "duplicate"):
            if event == "human_handoff":
                async with self._session.begin():
                    conversation = await self._session.get(
                        Conversation, conversation_id, with_for_update=True
                    )
                    if conversation is not None:
                        set_mode(conversation, "human", "booking_handoff", self._now)
            return None
        return {"skipped_human": "human_mode", "rejected": "rejected"}.get(result, result)
