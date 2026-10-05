"""Booking rules: holds, human deposit confirmation, expiry, cancellation and rescheduling.

PostgreSQL owns booking state and enforces non-overlap per professional. The calendar is updated
through the outbox and is never assumed atomic with the database (ADR-003/008): when the remote
state is uncertain the booking is not confirmed to the client. Calendar I/O never happens inside a
database transaction. Errors carry fixed messages only.
"""

import re
import uuid
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Literal

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from lumini.booking.availability import Interval, WeeklyRule, free_slots, working_windows
from lumini.booking.calendar import (
    CalendarAdapter,
    CalendarEvent,
    CalendarRejected,
    event_id,
    is_ours,
)
from lumini.booking.outbox import enqueue_calendar_sync, enqueue_notification
from lumini.booking.policy import CLINIC_TZ, DEFAULT_POLICY, BookingPolicy
from lumini.catalog.service import bookable_service
from lumini.models import (
    ACTIVE_BOOKING_STATUSES,
    AvailabilityRule,
    Booking,
    BookingEvent,
    Contact,
    ProfessionalSchedule,
    Service,
)

_CENTS = Decimal("0.01")
_PHONE = re.compile(r"\+[1-9]\d{7,14}\Z")
_EXCLUSION_VIOLATION = "23P01"
_UNIQUE_VIOLATION = "23505"
_RETRYABLE = {"40P01", "40001"}  # deadlock detected, serialization failure
WRITE_ATTEMPTS = 3

ActorType = Literal["system", "staff", "client"]


@dataclass(frozen=True)
class Actor:
    type: ActorType
    subject: str | None = None

    @classmethod
    def staff(cls, subject: str) -> "Actor":
        return cls("staff", subject)


SYSTEM = Actor("system")
CLIENT = Actor("client")


class BookingError(Exception):
    """Workflow refusal: fixed English message plus a stable code the UI translates."""

    code = "conflict"

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


class BookingNotFound(BookingError):
    code = "not_found"


class BookingConflict(BookingError):
    """Stale version, invalid state, reused idempotency key or divergent deposit."""


class SlotUnavailable(BookingError):
    code = "slot_unavailable"


class InvalidBookingRequest(BookingError):
    """Malformed client input (name, phone, idempotency key)."""

    code = "invalid_request"


class NotBookable(BookingError):
    """Service, professional or agenda is not eligible for online booking."""

    code = "not_bookable"


class RequiresHuman(BookingError):
    """Policy reserves this decision for the clinic (late changes, second reschedule, ...)."""

    code = "requires_human"


@dataclass(frozen=True)
class HoldRequest:
    idempotency_key: str
    service_id: uuid.UUID
    professional_id: uuid.UUID
    starts_at: datetime
    contact_name: str
    contact_phone: str


@dataclass(frozen=True)
class _SlotContext:
    service: Service
    calendar_id: str
    rules: list[WeeklyRule]
    duration: timedelta
    buffer: timedelta
    deposit: Decimal


def _sqlstate(error: DBAPIError) -> str | None:
    return getattr(error.orig, "sqlstate", None)


async def _retrying[T](operation: Callable[[], Awaitable[T]]) -> T:
    """Run a write transaction again when PostgreSQL aborted it to break a deadlock.

    Concurrent inserts for the same time wait on each other in the exclusion constraint and
    PostgreSQL may abort one of them (40P01). The retry then sees the winner and answers
    SlotUnavailable, or succeeds if the winner rolled back. Constraint violations are final.
    """
    attempt = 1
    while True:
        try:
            return await operation()
        except DBAPIError as error:
            if (
                isinstance(error, IntegrityError)
                or _sqlstate(error) not in _RETRYABLE
                or attempt >= WRITE_ATTEMPTS
            ):
                raise
            attempt += 1


def _record(
    session: AsyncSession,
    booking: Booking,
    action: str,
    from_status: str | None,
    actor: Actor,
) -> None:
    session.add(
        BookingEvent(
            id=uuid.uuid4(),
            booking_id=booking.id,
            action=action,
            from_status=from_status,
            to_status=booking.status,
            actor_type=actor.type,
            actor_subject=actor.subject,
        )
    )


