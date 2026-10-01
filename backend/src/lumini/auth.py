"""Google ID-token authentication; no credentials, sessions, or network work at import."""

import asyncio
import json
import re
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Annotated, Protocol, cast
from uuid import UUID

import requests
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from google.auth import exceptions as google_exceptions
from google.oauth2 import id_token
from starlette.concurrency import run_in_threadpool

from lumini.settings import Settings, normalize_email

_CERTS_URL = "https://www.googleapis.com/oauth2/v1/certs"
_GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}
_MAX_TOKEN_LENGTH = 8192
_MAX_CERTIFICATE_BYTES = 262_144
_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\Z")
_DOMAIN_PATTERN = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")
# Tolerates a slightly slow server clock for iat/nbf only; expiry stays strict.
_CLOCK_SKEW_SECONDS = 10
_verify_oauth2_token = cast(Callable[..., object], id_token.verify_oauth2_token)
_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AdminPrincipal:
    subject: str
    email: str
    reviewer_professional_ids: tuple[UUID, ...]


class IdentityVerifier(Protocol):
    def verify(self, token: str) -> Mapping[str, object]: ...


class InvalidIdentityToken(Exception):
    """Deliberately omits provider details and token claims."""


class IdentityProviderUnavailable(Exception):
    """Certificate retrieval/configuration failed, distinct from invalid identity."""


@dataclass(frozen=True)
class _CertificateResponse:
    data: bytes
    status: int = 200


class _CertificateRequest:
    """Small in-memory cache for Google's fixed certificate URL only.

    Cache-Control/Age govern reuse, capped at one hour; stale keys are never used.
    A lock coalesces concurrent fetches. HTTP has bounded connect/read timeouts,
    no redirects/retries, and a size limit. No user token is sent to Google.
    """

    def __init__(self, timeout_seconds: float) -> None:
        self.timeout_seconds = timeout_seconds
        self._lock = threading.Lock()
        self._cached: _CertificateResponse | None = None
        self._expires_at = 0.0

    def __call__(self, url: str, method: str = "GET") -> _CertificateResponse:
        if url != _CERTS_URL or method != "GET":
            raise IdentityProviderUnavailable("Identity provider unavailable")
        if not self._lock.acquire(timeout=self.timeout_seconds):
            raise IdentityProviderUnavailable("Identity provider unavailable")
        try:
            if self._cached is not None and time.monotonic() < self._expires_at:
                return self._cached
            try:
                started_at = time.monotonic()
                with requests.get(
                    _CERTS_URL,
                    timeout=(self.timeout_seconds, self.timeout_seconds),
                    allow_redirects=False,
                    stream=True,
                ) as response:
                    if response.status_code != 200:
                        raise IdentityProviderUnavailable("Identity provider unavailable")
                    chunks = bytearray()
                    for chunk in response.iter_content(chunk_size=4096):
                        chunks.extend(chunk)
                        if (
                            len(chunks) > _MAX_CERTIFICATE_BYTES
                            or time.monotonic() - started_at > self.timeout_seconds * 2
                        ):
                            raise IdentityProviderUnavailable("Identity provider unavailable")
                    data = bytes(chunks)
                    certificates = json.loads(data)
                    if (
                        not isinstance(certificates, dict)
                        or not certificates
                        or "keys" in certificates
                        or not all(
                            isinstance(key, str) and isinstance(value, str)
                            for key, value in certificates.items()
                        )
                    ):
                        raise IdentityProviderUnavailable("Identity provider unavailable")
                    cached = _CertificateResponse(data=data)
                    ttl = _cache_ttl(response.headers)
                self._cached = cached
                self._expires_at = time.monotonic() + ttl
                return cached
            except (requests.RequestException, ValueError, TypeError):
                raise IdentityProviderUnavailable("Identity provider unavailable") from None
        finally:
            self._lock.release()


def _cache_ttl(headers: Mapping[str, str]) -> float:
    directives = [part.strip().lower() for part in headers.get("Cache-Control", "").split(",")]
    if any(item.split("=", 1)[0] in {"no-store", "no-cache"} for item in directives):
        return 0.0
    for item in directives:
        key, _, value = item.partition("=")
        if key == "max-age":
            try:
                age = max(0, int(headers.get("Age", "0")))
                return float(max(0, min(3600, int(value.strip('"')) - age)))
            except ValueError:
                return 0.0
    return 0.0


