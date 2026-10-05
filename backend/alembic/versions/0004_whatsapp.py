"""WhatsApp conversations (human mode, flow state), message metadata and integration state."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004_whatsapp"
down_revision: str | Sequence[str] | None = "0003_bookings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
NOW = sa.func.now()


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", UUID, nullable=False),
        sa.Column("chat_id", sa.String(80), nullable=False),
        sa.Column("phone_e164", sa.String(16), nullable=True),
        sa.Column("mode", sa.String(10), server_default="bot", nullable=False),
        sa.Column("mode_reason", sa.String(30), nullable=True),
        sa.Column("mode_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("state", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("marketing_opt_out_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.CheckConstraint("mode IN ('bot', 'human')", name="ck_conversations_mode"),
        sa.CheckConstraint("version > 0", name="ck_conversations_version"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chat_id"),
    )
    op.create_index("ix_conversations_phone_e164", "conversations", ["phone_e164"])
    op.create_table(
        "whatsapp_messages",
        sa.Column("id", UUID, nullable=False),
        sa.Column("conversation_id", UUID, nullable=False),
        sa.Column("provider_id", sa.String(128), nullable=True),
        sa.Column("dedupe_key", sa.String(200), nullable=True),
        sa.Column("direction", sa.String(3), nullable=False),
        sa.Column("origin", sa.String(10), nullable=False),
        sa.Column("purpose", sa.String(40), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("conversation_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.CheckConstraint("direction IN ('in', 'out')", name="ck_whatsapp_messages_direction"),
        sa.CheckConstraint(
            "origin IN ('client', 'bot', 'staff', 'unknown')", name="ck_whatsapp_messages_origin"
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'handled', 'ignored', 'sending', 'sent', 'failed', 'skipped')",
            name="ck_whatsapp_messages_status",
        ),
        sa.CheckConstraint(
            "body IS NULL OR status IN ('pending', 'sending', 'failed')",
            name="ck_whatsapp_messages_body",
        ),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_id"),
        sa.UniqueConstraint("dedupe_key"),
    )
    op.create_index(
        "ix_whatsapp_messages_conversation_status",
        "whatsapp_messages",
        ["conversation_id", "status"],
    )
    op.create_table(
        "integration_states",
        sa.Column("name", sa.String(30), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("detail", sa.String(60), nullable=True),
        sa.Column("needs_attention", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("name"),
    )


def downgrade() -> None:
    op.drop_table("integration_states")
    op.drop_table("whatsapp_messages")
    op.drop_table("conversations")
