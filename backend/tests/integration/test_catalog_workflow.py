"""Catalog HTTP workflows run against PostgreSQL and roll back every synthetic record."""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, create_async_engine

from lumini.app import create_app
from lumini.auth import AdminPrincipal, require_admin
from lumini.catalog.service import CATALOG_LOCK_KEY
from lumini.deps import get_session
from lumini.settings import Settings

pytestmark = pytest.mark.integration


@dataclass
class CatalogClient:
    app: FastAPI
    http: AsyncClient
    reviewer_ids: list[UUID] = field(default_factory=list)


@pytest.fixture
async def catalog(connection: AsyncConnection) -> AsyncIterator[CatalogClient]:
    app = create_app(Settings(environment="test"))

    async def session_override() -> AsyncIterator[AsyncSession]:
        async with AsyncSession(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        ) as session:
            yield session

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://synthetic.test"
    ) as http:
        client = CatalogClient(app=app, http=http)

        async def actor_override() -> AdminPrincipal:
            return AdminPrincipal(
                subject="synthetic-reviewer-subject",
                email="reviewer@example.invalid",
                reviewer_professional_ids=tuple(client.reviewer_ids),
            )

        app.dependency_overrides[get_session] = session_override
        app.dependency_overrides[require_admin] = actor_override
        yield client


async def professional(catalog: CatalogClient, *, verified: bool = True) -> dict[str, Any]:
    response = await catalog.http.post(
        "/api/admin/professionals",
        json={
            "display_name": "Synthetic professional",
            "category": "Synthetic category",
            "council_registration": "SYNTHETIC-ONLY-000",
        },
    )
    assert response.status_code == 201, response.text
    result: dict[str, Any] = response.json()
    catalog.reviewer_ids.append(UUID(result["id"]))
    if verified:
        response = await catalog.http.post(
            f"/api/admin/professionals/{result['id']}/verify",
            json={"expected_revision": result["revision"]},
        )
        assert response.status_code == 200, response.text
        result = response.json()
    return result


def service_payload(*professional_ids: str, **changes: Any) -> dict[str, Any]:
    return {
        "slug": f"synthetic-{uuid4()}",
        "name": "Synthetic procedure",
        "category": "synthetic-only",
        "description": "SYNTHETIC CLINICAL TEXT THAT MUST NOT ENTER AUDIT",
        "content": {
            "objectives": ["Synthetic objective"],
            "audience": "Synthetic audience pending professional assessment",
            "preparation": ["Synthetic approved preparation"],
            "aftercare": ["Synthetic approved aftercare"],
            "human_guidance": "Contact the synthetic professional for clinical questions",
            "price_kind": "on_evaluation",
            "communication_restrictions": ["SYNTHETIC INTERNAL RESTRICTION"],
        },
        "duration_minutes": 45,
        "buffer_minutes": 15,
        "booking_mode": "evaluation",
        "price_brl": None,
        "deposit_brl": "0.00",
        "professional_ids": list(professional_ids),
        **changes,
    }


async def service(catalog: CatalogClient, *ids: str, **changes: Any) -> dict[str, Any]:
    response = await catalog.http.post("/api/admin/services", json=service_payload(*ids, **changes))
    assert response.status_code == 201, response.text
    result: dict[str, Any] = response.json()
    return result


async def approve(
    catalog: CatalogClient, item: dict[str, Any], professional_id: str
) -> dict[str, Any]:
    response = await catalog.http.post(
        f"/api/admin/services/{item['id']}/approve",
        json={"expected_revision": item["revision"], "professional_id": professional_id},
    )
    assert response.status_code == 200, response.text
    result: dict[str, Any] = response.json()
    return result


async def published(catalog: CatalogClient, *professionals: dict[str, Any]) -> dict[str, Any]:
    item = await service(catalog, *(p["id"] for p in professionals))
    for person in professionals:
        item = await approve(catalog, item, person["id"])
    response = await catalog.http.post(
        f"/api/admin/services/{item['id']}/publish",
        json={"expected_revision": item["revision"]},
    )
    assert response.status_code == 200, response.text
    result: dict[str, Any] = response.json()
    return result


