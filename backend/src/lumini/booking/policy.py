"""Booking rules as data. Changing a value is a product decision recorded in docs/DECISOES.md."""

from dataclasses import dataclass, field
from datetime import timedelta
from zoneinfo import ZoneInfo

CLINIC_TZ = ZoneInfo("America/Sao_Paulo")


@dataclass(frozen=True)
class BookingPolicy:
    # Plan: a chosen time is reserved for two hours while the deposit is confirmed by a human.
    hold: timedelta = timedelta(hours=2)
    # Placing the tentative calendar event must finish quickly or the slot is released.
    calendar_placement: timedelta = timedelta(minutes=10)
    # ADR-008: never closer than 2h; one extra hour leaves time for the human confirmation.
    min_lead: timedelta = timedelta(hours=3)
    horizon: timedelta = timedelta(days=60)
    slot_step: timedelta = timedelta(minutes=15)
    min_buffer: timedelta = timedelta(minutes=15)
    expiry_warning: timedelta = timedelta(minutes=30)
    # ADR-006: self-service only when strictly more than 24h remain.
    self_service_cutoff: timedelta = timedelta(hours=24)
    reminders: tuple[tuple[str, timedelta], ...] = field(
        default=(("reminder_24h", timedelta(hours=24)), ("reminder_2h", timedelta(hours=2)))
    )
    aftercare_window: timedelta = timedelta(days=2)


DEFAULT_POLICY = BookingPolicy()
