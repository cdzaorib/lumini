"""Model boundary without a provider: redaction, guardrails, client, assistant, benchmark."""

import json
from dataclasses import dataclass, field
from typing import Any

import pytest
import requests
from pydantic import SecretStr, ValidationError

from lumini.ai import benchmark
from lumini.ai.assistant import ModelAssistant, build_assistant
from lumini.ai.client import AIUnavailable, ChatClient, Completion
from lumini.ai.contracts import (
    AnswerRequest,
    Classification,
    ClassifyRequest,
    ServiceFacts,
    ServiceRef,
)
from lumini.ai.guardrails import safe_answer
from lumini.ai.redaction import MAX_CHARS, leaks, redact
from lumini.settings import Settings


@pytest.mark.parametrize(
    ("raw", "gone"),
    [
        ("meu zap é (21) 99999-0000", "99999"),
        ("liga 21999990000", "21999990000"),
        ("+55 21 98888-7777 por favor", "98888"),
        ("email ana.sintetica@example.com", "example.com"),
        ("cpf 123.456.789-09", "123.456"),
        ("cep 23860-000", "23860"),
        ("veja https://exemplo.invalid/x", "exemplo.invalid"),
        ("me acha no @ana.sintetica", "@ana"),
        ("pedido 1234567", "1234567"),
    ],
)
def test_redaction_removes_direct_identifiers(raw: str, gone: str) -> None:
    redacted = redact(raw)
    assert gone not in redacted and not leaks(redacted)


def test_redaction_keeps_meaning_and_bounds_length() -> None:
    assert redact("quero  limpeza de pele\n sexta 14h") == "quero limpeza de pele sexta 14h"
    assert len(redact("a" * 1000)) == MAX_CHARS


FACTS = "Limpeza de pele, duração 60 minutos, a partir de R$ 150,00"


@pytest.mark.parametrize(
    "answer",
    [
        "O resultado é garantido em 60 minutos.",
        "É um tratamento sem dor e sem riscos.",
        "É indicado para você, pode fazer tranquila.",
        "Leva 90 minutos.",  # number not in the approved facts
        "",
        "x" * 601,
    ],
)
def test_unsafe_or_ungrounded_answers_are_blocked(answer: str) -> None:
    assert not safe_answer(answer, FACTS)


def test_grounded_plain_answer_passes() -> None:
    assert safe_answer("A sessão dura cerca de 60 minutos; o valor parte de R$ 150,00.", FACTS)


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


def chat(
    body: dict[str, Any] | bytes | Exception, status: int = 200
) -> tuple[ChatClient, FakeSession]:
    response: FakeResponse | Exception = (
        body
        if isinstance(body, Exception)
        else FakeResponse(
            status, FakeRaw(body if isinstance(body, bytes) else json.dumps(body).encode())
        )
    )
    session = FakeSession(response)
    return ChatClient("https://ai.synthetic.invalid/v1", "synthetic-key", lambda: session), session  # type: ignore[arg-type,return-value]


def completion_body(content: dict[str, Any] | str, finish: str = "stop") -> dict[str, Any]:
    return {
        "choices": [
            {
                "message": {
                    "content": content if isinstance(content, str) else json.dumps(content)
                },
                "finish_reason": finish,
            }
        ],
        "usage": {"prompt_tokens": 120, "completion_tokens": 12},
    }


async def test_client_asks_for_deterministic_json_without_redirects() -> None:
    client, session = chat(completion_body({"intent": "browse", "confidence": 0.9}))
    result = await client.complete("synthetic-model", "system", "user", max_tokens=50)
    assert result.content == {"intent": "browse", "confidence": 0.9}
    assert (result.prompt_tokens, result.completion_tokens) == (120, 12)
    [call] = session.calls
    assert call["url"] == "https://ai.synthetic.invalid/v1/chat/completions"
    assert call["json"]["temperature"] == 0
    assert call["json"]["response_format"] == {"type": "json_object"}
    assert call["allow_redirects"] is False
    assert call["headers"]["Authorization"] == "Bearer synthetic-key"


@pytest.mark.parametrize(
    "body",
    [
        requests.ConnectionError("SECRET PROVIDER TEXT"),
        completion_body({"intent": "browse"}, finish="length"),
        completion_body("not json"),
        completion_body("[1, 2]"),
        {"unexpected": True},
    ],
)
async def test_client_failures_are_one_fixed_exception(body: Any) -> None:
    client, _ = chat(body)
    with pytest.raises(AIUnavailable) as caught:
        await client.complete("synthetic-model", "s", "u", max_tokens=10)
    assert "SECRET" not in str(caught.value)


async def test_client_http_errors_are_unavailable() -> None:
    client, _ = chat({"error": {"message": "SECRET"}}, status=429)
    with pytest.raises(AIUnavailable, match="http_429"):
        await client.complete("synthetic-model", "s", "u", max_tokens=10)


