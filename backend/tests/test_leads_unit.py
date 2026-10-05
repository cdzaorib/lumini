"""Lead form input: Brazilian phones, required consent, no free text, bot trap."""

from typing import Any

import pytest
from pydantic import ValidationError

from lumini.leads.service import LeadCreate, brazilian_phone


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("(21) 99999-0000", "+5521999990000"),
        ("21 9999-0000", "+552199990000"),
        ("5521999990000", "+5521999990000"),
        ("+55 21 99999-0000", "+5521999990000"),
        ("+351 912 345 678", "+351912345678"),
    ],
)
def test_common_phone_writing_is_normalized(raw: str, expected: str) -> None:
    assert brazilian_phone(raw) == expected


@pytest.mark.parametrize("raw", ["99999-0000", "abc", "+0123", "1" * 20])
def test_phones_without_area_code_are_refused(raw: str) -> None:
    with pytest.raises(ValueError):
        brazilian_phone(raw)


def form(**changes: Any) -> dict[str, Any]:
    return {"name": "Ana Sintética", "phone": "(21) 99999-0000", "contact_consent": True, **changes}


def test_minimal_form_and_optional_marketing() -> None:
    lead = LeadCreate.model_validate(form())
    assert (lead.phone, lead.marketing_consent, lead.preferred_period) == (
        "+5521999990000",
        False,
        "any",
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"contact_consent": False},
        {"contact_consent": None},
        {"name": "A"},
        {"name": "<b>Ana</b>"},
        {"name": "Ana 123"},
        {"phone": "99999-0000"},
        {"message": "tenho uma condição de saúde"},  # free text is not accepted at all
        {"preferred_period": "night"},
    ],
)
def test_invalid_forms_are_refused_without_echo(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError) as caught:
        LeadCreate.model_validate(form(**changes))
    assert "99999" not in str(caught.value) and "saúde" not in str(caught.value)
