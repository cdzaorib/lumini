"""Synthetic benchmark for the classifier (plan §5, ADR-018). No real conversations.

Run against a configured provider with `python -m lumini.ai.benchmark` (needs LUMINI_AI_* in the
environment). Reports route accuracy per confidence band, health safety and identifier leaks.
Numbers only come from an actual run; nothing here is a measured result.
"""

import asyncio
import json
import sys
import time
from dataclasses import dataclass, field

from lumini.ai.assistant import Assistant, build_assistant
from lumini.ai.contracts import ClassifyRequest, ServiceRef
from lumini.ai.redaction import leaks, redact
from lumini.settings import Settings
from lumini.whatsapp.flow import local_route

CATALOG = [
    ServiceRef(id="svc-limpeza", name="Limpeza de pele", category="Estética facial"),
    ServiceRef(id="svc-drenagem", name="Drenagem linfática", category="Bem-estar"),
    ServiceRef(id="svc-massagem", name="Massagem relaxante", category="Bem-estar"),
    ServiceRef(id="svc-capilar", name="Avaliação capilar", category="Capilar"),
]


@dataclass(frozen=True)
class Case:
    text: str
    expected: str  # local_health | local_human | local_opt_out | browse | human | other |
    # info:<id> | book:<id>


CASES = [
    Case("quero saber como funciona a limpeza de pele", "info:svc-limpeza"),
    Case("vocês fazem drenagem?", "info:svc-drenagem"),
    Case("queria marcar uma massagem pra sexta", "book:svc-massagem"),
    Case("tem horário pra limpeza de pele essa semana?", "book:svc-limpeza"),
    Case("meu cabelo está caindo muito, vocês avaliam?", "info:svc-capilar"),
    Case("quais tratamentos vocês têm?", "browse"),
    Case("me manda a lista de procedimentos", "browse"),
    Case("bom dia, qual o endereço?", "other"),
    Case("quero falar com uma atendente", "local_human"),
    Case("estou grávida, posso fazer drenagem?", "local_health"),
    Case("tomo remédio para pressão alta", "local_health"),
    Case("tive uma cirurgia mês passado", "local_health"),
    Case("STOP", "local_opt_out"),
    Case("meu telefone é 21 99999-0000, me liga sobre a massagem", "book:svc-massagem"),
    Case("pode mandar no email ana.sintetica@example.com a lista?", "browse"),
]


@dataclass
class Report:
    total: int = 0
    correct: int = 0
    local: int = 0
    model_calls: int = 0
    failures: int = 0
    health_unsafe: int = 0
    leaks: int = 0
    latency_ms: list[int] = field(default_factory=list)
    misses: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        latencies = sorted(self.latency_ms)
        return {
            "total": self.total,
            "correct": self.correct,
            "decided_locally": self.local,
            "model_calls": self.model_calls,
            "model_failures": self.failures,
            "health_cases_reaching_model": self.health_unsafe,
            "identifier_leaks_after_redaction": self.leaks,
            "latency_ms_median": latencies[len(latencies) // 2] if latencies else None,
            "misses": self.misses,
        }


async def run(assistant: Assistant, cases: list[Case], *, threshold: float) -> Report:
    report = Report()
    for case in cases:
        report.total += 1
        local = local_route(case.text)
        if local is not None:
            report.local += 1
            got = f"local_{local}"
        else:
            if case.expected == "local_health":
                report.health_unsafe += 1  # would reach the model: keyword list too narrow
            redacted = redact(case.text)
            report.leaks += leaks(redacted)
            started = time.monotonic()
            result = await assistant.classify(
                None, ClassifyRequest(text=redacted, step="menu", services=CATALOG)
            )
            report.latency_ms.append(int((time.monotonic() - started) * 1000))
            report.model_calls += 1
            if result is None:
                report.failures += 1
                got = "failure"
            elif result.confidence < threshold:
                got = "other"
            elif result.intent == "service_info":
                got = f"info:{result.service_id}"
            elif result.intent == "book":
                got = f"book:{result.service_id}"
            else:
                got = result.intent
        if got == case.expected:
            report.correct += 1
        else:
            report.misses.append(f"{case.expected} -> {got}")
    return report


def main() -> None:  # pragma: no cover - needs a real provider
    settings = Settings()
    assistant = build_assistant(settings.model_copy(update={"ai_enabled": True}))
    if assistant is None:
        print("Configure LUMINI_AI_BASE_URL, LUMINI_AI_API_KEY and the model names first.")
        sys.exit(2)
    report = asyncio.run(run(assistant, CASES, threshold=settings.ai_high_confidence))
    print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":  # pragma: no cover
    main()
