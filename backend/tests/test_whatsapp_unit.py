"""WhatsApp pieces without a database: payload reading, choices, texts, Evolution client."""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
import requests
from pydantic import SecretStr, ValidationError

from lumini.settings import Settings
from lumini.whatsapp import texts
from lumini.whatsapp.conversations import parse_messages
from lumini.whatsapp.evolution import (
    TIMEOUT,
    EvolutionClient,
    EvolutionConfig,
    WhatsAppRejected,
    WhatsAppUnavailable,
    build_sender,
)
from lumini.whatsapp.flow import choice, normalize
from lumini.whatsapp.notifier import phone_variants

NOW = datetime(2026, 10, 5, 12, tzinfo=UTC)


def message(jid: str, **changes: Any) -> dict[str, Any]:
    return {
        "key": {"remoteJid": jid, "fromMe": False, "id": "SYNTH0001"},
        "message": {"conversation": "  oi  "},
        "messageTimestamp": int(NOW.timestamp()) - 60,
        **changes,
    }


def test_personal_chats_are_read_and_groups_status_and_channels_ignored() -> None:
    [item] = parse_messages(
        [
            message("5521988887777@s.whatsapp.net"),
            message("120363000000000000@g.us"),
            message("status@broadcast"),
            message("120363000000000001@newsletter"),
            {"key": "broken"},
            "not a dict",
        ],
        now=NOW,
    )
    assert (item.chat_id, item.phone, item.text, item.from_me) == (
        "5521988887777@s.whatsapp.net",
        "+5521988887777",
        "oi",
        False,
    )
    assert item.occurred_at == NOW - timedelta(seconds=60)


def test_lid_chats_take_the_phone_from_alternate_fields_when_present() -> None:
    lid = message("123456789012345@lid")
    lid["key"]["senderPn"] = "5521977776666@s.whatsapp.net"
    [item] = parse_messages(lid, now=NOW)
    assert (item.chat_id, item.phone) == ("123456789012345@lid", "+5521977776666")
    [unknown] = parse_messages(message("123456789012345@lid"), now=NOW)
    assert unknown.phone is None


def test_text_variants_media_and_timestamps() -> None:
    extended = message(
        "5521988887777@s.whatsapp.net", message={"extendedTextMessage": {"text": "2"}}
    )
    media = message("5521988887777@s.whatsapp.net", message={"imageMessage": {}})
    future = message("5521988887777@s.whatsapp.net", messageTimestamp=int(NOW.timestamp()) + 999)
    garbage = message("5521988887777@s.whatsapp.net", messageTimestamp="not-a-number")
    long = message("5521988887777@s.whatsapp.net", message={"conversation": "x" * 5000})
    items = parse_messages([extended, media, future, garbage, long], now=NOW)
    assert [item.text for item in items[:2]] == ["2", None]
    assert items[2].occurred_at == NOW and items[3].occurred_at == NOW
    assert items[4].text is not None and len(items[4].text) == 2000


@pytest.mark.parametrize(
    ("text", "count", "expected"),
    [
        ("2", 3, 2),
        (" 2. ", 3, 2),
        ("2) Agendar", 3, 2),
        ("Opção 3", 3, 3),
        ("4", 3, None),
        ("0", 3, None),
        ("10:00", 12, None),
        ("quero o dois", 3, None),
    ],
)
def test_numbered_choices(text: str, count: int, expected: int | None) -> None:
    assert choice(text, count) == expected


def test_normalize_folds_accents_case_and_spaces() -> None:
    assert normalize("  Olá,   GRÁVIDA  ") == "ola, gravida"


def test_money_and_price_lines_in_brazilian_format() -> None:
    assert texts.money(Decimal("1234.5")) == "R$ 1.234,50"
    assert texts.money(Decimal("50")) == "R$ 50,00"
    assert texts.price_line("fixed", Decimal("200")) == "Valor: R$ 200,00."
    assert texts.price_line("from", Decimal("90")) == "A partir de R$ 90,00."
    assert texts.price_line("on_evaluation", None) == "O valor é definido após a avaliação."


