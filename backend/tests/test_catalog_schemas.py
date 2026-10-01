"""Untrusted clients cannot provide publication metadata or unsafe catalog values."""

from typing import Any
from uuid import uuid4

import pytest
from pydantic import ValidationError

from lumini.catalog.schemas import (
    ApprovalRequest,
    ProfessionalCreate,
    ProfessionalUpdate,
    ServiceCreate,
    ServiceUpdate,
    VersionRequest,
)


def service_input(**changes: Any) -> dict[str, Any]:
    return {
        "slug": "synthetic-procedure",
        "name": "Synthetic procedure",
        "category": "synthetic-only",
        **changes,
    }


@pytest.mark.parametrize(
    "field",
    ["status", "approved_by", "approved_at", "published_at", "revision", "approvals"],
)
def test_service_creation_cannot_forge_workflow_metadata(field: str) -> None:
    with pytest.raises(ValidationError):
        ServiceCreate.model_validate(service_input(**{field: "forged"}))


@pytest.mark.parametrize(
    "field", ["status", "approved_by", "approved_at", "published_at", "revision"]
)
def test_service_update_cannot_forge_workflow_metadata(field: str) -> None:
    with pytest.raises(ValidationError):
        ServiceUpdate.model_validate({"expected_revision": 1, field: "forged"})


@pytest.mark.parametrize("field", ["credentials_verified_at", "revision", "verified_by"])
def test_professional_creation_cannot_verify_its_own_credentials(field: str) -> None:
    with pytest.raises(ValidationError):
        ProfessionalCreate.model_validate({"display_name": "Synthetic professional", field: "x"})


def test_professional_update_cannot_verify_credentials() -> None:
    with pytest.raises(ValidationError):
        ProfessionalUpdate.model_validate(
            {"expected_revision": 1, "credentials_verified_at": "2026-01-01T00:00:00Z"}
        )


@pytest.mark.parametrize("value", [0, -1, True, 1.5])
def test_revision_is_a_positive_integer(value: object) -> None:
    with pytest.raises(ValidationError):
        VersionRequest.model_validate({"expected_revision": value})


@pytest.mark.parametrize("value", [-1, 0, 14, 15.5, True])
def test_minimum_buffer_is_fifteen_minutes(value: object) -> None:
    with pytest.raises(ValidationError):
        ServiceCreate.model_validate(service_input(buffer_minutes=value))


@pytest.mark.parametrize("field", ["price_brl", "deposit_brl"])
@pytest.mark.parametrize("value", ["-0.01", "NaN", "Infinity", "10.001", "100000000.00"])
def test_money_rejects_invalid_precision_range_and_nonfinite_values(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        ServiceCreate.model_validate(service_input(**{field: value}))


def test_zero_deposit_and_incomplete_draft_are_allowed() -> None:
    created = ServiceCreate.model_validate(service_input(deposit_brl="0.00"))
    assert created.buffer_minutes == 15
    assert created.deposit_brl is not None
    assert str(created.deposit_brl) in {"0.00", "0"}
    assert created.description is None


@pytest.mark.parametrize("field", ["description", "name"])
def test_catalog_fields_are_plain_text(field: str) -> None:
    with pytest.raises(ValidationError):
        ServiceCreate.model_validate(service_input(**{field: "<script>synthetic</script>"}))


def test_nested_clinical_content_is_plain_text() -> None:
    with pytest.raises(ValidationError):
        ServiceCreate.model_validate(
            service_input(content={"objectives": ["<strong>synthetic</strong>"]})
        )


def test_linked_professionals_cannot_be_duplicated() -> None:
    professional_id = str(uuid4())
    with pytest.raises(ValidationError):
        ServiceCreate.model_validate(service_input(professional_ids=[professional_id] * 2))


def test_approval_cannot_forge_actor() -> None:
    with pytest.raises(ValidationError):
        ApprovalRequest.model_validate(
            {
                "expected_revision": 1,
                "professional_id": str(uuid4()),
                "approved_by": "forged-subject",
            }
        )
