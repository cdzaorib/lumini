"""Leads with consent and retention date; AI call accounting without prompts."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0005_leads_ai"
down_revision: str | Sequence[str] | None = "0004_whatsapp"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
NOW = sa.func.now()


def upgrade() -> None:
    op.create_table(
        "leads",
        sa.Column("id", UUID, nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("phone_e164", sa.String(16), nullable=False),
        sa.Column("city", sa.String(80), nullable=True),
        sa.Column("service_id", UUID, nullable=True),
        sa.Column("preferred_period", sa.String(10), server_default="any", nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("status", sa.String(12), server_default="new", nullable=False),
        sa.Column("contact_consent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("marketing_consent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retain_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.CheckConstraint(
            "status IN ('new', 'contacted', 'converted', 'discarded')", name="ck_leads_status"
        ),
        sa.CheckConstraint(
            "preferred_period IN ('morning', 'afternoon', 'any')", name="ck_leads_period"
        ),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_leads_status_created_at", "leads", ["status", "created_at"])
    op.create_index("ix_leads_retain_until", "leads", ["retain_until"])
    op.create_table(
        "ai_calls",
        sa.Column("id", UUID, nullable=False),
        sa.Column("purpose", sa.String(20), nullable=False),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_calls_created_at", "ai_calls", ["created_at"])


def downgrade() -> None:
    op.drop_table("ai_calls")
    op.drop_table("leads")
