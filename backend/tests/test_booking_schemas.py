"""Staff booking inputs: agenda windows on the slot grid, versions required, no extra fields."""

from datetime import time
from typing import Any

import pytest
from pydantic import ValidationError

from lumini.booking.schemas import (
    AvailabilityQuery,
    ConflictResolution,
    DepositConfirmation,
    ScheduleUpdate,
    StaffReschedule,
)


def window(day: int, start: str, end: str) -> dict[str, Any]:
    return {"weekday": day, "start": start, "end": end}


def test_adjacent_windows_and_other_days_are_accepted() -> None:
    update = ScheduleUpdate.model_validate(
        {
            "expected_revision": 0,
            "calendar_id": "  synthetic@group.calendar.google.com ",
            "rules": [
                window(0, "13:00", "18:00"),
                window(0, "09:00", "13:00"),
                window(6, "08:00", "09:15"),
            ],
        }
    )
    assert update.calendar_id == "synthetic@group.calendar.google.com"
    assert [(rule.weekday, rule.start) for rule in update.rules] == [
        (0, time(13)),
        (0, time(9)),
        (6, time(8)),
    ]


@pytest.mark.parametrize(
    "rules",
    [
        [window(0, "09:00", "12:00"), window(0, "11:45", "13:00")],
        [window(0, "09:00", "09:00")],
        [window(0, "09:05", "12:00")],
        [window(0, "09:00:30", "12:00")],
        [window(0, "09:00Z", "12:00")],
        [window(-1, "09:00", "12:00")],
        [window(0, "09:00", "12:00")] * 29,
    ],
)
def test_invalid_windows_are_rejected(rules: list[dict[str, Any]]) -> None:
    with pytest.raises(ValidationError):
        ScheduleUpdate.model_validate({"expected_revision": 1, "rules": rules})


@pytest.mark.parametrize(
    "changes",
    [
        {"expected_revision": -1},
        {"expected_revision": "1"},
        {"calendar_id": "not-a-calendar"},
        {"calendar_id": "a@b.c<"},
        {"revision": 5},
    ],
)
def test_schedule_metadata_cannot_be_forged(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        ScheduleUpdate.model_validate({"expected_revision": 1, **changes})


@pytest.mark.parametrize(
    ("model", "body"),
    [
        (DepositConfirmation, {"amount_brl": "50.00"}),
        (DepositConfirmation, {"expected_version": 0, "amount_brl": "50.00"}),
        (DepositConfirmation, {"expected_version": 1, "amount_brl": "-1"}),
        (DepositConfirmation, {"expected_version": 1, "amount_brl": "NaN"}),
        (DepositConfirmation, {"expected_version": 1, "amount_brl": "50.001"}),
        (DepositConfirmation, {"expected_version": 1, "amount_brl": "50", "confirmed_by": "x"}),
        (ConflictResolution, {"expected_version": 1, "resolution": "ignore"}),
        (StaffReschedule, {"expected_version": 1, "starts_at": "2026-10-07T14:00:00"}),
    ],
)
def test_staff_actions_require_versions_and_exact_values(model: Any, body: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        model.model_validate(body)


def test_availability_window_is_bounded() -> None:
    base = {"service_id": "00000000-0000-0000-0000-000000000001", "first_day": "2026-10-06"}
    base["professional_id"] = base["service_id"]
    assert AvailabilityQuery.model_validate(base).days == 7
    for days in (0, 15):
        with pytest.raises(ValidationError):
            AvailabilityQuery.model_validate({**base, "days": days})