def _transition(
    session: AsyncSession,
    booking: Booking,
    to_status: str,
    *,
    action: str,
    actor: Actor,
    expires_at: datetime | None = None,
    reason: str | None = None,
) -> None:
    from_status = booking.status
    booking.status = to_status
    booking.version += 1
    booking.expires_at = expires_at
    if reason is not None:
        booking.closed_reason = reason
    _record(session, booking, action, from_status, actor)


def _check_version(booking: Booking, expected_version: int) -> None:
    if booking.version != expected_version:
        raise BookingConflict("The booking changed; reload before retrying", "stale")


async def _locked(session: AsyncSession, booking_id: uuid.UUID) -> Booking:
    booking = await session.get(Booking, booking_id, with_for_update=True)
    if booking is None:
        raise BookingNotFound("Booking not found")
    return booking


def normalize_phone(raw: str) -> str:
    phone = re.sub(r"[\s().-]", "", raw)
    if not _PHONE.fullmatch(phone):
        raise InvalidBookingRequest("Phone must be in international format, e.g. +5521999999999")
    return phone


async def _slot_context(
    session: AsyncSession,
    service_id: uuid.UUID,
    professional_id: uuid.UUID,
    policy: BookingPolicy,
) -> _SlotContext:
    found = await bookable_service(session, service_id)
    if found is None:
        raise NotBookable("Service is not available for online booking")
    service, linked = found
    if service.booking_mode != "direct":
        raise NotBookable("This service starts with an evaluation booking", "evaluation_required")
    if professional_id not in linked:
        raise NotBookable("Professional does not perform this service")
    schedule = await session.get(ProfessionalSchedule, professional_id)
    rules = [
        WeeklyRule(rule.weekday, rule.start_time, rule.end_time)
        for rule in await session.scalars(
            select(AvailabilityRule).where(AvailabilityRule.professional_id == professional_id)
        )
    ]
    if schedule is None or not schedule.calendar_id or not rules:
        raise NotBookable("Professional agenda is not configured", "agenda_not_configured")
    if service.duration_minutes is None or service.deposit_brl is None:
        raise NotBookable("Service is not available for online booking")  # defensive
    return _SlotContext(
        service=service,
        calendar_id=schedule.calendar_id,
        rules=rules,
        duration=timedelta(minutes=service.duration_minutes),
        buffer=max(timedelta(minutes=service.buffer_minutes), policy.min_buffer),
        deposit=service.deposit_brl.quantize(_CENTS),
    )


def _local_day(instant: datetime) -> date:
    return instant.astimezone(CLINIC_TZ).date()


def _check_start(
    rules: Sequence[WeeklyRule],
    starts_at: datetime,
    duration: timedelta,
    buffer: timedelta,
    now: datetime,
    policy: BookingPolicy,
) -> None:
    """The start must be a grid slot inside working hours, past the minimum lead, within horizon."""
    if now < starts_at < now + policy.min_lead:
        raise RequiresHuman("Times this close are arranged directly with the clinic", "too_close")
    day = _local_day(starts_at)
    candidates = free_slots(
        windows=working_windows(rules, day, day, CLINIC_TZ),
        busy=[],
        duration=duration,
        buffer=buffer,
        step=policy.slot_step,
        earliest=now + policy.min_lead,
        latest=now + policy.horizon,
    )
    if starts_at not in candidates:
        raise SlotUnavailable("Requested time is outside the bookable schedule")


async def _external_conflict(
    calendar: CalendarAdapter, calendar_id: str, blocked: Interval
) -> bool:
    # Our own events mirror bookings that PostgreSQL already accounts for.
    busy = await calendar.list_busy(calendar_id, blocked.start, blocked.end)
    return any(
        not is_ours(item.event_id) and blocked.overlaps(Interval(item.start, item.end))
        for item in busy
    )


async def _booked(
    session: AsyncSession, professional_id: uuid.UUID, span: Interval
) -> list[Interval]:
    rows = await session.execute(
        select(Booking.starts_at, Booking.blocked_until).where(
            Booking.professional_id == professional_id,
            Booking.status.in_(ACTIVE_BOOKING_STATUSES),
            Booking.starts_at < span.end,
            Booking.blocked_until > span.start,
        )
    )
    return [Interval(start, end) for start, end in rows]


