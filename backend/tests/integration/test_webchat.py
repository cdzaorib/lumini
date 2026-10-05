"""Website chat against PostgreSQL (rolled back), real Redis and a calendar double."""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from httpx2 import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from lumini.app import create_app
from lumini.booking.dispatch import tick
from lumini.deps import get_session
from lumini.models import Booking, Contact, Conversation, WhatsAppMessage
from lumini.resources import Resources
from lumini.settings import Settings
from lumini.webchat import router as webchat
from lumini.whatsapp import texts
from tests.booking_fakes import FakeCalendar
from tests.integration.test_booking_flow import NOW, TUESDAY, local, professional, published_service

pytestmark = pytest.mark.integration


@dataclass
class Chat:
    app: FastAPI
    http: AsyncClient
    session: AsyncSession
    now: list[datetime] = field(default_factory=lambda: [NOW])
    token: str = ""

    async def start(self) -> dict[str, Any]:
        response = await self.http.post("/api/public/chat/session")
        assert response.status_code == 201, response.text
        assert response.headers["cache-control"] == "no-store"
        body: dict[str, Any] = response.json()
        self.token = body["token"]
        return body

    async def say(self, text: str, token: str | None = None) -> Any:
        return await self.http.post(
            "/api/public/chat/messages",
            json={"text": text},
            headers={"Authorization": f"Bearer {token if token is not None else self.token}"},
        )

    async def reply(self, text: str) -> str:
        response = await self.say(text)
        assert response.status_code == 200, response.text
        replies: list[str] = response.json()["replies"]
        return replies[-1]


@pytest.fixture
async def chat(connection: AsyncConnection, integration_settings: Settings) -> AsyncIterator[Chat]:
    session = AsyncSession(
        bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    async with session.begin():
        person = await professional(session)
        await published_service(session, person)
    app = create_app(Settings(environment="test"))
    assert integration_settings.redis_url is not None
    redis = Redis.from_url(integration_settings.redis_url.get_secret_value(), decode_responses=True)
    app.state.resources = Resources(redis_client=redis)
    app.state.calendar = FakeCalendar()

    async def bound() -> AsyncIterator[AsyncSession]:
        async with AsyncSession(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        ) as request_session:
            yield request_session

    app.dependency_overrides[get_session] = bound
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://synthetic.test"
        ) as http:
            result = Chat(app, http, session)
            app.state.clock = lambda: result.now[0]
            yield result
    finally:
        async for key in redis.scan_iter("lumini:rl:*"):
            await redis.delete(key)
        await redis.aclose()
        await session.close()


async def test_session_starts_with_the_menu_and_stores_only_a_hash(chat: Chat) -> None:
    body = await chat.start()
    assert body["replies"] == [texts.MENU]
    assert body["options"] == [
        "Conhecer os procedimentos",
        "Agendar um horário",
        "Falar com a equipe",
    ]
    async with chat.session.begin():
        stored = await chat.session.scalar(select(Conversation.chat_id))
    assert stored is not None and stored.startswith("web:") and chat.token not in stored


async def test_bad_tokens_fail_before_the_database(chat: Chat) -> None:
    async def forbidden() -> AsyncIterator[AsyncSession]:
        raise AssertionError("database touched")
        yield  # pragma: no cover

    chat.app.dependency_overrides[get_session] = forbidden
    for token in ("", "short", "x" * 44, "a" * 42 + "!"):
        response = await chat.say("oi", token=token)
        assert response.status_code == 404 and response.json()["detail"] == {
            "code": "session_invalid"
        }


async def test_unknown_or_expired_sessions_are_refused(chat: Chat) -> None:
    assert (await chat.say("oi", token="A" * 43)).status_code == 404
    await chat.start()
    chat.now[0] = NOW + timedelta(hours=25)
    assert (await chat.say("oi")).status_code == 404


async def test_booking_from_the_website_asks_for_whatsapp_and_keeps_no_text(chat: Chat) -> None:
    await chat.start()
    for text in ("2", "1", "1", "2", "2"):
        await chat.reply(text)
    assert await chat.reply("1") == texts.ASK_NAME
    assert await chat.reply("Bia Sintética") == texts.ASK_PHONE
    assert await chat.reply("12345") == texts.BAD_PHONE
    summary = await chat.reply("(21) 97777-6666")
    assert (
        summary.startswith("Confirmando: Synthetic procedure")
        and "terça, 06/10, às 08:00" in summary
    )
    response = await chat.say("1")
    assert response.json() == {"replies": [texts.HOLD_REQUESTED], "options": []}
    async with chat.session.begin():
        booking = await chat.session.scalar(select(Booking))
        contact = await chat.session.scalar(select(Contact))
        conversation = await chat.session.scalar(select(Conversation))
        messages = await chat.session.scalar(select(func.count()).select_from(WhatsAppMessage))
    assert booking is not None and booking.starts_at == local(TUESDAY, 8)
    assert booking.idempotency_key.startswith("web:")  # origin shown in the metrics
    assert contact is not None and (contact.name, contact.phone_e164) == (
        "Bia Sintética",
        "+5521977776666",
    )
    assert conversation is not None and conversation.state == {"step": "menu"}
    assert messages == 0  # nothing the person typed is stored


async def test_health_and_team_requests_point_to_the_contact_form(chat: Chat) -> None:
    await chat.start()
    assert await chat.reply("estou grávida, posso?") == webchat.WEB_HEALTH_HANDOFF
    assert await chat.reply("quero falar com a equipe") == webchat.WEB_HANDOFF
    assert await chat.reply("1") != webchat.WEB_HANDOFF  # still served: no human mode on the web
    async with chat.session.begin():
        mode = await chat.session.scalar(select(Conversation.mode))
    assert mode == "bot"


async def test_floods_are_slowed(chat: Chat, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(webchat, "MESSAGE_LIMIT", 2)
    await chat.start()
    statuses = [(await chat.say("0")).status_code for _ in range(3)]
    assert statuses == [200, 200, 429]


async def test_abandoned_sessions_are_deleted_after_a_day(chat: Chat) -> None:
    await chat.start()
    await chat.reply("2")
    report = await tick(chat.session, calendar=None, notifier=None, now=NOW + timedelta(hours=23))
    assert report.purged_chats == 0
    report = await tick(chat.session, calendar=None, notifier=None, now=NOW + timedelta(hours=25))
    assert report.purged_chats == 1
