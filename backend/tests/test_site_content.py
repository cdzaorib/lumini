"""Site content input: advertising rules, authorized testimonials, normalized contacts."""

from typing import Any

import pytest
from pydantic import ValidationError

from lumini.site.service import SiteContent


def test_full_content_is_accepted_and_normalized() -> None:
    content = SiteContent.model_validate(
        {
            "address": {"street": "Rua Sintética, 10", "city": "Mangaratiba - RJ"},
            "hours": ["Segunda a sexta, 9h às 18h"],
            "whatsapp": "(21) 99999-0000",
            "instagram": "lumini.sintetica",
            "differentiators": ["Atendimento individual e acolhedor"],
            "faq": [
                {
                    "question": "Preciso de avaliação?",
                    "answer": "Alguns procedimentos começam com avaliação.",
                }
            ],
            "testimonials": [
                {
                    "quote": "Fui muito bem atendida.",
                    "author": "Cliente S.",
                    "authorized_on": "2026-09-30",
                    "authorization_confirmed": True,
                }
            ],
            "deposit_instructions": "Pix sintético: chave-ficticia",
        }
    )
    assert content.whatsapp == "+5521999990000"


@pytest.mark.parametrize(
    "changes",
    [
        {"differentiators": ["Resultado garantido em uma sessão"]},
        {"differentiators": ["Tratamento definitivo"]},
        {"faq": [{"question": "Dói?", "answer": "É um procedimento sem dor."}]},
        {"differentiators": ["Veja nosso antes e depois"]},
        {
            "testimonials": [
                {
                    "quote": "Ótimo",
                    "author": "Cliente",
                    "authorized_on": "2026-09-30",
                    "authorization_confirmed": False,
                }
            ]
        },
        {"testimonials": [{"quote": "Ótimo", "author": "Cliente"}]},
        {"whatsapp": "99999-0000"},
        {"instagram": "not valid handle!"},
        {"address": {"street": "Rua", "city": "Cidade", "maps_url": "http://maps.invalid"}},
        {"differentiators": ["<script>x</script>"]},
        {"unknown": "field"},
    ],
)
def test_content_breaking_rules_is_refused(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        SiteContent.model_validate(changes)