async def available_slots(
    session: AsyncSession,
    calendar: CalendarAdapter,
    *,
    service_id: uuid.UUID,
    professional_id: uuid.UUID,
    first_day: date,
    last_day: date,
    now: datetime,
    policy: BookingPolicy = DEFAULT_POLICY,
) -> list[datetime]:
    """Bookable starts: working hours minus bookings and minus external calendar events."""
    earliest, latest = now + policy.min_lead, now + policy.horizon
    async with session.begin():
        context = await _slot_context(session, service_id, professional_id, policy)
        windows = [
            window
            for window in working_windows(context.rules, first_day, last_day, CLINIC_TZ)
            if window.end > earliest and window.start <= latest
        ]
        if not windows:
            return []
        span = Interval(windows[0].start, windows[-1].end + context.buffer)
        booked = await _booked(session, professional_id, span)
    external = await _external_busy(calendar, context.calendar_id, span)
    return free_slots(
        windows=windows,
        busy=booked + external,
        duration=context.duration,
        buffer=context.buffer,
        step=policy.slot_step,
        earliest=earliest,
        latest=latest,
    )


async def _external_busy(
    calendar: CalendarAdapter, calendar_id: str, span: Interval
) -> list[Interval]:
    busy = await calendar.list_busy(calendar_id, span.start, span.end)
    return [Interval(item.start, item.end) for item in busy if not is_ours(item.event_id)]


def _same_request(booking: Booking, request: HoldRequest, starts_at: datetime) -> bool:
    return (
        booking.service_id == request.service_id
        and booking.professional_id == request.professional_id
        and booking.starts_at == starts_at
    )


async def _by_key(session: AsyncSession, key: str) -> Booking | None:
    result = await session.scalars(
        select(Booking)
        .where(Booking.idempotency_key == key)
        .execution_options(populate_existing=True)
    )
    return result.one_or_none()


async def _contact_id(session: AsyncSession, name: str, phone: str) -> uuid.UUID:
    contact_id = await session.scalar(
        insert(Contact)
        .values(id=uuid.uuid4(), name=name, phone_e164=phone)
        .on_conflict_do_update(index_elements=[Contact.phone_e164], set_={"name": name})
        .returning(Contact.id)
    )
    if contact_id is None:  # pragma: no cover - RETURNING always yields a row
        raise BookingConflict("Contact could not be stored")
    return contact_id


async def create_hold(
    session: AsyncSession,
    calendar: CalendarAdapter,
    request: HoldRequest,
    *,
    now: datetime,
    actor: Actor = CLIENT,
    policy: BookingPolicy = DEFAULT_POLICY,
) -> Booking:
    """Reserve a slot. Idempotent by key; the client is told it is held only after the calendar."""
    if not 8 <= len(request.idempotency_key) <= 128:
        raise InvalidBookingRequest("Invalid idempotency key")
    name = request.contact_name.strip()
    if not 1 <= len(name) <= 120 or "<" in name or ">" in name:
        raise InvalidBookingRequest("Contact name must be plain text up to 120 characters")
    phone = normalize_phone(request.contact_phone)
    starts_at = request.starts_at.astimezone(UTC)

    async with session.begin():
        existing = await _by_key(session, request.idempotency_key)
        if existing is not None:
            if not _same_request(existing, request, starts_at):
                raise BookingConflict(
                    "Idempotency key already used for another request", "idempotency_conflict"
                )
            return existing
        context = await _slot_context(session, request.service_id, request.professional_id, policy)

    _check_start(context.rules, starts_at, context.duration, context.buffer, now, policy)
    blocked = Interval(starts_at, starts_at + context.duration + context.buffer)
    if await _external_conflict(calendar, context.calendar_id, blocked):
        raise SlotUnavailable("Requested time is no longer available")

    async def write() -> Booking:
        async with session.begin():
            # Revalidate inside the write transaction: catalog or agenda may have changed.
            context = await _slot_context(
                session, request.service_id, request.professional_id, policy
            )
            booking = Booking(
                id=uuid.uuid4(),
                idempotency_key=request.idempotency_key,
                service_id=context.service.id,
                service_revision=context.service.revision,
                professional_id=request.professional_id,
                contact_id=await _contact_id(session, name, phone),
                starts_at=starts_at,
                ends_at=starts_at + context.duration,
                blocked_until=blocked.end,
                status="pending_calendar",
                version=1,
                expires_at=now + policy.calendar_placement,
                deposit_brl=context.deposit,
                calendar_status="none",
                reschedule_count=0,
            )
            session.add(booking)
            await session.flush()
            _record(session, booking, "hold_requested", None, actor)
            await enqueue_calendar_sync(session, booking, now)
        return booking

    try:
        booking = await _retrying(write)
    except IntegrityError as error:
        if _sqlstate(error) == _EXCLUSION_VIOLATION:
            raise SlotUnavailable("Requested time is no longer available") from None
        if _sqlstate(error) == _UNIQUE_VIOLATION:
            async with session.begin():
                existing = await _by_key(session, request.idempotency_key)
            if existing is not None and _same_request(existing, request, starts_at):
                return existing
            raise BookingConflict(
                "Idempotency key already used for another request", "idempotency_conflict"
            ) from None
        raise
    return booking


