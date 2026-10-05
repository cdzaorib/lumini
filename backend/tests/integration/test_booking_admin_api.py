"""Staff agenda and booking HTTP routes against PostgreSQL (rolled back) and a calendar double."""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx2 import ASGITransport, AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from lumini.app import create_app
from lumini.auth import AdminPrincipal, require_admin
from lumini.booking.service import sync_calendar
from lumini.deps import get_session
from lumini.models import BookingEvent, CatalogAuditEvent, OutboxJob, Professional
from lumini.settings import Settings
from tests.booking_fakes import FakeCalendar
from tests.integration.test_booking_flow import (
    CAL,
    MINUTE,
    NOW,
    TUESDAY,
    WEDNESDAY,
    World,
    confirmed,
    held,
    hold,
    local,
    professional,
    published_service,
    reload,
    slots_on,
)

pytestmark = pytest.mark.integration

SUBJECT = "synthetic-staff-subject"
OTHER_CAL = "synthetic-other@group.calendar.google.com"


@dataclass
class Api:
    app: FastAPI
    http: AsyncClient
    world: World
    now: list[datetime] = field(default_factory=lambda: [NOW])

    async def call(self, method: str, path: str, body: Any = None) -> Response:
        response = await self.http.request(method, f"/api/admin{path}", json=body)
        assert response.headers["cache-control"] == "no-store"
        return response

    async def ok(self, method: str, path: str, body: Any = None) -> Any:
        response = await self.call(method, path, body)
        assert response.status_code == 200, response.text
        return response.json()

    async def refused(self, method: str, path: str, body: Any, status: int, code: str) -> None:
        response = await self.call(method, path, body)
        assert (response.status_code, response.json().get("code")) == (status, code), response.text


@pytest.fixture
async def api(connection: AsyncConnection) -> AsyncIterator[Api]:
    session = AsyncSession(
        bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    async with session.begin():
        professional_id = await professional(session)
        service_id = await published_service(session, professional_id)
        evaluation_id = await published_service(session, professional_id, booking_mode="evaluation")
    world = World(session, connection, FakeCalendar(), professional_id, service_id, evaluation_id)
    app = create_app(Settings(environment="test"))

    async def session_override() -> AsyncIterator[AsyncSession]:
        async with AsyncSession(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        ) as request_session:
            yield request_session

    async def actor_override() -> AdminPrincipal:
        return AdminPrincipal(
            subject=SUBJECT, email="staff@example.invalid", reviewer_professional_ids=()
        )

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_admin] = actor_override
    app.state.calendar = world.calendar
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://synthetic.test"
    ) as http:
        client = Api(app, http, world)
        app.state.clock = lambda: client.now[0]
        yield client
    await session.close()


def rules(*windows: tuple[int, str, str]) -> list[dict[str, Any]]:
    return [{"weekday": day, "start": start, "end": end} for day, start, end in windows]


def availability(api: Api, *, service_id: UUID | None = None, days: int = 1) -> str:
    world = api.world
    return (
        f"/availability?service_id={service_id or world.service_id}"
        f"&professional_id={world.professional_id}&first_day={TUESDAY}&days={days}"
    )


ID = uuid4()


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/admin/bookings"),
        ("get", f"/api/admin/bookings/{ID}"),
        ("post", f"/api/admin/bookings/{ID}/deposit"),
        ("post", f"/api/admin/bookings/{ID}/cancel"),
        ("post", f"/api/admin/bookings/{ID}/resolve"),
        ("post", f"/api/admin/bookings/{ID}/reschedule"),
        ("get", f"/api/admin/professionals/{ID}/schedule"),
        ("put", f"/api/admin/professionals/{ID}/schedule"),
        (
            "get",
            f"/api/admin/availability?service_id={ID}&professional_id={ID}&first_day={TUESDAY}",
        ),
    ],
)
async def test_anonymous_requests_fail_before_database_or_calendar(
    api: Api, method: str, path: str
) -> None:
    api.app.dependency_overrides.pop(require_admin)

    async def forbidden_database_access() -> AsyncIterator[AsyncSession]:
        raise AssertionError("Anonymous request accessed database")
        yield  # pragma: no cover

    api.app.dependency_overrides[get_session] = forbidden_database_access
    response = await api.http.request(method, path, json={})
    assert response.status_code == 401, response.text
    assert api.world.calendar.calls == []


