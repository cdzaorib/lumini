"""Booking rules against real PostgreSQL (rolled back) with an in-memory calendar double."""

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from lumini.booking.calendar import event_id
from lumini.booking.dispatch import deliver_due
from lumini.booking.policy import CLINIC_TZ
from lumini.booking.service import (
    CLIENT,
    Actor,
    BookingConflict,
    HoldRequest,
    InvalidBookingRequest,
    NotBookable,
    RequiresHuman,
    SlotUnavailable,
    available_slots,
    cancel_booking,
    confirm_deposit,
    create_hold,
    enqueue_due_notifications,
    expire_due,
    reschedule_booking,
    resolve_conflict,
    sync_calendar,
)
from lumini.models import (
    AvailabilityRule,
    Booking,
    OutboxJob,
    Professional,
    ProfessionalSchedule,
    ProfessionalService,
    Service,
    ServiceApproval,
)
from tests.booking_fakes import FakeCalendar

pytestmark = pytest.mark.integration

MONDAY, TUESDAY, WEDNESDAY = date(2026, 10, 5), date(2026, 10, 6), date(2026, 10, 7)
CAL = "synthetic-calendar@group.calendar.google.com"
STAFF = Actor.staff("synthetic-staff-subject")
MINUTE = timedelta(minutes=1)


def local(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=CLINIC_TZ).astimezone(UTC)


NOW = local(MONDAY, 9)


@dataclass
class World:
    session: AsyncSession
    connection: AsyncConnection
    calendar: FakeCalendar
    professional_id: UUID
    service_id: UUID
    evaluation_service_id: UUID
    keys: int = 0


async def professional(session: AsyncSession, *, schedule: bool = True) -> UUID:
    person = Professional(
        id=uuid4(),
        display_name="Synthetic professional",
        category="Synthetic category",
        council_registration="SYNTHETIC-REG",
        credentials_verified_at=NOW - timedelta(days=1),
        credentials_verified_by="synthetic-verifier",
        revision=1,
    )
    session.add(person)
    await session.flush()
    if schedule:
        session.add(ProfessionalSchedule(professional_id=person.id, calendar_id=CAL, revision=1))
        await session.flush()
        session.add_all(
            AvailabilityRule(
                id=uuid4(),
                professional_id=person.id,
                weekday=weekday,
                start_time=time(8),
                end_time=time(20),
            )
            for weekday in range(7)
        )
    return person.id


async def published_service(
    session: AsyncSession, professional_id: UUID, *, booking_mode: str = "direct"
) -> UUID:
    service = Service(
        id=uuid4(),
        slug=f"synthetic-{uuid4()}",
        name="Synthetic procedure",
        category="synthetic",
        description="Synthetic approved description",
        content={
            "objectives": ["Synthetic objective"],
            "audience": "Synthetic audience",
            "preparation": ["Synthetic preparation"],
            "aftercare": ["Synthetic aftercare"],
            "human_guidance": "Synthetic guidance",
            "price_kind": "on_evaluation",
            "communication_restrictions": [],
        },
        duration_minutes=60,
        buffer_minutes=15,
        booking_mode=booking_mode,
        price_brl=None,
        deposit_brl=Decimal("50.00"),
        status="published",
        revision=1,
        approved_by="synthetic-reviewer",
        approved_at=NOW - timedelta(days=1),
        published_at=NOW - timedelta(days=1),
    )
    session.add(service)
    await session.flush()
    session.add(ProfessionalService(professional_id=professional_id, service_id=service.id))
    session.add(
        ServiceApproval(
            service_id=service.id,
            professional_id=professional_id,
            revision=1,
            approved_by="synthetic-reviewer",
            approved_at=NOW - timedelta(days=1),
        )
    )
    return service.id


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