@dataclass(frozen=True)
class _SyncSnapshot:
    version: int
    status: str
    calendar_id: str | None
    event: CalendarEvent
    blocked: Interval
    desired: Literal["tentative", "confirmed", "deleted"] | None


def _desired(booking: Booking) -> Literal["tentative", "confirmed", "deleted"] | None:
    if booking.status == "pending_calendar":
        return "confirmed" if booking.deposit_confirmed_at is not None else "tentative"
    if booking.status == "held":
        return "tentative"
    if booking.status in ("confirming", "confirmed"):
        return "confirmed"
    if booking.status in ("expired", "cancelled"):
        return "deleted"
    return None  # conflict: a human decides what the calendar should show


def _summary(service_name: str, status: str) -> str:
    label = "confirmado" if status == "confirmed" else "aguardando confirmação do sinal"
    return f"Lumini · {service_name} · {label}"


SyncResult = Literal["synced", "unchanged", "superseded", "rejected", "human"]


async def sync_calendar(
    session: AsyncSession,
    calendar: CalendarAdapter,
    booking_id: uuid.UUID,
    *,
    now: datetime,
    policy: BookingPolicy = DEFAULT_POLICY,
) -> SyncResult:
    """Converge the calendar to the booking's current state, then advance the booking.

    Raises CalendarUnavailable for transient failures so the outbox retries.
    """
    async with session.begin():
        row = (
            await session.execute(
                select(Booking, ProfessionalSchedule.calendar_id, Service.name)
                .join(Service, Service.id == Booking.service_id)
                .outerjoin(
                    ProfessionalSchedule,
                    ProfessionalSchedule.professional_id == Booking.professional_id,
                )
                .where(Booking.id == booking_id)
                # A long-lived session may hold an older copy; sync must see the current state.
                .execution_options(populate_existing=True)
            )
        ).one_or_none()
        if row is None:
            raise BookingNotFound("Booking not found")
        booking, calendar_id, service_name = row
        desired = _desired(booking)
        settled = booking.status not in ("pending_calendar", "confirming")
        if desired is None:
            return "human"
        if settled and booking.calendar_status == desired:
            return "unchanged"
        snapshot = _SyncSnapshot(
            version=booking.version,
            status=booking.status,
            calendar_id=calendar_id,
            event=CalendarEvent(
                id=event_id(booking.id),
                start=booking.starts_at,
                end=booking.ends_at,
                status="confirmed" if desired == "confirmed" else "tentative",
                summary=_summary(service_name, desired or "tentative"),
                description=(
                    f"Reserva {booking.id.hex[:8].upper()} gerenciada pelo sistema Lumini. "
                    "Não altere horário ou exclua por aqui: use o painel."
                ),
            ),
            blocked=Interval(booking.starts_at, booking.blocked_until),
            desired=desired,
        )
    if snapshot.desired is None:  # pragma: no cover - returned above
        return "human"

    conflict = rejected = False
    try:
        if snapshot.calendar_id is None:
            raise CalendarRejected("calendar_not_configured")
        if snapshot.desired == "deleted":
            await calendar.delete_event(snapshot.calendar_id, snapshot.event.id)
        else:
            await calendar.upsert_event(snapshot.calendar_id, snapshot.event)
            if snapshot.status == "pending_calendar":
                conflict = await _external_conflict(
                    calendar, snapshot.calendar_id, snapshot.blocked
                )
    except CalendarRejected:
        rejected = True

    async with session.begin():
        booking = await _locked(session, booking_id)
        if booking.version != snapshot.version:
            return "superseded"  # the job enqueued with that change converges again
        if rejected:
            if booking.status == "pending_calendar":
                _transition(
                    session,
                    booking,
                    "conflict",
                    action="calendar_rejected",
                    actor=SYSTEM,
                    reason="calendar_rejected",
                )
                await enqueue_notification(session, booking.id, "human_handoff", now)
            return "rejected"
        booking.calendar_status = snapshot.desired
        if booking.status == "pending_calendar":
            if conflict:
                _transition(
                    session,
                    booking,
                    "conflict",
                    action="calendar_conflict",
                    actor=SYSTEM,
                    reason="calendar_conflict",
                )
                await enqueue_notification(session, booking.id, "human_handoff", now)
            elif booking.deposit_confirmed_at is not None:
                _transition(session, booking, "confirmed", action="rescheduled", actor=SYSTEM)
                for event in ("booking_rescheduled", "manage_link"):
                    await enqueue_notification(session, booking.id, event, now)
            else:
                _transition(
                    session,
                    booking,
                    "held",
                    action="held",
                    actor=SYSTEM,
                    expires_at=now + policy.hold,
                )
                await enqueue_notification(session, booking.id, "hold_created", now)
                if booking.deposit_brl > 0:
                    await enqueue_notification(session, booking.id, "deposit_instructions", now)
        elif booking.status == "confirming":
            _transition(session, booking, "confirmed", action="confirmed", actor=SYSTEM)
            for event in ("booking_confirmed", "manage_link"):
                await enqueue_notification(session, booking.id, event, now)
    return "synced"


