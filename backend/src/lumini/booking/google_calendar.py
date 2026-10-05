"""Google Calendar adapter (REST v3) authenticated as a service account.

The service account must be given "make changes to events" access on each professional calendar.
Blocking HTTP runs in worker threads with short timeouts and no redirects. Provider responses
never leave this module: failures become CalendarUnavailable (retry later) or CalendarRejected
(a human must fix access or the calendar id), each with a fixed code.
"""

import asyncio
import json
import logging
import threading
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Any, Protocol
from urllib.parse import quote

import requests
from google.auth.exceptions import GoogleAuthError, TransportError
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import service_account

from lumini.booking.calendar import (
    BusyBlock,
    CalendarEvent,
    CalendarRejected,
    CalendarUnavailable,
    RemoteEvent,
)
from lumini.booking.policy import CLINIC_TZ
from lumini.settings import Settings

logger = logging.getLogger(__name__)

SCOPE = "https://www.googleapis.com/auth/calendar.events"
API = "https://www.googleapis.com/calendar/v3"
TIMEOUT = (3.05, 10.0)  # connect, read (seconds)
MAX_RESPONSE_BYTES = 1_000_000
MAX_PAGES = 10
_RATE_LIMIT_REASONS = {"rateLimitExceeded", "userRateLimitExceeded", "quotaExceeded"}


@dataclass(frozen=True)
class HttpResponse:
    status: int
    body: dict[str, Any] | None