async def hold(
    world: World,
    starts_at: datetime,
    *,
    key: str | None = None,
    service_id: UUID | None = None,
    professional_id: UUID | None = None,
    name: str = "Synthetic contact",
    phone: str = "+55 (21) 99999-0000",
    now: datetime = NOW,
) -> Booking:
    world.keys += 1
    request = HoldRequest(
        idempotency_key=key or f"synthetic-key-{world.keys:04d}",
        service_id=service_id or world.service_id,
        professional_id=professional_id or world.professional_id,
        starts_at=starts_at,
        contact_name=name,
        contact_phone=phone,
    )
    return await create_hold(world.session, world.calendar, request, now=now)


async def reload(world: World, booking_id: UUID) -> Booking:
    async with world.session.begin():
        booking = await world.session.get(Booking, booking_id, populate_existing=True)
    assert booking is not None
    return booking


async def held(world: World, starts_at: datetime, **options: Any) -> Booking:
    booking = await hold(world, starts_at, **options)
    assert await sync_calendar(world.session, world.calendar, booking.id, now=NOW) == "synced"
    return await reload(world, booking.id)


async def confirmed(world: World, starts_at: datetime, **options: Any) -> Booking:
    booking = await held(world, starts_at, **options)
    await confirm_deposit(
        world.session,
        booking.id,
        actor=STAFF,
        expected_version=booking.version,
        amount_brl=Decimal("50.00"),
        now=NOW + 10 * MINUTE,
    )
    await sync_calendar(world.session, world.calendar, booking.id, now=NOW + 10 * MINUTE)
    current = await reload(world, booking.id)
    assert current.status == "confirmed"
    return current


async def notifications(world: World, booking_id: UUID) -> list[str]:
    rows = await world.connection.execute(
        select(OutboxJob.event).where(
            OutboxJob.booking_id == booking_id, OutboxJob.kind == "notification"
        )
    )
    return sorted(str(event) for event in rows.scalars())


async def slots_on(world: World, day: date, now: datetime = NOW) -> list[datetime]:
    return await available_slots(
        world.session,
        world.calendar,
        service_id=world.service_id,
        professional_id=world.professional_id,
        first_day=day,
        last_day=day,
        now=now,
    )


async def test_slots_combine_working_hours_bookings_buffer_and_manual_events(world: World) -> None:
    assert (await slots_on(world, MONDAY))[0] == local(MONDAY, 12)  # 3h minimum lead
    free = await slots_on(world, TUESDAY)
    assert free[0] == local(TUESDAY, 8) and free[-1] == local(TUESDAY, 19)
    world.calendar.add_manual(CAL, local(TUESDAY, 10), local(TUESDAY, 11))
    await held(world, local(TUESDAY, 14))  # its own calendar event must not count twice
    free = await slots_on(world, TUESDAY)
    assert local(TUESDAY, 8, 45) in free  # blocked until 10:00, touching the manual event
    assert local(TUESDAY, 9) not in free and local(TUESDAY, 10, 45) not in free
    assert local(TUESDAY, 11) in free
    assert local(TUESDAY, 12, 45) in free  # buffer ends exactly when the booking starts
    assert local(TUESDAY, 13) not in free and local(TUESDAY, 15) not in free
    assert local(TUESDAY, 15, 15) in free  # booking + 15 min buffer


async def test_hold_waits_for_the_calendar_then_reserves_two_hours(world: World) -> None:
    booking = await hold(world, local(TUESDAY, 10))
    assert (booking.status, booking.expires_at) == ("pending_calendar", NOW + 10 * MINUTE)
    assert booking.deposit_brl == Decimal("50.00")
    assert await notifications(world, booking.id) == []
    assert await sync_calendar(world.session, world.calendar, booking.id, now=NOW) == "synced"
    current = await reload(world, booking.id)
    assert (current.status, current.expires_at) == ("held", NOW + timedelta(hours=2))
    assert current.calendar_status == "tentative"
    assert world.calendar.status(CAL, event_id(booking.id)) == "tentative"
    assert await notifications(world, booking.id) == ["deposit_instructions", "hold_created"]
    assert await sync_calendar(world.session, world.calendar, booking.id, now=NOW) == "unchanged"


