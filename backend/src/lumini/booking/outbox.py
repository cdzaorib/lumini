"""Transactional outbox: jobs are written in the same transaction as the state change.

Delivery is at-least-once; every handler is idempotent and every job has a dedupe key, so retries
and duplicate enqueues never produce duplicate calendar events or messages.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from lumini.models import Booking, OutboxJob

LEASE = timedelta(minutes=2)
MAX_ATTEMPTS = 10


@dataclass(frozen=True)
class ClaimedJob:
    id: uuid.UUID
    kind: str
    booking_id: uuid.UUID
    event: str | None
    attempts: int


async def enqueue(
    session: AsyncSession,
    *,
    kind: str,
    booking_id: uuid.UUID,
    dedupe_key: str,
    now: datetime,
    event: str | None = None,
) -> bool:
    """True when a new job was written (False: the dedupe key already existed)."""
    result = await session.execute(
        insert(OutboxJob)
        .values(
            id=uuid.uuid4(),
            kind=kind,
            booking_id=booking_id,
            event=event,
            dedupe_key=dedupe_key,
            status="pending",
            attempts=0,
            available_at=now,
        )
        .on_conflict_do_nothing(index_elements=[OutboxJob.dedupe_key])
        .returning(OutboxJob.id)
    )
    return result.scalar_one_or_none() is not None


async def enqueue_calendar_sync(
    session: AsyncSession, booking: Booking, now: datetime, *, reason: str | None = None
) -> bool:
    # One job per booking version; the handler always converges to the current desired state.
    # Reconciliation adds a reason so a repair is not swallowed by the version's spent key.
    suffix = f":{reason}" if reason else ""
    return await enqueue(
        session,
        kind="calendar_sync",
        booking_id=booking.id,
        dedupe_key=f"calendar:{booking.id}:{booking.version}{suffix}",
        now=now,
    )


async def enqueue_notification(
    session: AsyncSession, booking_id: uuid.UUID, event: str, now: datetime
) -> bool:
    # Each message type is sent at most once per booking.
    return await enqueue(
        session,
        kind="notification",
        booking_id=booking_id,
        event=event,
        dedupe_key=f"notify:{event}:{booking_id}",
        now=now,
    )


async def claim(
    session: AsyncSession, *, now: datetime, kinds: tuple[str, ...], limit: int = 20
) -> list[ClaimedJob]:
    """Lease due jobs; concurrent workers skip rows another worker holds."""
    async with session.begin():
        jobs = list(
            await session.scalars(
                select(OutboxJob)
                .where(
                    OutboxJob.status == "pending",
                    OutboxJob.kind.in_(kinds),
                    OutboxJob.available_at <= now,
                    or_(OutboxJob.locked_until.is_(None), OutboxJob.locked_until < now),
                )
                .order_by(OutboxJob.available_at, OutboxJob.created_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        )
        for job in jobs:
            job.attempts += 1
            job.locked_until = now + LEASE
        return [
            ClaimedJob(job.id, job.kind, job.booking_id, job.event, job.attempts) for job in jobs
        ]


async def finish(session: AsyncSession, job_id: uuid.UUID, *, note: str | None = None) -> None:
    async with session.begin():
        job = await session.get(OutboxJob, job_id, with_for_update=True)
        if job is not None:
            job.status = "done"
            job.locked_until = None
            job.last_error = note


async def retry_later(
    session: AsyncSession, job_id: uuid.UUID, *, now: datetime, error_code: str
) -> bool:
    """Exponential backoff capped at one hour. Returns True when the job gave up."""
    async with session.begin():
        job = await session.get(OutboxJob, job_id, with_for_update=True)
        if job is None:
            return False
        job.locked_until = None
        job.last_error = error_code[:60]
        if job.attempts >= MAX_ATTEMPTS:
            job.status = "failed"
            return True
        job.available_at = now + min(timedelta(minutes=2**job.attempts), timedelta(hours=1))
        return False
