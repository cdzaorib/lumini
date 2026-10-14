"""Official TypeSafe REST contract over a synthetic transport; no provider credentials."""

import copy
import json
from typing import Any

import pytest
import requests
from pydantic import SecretStr

from lumini.ai.assistant import ModelAssistant, SplitAssistant, build_assistant
from lumini.ai.client import AIUnavailable, CallObservation
from lumini.ai.contracts import ClassifyRequest, ServiceRef
from lumini.ai.jev import MAX_RESPONSE_BYTES, URL, JevClassifier, JevClient
from lumini.settings import Settings
from tests.test_ai import FakeRaw, FakeResponse, FakeSession

REQUEST = ClassifyRequest(
    text="quero marcar limpeza de pele",
    step="menu",
    services=[ServiceRef(id="svc-1", name="Limpeza de pele", category="Facial")],
)
INTENTS = ("service_info", "book", "browse", "human", "health", "other")


def response_body(intent: str = "book", service: str = "service:svc-1") -> dict[str, Any]:
    return {
        "model": "synthetic-resolved-model",
        "answers": {
            "intent": {
                "type": "choice",
                "choice": intent,
                "confidence": 0.93,
                "probabilities": {key: 0.9 if key == intent else 0.02 for key in INTENTS},
            },
            "service": {
                "type": "choice",
                "choice": service,
                "confidence": 0.82,
                "probabilities": {
                    "none": 0.05 if service != "none" else 0.95,
                    "service:svc-1": 0.95 if service != "none" else 0.05,
                },
            },
        },
        "usage": {"input_tokens": 120, "output_tokens": 12},
    }


def client(
    body: dict[str, Any] | bytes | Exception, status: int = 200
) -> tuple[JevClient, FakeSession]:
    response: FakeResponse | Exception = (
        body
        if isinstance(body, Exception)
        else FakeResponse(
            status, FakeRaw(body if isinstance(body, bytes) else json.dumps(body).encode())
        )
    )
    session = FakeSession(response)
    return JevClient("synthetic-key", lambda: session), session  # type: ignore[arg-type,return-value]


async def test_jev_uses_the_documented_typed_endpoint_and_real_confidence() -> None:
    provider, session = client(response_body())
    observations: list[CallObservation] = []
    classifier = JevClassifier(provider, "synthetic-alias", observations.append)
    result = await classifier.classify(None, REQUEST)
    assert result is not None
    assert (result.intent, result.service_id, result.confidence) == ("book", "svc-1", 0.82)
    [call] = session.calls
    assert call["url"] == URL
    assert call["headers"]["Authorization"] == "Bearer synthetic-key"
    assert call["allow_redirects"] is False and call["stream"] is True
    payload = call["json"]
    assert payload["model"] == "synthetic-alias"
    assert payload["state"] == {"text": REQUEST.text, "step": "menu"}
    assert set(payload["questions"]) == {"intent", "service"}
    assert payload["questions"]["intent"]["type"] == "choice"
    assert set(payload["questions"]["service"]["criteria"]) == {"none", "service:svc-1"}
    assert observations == [
        CallObservation(
            "classify", "synthetic-resolved-model", "ok", observations[0].latency_ms, 120, 12
        )
    ]


async def test_non_service_intent_uses_intent_confidence_and_ignores_service() -> None:
    provider, _ = client(response_body("browse"))
    result = await JevClassifier(provider, "synthetic-model").classify(None, REQUEST)
    assert result is not None
    assert (result.intent, result.service_id, result.confidence) == ("browse", None, 0.93)


async def test_ambiguous_service_is_not_inferred() -> None:
    provider, _ = client(response_body(service="none"))
    assert await JevClassifier(provider, "synthetic-model").classify(None, REQUEST) is None


@pytest.mark.parametrize(
    "field",
    [
        "unknown_intent",
        "unknown_service",
        "missing_question",
        "wrong_type",
        "nan_confidence",
        "string_confidence",
        "invalid_distribution",
        "missing_usage",
        "bool_tokens",
        "negative_tokens",
        "wrong_winner",
    ],
)
async def test_malformed_contract_fails_closed(field: str) -> None:
    body = copy.deepcopy(response_body())
    answer = body["answers"]["intent"]
    if field == "unknown_intent":
        answer["choice"] = "diagnose"
    elif field == "unknown_service":
        body["answers"]["service"]["choice"] = "service:invented"
    elif field == "missing_question":
        del body["answers"]["service"]
    elif field == "wrong_type":
        answer["type"] = "score"
    elif field == "nan_confidence":
        answer["confidence"] = float("nan")
    elif field == "string_confidence":
        answer["confidence"] = "0.9"
    elif field == "invalid_distribution":
        answer["probabilities"]["book"] = 0.1
    elif field == "missing_usage":
        del body["usage"]
    elif field == "bool_tokens":
        body["usage"]["input_tokens"] = True
    elif field == "negative_tokens":
        body["usage"]["input_tokens"] = -1
    elif field == "wrong_winner":
        answer["choice"] = "other"
    provider, _ = client(body)
    with pytest.raises(AIUnavailable, match="jev_invalid_response"):
        await provider.evaluate("synthetic-model", REQUEST)


@pytest.mark.parametrize("status", [401, 403, 422, 429, 529, 500, 307])
async def test_refusals_are_fixed_codes_with_no_provider_body(
    status: int, caplog: pytest.LogCaptureFixture
) -> None:
    provider, _ = client({"error": "SECRET PROVIDER CONTENT"}, status)
    assert await JevClassifier(provider, "synthetic-model").classify(None, REQUEST) is None
    assert f"jev_http_{status}" in caplog.text
    assert "SECRET" not in caplog.text


@pytest.mark.parametrize(
    "body",
    [
        b"invalid json",
        b"x" * (MAX_RESPONSE_BYTES + 1),
        requests.ConnectionError("SECRET NETWORK CONTENT"),
    ],
)
async def test_bounded_transport_refuses_failures_without_echoing_text(body: Any) -> None:
    provider, _ = client(body)
    with pytest.raises(AIUnavailable) as error:
        await provider.evaluate("synthetic-model", REQUEST)
    assert "SECRET" not in str(error.value)


@pytest.mark.parametrize(
    "text", ["meu telefone é 21999990000", "estou grávida", "quero falar com a equipe", "STOP"]
)
async def test_identifiers_and_local_routes_do_not_reach_jev(text: str) -> None:
    provider, transport = client(response_body())
    request = REQUEST.model_copy(update={"text": text})
    assert await JevClassifier(provider, "synthetic-model").classify(None, request) is None
    assert transport.calls == []


def test_build_separates_jev_from_writer_and_keeps_provider_off_by_default() -> None:
    values: dict[str, Any] = {
        "ai_classifier_provider": "jev",
        "jev_api_key": SecretStr("synthetic-jev-key"),
        "jev_model": "synthetic-jev-model",
        "ai_base_url": "https://ai.synthetic.invalid/v1",
        "ai_api_key": SecretStr("synthetic-writer-key"),
        "ai_writer_model": "synthetic-writer",
    }
    assert build_assistant(Settings(**values)) is None
    assert isinstance(build_assistant(Settings(ai_enabled=True, **values)), SplitAssistant)
    del values["jev_model"]
    assert build_assistant(Settings(ai_enabled=True, **values)) is None
    assert isinstance(
        build_assistant(
            Settings(
                ai_enabled=True,
                ai_classifier_model="synthetic-classifier",
                **{
                    key: value
                    for key, value in values.items()
                    if not key.startswith("jev") and key != "ai_classifier_provider"
                },
            )
        ),
        ModelAssistant,
    )
