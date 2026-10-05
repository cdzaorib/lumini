"""Booking HTTP models. Contact data appears only in staff views."""

from datetime import date, datetime, time
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator

from lumini.catalog.schemas import InputModel, Money

CalendarId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        max_length=255,
        pattern=r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$",
    ),
]
Version = Annotated[int, Field(strict=True, ge=1)]


class RuleInput(InputModel):
    weekday: Annotated[int, Field(strict=True, ge=0, le=6)]
    start: time
    end: time

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.start.tzinfo is not None or self.end.tzinfo is not None:
            raise ValueError("Use local clinic time without offsets")
        # Slots are laid on a 15-minute grid from each window's start.
        for value in (self.start, self.end):
            if value.minute % 15 or value.second or value.microsecond:
                raise ValueError("Use times on a 15-minute grid")
        if self.start >= self.end:
            raise ValueError("Start must be before end")
        return self


class ScheduleUpdate(InputModel):
    expected_revision: Annotated[int, Field(strict=True, ge=0)]  # 0 = not configured yet
    calendar_id: CalendarId | None = None
    rules: list[RuleInput] = Field(default_factory=list, max_length=28)

    @model_validator(mode="after")
    def no_overlaps(self) -> Self:
        by_day: dict[int, list[RuleInput]] = {}
        for rule in self.rules:
            by_day.setdefault(rule.weekday, []).append(rule)
        for rules in by_day.values():
            rules.sort(key=lambda item: item.start)
            for previous, current in zip(rules, rules[1:], strict=False):
                if current.start < previous.end:
                    raise ValueError("Working windows on the same day cannot overlap")
        return self


class RuleView(BaseModel):
    weekday: int
    start: time
    end: time


class ScheduleView(BaseModel):
    professional_id: UUID
    calendar_id: str | None
    revision: int
    rules: list[RuleView]


class BookingVersion(InputModel):
    expected_version: Version


class DepositConfirmation(BookingVersion):
    amount_brl: Money


class ConflictResolution(BookingVersion):
    resolution: Literal["release", "retry"]


class StaffReschedule(BookingVersion):
    starts_at: AwareDatetime


class AvailabilityQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_id: UUID
    professional_id: UUID
    first_day: date
    days: Annotated[int, Field(ge=1, le=14)] = 7


class AvailabilityView(BaseModel):
    slots: list[datetime]


BookingScope = Literal["upcoming", "history"]


class NamedRef(BaseModel):
    id: UUID
    name: str


class ContactView(BaseModel):
    name: str
    phone: str


class BookingAdminView(BaseModel):
    id: UUID
    code: str
    status: str
    version: int
    starts_at: datetime
    ends_at: datetime
    expires_at: datetime | None
    service: NamedRef
    professional: NamedRef
    contact: ContactView
    deposit_brl: Decimal
    deposit_confirmed_at: datetime | None
    calendar_status: str
    reschedule_count: int
    rescheduled_from_id: UUID | None
    closed_reason: str | None
    created_at: datetime


class PublicBooking(BaseModel):
    """What a client sees through their link: no contact data, no internal ids or audit."""

    code: str
    status: str
    version: int
    service: str
    professional: str
    starts_at: datetime
    ends_at: datetime
    hold_expires_at: datetime | None
    deposit_brl: Decimal
    deposit_confirmed: bool
    self_service_until: datetime
    can_cancel: bool
    cancel_blocked: str | None
    can_reschedule: bool
    reschedule_blocked: str | None


class PublicRescheduled(BaseModel):
    booking: PublicBooking
    token: str  # link for the new booking; the old one now shows the cancelled original


class PublicAvailabilityQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_day: date
    days: Annotated[int, Field(ge=1, le=7)] = 7


class ManageLinkView(BaseModel):
    url: str
    expires_at: datetime