class Transport(Protocol):
    def __call__(
        self,
        method: str,
        url: str,
        *,
        token: str,
        params: Mapping[str, str] | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> HttpResponse: ...


class TokenSource(Protocol):
    def token(self, *, force: bool = False) -> str: ...


def _unavailable(code: str) -> CalendarUnavailable:
    logger.warning("google calendar unavailable: %s", code)
    return CalendarUnavailable(code)


def _rejected(code: str) -> CalendarRejected:
    logger.warning("google calendar rejected: %s", code)
    return CalendarRejected(code)


class RequestsTransport:
    """One requests.Session per thread; bodies are size-capped before parsing."""

    def __init__(self, session_factory: Callable[[], requests.Session] = requests.Session) -> None:
        self._factory = session_factory
        self._local = threading.local()

    def _session(self) -> requests.Session:
        session: requests.Session | None = getattr(self._local, "session", None)
        if session is None:
            session = self._factory()
            self._local.session = session
        return session

    def __call__(
        self,
        method: str,
        url: str,
        *,
        token: str,
        params: Mapping[str, str] | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> HttpResponse:
        try:
            response = self._session().request(
                method,
                url,
                params=params,
                json=payload,
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                timeout=TIMEOUT,
                allow_redirects=False,
                stream=True,
            )
            try:
                raw = response.raw.read(MAX_RESPONSE_BYTES + 1, decode_content=True)
            finally:
                response.close()
        except requests.RequestException:
            raise _unavailable("network") from None
        if len(raw) > MAX_RESPONSE_BYTES:
            raise _unavailable("response_too_large")
        try:
            body = json.loads(raw) if raw else None
        except ValueError:
            body = None
        return HttpResponse(response.status_code, body if isinstance(body, dict) else None)


class _ShortTimeoutRequest(GoogleAuthRequest):
    """google-auth waits up to 120 s for the token endpoint by default."""

    def __call__(
        self,
        url: Any,
        method: Any = "GET",
        body: Any = None,
        headers: Any = None,
        timeout: Any = None,
        **kwargs: Any,
    ) -> Any:
        return super().__call__(  # type: ignore[no-untyped-call]
            url, method=method, body=body, headers=headers, timeout=TIMEOUT[1], **kwargs
        )


class ServiceAccountTokens:
    """Access tokens minted locally from the key; refreshed under a lock, cached until expiry."""

    def __init__(self, info: Mapping[str, Any], request: Any | None = None) -> None:
        self._credentials = service_account.Credentials.from_service_account_info(  # type: ignore[no-untyped-call]
            dict(info), scopes=[SCOPE]
        )
        self._request = request if request is not None else _ShortTimeoutRequest()
        self._lock = threading.Lock()

    def token(self, *, force: bool = False) -> str:
        with self._lock:
            try:
                if force or not self._credentials.valid:
                    self._credentials.refresh(self._request)
            except TransportError:
                raise _unavailable("token_network") from None
            except GoogleAuthError:
                # Revoked/disabled key or clock skew: retried, and visible in logs by code.
                raise _unavailable("token_refused") from None
            token = self._credentials.token
            if not isinstance(token, str) or not token:
                raise _unavailable("token_missing")
            return token


def _reason(body: dict[str, Any] | None) -> str | None:
    error = (body or {}).get("error")
    if not isinstance(error, dict):
        return None
    errors = error.get("errors")
    if isinstance(errors, list) and errors and isinstance(errors[0], dict):
        reason = errors[0].get("reason")
        return reason if isinstance(reason, str) else None
    return None


def _utc(instant: datetime) -> str:
    return instant.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _instant(value: object) -> datetime:
    """Event boundary: {dateTime} with offset, or {date} for all-day events (clinic midnight)."""
    if isinstance(value, dict):
        if isinstance(value.get("dateTime"), str):
            parsed = datetime.fromisoformat(value["dateTime"])
            if parsed.tzinfo is None:
                raise ValueError("naive dateTime")
            return parsed.astimezone(UTC)
        if isinstance(value.get("date"), str):
            day = date.fromisoformat(value["date"])
            return datetime.combine(day, time(), tzinfo=CLINIC_TZ).astimezone(UTC)
    raise ValueError("missing event boundary")


class GoogleCalendar:
    """CalendarAdapter over Google Calendar API v3."""

    def __init__(self, tokens: TokenSource, transport: Transport | None = None) -> None:
        self._tokens = tokens
        self._transport = transport if transport is not None else RequestsTransport()

    @classmethod
    def from_service_account(cls, info: Mapping[str, Any]) -> "GoogleCalendar":
        return cls(ServiceAccountTokens(info))

    # Blocking core -----------------------------------------------------------------------

    def _send(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> HttpResponse:
        url = f"{API}{path}"
        response = self._transport(
            method, url, token=self._tokens.token(), params=params, payload=payload
        )
        if response.status == 401:  # token revoked or expired early: one fresh attempt
            response = self._transport(
                method, url, token=self._tokens.token(force=True), params=params, payload=payload
            )
            if response.status == 401:
                raise _unavailable("unauthorized")
        return response

    @staticmethod
    def _fail(response: HttpResponse) -> Exception:
        status = response.status
        if status == 429 or status >= 500:
            return _unavailable(f"http_{status}")
        if status == 403 and _reason(response.body) in _RATE_LIMIT_REASONS:
            return _unavailable("rate_limited")
        if status in (403, 404):
            return _rejected("calendar_access")  # missing calendar or not shared with us
        return _rejected(f"http_{status}")

    @staticmethod
    def _events_path(calendar_id: str, event_id: str | None = None) -> str:
        path = f"/calendars/{quote(calendar_id, safe='')}/events"
        return path if event_id is None else f"{path}/{quote(event_id, safe='')}"

    def _list(self, calendar_id: str, start: datetime, end: datetime) -> Iterator[dict[str, Any]]:
        params = {
            "timeMin": _utc(start),
            "timeMax": _utc(end),
            "singleEvents": "true",
            "showDeleted": "false",
            "maxResults": "250",
            "fields": "items(id,status,transparency,start,end),nextPageToken",
        }
        for _ in range(MAX_PAGES):
            response = self._send("GET", self._events_path(calendar_id), params=params)
            if response.status != 200 or response.body is None:
                raise self._fail(response) if response.status != 200 else _unavailable("body")
            items = response.body.get("items", [])
            if not isinstance(items, list):
                raise _unavailable("invalid_response")
            yield from (item for item in items if isinstance(item, dict))
            token = response.body.get("nextPageToken")
            if not isinstance(token, str) or not token:
                return
            params = {**params, "pageToken": token}
        # Never treat an unread page as free time.
        raise _unavailable("too_many_pages")

    def _list_busy(self, calendar_id: str, start: datetime, end: datetime) -> list[BusyBlock]:
        blocks: list[BusyBlock] = []
        for item in self._list(calendar_id, start, end):
            if item.get("status") == "cancelled" or item.get("transparency") == "transparent":
                continue
            try:
                block_start, block_end = _instant(item.get("start")), _instant(item.get("end"))
            except ValueError:
                raise _unavailable("invalid_event") from None
            if block_end <= block_start:
                raise _unavailable("invalid_event")
            identifier = item.get("id")
            blocks.append(
                BusyBlock(
                    block_start, block_end, identifier if isinstance(identifier, str) else None
                )
            )
        return blocks

    def _get(self, calendar_id: str, event_id: str) -> RemoteEvent | None:
        response = self._send("GET", self._events_path(calendar_id, event_id))
        if response.status in (404, 410):
            return None
        if response.status != 200 or response.body is None:
            raise self._fail(response) if response.status != 200 else _unavailable("body")
        try:
            start, end = _instant(response.body.get("start")), _instant(response.body.get("end"))
        except ValueError:
            raise _unavailable("invalid_event") from None
        status = response.body.get("status")
        return RemoteEvent(event_id, start, end, status if isinstance(status, str) else "unknown")

    def _upsert(self, calendar_id: str, event: CalendarEvent) -> None:
        body = {
            "id": event.id,
            "summary": event.summary,
            "description": event.description,
            "start": {"dateTime": _utc(event.start), "timeZone": "America/Sao_Paulo"},
            "end": {"dateTime": _utc(event.end), "timeZone": "America/Sao_Paulo"},
            "status": event.status,
            "transparency": "opaque",
            "visibility": "private",
        }
        quiet = {"sendUpdates": "none"}
        path = self._events_path(calendar_id, event.id)
        # Update first: it also restores an event that was deleted (kept as "cancelled").
        response = self._send("PUT", path, params=quiet, payload=body)
        if response.status == 404:
            response = self._send(
                "POST", self._events_path(calendar_id), params=quiet, payload=body
            )
            if response.status == 409:  # created concurrently by another attempt
                response = self._send("PUT", path, params=quiet, payload=body)
        if response.status != 200:
            raise self._fail(response)

    def _delete(self, calendar_id: str, event_id: str) -> None:
        response = self._send(
            "DELETE", self._events_path(calendar_id, event_id), params={"sendUpdates": "none"}
        )
        if response.status not in (200, 204, 404, 410):
            raise self._fail(response)

    # CalendarAdapter ---------------------------------------------------------------------

    async def list_busy(self, calendar_id: str, start: datetime, end: datetime) -> list[BusyBlock]:
        return await asyncio.to_thread(self._list_busy, calendar_id, start, end)

    async def get_event(self, calendar_id: str, event_id: str) -> RemoteEvent | None:
        return await asyncio.to_thread(self._get, calendar_id, event_id)

    async def upsert_event(self, calendar_id: str, event: CalendarEvent) -> None:
        await asyncio.to_thread(self._upsert, calendar_id, event)

    async def delete_event(self, calendar_id: str, event_id: str) -> None:
        await asyncio.to_thread(self._delete, calendar_id, event_id)


def build_calendar(settings: Settings) -> GoogleCalendar | None:
    """No network work: the key is parsed locally and tokens are minted on first use."""
    info = settings.calendar_service_account()
    return None if info is None else GoogleCalendar.from_service_account(info)