async def confirm_deposit(
    session: AsyncSession,
    booking_id: uuid.UUID,
    *,
    actor: Actor,
    expected_version: int,
    amount_brl: Decimal,
    now: datetime,
) -> Booking:
    """Authenticated human confirmation. Competes with expiry on the same locked row."""
    if actor.type != "staff" or not actor.subject:
        raise BookingConflict("Only authenticated staff can confirm deposits", "forbidden")
    async with session.begin():
        booking = await _locked(session, booking_id)
        _check_version(booking, expected_version)
        if (
            booking.status == "held"
            and booking.expires_at is not None
            and booking.expires_at <= now
        ):
            raise RequiresHuman(
                "The hold expired; the time may already be free for others", "hold_expired"
            )
        if booking.status != "held":
            raise BookingConflict(
                "Only held bookings can receive a deposit confirmation", "invalid_state"
            )
        if amount_brl.quantize(_CENTS) != booking.deposit_brl.quantize(_CENTS):
            raise BookingConflict(
                "Received amount differs from the expected deposit", "deposit_mismatch"
            )
        booking.deposit_confirmed_at = now
        booking.deposit_confirmed_by = actor.subject
        _transition(session, booking, "confirming", action="deposit_confirmed", actor=actor)
        await enqueue_calendar_sync(session, booking, now)
    return booking