@dataclass
class ScriptedClient:
    replies: list[dict[str, Any] | Exception]
    prompts: list[str] = field(default_factory=list)

    async def complete(self, model: str, system: str, user: str, *, max_tokens: int) -> Completion:
        self.prompts.append(user)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return Completion(reply, 5, 10, 2)


SERVICES = [ServiceRef(id="svc-1", name="Limpeza de pele", category="Facial")]


def assistant(*replies: dict[str, Any] | Exception) -> tuple[ModelAssistant, ScriptedClient]:
    client = ScriptedClient(list(replies))
    return ModelAssistant(client, "classifier", "writer"), client  # type: ignore[arg-type]


async def test_classifier_accepts_only_known_services() -> None:
    model, _ = assistant({"intent": "service_info", "service_id": "svc-1", "confidence": 0.9})
    request = ClassifyRequest(text="quero limpeza", step="menu", services=SERVICES)
    assert await model.classify(None, request) == Classification(
        intent="service_info", service_id="svc-1", confidence=0.9
    )
    for reply in (
        {"intent": "book", "service_id": "svc-invented", "confidence": 0.99},
        {"intent": "diagnose", "confidence": 0.9},
        {"intent": "book", "confidence": 7},
        AIUnavailable("down"),
    ):
        model, _ = assistant(reply)
        assert await model.classify(None, request) is None


async def test_unredacted_text_never_leaves() -> None:
    model, client = assistant({"intent": "browse", "confidence": 0.9})
    request = ClassifyRequest(text="liga 21999990000", step="menu", services=SERVICES)
    assert await model.classify(None, request) is None
    assert client.prompts == []


FACT_MODEL = ServiceFacts(
    name="Limpeza de pele",
    description="Higienização profunda da pele.",
    objectives=["Remover impurezas"],
    audience="Pessoas que buscam cuidado facial",
    preparation=["Vir sem maquiagem"],
    aftercare=["Usar protetor solar"],
    human_guidance="Dúvidas de saúde com a profissional",
    duration_minutes=60,
    price_text="A partir de R$ 150,00.",
    restrictions=["Não prometer resultados"],
)


async def test_writer_output_is_used_only_when_grounded_and_safe() -> None:
    request = AnswerRequest(question="precisa vir sem maquiagem?", facts=FACT_MODEL)
    good = {
        "answer": "Sim, a orientação é vir sem maquiagem; a sessão dura 60 minutos.",
        "grounded": True,
    }
    model, client = assistant(good)
    assert await model.answer(None, request) == good["answer"]
    assert "Não prometer resultados" in client.prompts[0]  # restrictions guide the writer
    for reply in (
        {"answer": "Não sei.", "grounded": False},
        {"answer": "Resultado garantido!", "grounded": True},
        {"answer": "Dura 45 minutos.", "grounded": True},
        {"text": "missing fields"},
    ):
        model, _ = assistant(reply)
        assert await model.answer(None, request) is None


def test_models_stay_off_until_explicitly_enabled() -> None:
    configured: dict[str, Any] = {
        "ai_base_url": "https://ai.synthetic.invalid/v1",
        "ai_api_key": SecretStr("synthetic-key"),
        "ai_classifier_model": "synthetic-classifier",
        "ai_writer_model": "synthetic-writer",
    }
    assert build_assistant(Settings(**configured)) is None
    assert isinstance(build_assistant(Settings(ai_enabled=True, **configured)), ModelAssistant)
    assert build_assistant(Settings(ai_enabled=True)) is None
    with pytest.raises(ValidationError):
        Settings(ai_base_url="http://ai.synthetic.invalid")


@dataclass
class OracleAssistant:
    """Answers each benchmark case perfectly, to check the runner's bookkeeping."""

    seen: list[str] = field(default_factory=list)

    async def classify(self, session: Any, request: ClassifyRequest) -> Classification | None:
        self.seen.append(request.text)
        case = next(case for case in benchmark.CASES if redact(case.text) == request.text)
        kind, _, target = case.expected.partition(":")
        intent = {"info": "service_info", "book": "book"}.get(kind, kind)
        return Classification(intent=intent, service_id=target or None, confidence=0.95)  # type: ignore[arg-type]

    async def answer(self, session: Any, request: AnswerRequest) -> str | None:
        return None


async def test_benchmark_keeps_health_and_identifiers_away_from_the_model() -> None:
    oracle = OracleAssistant()
    report = await benchmark.run(oracle, benchmark.CASES, threshold=0.85)
    result = report.as_dict()
    assert result["total"] == len(benchmark.CASES)
    assert result["correct"] == len(benchmark.CASES), result["misses"]
    assert result["health_cases_reaching_model"] == 0
    assert result["identifier_leaks_after_redaction"] == 0
    assert not any("99999" in text or "@example" in text for text in oracle.seen)
    assert result["decided_locally"] == sum(
        case.expected.startswith("local_") for case in benchmark.CASES
    )
