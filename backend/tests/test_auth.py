"""Offline Google ID-token verification with synthetic keys; no network or real accounts."""

import base64
import json
import time
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from lumini import auth
from lumini.app import create_app
from lumini.settings import Settings

CLIENT_ID = "123456789-synthetic.apps.googleusercontent.com"
KID = "synthetic-kid"
WORKSPACE_ADMIN = "admin@example.com"
GMAIL_ADMIN = "person@gmail.com"
REVIEWER_ID = uuid4()


@dataclass(frozen=True)
class SigningKey:
    private: rsa.RSAPrivateKey
    certificate_pem: str


def make_key() -> SigningKey:
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "synthetic-test-only")])
    now = datetime.now(UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(private.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=1))
        .sign(private, hashes.SHA256())
    )
    return SigningKey(private, certificate.public_bytes(serialization.Encoding.PEM).decode())


@pytest.fixture(scope="module")
def google_key() -> SigningKey:
    return make_key()


@pytest.fixture(scope="module")
def attacker_key() -> SigningKey:
    return make_key()


def _segment(data: Mapping[str, object]) -> str:
    raw = json.dumps(data, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def sign(key: SigningKey, claims: Mapping[str, object], kid: str = KID) -> str:
    message = f"{_segment({'alg': 'RS256', 'typ': 'JWT', 'kid': kid})}.{_segment(claims)}"
    signature = key.private.sign(message.encode(), padding.PKCS1v15(), hashes.SHA256())
    return f"{message}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"


def claims(**overrides: object) -> dict[str, object]:
    now = int(time.time())
    result: dict[str, object] = {
        "iss": "https://accounts.google.com",
        "aud": CLIENT_ID,
        "sub": "109876543210987654321",
        "email": WORKSPACE_ADMIN,
        "email_verified": True,
        "hd": "example.com",
        "iat": now - 5,
        "exp": now + 300,
    }
    result.update(overrides)
    return {key: value for key, value in result.items() if value is not None}


@dataclass
class FakeResponse:
    body: bytes
    status_code: int = 200
    headers: dict[str, str] = field(default_factory=lambda: {"Cache-Control": "max-age=300"})

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def iter_content(self, chunk_size: int) -> Iterator[bytes]:
        for start in range(0, len(self.body), chunk_size):
            yield self.body[start : start + chunk_size]


@dataclass
class CertificateServer:
    response: FakeResponse
    calls: list[dict[str, Any]] = field(default_factory=list)

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        return self.response


@pytest.fixture
def certificates(monkeypatch: pytest.MonkeyPatch, google_key: SigningKey) -> CertificateServer:
    server = CertificateServer(FakeResponse(json.dumps({KID: google_key.certificate_pem}).encode()))
    monkeypatch.setattr("requests.get", server.get)
    return server


def settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "google_client_id": CLIENT_ID,
        "admin_emails": [WORKSPACE_ADMIN, GMAIL_ADMIN],
        "reviewer_assignments": {WORKSPACE_ADMIN: [str(REVIEWER_ID)]},
        **overrides,
    }
    return Settings(**values)


@pytest.fixture
def app() -> FastAPI:
    return create_app(settings())


def me(app: FastAPI, token: str | None, scheme: str = "Bearer") -> Any:
    headers = {} if token is None else {"Authorization": f"{scheme} {token}"}
    with TestClient(app) as client:
        return client.get("/api/admin/me", headers=headers)


def test_google_signed_token_admits_allowlisted_admin(
    app: FastAPI, certificates: CertificateServer, google_key: SigningKey
) -> None:
    response = me(app, sign(google_key, claims()))
    assert response.status_code == 200, response.text
    assert response.json() == {
        "subject": "109876543210987654321",
        "email": WORKSPACE_ADMIN,
        "reviewer_professional_ids": [str(REVIEWER_ID)],
    }
    assert response.headers["Cache-Control"] == "no-store"
    [call] = certificates.calls
    assert call["url"] == "https://www.googleapis.com/oauth2/v1/certs"
    assert call["allow_redirects"] is False
    assert "headers" not in call  # the user's token is never forwarded to Google


