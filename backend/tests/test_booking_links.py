"""Self-service link tokens: signed, bound to one booking, expiring at the appointment."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import pytest
from pydantic import SecretStr, ValidationError

from lumini.booking.links import issue_token, manage_url, read_token
from lumini.models import Booking
from lumini.settings import Settings

SECRET = "synthetic-manage-link-secret-0123456789"
BOOKING = UUID("12345678-1234-5678-1234-567812345678")
NOW = datetime(2026, 10, 5, 12, tzinfo=UTC)
STARTS = NOW + timedelta(days=3)


def test_valid_token_names_its_booking_until_the_appointment() -> None:
    token = issue_token(SECRET, BOOKING, STARTS)
    assert len(token) == 85 and token.startswith(BOOKING.hex)
    assert read_token(SECRET, token, now=NOW) == BOOKING
    assert read_token(SECRET, token, now=STARTS - timedelta(seconds=1)) == BOOKING
    assert read_token(SECRET, token, now=STARTS) is None


def flip(text: str, index: int) -> str:
    replacement = "0" if text[index] != "0" else "1"
    return text[:index] + replacement + text[index + 1 :]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda token: flip(token, 0),  # another booking
        lambda token: flip(token, 33),  # later expiry
        lambda token: flip(token, len(token) - 2),  # signature
        lambda token: token[:-1],
        lambda token: token + "A",
        lambda token: token.upper(),
        lambda token: "",
        lambda token: f"{token}\n",
    ],
)
def test_altered_tokens_are_rejected(mutate: Any) -> None:
    assert read_token(SECRET, mutate(issue_token(SECRET, BOOKING, STARTS)), now=NOW) is None


def test_rotating_the_secret_revokes_every_link() -> None:
    token = issue_token(SECRET, BOOKING, STARTS)
    assert read_token("another-synthetic-secret-0123456789abc", token, now=NOW) is None


def booking() -> Booking:
    return cast(Booking, SimpleNamespace(id=BOOKING, starts_at=STARTS))


def test_link_needs_both_secret_and_public_site() -> None:
    assert manage_url(Settings(), booking()) is None
    assert manage_url(Settings(manage_link_secret=SecretStr(SECRET)), booking()) is None
    settings = Settings(
        manage_link_secret=SecretStr(SECRET), public_site_url="https://synthetic.example/"
    )
    url = manage_url(settings, booking())
    assert url is not None and url.startswith("https://synthetic.example/reserva#")
    token = url.split("#", 1)[1]
    assert read_token(SECRET, token, now=NOW) == BOOKING


@pytest.mark.parametrize(
    "site",
    [
        "http://synthetic.example",
        "https://synthetic.example/path",
        "https://user:pass@synthetic.example",
        "https://synthetic.example/?q=1",
        "ftp://synthetic.example",
    ],
)
def test_public_site_must_be_a_plain_https_origin(site: str) -> None:
    with pytest.raises(ValidationError):
        Settings(public_site_url=site)


def test_loopback_site_may_use_http_and_short_secrets_are_refused() -> None:
    assert Settings(public_site_url="http://127.0.0.1:3000").public_site_url == (
        "http://127.0.0.1:3000"
    )
    with pytest.raises(ValidationError) as caught:
        Settings(manage_link_secret=SecretStr("too-short-synthetic"))
    assert "too-short" not in str(caught.value)
