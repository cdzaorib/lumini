"""Versioned catalog approvals and minimal audit trail; no accounts or content seeded."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002_catalog_workflow"
down_revision: str | Sequence[str] | None = "0001_catalog"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "professionals", sa.Column("revision", sa.Integer(), server_default="1", nullable=False)
    )
    op.add_column("professionals", sa.Column("credentials_verified_by", sa.String(255)))
    op.create_check_constraint("ck_professionals_revision", "professionals", "revision > 0")
    op.add_column(
        "services", sa.Column("revision", sa.Integer(), server_default="1", nullable=False)
    )
    op.create_check_constraint("ck_services_revision", "services", "revision > 0")
    # Approval authorship stores the Google subject, which may use up to 255 characters.
    op.alter_column("services", "approved_by", type_=sa.String(255), existing_type=sa.String(200))
    op.create_table(
        "service_approvals",
        sa.Column("service_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("professional_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("approved_by", sa.String(255), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["professional_id"], ["professionals.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("service_id", "professional_id"),
        sa.CheckConstraint("revision > 0", name="ck_service_approvals_revision"),
    )
    op.create_table(
        "catalog_audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_subject", sa.String(255), nullable=False),
        sa.Column("entity_type", sa.String(20), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "entity_type IN ('professional', 'service')", name="ck_catalog_audit_entity"
        ),
        sa.CheckConstraint("revision > 0", name="ck_catalog_audit_revision"),
    )
    op.create_index("ix_catalog_audit_events_target_id", "catalog_audit_events", ["target_id"])


def downgrade() -> None:
    op.drop_index("ix_catalog_audit_events_target_id", table_name="catalog_audit_events")
    op.drop_table("catalog_audit_events")
    op.drop_table("service_approvals")
    op.alter_column("services", "approved_by", type_=sa.String(200), existing_type=sa.String(255))
    op.drop_constraint("ck_services_revision", "services", type_="check")
    op.drop_column("services", "revision")
    op.drop_constraint("ck_professionals_revision", "professionals", type_="check")
    op.drop_column("professionals", "credentials_verified_by")
    op.drop_column("professionals", "revision")
