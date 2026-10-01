"""Bookings with overlap exclusion, schedules, contacts, audit and transactional outbox."""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003_bookings"
down_revision: str | Sequence[str] | None = "0002_catalog_workflow"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
STATUSES = (
    "'pending_calendar', 'held', 'confirming', 'confirmed', 'expired', 'cancelled', 'conflict'"
)
ACTIVE = "'pending_calendar', 'held', 'confirming', 'confirmed', 'conflict'"


def _timestamps() -> list[sa.Column[Any]]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    # Needed for "professional_id WITH =" inside a GiST exclusion constraint.
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.create_table(
        "contacts",
        sa.Column("id", UUID, nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("phone_e164", sa.String(16), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("phone_e164"),
    )
    op.create_table(
        "professional_schedules",
        sa.Column("professional_id", UUID, nullable=False),
        sa.Column("calendar_id", sa.String(255)),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        sa.ForeignKeyConstraint(["professional_id"], ["professionals.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("professional_id"),
        sa.CheckConstraint("revision > 0", name="ck_professional_schedules_revision"),
    )
    op.create_table(
        "availability_rules",
        sa.Column("id", UUID, nullable=False),
        sa.Column("professional_id", UUID, nullable=False),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.ForeignKeyConstraint(
            ["professional_id"], ["professional_schedules.professional_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_availability_rules_weekday"),
        sa.CheckConstraint("start_time < end_time", name="ck_availability_rules_window"),
    )
    op.create_index(
        "ix_availability_rules_professional_id", "availability_rules", ["professional_id"]
    )
    op.create_table(
        "bookings",
        sa.Column("id", UUID, nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("service_id", UUID, nullable=False),
        sa.Column("service_revision", sa.Integer(), nullable=False),
        sa.Column("professional_id", UUID, nullable=False),
        sa.Column("contact_id", UUID, nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("blocked_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("deposit_brl", sa.Numeric(10, 2), nullable=False),
        sa.Column("deposit_confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("deposit_confirmed_by", sa.String(255)),
        sa.Column("calendar_status", sa.String(20), server_default="none", nullable=False),
        sa.Column("rescheduled_from_id", UUID),
        sa.Column("reschedule_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("closed_reason", sa.String(40)),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
        sa.UniqueConstraint("rescheduled_from_id"),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["professional_id"], ["professionals.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["rescheduled_from_id"], ["bookings.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(f"status IN ({STATUSES})", name="ck_bookings_status"),
        sa.CheckConstraint(
            "calendar_status IN ('none', 'tentative', 'confirmed', 'deleted')",
            name="ck_bookings_calendar",
        ),
        sa.CheckConstraint("version > 0", name="ck_bookings_version"),
        sa.CheckConstraint(
            "starts_at < ends_at AND ends_at <= blocked_until", name="ck_bookings_time"
        ),
        sa.CheckConstraint("deposit_brl >= 0", name="ck_bookings_deposit"),
        sa.CheckConstraint("reschedule_count >= 0", name="ck_bookings_reschedules"),
        sa.CheckConstraint(
            "(status IN ('pending_calendar', 'held')) = (expires_at IS NOT NULL)",
            name="ck_bookings_expiry",
        ),
        sa.CheckConstraint(
            "status NOT IN ('confirming', 'confirmed') OR "
            "(deposit_confirmed_at IS NOT NULL AND deposit_confirmed_by IS NOT NULL)",
            name="ck_bookings_deposit_confirmation",
        ),
        postgresql.ExcludeConstraint(
            ("professional_id", "="),
            (sa.text("tstzrange(starts_at, blocked_until, '[)')"), "&&"),
            name="ex_bookings_professional_time",
            using="gist",
            where=sa.text(f"status IN ({ACTIVE})"),
        ),
    )
    op.create_index("ix_bookings_status_expires_at", "bookings", ["status", "expires_at"])
    op.create_index(
        "ix_bookings_professional_starts_at", "bookings", ["professional_id", "starts_at"]
    )
    op.create_index("ix_bookings_contact_id", "bookings", ["contact_id"])
    op.create_table(
        "booking_events",
        sa.Column("id", UUID, nullable=False),
        sa.Column("booking_id", UUID, nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("from_status", sa.String(20)),
        sa.Column("to_status", sa.String(20), nullable=False),
        sa.Column("actor_type", sa.String(10), nullable=False),
        sa.Column("actor_subject", sa.String(255)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "actor_type IN ('system', 'staff', 'client')", name="ck_booking_events_actor"
        ),
    )
    op.create_index("ix_booking_events_booking_id", "booking_events", ["booking_id"])
    op.create_table(
        "outbox_jobs",
        sa.Column("id", UUID, nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("booking_id", UUID, nullable=False),
        sa.Column("event", sa.String(40)),
        sa.Column("dedupe_key", sa.String(200), nullable=False),
        sa.Column("status", sa.String(12), server_default="pending", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String(60)),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_key"),
        sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("kind IN ('calendar_sync', 'notification')", name="ck_outbox_kind"),
        sa.CheckConstraint("status IN ('pending', 'done', 'failed')", name="ck_outbox_status"),
        sa.CheckConstraint("attempts >= 0", name="ck_outbox_attempts"),
    )
    op.create_index("ix_outbox_jobs_booking_id", "outbox_jobs", ["booking_id"])
    op.create_index("ix_outbox_jobs_status_available_at", "outbox_jobs", ["status", "available_at"])


def downgrade() -> None:
    op.drop_table("outbox_jobs")
    op.drop_table("booking_events")
    op.drop_table("bookings")
    op.drop_table("availability_rules")
    op.drop_table("professional_schedules")
    op.drop_table("contacts")
    # btree_gist is left installed: other objects may depend on it and it holds no data.
