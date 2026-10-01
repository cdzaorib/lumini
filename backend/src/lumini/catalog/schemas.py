"""Strict text-only inputs; clients cannot assign verification or approval metadata."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


def _text(max_length: int) -> StringConstraints:
    return StringConstraints(strip_whitespace=True, min_length=1, max_length=max_length)


ShortText = Annotated[str, _text(160)]
CategoryText = Annotated[str, _text(120)]
RegistrationText = Annotated[str, _text(100)]
ClinicalText = Annotated[str, _text(2000)]
LongText = Annotated[str, _text(6000)]
Minutes = Annotated[int, Field(strict=True, gt=0, le=1440)]
BufferMinutes = Annotated[int, Field(strict=True, ge=15, le=1440)]
Money = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=2, allow_inf_nan=False)]
Slug = Annotated[str, StringConstraints(max_length=160, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")]
Revision = Annotated[int, Field(strict=True, ge=1)]
BookingMode = Literal["evaluation", "direct"]


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    @model_validator(mode="after")
    def text_only(self) -> Self:
        def inspect(value: object) -> None:
            if isinstance(value, str) and ("<" in value or ">" in value):
                raise ValueError("Use plain text without markup")
            if isinstance(value, dict):
                for item in value.values():
                    inspect(item)
            if isinstance(value, list):
                for item in value:
                    inspect(item)

        inspect(self.model_dump())
        return self


class ProfessionalCreate(InputModel):
    display_name: ShortText
    category: CategoryText | None = None
    council_registration: RegistrationText | None = None


class VersionRequest(InputModel):
    expected_revision: Revision


class ProfessionalUpdate(VersionRequest):
    display_name: ShortText | None = None
    category: CategoryText | None = None
    council_registration: RegistrationText | None = None

    @model_validator(mode="after")
    def nonnull_name(self) -> Self:
        if "display_name" in self.model_fields_set and self.display_name is None:
            raise ValueError("Name cannot be null")
        return self


class ProfessionalView(ProfessionalCreate):
    id: UUID
    credentials_verified_at: datetime | None
    revision: int


class ServiceContent(InputModel):
    objectives: list[ClinicalText] = Field(default_factory=list, max_length=20)
    audience: ClinicalText | None = None
    preparation: list[ClinicalText] = Field(default_factory=list, max_length=20)
    aftercare: list[ClinicalText] = Field(default_factory=list, max_length=20)
    human_guidance: ClinicalText | None = None
    price_kind: Literal["fixed", "from", "on_evaluation"] = "on_evaluation"


class ServiceCreate(InputModel):
    slug: Slug
    name: ShortText
    category: ShortText
    description: LongText | None = None
    content: ServiceContent = Field(default_factory=ServiceContent)
    duration_minutes: Minutes | None = None
    buffer_minutes: BufferMinutes = 15
    booking_mode: BookingMode | None = None
    price_brl: Money | None = None
    deposit_brl: Money | None = None
    professional_ids: list[UUID] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def unique_professionals(self) -> Self:
        if len(self.professional_ids) != len(set(self.professional_ids)):
            raise ValueError("Professional identifiers must be unique")
        return self


class ServiceUpdate(VersionRequest):
    slug: Slug | None = None
    name: ShortText | None = None
    category: ShortText | None = None
    description: LongText | None = None
    content: ServiceContent | None = None
    duration_minutes: Minutes | None = None
    buffer_minutes: BufferMinutes | None = None
    booking_mode: BookingMode | None = None
    price_brl: Money | None = None
    deposit_brl: Money | None = None
    professional_ids: list[UUID] | None = Field(default=None, max_length=20)

    @model_validator(mode="after")
    def validate_patch(self) -> Self:
        required = {"slug", "name", "category", "content", "buffer_minutes", "professional_ids"}
        for field in required & self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError("Required fields cannot be null")
        ids = self.professional_ids
        if ids is not None and len(ids) != len(set(ids)):
            raise ValueError("Professional identifiers must be unique")
        return self


class ApprovalRequest(VersionRequest):
    professional_id: UUID


class ApprovalView(BaseModel):
    professional_id: UUID
    approved_at: datetime


class ServiceView(ServiceCreate):
    id: UUID
    status: Literal["draft", "approved", "published"]
    revision: int
    approved_at: datetime | None
    published_at: datetime | None
    approvals: list[ApprovalView]


class PublicProfessional(BaseModel):
    """Council registration stays internal until a reviewed public credential field exists."""

    id: UUID
    display_name: str
    category: str


class PublicService(BaseModel):
    id: UUID
    slug: str
    name: str
    category: str
    description: str
    content: ServiceContent
    duration_minutes: int
    buffer_minutes: int
    booking_mode: BookingMode
    price_brl: Decimal | None
    deposit_brl: Decimal
    professionals: list[PublicProfessional]
