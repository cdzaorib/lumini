"""Catalog, bookings, transactional outbox and minimal audit events (IDs only, no clinical text)."""

import uuid
from datetime import datetime, time
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Table,
    Text,
    Time,
    func,
    literal_column,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID, ExcludeConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Professional(Base):
    __tablename__ = "professionals"
    __table_args__ = (CheckConstraint("revision > 0", name="ck_professionals_revision"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    display_name: Mapped[str] = mapped_column(String(160))
    category: Mapped[str | None] = mapped_column(String(120))
    council_registration: Mapped[str | None] = mapped_column(String(100))
    credentials_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    credentials_verified_by: Mapped[str | None] = mapped_column(String(255))
    revision: Mapped[int] = mapped_column(Integer, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Service(Base):
    __tablename__ = "services"
    __table_args__ = (
        CheckConstraint("revision > 0", name="ck_services_revision"),
        CheckConstraint("status IN ('draft', 'approved', 'published')", name="ck_services_status"),
        CheckConstraint(
            "booking_mode IS NULL OR booking_mode IN ('evaluation', 'direct')",
            name="ck_services_booking_mode",
        ),
        CheckConstraint("duration_minutes > 0", name="ck_services_duration"),
        CheckConstraint("buffer_minutes >= 0", name="ck_services_buffer"),
        CheckConstraint("price_brl >= 0", name="ck_services_price"),
        CheckConstraint("deposit_brl >= 0", name="ck_services_deposit"),
        CheckConstraint(
            "status = 'draft' OR (approved_at IS NOT NULL AND approved_by IS NOT NULL)",
            name="ck_services_approval",
        ),
        CheckConstraint(
            "status != 'published' OR published_at IS NOT NULL", name="ck_services_publication"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(160), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    buffer_minutes: Mapped[int] = mapped_column(Integer, server_default="15")
    booking_mode: Mapped[str | None] = mapped_column(String(20))
    price_brl: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    deposit_brl: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    status: Mapped[str] = mapped_column(String(20), server_default="draft")
    revision: Mapped[int] = mapped_column(Integer, server_default="1")
    approved_by: Mapped[str | None] = mapped_column(String(255))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ProfessionalService(Base):
    __tablename__ = "professional_services"

    professional_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("professionals.id", ondelete="RESTRICT"), primary_key=True
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("services.id", ondelete="RESTRICT"), primary_key=True
    )


class ServiceApproval(Base):
    __tablename__ = "service_approvals"
    __table_args__ = (CheckConstraint("revision > 0", name="ck_service_approvals_revision"),)

    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("services.id", ondelete="RESTRICT"), primary_key=True
    )
    professional_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("professionals.id", ondelete="RESTRICT"), primary_key=True
    )
    revision: Mapped[int] = mapped_column(Integer)
    approved_by: Mapped[str] = mapped_column(String(255))
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CatalogAuditEvent(Base):
    __tablename__ = "catalog_audit_events"
    __table_args__ = (
        CheckConstraint(
            "entity_type IN ('professional', 'service')", name="ck_catalog_audit_entity"
        ),
        CheckConstraint("revision > 0", name="ck_catalog_audit_revision"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_subject: Mapped[str] = mapped_column(String(255))
    entity_type: Mapped[str] = mapped_column(String(20))
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    action: Mapped[str] = mapped_column(String(60))
    revision: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# Bookings ---------------------------------------------------------------------------------

BOOKING_STATUSES = (
    "pending_calendar",
    "held",
    "confirming",
    "confirmed",
    "expired",
    "cancelled",
    "conflict",
)
# States that occupy the professional's time. Conflict keeps blocking until a human decides.
ACTIVE_BOOKING_STATUSES = ("pending_calendar", "held", "confirming", "confirmed", "conflict")
CALENDAR_STATUSES = ("none", "tentative", "confirmed", "deleted")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


class Contact(Base):
    """Minimal booking contact. Phone numbers never go to logs, models or calendar events."""

    __tablename__ = "contacts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120))
    phone_e164: Mapped[str] = mapped_column(String(16), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProfessionalSchedule(Base):
    """Operational settings, kept apart from credentials so edits never revoke verification."""

    __tablename__ = "professional_schedules"
    __table_args__ = (CheckConstraint("revision > 0", name="ck_professional_schedules_revision"),)

    professional_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("professionals.id", ondelete="RESTRICT"), primary_key=True
    )
    calendar_id: Mapped[str | None] = mapped_column(String(255))
    revision: Mapped[int] = mapped_column(Integer, server_default="1")


class AvailabilityRule(Base):
    """Weekly working window in clinic local time (America/Sao_Paulo); weekday 0 = Monday."""

    __tablename__ = "availability_rules"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_availability_rules_weekday"),
        CheckConstraint("start_time < end_time", name="ck_availability_rules_window"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    professional_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("professional_schedules.professional_id", ondelete="CASCADE"),
        index=True,
    )
    weekday: Mapped[int] = mapped_column(SmallInteger)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint(_in("status", BOOKING_STATUSES), name="ck_bookings_status"),
        CheckConstraint(_in("calendar_status", CALENDAR_STATUSES), name="ck_bookings_calendar"),
        CheckConstraint("version > 0", name="ck_bookings_version"),
        CheckConstraint(
            "starts_at < ends_at AND ends_at <= blocked_until", name="ck_bookings_time"
        ),
        CheckConstraint("deposit_brl >= 0", name="ck_bookings_deposit"),
        CheckConstraint("reschedule_count >= 0", name="ck_bookings_reschedules"),
        # Only open holds carry a deadline; nothing else can expire.
        CheckConstraint(
            f"({_in('status', ('pending_calendar', 'held'))}) = (expires_at IS NOT NULL)",
            name="ck_bookings_expiry",
        ),
        # Confirmation states always carry an authenticated human deposit confirmation.
        CheckConstraint(
            "status NOT IN ('confirming', 'confirmed') OR "
            "(deposit_confirmed_at IS NOT NULL AND deposit_confirmed_by IS NOT NULL)",
            name="ck_bookings_deposit_confirmation",
        ),
        Index("ix_bookings_status_expires_at", "status", "expires_at"),
        Index("ix_bookings_professional_starts_at", "professional_id", "starts_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True)
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("services.id", ondelete="RESTRICT")
    )
    service_revision: Mapped[int] = mapped_column(Integer)
    professional_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("professionals.id", ondelete="RESTRICT")
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="RESTRICT"), index=True
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    blocked_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20))
    version: Mapped[int] = mapped_column(Integer, server_default="1")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deposit_brl: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    deposit_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deposit_confirmed_by: Mapped[str | None] = mapped_column(String(255))
    calendar_status: Mapped[str] = mapped_column(String(20), server_default="none")
    rescheduled_from_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bookings.id", ondelete="RESTRICT"), unique=True
    )
    reschedule_count: Mapped[int] = mapped_column(Integer, server_default="0")
    closed_reason: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# One professional can never hold two overlapping active bookings, whatever the race.