async def test_agenda_is_versioned_and_never_touches_credentials(api: Api) -> None:
    session = api.world.session
    async with session.begin():
        person = await professional(session, schedule=False)
    path = f"/professionals/{person}/schedule"
    assert await api.ok("get", path) == {
        "professional_id": str(person),
        "calendar_id": None,
        "revision": 0,
        "rules": [],
    }
    body = {
        "expected_revision": 0,
        "calendar_id": OTHER_CAL,
        "rules": rules((2, "08:00", "12:00"), (0, "13:00", "18:00"), (0, "09:00", "12:00")),
    }
    saved = await api.ok("put", path, body)
    assert saved["revision"] == 1
    assert saved["rules"] == rules(
        (0, "09:00:00", "12:00:00"), (0, "13:00:00", "18:00:00"), (2, "08:00:00", "12:00:00")
    )
    assert await api.ok("get", path) == saved
    await api.refused("put", path, body, 409, "stale")
    cleared = await api.ok("put", path, {"expected_revision": 1, "calendar_id": None})
    assert (cleared["revision"], cleared["calendar_id"], cleared["rules"]) == (2, None, [])

    async with session.begin():
        stored = await session.get(Professional, person, populate_existing=True)
        audit = (
            await session.execute(
                select(CatalogAuditEvent.action, CatalogAuditEvent.revision)
                .where(CatalogAuditEvent.target_id == person)
                .order_by(CatalogAuditEvent.revision)
            )
        ).all()
    assert stored is not None
    assert stored.credentials_verified_at is not None and stored.revision == 1
    assert [tuple(row) for row in audit] == [("schedule.updated", 1), ("schedule.updated", 2)]


@pytest.mark.parametrize(
    "body",
    [
        {"rules": rules((1, "09:00", "12:00"), (1, "11:45", "14:00"))},
        {"rules": rules((1, "09:10", "12:00"))},
        {"rules": rules((1, "12:00", "09:00"))},
        {"rules": rules((7, "09:00", "12:00"))},
        {"rules": rules((1, "09:00-03:00", "12:00"))},
        {"calendar_id": "<script>synthetic</script>@example.invalid"},
        {"calendar_id": OTHER_CAL, "status": "verified"},
    ],
)
async def test_invalid_agenda_is_rejected_without_echo(api: Api, body: dict[str, Any]) -> None:
    path = f"/professionals/{api.world.professional_id}/schedule"
    response = await api.call("put", path, {"expected_revision": 1, **body})
    assert response.status_code == 422, response.text
    assert "script" not in response.text and "09:10" not in response.text
    assert (await api.ok("get", path))["revision"] == 1


async def test_unknown_professional_agenda_is_not_found(api: Api) -> None:
    path = f"/professionals/{uuid4()}/schedule"
    await api.refused("get", path, None, 404, "not_found")
    await api.refused("put", path, {"expected_revision": 0}, 404, "not_found")


async def test_calendar_cannot_change_while_bookings_depend_on_it(api: Api) -> None:
    world = api.world
    booking = await held(world, local(TUESDAY, 10))
    path = f"/professionals/{world.professional_id}/schedule"
    week = rules(*((day, "08:00", "20:00") for day in range(7)))
    moved = {"expected_revision": 1, "calendar_id": OTHER_CAL, "rules": week}
    await api.refused("put", path, moved, 409, "calendar_in_use")

    # Working hours may change: existing bookings keep their times.
    narrowed = await api.ok(
        "put", path, {"expected_revision": 1, "calendar_id": CAL, "rules": week[:1]}
    )
    assert narrowed["revision"] == 2
    moved["expected_revision"] = 2

    cancelled = await api.ok("post", f"/bookings/{booking.id}/cancel", {"expected_version": 2})
    assert (cancelled["status"], cancelled["calendar_status"]) == ("cancelled", "tentative")
    await api.refused("put", path, moved, 409, "calendar_in_use")  # removal still pending
    await sync_calendar(world.session, world.calendar, booking.id, now=NOW)
    assert (await api.ok("put", path, moved))["calendar_id"] == OTHER_CAL


