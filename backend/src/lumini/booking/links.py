"""Signed self-service links (plan §7, ADR-016).

A token names one booking and an expiry (the appointment start) and is signed with HMAC-SHA256.
Nothing is stored: rotating the secret revokes every link. The token travels in the URL
fragment (`/reserva#<token>`), which browsers never send to servers, and then in an
Authorization header, so it stays out of access logs and Referer headers.
"""

import base64
import hashlib
import hmac
import re
import uuid
from datetime import datetime

from lumini.models import Booking
from lumini.settings import Settings

_DOMAIN = b"lumini-manage-link-v1:"
_TOKEN = re.compile(r"([0-9a-f]{32})([0-9a-f]{10})([A-Za-z0-9_-]{43})")


def _mac(secret: str, body: str) -> str:
    digest = hmac.new(secret.encode(), _DOMAIN + body.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def issue_token(secret: str, booking_id: uuid.UUID, expires_at: datetime) -> str:
    body = f"{booking_id.hex}{int(expires_at.timestamp()):010x}"
    return body + _mac(secret, body)


def read_token(secret: str, token: str, *, now: datetime) -> uuid.UUID | None:
    """The booking id, or None for malformed, forged or expired tokens (indistinguishable)."""
    match = _TOKEN.fullmatch(token)
    if match is None:
        return None
    booking_hex, expiry_hex, signature = match.groups()
    if not hmac.compare_digest(signature, _mac(secret, booking_hex + expiry_hex)):
        return None
    if int(expiry_hex, 16) <= now.timestamp():
        return None
    return uuid.UUID(booking_hex)


def manage_url(settings: Settings, booking: Booking) -> str | None:
    """Link valid until the appointment starts; None when links are not configured."""
    if settings.manage_link_secret is None or settings.public_site_url is None:
        return None
    token = issue_token(
        settings.manage_link_secret.get_secret_value(), booking.id, booking.starts_at
    )
    return f"{settings.public_site_url}/reserva#{token}"
