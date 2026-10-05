"""Google Calendar adapter against scripted HTTP responses; no network, synthetic keys only."""

import base64
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs
from uuid import UUID

import pytest
import requests
from google.auth.exceptions import TransportError

from lumini.booking.calendar import (
    BusyBlock,
    CalendarEvent,
    CalendarRejected,
    CalendarUnavailable,
    booking_id_of,
    event_id,
    is_ours,
)
from lumini.booking.google_calendar import (
    MAX_PAGES,
    MAX_RESPONSE_BYTES,
    SCOPE,
    TIMEOUT,
    GoogleCalendar,
    HttpResponse,
    RequestsTransport,
    ServiceAccountTokens,
    build_calendar,
)
from lumini.settings import Settings
from tests.calendar_keys import TOKEN_URI, service_account_info, service_account_json

CAL = "clinic#synthetic@group.calendar.google.com"
ENCODED = "clinic%23synthetic%40group.calendar.google.com"
BOOKING = UUID("12345678-1234-5678-1234-567812345678")
LEAK = "SYNTHETIC PROVIDER DETAIL"


@dataclass
class Call:
    method: str
    url: str
    token: str
    params: dict[str, str]
    payload: dict[str, Any] | None


@dataclass
class FakeTransport:
    responses: list[HttpResponse | Exception]
    calls: list[Call] = field(default_factory=list)

    def __call__(
        self,
        method: str,
        url: str,
        *,
        token: str,
        params: Any = None,
        payload: Any = None,
    ) -> HttpResponse:
        self.calls.append(Call(method, url, token, dict(params or {}), payload))
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@dataclass
class FakeTokens:
    forced: int = 0

    def token(self, *, force: bool = False) -> str:
        self.forced += force
        return f"synthetic-token-{self.forced}"


def adapter(*responses: HttpResponse | Exception) -> tuple[GoogleCalendar, FakeTransport]:
    transport = FakeTransport(list(responses))
    return GoogleCalendar(FakeTokens(), transport), transport


def ok(body: dict[str, Any] | None = None, status: int = 200) -> HttpResponse:
    return HttpResponse(status, body)


def failure(status: int, reason: str = "synthetic") -> HttpResponse:
    return HttpResponse(status, {"error": {"errors": [{"reason": reason}], "message": LEAK}})


def timed(value: str) -> dict[str, str]:
    return {"dateTime": value}


START = datetime(2026, 10, 6, 3, tzinfo=UTC)
END = datetime(2026, 10, 8, 3, tzinfo=UTC)
EVENT = CalendarEvent(
    id=event_id(BOOKING),
    start=datetime(2026, 10, 6, 13, tzinfo=UTC),
    end=datetime(2026, 10, 6, 14, tzinfo=UTC),
    status="tentative",
    summary="Lumini · Synthetic procedure · aguardando confirmação do sinal",
    description="Reserva 12345678 gerenciada pelo sistema Lumini.",
)


def test_event_ids_are_recognized_only_in_the_exact_format() -> None:
    assert booking_id_of(event_id(BOOKING)) == BOOKING
    assert is_ours(event_id(BOOKING))
    for other in (None, "", "manual0001", "lumini", "luminiabc", f"{event_id(BOOKING)}_20261006"):
        assert not is_ours(other)