async def test_availability_preview_matches_the_booking_rules(api: Api) -> None:
    world = api.world
    world.calendar.add_manual(CAL, local(TUESDAY, 10), local(TUESDAY, 11))
    await held(world, local(TUESDAY, 14))
    preview = await api.ok("get", availability(api))
    slots = [datetime.fromisoformat(item) for item in preview["slots"]]
    assert slots == await slots_on(world, TUESDAY)
    assert local(TUESDAY, 8) in slots  # 09:00 would run into the manual event with its buffer
    assert local(TUESDAY, 10) not in slots and local(TUESDAY, 14) not in slots


async def test_availability_preview_refusals(api: Api) -> None:
    evaluation = availability(api, service_id=api.world.evaluation_service_id)
    await api.refused("get", evaluation, None, 409, "evaluation_required")
    assert (await api.call("get", availability(api, days=15))).status_code == 422

    api.world.calendar.unavailable = 1
    outage = await api.call("get", availability(api))
    assert (outage.status_code, outage.json()["code"]) == (503, "calendar_unavailable")
    assert "synthetic" not in outage.text

    api.app.state.calendar = None
    await api.refused("get", availability(api), None, 503, "calendar_not_configured")


async def test_staff_see_contact_and_confirm_only_the_exact_deposit(api: Api) -> None:
    world = api.world
    booking = await held(
        world, local(TUESDAY, 10), name="Synthetic Contact", phone="+5521999990001"
    )
    [listed] = await api.ok("get", "/bookings")
    assert listed["id"] == str(booking.id)
    assert listed["code"] == booking.id.hex[:8].upper()
    assert listed["contact"] == {"name": "Synthetic Contact", "phone": "+5521999990001"}
    assert (listed["status"], listed["version"], listed["deposit_brl"]) == ("held", 2, "50.00")
    assert datetime.fromisoformat(listed["expires_at"]) == NOW + timedelta(hours=2)

    path = f"/bookings/{booking.id}/deposit"
    await api.refused(
        "post", path, {"expected_version": 2, "amount_brl": "49.99"}, 409, "deposit_mismatch"
    )
    await api.refused("post", path, {"expected_version": 1, "amount_brl": "50.00"}, 409, "stale")
    api.now[0] = NOW + 30 * MINUTE
    confirming = await api.ok("post", path, {"expected_version": 2, "amount_brl": "50.00"})
    assert (confirming["status"], confirming["version"]) == ("confirming", 3)
    assert datetime.fromisoformat(confirming["deposit_confirmed_at"]) == NOW + 30 * MINUTE
    await api.refused(
        "post", path, {"expected_version": 3, "amount_brl": "50.00"}, 409, "invalid_state"
    )

    async with world.session.begin():
        actors = (
            await world.session.execute(
                select(BookingEvent.actor_type, BookingEvent.actor_subject).where(
                    BookingEvent.booking_id == booking.id,
                    BookingEvent.action == "deposit_confirmed",
                )
            )
        ).all()
        sync_jobs = await world.session.scalars(
            select(OutboxJob.status).where(
                OutboxJob.booking_id == booking.id, OutboxJob.kind == "calendar_sync"
            )
        )
        assert "pending" in list(sync_jobs)
    assert [tuple(row) for row in actors] == [("staff", SUBJECT)]


async def test_expired_hold_cannot_be_confirmed(api: Api) -> None:
    booking = await held(api.world, local(TUESDAY, 10))
    api.now[0] = NOW + timedelta(hours=2)
    body = {"expected_version": booking.version, "amount_brl": "50.00"}
    await api.refused("post", f"/bookings/{booking.id}/deposit", body, 409, "hold_expired")


async def test_history_keeps_closed_and_past_bookings_apart(api: Api) -> None:
    world = api.world
    cancelled = await held(world, local(TUESDAY, 10))
    waiting = await held(world, local(TUESDAY, 14))
    attended = await confirmed(world, local(WEDNESDAY, 10))
    result = await api.ok("post", f"/bookings/{cancelled.id}/cancel", {"expected_version": 2})
    assert (result["status"], result["closed_reason"]) == ("cancelled", "cancelled_by_staff")
    await api.refused(
        "post", f"/bookings/{cancelled.id}/cancel", {"expected_version": 3}, 409, "invalid_state"
    )

    async def ids(scope: str) -> list[str]:
        return [item["id"] for item in await api.ok("get", f"/bookings?scope={scope}")]

    assert await ids("upcoming") == [str(waiting.id), str(attended.id)]
    assert await ids("history") == [str(cancelled.id)]
    # After the appointment ends it leaves the queue; an unattended hold stays until handled.
    api.now[0] = local(WEDNESDAY, 12)
    assert await ids("upcoming") == [str(waiting.id)]
    assert await ids("history") == [str(attended.id), str(cancelled.id)]
    assert (await api.call("get", "/bookings?scope=all")).status_code == 422