_bookings = cast(Table, Booking.__table__)
_bookings.append_constraint(
    ExcludeConstraint(
        (_bookings.c.professional_id, "="),
        (
            func.tstzrange(
                _bookings.c.starts_at,
                _bookings.c.blocked_until,
                literal_column("'[)'"),
            ),
            "&&",
        ),
        name="ex_bookings_professional_time",
        using="gist",
        where=literal_column(_in("status", ACTIVE_BOOKING_STATUSES)),
    )
)


class BookingEvent(Base):
    """Audit trail of booking transitions: who/when/what, never contact data or message text."""

    __tablename__ = "booking_events"
    __table_args__ = (
        CheckConstraint(
            "actor_type IN ('system', 'staff', 'client')", name="ck_booking_events_actor"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bookings.id", ondelete="RESTRICT"), index=True
    )
    action: Mapped[str] = mapped_column(String(40))
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    actor_type: Mapped[str] = mapped_column(String(10))
    actor_subject: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OutboxJob(Base):
    """Transactional outbox: written with the state change, delivered later, deduplicated."""

    __tablename__ = "outbox_jobs"
    __table_args__ = (
        CheckConstraint("kind IN ('calendar_sync', 'notification')", name="ck_outbox_kind"),
        CheckConstraint("status IN ('pending', 'done', 'failed')", name="ck_outbox_status"),
        CheckConstraint("attempts >= 0", name="ck_outbox_attempts"),
        Index("ix_outbox_jobs_status_available_at", "status", "available_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(20))
    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bookings.id", ondelete="RESTRICT"), index=True
    )
    event: Mapped[str | None] = mapped_column(String(40))
    dedupe_key: Mapped[str] = mapped_column(String(200), unique=True)
    status: Mapped[str] = mapped_column(String(12), server_default="pending")
    attempts: Mapped[int] = mapped_column(Integer, server_default="0")
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Sanitized short code only; never provider exception text.
    last_error: Mapped[str | None] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