async def test_hold_is_idempotent_and_a_key_cannot_be_reused(world: World) -> None:
    first = await hold(world, local(TUESDAY, 10), key="synthetic-idempotent-1")
    again = await hold(world, local(TUESDAY, 10), key="synthetic-idempotent-1")
    assert again.id == first.id
    with pytest.raises(BookingConflict):
        await hold(world, local(TUESDAY, 11), key="synthetic-idempotent-1")
    count = await world.connection.scalar(select(func.count()).select_from(Booking))
    assert count == 1


async def test_database_rejects_overlapping_active_holds(world: World) -> None:
    await hold(world, local(TUESDAY, 10))
    for start in (local(TUESDAY, 10), local(TUESDAY, 10, 45), local(TUESDAY, 9, 15)):
        with pytest.raises(SlotUnavailable):
            await hold(world, start)
    touching = await hold(world, local(TUESDAY, 11, 15))  # previous blocked until 11:15
    assert touching.status == "pending_calendar"


@pytest.mark.parametrize(
    ("starts_at", "error"),
    [
        (local(MONDAY, 11), RequiresHuman),  # inside the 3h minimum lead
        (local(TUESDAY, 10, 7), SlotUnavailable),  # off the 15-minute grid
        (local(TUESDAY, 19, 30), SlotUnavailable),  # would end after 20:00
        (local(TUESDAY, 7), SlotUnavailable),  # before opening
        (NOW + timedelta(days=61), SlotUnavailable),  # beyond the horizon
        (NOW - timedelta(hours=1), SlotUnavailable),  # in the past
    ],
)
async def test_hold_requires_a_bookable_time(
    world: World, starts_at: datetime, error: type[Exception]
) -> None:
    with pytest.raises(error):
        await hold(world, starts_at)


async def test_hold_rejects_times_taken_in_the_external_calendar(world: World) -> None:
    world.calendar.add_manual(CAL, local(TUESDAY, 10, 30), local(TUESDAY, 10, 45))
    with pytest.raises(SlotUnavailable):
        await hold(world, local(TUESDAY, 10))


async def test_only_eligible_services_and_agendas_are_bookable(world: World) -> None:
    with pytest.raises(NotBookable):
        await hold(world, local(TUESDAY, 10), service_id=world.evaluation_service_id)
    async with world.session.begin():
        stranger = await professional(world.session)
        unscheduled = await professional(world.session, schedule=False)
        unscheduled_service = await published_service(world.session, unscheduled)
    with pytest.raises(NotBookable):
        await hold(world, local(TUESDAY, 10), professional_id=stranger)
    with pytest.raises(NotBookable):
        await hold(
            world, local(TUESDAY, 10), service_id=unscheduled_service, professional_id=unscheduled
        )
    await world.connection.execute(
        update(Service)
        .where(Service.id == world.service_id)
        .values(status="draft", approved_at=None, approved_by=None, published_at=None)
    )
    with pytest.raises(NotBookable):
        await hold(world, local(TUESDAY, 10))


@pytest.mark.parametrize(
    ("name", "phone"),
    [("Synthetic", "21 9999"), ("<b>Synthetic</b>", "+5521999990000"), ("", "+5521999990000")],
)
async def test_contact_input_is_validated(world: World, name: str, phone: str) -> None:
    with pytest.raises(InvalidBookingRequest):
        await hold(world, local(TUESDAY, 10), name=name, phone=phone)


async def test_manual_event_created_meanwhile_turns_the_hold_into_conflict(world: World) -> None:
    booking = await hold(world, local(TUESDAY, 10))
    world.calendar.add_manual(CAL, local(TUESDAY, 10, 30), local(TUESDAY, 11))
    assert await sync_calendar(world.session, world.calendar, booking.id, now=NOW) == "synced"
    current = await reload(world, booking.id)
    assert (current.status, current.closed_reason) == ("conflict", "calendar_conflict")
    assert await notifications(world, booking.id) == ["human_handoff"]
    assert await sync_calendar(world.session, world.calendar, booking.id, now=NOW) == "human"
    released = await resolve_conflict(
        world.session,
        booking.id,
        actor=STAFF,
        expected_version=current.version,
        resolution="release",
        now=NOW,
    )
    assert released.status == "cancelled"
    await sync_calendar(world.session, world.calendar, booking.id, now=NOW)
    assert world.calendar.status(CAL, event_id(booking.id)) == "cancelled"