async def test_staff_resolve_conflicts_once(api: Api) -> None:
    world = api.world
    booking = await hold(world, local(TUESDAY, 10))
    world.calendar.add_manual(CAL, local(TUESDAY, 10, 30), local(TUESDAY, 11))
    await sync_calendar(world.session, world.calendar, booking.id, now=NOW)
    current = await reload(world, booking.id)
    assert current.status == "conflict"
    path = f"/bookings/{booking.id}/resolve"
    invalid = await api.call(
        "post", path, {"expected_version": current.version, "resolution": "ignore"}
    )
    assert invalid.status_code == 422
    released = await api.ok(
        "post", path, {"expected_version": current.version, "resolution": "release"}
    )
    assert (released["status"], released["closed_reason"]) == ("cancelled", "conflict_released")
    body = {"expected_version": released["version"], "resolution": "retry"}
    await api.refused("post", path, body, 409, "invalid_state")


async def test_staff_reschedule_answers_the_replacement(api: Api) -> None:
    world = api.world
    original = await confirmed(world, local(TUESDAY, 10))
    path = f"/bookings/{original.id}/reschedule"
    naive = await api.call(
        "post", path, {"expected_version": original.version, "starts_at": "2026-10-07T14:00:00"}
    )
    assert naive.status_code == 422
    too_close = {
        "expected_version": original.version,
        "starts_at": (NOW + timedelta(hours=1)).isoformat(),
    }
    await api.refused("post", path, too_close, 409, "too_close")

    body = {"expected_version": original.version, "starts_at": local(WEDNESDAY, 14).isoformat()}
    replacement = await api.ok("post", path, body)
    assert replacement["id"] != str(original.id)
    assert replacement["rescheduled_from_id"] == str(original.id)
    assert (replacement["status"], replacement["reschedule_count"]) == ("pending_calendar", 1)
    assert replacement["deposit_confirmed_at"] is not None
    assert datetime.fromisoformat(replacement["starts_at"]) == local(WEDNESDAY, 14)
    moved = await api.ok("get", f"/bookings/{original.id}")
    assert (moved["status"], moved["closed_reason"]) == ("cancelled", "rescheduled")
    assert await api.ok("post", path, body) == replacement  # idempotent retry

    held_booking = await held(world, local(TUESDAY, 15))
    body = {"expected_version": held_booking.version, "starts_at": local(WEDNESDAY, 16).isoformat()}
    await api.refused("post", f"/bookings/{held_booking.id}/reschedule", body, 409, "invalid_state")


async def test_unknown_booking_is_not_found(api: Api) -> None:
    missing = uuid4()
    await api.refused("get", f"/bookings/{missing}", None, 404, "not_found")
    for action, body in [
        ("deposit", {"expected_version": 1, "amount_brl": "50.00"}),
        ("cancel", {"expected_version": 1}),
        ("resolve", {"expected_version": 1, "resolution": "release"}),
        ("reschedule", {"expected_version": 1, "starts_at": local(WEDNESDAY, 14).isoformat()}),
    ]:
        await api.refused("post", f"/bookings/{missing}/{action}", body, 404, "not_found")


