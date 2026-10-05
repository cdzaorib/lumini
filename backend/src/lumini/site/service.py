"""Site content: validated input, single versioned row, audit with ids only."""

import uuid
from datetime import date, datetime
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from lumini.ai.guardrails import publicity_problem
from lumini.auth import AdminPrincipal
from lumini.catalog.schemas import InputModel
from lumini.leads.service import brazilian_phone
from lumini.models import CatalogAuditEvent, SiteSettings

SITE_ENTITY_ID = uuid.uuid5(uuid.NAMESPACE_URL, "lumini:site-settings")

Line = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Paragraph = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class SiteConflict(Exception):
    pass


class Address(InputModel):
    street: Line
    city: Line
    maps_url: Annotated[str, StringConstraints(max_length=500, pattern=r"^https://\S+$")] | None = (
        None
    )


class FaqItem(InputModel):
    question: Line
    answer: Paragraph


class Testimonial(InputModel):
    quote: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=400)]
    author: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    authorized_on: date
    authorization_confirmed: Literal[True]  # written authorization kept by the clinic


class SiteContent(InputModel):
    address: Address | None = None
    hours: list[Line] = Field(default_factory=list, max_length=10)
    whatsapp: str | None = None
    instagram: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9._]{1,30}$")] | None = None
    differentiators: list[Line] = Field(default_factory=list, max_length=8)
    faq: list[FaqItem] = Field(default_factory=list, max_length=20)
    testimonials: list[Testimonial] = Field(default_factory=list, max_length=10)
    legal_contact: Line | None = None
    # Sent by the bot after a reservation (e.g. Pix key and holder). Never on the public site.
    deposit_instructions: Paragraph | None = None

    @field_validator("whatsapp")
    @classmethod
    def phone(cls, value: str | None) -> str | None:
        return brazilian_phone(value) if value else None

    @model_validator(mode="after")
    def advertising_rules(self) -> Self:
        texts = [
            *self.differentiators,
            *(f"{item.question} {item.answer}" for item in self.faq),
            *(item.quote for item in self.testimonials),
        ]
        for text in texts:
            problem = publicity_problem(text)
            if problem is not None:
                raise ValueError(f"Advertising rule: avoid promising results ({problem})")
        return self


class SiteUpdate(InputModel):
    expected_revision: Annotated[int, Field(strict=True, ge=0)]
    content: SiteContent


class SiteView(BaseModel):
    revision: int
    content: SiteContent
    updated_at: datetime | None


class PublicTestimonial(BaseModel):
    quote: str
    author: str


class PublicSite(BaseModel):
    """What the website may show: never the deposit instructions or authorization records."""

    address: Address | None
    hours: list[str]
    whatsapp: str | None
    instagram: str | None
    differentiators: list[str]
    faq: list[FaqItem]
    testimonials: list[PublicTestimonial]
    legal_contact: str | None


def _content(raw: dict[str, Any] | None) -> SiteContent:
    return SiteContent.model_validate(raw or {})


async def get_site(session: AsyncSession) -> SiteView:
    async with session.begin():
        row = await session.get(SiteSettings, 1, populate_existing=True)
    if row is None:
        return SiteView(revision=0, content=SiteContent(), updated_at=None)
    return SiteView(revision=row.revision, content=_content(row.content), updated_at=row.updated_at)


async def put_site(
    session: AsyncSession, actor: AdminPrincipal, data: SiteUpdate, *, now: datetime
) -> SiteView:
    async with session.begin():
        row = await session.get(SiteSettings, 1, with_for_update=True, populate_existing=True)
        current = row.revision if row else 0
        if current != data.expected_revision:
            raise SiteConflict("The site content changed; reload before saving")
        if row is None:
            row = SiteSettings(id=1, revision=0)
            session.add(row)
        row.content = data.content.model_dump(mode="json")
        row.revision = current + 1
        row.updated_at = now
        session.add(
            CatalogAuditEvent(
                id=uuid.uuid4(),
                actor_subject=actor.subject,
                entity_type="site",
                target_id=SITE_ENTITY_ID,
                action="site.updated",
                revision=row.revision,
            )
        )
        revision = row.revision
    return SiteView(revision=revision, content=data.content, updated_at=now)


async def public_site(session: AsyncSession) -> PublicSite:
    content = (await get_site(session)).content
    return PublicSite(
        address=content.address,
        hours=content.hours,
        whatsapp=content.whatsapp,
        instagram=content.instagram,
        differentiators=content.differentiators,
        faq=content.faq,
        testimonials=[
            PublicTestimonial(quote=item.quote, author=item.author) for item in content.testimonials
        ],
        legal_contact=content.legal_contact,
    )


async def deposit_instructions(session: AsyncSession) -> str | None:
    return (await get_site(session)).content.deposit_instructions
