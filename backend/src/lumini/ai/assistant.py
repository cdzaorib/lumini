"""Classifier and writer over an OpenAI-compatible model. Returns None on any doubt."""

import json
import uuid
from typing import Protocol

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from lumini.ai.client import AIUnavailable, ChatClient, Completion
from lumini.ai.contracts import Answer, AnswerRequest, Classification, ClassifyRequest
from lumini.ai.guardrails import safe_answer
from lumini.ai.redaction import leaks
from lumini.models import AICall
from lumini.settings import Settings

CLASSIFY_SYSTEM = (
    "Você classifica mensagens recebidas por uma clínica de estética. Responda só JSON: "
    '{"intent": "service_info|book|browse|human|health|other", "service_id": string ou null, '
    '"confidence": número de 0 a 1}. service_id deve ser um dos ids da lista fornecida, ou null. '
    "Use health para qualquer menção a saúde, gestação, medicamentos, doenças ou sintomas. Use "
    "human quando a pessoa quiser falar com alguém. Nunca invente procedimentos."
)
ANSWER_SYSTEM = (
    "Você explica procedimentos de uma clínica usando SOMENTE os fatos fornecidos, em português, "
    "em até 3 frases. Não diagnostique, não diga que o procedimento é adequado para a pessoa, "
    "não prometa resultados, não fale de riscos que não estejam nos fatos e não cite números "
    "que não estejam nos fatos. Siga as restrições fornecidas. Se os fatos não respondem, "
    'responda grounded=false. Responda só JSON: {"answer": string, "grounded": boolean}.'
)


class Assistant(Protocol):
    async def classify(
        self, session: AsyncSession | None, request: ClassifyRequest
    ) -> Classification | None: ...

    async def answer(self, session: AsyncSession | None, request: AnswerRequest) -> str | None: ...


class ModelAssistant:
    def __init__(self, client: ChatClient, classifier_model: str, writer_model: str) -> None:
        self._client = client
        self._classifier = classifier_model
        self._writer = writer_model

    async def _call(
        self,
        session: AsyncSession | None,
        purpose: str,
        model: str,
        system: str,
        user: str,
        tokens: int,
    ) -> Completion | None:
        try:
            completion = await self._client.complete(model, system, user, max_tokens=tokens)
        except AIUnavailable:
            await _account(session, purpose, model, "unavailable", None)
            return None
        await _account(session, purpose, model, "ok", completion)
        return completion

    async def classify(
        self, session: AsyncSession | None, request: ClassifyRequest
    ) -> Classification | None:
        if leaks(request.text):
            return None  # defense in depth: redaction must have run
        completion = await self._call(
            session,
            "classify",
            self._classifier,
            CLASSIFY_SYSTEM,
            request.model_dump_json(),
            120,
        )
        if completion is None:
            return None
        try:
            result = Classification.model_validate(completion.content)
        except ValidationError:
            await _account(session, "classify", self._classifier, "invalid", None)
            return None
        known = {service.id for service in request.services}
        if result.service_id is not None and result.service_id not in known:
            await _account(session, "classify", self._classifier, "invalid", None)
            return None
        return result

    async def answer(self, session: AsyncSession | None, request: AnswerRequest) -> str | None:
        if leaks(request.question):
            return None
        completion = await self._call(
            session, "answer", self._writer, ANSWER_SYSTEM, request.model_dump_json(), 300
        )
        if completion is None:
            return None
        try:
            result = Answer.model_validate(completion.content)
        except ValidationError:
            await _account(session, "answer", self._writer, "invalid", None)
            return None
        facts = json.dumps(request.facts.model_dump(), ensure_ascii=False)
        if not result.grounded or not safe_answer(result.answer, facts):
            await _account(session, "answer", self._writer, "blocked", None)
            return None
        return result.answer.strip()


async def _account(
    session: AsyncSession | None,
    purpose: str,
    model: str,
    outcome: str,
    completion: Completion | None,
) -> None:
    if session is None:  # offline benchmark: nothing to store
        return
    async with session.begin():
        session.add(
            AICall(
                id=uuid.uuid4(),
                purpose=purpose,
                model=model[:80],
                outcome=outcome,
                latency_ms=completion.latency_ms if completion else 0,
                prompt_tokens=completion.prompt_tokens if completion else None,
                completion_tokens=completion.completion_tokens if completion else None,
            )
        )


def build_assistant(settings: Settings) -> ModelAssistant | None:
    """Only when explicitly enabled after the minimization evaluation (ADR-007/018)."""
    if (
        not settings.ai_enabled
        or settings.ai_base_url is None
        or settings.ai_api_key is None
        or settings.ai_classifier_model is None
        or settings.ai_writer_model is None
    ):
        return None
    return ModelAssistant(
        ChatClient(settings.ai_base_url, settings.ai_api_key.get_secret_value()),
        settings.ai_classifier_model,
        settings.ai_writer_model,
    )
