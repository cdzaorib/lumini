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
from lumini.models import CatalogAuditEvent, Professional
from lumini.settings import Settings
from lumini.site.service import SITE_ENTITY_ID, approved_content, deposit_instructions
from tests.integration.test_booking_flow import NOW, professional

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
    async with session.begin():
        reviewer_id = await professional(session, schedule=False)
    session.info["site_reviewer_id"] = reviewer_id
    app = create_app(Settings(environment="test", media_origins=["https://media.example.invalid"]))
    app.state.clock = lambda: NOW

    async def bound() -> AsyncIterator[AsyncSession]:
        async with AsyncSession(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        ) as request_session:
            yield request_session

    async def staff() -> AdminPrincipal:
        return AdminPrincipal(
            subject="synthetic-staff",
            email="staff@example.invalid",
            reviewer_professional_ids=(reviewer_id,),
        )

    app.dependency_overrides[get_session] = bound
    app.dependency_overrides[require_admin] = staff
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://synthetic.test"
    ) as client:
        yield client, session
    await session.close()


def review_request(session: AsyncSession, revision: int = 1) -> dict[str, Any]:
    return {
        "expected_revision": revision,
        "professional_id": str(session.info["site_reviewer_id"]),
        "review_confirmed": True,
    }


async def approve_and_publish(
    client: AsyncClient, session: AsyncSession, revision: int = 1
) -> None:
    data = review_request(session, revision)
    reviewed = await client.post("/api/admin/site/approve", json=data)
    assert reviewed.status_code == 200, reviewed.text
    published = await client.post("/api/admin/site/publish", json=data)
    assert published.status_code == 200, published.text


