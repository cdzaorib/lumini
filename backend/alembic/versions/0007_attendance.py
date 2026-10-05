"""Attendance marked by staff after the appointment; booking events keep insertion order."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_attendance"
down_revision: str | Sequence[str] | None = "0006_site_settings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("bookings", sa.Column("attendance", sa.String(10), nullable=True))
    op.add_column(
        "bookings", sa.Column("attendance_marked_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("bookings", sa.Column("attendance_marked_by", sa.String(255), nullable=True))
    op.create_check_constraint(
        "ck_bookings_attendance",
        "bookings",
        "attendance IS NULL OR (attendance IN ('attended', 'no_show') AND status = 'confirmed')",
    )
    # now() is the transaction start: events written together would tie and lose their order.
    op.alter_column("booking_events", "created_at", server_default=sa.func.clock_timestamp())


def downgrade() -> None:
    op.alter_column("booking_events", "created_at", server_default=sa.func.now())
    op.drop_constraint("ck_bookings_attendance", "bookings", type_="check")
    op.drop_column("bookings", "attendance_marked_by")
    op.drop_column("bookings", "attendance_marked_at")
    op.drop_column("bookings", "attendance")