async def test_conflict_retry_reverifies_the_calendar(world: World) -> None:
    booking = await hold(world, local(TUESDAY, 10))
    world.calendar.add_manual(CAL, local(TUESDAY, 10, 30), local(TUESDAY, 11))
    await sync_calendar(world.session, world.calendar, booking.id, now=NOW)
    world.calendar.manual.clear()  # staff removed the manual event
    current = await reload(world, booking.id)
    retried = await resolve_conflict(
        world.session,
        booking.id,
        actor=STAFF,
        expected_version=current.version,
        resolution="retry",
        now=NOW,
    )
    assert retried.status == "pending_calendar"
    await sync_calendar(world.session, world.calendar, booking.id, now=NOW)
    assert (await reload(world, booking.id)).status == "held"


async def test_rejected_calendar_hands_the_booking_to_a_human(world: World) -> None:
    booking = await hold(world, local(TUESDAY, 10))
    world.calendar.rejected = True
    assert await sync_calendar(world.session, world.calendar, booking.id, now=NOW) == "rejected"
    current = await reload(world, booking.id)
    assert (current.status, current.closed_reason) == ("conflict", "calendar_rejected")
    assert await notifications(world, booking.id) == ["human_handoff"]


async def test_human_deposit_confirmation_then_calendar_confirmation(world: World) -> None:
    booking = await held(world, local(TUESDAY, 10))
    confirming = await confirm_deposit(
        world.session,
        booking.id,
        actor=STAFF,
        expected_version=booking.version,
        amount_brl=Decimal("50"),
        now=NOW + 30 * MINUTE,
    )
    assert confirming.status == "confirming"
    assert confirming.deposit_confirmed_by == "synthetic-staff-subject"
    assert confirming.expires_at is None
    await sync_calendar(world.session, world.calendar, booking.id, now=NOW + 30 * MINUTE)
    current = await reload(world, booking.id)
    assert (current.status, current.calendar_status) == ("confirmed", "confirmed")
    assert world.calendar.status(CAL, event_id(booking.id)) == "confirmed"
    assert {"booking_confirmed", "manage_link"} <= set(await notifications(world, booking.id))


@pytest.mark.parametrize(
    ("actor", "amount", "version_offset", "error"),
    [
        (STAFF, "49.99", 0, BookingConflict),  # divergent value goes to a human
        (STAFF, "50.00", -1, BookingConflict),  # stale screen
        (CLIENT, "50.00", 0, BookingConflict),  # never by the client or a message
        (Actor("staff"), "50.00", 0, BookingConflict),  # unauthenticated staff
    ],
)
async def test_deposit_confirmation_guards(
    world: World, actor: Actor, amount: str, version_offset: int, error: type[Exception]
) -> None:
    booking = await held(world, local(TUESDAY, 10))
    # A refused operation rolls back and expires ORM objects: keep plain values.
    booking_id, version = booking.id, booking.version
    with pytest.raises(error):
        await confirm_deposit(
            world.session,
            booking_id,
            actor=actor,
            expected_version=version + version_offset,
            amount_brl=Decimal(amount),
            now=NOW + MINUTE,
        )
    assert (await reload(world, booking_id)).status == "held"


async def test_late_deposit_confirmation_needs_a_human(world: World) -> None:
    booking = await held(world, local(TUESDAY, 10))
    assert booking.expires_at is not None
    with pytest.raises(RequiresHuman):
        await confirm_deposit(
            world.session,
            booking.id,
            actor=STAFF,
            expected_version=booking.version,
            amount_brl=Decimal("50"),
            now=booking.expires_at,
        )


