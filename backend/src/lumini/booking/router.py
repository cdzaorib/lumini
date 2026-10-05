"""Staff booking HTTP boundary. Authentication runs before any session or calendar dependency.

Refusals answer `{detail, code}`: `detail` is a fixed English message, `code` a stable identifier
the panel translates. Calendar and database failures never echo provider or driver text.
"""

import uuid
from collections.abc import Awaitable
from datetime import datetime, timedelta
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from lumini.auth import AdminPrincipal, require_admin
from lumini.booking import queries, schedule
from lumini.booking import service as booking
from lumini.booking.calendar import (
    CalendarAdapter,
    CalendarNotConfigured,
    CalendarRejected,
    CalendarUnavailable,
)
from lumini.booking.links import manage_url
from lumini.booking.schemas import (
    AvailabilityQuery,
    AvailabilityView,
    BookingAdminView,
    BookingScope,
    BookingVersion,
    ConflictResolution,
    DepositConfirmation,
    ManageLinkView,
    ScheduleUpdate,
    ScheduleView,
    StaffReschedule,
)
from lumini.deps import NO_STORE, get_calendar, get_now, get_session, no_store
from lumini.models import Booking, BookingEvent
from lumini.settings import Settings

Admin = Annotated[AdminPrincipal, Depends(require_admin)]
Session = Annotated[AsyncSession, Depends(get_session)]
Now = Annotated[datetime, Depends(get_now)]
Calendar = Annotated[CalendarAdapter, Depends(get_calendar)]


def _status(error: booking.BookingError) -> int:
    if isinstance(error, booking.BookingNotFound):
        return 404
    if error.code == "rate_limited":
        return 429
    if error.code in ("self_service_unavailable", "manage_link_not_configured"):
        return 503
    if error.code == "forbidden":
        return 403
    if isinstance(error, booking.InvalidBookingRequest):
        return 422
    return 409


async def booking_error_handler(request: Request, error: Exception) -> JSONResponse:
    if isinstance(error, booking.BookingError):
        return JSONResponse(
            {"detail": str(error), "code": error.code}, status_code=_status(error), headers=NO_STORE
        )
    if isinstance(error, CalendarNotConfigured):
        return JSONResponse(
            {"detail": str(error), "code": "calendar_not_configured"},
            status_code=503,
            headers=NO_STORE,
        )
    # CalendarUnavailable / CalendarRejected: provider text stays out of the response.
    return JSONResponse(
        {"detail": "Calendar unavailable", "code": "calendar_unavailable"},
        status_code=503,
        headers=NO_STORE,
    )


BOOKING_ERRORS: tuple[type[Exception], ...] = (
    booking.BookingError,
    CalendarUnavailable,
    CalendarRejected,
)


async def _guard[T](operation: Awaitable[T]) -> T:
    try:
        return await operation
    except IntegrityError:
        raise booking.BookingConflict(
            "Conflicting change; reload before retrying", "stale"
        ) from None
    except SQLAlchemyError:
        raise HTTPException(503, "Bookings unavailable", headers=NO_STORE) from None


router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin), Depends(no_store)],
)


@router.get("/professionals/{professional_id}/schedule", response_model=ScheduleView)
async def get_schedule(actor: Admin, session: Session, professional_id: UUID) -> ScheduleView:
    return await _guard(schedule.get_schedule(session, professional_id))


@router.put("/professionals/{professional_id}/schedule", response_model=ScheduleView)
async def put_schedule(
    actor: Admin, session: Session, professional_id: UUID, data: ScheduleUpdate
) -> ScheduleView:
    return await _guard(schedule.put_schedule(session, actor, professional_id, data))


@router.get("/availability", response_model=AvailabilityView)
async def availability(
    actor: Admin,
    session: Session,
    calendar: Calendar,
    now: Now,
    query: Annotated[AvailabilityQuery, Query()],
) -> AvailabilityView:
    slots = await _guard(
        booking.available_slots(
            session,
            calendar,
            service_id=query.service_id,
            professional_id=query.professional_id,
            first_day=query.first_day,
            last_day=query.first_day + timedelta(days=query.days - 1),
            now=now,
        )
    )
    return AvailabilityView(slots=slots)


