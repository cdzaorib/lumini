"""Calendar boundary. Google Calendar is the availability reference; PostgreSQL owns booking state.

Event ids are derived from booking ids, so creating, updating and deleting are idempotent and a lost
response can always be reconciled. Events never carry contact names, phones or clinical text.
"""

import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

EVENT_PREFIX = "lumini"


def event_id(booking_id: uuid.UUID) -> str:
    # Google accepts base32hex ids (0-9, a-v), 5-1024 chars; "lumini" + uuid hex fits.
    return f"{EVENT_PREFIX}{booking_id.hex}"


_OURS = re.compile(rf"{EVENT_PREFIX}([0-9a-f]{{32}})")


def booking_id_of(remote_event_id: str | None) -> uuid.UUID | None:
    """The booking behind one of our events. Exact format only: a manual event whose id merely
    starts with the prefix still counts as busy time."""
    match = _OURS.fullmatch(remote_event_id or "")
    return uuid.UUID(match.group(1)) if match else None


def is_ours(remote_event_id: str | None) -> bool:
    return booking_id_of(remote_event_id) is not None


@dataclass(frozen=True)
class BusyBlock:
    start: datetime
    end: datetime
    event_id: str | None = None


@dataclass(frozen=True)
class CalendarEvent:
    id: str
    start: datetime
    end: datetime
    status: Literal["tentative", "confirmed"]
    summary: str
    description: str


@dataclass(frozen=True)
class RemoteEvent:
    id: str
    start: datetime
    end: datetime
    status: str


class CalendarUnavailable(Exception):
    """Transient (network, timeout, 5xx, rate limit): retry later. Never carries provider text."""


class CalendarRejected(Exception):
    """Permanent (calendar missing, no permission, invalid request): needs a human."""


class CalendarNotConfigured(CalendarRejected):
    """No adapter in this process (integration credentials not provided)."""


class CalendarAdapter(Protocol):
    async def list_busy(
        self, calendar_id: str, start: datetime, end: datetime
    ) -> list[BusyBlock]: ...

    async def get_event(self, calendar_id: str, event_id: str) -> RemoteEvent | None: ...

    async def upsert_event(self, calendar_id: str, event: CalendarEvent) -> None: ...

    async def delete_event(self, calendar_id: str, event_id: str) -> None: ...
