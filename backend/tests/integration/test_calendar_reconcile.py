"""Reconciliation and periodic jobs against PostgreSQL/Redis with the in-memory calendar."""

from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import timedelta

import pytest
from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from lumini.booking.calendar import event_id
from lumini.booking.dispatch import deliver_due, tick
from lumini.booking.jobs import TICK_LOCK, run_reconcile, run_tick
from lumini.booking.reconcile import reconcile_calendars
from lumini.booking.service import HoldRequest, cancel_booking, confirm_deposit, create_hold
from lumini.models import Booking, BookingEvent, OutboxJob
from lumini.settings import Settings
from tests.booking_fakes import FakeCalendar
from tests.integration import test_booking_concurrency as concurrency
from tests.integration.test_booking_flow import (
    CAL,
    MINUTE,
    NOW,
    STAFF,
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
)

pytestmark = pytest.mark.integration
committed = concurrency.committed  # committed rows for jobs that open their own engine


@pytest.fixture
async def world(connection: AsyncConnection) -> AsyncIterator[World]:
    session = AsyncSession(
        bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    async with session.begin():
        professional_id = await professional(session)
        service_id = await published_service(session, professional_id)
        evaluation_id = await published_service(session, professional_id, booking_mode="evaluation")
    yield World(session, connection, FakeCalendar(), professional_id, service_id, evaluation_id)
    await session.close()


async def drift_events(world: World, booking_id: object) -> int:
    async with world.session.begin():
        rows = await world.session.scalars(
            select(BookingEvent.id).where(
                BookingEvent.booking_id == booking_id, BookingEvent.action == "calendar_drift"
            )
        )
        return len(list(rows))


async def test_event_deleted_in_google_is_put_back(world: World) -> None:
    booking = await confirmed(world, local(TUESDAY, 10))
    del world.calendar.events[CAL][event_id(booking.id)]

    report = await reconcile_calendars(world.session, world.calendar, now=NOW)
    assert (report.calendars, report.repaired, report.unavailable) == (1, 1, 0)
    current = await reload(world, booking.id)
    # Status and version are untouched: only the remote state is marked unknown.
    assert (current.status, current.version, current.calendar_status) == (
        "confirmed",
        booking.version,
        "none",
    )
    await deliver_due(world.session, calendar=world.calendar, notifier=None, now=NOW)
    assert world.calendar.status(CAL, event_id(booking.id)) == "confirmed"
    assert (await reload(world, booking.id)).calendar_status == "confirmed"
    assert await drift_events(world, booking.id) == 1

    again = await reconcile_calendars(world.session, world.calendar, now=NOW)
    assert again.repaired == 0


async def test_event_moved_in_google_returns_to_the_booked_time(world: World) -> None:
    booking = await held(world, local(TUESDAY, 10))
    remote = world.calendar.events[CAL][event_id(booking.id)]
    world.calendar.events[CAL][remote.id] = replace(
        remote, start=local(TUESDAY, 15), end=local(TUESDAY, 16)
    )
    assert (await reconcile_calendars(world.session, world.calendar, now=NOW)).repaired == 1
    await deliver_due(world.session, calendar=world.calendar, notifier=None, now=NOW)
    restored = world.calendar.events[CAL][remote.id]
    assert (restored.start, restored.end, restored.status) == (
        local(TUESDAY, 10),
        local(TUESDAY, 11),
        "tentative",
    )


async def test_event_restored_after_cancellation_is_removed_again(world: World) -> None:
    booking = await held(world, local(TUESDAY, 10))
    await cancel_booking(
        world.session, booking.id, actor=STAFF, expected_version=booking.version, now=NOW
    )
    await deliver_due(world.session, calendar=world.calendar, notifier=None, now=NOW)
    assert world.calendar.status(CAL, event_id(booking.id)) == "cancelled"
    remote = world.calendar.events[CAL][event_id(booking.id)]
    world.calendar.events[CAL][remote.id] = replace(remote, status="confirmed")  # undeleted

    assert (await reconcile_calendars(world.session, world.calendar, now=NOW)).repaired == 1
    await deliver_due(world.session, calendar=world.calendar, notifier=None, now=NOW)
    assert world.calendar.status(CAL, event_id(booking.id)) == "cancelled"
    assert (await reload(world, booking.id)).status == "cancelled"


async def test_in_flight_and_conflict_bookings_are_left_to_their_owners(world: World) -> None:
    contested = await hold(world, local(WEDNESDAY, 10))
    world.calendar.add_manual(CAL, local(WEDNESDAY, 10, 30), local(WEDNESDAY, 11))
    await deliver_due(world.session, calendar=world.calendar, notifier=None, now=NOW)
    assert (await reload(world, contested.id)).status == "conflict"
    pending = await hold(world, local(TUESDAY, 10))  # its own job will place the event
    world.calendar.events[CAL].clear()  # the conflict's event vanishes behind our back

    report = await reconcile_calendars(world.session, world.calendar, now=NOW)
    assert report.repaired == 0
    assert (await reload(world, pending.id)).calendar_status == "none"


async def test_unavailable_calendar_is_skipped_without_inferring_anything(world: World) -> None:
    booking = await confirmed(world, local(TUESDAY, 10))
    world.calendar.unavailable = 1
    report = await reconcile_calendars(world.session, world.calendar, now=NOW)
    assert (report.calendars, report.unavailable, report.repaired) == (0, 1, 0)
    assert (await reload(world, booking.id)).calendar_status == "confirmed"


async def test_confirmation_stuck_after_the_job_gave_up_is_requeued(world: World) -> None:
    booking = await held(world, local(TUESDAY, 10))
    await confirm_deposit(
        world.session,
        booking.id,
        actor=STAFF,
        expected_version=booking.version,
        amount_brl=booking.deposit_brl,
        now=NOW,
    )
    async with world.session.begin():  # a long outage exhausted the retries
        await world.session.execute(
            update(OutboxJob).where(OutboxJob.booking_id == booking.id).values(status="failed")
        )

    idle = await tick(world.session, calendar=None, notifier=None, now=NOW + MINUTE)
    assert idle.requeued == 0
    assert (await reload(world, booking.id)).status == "confirming"

    later = NOW + timedelta(hours=1)
    report = await tick(world.session, calendar=world.calendar, notifier=None, now=later)
    assert report.requeued == 1
    assert (await reload(world, booking.id)).status == "confirmed"
    assert world.calendar.status(CAL, event_id(booking.id)) == "confirmed"
    assert (
        await tick(world.session, calendar=world.calendar, notifier=None, now=later)
    ).requeued == 0


async def test_tick_without_calendar_never_turns_missing_setup_into_conflicts(
    world: World,
) -> None:
    booking = await hold(world, local(TUESDAY, 10))
    await tick(world.session, calendar=None, notifier=None, now=NOW + MINUTE)
    assert (await reload(world, booking.id)).status == "pending_calendar"
    await tick(world.session, calendar=None, notifier=None, now=NOW + 11 * MINUTE)
    current = await reload(world, booking.id)
    assert (current.status, current.closed_reason) == ("expired", "calendar_timeout")


async def test_periodic_jobs_use_their_own_session_and_skip_while_locked(
    committed: concurrency.Committed, integration_settings: Settings
) -> None:
    async with committed.sessions() as session:
        booking = await create_hold(
            session,
            committed.calendar,
            HoldRequest(
                "synthetic-periodic-0001",
                committed.service_id,
                committed.professional_id,
                local(TUESDAY, 10),
                "Synthetic periodic",
                f"{concurrency.PHONE_PREFIX}0101",
            ),
            now=NOW,
        )

    report = await run_tick(integration_settings, calendar=committed.calendar, clock=lambda: NOW)
    assert report is not None and report.delivered == 1
    async with committed.sessions() as session, session.begin():
        stored = await session.get(Booking, booking.id)
        assert stored is not None and stored.status == "held"

    assert integration_settings.redis_url is not None
    redis = Redis.from_url(integration_settings.redis_url.get_secret_value())
    try:
        lock = redis.lock(TICK_LOCK, timeout=30)
        assert await lock.acquire(blocking=False)
        try:
            assert (
                await run_tick(integration_settings, calendar=committed.calendar, clock=lambda: NOW)
                is None
            )
        finally:
            await lock.release()
    finally:
        await redis.aclose()

    reconciled = await run_reconcile(
        integration_settings, calendar=committed.calendar, clock=lambda: NOW
    )
    assert reconciled is not None and reconciled.repaired == 0 and reconciled.calendars >= 1


async def test_other_commitments_over_live_bookings_are_flagged_not_changed(world: World) -> None:
    confirmed_booking = await confirmed(world, local(TUESDAY, 10))
    holding = await held(world, local(WEDNESDAY, 10))
    closed = await held(world, local(WEDNESDAY, 14))
    await cancel_booking(
        world.session, closed.id, actor=STAFF, expected_version=closed.version, now=NOW
    )
    await deliver_due(world.session, calendar=world.calendar, notifier=None, now=NOW)
    for start, end in (
        (local(TUESDAY, 10, 30), local(TUESDAY, 11, 30)),  # over the confirmed appointment
        (local(WEDNESDAY, 9), local(WEDNESDAY, 10, 15)),  # over the unpaid hold
        (local(WEDNESDAY, 14), local(WEDNESDAY, 15)),  # over a cancelled booking: irrelevant
    ):
        world.calendar.add_manual(CAL, start, end)

    report = await reconcile_calendars(world.session, world.calendar, now=NOW)
    assert (report.overlaps_flagged, report.overlaps_cleared, report.repaired) == (2, 0, 0)
    for item in (confirmed_booking, holding):
        current = await reload(world, item.id)
        assert current.calendar_overlap_at == NOW and current.status == item.status
    assert (await reload(world, closed.id)).calendar_overlap_at is None
    again = await reconcile_calendars(world.session, world.calendar, now=NOW)
    assert again.overlaps_flagged == 0  # flagged once

    world.calendar.manual.clear()
    cleared = await reconcile_calendars(world.session, world.calendar, now=NOW)
    assert cleared.overlaps_cleared == 2
    assert (await reload(world, confirmed_booking.id)).calendar_overlap_at is None
    async with world.session.begin():
        actions = list(
            await world.session.scalars(
                select(BookingEvent.action)
                .where(BookingEvent.booking_id == confirmed_booking.id)
                .order_by(BookingEvent.created_at)
            )
        )
    assert actions[-2:] == ["calendar_overlap", "calendar_overlap_cleared"]