async def public_ids(catalog: CatalogClient) -> set[str]:
    response = await catalog.http.get("/api/catalog/services")
    assert response.status_code == 200, response.text
    return {item["id"] for item in response.json()}


async def test_complete_draft_is_hidden_until_human_approval_and_publication(
    catalog: CatalogClient,
) -> None:
    person = await professional(catalog)
    item = await service(catalog, person["id"])
    assert item["status"] == "draft"
    assert item["approvals"] == []
    assert item["id"] not in await public_ids(catalog)
    item = await approve(catalog, item, person["id"])
    assert item["status"] == "approved"
    assert item["id"] not in await public_ids(catalog)
    response = await catalog.http.post(
        f"/api/admin/services/{item['id']}/publish",
        json={"expected_revision": item["revision"]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "published"
    assert response.json()["revision"] == item["revision"]
    assert item["id"] in await public_ids(catalog)


async def test_public_catalog_identifies_professional_without_internal_review_data(
    catalog: CatalogClient,
) -> None:
    person = await professional(catalog)
    item = await published(catalog, person)
    response = await catalog.http.get("/api/catalog/services")
    [public] = [row for row in response.json() if row["id"] == item["id"]]
    # Nursing advertising must identify the professional (Cofen 554/2017).
    assert public["professionals"] == [
        {
            "id": person["id"],
            "display_name": "Synthetic professional",
            "category": "Synthetic category",
            "council_registration": "SYNTHETIC-ONLY-000",
        }
    ]
    assert "communication_restrictions" not in public["content"]
    for confidential in (
        "reviewer@example.invalid",
        "synthetic-reviewer-subject",
        "SYNTHETIC INTERNAL RESTRICTION",
        "approved_by",
        "approvals",
        "actor_subject",
        "credentials_verified",
        "revision",
    ):
        assert confidential not in response.text


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/api/admin/professionals"),
        ("patch", f"/api/admin/professionals/{uuid4()}"),
        ("post", f"/api/admin/professionals/{uuid4()}/verify"),
        ("post", f"/api/admin/professionals/{uuid4()}/revoke"),
        ("post", "/api/admin/services"),
        ("patch", f"/api/admin/services/{uuid4()}"),
        ("post", f"/api/admin/services/{uuid4()}/approve"),
        ("post", f"/api/admin/services/{uuid4()}/publish"),
        ("post", f"/api/admin/services/{uuid4()}/unpublish"),
    ],
)
async def test_anonymous_mutations_fail_before_opening_a_database_session(
    catalog: CatalogClient, method: str, path: str
) -> None:
    catalog.app.dependency_overrides.pop(require_admin)

    async def forbidden_database_access() -> AsyncIterator[AsyncSession]:
        raise AssertionError("Anonymous request accessed database")
        yield  # pragma: no cover

    catalog.app.dependency_overrides[get_session] = forbidden_database_access
    response = await catalog.http.request(method, path, json={})
    assert response.status_code == 401, response.text


async def test_complete_content_cannot_approve_with_unverified_credentials(
    catalog: CatalogClient,
) -> None:
    person = await professional(catalog, verified=False)
    item = await service(catalog, person["id"])
    response = await catalog.http.post(
        f"/api/admin/services/{item['id']}/approve",
        json={"expected_revision": item["revision"], "professional_id": person["id"]},
    )
    assert response.status_code == 409, response.text
    assert item["id"] not in await public_ids(catalog)


async def test_professional_cannot_be_verified_without_complete_credentials(
    catalog: CatalogClient,
) -> None:
    response = await catalog.http.post(
        "/api/admin/professionals", json={"display_name": "Synthetic incomplete professional"}
    )
    assert response.status_code == 201, response.text
    item = response.json()
    response = await catalog.http.post(
        f"/api/admin/professionals/{item['id']}/verify",
        json={"expected_revision": item["revision"]},
    )
    assert response.status_code == 409, response.text


