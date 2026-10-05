"""Evolution API v2 client: only sending text. Provider text never leaves this module.

Assumptions to confirm in the PoC with a real instance (docs/DECISOES.md, ADR-017): the id in the
send response equals `key.id` of the echoed `messages.upsert` webhook, and Brazilian numbers are
accepted in E.164 digits (with or without the ninth digit).
"""

import asyncio
import json
import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

import requests

from lumini.settings import Settings

logger = logging.getLogger(__name__)

TIMEOUT = (3.05, 15.0)
MAX_RESPONSE_BYTES = 256_000


class WhatsAppUnavailable(Exception):
    """Transient (network, 5xx, 429, disconnected instance): retry later. Fixed code only."""


class WhatsAppRejected(Exception):
    """Permanent (invalid number, bad request, wrong credentials): a human must look."""


class WhatsAppSender(Protocol):
    async def send_text(self, chat_id: str, text: str) -> str:
        """Send and return the provider message id."""
        ...


@dataclass(frozen=True)
class EvolutionConfig:
    base_url: str
    instance: str
    api_key: str


class EvolutionClient:
    def __init__(
        self,
        config: EvolutionConfig,
        session_factory: Callable[[], requests.Session] = requests.Session,
    ) -> None:
        self._config = config
        self._factory = session_factory
        self._local = threading.local()

    def _session(self) -> requests.Session:
        session: requests.Session | None = getattr(self._local, "session", None)
        if session is None:
            session = self._factory()
            self._local.session = session
        return session

    def _send(self, chat_id: str, text: str) -> str:
        url = f"{self._config.base_url}/message/sendText/{self._config.instance}"
        try:
            response = self._session().post(
                url,
                json={"number": chat_id, "text": text},
                headers={"apikey": self._config.api_key, "Accept": "application/json"},
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
        status = response.status_code
        if status == 429 or status >= 500:
            raise _unavailable(f"http_{status}")
        if status in (401, 403):
            raise _rejected("credentials")
        if status not in (200, 201):
            raise _rejected(f"http_{status}")
        try:
            body: Any = json.loads(raw)
        except ValueError:
            raise _unavailable("invalid_response") from None
        key = body.get("key") if isinstance(body, dict) else None
        message_id = key.get("id") if isinstance(key, dict) else None
        if not isinstance(message_id, str) or not 1 <= len(message_id) <= 128:
            # Sent or not, we cannot recognize its echo: fail loudly instead of guessing.
            raise _unavailable("missing_message_id")
        return message_id

    async def send_text(self, chat_id: str, text: str) -> str:
        return await asyncio.to_thread(self._send, chat_id, text)


def _unavailable(code: str) -> WhatsAppUnavailable:
    logger.warning("whatsapp unavailable: %s", code)
    return WhatsAppUnavailable(code)


def _rejected(code: str) -> WhatsAppRejected:
    logger.warning("whatsapp rejected: %s", code)
    return WhatsAppRejected(code)


def build_sender(settings: Settings) -> EvolutionClient | None:
    base, instance, key = (
        settings.evolution_base_url,
        settings.evolution_instance,
        settings.evolution_api_key,
    )
    if base is None or instance is None or key is None or not settings.whatsapp_configured():
        return None
    return EvolutionClient(EvolutionConfig(base, instance, key.get_secret_value()))
