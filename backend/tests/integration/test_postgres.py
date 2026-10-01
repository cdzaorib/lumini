"""Exercise actual PostgreSQL constraints with synthetic, always-rolled-back records."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from lumini.models import Professional, ProfessionalService, Service

pytestmark = pytest.mark.integration


def synthetic_service(**overrides: Any) -> dict[str, Any]:
    return {
        "id": uuid4(),
        "slug": f"synthetic-test-{uuid4()}",
        "name": "Synthetic procedure",
        "category": "synthetic-only",
        **overrides,
    }


async def test_catalog_defaults_and_valid_professional_association(
    connection: AsyncConnection,
) -> None:
    professional_id = uuid4()
    service = synthetic_service()
    await connection.execute(
        insert(Professional).values(id=professional_id, display_name="Synthetic professional")
    )
    result = await connection.execute(
        insert(Service).values(**service).returning(Service.__table__)
    )
    stored = result.mappings().one()
    assert stored["status"] == "draft"
    assert stored["buffer_minutes"] == 15
    assert stored["content"] == {}
    assert stored["approved_at"] is None
    assert stored["approved_by"] is None
    assert stored["published_at"] is None
    assert stored["price_brl"] is None
    assert stored["deposit_brl"] is None
    assert stored["created_at"].tzinfo is not None
    await connection.execute(
        insert(ProfessionalService).values(
            professional_id=professional_id, service_id=service["id"]
        )
    )
    relationship = await connection.execute(
        select(ProfessionalService.professional_id).where(
            ProfessionalService.service_id == service["id"]
        )
    )
    assert relationship.scalar_one() == professional_id


@pytest.mark.parametrize(
    ("overrides", "constraint_name"),
    [
        (
            {
                "status": "unknown",
                "approved_at": datetime(2026, 1, 1, tzinfo=UTC),
                "approved_by": "synthetic-reviewer",
            },
            "ck_services_status",
        ),
        ({"booking_mode": "unknown"}, "ck_services_booking_mode"),
        ({"duration_minutes": 0}, "ck_services_duration"),
        ({"buffer_minutes": -1}, "ck_services_buffer"),
        ({"price_brl": -1}, "ck_services_price"),
        ({"deposit_brl": -1}, "ck_services_deposit"),
        ({"status": "approved"}, "ck_services_approval"),
        ({"status": "approved", "approved_by": "synthetic-reviewer"}, "ck_services_approval"),
        (
            {
                "status": "approved",
                "approved_at": datetime(2026, 1, 1, tzinfo=UTC),
            },
            "ck_services_approval",
        ),
        (
            {
                "status": "published",
                "approved_at": datetime(2026, 1, 1, tzinfo=UTC),
                "approved_by": "synthetic-reviewer",
            },
            "ck_services_publication",
        ),
    ],
)
async def test_postgresql_rejects_invalid_catalog_state(
    connection: AsyncConnection, overrides: dict[str, Any], constraint_name: str
) -> None:
    with pytest.raises(IntegrityError) as caught:
        async with connection.begin_nested():
            await connection.execute(insert(Service).values(**synthetic_service(**overrides)))
    assert getattr(caught.value.orig, "sqlstate", None) == "23514"
    assert constraint_name in str(caught.value.orig)


@pytest.mark.parametrize("missing_target", ["professional", "service"])
async def test_postgresql_enforces_professional_service_foreign_keys(
    connection: AsyncConnection, missing_target: str
) -> None:
    professional_id = uuid4()
    service = synthetic_service()
    if missing_target != "professional":
        await connection.execute(
            insert(Professional).values(id=professional_id, display_name="Synthetic professional")
        )
    if missing_target != "service":
        await connection.execute(insert(Service).values(**service))
    with pytest.raises(IntegrityError) as caught:
        async with connection.begin_nested():
            await connection.execute(
                insert(ProfessionalService).values(
                    professional_id=professional_id, service_id=service["id"]
                )
            )
    assert getattr(caught.value.orig, "sqlstate", None) == "23503"
