import asyncio
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response

from lumini.app import create_app, get_resources
from lumini.resources import Resources, check_dependency
from lumini.settings import Settings


@dataclass
class SyntheticProbe:
    error: Exception | None = None
    calls: int = 0

    async def ping(self) -> None:
        self.calls += 1
        if self.error is not None:
            raise self.error


def test_liveness_does_not_depend_on_services_and_missing_readiness_is_503() -> None:
    with TestClient(create_app(Settings())) as client:
        live = client.get("/health/live")
        assert live.status_code == 200
        assert live.json() == {"status": "alive"}
        ready = client.get("/health/ready")
        assert ready.status_code == 503
        assert ready.headers["Cache-Control"] == "no-store"
        assert ready.json() == {
            "status": "not_ready",
            "dependencies": {"postgresql": "not_configured", "redis": "not_configured"},
        }


def test_readiness_only_succeeds_after_both_probes_succeed() -> None:
    database, redis = SyntheticProbe(), SyntheticProbe()
    app = create_app(Settings())
    app.dependency_overrides[get_resources] = lambda: Resources(database=database, redis=redis)
    with TestClient(app) as client:
        assert client.get("/health/live").status_code == 200
        assert database.calls == redis.calls == 0
        response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "dependencies": {"postgresql": "ok", "redis": "ok"},
    }
    assert database.calls == redis.calls == 1


@pytest.mark.parametrize("error_type", [ConnectionError, RuntimeError, ValueError])
def test_failed_probe_and_unexpected_error_never_leak_exception(
    error_type: type[Exception], caplog: pytest.LogCaptureFixture
) -> None:
    secret = "synthetic-secret-must-not-leak"
    app = create_app(Settings())
    app.dependency_overrides[get_resources] = lambda: Resources(
        database=SyntheticProbe(error_type(secret)), redis=SyntheticProbe()
    )
    with TestClient(app) as client:
        response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["dependencies"] == {"postgresql": "unavailable", "redis": "ok"}
    assert secret not in response.text
    assert secret not in caplog.text


async def test_slow_dependency_is_bounded() -> None:
    class SlowProbe:
        async def ping(self) -> None:
            await asyncio.sleep(60)

    async with asyncio.timeout(1):
        assert await check_dependency(SlowProbe(), 0.001) == "unavailable"


def test_production_does_not_expose_api_schema_or_documentation() -> None:
    with TestClient(create_app(Settings(environment="production"))) as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/openapi.json").status_code == 404
        assert client.post("/admin/services", json={}).status_code == 404


def preflight(client: TestClient, origin: str, method: str, headers: str = "") -> Response:
    request_headers = {"Origin": origin, "Access-Control-Request-Method": method}
    if headers:
        request_headers["Access-Control-Request-Headers"] = headers
    return client.options("/api/admin/me", headers=request_headers)


def test_cors_is_explicit_bearer_only_and_limited_to_admin_verbs() -> None:
    app = create_app(Settings(cors_origins=["http://localhost:3000"]))
    with TestClient(app) as client:
        allowed = client.get("/health/live", headers={"Origin": "http://localhost:3000"})
        rejected = client.get("/health/live", headers={"Origin": "https://untrusted.invalid"})
        write = preflight(client, "http://localhost:3000", "PATCH", "authorization,content-type")
        foreign = preflight(client, "https://untrusted.invalid", "POST", "authorization")
        delete = preflight(client, "http://localhost:3000", "DELETE")
        cookie = preflight(client, "http://localhost:3000", "POST", "cookie")
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "access-control-allow-origin" not in rejected.headers
    assert write.status_code == 200
    assert "access-control-allow-credentials" not in write.headers
    assert foreign.status_code == delete.status_code == cookie.status_code == 400
