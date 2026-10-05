"""Informational flag: another Google Calendar commitment overlaps an active booking."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008_calendar_overlap"
down_revision: str | Sequence[str] | None = "0007_attendance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "bookings", sa.Column("calendar_overlap_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("bookings", "calendar_overlap_at")
