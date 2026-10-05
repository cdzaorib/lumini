"""OpenAI-compatible chat completions in JSON mode (DeepSeek and similar), blocking I/O in a
thread, short timeouts, no redirects, bounded responses. Provider text never leaves here."""

import asyncio
import json
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import requests

logger = logging.getLogger(__name__)

TIMEOUT = (3.05, 20.0)
MAX_RESPONSE_BYTES = 200_000


class AIUnavailable(Exception):
    """Any failure: network, quota, refusal, invalid JSON. Callers fall back; fixed code only."""


@dataclass(frozen=True)
class Completion:
    content: dict[str, Any]
    latency_ms: int
    prompt_tokens: int | None
    completion_tokens: int | None


class ChatClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        session_factory: Callable[[], requests.Session] = requests.Session,
    ) -> None:
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._key = api_key
        self._factory = session_factory
        self._local = threading.local()

    def _session(self) -> requests.Session:
        session: requests.Session | None = getattr(self._local, "session", None)
        if session is None:
            session = self._factory()
            self._local.session = session
        return session

    def _complete(self, model: str, system: str, user: str, max_tokens: int) -> Completion:
        started = time.monotonic()
        try:
            response = self._session().post(
                self._url,
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": 0,
                    "max_tokens": max_tokens,
                    "response_format": {"type": "json_object"},
                    "stream": False,
                },
                headers={"Authorization": f"Bearer {self._key}", "Accept": "application/json"},
                timeout=TIMEOUT,
                allow_redirects=False,
                stream=True,
            )
            try:
                raw = response.raw.read(MAX_RESPONSE_BYTES + 1, decode_content=True)
            finally:
                response.close()
        except requests.RequestException:
            raise _unavailable("network") from None
        if response.status_code != 200 or len(raw) > MAX_RESPONSE_BYTES:
            raise _unavailable(f"http_{response.status_code}")
        try:
            body = json.loads(raw)
            choice = body["choices"][0]
            if choice.get("finish_reason") not in (None, "stop"):
                raise _unavailable(f"finish_{choice.get('finish_reason')}"[:40])
            content = json.loads(choice["message"]["content"])
            usage = body.get("usage") or {}
        except AIUnavailable:
            raise
        except (ValueError, KeyError, IndexError, TypeError):
            raise _unavailable("invalid_response") from None
        if not isinstance(content, dict):
            raise _unavailable("invalid_response")
        return Completion(
            content=content,
            latency_ms=int((time.monotonic() - started) * 1000),
            prompt_tokens=usage.get("prompt_tokens") if isinstance(usage, dict) else None,
            completion_tokens=usage.get("completion_tokens") if isinstance(usage, dict) else None,
        )

    async def complete(self, model: str, system: str, user: str, *, max_tokens: int) -> Completion:
        return await asyncio.to_thread(self._complete, model, system, user, max_tokens)


def _unavailable(code: str) -> AIUnavailable:
    logger.warning("ai unavailable: %s", code)
    return AIUnavailable(code)
