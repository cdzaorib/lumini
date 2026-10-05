"""Clinic facts edited in the panel (site content, deposit instructions); audit entity 'site'."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006_site_settings"
down_revision: str | Sequence[str] | None = "0005_leads_ai"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "site_settings",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column("content", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("id = 1", name="ck_site_settings_single_row"),
        sa.CheckConstraint("revision > 0", name="ck_site_settings_revision"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.drop_constraint("ck_catalog_audit_entity", "catalog_audit_events", type_="check")
    op.create_check_constraint(
        "ck_catalog_audit_entity",
        "catalog_audit_events",
        "entity_type IN ('professional', 'service', 'site')",
    )


def downgrade() -> None:
    op.execute("DELETE FROM catalog_audit_events WHERE entity_type = 'site'")
    op.drop_constraint("ck_catalog_audit_entity", "catalog_audit_events", type_="check")
    op.create_check_constraint(
        "ck_catalog_audit_entity",
        "catalog_audit_events",
        "entity_type IN ('professional', 'service')",
    )
    op.drop_table("site_settings")
