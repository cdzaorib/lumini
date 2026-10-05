"""Calendar reconciliation: PostgreSQL decides what Google shows for Lumini bookings (ADR-003).

Both passes are idempotent and only enqueue outbox work; calendar writes still go through
sync_calendar.

- requeue_stalled: a booking whose calendar state never converged (for example, its sync job
  gave up during a long outage) gets a fresh sync job, at most one per hour.
- reconcile_calendars: compares our own events in each professional calendar with the settled
  bookings and repairs edits made directly in Google (event deleted, moved, or restored).
  Conflict and in-flight bookings are left alone: a human or a pending job owns them.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from lumini.booking.availability import Interval
from lumini.booking.calendar import (
    CalendarAdapter,
    CalendarRejected,
    CalendarUnavailable,
    booking_id_of,
)
from lumini.booking.outbox import enqueue_calendar_sync
from lumini.booking.policy import DEFAULT_POLICY, BookingPolicy
from lumini.models import Booking, BookingEvent, OutboxJob, ProfessionalSchedule

logger = logging.getLogger(__name__)

_CLOSED = ("expired", "cancelled")
_SHOWN = ("tentative", "confirmed")
# Settled bookings whose recorded calendar state disagrees with the state they need.
_STALLED = or_(
    Booking.status == "confirming",
    and_(Booking.status == "held", Booking.calendar_status != "tentative"),
    and_(Booking.status == "confirmed", Booking.calendar_status != "confirmed"),
    and_(Booking.status.in_(_CLOSED), Booking.calendar_status.in_(_SHOWN)),
)


async def requeue_stalled(session: AsyncSession, *, now: datetime, limit: int = 100) -> int:
    pending = exists().where(
        OutboxJob.booking_id == Booking.id,
        OutboxJob.kind == "calendar_sync",
        OutboxJob.status == "pending",
    )
    async with session.begin():
        stalled = await session.scalars(
            select(Booking)
            .where(_STALLED, ~pending)
            .order_by(Booking.starts_at)
            .limit(limit)
            .execution_options(populate_existing=True)
        )
        count = 0
        for booking in stalled:
            count += await enqueue_calendar_sync(
                session, booking, now, reason=f"requeue:{now:%Y%m%d%H}"
            )
    return count


@dataclass
class ReconcileReport:
    calendars: int = 0
    unavailable: int = 0
    repaired: int = 0
    overlaps_flagged: int = 0
    overlaps_cleared: int = 0


def _drifted(booking: Booking, shown: Interval | None) -> bool:
    if booking.status in ("held", "confirmed") and booking.calendar_status in _SHOWN:
        return shown != Interval(booking.starts_at, booking.ends_at)  # deleted or moved
    if booking.status in _CLOSED and booking.calendar_status == "deleted":
        return shown is not None  # restored in Google after we removed it
    return False


def _event(session: AsyncSession, booking: Booking, action: str) -> None:
    session.add(
        BookingEvent(
            id=uuid.uuid4(),
            booking_id=booking.id,
            action=action,
            from_status=booking.status,
            to_status=booking.status,
            actor_type="system",
            actor_subject=None,
        )
    )


async def _repair(
    session: AsyncSession, booking_id: uuid.UUID, version: int, now: datetime
) -> bool:
    async with session.begin():
        booking = await session.get(Booking, booking_id, with_for_update=True)
        if booking is None or booking.version != version:
            return False  # changed meanwhile; its own job converges the calendar
        # "none" = unknown remote state, so the next sync writes the desired state again.
        booking.calendar_status = "none"
        session.add(
            BookingEvent(
                id=uuid.uuid4(),
                booking_id=booking.id,
                action="calendar_drift",
                from_status=booking.status,
                to_status=booking.status,
                actor_type="system",
                actor_subject=None,
            )
        )
        await enqueue_calendar_sync(session, booking, now, reason=f"drift:{now:%Y%m%d%H%M}")
    return True


async def reconcile_calendars(
    session: AsyncSession,
    calendar: CalendarAdapter,
    *,
    now: datetime,
    policy: BookingPolicy = DEFAULT_POLICY,
) -> ReconcileReport:
    window = Interval(now, now + policy.horizon)
    report = ReconcileReport()
    async with session.begin():
        calendars = (
            await session.execute(
                select(
                    ProfessionalSchedule.professional_id, ProfessionalSchedule.calendar_id
                ).where(ProfessionalSchedule.calendar_id.is_not(None))
            )
        ).all()
    for professional_id, calendar_id in calendars:
        try:
            busy = await calendar.list_busy(calendar_id, window.start, window.end)
        except (CalendarUnavailable, CalendarRejected):
            report.unavailable += 1  # try again next run; nothing is inferred from silence
            continue
        report.calendars += 1
        shown: dict[uuid.UUID, Interval] = {}
        others: list[Interval] = []
        for item in busy:
            booking_id = booking_id_of(item.event_id)
            if booking_id is not None:
                shown[booking_id] = Interval(item.start, item.end)
            else:
                others.append(Interval(item.start, item.end))
        async with session.begin():
            candidates = await session.scalars(
                select(Booking)
                .where(
                    Booking.professional_id == professional_id,
                    Booking.starts_at < window.end,
                    Booking.ends_at > window.start,
                    Booking.status.in_(("held", "confirmed", *_CLOSED)),
                )
                .with_for_update(skip_locked=True)  # a row being changed is checked next run
                .execution_options(populate_existing=True)
            )
            rows = list(candidates)
            drifted = [
                (booking.id, booking.version)
                for booking in rows
                if _drifted(booking, shown.get(booking.id))
            ]
            # Someone booked something else over a live reservation directly in Google: tell
            # the team (panel + history). The reservation itself is not changed (ADR-015).
            for booking in rows:
                if booking.status not in ("held", "confirmed"):
                    continue
                appointment = Interval(booking.starts_at, booking.ends_at)
                overlapping = any(appointment.overlaps(other) for other in others)
                if overlapping and booking.calendar_overlap_at is None:
                    booking.calendar_overlap_at = now
                    _event(session, booking, "calendar_overlap")
                    report.overlaps_flagged += 1
                elif not overlapping and booking.calendar_overlap_at is not None:
                    booking.calendar_overlap_at = None
                    _event(session, booking, "calendar_overlap_cleared")
                    report.overlaps_cleared += 1
        for booking_id, version in drifted:
            report.repaired += await _repair(session, booking_id, version, now)
    if report.repaired or report.unavailable or report.overlaps_flagged:
        logger.warning(
            "calendar reconcile: %d repaired, %d calendars unavailable, %d overlaps flagged",
            report.repaired,
            report.unavailable,
            report.overlaps_flagged,
        )
    return report
