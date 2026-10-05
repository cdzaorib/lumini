"""Professional agenda settings. Separate from credentials: editing never revokes verification."""

import uuid

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from lumini.auth import AdminPrincipal
from lumini.booking.schemas import RuleView, ScheduleUpdate, ScheduleView
from lumini.booking.service import BookingConflict, BookingNotFound
from lumini.models import (
    ACTIVE_BOOKING_STATUSES,
    AvailabilityRule,
    Booking,
    CatalogAuditEvent,
    Professional,
    ProfessionalSchedule,
)


async def _view(session: AsyncSession, professional_id: uuid.UUID) -> ScheduleView:
    schedule = await session.get(ProfessionalSchedule, professional_id)
    rules = await session.scalars(
        select(AvailabilityRule)
        .where(AvailabilityRule.professional_id == professional_id)
        .order_by(AvailabilityRule.weekday, AvailabilityRule.start_time)
    )
    return ScheduleView(
        professional_id=professional_id,
        calendar_id=schedule.calendar_id if schedule else None,
        revision=schedule.revision if schedule else 0,
        rules=[RuleView(weekday=r.weekday, start=r.start_time, end=r.end_time) for r in rules],
    )


async def _calendar_in_use(session: AsyncSession, professional_id: uuid.UUID) -> bool:
    found = await session.scalar(
        select(Booking.id)
        .where(
            Booking.professional_id == professional_id,
            or_(
                Booking.status.in_(ACTIVE_BOOKING_STATUSES),
                Booking.calendar_status.in_(("tentative", "confirmed")),
            ),
        )
        .limit(1)
    )
    return found is not None


async def get_schedule(session: AsyncSession, professional_id: uuid.UUID) -> ScheduleView:
    async with session.begin():
        if await session.get(Professional, professional_id) is None:
            raise BookingNotFound("Professional not found")
        return await _view(session, professional_id)


async def put_schedule(
    session: AsyncSession,
    actor: AdminPrincipal,
    professional_id: uuid.UUID,
    data: ScheduleUpdate,
) -> ScheduleView:
    """Replace the agenda. Existing bookings keep their times; only future availability changes."""
    async with session.begin():
        if await session.get(Professional, professional_id) is None:
            raise BookingNotFound("Professional not found")
        schedule = await session.get(ProfessionalSchedule, professional_id, with_for_update=True)
        current = schedule.revision if schedule else 0
        if current != data.expected_revision:
            raise BookingConflict("The agenda changed; reload before retrying", "stale")
        previous = schedule.calendar_id if schedule else None
        if data.calendar_id != previous and await _calendar_in_use(session, professional_id):
            # Sync writes to the current calendar id; events on the old one would be orphaned.
            raise BookingConflict(
                "The calendar has active bookings or pending removals", "calendar_in_use"
            )
        if schedule is None:
            schedule = ProfessionalSchedule(professional_id=professional_id, revision=0)
            session.add(schedule)
        schedule.calendar_id = data.calendar_id
        schedule.revision = current + 1
        await session.flush()
        await session.execute(
            delete(AvailabilityRule).where(AvailabilityRule.professional_id == professional_id)
        )
        session.add_all(
            AvailabilityRule(
                id=uuid.uuid4(),
                professional_id=professional_id,
                weekday=rule.weekday,
                start_time=rule.start,
                end_time=rule.end,
            )
            for rule in data.rules
        )
        session.add(
            CatalogAuditEvent(
                id=uuid.uuid4(),
                actor_subject=actor.subject,
                entity_type="professional",
                target_id=professional_id,
                action="schedule.updated",
                revision=schedule.revision,
            )
        )
        await session.flush()
        return await _view(session, professional_id)
