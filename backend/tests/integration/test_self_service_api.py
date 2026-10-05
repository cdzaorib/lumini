"""Client self-service links against PostgreSQL (rolled back), real Redis and a calendar double."""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx2 import ASGITransport, AsyncClient, Response
from pydantic import SecretStr
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from lumini.app import create_app
from lumini.auth import AdminPrincipal, require_admin
from lumini.booking import public_router
from lumini.booking.dispatch import deliver_due
from lumini.booking.links import issue_token
from lumini.deps import get_session
from lumini.models import Booking, BookingEvent
from lumini.resources import Resources
from lumini.settings import Settings
from tests.booking_fakes import FakeCalendar
from tests.integration.test_booking_flow import (
    MINUTE,
    NOW,
    TUESDAY,
    WEDNESDAY,
    World,
    confirmed,
    held,
    local,
    professional,
    published_service,
)

pytestmark = pytest.mark.integration

SECRET = "synthetic-manage-link-secret-0123456789"
SITE = "https://synthetic.example"


@dataclass
class Client:
    app: FastAPI
    http: AsyncClient
    world: World
    redis: Redis
    now: list[datetime] = field(default_factory=lambda: [NOW])

    def token(self, booking_id: UUID, expires: datetime | None = None) -> str:
        return issue_token(SECRET, booking_id, expires or NOW + timedelta(days=30))

    async def call(self, method: str, path: str, token: str, body: Any = None) -> Response:
        response = await self.http.request(
            method,
            f"/api/public/booking{path}",
            json=body,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.headers["cache-control"] == "no-store"
        return response

    async def ok(self, method: str, path: str, token: str, body: Any = None) -> Any:
        response = await self.call(method, path, token, body)
        assert response.status_code == 200, response.text
        return response.json()

    async def refused(
        self, method: str, path: str, token: str, body: Any, status: int, code: str
    ) -> None:
        response = await self.call(method, path, token, body)
        assert (response.status_code, response.json().get("code")) == (status, code), response.text


@pytest.fixture
async def client(
    connection: AsyncConnection, integration_settings: Settings
) -> AsyncIterator[Client]:
    session = AsyncSession(
        bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    async with session.begin():
        professional_id = await professional(session)
        service_id = await published_service(session, professional_id)
        evaluation_id = await published_service(session, professional_id, booking_mode="evaluation")
    world = World(session, connection, FakeCalendar(), professional_id, service_id, evaluation_id)
    app = create_app(
        Settings(
            environment="test",
            manage_link_secret=SecretStr(SECRET),
            public_site_url=SITE,
        )
    )
    assert integration_settings.redis_url is not None
    redis = Redis.from_url(integration_settings.redis_url.get_secret_value(), decode_responses=True)
    app.state.resources = Resources(redis_client=redis)
    app.state.calendar = world.calendar

    async def session_override() -> AsyncIterator[AsyncSession]:
        async with AsyncSession(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        ) as request_session:
            yield request_session

    async def staff() -> AdminPrincipal:
        return AdminPrincipal(
            subject="synthetic-staff-subject",
            email="staff@example.invalid",
            reviewer_professional_ids=(),
        )

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_admin] = staff
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://synthetic.test"
        ) as http:
            result = Client(app, http, world, redis)
            app.state.clock = lambda: result.now[0]
            yield result
    finally:
        async for key in redis.scan_iter("lumini:rl:*"):
            await redis.delete(key)
        await redis.aclose()
        await session.close()


ROUTES = [
    ("get", ""),
    ("get", f"/availability?first_day={TUESDAY}"),
    ("post", "/cancel"),
    ("post", "/reschedule"),
]


@pytest.mark.parametrize(("method", "path"), ROUTES)
async def test_bad_links_fail_alike_before_the_database(
    client: Client, method: str, path: str
) -> None:
    async def forbidden_database_access() -> AsyncIterator[AsyncSession]:
        raise AssertionError("Invalid link accessed the database")
        yield  # pragma: no cover

    client.app.dependency_overrides[get_session] = forbidden_database_access
    good = client.token(uuid4())
    for token in (
        "",
        "not-a-token",
        issue_token("another-synthetic-secret-0123456789abc", uuid4(), NOW + timedelta(days=1)),
        issue_token(SECRET, uuid4(), NOW - MINUTE),  # expired
        good[:-1] + ("A" if good[-1] != "A" else "B"),
    ):
        response = await client.http.request(
            method,
            f"/api/public/booking{path}",
            json={},
            headers={"Authorization": f"Bearer {token}"} if token else {},
        )
        assert (response.status_code, response.json()["code"]) == (404, "link_invalid")
    assert client.world.calendar.calls == []


async def test_unknown_booking_looks_like_a_bad_link(client: Client) -> None:
    await client.refused("get", "", client.token(uuid4()), None, 404, "link_invalid")


async def test_links_are_off_until_configured(client: Client) -> None:
    client.app.state.settings = Settings(environment="test")
    await client.refused("get", "", client.token(uuid4()), None, 503, "self_service_unavailable")


async def test_client_sees_their_booking_without_contact_data(client: Client) -> None:
    booking = await confirmed(
        client.world, local(WEDNESDAY, 10), name="Synthetic Visible?", phone="+5521999990077"
    )
    view = await client.ok("get", "", client.token(booking.id))
    assert view["code"] == booking.id.hex[:8].upper()
    assert (view["status"], view["service"], view["professional"]) == (
        "confirmed",
        "Synthetic procedure",
        "Synthetic professional",
    )
    assert (view["can_cancel"], view["can_reschedule"]) == (True, True)
    assert (view["deposit_brl"], view["deposit_confirmed"]) == ("50.00", True)
    assert datetime.fromisoformat(view["self_service_until"]) == local(WEDNESDAY, 10) - timedelta(
        hours=24
    )
    text = str(view)
    assert "999990077" not in text and "Visible" not in text and str(booking.id) not in text


