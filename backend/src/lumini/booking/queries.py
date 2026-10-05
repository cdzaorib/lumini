"""Staff read models. Contact name and phone are joined only here, behind admin authentication."""

import uuid
from datetime import datetime

from sqlalchemy import Select, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from lumini.booking.schemas import BookingAdminView, BookingScope, ContactView, NamedRef
from lumini.booking.service import BookingNotFound
from lumini.models import ACTIVE_BOOKING_STATUSES, Booking, Contact, Professional, Service

# Needs staff attention regardless of the appointment time.
_OPEN_STATUSES = tuple(status for status in ACTIVE_BOOKING_STATUSES if status != "confirmed")
UPCOMING_LIMIT = 500
HISTORY_LIMIT = 100


def _base() -> Select[tuple[Booking, str, str, str, str]]:
    return (
        select(Booking, Service.name, Professional.display_name, Contact.name, Contact.phone_e164)
        .join(Service, Service.id == Booking.service_id)
        .join(Professional, Professional.id == Booking.professional_id)
        .join(Contact, Contact.id == Booking.contact_id)
        # Mutations ran in earlier transactions of this session; never serve a stale identity.
        .execution_options(populate_existing=True)
    )


def _view(row: tuple[Booking, str, str, str, str]) -> BookingAdminView:
    booking, service_name, professional_name, contact_name, phone = row
    return BookingAdminView(
        id=booking.id,
        code=booking.id.hex[:8].upper(),
        status=booking.status,
        version=booking.version,
        starts_at=booking.starts_at,
        ends_at=booking.ends_at,
        expires_at=booking.expires_at,
        service=NamedRef(id=booking.service_id, name=service_name),
        professional=NamedRef(id=booking.professional_id, name=professional_name),
        contact=ContactView(name=contact_name, phone=phone),
        deposit_brl=booking.deposit_brl,
        deposit_confirmed_at=booking.deposit_confirmed_at,
        calendar_status=booking.calendar_status,
        reschedule_count=booking.reschedule_count,
        rescheduled_from_id=booking.rescheduled_from_id,
        closed_reason=booking.closed_reason,
        created_at=booking.created_at,
    )


async def list_bookings(
    session: AsyncSession, *, scope: BookingScope, now: datetime
) -> list[BookingAdminView]:
    """Upcoming: anything awaiting staff plus confirmed appointments not yet over. History: the
    rest, most recent first."""
    upcoming = or_(
        Booking.status.in_(_OPEN_STATUSES),
        and_(Booking.status == "confirmed", Booking.ends_at > now),
    )
    if scope == "upcoming":
        query = _base().where(upcoming).order_by(Booking.starts_at).limit(UPCOMING_LIMIT)
    else:
        query = _base().where(~upcoming).order_by(Booking.starts_at.desc()).limit(HISTORY_LIMIT)
    async with session.begin():
        return [_view(row) for row in (await session.execute(query)).tuples()]


async def get_booking(session: AsyncSession, booking_id: uuid.UUID) -> BookingAdminView:
    async with session.begin():
        row = (await session.execute(_base().where(Booking.id == booking_id))).tuples().first()
    if row is None:
        raise BookingNotFound("Booking not found")
    return _view(row)