async def test_reviewer_cannot_approve_for_unassigned_professional(catalog: CatalogClient) -> None:
    person = await professional(catalog)
    item = await service(catalog, person["id"])
    catalog.reviewer_ids.clear()
    response = await catalog.http.post(
        f"/api/admin/services/{item['id']}/approve",
        json={"expected_revision": item["revision"], "professional_id": person["id"]},
    )
    assert response.status_code == 403, response.text
    rows = (await catalog.http.get("/api/admin/services")).json()
    assert next(row for row in rows if row["id"] == item["id"])["approvals"] == []


async def test_all_associated_professionals_must_approve_same_revision(
    catalog: CatalogClient,
) -> None:
    first, second = await professional(catalog), await professional(catalog)
    item = await service(catalog, first["id"], second["id"])
    original_revision = item["revision"]
    item = await approve(catalog, item, first["id"])
    assert item["status"] == "draft"
    response = await catalog.http.post(
        f"/api/admin/services/{item['id']}/publish",
        json={"expected_revision": original_revision},
    )
    assert response.status_code == 409, response.text
    item = await approve(catalog, item, second["id"])
    assert item["status"] == "approved"
    assert item["revision"] == original_revision
    assert {row["professional_id"] for row in item["approvals"]} == {first["id"], second["id"]}
    response = await catalog.http.post(
        f"/api/admin/services/{item['id']}/publish",
        json={"expected_revision": original_revision},
    )
    assert response.status_code == 200, response.text


@pytest.mark.parametrize(
    "change",
    [
        {"description": "Edited synthetic description"},
        {"duration_minutes": 60},
        {"deposit_brl": "25.00"},
    ],
)
async def test_edit_revokes_publication_and_all_approvals(
    catalog: CatalogClient, change: dict[str, Any]
) -> None:
    person = await professional(catalog)
    item = await published(catalog, person)
    response = await catalog.http.patch(
        f"/api/admin/services/{item['id']}",
        json={"expected_revision": item["revision"], **change},
    )
    assert response.status_code == 200, response.text
    changed = response.json()
    assert changed["status"] == "draft"
    assert changed["approvals"] == []
    assert changed["approved_at"] is None
    assert changed["published_at"] is None
    assert changed["revision"] == item["revision"] + 1
    assert item["id"] not in await public_ids(catalog)


@pytest.mark.parametrize("operation", ["edit", "revoke"])
async def test_credentials_change_invalidates_every_linked_service(
    catalog: CatalogClient, operation: str
) -> None:
    person = await professional(catalog)
    items = [await published(catalog, person), await published(catalog, person)]
    if operation == "edit":
        response = await catalog.http.patch(
            f"/api/admin/professionals/{person['id']}",
            json={
                "expected_revision": person["revision"],
                "council_registration": "SYNTHETIC-CHANGED-001",
            },
        )
    else:
        response = await catalog.http.post(
            f"/api/admin/professionals/{person['id']}/revoke",
            json={"expected_revision": person["revision"]},
        )
    assert response.status_code == 200, response.text
    assert response.json()["credentials_verified_at"] is None
    assert not {item["id"] for item in items}.intersection(await public_ids(catalog))
    rows = (await catalog.http.get("/api/admin/services")).json()
    for item in items:
        current = next(row for row in rows if row["id"] == item["id"])
        assert current["status"] == "draft"
        assert current["approvals"] == []


async def test_stale_edit_is_rejected_without_lost_update(catalog: CatalogClient) -> None:
    item = await service(catalog)
    first = await catalog.http.patch(
        f"/api/admin/services/{item['id']}",
        json={"expected_revision": item["revision"], "name": "First synthetic update"},
    )
    assert first.status_code == 200, first.text
    stale = await catalog.http.patch(
        f"/api/admin/services/{item['id']}",
        json={"expected_revision": item["revision"], "name": "Stale synthetic update"},
    )
    assert stale.status_code == 409, stale.text
    rows = (await catalog.http.get("/api/admin/services")).json()
    current = next(row for row in rows if row["id"] == item["id"])
    assert current["name"] == "First synthetic update"
    assert current["revision"] == first.json()["revision"]


