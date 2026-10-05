"""Every admin route refuses anonymous calls; the public surface is exactly the reviewed list.

Black-box on purpose: it reads the OpenAPI document and calls each route, so it keeps working
whatever the framework does internally with routers.
"""

import re
import uuid
from typing import Any

from fastapi.testclient import TestClient

from lumini.app import create_app
from lumini.settings import Settings

# Reviewed public surface (docs/SEGURANCA.md). Adding a route here needs the same review.
PUBLIC = {
    ("GET", "/health/live"),
    ("GET", "/health/ready"),
    ("GET", "/api/catalog/services"),
    ("GET", "/api/public/site"),
    ("POST", "/api/public/leads"),
    ("POST", "/api/public/chat/session"),
    ("POST", "/api/public/chat/messages"),
    ("GET", "/api/public/booking"),
    ("GET", "/api/public/booking/availability"),
    ("POST", "/api/public/booking/cancel"),
    ("POST", "/api/public/booking/reschedule"),
    ("POST", "/api/webhooks/evolution"),
}


def _operations() -> list[tuple[str, str]]:
    schema: dict[str, Any] = create_app(Settings(environment="test")).openapi()
    return [
        (method.upper(), path)
        for path, methods in schema["paths"].items()
        for method in methods
        if method in ("get", "post", "put", "patch", "delete")
    ]


def test_every_admin_route_refuses_anonymous_calls() -> None:
    admin = [(method, path) for method, path in _operations() if path.startswith("/api/admin")]
    assert len(admin) > 25
    app = create_app(Settings(environment="test"))
    with TestClient(app, raise_server_exceptions=True) as client:
        for method, path in admin:
            concrete = re.sub(r"\{[^}]+\}", str(uuid.uuid4()), path)
            response = client.request(method, concrete, json={})
            assert response.status_code == 401, f"{method} {path} -> {response.status_code}"


def test_public_surface_is_exactly_the_reviewed_list() -> None:
    public = {(method, path) for method, path in _operations() if not path.startswith("/api/admin")}
    assert public == PUBLIC
