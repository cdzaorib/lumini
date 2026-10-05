"""Client self-service through a signed link (plan §7). No login: the token is the credential.

Every route resolves the token before touching the database; forged, expired and unknown links
answer the same 404. Rules come from the booking service with the `client` actor, so the page can
never allow what the service refuses.
"""

from collections.abc import Awaitable
from datetime import datetime, timedelta
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from lumini.booking import service as booking
from lumini.booking.links import issue_token, read_token
from lumini.booking.policy import DEFAULT_POLICY
from lumini.booking.schemas import (
    AvailabilityView,
    BookingVersion,
    PublicAvailabilityQuery,
    PublicBooking,
    PublicRescheduled,
    StaffReschedule,
)
from lumini.deps import get_calendar, get_now, get_session, no_store
from lumini.models import Booking, Professional, Service
from lumini.ratelimit import allow
from lumini.resources import Resources
from lumini.settings import Settings

_bearer = HTTPBearer(auto_error=False)
_INVALID = "Link invalid or expired"
# Per link, per 10 minutes.
LINK_LIMIT = 120
AVAILABILITY_LIMIT = 30


class SelfServiceUnavailable(booking.BookingError):
    code = "self_service_unavailable"


def _secret(request: Request) -> str:
    settings = cast(Settings | None, getattr(request.app.state, "settings", None))
    if settings is None or settings.manage_link_secret is None:
        raise SelfServiceUnavailable("Self-service links are not configured")
    return settings.manage_link_secret.get_secret_value()


async def _limited(request: Request, scope: str, token: str, limit: int) -> None:
    resources = cast(Resources | None, getattr(request.app.state, "resources", None))
    redis = resources.redis_client if resources is not None else None
    if not await allow(redis, scope, token, limit=limit, window_seconds=600):
        raise booking.RequiresHuman("Too many requests for this link", "rate_limited")


async def client_booking(
    request: Request,
    now: Annotated[datetime, Depends(get_now)],
    authorization: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> UUID:
    secret = _secret(request)
    token = authorization.credentials if authorization else ""
    booking_id = read_token(secret, token, now=now)
    if booking_id is None:
        raise booking.BookingNotFound(_INVALID, "link_invalid")
    await _limited(request, "booking-link", token, limit=LINK_LIMIT)
    return booking_id


ClientBooking = Annotated[UUID, Depends(client_booking)]
Session = Annotated[AsyncSession, Depends(get_session)]
Now = Annotated[datetime, Depends(get_now)]

router = APIRouter(prefix="/api/public/booking", tags=["public"], dependencies=[Depends(no_store)])


async def _guard[T](operation: Awaitable[T]) -> T:
    try:
        return await operation
    except SQLAlchemyError:
        raise SelfServiceUnavailable("Bookings unavailable") from None


async def _view(session: AsyncSession, booking_id: UUID, now: datetime) -> PublicBooking:
    async with session.begin():
        row = (
            (
                await session.execute(
                    select(Booking, Service.name, Professional.display_name)
                    .join(Service, Service.id == Booking.service_id)
                    .join(Professional, Professional.id == Booking.professional_id)
                    .where(Booking.id == booking_id)
                    .execution_options(populate_existing=True)
                )
            )
            .tuples()
            .first()
        )
    if row is None:
        raise booking.BookingNotFound(_INVALID, "link_invalid")
    item, service_name, professional_name = row
    cancel = booking.client_cancel_refusal(item, now, DEFAULT_POLICY)
    reschedule = booking.client_reschedule_refusal(item, now, DEFAULT_POLICY)
    return PublicBooking(
        code=item.id.hex[:8].upper(),
        status=item.status,
        version=item.version,
        service=service_name,
        professional=professional_name,
        starts_at=item.starts_at,
        ends_at=item.ends_at,
        hold_expires_at=item.expires_at if item.status == "held" else None,
        deposit_brl=item.deposit_brl,
        deposit_confirmed=item.deposit_confirmed_at is not None,
        self_service_until=item.starts_at - DEFAULT_POLICY.self_service_cutoff,
        can_cancel=cancel is None,
        cancel_blocked=cancel,
        can_reschedule=reschedule is None,
        reschedule_blocked=reschedule,
    )


@router.get("", response_model=PublicBooking)
async def show(booking_id: ClientBooking, session: Session, now: Now) -> PublicBooking:
    return await _guard(_view(session, booking_id, now))


@router.get("/availability", response_model=AvailabilityView)
async def availability(
    request: Request,
    booking_id: ClientBooking,
    session: Session,
    now: Now,
    query: Annotated[PublicAvailabilityQuery, Query()],
) -> AvailabilityView:
    current = await _guard(_view(session, booking_id, now))
    if not current.can_reschedule:
        raise booking.RequiresHuman(
            "This change is handled by the clinic", current.reschedule_blocked
        )
    # Each preview reads the professional's Google Calendar: keep a leaked link from draining quota.
    await _limited(request, "booking-availability", booking_id.hex, limit=AVAILABILITY_LIMIT)
    calendar = get_calendar(request)
    async with session.begin():
        item = await session.get(Booking, booking_id)
    if item is None:
        raise booking.BookingNotFound(_INVALID, "link_invalid")
    slots = await _guard(
        booking.available_slots(
            session,
            calendar,
            service_id=item.service_id,
            professional_id=item.professional_id,
            first_day=query.first_day,
            last_day=query.first_day + timedelta(days=query.days - 1),
            now=now,
        )
    )
    # Its own time is booked by itself; offering it back would only fail.
    return AvailabilityView(slots=[slot for slot in slots if slot != item.starts_at])


@router.post("/cancel", response_model=PublicBooking)
async def cancel(
    booking_id: ClientBooking, session: Session, now: Now, data: BookingVersion
) -> PublicBooking:
    await _guard(
        booking.cancel_booking(
            session,
            booking_id,
            actor=booking.CLIENT,
            expected_version=data.expected_version,
            now=now,
        )
    )
    return await _guard(_view(session, booking_id, now))


@router.post("/reschedule", response_model=PublicRescheduled)
async def reschedule(
    request: Request,
    booking_id: ClientBooking,
    session: Session,
    now: Now,
    data: StaffReschedule,
) -> PublicRescheduled:
    calendar = get_calendar(request)
    replacement = await _guard(
        booking.reschedule_booking(
            session,
            calendar,
            booking_id,
            actor=booking.CLIENT,
            expected_version=data.expected_version,
            new_starts_at=data.starts_at,
            now=now,
        )
    )
    token = issue_token(_secret(request), replacement.id, replacement.starts_at)
    return PublicRescheduled(booking=await _guard(_view(session, replacement.id, now)), token=token)