async def test_unpaid_hold_expires_and_frees_the_time(world: World) -> None:
    booking = await held(world, local(TUESDAY, 10))
    deadline = booking.expires_at
    assert deadline is not None
    assert await expire_due(world.session, now=deadline - timedelta(seconds=1)) == []
    assert await expire_due(world.session, now=deadline) == [booking.id]
    current = await reload(world, booking.id)
    assert (current.status, current.closed_reason) == ("expired", "deposit_timeout")
    assert "hold_expired" in await notifications(world, booking.id)
    await sync_calendar(world.session, world.calendar, booking.id, now=deadline)
    assert world.calendar.status(CAL, event_id(booking.id)) == "cancelled"
    again = await hold(world, local(TUESDAY, 10), now=deadline)
    assert again.status == "pending_calendar"


async def test_stuck_calendar_placement_releases_and_hands_off(world: World) -> None:
    booking = await hold(world, local(TUESDAY, 10))
    assert await expire_due(world.session, now=NOW + 10 * MINUTE) == [booking.id]
    current = await reload(world, booking.id)
    assert (current.status, current.closed_reason) == ("expired", "calendar_timeout")
    assert await notifications(world, booking.id) == ["human_handoff"]


async def test_client_cancellation_respects_the_24_hour_rule(world: World) -> None:
    unpaid = await held(world, local(MONDAY, 15))
    cancelled = await cancel_booking(
        world.session, unpaid.id, actor=CLIENT, expected_version=unpaid.version, now=NOW
    )
    assert (cancelled.status, cancelled.closed_reason) == ("cancelled", "cancelled_by_client")

    far = await confirmed(world, local(TUESDAY, 10))  # 25h ahead
    await cancel_booking(world.session, far.id, actor=CLIENT, expected_version=far.version, now=NOW)

    boundary = await confirmed(world, local(TUESDAY, 9))  # exactly 24h: humans decide
    near = await confirmed(world, local(MONDAY, 15))
    targets = [(item.id, item.version) for item in (boundary, near)]
    for booking_id, version in targets:
        with pytest.raises(RequiresHuman):
            await cancel_booking(
                world.session, booking_id, actor=CLIENT, expected_version=version, now=NOW
            )
    near_id, near_version = targets[1]
    staff = await cancel_booking(
        world.session, near_id, actor=STAFF, expected_version=near_version, now=NOW
    )
    assert staff.closed_reason == "cancelled_by_staff"
    assert "booking_cancelled" in await notifications(world, near_id)


async def test_first_client_reschedule_keeps_the_deposit(world: World) -> None:
    original = await confirmed(world, local(WEDNESDAY, 10))
    # Transitions mutate the identity-mapped object, so keep what the client's screen had.
    original_version, deposit_at = original.version, original.deposit_confirmed_at
    replacement = await reschedule_booking(
        world.session,
        world.calendar,
        original.id,
        actor=CLIENT,
        expected_version=original_version,
        new_starts_at=local(WEDNESDAY, 10, 30),  # overlaps its own old time
        now=NOW,
    )
    assert replacement.status == "pending_calendar"
    assert (replacement.reschedule_count, replacement.rescheduled_from_id) == (1, original.id)
    assert replacement.deposit_confirmed_at == deposit_at
    again = await reschedule_booking(
        world.session,
        world.calendar,
        original.id,
        actor=CLIENT,
        expected_version=original_version,
        new_starts_at=local(WEDNESDAY, 10, 30),
        now=NOW,
    )
    assert again.id == replacement.id
    old = await reload(world, original.id)
    assert (old.status, old.closed_reason) == ("cancelled", "rescheduled")
    await sync_calendar(world.session, world.calendar, original.id, now=NOW)
    await sync_calendar(world.session, world.calendar, replacement.id, now=NOW)
    moved = await reload(world, replacement.id)
    assert moved.status == "confirmed"  # deposit already confirmed by a human
    assert world.calendar.status(CAL, event_id(original.id)) == "cancelled"
    assert world.calendar.status(CAL, event_id(replacement.id)) == "confirmed"
    assert {"booking_rescheduled", "manage_link"} <= set(await notifications(world, moved.id))

    moved_id, moved_version = moved.id, moved.version
    with pytest.raises(RequiresHuman):  # second reschedule is a clinic decision
        await reschedule_booking(
            world.session,
            world.calendar,
            moved_id,
            actor=CLIENT,
            expected_version=moved_version,
            new_starts_at=local(WEDNESDAY, 14),
            now=NOW,
        )
    by_staff = await reschedule_booking(
        world.session,
        world.calendar,
        moved_id,
        actor=STAFF,
        expected_version=moved_version,
        new_starts_at=local(WEDNESDAY, 14),
        now=NOW,
    )
    assert by_staff.reschedule_count == 2


