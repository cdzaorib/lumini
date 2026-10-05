"""Panel-edited site content against PostgreSQL (rolled back)."""

from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from lumini.app import create_app
from lumini.auth import AdminPrincipal, require_admin
from lumini.deps import get_session
from lumini.models import CatalogAuditEvent
from lumini.settings import Settings
from lumini.site.service import SITE_ENTITY_ID
from tests.integration.test_booking_flow import NOW

pytestmark = pytest.mark.integration

CONTENT: dict[str, Any] = {
    "address": {"street": "Rua Sintética, 10", "city": "Mangaratiba - RJ"},
    "hours": ["Segunda a sexta, 9h às 18h"],
    "whatsapp": "(21) 99999-0000",
    "faq": [{"question": "Preciso de avaliação?", "answer": "Alguns procedimentos começam assim."}],
    "testimonials": [
        {
            "quote": "Fui muito bem atendida.",
            "author": "Cliente S.",
            "authorized_on": "2026-09-30",
            "authorization_confirmed": True,
        }
    ],
    "deposit_instructions": "Pix sintético: chave-ficticia-123",
}


@pytest.fixture
async def http(connection: AsyncConnection) -> AsyncIterator[tuple[AsyncClient, AsyncSession]]:
    session = AsyncSession(
        bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    app = create_app(Settings(environment="test"))
    app.state.clock = lambda: NOW

    async def bound() -> AsyncIterator[AsyncSession]:
        async with AsyncSession(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        ) as request_session:
            yield request_session

    async def staff() -> AdminPrincipal:
        return AdminPrincipal(
            subject="synthetic-staff", email="staff@example.invalid", reviewer_professional_ids=()
        )

    app.dependency_overrides[get_session] = bound
    app.dependency_overrides[require_admin] = staff
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://synthetic.test"
    ) as client:
        yield client, session
    await session.close()


async def test_content_is_versioned_audited_and_public_without_private_fields(
    http: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = http
    empty = (await client.get("/api/admin/site")).json()
    assert empty["revision"] == 0 and empty["content"]["faq"] == []
    saved = await client.put("/api/admin/site", json={"expected_revision": 0, "content": CONTENT})
    assert saved.status_code == 200, saved.text
    assert saved.json()["revision"] == 1 and saved.json()["content"]["whatsapp"] == "+5521999990000"
    stale = await client.put("/api/admin/site", json={"expected_revision": 0, "content": CONTENT})
    assert stale.status_code == 409

    public = await client.get("/api/public/site")
    assert public.status_code == 200 and "max-age=60" in public.headers["cache-control"]
    body = public.json()
    assert body["testimonials"] == [{"quote": "Fui muito bem atendida.", "author": "Cliente S."}]
    assert "deposit_instructions" not in body and "chave-ficticia" not in public.text
    assert "authorized_on" not in public.text

    async with session.begin():
        audit = (
            await session.execute(
                select(
                    CatalogAuditEvent.entity_type,
                    CatalogAuditEvent.action,
                    CatalogAuditEvent.revision,
                ).where(CatalogAuditEvent.target_id == SITE_ENTITY_ID)
            )
        ).all()
    assert [tuple(row) for row in audit] == [("site", "site.updated", 1)]


async def test_advertising_violations_are_refused_without_echo(
    http: tuple[AsyncClient, AsyncSession],
) -> None:
    client, _ = http
    response = await client.put(
        "/api/admin/site",
        json={
            "expected_revision": 0,
            "content": {"differentiators": ["Resultado garantido sempre"]},
        },
    )
    assert response.status_code == 422 and "sempre" not in response.text


async def test_anonymous_cannot_edit(http: tuple[AsyncClient, AsyncSession]) -> None:
    client, _ = http
    client._transport.app.dependency_overrides.pop(require_admin)  # type: ignore[attr-defined]
    assert (await client.put("/api/admin/site", json={})).status_code == 401
    assert (await client.get("/api/public/site")).status_code == 200