def test_gmail_account_needs_no_hosted_domain(
    app: FastAPI, certificates: CertificateServer, google_key: SigningKey
) -> None:
    token = sign(google_key, claims(email=GMAIL_ADMIN.upper(), hd=None))
    response = me(app, token)
    assert response.status_code == 200, response.text
    assert response.json()["email"] == GMAIL_ADMIN
    assert response.json()["reviewer_professional_ids"] == []


@pytest.mark.parametrize(
    "overrides",
    [
        {"aud": "999-other.apps.googleusercontent.com"},
        {"iss": "https://accounts.example.invalid"},
        {"exp": int(time.time()) - 1},
        {"iat": int(time.time()) + 600, "exp": int(time.time()) + 900},
        {"nbf": int(time.time()) + 600},
        {"email_verified": False},
        {"email_verified": "true"},
        {"sub": None},
        {"email": None},
        {"hd": None},  # non-Gmail address without a Google-managed hosted domain
        {"email": "not-an-email"},
    ],
)
def test_invalid_claims_are_rejected_as_unauthenticated(
    app: FastAPI,
    certificates: CertificateServer,
    google_key: SigningKey,
    overrides: dict[str, object],
) -> None:
    response = me(app, sign(google_key, claims(**overrides)))
    assert response.status_code == 401, response.text
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize("kid", [KID, "unknown-kid"])
def test_token_signed_by_another_key_is_rejected(
    app: FastAPI, certificates: CertificateServer, attacker_key: SigningKey, kid: str
) -> None:
    assert me(app, sign(attacker_key, claims(), kid=kid)).status_code == 401


def test_tampered_payload_is_rejected(
    app: FastAPI, certificates: CertificateServer, google_key: SigningKey
) -> None:
    header, _, signature = sign(google_key, claims()).split(".")
    forged = _segment(claims(email=GMAIL_ADMIN, hd=None))
    assert me(app, f"{header}.{forged}.{signature}").status_code == 401


def test_valid_identity_outside_allowlist_is_forbidden(
    app: FastAPI, certificates: CertificateServer, google_key: SigningKey
) -> None:
    response = me(app, sign(google_key, claims(email="other@example.com")))
    assert response.status_code == 403
    assert "other@example.com" not in response.text


def test_allowlist_revocation_applies_to_the_next_request(
    app: FastAPI, certificates: CertificateServer, google_key: SigningKey
) -> None:
    token = sign(google_key, claims())
    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {token}"}
        assert client.get("/api/admin/me", headers=headers).status_code == 200
        app.state.settings = settings(admin_emails=[GMAIL_ADMIN], reviewer_assignments={})
        assert client.get("/api/admin/me", headers=headers).status_code == 403


@pytest.mark.parametrize(
    ("token", "scheme"),
    [(None, "Bearer"), ("a.b.c", "Basic"), ("not-a-jwt", "Bearer"), ("a.b.c" * 2000, "Bearer")],
)
def test_missing_or_malformed_credentials_never_reach_the_verifier(
    app: FastAPI, certificates: CertificateServer, token: str | None, scheme: str
) -> None:
    response = me(app, token, scheme)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert certificates.calls == []


@pytest.mark.parametrize(
    "configuration",
    [{"google_client_id": None}, {"admin_emails": [], "reviewer_assignments": {}}],
)
def test_unconfigured_authentication_fails_closed(
    certificates: CertificateServer, google_key: SigningKey, configuration: dict[str, Any]
) -> None:
    response = me(create_app(settings(**configuration)), sign(google_key, claims()))
    assert response.status_code == 503
    assert certificates.calls == []


@pytest.mark.parametrize(
    "response",
    [
        FakeResponse(b"{}", status_code=500),
        FakeResponse(b"", status_code=302, headers={"Location": "https://attacker.invalid"}),
        FakeResponse(b"not json"),
        FakeResponse(b'{"keys": []}'),
        FakeResponse(b"{}"),
        FakeResponse(b'{"kid": "' + b"x" * 300_000 + b'"}'),
    ],
)
def test_certificate_failures_are_unavailable_not_invalid_login(
    app: FastAPI,
    certificates: CertificateServer,
    google_key: SigningKey,
    response: FakeResponse,
) -> None:
    certificates.response = response
    assert me(app, sign(google_key, claims())).status_code == 503