async def test_busy_time_follows_pages_and_skips_free_or_cancelled_events() -> None:
    calendar, transport = adapter(
        ok(
            {
                "items": [
                    {
                        "id": event_id(BOOKING),
                        "status": "tentative",
                        "start": timed("2026-10-06T10:00:00-03:00"),
                        "end": timed("2026-10-06T11:00:00-03:00"),
                    },
                    {
                        "id": "free0001",
                        "transparency": "transparent",
                        "start": timed("2026-10-06T12:00:00Z"),
                        "end": timed("2026-10-06T13:00:00Z"),
                    },
                    {
                        "id": "gone0001",
                        "status": "cancelled",
                        "start": timed("2026-10-06T12:00:00Z"),
                        "end": timed("2026-10-06T13:00:00Z"),
                    },
                ],
                "nextPageToken": "synthetic-page-2",
            }
        ),
        ok(
            {
                "items": [
                    {
                        "id": "allday01",
                        "start": {"date": "2026-10-07"},
                        "end": {"date": "2026-10-08"},
                    },
                    {
                        "id": "manual01",
                        "start": timed("2026-10-07T15:00:00Z"),
                        "end": timed("2026-10-07T15:30:00Z"),
                    },
                ]
            }
        ),
    )
    blocks = await calendar.list_busy(CAL, START, END)
    assert blocks == [
        BusyBlock(
            datetime(2026, 10, 6, 13, tzinfo=UTC),
            datetime(2026, 10, 6, 14, tzinfo=UTC),
            event_id(BOOKING),
        ),
        # All-day events block the whole clinic day (midnight in Sao Paulo, UTC-3).
        BusyBlock(
            datetime(2026, 10, 7, 3, tzinfo=UTC), datetime(2026, 10, 8, 3, tzinfo=UTC), "allday01"
        ),
        BusyBlock(
            datetime(2026, 10, 7, 15, tzinfo=UTC),
            datetime(2026, 10, 7, 15, 30, tzinfo=UTC),
            "manual01",
        ),
    ]
    first, second = transport.calls
    assert first.method == "GET"
    assert first.url == f"https://www.googleapis.com/calendar/v3/calendars/{ENCODED}/events"
    assert first.params["timeMin"] == "2026-10-06T03:00:00Z"
    assert first.params["timeMax"] == "2026-10-08T03:00:00Z"
    assert (first.params["singleEvents"], first.params["showDeleted"]) == ("true", "false")
    assert "pageToken" not in first.params
    assert second.params["pageToken"] == "synthetic-page-2"


@pytest.mark.parametrize(
    "item",
    [
        {"id": "x0000001", "end": timed("2026-10-06T13:00:00Z")},
        {
            "id": "x0000002",
            "start": timed("2026-10-06T12:00:00"),
            "end": timed("2026-10-06T13:00:00"),
        },
        {
            "id": "x0000003",
            "start": timed("2026-10-06T13:00:00Z"),
            "end": timed("2026-10-06T13:00:00Z"),
        },
        {"id": "x0000004", "start": {"date": "not-a-date"}, "end": {"date": "2026-10-08"}},
    ],
)
async def test_unreadable_events_never_count_as_free_time(item: dict[str, Any]) -> None:
    calendar, _ = adapter(ok({"items": [item]}))
    with pytest.raises(CalendarUnavailable):
        await calendar.list_busy(CAL, START, END)


async def test_too_many_pages_is_not_read_as_free_time() -> None:
    pages = [ok({"items": [], "nextPageToken": f"page-{n}"}) for n in range(MAX_PAGES)]
    calendar, transport = adapter(*pages)
    with pytest.raises(CalendarUnavailable, match="too_many_pages"):
        await calendar.list_busy(CAL, START, END)
    assert len(transport.calls) == MAX_PAGES


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (failure(429), CalendarUnavailable),
        (failure(500), CalendarUnavailable),
        (failure(503), CalendarUnavailable),
        (failure(403, "rateLimitExceeded"), CalendarUnavailable),
        (failure(403, "userRateLimitExceeded"), CalendarUnavailable),
        (failure(403, "forbidden"), CalendarRejected),
        (failure(404, "notFound"), CalendarRejected),
        (failure(400, "invalid"), CalendarRejected),
        (ok(None), CalendarUnavailable),
        (ok({"items": "not-a-list"}), CalendarUnavailable),
    ],
)
async def test_failures_are_classified_without_provider_text(
    response: HttpResponse, expected: type[Exception]
) -> None:
    calendar, _ = adapter(response)
    with pytest.raises(expected) as caught:
        await calendar.list_busy(CAL, START, END)
    assert type(caught.value) is expected
    assert LEAK not in str(caught.value) and LEAK not in repr(caught.value.args)