def test_brazilian_mobiles_match_with_or_without_the_ninth_digit() -> None:
    assert phone_variants("+5521988887777") == ["+5521988887777", "+552188887777"]
    assert phone_variants("+552188887777") == ["+552188887777", "+5521988887777"]
    assert phone_variants("+14155550100") == ["+14155550100"]


@dataclass
class FakeRaw:
    data: bytes

    def read(self, amount: int, decode_content: bool = False) -> bytes:
        return self.data[:amount]


@dataclass
class FakeResponse:
    status_code: int
    raw: FakeRaw

    def close(self) -> None:
        pass


@dataclass
class FakeSession:
    response: FakeResponse | Exception
    calls: list[dict[str, Any]] = field(default_factory=list)

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def client(response: FakeResponse | Exception) -> tuple[EvolutionClient, FakeSession]:
    session = FakeSession(response)
    config = EvolutionConfig("https://evolution.synthetic.invalid", "lumini", "synthetic-key")
    return EvolutionClient(config, lambda: session), session  # type: ignore[arg-type,return-value]


async def test_send_returns_the_provider_id_without_redirects() -> None:
    body = b'{"key": {"remoteJid": "x@s.whatsapp.net", "fromMe": true, "id": "3EB0SYNTH"}}'
    evolution, session = client(FakeResponse(201, FakeRaw(body)))
    assert await evolution.send_text("5521988887777@s.whatsapp.net", "olá") == "3EB0SYNTH"
    [call] = session.calls
    assert call["url"] == "https://evolution.synthetic.invalid/message/sendText/lumini"
    assert call["json"] == {"number": "5521988887777@s.whatsapp.net", "text": "olá"}
    assert call["headers"]["apikey"] == "synthetic-key"
    assert (call["allow_redirects"], call["timeout"]) == (False, TIMEOUT)


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (FakeResponse(500, FakeRaw(b"SECRET PROVIDER TEXT")), WhatsAppUnavailable),
        (FakeResponse(429, FakeRaw(b"")), WhatsAppUnavailable),
        (FakeResponse(401, FakeRaw(b"SECRET PROVIDER TEXT")), WhatsAppRejected),
        (FakeResponse(400, FakeRaw(b"{}")), WhatsAppRejected),
        (FakeResponse(200, FakeRaw(b"{}")), WhatsAppUnavailable),  # no id: cannot match the echo
        (FakeResponse(200, FakeRaw(b"<html>")), WhatsAppUnavailable),
        (requests.ConnectionError("SECRET PROVIDER TEXT"), WhatsAppUnavailable),
    ],
)
async def test_send_failures_carry_fixed_codes_only(
    response: FakeResponse | Exception, expected: type[Exception]
) -> None:
    evolution, _ = client(response)
    with pytest.raises(expected) as caught:
        await evolution.send_text("5521988887777@s.whatsapp.net", "olá")
    assert type(caught.value) is expected
    assert "SECRET" not in str(caught.value) and caught.value.__cause__ is None


def configured(**changes: Any) -> Settings:
    values: dict[str, Any] = {
        "evolution_base_url": "https://evolution.synthetic.invalid/",
        "evolution_instance": "lumini",
        "evolution_api_key": SecretStr("synthetic-key"),
        "evolution_webhook_token": SecretStr("synthetic-evolution-webhook-token-0123456789"),
        **changes,
    }
    return Settings(**values)


def test_whatsapp_needs_all_four_settings() -> None:
    settings = configured()
    assert settings.whatsapp_configured() and settings.evolution_base_url == (
        "https://evolution.synthetic.invalid"
    )
    assert isinstance(build_sender(settings), EvolutionClient)
    assert build_sender(configured(evolution_api_key=None)) is None
    assert build_sender(Settings()) is None


@pytest.mark.parametrize(
    "changes",
    [
        {"evolution_base_url": "http://evolution.synthetic.invalid"},
        {"evolution_base_url": "https://user:pass@evolution.synthetic.invalid"},
        {"evolution_instance": "bad/instance"},
        {"evolution_webhook_token": SecretStr("short")},
    ],
)
def test_unsafe_whatsapp_settings_are_refused(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError) as caught:
        configured(**changes)
    assert "pass@" not in str(caught.value)
