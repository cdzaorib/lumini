"""Minimal structured progress and human mode history, without message content."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0010_conversation_history"
down_revision: str | Sequence[str] | None = "0009_site_publication"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "conversation_events",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.UUID(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("reason", sa.String(30)),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("summary", postgresql.JSONB(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('progress', 'human', 'bot', 'handoff')", name="ck_conversation_events_kind"
        ),
    )
    op.create_index(
        "ix_conversation_events_conversation_time",
        "conversation_events",
        ["conversation_id", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_table("conversation_events")
