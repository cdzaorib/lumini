"""Real SQL SELECT 1 and Redis PING through the app lifespan; no probe overrides."""

import pytest
from fastapi.testclient import TestClient

from lumini.app import create_app
from lumini.settings import Settings

pytestmark = pytest.mark.integration


def test_readiness_connects_to_real_test_services(integration_settings: Settings) -> None:
    with TestClient(create_app(integration_settings)) as client:
        assert client.get("/health/live").status_code == 200
        response = client.get("/health/ready")
        assert response.status_code == 200
        assert response.json() == {
            "status": "ready",
            "dependencies": {"postgresql": "ok", "redis": "ok"},
        }