async def expire_due(session: AsyncSession, *, now: datetime, limit: int = 200) -> list[uuid.UUID]:
    """Release holds past their deadline. Rows locked by a concurrent confirmation are skipped."""
    async with session.begin():
        due = list(
            await session.scalars(
                select(Booking)
                .where(
                    Booking.status.in_(("pending_calendar", "held")),
                    Booking.expires_at <= now,
                )
                .order_by(Booking.expires_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        )
        for booking in due:
            was_held = booking.status == "held"
            _transition(
                session,
                booking,
                "expired",
                action="expired",
                actor=SYSTEM,
                reason="deposit_timeout" if was_held else "calendar_timeout",
            )
            await enqueue_calendar_sync(session, booking, now)
            event = "hold_expired" if was_held else "human_handoff"
            await enqueue_notification(session, booking.id, event, now)
        return [booking.id for booking in due]


async def cancel_booking(
    session: AsyncSession,
    booking_id: uuid.UUID,
    *,
    actor: Actor,
    expected_version: int,
    now: datetime,
    policy: BookingPolicy = DEFAULT_POLICY,
) -> Booking:
    """Clients cancel unpaid holds anytime and paid bookings only with more than 24h left."""
    async with session.begin():
        booking = await _locked(session, booking_id)
        _check_version(booking, expected_version)
        if booking.status not in ACTIVE_BOOKING_STATUSES:
            raise BookingConflict("Booking is no longer active", "invalid_state")
        if booking.attendance is not None:
            raise BookingConflict("Attendance already recorded", "attendance_recorded")
        if actor.type == "client":
            refusal = client_cancel_refusal(booking, now, policy)
            if refusal is not None:
                raise RequiresHuman("This cancellation is handled by the clinic", refusal)
        elif actor.type != "staff" or not actor.subject:
            raise BookingConflict("Not allowed")
        _transition(
            session,
            booking,
            "cancelled",
            action="cancelled",
            actor=actor,
            reason=f"cancelled_by_{actor.type}",
        )
        await enqueue_calendar_sync(session, booking, now)
        await enqueue_notification(session, booking.id, "booking_cancelled", now)
    return booking


def client_cancel_refusal(booking: Booking, now: datetime, policy: BookingPolicy) -> str | None:
    """Why a client may not cancel on their own (None = allowed). Shared with the client page."""
    if booking.status not in ACTIVE_BOOKING_STATUSES:
        return "closed"
    if booking.status == "held":
        return None  # unpaid: always free to give the time back
    if booking.status != "confirmed":
        return "in_progress"  # calendar placement, deposit confirmation or conflict: the clinic
    if booking.starts_at - now <= policy.self_service_cutoff:
        return "within_24h"
    return None


def client_reschedule_refusal(booking: Booking, now: datetime, policy: BookingPolicy) -> str | None:
    """Why a client may not reschedule on their own (None = allowed)."""
    if booking.status not in ACTIVE_BOOKING_STATUSES:
        return "closed"
    if booking.status != "confirmed":
        return "not_confirmed"
    if booking.reschedule_count > 0:
        return "second_reschedule"
    if booking.starts_at - now <= policy.self_service_cutoff:
        return "within_24h"
    return None


def _check_reschedule(booking: Booking, actor: Actor, now: datetime, policy: BookingPolicy) -> None:
    if booking.status != "confirmed":
        raise BookingConflict("Only confirmed bookings can be rescheduled", "invalid_state")
    if booking.attendance is not None:
        raise BookingConflict("Attendance already recorded", "attendance_recorded")
    if actor.type == "client":
        refusal = client_reschedule_refusal(booking, now, policy)
        if refusal is not None:
            raise RequiresHuman("This change is handled by the clinic", refusal)
    elif actor.type != "staff" or not actor.subject:
        raise BookingConflict("Not allowed")


async def reschedule_booking(
    session: AsyncSession,
    calendar: CalendarAdapter,
    booking_id: uuid.UUID,
    *,
    actor: Actor,
    expected_version: int,
    new_starts_at: datetime,
    now: datetime,
    policy: BookingPolicy = DEFAULT_POLICY,
) -> Booking:
    """Move a paid booking keeping its deposit: new booking + cancelled original, atomically."""
    starts_at = new_starts_at.astimezone(UTC)
    async with session.begin():
        original = await session.get(Booking, booking_id, populate_existing=True)
        if original is None:
            raise BookingNotFound("Booking not found")
        key = f"reschedule:{original.id}:{expected_version}"
        existing = await _by_key(session, key)
        if existing is not None:  # idempotent retry of the same reschedule
            if existing.starts_at != starts_at:
                raise BookingConflict("This reschedule was already requested for another time")
            return existing
        _check_version(original, expected_version)
        _check_reschedule(original, actor, now, policy)
        context = await _slot_context(
            session, original.service_id, original.professional_id, policy
        )
        duration = original.ends_at - original.starts_at
        buffer = original.blocked_until - original.ends_at

    _check_start(context.rules, starts_at, duration, buffer, now, policy)
    blocked = Interval(starts_at, starts_at + duration + buffer)
    if await _external_conflict(calendar, context.calendar_id, blocked):
        raise SlotUnavailable("Requested time is no longer available")

    async def write() -> Booking:
        async with session.begin():
            original = await _locked(session, booking_id)
            _check_version(original, expected_version)
            _check_reschedule(original, actor, now, policy)
            _transition(
                session,
                original,
                "cancelled",
                action="rescheduled",
                actor=actor,
                reason="rescheduled",
            )
            await enqueue_calendar_sync(session, original, now)
            await session.flush()  # free the old range before the new one is checked
            replacement = Booking(
                id=uuid.uuid4(),
                idempotency_key=key,
                service_id=original.service_id,
                service_revision=original.service_revision,
                professional_id=original.professional_id,
                contact_id=original.contact_id,
                starts_at=starts_at,
                ends_at=starts_at + duration,
                blocked_until=blocked.end,
                status="pending_calendar",
                version=1,
                expires_at=now + policy.calendar_placement,
                deposit_brl=original.deposit_brl,
                deposit_confirmed_at=original.deposit_confirmed_at,
                deposit_confirmed_by=original.deposit_confirmed_by,
                calendar_status="none",
                rescheduled_from_id=original.id,
                reschedule_count=original.reschedule_count + 1,
            )
            session.add(replacement)
            await session.flush()
            _record(session, replacement, "rescheduled_from", None, actor)
            await enqueue_calendar_sync(session, replacement, now)
        return replacement

    try:
        replacement = await _retrying(write)
    except IntegrityError as error:
        if _sqlstate(error) == _EXCLUSION_VIOLATION:
            raise SlotUnavailable("Requested time is no longer available") from None
        raise
    return replacement


async def resolve_conflict(
    session: AsyncSession,
    booking_id: uuid.UUID,
    *,
    actor: Actor,
    expected_version: int,
    resolution: Literal["release", "retry"],
    now: datetime,
    policy: BookingPolicy = DEFAULT_POLICY,
) -> Booking:
    """Staff decide: release the time, or retry placing the calendar event (re-verified)."""
    if actor.type != "staff" or not actor.subject:
        raise BookingConflict("Only authenticated staff can resolve conflicts", "forbidden")
    async with session.begin():
        booking = await _locked(session, booking_id)
        _check_version(booking, expected_version)
        if booking.status != "conflict":
            raise BookingConflict("Booking is not in conflict", "invalid_state")
        if resolution == "release":
            _transition(
                session,
                booking,
                "cancelled",
                action="conflict_released",
                actor=actor,
                reason="conflict_released",
            )
        else:
            _transition(
                session,
                booking,
                "pending_calendar",
                action="conflict_retry",
                actor=actor,
                expires_at=now + policy.calendar_placement,
            )
        await enqueue_calendar_sync(session, booking, now)
    return booking


async def enqueue_due_notifications(
    session: AsyncSession, *, now: datetime, policy: BookingPolicy = DEFAULT_POLICY
) -> int:
    """Time-based messages; dedupe keys make repeated scans harmless."""
    count = 0
    async with session.begin():
        expiring = await session.scalars(
            select(Booking.id).where(
                Booking.status == "held",
                Booking.expires_at > now,
                Booking.expires_at <= now + policy.expiry_warning,
            )
        )
        for booking_id in expiring:
            await enqueue_notification(session, booking_id, "hold_expiring", now)
            count += 1
        for event, delta in policy.reminders:
            due = await session.scalars(
                select(Booking.id).where(
                    Booking.status == "confirmed",
                    Booking.starts_at > now,
                    Booking.starts_at <= now + delta,
                    # Confirmed too late for this reminder: skip it rather than send it early.
                    Booking.deposit_confirmed_at <= Booking.starts_at - delta,
                )
            )
            for booking_id in due:
                await enqueue_notification(session, booking_id, event, now)
                count += 1
        finished = await session.scalars(
            select(Booking.id).where(
                Booking.status == "confirmed",
                Booking.ends_at <= now,
                Booking.ends_at > now - policy.aftercare_window,
                or_(Booking.attendance.is_(None), Booking.attendance != "no_show"),
            )
        )
        for booking_id in finished:
            await enqueue_notification(session, booking_id, "aftercare", now)
            count += 1
    return count


Attendance = Literal["attended", "no_show"]


async def mark_attendance(
    session: AsyncSession,
    booking_id: uuid.UUID,
    *,
    actor: Actor,
    expected_version: int,
    attendance: Attendance,
    now: datetime,
) -> Booking:
    """Staff record whether a confirmed appointment happened, once it has started."""
    if actor.type != "staff" or not actor.subject:
        raise BookingConflict("Only authenticated staff can record attendance", "forbidden")
    async with session.begin():
        booking = await _locked(session, booking_id)
        _check_version(booking, expected_version)
        if booking.status != "confirmed":
            raise BookingConflict("Only confirmed bookings have attendance", "invalid_state")
        if booking.starts_at > now:
            raise BookingConflict("The appointment has not started yet", "too_early")
        booking.attendance = attendance
        booking.attendance_marked_at = now
        booking.attendance_marked_by = actor.subject
        booking.version += 1
        _record(session, booking, attendance, booking.status, actor)
    return booking