async def test_failed_association_edit_rolls_back_publication_and_content(
    catalog: CatalogClient,
) -> None:
    person = await professional(catalog)
    item = await published(catalog, person)
    response = await catalog.http.patch(
        f"/api/admin/services/{item['id']}",
        json={
            "expected_revision": item["revision"],
            "name": "This synthetic change must roll back",
            "professional_ids": [str(uuid4())],
        },
    )
    assert response.status_code in {404, 409}, response.text
    rows = (await catalog.http.get("/api/admin/services")).json()
    current = next(row for row in rows if row["id"] == item["id"])
    assert current == item
    assert item["id"] in await public_ids(catalog)


@pytest.mark.parametrize("forged_field", ["status", "approved_by"])
async def test_validation_errors_do_not_echo_sensitive_input(
    catalog: CatalogClient, forged_field: str
) -> None:
    marker = "SYNTHETIC-SECRET-DO-NOT-ECHO"
    response = await catalog.http.post(
        "/api/admin/services", json=service_payload(**{forged_field: marker})
    )
    assert response.status_code == 422, response.text
    assert marker not in response.text
    assert "SYNTHETIC CLINICAL TEXT" not in response.text


async def test_unpublish_requires_new_approval_before_republication(catalog: CatalogClient) -> None:
    person = await professional(catalog)
    item = await published(catalog, person)
    response = await catalog.http.post(
        f"/api/admin/services/{item['id']}/unpublish",
        json={"expected_revision": item["revision"]},
    )
    assert response.status_code == 200, response.text
    current = response.json()
    assert current["status"] == "draft"
    assert current["approvals"] == []
    response = await catalog.http.post(
        f"/api/admin/services/{item['id']}/publish",
        json={"expected_revision": current["revision"]},
    )
    assert response.status_code == 409, response.text
    assert item["id"] not in await public_ids(catalog)


async def test_audit_contains_actor_and_ids_without_clinical_text(
    catalog: CatalogClient, connection: AsyncConnection
) -> None:
    person = await professional(catalog)
    await published(catalog, person)
    # Table and field names are intentionally inspected independently from ORM serialization.
    table_result = await connection.execute(
        text(
            "SELECT tablename FROM pg_tables "
            "WHERE schemaname = 'public' AND tablename LIKE '%audit%'"
        )
    )
    tables = list(table_result.scalars())
    assert tables == ["catalog_audit_events"]
    records = await connection.execute(text("SELECT row_to_json(a) FROM catalog_audit_events AS a"))
    rows = list(records.scalars())
    assert rows
    rendered = str(rows)
    assert "synthetic-reviewer-subject" in rendered
    assert person["id"] in rendered
    assert "SYNTHETIC CLINICAL TEXT" not in rendered
    assert "Synthetic procedure" not in rendered
    assert "reviewer@example.invalid" not in rendered
    assert "SYNTHETIC-ONLY-000" not in rendered


async def test_catalog_mutation_holds_lock_until_its_transaction_ends(
    catalog: CatalogClient, integration_settings: Settings
) -> None:
    await professional(catalog)
    # The mutation's savepoint was released, but the transaction-level lock stays
    # with the still-open transaction; a concurrent administrator must wait.
    url = integration_settings.sqlalchemy_url()
    assert url is not None
    engine = create_async_engine(url, echo=False, hide_parameters=True)
    try:
        async with engine.connect() as other:
            acquired = await other.scalar(select(func.pg_try_advisory_xact_lock(CATALOG_LOCK_KEY)))
            await other.rollback()
    finally:
        await engine.dispose()
    assert acquired is False


async def test_unknown_professional_or_duplicate_slug_creates_nothing(
    catalog: CatalogClient,
) -> None:
    unknown = await catalog.http.post(
        "/api/admin/services", json=service_payload(str(uuid4()), slug="synthetic-unknown")
    )
    assert unknown.status_code == 409, unknown.text
    first = await service(catalog, slug="synthetic-duplicate")
    duplicate = await catalog.http.post(
        "/api/admin/services", json=service_payload(slug="synthetic-duplicate")
    )
    assert duplicate.status_code == 409, duplicate.text
    rows = (await catalog.http.get("/api/admin/services")).json()
    assert [
        row["id"] for row in rows if row["slug"] in {"synthetic-unknown", "synthetic-duplicate"}
    ] == [first["id"]]