async def test_client_reschedule_within_24_hours_needs_a_human(world: World) -> None:
    booking = await confirmed(world, local(MONDAY, 15))
    with pytest.raises(RequiresHuman):
        await reschedule_booking(
            world.session,
            world.calendar,
            booking.id,
            actor=CLIENT,
            expected_version=booking.version,
            new_starts_at=local(WEDNESDAY, 10),
            now=NOW,
        )


async def outbox_events(world: World, event: str) -> int:
    count = await world.connection.scalar(
        select(func.count()).select_from(OutboxJob).where(OutboxJob.event == event)
    )
    return int(count or 0)


async def test_time_based_messages_are_scheduled_once_and_never_early(world: World) -> None:
    unpaid = await held(world, local(TUESDAY, 15))
    assert unpaid.expires_at is not None
    await enqueue_due_notifications(world.session, now=unpaid.expires_at - 31 * MINUTE)
    assert await outbox_events(world, "hold_expiring") == 0
    for _ in range(2):
        await enqueue_due_notifications(world.session, now=unpaid.expires_at - 29 * MINUTE)
    assert await outbox_events(world, "hold_expiring") == 1

    early = await confirmed(world, local(TUESDAY, 10))  # confirmed 25h before
    late = await confirmed(world, local(MONDAY, 15))  # confirmed 6h before
    await enqueue_due_notifications(world.session, now=local(MONDAY, 10))
    assert await notifications(world, early.id) == sorted(
        ["booking_confirmed", "deposit_instructions", "hold_created", "manage_link", "reminder_24h"]
    )
    await enqueue_due_notifications(world.session, now=local(MONDAY, 13))
    late_events = await notifications(world, late.id)
    assert "reminder_2h" in late_events and "reminder_24h" not in late_events
    await enqueue_due_notifications(world.session, now=local(TUESDAY, 11, 30))
    assert "aftercare" in await notifications(world, early.id)


@dataclass
class RecordingNotifier:
    sent: list[tuple[str, UUID]]

    async def send(self, event: str, booking_id: UUID) -> None:
        self.sent.append((event, booking_id))


async def test_outbox_retries_calendar_outages_and_skips_stale_messages(world: World) -> None:
    booking = await hold(world, local(TUESDAY, 10))
    world.calendar.unavailable = 1
    report = await deliver_due(world.session, calendar=world.calendar, notifier=None, now=NOW)
    assert (report.retried, report.delivered) == (1, 0)
    job = await world.connection.execute(
        select(OutboxJob.attempts, OutboxJob.available_at, OutboxJob.last_error).where(
            OutboxJob.booking_id == booking.id
        )
    )
    assert job.one() == (1, NOW + 2 * MINUTE, "calendar_unavailable")
    assert (await reload(world, booking.id)).status == "pending_calendar"

    report = await deliver_due(
        world.session, calendar=world.calendar, notifier=None, now=NOW + 2 * MINUTE
    )
    assert report.delivered == 1
    current = await reload(world, booking.id)
    assert current.status == "held"

    await cancel_booking(
        world.session, booking.id, actor=CLIENT, expected_version=current.version, now=NOW
    )
    notifier = RecordingNotifier([])
    report = await deliver_due(
        world.session, calendar=world.calendar, notifier=notifier, now=NOW + 3 * MINUTE
    )
    # hold_created/deposit_instructions no longer match the cancelled booking
    assert notifier.sent == [("booking_cancelled", booking.id)]
    assert report.skipped == 2
    assert world.calendar.status(CAL, event_id(booking.id)) == "cancelled"