class GoogleIdentityVerifier:
    def __init__(self, client_id: str, timeout_seconds: float = 2.0) -> None:
        if not client_id or not 0 < timeout_seconds <= 10:
            raise ValueError("Invalid identity provider configuration")
        self.client_id = client_id
        self._request = _CertificateRequest(timeout_seconds)

    def verify(self, token: str) -> Mapping[str, object]:
        try:
            claims = _verify_oauth2_token(
                token,
                self._request,
                audience=self.client_id,
                clock_skew_in_seconds=_CLOCK_SKEW_SECONDS,
            )
            if not isinstance(claims, Mapping):
                raise InvalidIdentityToken("Invalid identity token")
            return cast(Mapping[str, object], claims)
        except google_exceptions.TransportError:
            raise IdentityProviderUnavailable("Identity provider unavailable") from None
        except (google_exceptions.GoogleAuthError, ValueError, TypeError, KeyError):
            raise InvalidIdentityToken("Invalid identity token") from None


def build_identity_verifier(settings: Settings) -> IdentityVerifier | None:
    if not settings.google_client_id or not settings.admin_emails:
        return None
    return GoogleIdentityVerifier(settings.google_client_id, settings.dependency_timeout_seconds)


def _valid_hosted_domain(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) <= 253
        and "." in value
        and all(_DOMAIN_PATTERN.fullmatch(label) for label in value.split("."))
    )


def _validate_claims(claims: Mapping[str, object], client_id: str) -> tuple[str, str]:
    """Recheck authorization-critical claims, including for injected test verifiers."""
    now = time.time()
    expires = claims.get("exp")
    issued = claims.get("iat")
    not_before = claims.get("nbf", 0)
    subject = claims.get("sub")
    email = claims.get("email")
    if (
        claims.get("iss") not in _GOOGLE_ISSUERS
        or claims.get("aud") != client_id
        or type(expires) is not int
        or expires <= now
        or type(issued) is not int
        or issued > now + _CLOCK_SKEW_SECONDS
        or expires <= issued
        or type(not_before) is not int
        or not_before > now + _CLOCK_SKEW_SECONDS
        or claims.get("email_verified") is not True
        or not isinstance(subject, str)
        or not 1 <= len(subject) <= 255
        or any(char.isspace() or ord(char) < 32 for char in subject)
        or not isinstance(email, str)
    ):
        raise InvalidIdentityToken("Invalid identity token")
    try:
        normalized = normalize_email(email)
    except ValueError:
        raise InvalidIdentityToken("Invalid identity token") from None
    # Email allowlists must not rely on stale third-party address verification.
    # hd is trustworthy only because verify_oauth2_token checked Google's signature.
    if normalized.rsplit("@", 1)[1] != "gmail.com" and not _valid_hosted_domain(claims.get("hd")):
        raise InvalidIdentityToken("Invalid identity token")
    return subject, normalized


def _auth_error(status: int) -> HTTPException:
    headers = {"Cache-Control": "no-store"}
    if status == 401:
        headers["WWW-Authenticate"] = "Bearer"
    return HTTPException(
        status_code=status,
        detail={
            401: "Authentication required or invalid",
            403: "Administrator access denied",
            503: "Authentication unavailable",
        }[status],
        headers=headers,
    )


async def require_admin(
    request: Request,
    authorization: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> AdminPrincipal:
    if (
        authorization is None
        or authorization.scheme.lower() != "bearer"
        or len(authorization.credentials) > _MAX_TOKEN_LENGTH
        or not _TOKEN_PATTERN.fullmatch(authorization.credentials)
        or len(request.headers.getlist("authorization")) != 1
    ):
        raise _auth_error(401)
    settings = cast(Settings | None, getattr(request.app.state, "settings", None))
    verifier = cast(IdentityVerifier | None, getattr(request.app.state, "identity_verifier", None))
    if settings is None or not settings.google_client_id or not settings.admin_emails:
        raise _auth_error(503)
    if verifier is None:
        raise _auth_error(503)
    try:
        # The network work runs outside the event loop, with HTTP timeouts plus an
        # overall request deadline. A timed-out result is never used for admission.
        async with asyncio.timeout(settings.dependency_timeout_seconds * 3):
            claims = await run_in_threadpool(verifier.verify, authorization.credentials)
        subject, email = _validate_claims(claims, settings.google_client_id)
    except InvalidIdentityToken:
        raise _auth_error(401) from None
    except Exception:
        # Provider/library exceptions may contain claims or request details.
        raise _auth_error(503) from None
    if email not in settings.admin_emails:
        raise _auth_error(403)
    return AdminPrincipal(
        subject=subject,
        email=email,
        reviewer_professional_ids=tuple(settings.reviewer_assignments.get(email, [])),
    )
