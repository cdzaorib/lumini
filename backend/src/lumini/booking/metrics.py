"""Panel metrics (plan §11): leads, reservations, deposits, appointments, no-shows, origin,
demand per procedure and handoffs. Counts only; no personal data leaves these queries."""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Select, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lumini.booking.schemas import Count, MetricsView
from lumini.models import Booking, Lead, Service
from lumini.whatsapp.history import ConversationEvent

_ORIGIN = case(
    (Booking.idempotency_key.startswith("wa:"), "whatsapp"),
    (Booking.idempotency_key.startswith("web:"), "site"),
    (Booking.idempotency_key.startswith("reschedule:"), "reschedule"),
    else_="other",
)


async def _counts(session: AsyncSession, query: Select[Any]) -> list[Count]:
    rows = (await session.execute(query)).all()
    return sorted(
        (Count(key=str(key or "unknown"), count=int(count)) for key, count in rows),
        key=lambda item: (-item.count, item.key),
    )


async def _scalar(session: AsyncSession, query: Select[tuple[int]]) -> int:
    return int(await session.scalar(query) or 0)


async def collect(session: AsyncSession, *, now: datetime, days: int) -> MetricsView:
    since = now - timedelta(days=days)
    new_request = Booking.rescheduled_from_id.is_(None)
    async with session.begin():
        leads_by_status = await _counts(
            session,
            select(Lead.status, func.count()).where(Lead.created_at >= since).group_by(Lead.status),
        )
        appointments = select(Booking.attendance, func.count()).where(
            Booking.status == "confirmed", Booking.starts_at >= since, Booking.starts_at <= now
        )
        attendance = {
            item.key: item.count
            for item in await _counts(session, appointments.group_by(Booking.attendance))
        }
        return MetricsView(
            days=days,
            leads_total=sum(item.count for item in leads_by_status),
            leads_by_status=leads_by_status,
            leads_marketing_consent=await _scalar(
                session,
                select(func.count())
                .select_from(Lead)
                .where(Lead.created_at >= since, Lead.marketing_consent_at.is_not(None)),
            ),
            bookings_requested=await _scalar(
                session,
                select(func.count())
                .select_from(Booking)
                .where(Booking.created_at >= since, new_request),
            ),
            bookings_by_origin=await _counts(
                session,
                select(_ORIGIN, func.count())
                .where(Booking.created_at >= since, new_request)
                .group_by(_ORIGIN),
            ),
            deposits_confirmed=await _scalar(
                session,
                select(func.count())
                .select_from(Booking)
                .where(Booking.deposit_confirmed_at >= since, new_request),
            ),
            appointments=sum(attendance.values()),
            attended=attendance.get("attended", 0),
            no_show=attendance.get("no_show", 0),
            attendance_unmarked=attendance.get("unknown", 0),
            cancellations=await _counts(
                session,
                select(Booking.closed_reason, func.count())
                .where(
                    Booking.status == "cancelled",
                    Booking.updated_at >= since,
                    Booking.closed_reason != "rescheduled",
                )
                .group_by(Booking.closed_reason),
            ),
            reschedules=await _scalar(
                session,
                select(func.count())
                .select_from(Booking)
                .where(Booking.closed_reason == "rescheduled", Booking.updated_at >= since),
            ),
            expired=await _counts(
                session,
                select(Booking.closed_reason, func.count())
                .where(Booking.status == "expired", Booking.updated_at >= since)
                .group_by(Booking.closed_reason),
            ),
            demand_by_service=(
                await _counts(
                    session,
                    select(Service.name, func.count())
                    .join(Booking, Booking.service_id == Service.id)
                    .where(Booking.created_at >= since, new_request)
                    .group_by(Service.name),
                )
            )[:10],
            handoffs_by_reason=await _counts(
                session,
                select(ConversationEvent.reason, func.count())
                .where(
                    ConversationEvent.kind == "human",
                    ConversationEvent.occurred_at >= since,
                )
                .group_by(ConversationEvent.reason),
            ),
            upcoming_confirmed_7d=await _scalar(
                session,
                select(func.count())
                .select_from(Booking)
                .where(
                    Booking.status == "confirmed",
                    Booking.starts_at > now,
                    Booking.starts_at <= now + timedelta(days=7),
                ),
            ),
        )
