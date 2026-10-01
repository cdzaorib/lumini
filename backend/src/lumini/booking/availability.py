"""Pure slot computation in UTC: weekly working windows minus busy time. No I/O."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo


@dataclass(frozen=True, order=True)
class Interval:
    start: datetime
    end: datetime

    def overlaps(self, other: "Interval") -> bool:
        # Half-open: touching intervals do not overlap.
        return self.start < other.end and other.start < self.end


@dataclass(frozen=True)
class WeeklyRule:
    weekday: int  # 0 = Monday, clinic local time
    start: time
    end: time


def working_windows(
    rules: Iterable[WeeklyRule], first_day: date, last_day: date, tz: ZoneInfo
) -> list[Interval]:
    """Local weekly rules materialized as UTC intervals for each calendar day in range."""
    rules = list(rules)
    result: list[Interval] = []
    day = first_day
    while day <= last_day:
        for rule in rules:
            if rule.weekday == day.weekday():
                start = datetime.combine(day, rule.start, tzinfo=tz).astimezone(UTC)
                end = datetime.combine(day, rule.end, tzinfo=tz).astimezone(UTC)
                if start < end:
                    result.append(Interval(start, end))
        day += timedelta(days=1)
    return sorted(result)


def free_slots(
    *,
    windows: Sequence[Interval],
    busy: Iterable[Interval],
    duration: timedelta,
    buffer: timedelta,
    step: timedelta,
    earliest: datetime,
    latest: datetime,
) -> list[datetime]:
    """Starts on each window's step grid where the appointment fits inside the window and the
    blocked time (appointment + buffer) overlaps nothing busy."""
    busy = sorted(busy)
    slots: set[datetime] = set()
    for window in windows:
        start = window.start
        if start < earliest:
            start += -((start - earliest) // step) * step  # next grid point at or after earliest
        while start + duration <= window.end and start <= latest:
            blocked = Interval(start, start + duration + buffer)
            if not any(blocked.overlaps(item) for item in busy):
                slots.add(start)
            start += step
    return sorted(slots)