async def test_content_requires_review_before_publication_and_hides_private_fields(
    http: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = http
    empty = (await client.get("/api/admin/site")).json()
    assert empty["revision"] == 0 and empty["content"]["faq"] == []
    saved = await client.put("/api/admin/site", json={"expected_revision": 0, "content": CONTENT})
    assert saved.status_code == 200, saved.text
    assert saved.json()["revision"] == 1 and saved.json()["content"]["whatsapp"] == "+5521999990000"
    assert saved.json()["status"] == "draft"
    stale = await client.put("/api/admin/site", json={"expected_revision": 0, "content": CONTENT})
    assert stale.status_code == 409

    pending = (await client.get("/api/public/site")).json()
    assert pending["faq"] == [] and pending["testimonials"] == [] and pending["whatsapp"] is None
    assert await deposit_instructions(session) is None
    premature = await client.post("/api/admin/site/publish", json=review_request(session))
    assert premature.status_code == 409
    await approve_and_publish(client, session)
    assert await deposit_instructions(session) == CONTENT["deposit_instructions"]

    public = await client.get("/api/public/site")
    assert public.status_code == 200 and public.headers["cache-control"] == "no-store"
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
    assert sorted(tuple(row) for row in audit) == [
        ("site", "site.approved", 1),
        ("site", "site.published", 1),
        ("site", "site.updated", 1),
    ]


async def test_staff_cannot_approve_another_professional_or_skip_confirmation(
    http: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = http
    await client.put("/api/admin/site", json={"expected_revision": 0, "content": CONTENT})
    data = review_request(session)
    data["review_confirmed"] = False
    assert (await client.post("/api/admin/site/approve", json=data)).status_code == 422

    async def staff() -> AdminPrincipal:
        return AdminPrincipal("synthetic-other", "other@example.invalid", ())

    client._transport.app.dependency_overrides[require_admin] = staff  # type: ignore[attr-defined]
    assert (
        await client.post("/api/admin/site/approve", json=review_request(session))
    ).status_code == 403
    assert (
        await client.post("/api/admin/site/publish", json=review_request(session))
    ).status_code == 403
    assert (await client.get("/api/public/site")).json()["faq"] == []


async def test_every_verified_professional_must_review_and_new_review_never_republishes(
    http: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = http
    await client.put("/api/admin/site", json={"expected_revision": 0, "content": CONTENT})
    await approve_and_publish(client, session)
    async with session.begin():
        second = await professional(session, schedule=False)
    assert (await client.get("/api/public/site")).json()["faq"] == []
    assert (
        await client.post("/api/admin/site/publish", json=review_request(session))
    ).status_code == 409

    async def second_reviewer() -> AdminPrincipal:
        return AdminPrincipal("synthetic-second", "second@example.invalid", (second,))

    client._transport.app.dependency_overrides[require_admin] = second_reviewer  # type: ignore[attr-defined]
    data = {**review_request(session), "professional_id": str(second)}
    review = await client.post("/api/admin/site/approve", json=data)
    assert review.status_code == 200 and review.json()["status"] == "approved"
    assert (await client.get("/api/public/site")).json()["faq"] == []
    assert (await client.post("/api/admin/site/publish", json=data)).status_code == 200
    assert (await client.get("/api/public/site")).json()["faq"] == CONTENT["faq"]


async def test_edits_withdrawal_and_credential_changes_revoke_site_and_bot_content(
    http: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = http
    content = {**CONTENT, "bot_texts": {"handoff": "A equipe vai continuar seu atendimento."}}
    await client.put("/api/admin/site", json={"expected_revision": 0, "content": content})
    await approve_and_publish(client, session)
    assert (await approved_content(session)).bot_texts == content["bot_texts"]
    saved = await client.put("/api/admin/site", json={"expected_revision": 1, "content": content})
    assert saved.status_code == 200 and saved.json()["status"] == "draft"
    assert (await client.get("/api/public/site")).json()["faq"] == []
    assert (await approved_content(session)).bot_texts == {} and await deposit_instructions(
        session
    ) is None
    assert (
        await client.post("/api/admin/site/approve", json=review_request(session))
    ).status_code == 409
    await approve_and_publish(client, session, 2)
    withdrawn = await client.post("/api/admin/site/unpublish", json={"expected_revision": 2})
    assert withdrawn.status_code == 200 and withdrawn.json()["status"] == "draft"
    assert (
        await client.post("/api/admin/site/publish", json=review_request(session, 2))
    ).status_code == 409
    await approve_and_publish(client, session, 2)
    async with session.begin():
        person = await session.get(Professional, session.info["site_reviewer_id"])
        assert person is not None
        person.revision += 1
        person.credentials_verified_at = None
    assert (await client.get("/api/public/site")).json()["faq"] == []
    assert await deposit_instructions(session) is None


async def test_photos_require_permitted_origin_and_authorization_is_never_public(
    http: tuple[AsyncClient, AsyncSession],
) -> None:
    client, session = http
    photo = {
        "url": "https://media.example.invalid/clinic.webp",
        "alt": "Recepção sintética da clínica",
        "width": 1200,
        "height": 800,
        "authorized_on": "2026-09-30",
        "authorization_confirmed": True,
    }
    content = {"photos": [{**photo, "url": "https://other.example.invalid/photo.webp"}]}
    await client.put("/api/admin/site", json={"expected_revision": 0, "content": content})
    blocked = await client.post("/api/admin/site/approve", json=review_request(session))
    assert blocked.status_code == 409 and "other.example" not in blocked.text
    content["photos"] = [photo]
    await client.put("/api/admin/site", json={"expected_revision": 1, "content": content})
    await approve_and_publish(client, session, 2)
    public = await client.get("/api/public/site")
    assert public.json()["photos"] == [
        {key: photo[key] for key in ("url", "alt", "width", "height")}
    ]
    assert "authorized_on" not in public.text and "authorization_confirmed" not in public.text


@pytest.mark.parametrize("target", ["publisher", "other"])
@pytest.mark.parametrize("operation", ["revoke", "update"])
async def test_real_professional_api_changes_cannot_restore_old_site_approval(
    http: tuple[AsyncClient, AsyncSession],
    target: str,
    operation: str,
) -> None:
    client, session = http
    first = session.info["site_reviewer_id"]
    async with session.begin():
        second = await professional(session, schedule=False)

    async def reviewer() -> AdminPrincipal:
        return AdminPrincipal("synthetic-reviewer", "reviewer@example.invalid", (first, second))

    client._transport.app.dependency_overrides[require_admin] = reviewer  # type: ignore[attr-defined]
    await client.put("/api/admin/site", json={"expected_revision": 0, "content": CONTENT})
    for professional_id in (first, second):
        response = await client.post(
            "/api/admin/site/approve",
            json={
                **review_request(session),
                "professional_id": str(professional_id),
            },
        )
        assert response.status_code == 200, response.text
    assert (
        await client.post("/api/admin/site/publish", json=review_request(session))
    ).status_code == 200
    changed_id = first if target == "publisher" else second
    if operation == "revoke":
        changed = await client.post(
            f"/api/admin/professionals/{changed_id}/revoke", json={"expected_revision": 1}
        )
    else:
        changed = await client.patch(
            f"/api/admin/professionals/{changed_id}",
            json={
                "expected_revision": 1,
                "display_name": "Nome sintético atualizado",
            },
        )
    assert changed.status_code == 200, changed.text
    assert (await client.get("/api/public/site")).json()["faq"] == []
    assert await deposit_instructions(session) is None
    restored = await client.post(
        f"/api/admin/professionals/{changed_id}/verify",
        json={
            "expected_revision": changed.json()["revision"],
        },
    )
    assert restored.status_code == 200, restored.text
    assert (await client.get("/api/public/site")).json()["faq"] == []
    assert (
        await client.post("/api/admin/site/publish", json=review_request(session))
    ).status_code == 409
    current = (await client.get("/api/admin/site")).json()
    assert current["status"] == "draft" and all(
        not item["approved"] for item in current["required_reviewers"]
    )
    for professional_id in (first, second):
        assert (
            await client.post(
                "/api/admin/site/approve",
                json={
                    **review_request(session),
                    "professional_id": str(professional_id),
                },
            )
        ).status_code == 200
    assert (await client.get("/api/public/site")).json()["faq"] == []
    assert (
        await client.post("/api/admin/site/publish", json=review_request(session))
    ).status_code == 200


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