@router.get("/bookings", response_model=list[BookingAdminView])
async def list_bookings(
    actor: Admin, session: Session, now: Now, scope: BookingScope = "upcoming"
) -> list[BookingAdminView]:
    return await _guard(queries.list_bookings(session, scope=scope, now=now))


@router.get("/bookings/{booking_id}", response_model=BookingAdminView)
async def get_booking(actor: Admin, session: Session, booking_id: UUID) -> BookingAdminView:
    return await _guard(queries.get_booking(session, booking_id))


@router.post("/bookings/{booking_id}/deposit", response_model=BookingAdminView)
async def confirm_deposit(
    actor: Admin, session: Session, now: Now, booking_id: UUID, data: DepositConfirmation
) -> BookingAdminView:
    result = await _guard(
        booking.confirm_deposit(
            session,
            booking_id,
            actor=booking.Actor.staff(actor.subject),
            expected_version=data.expected_version,
            amount_brl=data.amount_brl,
            now=now,
        )
    )
    return await _guard(queries.get_booking(session, result.id))


@router.post("/bookings/{booking_id}/cancel", response_model=BookingAdminView)
async def cancel(
    actor: Admin, session: Session, now: Now, booking_id: UUID, data: BookingVersion
) -> BookingAdminView:
    result = await _guard(
        booking.cancel_booking(
            session,
            booking_id,
            actor=booking.Actor.staff(actor.subject),
            expected_version=data.expected_version,
            now=now,
        )
    )
    return await _guard(queries.get_booking(session, result.id))


@router.post("/bookings/{booking_id}/resolve", response_model=BookingAdminView)
async def resolve(
    actor: Admin, session: Session, now: Now, booking_id: UUID, data: ConflictResolution
) -> BookingAdminView:
    result = await _guard(
        booking.resolve_conflict(
            session,
            booking_id,
            actor=booking.Actor.staff(actor.subject),
            expected_version=data.expected_version,
            resolution=data.resolution,
            now=now,
        )
    )
    return await _guard(queries.get_booking(session, result.id))


@router.post("/bookings/{booking_id}/reschedule", response_model=BookingAdminView)
async def reschedule(
    actor: Admin,
    session: Session,
    calendar: Calendar,
    now: Now,
    booking_id: UUID,
    data: StaffReschedule,
) -> BookingAdminView:
    """Answers the replacement booking; the original becomes cancelled with reason rescheduled."""
    result = await _guard(
        booking.reschedule_booking(
            session,
            calendar,
            booking_id,
            actor=booking.Actor.staff(actor.subject),
            expected_version=data.expected_version,
            new_starts_at=data.starts_at,
            now=now,
        )
    )
    return await _guard(queries.get_booking(session, result.id))


@router.post("/bookings/{booking_id}/manage-link", response_model=ManageLinkView)
async def manage_link(
    request: Request, actor: Admin, session: Session, now: Now, booking_id: UUID
) -> ManageLinkView:
    """Self-service link for staff to send by hand until the WhatsApp channel sends it."""
    settings = cast(Settings, request.app.state.settings)

    async def issue() -> ManageLinkView:
        async with session.begin():
            item = await session.get(Booking, booking_id, with_for_update=True)
            if item is None:
                raise booking.BookingNotFound("Booking not found")
            if item.status not in ("held", "confirmed") or item.starts_at <= now:
                raise booking.BookingConflict("Booking is not open for changes", "invalid_state")
            url = manage_url(settings, item)
            if url is None:
                raise booking.BookingError(
                    "Self-service links are not configured", "manage_link_not_configured"
                )
            session.add(
                BookingEvent(
                    id=uuid.uuid4(),
                    booking_id=item.id,
                    action="manage_link_issued",
                    from_status=item.status,
                    to_status=item.status,
                    actor_type="staff",
                    actor_subject=actor.subject,
                )
            )
            return ManageLinkView(url=url, expires_at=item.starts_at)

    return await _guard(issue())