async def test_expired_token_is_refreshed_once() -> None:
    calendar, transport = adapter(failure(401), ok({"items": []}))
    assert await calendar.list_busy(CAL, START, END) == []
    assert [call.token for call in transport.calls] == ["synthetic-token-0", "synthetic-token-1"]

    calendar, _ = adapter(failure(401), failure(401))
    with pytest.raises(CalendarUnavailable, match="unauthorized"):
        await calendar.list_busy(CAL, START, END)


async def test_upsert_updates_in_place_and_carries_no_contact_data() -> None:
    calendar, transport = adapter(ok({}))
    await calendar.upsert_event(CAL, EVENT)
    [call] = transport.calls
    assert call.method == "PUT"
    assert call.url.endswith(f"/calendars/{ENCODED}/events/{EVENT.id}")
    assert call.params == {"sendUpdates": "none"}
    assert call.payload == {
        "id": EVENT.id,
        "summary": EVENT.summary,
        "description": EVENT.description,
        "start": {"dateTime": "2026-10-06T13:00:00Z", "timeZone": "America/Sao_Paulo"},
        "end": {"dateTime": "2026-10-06T14:00:00Z", "timeZone": "America/Sao_Paulo"},
        "status": "tentative",
        "transparency": "opaque",
        "visibility": "private",
    }


async def test_upsert_inserts_missing_events_and_survives_a_concurrent_insert() -> None:
    calendar, transport = adapter(failure(404), ok({}))
    await calendar.upsert_event(CAL, EVENT)
    assert [(call.method, call.url.rsplit("/", 1)[1]) for call in transport.calls] == [
        ("PUT", EVENT.id),
        ("POST", "events"),
    ]
    assert transport.calls[1].payload == transport.calls[0].payload

    calendar, transport = adapter(failure(404), failure(409), ok({}))
    await calendar.upsert_event(CAL, EVENT)
    assert [call.method for call in transport.calls] == ["PUT", "POST", "PUT"]

    calendar, _ = adapter(failure(403, "forbidden"))
    with pytest.raises(CalendarRejected):
        await calendar.upsert_event(CAL, EVENT)


@pytest.mark.parametrize("status", [200, 204, 404, 410])
async def test_delete_is_idempotent(status: int) -> None:
    calendar, transport = adapter(ok(None, status))
    await calendar.delete_event(CAL, EVENT.id)
    [call] = transport.calls
    assert (call.method, call.params) == ("DELETE", {"sendUpdates": "none"})


async def test_delete_outage_is_retried_later() -> None:
    calendar, _ = adapter(failure(503))
    with pytest.raises(CalendarUnavailable):
        await calendar.delete_event(CAL, EVENT.id)


async def test_get_event_reads_status_or_reports_absence() -> None:
    calendar, _ = adapter(
        ok(
            {
                "status": "confirmed",
                "start": timed("2026-10-06T10:00:00-03:00"),
                "end": timed("2026-10-06T11:00:00-03:00"),
            }
        )
    )
    found = await calendar.get_event(CAL, EVENT.id)
    assert found is not None
    assert (found.status, found.start) == ("confirmed", datetime(2026, 10, 6, 13, tzinfo=UTC))
    calendar, _ = adapter(failure(404))
    assert await calendar.get_event(CAL, EVENT.id) is None


@dataclass
class FakeRaw:
    data: bytes

    def read(self, amount: int, decode_content: bool = False) -> bytes:
        assert decode_content is True
        return self.data[:amount]


@dataclass
class FakeResponse:
    status_code: int
    raw: FakeRaw
    closed: bool = False

    def close(self) -> None:
        self.closed = True


@dataclass
class FakeSession:
    response: FakeResponse | Exception
    kwargs: dict[str, Any] = field(default_factory=dict)

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.kwargs = {"method": method, "url": url, **kwargs}
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def transport_with(response: FakeResponse | Exception) -> tuple[RequestsTransport, FakeSession]:
    session = FakeSession(response)
    return RequestsTransport(lambda: session), session  # type: ignore[arg-type,return-value]