async def test_unpaid_hold_can_be_given_back_but_not_moved(client: Client) -> None:
    booking = await held(client.world, local(TUESDAY, 10))
    token = client.token(booking.id)
    view = await client.ok("get", "", token)
    assert (view["can_cancel"], view["can_reschedule"], view["reschedule_blocked"]) == (
        True,
        False,
        "not_confirmed",
    )
    assert view["hold_expires_at"] is not None
    await client.refused(
        "get", f"/availability?first_day={TUESDAY}", token, None, 409, "not_confirmed"
    )
    cancelled = await client.ok("post", "/cancel", token, {"expected_version": view["version"]})
    assert (cancelled["status"], cancelled["can_cancel"], cancelled["cancel_blocked"]) == (
        "cancelled",
        False,
        "closed",
    )
    async with client.world.session.begin():
        actors = (
            await client.world.session.execute(
                select(BookingEvent.actor_type, BookingEvent.actor_subject).where(
                    BookingEvent.booking_id == booking.id, BookingEvent.action == "cancelled"
                )
            )
        ).all()
    assert [tuple(row) for row in actors] == [("client", None)]


async def test_within_24_hours_the_clinic_decides(client: Client) -> None:
    booking = await confirmed(client.world, local(WEDNESDAY, 10))
    token = client.token(booking.id)
    client.now[0] = local(WEDNESDAY, 10) - timedelta(hours=24)  # exactly 24h: human
    view = await client.ok("get", "", token)
    assert (view["cancel_blocked"], view["reschedule_blocked"]) == ("within_24h", "within_24h")
    body = {"expected_version": view["version"]}
    await client.refused("post", "/cancel", token, body, 409, "within_24h")
    body = {**body, "starts_at": local(WEDNESDAY, 15).isoformat()}
    await client.refused("post", "/reschedule", token, body, 409, "within_24h")


async def test_one_reschedule_keeps_the_deposit_and_issues_a_new_link(client: Client) -> None:
    booking = await confirmed(client.world, local(WEDNESDAY, 10))
    token = client.token(booking.id)
    preview = await client.ok("get", f"/availability?first_day={WEDNESDAY}&days=1", token)
    slots = [datetime.fromisoformat(slot) for slot in preview["slots"]]
    assert local(WEDNESDAY, 14) in slots and local(WEDNESDAY, 10) not in slots

    body = {"expected_version": booking.version, "starts_at": local(WEDNESDAY, 14).isoformat()}
    moved = await client.ok("post", "/reschedule", token, body)
    new = moved["booking"]
    assert (new["status"], new["deposit_confirmed"]) == ("pending_calendar", True)
    assert datetime.fromisoformat(new["starts_at"]) == local(WEDNESDAY, 14)
    assert (await client.ok("get", "", moved["token"]))["code"] == new["code"]
    old = await client.ok("get", "", token)
    assert (old["status"], old["can_reschedule"]) == ("cancelled", False)

    # The replacement becomes confirmed once the calendar accepts it; a second move is human.
    await deliver_due(client.world.session, calendar=client.world.calendar, notifier=None, now=NOW)
    second = await client.ok("get", "", moved["token"])
    assert (second["status"], second["reschedule_blocked"]) == ("confirmed", "second_reschedule")
    body = {"expected_version": second["version"], "starts_at": local(WEDNESDAY, 16).isoformat()}
    await client.refused("post", "/reschedule", moved["token"], body, 409, "second_reschedule")


async def test_a_leaked_link_cannot_drain_the_calendar_quota(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(public_router, "AVAILABILITY_LIMIT", 2)
    booking = await confirmed(client.world, local(WEDNESDAY, 10))
    token = client.token(booking.id)
    path = f"/availability?first_day={WEDNESDAY}&days=1"
    for _ in range(2):
        await client.ok("get", path, token)
    await client.refused("get", path, token, None, 429, "rate_limited")
    assert len([call for call in client.world.calendar.calls if call == "list_busy"]) <= 4


async def test_staff_issue_links_for_open_bookings_only(client: Client) -> None:
    booking = await held(client.world, local(TUESDAY, 10))
    response = await client.http.post(f"/api/admin/bookings/{booking.id}/manage-link")
    assert response.status_code == 200, response.text
    link = response.json()
    assert link["url"].startswith(f"{SITE}/reserva#")
    assert datetime.fromisoformat(link["expires_at"]) == local(TUESDAY, 10)
    token = link["url"].split("#", 1)[1]
    assert (await client.ok("get", "", token))["status"] == "held"
    async with client.world.session.begin():
        stored = await client.world.session.get(Booking, booking.id, populate_existing=True)
        issued = await client.world.session.scalar(
            select(BookingEvent.actor_subject).where(
                BookingEvent.booking_id == booking.id,
                BookingEvent.action == "manage_link_issued",
            )
        )
    assert stored is not None and issued == "synthetic-staff-subject"

    await client.ok("post", "/cancel", token, {"expected_version": stored.version})
    closed = await client.http.post(f"/api/admin/bookings/{booking.id}/manage-link")
    assert (closed.status_code, closed.json()["code"]) == (409, "invalid_state")

    client.app.state.settings = Settings(environment="test")
    other = await held(client.world, local(TUESDAY, 15))
    missing = await client.http.post(f"/api/admin/bookings/{other.id}/manage-link")
    assert (missing.status_code, missing.json()["code"]) == (503, "manage_link_not_configured")
