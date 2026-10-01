"""Real races on separate connections with committed synthetic rows, removed afterwards."""

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from lumini.booking.service import (
    Actor,
    BookingConflict,
    HoldRequest,
    RequiresHuman,
    SlotUnavailable,
    confirm_deposit,
    create_hold,
    expire_due,
    sync_calendar,
)
from lumini.models import (
    AvailabilityRule,
    Booking,
    BookingEvent,
    Contact,
    OutboxJob,
    Professional,
    ProfessionalSchedule,
    ProfessionalService,
    Service,
    ServiceApproval,
)
from lumini.settings import Settings
from tests.booking_fakes import FakeCalendar
from tests.integration.test_booking_flow import (
    NOW,
    TUESDAY,
    WEDNESDAY,
    local,
    professional,
    published_service,
)

pytestmark = pytest.mark.integration
STAFF = Actor.staff("synthetic-staff-subject")
PHONE_PREFIX = "+5521900"


@dataclass
class Committed:
    sessions: async_sessionmaker[AsyncSession]
    calendar: FakeCalendar
    professional_id: UUID
    service_id: UUID


@pytest.fixture
async def committed(integration_settings: Settings) -> AsyncIterator[Committed]:
    url = integration_settings.sqlalchemy_url()
    assert url is not None
    engine = create_async_engine(url, echo=False, hide_parameters=True, pool_size=10)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session, session.begin():
        professional_id = await professional(session)
        service_id = await published_service(session, professional_id)
    try:
        yield Committed(sessions, FakeCalendar(), professional_id, service_id)
    finally:
        async with sessions() as session, session.begin():
            bookings = select(Booking.id).where(Booking.professional_id == professional_id)
            await session.execute(delete(OutboxJob).where(OutboxJob.booking_id.in_(bookings)))
            await session.execute(delete(BookingEvent).where(BookingEvent.booking_id.in_(bookings)))
            await session.execute(delete(Booking).where(Booking.professional_id == professional_id))
            await session.execute(
                delete(Contact).where(Contact.phone_e164.startswith(PHONE_PREFIX))
            )
            await session.execute(
                delete(AvailabilityRule).where(AvailabilityRule.professional_id == professional_id)
            )
            await session.execute(
                delete(ProfessionalSchedule).where(
                    ProfessionalSchedule.professional_id == professional_id
                )
            )
            await session.execute(
                delete(ServiceApproval).where(ServiceApproval.service_id == service_id)
            )
            await session.execute(
                delete(ProfessionalService).where(ProfessionalService.service_id == service_id)
            )
            await session.execute(delete(Service).where(Service.id == service_id))
            await session.execute(delete(Professional).where(Professional.id == professional_id))
        await engine.dispose()


def request(world: Committed, key: str, start_hour: int, phone_suffix: int) -> HoldRequest:
    return HoldRequest(
        idempotency_key=key,
        service_id=world.service_id,
        professional_id=world.professional_id,
        starts_at=local(TUESDAY, start_hour),
        contact_name="Synthetic concurrent contact",
        contact_phone=f"{PHONE_PREFIX}{phone_suffix:05d}",
    )


async def run_hold(world: Committed, hold: HoldRequest) -> Booking | Exception:
    async with world.sessions() as session:
        try:
            return await create_hold(session, world.calendar, hold, now=NOW)
        except Exception as error:  # collected and asserted by the caller
            return error


async def active_count(world: Committed) -> int:
    async with world.sessions() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(Booking)
            .where(Booking.professional_id == world.professional_id, Booking.status != "expired")
        )
    return int(count or 0)


async def test_simultaneous_holds_for_the_same_time_admit_exactly_one(committed: Committed) -> None:
    results = await asyncio.gather(
        *(
            run_hold(committed, request(committed, f"synthetic-race-{index}", 10, index))
            for index in range(8)
        )
    )
    winners = [item for item in results if isinstance(item, Booking)]
    losers = [item for item in results if not isinstance(item, Booking)]
    assert len(winners) == 1
    assert all(isinstance(item, SlotUnavailable) for item in losers), losers
    assert await active_count(committed) == 1


async def test_retries_with_the_same_key_create_a_single_booking(committed: Committed) -> None:
    hold = request(committed, "synthetic-same-key-0001", 14, 90)
    results = await asyncio.gather(*(run_hold(committed, hold) for _ in range(6)))
    assert all(isinstance(item, Booking) for item in results), results
    assert len({item.id for item in results if isinstance(item, Booking)}) == 1
    assert await active_count(committed) == 1


async def held_booking(world: Committed, hour: int, suffix: int) -> Booking:
    hold = HoldRequest(
        idempotency_key=f"synthetic-expiry-race-{suffix}",
        service_id=world.service_id,
        professional_id=world.professional_id,
        starts_at=local(WEDNESDAY, hour),
        contact_name="Synthetic concurrent contact",
        contact_phone=f"{PHONE_PREFIX}{suffix:05d}",
    )
    async with world.sessions() as session:
        booking = await create_hold(session, world.calendar, hold, now=NOW)
        await sync_calendar(session, world.calendar, booking.id, now=NOW)
        current = await session.get(Booking, booking.id, populate_existing=True)
        assert current is not None and current.status == "held"
        return current


async def confirm_at(world: Committed, booking: Booking, at: datetime) -> object:
    async with world.sessions() as session:
        try:
            return await confirm_deposit(
                session,
                booking.id,
                actor=STAFF,
                expected_version=booking.version,
                amount_brl=Decimal("50.00"),
                now=at,
            )
        except (BookingConflict, RequiresHuman) as error:
            return error


async def expire_at(world: Committed, at: datetime) -> object:
    async with world.sessions() as session:
        return await expire_due(session, now=at)


async def test_deposit_confirmation_and_expiry_never_both_win(committed: Committed) -> None:
    """Two app instances with slightly different clocks race on the same hold."""
    for index, hour in enumerate(range(8, 20, 2)):
        booking = await held_booking(committed, hour, 200 + index)
        assert booking.expires_at is not None
        second = timedelta(seconds=1)
        await asyncio.gather(
            confirm_at(committed, booking, booking.expires_at - second),
            expire_at(committed, booking.expires_at + second),
        )
        async with committed.sessions() as session:
            final = await session.get(Booking, booking.id)
            assert final is not None
            actions = list(
                await session.scalars(
                    select(BookingEvent.action).where(BookingEvent.booking_id == booking.id)
                )
            )
        assert final.status in ("confirming", "expired")
        if final.status == "confirming":
            assert final.deposit_confirmed_at is not None and "expired" not in actions
        else:
            assert final.deposit_confirmed_at is None and "deposit_confirmed" not in actions
