"""Catalog schema only. Publication workflows and authorization are not implemented yet."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Professional(Base):
    __tablename__ = "professionals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    display_name: Mapped[str] = mapped_column(String(160))
    category: Mapped[str | None] = mapped_column(String(120))
    council_registration: Mapped[str | None] = mapped_column(String(100))
    credentials_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Service(Base):
    __tablename__ = "services"
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'approved', 'published')", name="ck_services_status"),
        CheckConstraint(
            "booking_mode IS NULL OR booking_mode IN ('evaluation', 'direct')",
            name="ck_services_booking_mode",
        ),
        CheckConstraint("duration_minutes > 0", name="ck_services_duration"),
        CheckConstraint("buffer_minutes >= 0", name="ck_services_buffer"),
        CheckConstraint("price_brl >= 0", name="ck_services_price"),
        CheckConstraint("deposit_brl >= 0", name="ck_services_deposit"),
        CheckConstraint(
            "status = 'draft' OR (approved_at IS NOT NULL AND approved_by IS NOT NULL)",
            name="ck_services_approval",
        ),
        CheckConstraint(
            "status != 'published' OR published_at IS NOT NULL", name="ck_services_publication"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(160), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    buffer_minutes: Mapped[int] = mapped_column(Integer, server_default="15")
    booking_mode: Mapped[str | None] = mapped_column(String(20))
    price_brl: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    deposit_brl: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    status: Mapped[str] = mapped_column(String(20), server_default="draft")
    approved_by: Mapped[str | None] = mapped_column(String(200))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ProfessionalService(Base):
    __tablename__ = "professional_services"

    professional_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("professionals.id", ondelete="RESTRICT"), primary_key=True
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("services.id", ondelete="RESTRICT"), primary_key=True
    )