async def test_a_long_lived_session_never_acts_on_an_old_copy(world: World) -> None:
    """The worker may reuse one session while the panel changes the booking elsewhere."""
    booking = await held(world, local(TUESDAY, 10))  # world.session now holds a "held" copy
    async with AsyncSession(
        bind=world.connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    ) as panel:
        await cancel_booking(
            panel, booking.id, actor=STAFF, expected_version=booking.version, now=NOW
        )
    notifier = RecordingNotifier([])
    await deliver_due(world.session, calendar=world.calendar, notifier=notifier, now=NOW + MINUTE)
    assert notifier.sent == [("booking_cancelled", booking.id)]
    assert world.calendar.status(CAL, event_id(booking.id)) == "cancelled"


async def test_audit_and_outbox_never_hold_contact_data(world: World) -> None:
    booking = await confirmed(
        world, local(TUESDAY, 10), name="SYNTHETIC CONTACT NAME", phone="+5521987650000"
    )
    await cancel_booking(
        world.session, booking.id, actor=STAFF, expected_version=booking.version, now=NOW
    )
    for table in ("booking_events", "outbox_jobs"):
        rows = await world.connection.execute(text(f"SELECT row_to_json(t) FROM {table} AS t"))  # noqa: S608
        rendered = json.dumps([row for row in rows.scalars()])
        assert "SYNTHETIC CONTACT NAME" not in rendered
        assert "987650000" not in rendered
        assert str(booking.id) in rendered


async def test_conflict_and_open_states_block_time_while_closed_states_do_not(
    world: World,
) -> None:
    booking = await hold(world, local(TUESDAY, 10))
    for status, expires in (("conflict", None), ("cancelled", None), ("expired", None)):
        await world.connection.execute(
            update(Booking)
            .where(Booking.id == booking.id)
            .values(status=status, expires_at=expires)
        )
        try:
            await world.connection.execute(text("SAVEPOINT probe"))
            await world.connection.execute(
                text(
                    "INSERT INTO bookings (id, idempotency_key, service_id, service_revision, "
                    "professional_id, contact_id, starts_at, ends_at, blocked_until, status, "
                    "expires_at, deposit_brl) SELECT :id, :key, service_id, 1, professional_id, "
                    "contact_id, starts_at, ends_at, blocked_until, 'pending_calendar', "
                    "now(), 0 FROM bookings WHERE id = :source"
                ),
                {"id": uuid4(), "key": f"probe-{status}", "source": booking.id},
            )
            blocked = False
        except IntegrityError:
            blocked = True
        finally:
            await world.connection.execute(text("ROLLBACK TO SAVEPOINT probe"))
        assert blocked is (status == "conflict"), status


class _DeadlockOrig(Exception):
    sqlstate = "40P01"


async def test_deadlocked_hold_is_retried_and_gives_up_after_the_limit(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    import lumini.booking.service as service

    original = service._contact_id
    failures = {"left": 1}

    async def flaky(session: AsyncSession, name: str, phone: str) -> UUID:
        if failures["left"] > 0:
            failures["left"] -= 1
            raise OperationalError("INSERT", {}, _DeadlockOrig())
        return await original(session, name, phone)

    monkeypatch.setattr(service, "_contact_id", flaky)
    booking = await hold(world, local(TUESDAY, 10))
    assert (await reload(world, booking.id)).status == "pending_calendar"

    failures["left"] = service.WRITE_ATTEMPTS
    with pytest.raises(OperationalError):
        await hold(world, local(TUESDAY, 14))
    async with world.session.begin():
        count = await world.session.scalar(select(func.count()).select_from(Booking))
    assert count == 1  # every aborted attempt rolled back
