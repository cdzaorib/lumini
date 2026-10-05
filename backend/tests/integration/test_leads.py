"""Lead form and panel list against PostgreSQL (rolled back) and real Redis."""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from httpx2 import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from lumini.app import create_app
from lumini.auth import AdminPrincipal, require_admin
from lumini.booking.dispatch import tick
from lumini.deps import get_session
from lumini.leads import router as leads_router
from lumini.models import Lead
from lumini.resources import Resources
from lumini.settings import Settings
from tests.integration.test_booking_flow import NOW, professional, published_service

pytestmark = pytest.mark.integration


@dataclass
class Leads:
    app: FastAPI
    http: AsyncClient
    session: AsyncSession
    service_id: Any
    now: list[datetime] = field(default_factory=lambda: [NOW])

    async def submit(self, **changes: Any) -> int:
        body = {"name": "Ana Sintética", "phone": "(21) 99999-0000", "contact_consent": True}
        response = await self.http.post("/api/public/leads", json={**body, **changes})
        assert response.headers["cache-control"] == "no-store"
        return response.status_code

    async def stored(self) -> list[Lead]:
        async with self.session.begin():
            return list(
                await self.session.scalars(
                    select(Lead).execution_options(populate_existing=True).order_by(Lead.created_at)
                )
            )


@pytest.fixture
async def leads(
    connection: AsyncConnection, integration_settings: Settings
) -> AsyncIterator[Leads]:
    session = AsyncSession(
        bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    async with session.begin():
        professional_id = await professional(session)
        service_id = await published_service(session, professional_id)
    app = create_app(Settings(environment="test"))
    assert integration_settings.redis_url is not None
    redis = Redis.from_url(integration_settings.redis_url.get_secret_value(), decode_responses=True)
    app.state.resources = Resources(redis_client=redis)

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
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://synthetic.test"
        ) as http:
            result = Leads(app, http, session, service_id)
            app.state.clock = lambda: result.now[0]
            yield result
    finally:
        async for key in redis.scan_iter("lumini:rl:*"):
            await redis.delete(key)
        await redis.aclose()
        await session.close()


async def test_form_stores_minimal_data_with_consent_and_retention(leads: Leads) -> None:
    assert (
        await leads.submit(
            service_id=str(leads.service_id), preferred_period="morning", city="Mangaratiba"
        )
        == 201
    )
    [lead] = await leads.stored()
    assert (lead.name, lead.phone_e164, lead.city, lead.service_id) == (
        "Ana Sintética",
        "+5521999990000",
        "Mangaratiba",
        leads.service_id,
    )
    assert (lead.source, lead.status, lead.preferred_period) == ("site_form", "new", "morning")
    assert lead.contact_consent_at == NOW and lead.marketing_consent_at is None
    assert lead.retain_until == NOW + timedelta(days=90)


async def test_same_day_resubmission_refreshes_instead_of_duplicating(leads: Leads) -> None:
    await leads.submit()
    leads.now[0] = NOW + timedelta(hours=2)
    await leads.submit(marketing_consent=True, phone="+55 21 99999-0000")
    [lead] = await leads.stored()
    assert lead.marketing_consent_at == NOW + timedelta(hours=2)


async def test_bot_trap_and_unpublished_services(leads: Leads) -> None:
    assert await leads.submit(website="https://spam.invalid") == 201
    assert await leads.stored() == []
    from uuid import uuid4

    await leads.submit(service_id=str(uuid4()))
    [lead] = await leads.stored()
    assert lead.service_id is None


async def test_refused_forms_echo_nothing(leads: Leads) -> None:
    response = await leads.http.post(
        "/api/public/leads",
        json={"name": "Ana", "phone": "(21) 99999-0000", "contact_consent": False},
    )
    assert response.status_code == 422 and "99999" not in response.text


async def test_flood_from_one_address_is_slowed(
    leads: Leads, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(leads_router, "FORM_LIMIT", 2)
    assert [await leads.submit(phone=f"(21) 9999{n}-0000") for n in range(3)] == [201, 201, 429]


async def test_panel_lists_and_updates_leads(leads: Leads) -> None:
    await leads.submit(service_id=str(leads.service_id))
    [listed] = (await leads.http.get("/api/admin/leads")).json()
    assert (listed["service"], listed["phone"], listed["status"]) == (
        "Synthetic procedure",
        "+5521999990000",
        "new",
    )
    path = f"/api/admin/leads/{listed['id']}/status"
    assert (await leads.http.post(path, json={"status": "contacted"})).status_code == 204
    assert (await leads.http.get("/api/admin/leads")).json() == []
    assert len((await leads.http.get("/api/admin/leads?status=contacted")).json()) == 1
    assert (await leads.http.post(path, json={"status": "deleted"})).status_code == 422
    from uuid import uuid4

    missing = await leads.http.post(f"/api/admin/leads/{uuid4()}/status", json={"status": "new"})
    assert missing.status_code == 404


async def test_anonymous_cannot_read_leads(leads: Leads) -> None:
    leads.app.dependency_overrides.pop(require_admin)
    assert (await leads.http.get("/api/admin/leads")).status_code == 401


async def test_leads_not_converted_are_deleted_after_three_months(leads: Leads) -> None:
    await leads.submit()
    await leads.submit(phone="(21) 98888-0000")
    first, second = await leads.stored()
    await leads.http.post(f"/api/admin/leads/{second.id}/status", json={"status": "converted"})
    report = await tick(leads.session, calendar=None, notifier=None, now=NOW + timedelta(days=89))
    assert report.purged_leads == 0
    report = await tick(leads.session, calendar=None, notifier=None, now=NOW + timedelta(days=90))
    assert report.purged_leads == 1
    assert [lead.id for lead in await leads.stored()] == [second.id]
