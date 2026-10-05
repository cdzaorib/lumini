"""Lead rules. No free text is accepted: it could carry health information (ADR-007)."""

import re
import uuid
from datetime import datetime, timedelta
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from lumini.catalog.service import bookable_service
from lumini.models import Lead, Service

RETENTION = timedelta(days=90)  # plan §12: leads not converted, three months
DUPLICATE_WINDOW = timedelta(hours=24)

PlainName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
City = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)]
Status = Literal["new", "contacted", "converted", "discarded"]


def brazilian_phone(raw: str) -> str:
    """Accept common Brazilian writing ("(21) 99999-0000") or E.164; return E.164."""
    digits = re.sub(r"\D", "", raw)
    if raw.strip().startswith("+"):
        candidate = f"+{digits}"
    elif len(digits) in (10, 11):
        candidate = f"+55{digits}"
    elif digits.startswith("55") and len(digits) in (12, 13):
        candidate = f"+{digits}"
    else:
        raise ValueError("Informe um telefone com DDD")
    if not re.fullmatch(r"\+[1-9]\d{9,14}", candidate):
        raise ValueError("Informe um telefone com DDD")
    return candidate


class LeadCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    name: PlainName
    phone: Annotated[str, StringConstraints(max_length=30)]
    city: City | None = None
    service_id: uuid.UUID | None = None
    preferred_period: Literal["morning", "afternoon", "any"] = "any"
    contact_consent: Literal[True]  # required: may the clinic contact you about this request?
    marketing_consent: bool = False  # separate and optional (plan §12)
    website: Annotated[str, StringConstraints(max_length=200)] = ""  # honeypot: humans leave it

    @field_validator("name", "city")
    @classmethod
    def plain_text(cls, value: str | None) -> str | None:
        if value is not None and (re.search(r"[<>{}\d@]", value)):
            raise ValueError("Use only letters")
        return value

    @field_validator("phone")
    @classmethod
    def normalized_phone(cls, value: str) -> str:
        return brazilian_phone(value)


async def create_lead(
    session: AsyncSession, data: LeadCreate, *, source: str, now: datetime
) -> uuid.UUID | None:
    """Store (or refresh a same-day duplicate). None when silently discarded (bot trap)."""
    if data.website:
        return None
    async with session.begin():
        service_id = data.service_id
        if service_id is not None and await bookable_service(session, service_id) is None:
            service_id = None  # only published services can be named; others are dropped
        existing = await session.scalar(
            select(Lead)
            .where(
                Lead.phone_e164 == data.phone,
                Lead.status == "new",
                Lead.created_at > now - DUPLICATE_WINDOW,
            )
            .with_for_update()
        )
        target = existing or Lead(
            id=uuid.uuid4(), source=source, status="new", created_at=now, phone_e164=data.phone
        )
        target.name = data.name
        target.city = data.city
        target.service_id = service_id or (existing.service_id if existing else None)
        target.preferred_period = data.preferred_period
        target.contact_consent_at = now
        target.marketing_consent_at = now if data.marketing_consent else None
        target.retain_until = now + RETENTION
        if existing is None:
            session.add(target)
        return target.id


class LeadView(BaseModel):
    id: uuid.UUID
    name: str
    phone: str
    city: str | None
    service: str | None
    preferred_period: str
    source: str
    status: str
    marketing_consent: bool
    created_at: datetime
    retain_until: datetime


class LeadStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Status


async def list_leads(session: AsyncSession, status: Status | None) -> list[LeadView]:
    query = (
        select(Lead, Service.name)
        .outerjoin(Service, Service.id == Lead.service_id)
        .order_by(Lead.created_at.desc())
        .limit(200)
    )
    if status is not None:
        query = query.where(Lead.status == status)
    async with session.begin():
        rows = (await session.execute(query)).tuples().all()
    return [
        LeadView(
            id=lead.id,
            name=lead.name,
            phone=lead.phone_e164,
            city=lead.city,
            service=service_name,
            preferred_period=lead.preferred_period,
            source=lead.source,
            status=lead.status,
            marketing_consent=lead.marketing_consent_at is not None,
            created_at=lead.created_at,
            retain_until=lead.retain_until,
        )
        for lead, service_name in rows
    ]


async def set_status(
    session: AsyncSession, lead_id: uuid.UUID, status: Status, *, now: datetime
) -> bool:
    async with session.begin():
        lead = await session.get(Lead, lead_id, with_for_update=True)
        if lead is None:
            return False
        lead.status = status
        lead.updated_at = now
        return True


async def purge_expired(session: AsyncSession, *, now: datetime) -> int:
    """Leads not converted are deleted at their retention date; converted ones follow the
    booking retention policy (still to be approved before launch)."""
    async with session.begin():
        result = await session.execute(
            delete(Lead)
            .where(Lead.status != "converted", Lead.retain_until <= now)
            .returning(Lead.id)
        )
        return len(result.all())
