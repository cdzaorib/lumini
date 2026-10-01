"""Slot arithmetic in clinic local time; no database or calendar involved."""

from datetime import UTC, date, datetime, time, timedelta

import pytest

from lumini.booking.availability import Interval, WeeklyRule, free_slots, working_windows
from lumini.booking.calendar import event_id, is_ours
from lumini.booking.policy import CLINIC_TZ

MONDAY = date(2026, 10, 5)
MINUTES = timedelta(minutes=1)


def local(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=CLINIC_TZ).astimezone(UTC)


def slots(
    *,
    busy: list[Interval] | None = None,
    earliest: datetime | None = None,
    latest: datetime | None = None,
    duration: int = 60,
    buffer: int = 15,
) -> list[datetime]:
    windows = working_windows([WeeklyRule(0, time(9), time(12))], MONDAY, MONDAY, CLINIC_TZ)
    return free_slots(
        windows=windows,
        busy=busy or [],
        duration=duration * MINUTES,
        buffer=buffer * MINUTES,
        step=15 * MINUTES,
        earliest=earliest or local(MONDAY, 0),
        latest=latest or local(MONDAY, 23),
    )


def test_local_rules_become_utc_windows_on_matching_weekdays_only() -> None:
    rules = [WeeklyRule(0, time(9), time(12)), WeeklyRule(0, time(13), time(18))]
    windows = working_windows(
        rules, MONDAY - timedelta(days=1), MONDAY + timedelta(days=1), CLINIC_TZ
    )
    assert windows == [
        Interval(local(MONDAY, 9), local(MONDAY, 12)),
        Interval(local(MONDAY, 13), local(MONDAY, 18)),
    ]
    assert windows[0].start == datetime(2026, 10, 5, 12, tzinfo=UTC)  # São Paulo is UTC-3


def test_appointment_must_fit_the_window_but_buffer_may_end_after_it() -> None:
    result = slots()
    assert result[0] == local(MONDAY, 9)
    assert result[-1] == local(MONDAY, 11)  # 11:00 + 60 min ends exactly at 12:00
    assert len(result) == 9


def test_buffer_and_busy_time_block_overlapping_starts_only() -> None:
    busy = [Interval(local(MONDAY, 10), local(MONDAY, 10, 30))]
    result = slots(busy=busy)
    # A start s blocks [s, s + 75 min): it collides while s is in (08:45, 10:30).
    assert result == [local(MONDAY, 10, 30), local(MONDAY, 10, 45), local(MONDAY, 11)]


def test_touching_intervals_do_not_collide() -> None:
    busy = [Interval(local(MONDAY, 10, 15), local(MONDAY, 12))]
    assert slots(busy=busy) == [local(MONDAY, 9)]  # blocked until exactly 10:15


def test_earliest_snaps_to_the_window_grid_and_latest_bounds_starts() -> None:
    result = slots(earliest=local(MONDAY, 9, 20), latest=local(MONDAY, 10, 15))
    assert result == [
        local(MONDAY, 9, 30),
        local(MONDAY, 9, 45),
        local(MONDAY, 10),
        local(MONDAY, 10, 15),
    ]


def test_long_service_without_room_has_no_slots() -> None:
    assert slots(duration=181) == []


@pytest.mark.parametrize(
    ("busy_start", "busy_end"),
    [((8, 0), (13, 0)), ((9, 0), (12, 0))],
)
def test_fully_busy_window_has_no_slots(
    busy_start: tuple[int, int], busy_end: tuple[int, int]
) -> None:
    busy = [Interval(local(MONDAY, *busy_start), local(MONDAY, *busy_end))]
    assert slots(busy=busy) == []


def test_calendar_event_ids_are_deterministic_and_google_compatible() -> None:
    from uuid import UUID

    booking = UUID("12345678-1234-4234-8234-1234567890ab")
    identifier = event_id(booking)
    assert identifier == "lumini12345678123442348234123456789" + "0ab"
    assert set(identifier) <= set("0123456789abcdefghijklmnopqrstuv")
    assert is_ours(identifier) and not is_ours("manualevent123") and not is_ours(None)