async def test_attendance_is_recorded_after_the_start_and_freezes_the_booking(api: Api) -> None:
    world = api.world
    booking = await confirmed(world, local(TUESDAY, 10))
    path = f"/bookings/{booking.id}/attendance"
    body = {"expected_version": booking.version, "attendance": "attended"}
    await api.refused("post", path, body, 409, "too_early")
    api.now[0] = local(TUESDAY, 10, 5)
    await api.refused("post", path, {**body, "expected_version": 1}, 409, "stale")
    marked = await api.ok("post", path, body)
    assert (marked["attendance"], marked["version"]) == ("attended", booking.version + 1)
    version = {"expected_version": marked["version"]}
    await api.refused("post", f"/bookings/{booking.id}/cancel", version, 409, "attendance_recorded")
    move = {**version, "starts_at": local(WEDNESDAY, 14).isoformat()}
    await api.refused(
        "post", f"/bookings/{booking.id}/reschedule", move, 409, "attendance_recorded"
    )
    holding = await held(world, local(WEDNESDAY, 10))
    hold_body = {"expected_version": holding.version, "attendance": "no_show"}
    await api.refused("post", f"/bookings/{holding.id}/attendance", hold_body, 409, "invalid_state")


async def test_no_show_gets_no_aftercare(api: Api) -> None:
    from lumini.booking.service import enqueue_due_notifications

    world = api.world
    present = await confirmed(world, local(TUESDAY, 10))
    absent = await confirmed(world, local(TUESDAY, 14))
    api.now[0] = local(TUESDAY, 16)
    for item, mark in ((present, "attended"), (absent, "no_show")):
        current = await api.ok("get", f"/bookings/{item.id}")
        body = {"expected_version": current["version"], "attendance": mark}
        await api.ok("post", f"/bookings/{item.id}/attendance", body)
    await enqueue_due_notifications(world.session, now=local(TUESDAY, 16))
    async with world.session.begin():
        aftercare = set(
            await world.session.scalars(
                select(OutboxJob.booking_id).where(OutboxJob.event == "aftercare")
            )
        )
    assert aftercare == {present.id}


async def test_booking_history_shows_steps_without_identifying_staff(api: Api) -> None:
    booking = await confirmed(api.world, local(TUESDAY, 10))
    history = await api.ok("get", f"/bookings/{booking.id}/events")
    assert [(item["action"], item["actor"]) for item in history] == [
        ("hold_requested", "client"),
        ("held", "system"),
        ("deposit_confirmed", "staff"),
        ("confirmed", "system"),
    ]
    assert "subject" not in str(history) and "synthetic-staff" not in str(history)
    await api.refused("get", f"/bookings/{uuid4()}/events", None, 404, "not_found")


async def test_metrics_count_the_plan_indicators(api: Api) -> None:
    from lumini.models import Lead

    world = api.world
    attended = await confirmed(world, local(TUESDAY, 9), key="wa:synthetic-metrics-0001")
    absent = await confirmed(world, local(TUESDAY, 11), key="web:synthetic-metrics-0002")
    cancelled = await held(world, local(TUESDAY, 15))
    await api.ok(
        "post", f"/bookings/{cancelled.id}/cancel", {"expected_version": cancelled.version}
    )
    async with world.session.begin():
        for index, marketing in enumerate((True, False)):
            world.session.add(
                Lead(
                    id=uuid4(),
                    name="Lead Sintética",
                    phone_e164=f"+55219000001{index}",
                    source="site_form",
                    status="new",
                    service_id=world.service_id,
                    contact_consent_at=NOW,
                    marketing_consent_at=NOW if marketing else None,
                    retain_until=NOW + timedelta(days=90),
                    created_at=NOW,
                )
            )
    api.now[0] = local(TUESDAY, 13)
    for item, mark in ((attended, "attended"), (absent, "no_show")):
        current = await api.ok("get", f"/bookings/{item.id}")
        await api.ok(
            "post",
            f"/bookings/{item.id}/attendance",
            {"expected_version": current["version"], "attendance": mark},
        )
    metrics = await api.ok("get", "/metrics?days=30")
    assert (metrics["leads_total"], metrics["leads_marketing_consent"]) == (2, 1)
    assert metrics["bookings_requested"] == 3 and metrics["deposits_confirmed"] == 2
    assert {item["key"]: item["count"] for item in metrics["bookings_by_origin"]} == {
        "whatsapp": 1,
        "site": 1,
        "other": 1,
    }
    assert (metrics["appointments"], metrics["attended"], metrics["no_show"]) == (2, 1, 1)
    assert metrics["cancellations"] == [{"key": "cancelled_by_staff", "count": 1}]
    assert metrics["demand_by_service"] == [{"key": "Synthetic procedure", "count": 3}]
    assert (await api.call("get", "/metrics?days=0")).status_code == 422