def test_certificates_are_cached_only_as_long_as_google_allows(
    app: FastAPI, certificates: CertificateServer, google_key: SigningKey
) -> None:
    token = sign(google_key, claims())
    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {token}"}
        assert client.get("/api/admin/me", headers=headers).status_code == 200
        assert client.get("/api/admin/me", headers=headers).status_code == 200
        assert len(certificates.calls) == 1
    certificates.response.headers = {"Cache-Control": "no-store"}
    uncached = create_app(settings())
    with TestClient(uncached) as client:
        for _ in range(2):
            assert client.get("/api/admin/me", headers=headers).status_code == 200
    assert len(certificates.calls) == 3


def test_verifier_failures_do_not_echo_token_or_exception(
    app: FastAPI, caplog: pytest.LogCaptureFixture
) -> None:
    secret = "synthetic-provider-secret"

    class ExplodingVerifier:
        def verify(self, token: str) -> Mapping[str, object]:
            raise RuntimeError(f"{secret} {token}")

    app.state.identity_verifier = ExplodingVerifier()
    response = me(app, "header.payload.signature")
    assert response.status_code == 503
    assert secret not in response.text + caplog.text
    assert "payload" not in response.text + caplog.text


def test_certificate_request_only_fetches_google_certificates() -> None:
    request = auth._CertificateRequest(timeout_seconds=1)
    with pytest.raises(auth.IdentityProviderUnavailable):
        request("https://attacker.invalid/certs")


@pytest.mark.parametrize(
    ("headers", "ttl"),
    [
        ({"Cache-Control": "public, max-age=300"}, 300.0),
        ({"Cache-Control": "max-age=300", "Age": "100"}, 200.0),
        ({"Cache-Control": "max-age=999999"}, 3600.0),
        ({"Cache-Control": "no-store, max-age=300"}, 0.0),
        ({"Cache-Control": "max-age=nope"}, 0.0),
        ({}, 0.0),
    ],
)
def test_certificate_cache_ttl(headers: dict[str, str], ttl: float) -> None:
    assert auth._cache_ttl(headers) == ttl


def test_admin_identities_are_normalized_and_hidden_from_representation() -> None:
    configured = settings(admin_emails=[" Admin@Example.com ", WORKSPACE_ADMIN])
    assert configured.admin_emails == [WORKSPACE_ADMIN]
    assert WORKSPACE_ADMIN not in repr(configured)


@pytest.mark.parametrize("email", ["no-at-sign", "two@@example.com", "x@localhost", "a b@x.com"])
def test_invalid_admin_email_is_rejected_without_echo(email: str) -> None:
    with pytest.raises(ValidationError) as caught:
        settings(admin_emails=[email], reviewer_assignments={})
    assert email not in str(caught.value)


def test_reviewer_assignment_requires_allowlisted_administrator() -> None:
    with pytest.raises(ValidationError):
        settings(reviewer_assignments={"stranger@example.com": [str(REVIEWER_ID)]})


def test_admin_routes_without_database_are_unavailable_after_authentication(
    app: FastAPI,
) -> None:
    async def admin() -> auth.AdminPrincipal:
        return auth.AdminPrincipal("synthetic-subject", WORKSPACE_ADMIN, ())

    app.dependency_overrides[auth.require_admin] = admin
    with TestClient(app) as client:
        response = client.get("/api/admin/services")
    assert response.status_code == 503
    assert response.json() == {"detail": "Catalog unavailable"}


def test_malformed_json_error_does_not_echo_body(app: FastAPI) -> None:
    marker = "SYNTHETIC-CLINICAL-MARKER"
    with TestClient(app) as client:
        response = client.post(
            "/api/admin/professionals",
            content=f'{{"display_name": "{marker}"',
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code in {401, 422}
    assert marker not in response.text
