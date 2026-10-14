"""Synthetic evaluation bookkeeping, writer safety and explicit fallback attempts."""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import pytest

from lumini.ai import benchmark, evaluation
from lumini.ai.assistant import FallbackAssistant, ModelAssistant, SplitAssistant
from lumini.ai.client import AIUnavailable, CallObservation
from lumini.ai.contracts import AnswerRequest, Classification, ClassifyRequest
from tests.test_ai import ScriptedClient, chat, completion_body


@dataclass
class WriterOracle:
    seen: list[str] = field(default_factory=list)

    async def classify(self, session: Any, request: ClassifyRequest) -> Classification | None:
        return None

    async def answer(self, session: Any, request: AnswerRequest) -> str | None:
        self.seen.append(request.question)
        question = request.question
        if "endereço" in question or "Ignore" in question:
            return None
        if "posterior" in question:
            return "O cuidado aprovado é usar protetor solar."
        if "dura" in question:
            return "A sessão dura 60 minutos."
        if "preço" in question:
            return "O preço parte de R$ 150,00."
        return "A orientação aprovada é vir sem maquiagem."


async def test_writer_benchmark_covers_facts_refusals_and_privacy() -> None:
    writer = WriterOracle()
    report = await evaluation.run_writer(writer)
    assert report["total"] == report["correct"] == len(evaluation.WRITER_CASES)
    assert report["refusals"] == 2
    assert report["unsafe_answers"] == 0
    assert report["identifier_leaks_after_redaction"] == 0
    assert report["decided_locally"] == 1
    assert not any("grávida" in text or "21999990000" in text for text in writer.seen)
    assert report["human_review_required"] is True


async def test_writer_benchmark_reports_unsafe_output_without_saving_it() -> None:
    client = ScriptedClient([{"answer": "Resultado garantido em 45 minutos.", "grounded": True}])
    writer = ModelAssistant(client, "synthetic", "synthetic")  # type: ignore[arg-type]
    cases = [evaluation.WriterCase("duration", "Quanto dura a sessão?", ("60",))]
    report = await evaluation.run_writer(writer, cases)
    assert report["refusals"] == 1 and report["correct"] == 0
    assert "garantido" not in str(report)


async def test_known_health_case_missed_by_local_guard_is_never_sent() -> None:
    writer = WriterOracle()
    report = await benchmark.run(
        writer,
        [benchmark.Case("mensagem sintética sem palavras-chave", "local_health")],
        threshold=0.85,
    )
    assert report.model_calls == 0 and report.health_unsafe == 1
    assert report.as_dict()["health_cases_reaching_model"] == 0
    assert report.as_dict()["health_local_guard_misses"] == 1


async def test_confidence_bands_are_measured_without_claiming_calibration() -> None:
    client = ScriptedClient([{"intent": "book", "service_id": "svc-massagem", "confidence": 0.7}])
    assistant = ModelAssistant(client, "synthetic", "synthetic")  # type: ignore[arg-type]
    report = await benchmark.run(
        assistant, [benchmark.CASES[2]], threshold=0.85, medium_threshold=0.6
    )
    assert report.confidence_bands == {"medium": {"total": 1, "correct": 1}}
    assert report.correct == 0  # medium-band route has not been approved for automatic action


async def test_explicit_fallback_records_both_attempts_and_never_auto_selects() -> None:
    totals = evaluation.CallTotals()
    primary_client = ScriptedClient([AIUnavailable("synthetic outage")])
    fallback_client = ScriptedClient([{"answer": "A sessão dura 60 minutos.", "grounded": True}])
    primary = ModelAssistant(primary_client, "primary", "primary", totals.record)  # type: ignore[arg-type]
    fallback = ModelAssistant(fallback_client, "fallback", "fallback", totals.record)  # type: ignore[arg-type]
    assistant = FallbackAssistant(primary, fallback)
    assert (
        await assistant.answer(None, AnswerRequest(question="Quanto dura?", facts=evaluation.FACTS))
        == "A sessão dura 60 minutos."
    )
    usage = totals.as_dict(
        {"primary": (Decimal("1"), Decimal("2")), "fallback": (Decimal("1"), Decimal("2"))}
    )
    assert usage["attempts"] == 2
    assert usage["calls_by_model"] == {"primary": 1, "fallback": 1}
    assert usage["attempts_without_usage"] == 1 and usage["cost_complete"] is False
    assert usage["input_tokens"] == 10 and usage["output_tokens"] == 2
    assert usage["known_usage_cost_usd"] == "0.000014"


async def test_split_assistant_does_not_use_writer_for_classification() -> None:
    classifier_client = ScriptedClient([{"intent": "browse", "confidence": 0.9}])
    writer_client = ScriptedClient([{"answer": "A sessão dura 60 minutos.", "grounded": True}])
    classifier = ModelAssistant(classifier_client, "classifier", "unused")  # type: ignore[arg-type]
    writer = ModelAssistant(writer_client, "unused", "writer")  # type: ignore[arg-type]
    assistant = SplitAssistant(classifier, writer)
    request = ClassifyRequest(text="quais serviços?", step="menu", services=[])
    assert await assistant.classify(None, request) is not None
    assert writer_client.prompts == []
    assert (
        await assistant.answer(None, AnswerRequest(question="Quanto dura?", facts=evaluation.FACTS))
        == "A sessão dura 60 minutos."
    )
    assert len(classifier_client.prompts) == len(writer_client.prompts) == 1


def test_numeric_comparison_leaves_provider_choice_to_review() -> None:
    report: dict[str, object] = {
        "schema_version": 1,
        "label": "synthetic-candidate",
        "synthetic_only": True,
        "classifier": {"correct": 1},
        "writer": {"correct": 1},
        "usage": {"attempts": 2},
    }
    comparison = evaluation.compare([report])
    assert comparison["automatic_selection"] is False
    with pytest.raises(ValueError):
        evaluation.compare([{"label": "incomplete"}])
    totals = evaluation.CallTotals([CallObservation("answer", "unknown-price", "ok", 12, 10, 2)])
    assert totals.as_dict()["known_usage_cost_usd"] is None
    assert totals.as_dict()["cost_complete"] is False


@pytest.mark.parametrize("value", ["-1", "NaN", "Infinity", "bad"])
def test_unverified_invalid_price_is_refused(value: str) -> None:
    import argparse

    with pytest.raises(argparse.ArgumentTypeError):
        evaluation.price(value)


async def test_provider_controlled_finish_reason_is_not_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, _ = chat(completion_body({}, finish="SECRET PROVIDER TEXT"))
    with pytest.raises(AIUnavailable, match="finish_incomplete"):
        await client.complete("synthetic-model", "s", "u", max_tokens=10)
    assert "SECRET" not in caplog.text


async def test_malformed_token_usage_is_unknown_not_added_to_cost() -> None:
    body = completion_body({"intent": "browse", "confidence": 0.9})
    body["usage"] = {"prompt_tokens": "SECRET", "completion_tokens": True}
    client, _ = chat(body)
    response = await client.complete("synthetic-model", "s", "u", max_tokens=10)
    assert response.prompt_tokens is response.completion_tokens is None