@pytest.mark.parametrize(
    "changes",
    [
        {"description": None},
        {"duration_minutes": None},
        {"booking_mode": None},
        {"deposit_brl": None},
        {"price_brl": "100.00"},  # on_evaluation must not show a price
        {"price_brl": "50.00", "deposit_brl": "60.00", "content_price_kind": "fixed"},
        {"price_brl": None, "content_price_kind": "from"},
        {"content_objectives": []},
    ],
)
async def test_incomplete_or_inconsistent_content_cannot_be_approved(
    catalog: CatalogClient, changes: dict[str, Any]
) -> None:
    person = await professional(catalog)
    payload = service_payload(person["id"])
    for key, value in changes.items():
        if key.startswith("content_"):
            payload["content"][key.removeprefix("content_")] = value
        else:
            payload[key] = value
    response = await catalog.http.post("/api/admin/services", json=payload)
    assert response.status_code == 201, response.text
    item = response.json()
    response = await catalog.http.post(
        f"/api/admin/services/{item['id']}/approve",
        json={"expected_revision": item["revision"], "professional_id": person["id"]},
    )
    assert response.status_code == 409, response.text


async def test_fixed_price_with_lower_deposit_is_approvable(catalog: CatalogClient) -> None:
    person = await professional(catalog)
    item = await service(catalog, person["id"], price_brl="150", deposit_brl="50")
    assert (item["price_brl"], item["deposit_brl"]) == ("150.00", "50.00")
    item["content"]["price_kind"] = "fixed"
    response = await catalog.http.patch(
        f"/api/admin/services/{item['id']}",
        json={"expected_revision": item["revision"], "content": item["content"]},
    )
    assert response.status_code == 200, response.text
    assert (await approve(catalog, response.json(), person["id"]))["status"] == "approved"


async def test_unlinked_professional_cannot_approve(catalog: CatalogClient) -> None:
    linked, other = await professional(catalog), await professional(catalog)
    item = await service(catalog, linked["id"])
    response = await catalog.http.post(
        f"/api/admin/services/{item['id']}/approve",
        json={"expected_revision": item["revision"], "professional_id": other["id"]},
    )
    assert response.status_code == 409, response.text


async def test_repeated_approval_and_publication_are_idempotent(catalog: CatalogClient) -> None:
    person = await professional(catalog)
    item = await published(catalog, person)
    again = await approve(catalog, item, person["id"])
    assert again == item
    response = await catalog.http.post(
        f"/api/admin/services/{item['id']}/publish",
        json={"expected_revision": item["revision"]},
    )
    assert response.status_code == 200
    assert response.json() == item


async def test_draft_cannot_be_published_and_unknown_items_are_not_found(
    catalog: CatalogClient,
) -> None:
    person = await professional(catalog)
    item = await service(catalog, person["id"])
    response = await catalog.http.post(
        f"/api/admin/services/{item['id']}/publish", json={"expected_revision": 1}
    )
    assert response.status_code == 409
    for path in (
        f"/api/admin/services/{uuid4()}/publish",
        f"/api/admin/professionals/{uuid4()}/verify",
    ):
        response = await catalog.http.post(path, json={"expected_revision": 1})
        assert response.status_code == 404, response.text


async def test_unchanged_patch_keeps_revision_and_publication(catalog: CatalogClient) -> None:
    person = await professional(catalog)
    item = await published(catalog, person)
    response = await catalog.http.patch(
        f"/api/admin/services/{item['id']}",
        json={
            "expected_revision": item["revision"],
            "name": item["name"],
            "deposit_brl": "0",
            "professional_ids": item["professional_ids"],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json() == item
    response = await catalog.http.patch(
        f"/api/admin/professionals/{person['id']}",
        json={"expected_revision": person["revision"], "display_name": person["display_name"]},
    )
    assert response.status_code == 200
    assert response.json() == person
    assert item["id"] in await public_ids(catalog)
