"""Create empty professional and service catalog; no clinical content seeded."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001_catalog"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "professionals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("category", sa.String(120)),
        sa.Column("council_registration", sa.String(100)),
        sa.Column("credentials_verified_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "services",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(160), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("category", sa.String(120), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("content", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("duration_minutes", sa.Integer()),
        sa.Column("buffer_minutes", sa.Integer(), server_default="15", nullable=False),
        sa.Column("booking_mode", sa.String(20)),
        sa.Column("price_brl", sa.Numeric(10, 2)),
        sa.Column("deposit_brl", sa.Numeric(10, 2)),
        sa.Column("status", sa.String(20), server_default="draft", nullable=False),
        sa.Column("approved_by", sa.String(200)),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'approved', 'published')", name="ck_services_status"
        ),
        sa.CheckConstraint(
            "booking_mode IS NULL OR booking_mode IN ('evaluation', 'direct')",
            name="ck_services_booking_mode",
        ),
        sa.CheckConstraint("duration_minutes > 0", name="ck_services_duration"),
        sa.CheckConstraint("buffer_minutes >= 0", name="ck_services_buffer"),
        sa.CheckConstraint("price_brl >= 0", name="ck_services_price"),
        sa.CheckConstraint("deposit_brl >= 0", name="ck_services_deposit"),
        sa.CheckConstraint(
            "status = 'draft' OR (approved_at IS NOT NULL AND approved_by IS NOT NULL)",
            name="ck_services_approval",
        ),
        sa.CheckConstraint(
            "status != 'published' OR published_at IS NOT NULL", name="ck_services_publication"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "professional_services",
        sa.Column("professional_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("service_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["professional_id"], ["professionals.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("professional_id", "service_id"),
    )


def downgrade() -> None:
    op.drop_table("professional_services")
    op.drop_table("services")
    op.drop_table("professionals")
