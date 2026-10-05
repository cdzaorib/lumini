"""Worker-side processing: expire holds, schedule time-based messages, deliver the outbox.

Every automatic message is revalidated against the booking right before delivery (ADR-008):
a job queued earlier never sends something the current state contradicts.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from lumini.booking.calendar import CalendarAdapter, CalendarUnavailable
from lumini.booking.outbox import claim, finish, retry_later
from lumini.booking.policy import DEFAULT_POLICY, BookingPolicy
from lumini.booking.reconcile import requeue_stalled
from lumini.booking.service import enqueue_due_notifications, expire_due, sync_calendar
from lumini.leads.service import purge_expired
from lumini.models import Booking

logger = logging.getLogger(__name__)

# Event -> booking statuses in which the message still makes sense.
NOTIFICATION_STATES: dict[str, tuple[str, ...]] = {
    "hold_created": ("held",),
    "deposit_instructions": ("held",),
    "hold_expiring": ("held",),
    "hold_expired": ("expired",),
    "booking_confirmed": ("confirmed",),
    "booking_rescheduled": ("confirmed",),
    "manage_link": ("confirmed",),
    "reminder_24h": ("confirmed",),
    "reminder_2h": ("confirmed",),
    "aftercare": ("confirmed",),
    "booking_cancelled": ("cancelled",),
    "human_handoff": ("expired", "conflict"),
}


class NotifierUnavailable(Exception):
    """Transient delivery failure; the job is retried with backoff."""


class Notifier(Protocol):
    """Channel adapter (WhatsApp). It loads approved content and contact data itself; the outbox
    only carries the booking id and the event name. Returns None when delivered, or a short note
    when the message was deliberately not sent (e.g. the team is talking in human mode)."""

    async def send(self, event: str, booking_id: UUID) -> str | None: ...


def still_relevant(event: str, booking: Booking, now: datetime) -> bool:
    if booking.status not in NOTIFICATION_STATES.get(event, ()):
        return False
    if event == "hold_expiring":
        return booking.expires_at is not None and now < booking.expires_at
    if event in ("reminder_24h", "reminder_2h"):
        return now < booking.starts_at
    return True


@dataclass
class TickReport:
    expired: int = 0
    scheduled_messages: int = 0
    delivered: int = 0
    skipped: int = 0
    retried: int = 0
    failed: int = 0
    requeued: int = 0
    purged_leads: int = 0
    notes: list[str] = field(default_factory=list)


async def deliver_due(
    session: AsyncSession,
    *,
    calendar: CalendarAdapter | None,
    notifier: Notifier | None,
    now: datetime,
    policy: BookingPolicy = DEFAULT_POLICY,
    limit: int = 20,
    report: TickReport | None = None,
) -> TickReport:
    """Without a notifier, messages stay pending (never lost); without a calendar adapter,
    calendar jobs stay pending."""
    report = report or TickReport()
    kinds = tuple(
        kind
        for kind, enabled in (("calendar_sync", calendar), ("notification", notifier))
        if enabled is not None
    )
    if not kinds:
        return report
    for job in await claim(session, now=now, kinds=kinds, limit=limit):
        try:
            if job.kind == "calendar_sync" and calendar is not None:
                result = await sync_calendar(
                    session, calendar, job.booking_id, now=now, policy=policy
                )
                note = "calendar_rejected" if result == "rejected" else None
                await finish(session, job.id, note=note)
                if note:
                    report.notes.append(note)
                report.delivered += 1
                continue
            async with session.begin():
                booking = await session.get(Booking, job.booking_id, populate_existing=True)
                relevant = (
                    booking is not None
                    and job.event is not None
                    and still_relevant(job.event, booking, now)
                )
            if not relevant or notifier is None or job.event is None:
                await finish(session, job.id, note="stale_skipped")
                report.skipped += 1
                continue
            note = await notifier.send(job.event, job.booking_id)
            await finish(session, job.id, note=note)
            if note is None:
                report.delivered += 1
            else:
                report.skipped += 1
                report.notes.append(note)
        except (CalendarUnavailable, NotifierUnavailable) as error:
            code = (
                "calendar_unavailable"
                if isinstance(error, CalendarUnavailable)
                else "notifier_unavailable"
            )
            gave_up = await retry_later(session, job.id, now=now, error_code=code)
            report.failed += gave_up
            report.retried += not gave_up
        except Exception as error:  # one bad job must not stop the queue
            # Type name only: exception text may contain provider payloads or personal data.
            logger.warning("outbox job failed with %s", type(error).__name__)
            gave_up = await retry_later(session, job.id, now=now, error_code="unexpected_error")
            report.failed += gave_up
            report.retried += not gave_up
    return report


async def tick(
    session: AsyncSession,
    *,
    calendar: CalendarAdapter | None,
    notifier: Notifier | None,
    now: datetime,
    policy: BookingPolicy = DEFAULT_POLICY,
) -> TickReport:
    """One worker cycle; safe to run concurrently and repeatedly.

    Without a calendar adapter, calendar jobs wait (never turned into conflicts); expiry, message
    scheduling and (with a notifier) messages still run.
    """
    report = TickReport()
    report.purged_leads = await purge_expired(session, now=now)
    report.expired = len(await expire_due(session, now=now))
    report.scheduled_messages = await enqueue_due_notifications(session, now=now, policy=policy)
    if calendar is not None:
        report.requeued = await requeue_stalled(session, now=now)
    return await deliver_due(
        session, calendar=calendar, notifier=notifier, now=now, policy=policy, report=report
    )