def test_http_transport_never_follows_redirects_and_bounds_time() -> None:
    response = FakeResponse(200, FakeRaw(b'{"items": []}'))
    transport, session = transport_with(response)
    result = transport("GET", "https://example.invalid/x", token="synthetic", params={"a": "1"})
    assert result == HttpResponse(200, {"items": []})
    assert response.closed
    assert session.kwargs["allow_redirects"] is False
    assert session.kwargs["timeout"] == TIMEOUT
    assert session.kwargs["stream"] is True
    assert session.kwargs["headers"]["Authorization"] == "Bearer synthetic"


def test_http_transport_bounds_body_and_tolerates_non_json() -> None:
    transport, _ = transport_with(FakeResponse(200, FakeRaw(b"x" * (MAX_RESPONSE_BYTES + 1))))
    with pytest.raises(CalendarUnavailable, match="response_too_large"):
        transport("GET", "https://example.invalid/x", token="synthetic")
    transport, _ = transport_with(FakeResponse(502, FakeRaw(b"<html>bad gateway</html>")))
    assert transport("GET", "https://example.invalid/x", token="synthetic") == HttpResponse(
        502, None
    )


def test_http_transport_turns_network_errors_into_outages() -> None:
    transport, _ = transport_with(requests.ConnectionError(LEAK))
    with pytest.raises(CalendarUnavailable) as caught:
        transport("GET", "https://example.invalid/x", token="synthetic")
    assert LEAK not in str(caught.value) and caught.value.__cause__ is None


@dataclass
class TokenEndpoint:
    status: int = 200
    raises: Exception | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)

    def __call__(self, url: str, method: str = "GET", body: Any = None, **kwargs: Any) -> Any:
        self.calls.append({"url": url, "method": method, "body": body})
        if self.raises is not None:
            raise self.raises
        payload = (
            {"access_token": "synthetic-access-token", "expires_in": 3600}
            if self.status == 200
            else {"error": "invalid_grant", "error_description": LEAK}
        )
        return type(
            "Response",
            (),
            {"status": self.status, "headers": {}, "data": json.dumps(payload).encode()},
        )()


def test_service_account_tokens_are_minted_for_calendar_events_only() -> None:
    endpoint = TokenEndpoint()
    tokens = ServiceAccountTokens(service_account_info(), request=endpoint)
    assert tokens.token() == "synthetic-access-token"
    assert tokens.token() == "synthetic-access-token"  # cached until expiry
    assert len(endpoint.calls) == 1
    tokens.token(force=True)
    assert len(endpoint.calls) == 2
    call = endpoint.calls[0]
    assert (call["url"], call["method"]) == (TOKEN_URI, "POST")
    assertion = parse_qs(call["body"].decode())["assertion"][0]
    claims = json.loads(base64.urlsafe_b64decode(assertion.split(".")[1] + "=="))
    assert (claims["scope"], claims["aud"]) == (SCOPE, TOKEN_URI)


@pytest.mark.parametrize(
    ("endpoint", "code"),
    [
        (TokenEndpoint(raises=TransportError(LEAK)), "token_network"),  # type: ignore[no-untyped-call]
        (TokenEndpoint(status=400), "token_refused"),
    ],
)
def test_token_failures_are_outages_without_provider_text(
    endpoint: TokenEndpoint, code: str
) -> None:
    tokens = ServiceAccountTokens(service_account_info(), request=endpoint)
    with pytest.raises(CalendarUnavailable, match=code) as caught:
        tokens.token()
    assert LEAK not in str(caught.value)


def test_calendar_is_built_only_from_configured_credentials() -> None:
    from pydantic import SecretStr

    assert build_calendar(Settings()) is None
    configured = Settings(google_calendar_credentials=SecretStr(service_account_json()))
    assert isinstance(build_calendar(configured), GoogleCalendar)
