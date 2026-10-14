"""Explicit human review before publishing site content or using configured bot messages."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0009_site_publication"
down_revision: str | Sequence[str] | None = "0008_calendar_overlap"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Existing content becomes a draft. A migration cannot act as the clinic's approval.
    op.add_column("site_settings", sa.Column("published_revision", sa.Integer(), nullable=True))
    op.add_column("site_settings", sa.Column("published_by", sa.String(255), nullable=True))
    op.add_column(
        "site_settings", sa.Column("published_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "site_settings",
        sa.Column("reviewer_professional_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "site_settings", sa.Column("reviewer_professional_revision", sa.Integer(), nullable=True)
    )
    op.add_column(
        "site_settings",
        sa.Column("approvals", postgresql.JSONB(), server_default="{}", nullable=False),
    )
    op.create_foreign_key(
        "fk_site_settings_reviewer",
        "site_settings",
        "professionals",
        ["reviewer_professional_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_site_settings_publication",
        "site_settings",
        "(published_revision IS NULL AND published_by IS NULL AND published_at IS NULL "
        "AND reviewer_professional_id IS NULL AND reviewer_professional_revision IS NULL) "
        "OR (published_revision IS NOT NULL AND published_revision = revision "
        "AND published_by IS NOT NULL "
        "AND published_at IS NOT NULL AND reviewer_professional_id IS NOT NULL "
        "AND reviewer_professional_revision IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_site_settings_publication", "site_settings", type_="check")
    op.drop_constraint("fk_site_settings_reviewer", "site_settings", type_="foreignkey")
    for column in (
        "approvals",
        "reviewer_professional_revision",
        "reviewer_professional_id",
        "published_at",
        "published_by",
        "published_revision",
    ):
        op.drop_column("site_settings", column)
