"""Structured conversation progress and mode history; never message bodies or contact data."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from lumini.models import Base, Conversation

REASONS = {
    "requested",
    "health_condition",
    "evaluation",
    "calendar_not_configured",
    "agenda_unavailable",
    "no_phone",
    "booking_refused",
    "booking_handoff",
    "pause_command",
    "manual_reply",
    "no_catalog",
}
STEPS = {
    "menu",
    "categories",
    "services",
    "service",
    "health",
    "professional",
    "days",
    "times",
    "name",
    "phone",
    "confirm",
    "clarify",
}


class ConversationEvent(Base):
    __tablename__ = "conversation_events"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('progress', 'human', 'bot', 'handoff')", name="ck_conversation_events_kind"
        ),
        Index("ix_conversation_events_conversation_time", "conversation_id", "occurred_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(String(10))
    reason: Mapped[str | None] = mapped_column(String(30))
    version: Mapped[int] = mapped_column(Integer)
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def minimal_summary(state: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    step = state.get("step")
    if isinstance(step, str) and step in STEPS:
        result["step"] = step
    for key in ("service_id", "professional_id"):
        value = state.get(key)
        if isinstance(value, str):
            try:
                result[key] = str(uuid.UUID(value))
            except ValueError:
                pass
    return result


def remember(
    session: Session,
    conversation: Conversation,
    kind: str,
    now: datetime,
    *,
    reason: str | None = None,
    state: dict[str, Any] | None = None,
) -> None:
    session.add(
        ConversationEvent(
            conversation_id=conversation.id,
            kind=kind,
            reason=reason if reason in REASONS else None,
            version=conversation.version,
            summary=minimal_summary(state if state is not None else conversation.state),
            occurred_at=now,
        )
    )
