"""Site content input: advertising rules, authorized testimonials, normalized contacts."""

from typing import Any

import pytest
from pydantic import ValidationError

from lumini.site.service import SiteContent
from lumini.whatsapp import texts


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
        {"bot_texts": {"health_question": "O modelo pode avaliar sua saúde."}},
        {"bot_texts": {"hold_requested": "Seu agendamento está confirmado."}},
        {"bot_texts": {"menu": "Saudação sem as opções obrigatórias"}},
        {"bot_texts": {"reminder_2h": "{service.__class__} às {time} com {professional}"}},
        {"bot_texts": {"reminder_2h": "{service[0]} às {time} com {professional}"}},
        {"bot_texts": {"reminder_2h": "{service!r} às {time} com {professional}"}},
        {"bot_texts": {"reminder_2h": "{service:1000} às {time} com {professional}"}},
        {"bot_texts": {"reminder_2h": "{service} às {time} com {professional} {phone}"}},
    ],
)
def test_content_breaking_rules_is_refused(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        SiteContent.model_validate(changes)


PHOTO: dict[str, Any] = {
    "url": "https://media.example.invalid/clinic.webp",
    "alt": "Recepção sintética da clínica",
    "width": 1200,
    "height": 800,
    "authorized_on": "2026-09-30",
    "authorization_confirmed": True,
}


@pytest.mark.parametrize(
    "override",
    [
        {"url": "http://media.example.invalid/clinic.webp"},
        {"url": "https://media.example.invalid/clinic.webp?token=synthetic"},
        {"url": "https://media.example.invalid/clinic.webp#secret"},
        {"url": "https://user:synthetic@media.example.invalid/clinic.webp"},
        {"url": "https://localhost/clinic.webp"},
        {"alt": ""},
        {"width": True},
        {"width": 0},
        {"height": 10000},
        {"authorization_confirmed": False},
    ],
)
def test_invalid_photo_is_refused(override: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        SiteContent.model_validate({"photos": [{**PHOTO, **override}]})


def test_operational_placeholders_are_literal_and_safety_replies_stay_fixed() -> None:
    content = SiteContent.model_validate(
        {
            "photos": [PHOTO],
            "bot_texts": {
                "menu": "Bem-vinda ao atendimento da Lumini.\n{options}",
                "reminder_2h": "{service}, às {time}, com {professional}.",
            },
        }
    )
    menu = texts.customize_reply(texts.MENU, content.bot_texts)
    assert "Bem-vinda" in menu and "1. Conhecer os procedimentos" in menu
    assert texts.customize_reply(texts.HEALTH_HANDOFF, content.bot_texts) == texts.HEALTH_HANDOFF
    assert texts.customize_reply(texts.OPT_OUT, content.bot_texts) == texts.OPT_OUT
    assert (
        texts.operational(
            "reminder_2h",
            content.bot_texts,
            {
                "service": "Serviço {literal}",
                "time": "10:00",
                "professional": "Profissional sintética",
            },
        )
        == "Serviço {literal}, às 10:00, com Profissional sintética."
    )
