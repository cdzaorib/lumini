"""In-memory calendar double for tests; mirrors the adapter contract and its failure modes."""

from dataclasses import dataclass, field
from datetime import datetime

from lumini.booking.calendar import (
    BusyBlock,
    CalendarEvent,
    CalendarRejected,
    CalendarUnavailable,
    RemoteEvent,
)


@dataclass
class FakeCalendar:
    events: dict[str, dict[str, RemoteEvent]] = field(default_factory=dict)
    manual: dict[str, list[BusyBlock]] = field(default_factory=dict)
    unavailable: int = 0  # number of upcoming calls that fail transiently
    rejected: bool = False
    calls: list[str] = field(default_factory=list)

    def _enter(self, name: str) -> None:
        self.calls.append(name)
        if self.rejected:
            raise CalendarRejected("synthetic rejection")
        if self.unavailable > 0:
            self.unavailable -= 1
            raise CalendarUnavailable("synthetic outage")

    def add_manual(self, calendar_id: str, start: datetime, end: datetime) -> None:
        self.manual.setdefault(calendar_id, []).append(BusyBlock(start, end, "manual0001"))

    async def list_busy(self, calendar_id: str, start: datetime, end: datetime) -> list[BusyBlock]:
        self._enter("list_busy")
        ours = [
            BusyBlock(item.start, item.end, item.id)
            for item in self.events.get(calendar_id, {}).values()
            if item.status != "cancelled"
        ]
        return [
            item
            for item in ours + self.manual.get(calendar_id, [])
            if item.start < end and start < item.end
        ]

    async def get_event(self, calendar_id: str, event_id: str) -> RemoteEvent | None:
        self._enter("get_event")
        return self.events.get(calendar_id, {}).get(event_id)

    async def upsert_event(self, calendar_id: str, event: CalendarEvent) -> None:
        self._enter("upsert_event")
        self.events.setdefault(calendar_id, {})[event.id] = RemoteEvent(
            event.id, event.start, event.end, event.status
        )

    async def delete_event(self, calendar_id: str, event_id: str) -> None:
        self._enter("delete_event")
        current = self.events.get(calendar_id, {}).get(event_id)
        if current is not None:
            self.events[calendar_id][event_id] = RemoteEvent(
                current.id, current.start, current.end, "cancelled"
            )

    def status(self, calendar_id: str, event_id: str) -> str | None:
        event = self.events.get(calendar_id, {}).get(event_id)
        return None if event is None else event.status
