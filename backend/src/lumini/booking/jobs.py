"""Periodic jobs run by the Celery worker.

Each run opens its own engine and session (no state carried between runs) and holds a Redis lock
so overlapping runs skip instead of doing the same work twice. The lock is an optimization only:
row locks and versions in PostgreSQL keep concurrent runs correct.
"""

import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from redis.asyncio import Redis
from redis.exceptions import LockError

from lumini.booking.calendar import CalendarAdapter
from lumini.booking.dispatch import TickReport, tick
from lumini.booking.reconcile import ReconcileReport, reconcile_calendars
from lumini.resources import open_resources
from lumini.settings import Settings
from lumini.whatsapp.bot import Channel, handle, pending_conversations
from lumini.whatsapp.conversations import retry_failed_replies, settle_unknown
from lumini.whatsapp.evolution import WhatsAppSender
from lumini.whatsapp.notifier import WhatsAppNotifier

logger = logging.getLogger(__name__)

TICK_LOCK = "lumini:lock:booking-tick"
RECONCILE_LOCK = "lumini:lock:calendar-reconcile"
LOCK_SECONDS = 300


def utc_now() -> datetime:
    return datetime.now(UTC)


@asynccontextmanager
async def _exclusive(redis: Redis | None, name: str) -> AsyncIterator[bool]:
    if redis is None:
        raise RuntimeError("LUMINI_REDIS_URL is required for periodic jobs")
    lock = redis.lock(name, timeout=LOCK_SECONDS, blocking=False)
    acquired = bool(await lock.acquire())
    try:
        yield acquired
    finally:
        if acquired:
            try:
                await lock.release()
            except LockError:
                pass  # expired while running; the next run takes it again


async def run_tick(
    settings: Settings,
    *,
    calendar: CalendarAdapter | None,
    sender: WhatsAppSender | None = None,
    clock: Callable[[], datetime] = utc_now,
) -> TickReport | None:
    """None when another run holds the lock. With WhatsApp: settle unclassified `fromMe`
    messages first (they hold automatic sends), deliver notifications, retry replies that failed
    during an outage and answer conversations the webhook fast path missed."""
    async with (
        open_resources(settings) as resources,
        _exclusive(resources.redis_client, TICK_LOCK) as acquired,
    ):
        if not acquired:
            return None
        if resources.sessions is None:
            raise RuntimeError("LUMINI_DATABASE_URL is required for periodic jobs")
        now = clock()
        async with resources.sessions() as session:
            if sender is not None:
                await settle_unknown(session, now=now)
            notifier = (
                WhatsAppNotifier(session, sender, settings, now=now) if sender is not None else None
            )
            report = await tick(session, calendar=calendar, notifier=notifier, now=now)
            if sender is not None:
                channel = Channel(sender, calendar, settings)
                await retry_failed_replies(session, sender, now=now)
                for conversation_id in await pending_conversations(session, now=now):
                    await handle(session, channel, conversation_id, now=now)
    # Counts only: ids, names and provider details stay out of logs.
    logger.info(
        "booking tick: expired=%d scheduled=%d delivered=%d skipped=%d retried=%d failed=%d "
        "requeued=%d",
        report.expired,
        report.scheduled_messages,
        report.delivered,
        report.skipped,
        report.retried,
        report.failed,
        report.requeued,
    )
    return report


async def run_reconcile(
    settings: Settings,
    *,
    calendar: CalendarAdapter,
    clock: Callable[[], datetime] = utc_now,
) -> ReconcileReport | None:
    async with (
        open_resources(settings) as resources,
        _exclusive(resources.redis_client, RECONCILE_LOCK) as acquired,
    ):
        if not acquired:
            return None
        if resources.sessions is None:
            raise RuntimeError("LUMINI_DATABASE_URL is required for periodic jobs")
        async with resources.sessions() as session:
            return await reconcile_calendars(session, calendar, now=clock())
