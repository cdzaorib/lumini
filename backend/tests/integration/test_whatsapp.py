"""WhatsApp channel against PostgreSQL (rolled back) with fake Evolution sender and calendar."""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from httpx2 import ASGITransport, AsyncClient, Response
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from lumini.app import create_app
from lumini.auth import AdminPrincipal, require_admin
from lumini.booking.dispatch import deliver_due
from lumini.deps import get_sessions
from lumini.models import Booking, Contact, Conversation, OutboxJob, WhatsAppMessage
from lumini.settings import Settings
from lumini.whatsapp import texts
from lumini.whatsapp.conversations import (
    SEND_GRACE,
    parse_messages,
    record,
    retry_failed_replies,
    send_automatic,
    settle_unknown,
)
from lumini.whatsapp.evolution import WhatsAppRejected, WhatsAppUnavailable
from lumini.whatsapp.notifier import WhatsAppNotifier
from tests.booking_fakes import FakeCalendar
from tests.integration.test_booking_flow import (
    NOW,
    TUESDAY,
    World,
    held,
    local,
    professional,
    published_service,
)

pytestmark = pytest.mark.integration

TOKEN = "synthetic-evolution-webhook-token-0123456789"
INSTANCE = "lumini-synthetic"
CHAT = "5521988887777@s.whatsapp.net"
PHONE = "+5521988887777"


@dataclass
class FakeSender:
    sent: list[tuple[str, str, str]] = field(default_factory=list)  # chat, text, provider id
    unavailable: int = 0
    reject: bool = False
    during_send: Callable[[str], Awaitable[None]] | None = None
    counter: int = 0

    async def send_text(self, chat_id: str, text: str) -> str:
        if self.reject:
            raise WhatsAppRejected("synthetic")
        if self.unavailable > 0:
            self.unavailable -= 1
            raise WhatsAppUnavailable("synthetic")
        self.counter += 1
        message_id = f"BOTSYNTH{self.counter:06d}"
        if self.during_send is not None:
            await self.during_send(message_id)
        self.sent.append((chat_id, text, message_id))
        return message_id

    def texts(self) -> list[str]:
        return [text for _, text, _ in self.sent]


@dataclass
class Channelled:
    app: FastAPI
    http: AsyncClient
    world: World
    sender: FakeSender
    sessions: Callable[[], AbstractAsyncContextManager[AsyncSession]]
    now: list[datetime] = field(default_factory=lambda: [NOW])
    ids: int = 0

    def payload(
        self,
        text: str | None,
        *,
        from_me: bool = False,
        provider_id: str | None = None,
        chat: str = CHAT,
        at: datetime | None = None,
    ) -> dict[str, Any]:
        self.ids += 1
        message: dict[str, Any] = (
            {"conversation": text} if text is not None else {"imageMessage": {"caption": None}}
        )
        return {
            "event": "messages.upsert",
            "instance": INSTANCE,
            "data": {
                "key": {
                    "remoteJid": chat,
                    "fromMe": from_me,
                    "id": provider_id or f"SYNTHIN{self.ids:06d}",
                },
                "pushName": "Synthetic",
                "message": message,
                "messageType": "conversation",
                "messageTimestamp": int((at or self.now[0]).timestamp()),
            },
            "server_url": "https://evolution.synthetic.invalid",
        }

    async def post(self, body: dict[str, Any], token: str = TOKEN) -> Response:
        return await self.http.post(
            "/api/webhooks/evolution", json=body, headers={"Authorization": f"Bearer {token}"}
        )

    async def say(self, text: str | None, **options: Any) -> str:
        """Client message through the webhook; returns the bot's answer (if any)."""
        before = len(self.sender.sent)
        response = await self.post(self.payload(text, **options))
        assert response.status_code == 200, response.text
        new = self.sender.texts()[before:]
        return new[-1] if new else ""

    async def conversation(self) -> Conversation:
        async with self.sessions() as session, session.begin():
            found = await session.scalar(select(Conversation).where(Conversation.chat_id == CHAT))
        assert found is not None
        return found


@pytest.fixture
async def channel(connection: AsyncConnection) -> AsyncIterator[Channelled]:
    session = AsyncSession(
        bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    async with session.begin():
        professional_id = await professional(session)
        service_id = await published_service(session, professional_id)
        evaluation_id = await published_service(session, professional_id, booking_mode="evaluation")
    world = World(session, connection, FakeCalendar(), professional_id, service_id, evaluation_id)
    app = create_app(
        Settings(
            environment="test",
            evolution_base_url="https://evolution.synthetic.invalid",
            evolution_instance=INSTANCE,
            evolution_api_key=SecretStr("synthetic-evolution-api-key"),
            evolution_webhook_token=SecretStr(TOKEN),
            manage_link_secret=SecretStr("synthetic-manage-link-secret-0123456789"),
            public_site_url="https://synthetic.example",
        )
    )

    @asynccontextmanager
    async def bound() -> AsyncIterator[AsyncSession]:
        async with AsyncSession(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        ) as request_session:
            yield request_session

    async def staff() -> AdminPrincipal:
        return AdminPrincipal(
            subject="synthetic-staff", email="staff@example.invalid", reviewer_professional_ids=()
        )

    sender = FakeSender()
    app.dependency_overrides[get_sessions] = lambda: bound
    app.dependency_overrides[require_admin] = staff
    app.state.whatsapp = sender
    app.state.calendar = world.calendar
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://synthetic.test"
    ) as http:
        result = Channelled(app, http, world, sender, bound)
        app.state.clock = lambda: result.now[0]
        yield result
    await session.close()


async def test_webhook_refuses_unauthenticated_or_foreign_calls(channel: Channelled) -> None:
    def forbidden() -> Any:
        raise AssertionError("refused webhook touched the database")

    channel.app.dependency_overrides[get_sessions] = forbidden
    body = channel.payload("oi")
    assert (await channel.http.post("/api/webhooks/evolution", json=body)).status_code == 401
    assert (await channel.post(body, token="wrong-" + TOKEN)).status_code == 401
    assert (await channel.post({**body, "instance": "other"})).status_code == 403
    huge = await channel.http.post(
        "/api/webhooks/evolution",
        content=b"{" + b" " * 1_000_001 + b"}",
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
    )
    assert huge.status_code == 413
    broken = await channel.http.post(
        "/api/webhooks/evolution",
        content=b"not json",
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
    )
    assert broken.status_code == 400
    channel.app.state.settings = Settings(environment="test")
    assert (await channel.post(body)).status_code == 404
    assert channel.sender.sent == []


async def test_client_gets_the_menu_once_and_text_is_not_kept(channel: Channelled) -> None:
    body = channel.payload("Oi, tudo bem?")
    assert (await channel.post(body)).status_code == 200
    assert channel.sender.texts() == [texts.MENU]
    assert channel.sender.sent[0][0] == CHAT
    assert (await channel.post(body)).status_code == 200  # webhook retry: nothing new
    assert len(channel.sender.sent) == 1
    async with channel.sessions() as session, session.begin():
        kept = await session.scalar(
            select(func.count())
            .select_from(WhatsAppMessage)
            .where(WhatsAppMessage.body.is_not(None))
        )
        conversation = await session.scalar(select(Conversation))
    assert kept == 0
    assert conversation is not None and conversation.phone_e164 == PHONE


async def test_echo_of_our_own_message_keeps_the_bot_on(channel: Channelled) -> None:
    await channel.say("oi")
    our_id = channel.sender.sent[-1][2]
    await channel.post(channel.payload(texts.MENU, from_me=True, provider_id=our_id))
    assert (await channel.conversation()).mode == "bot"
    assert await channel.say("menu") == texts.MENU


async def test_echo_racing_the_send_response_is_still_recognized(channel: Channelled) -> None:
    async def echo_before_response(message_id: str) -> None:
        # Evolution may deliver the webhook before our send call returns.
        async with channel.sessions() as session:
            await record(
                session,
                parse_messages(
                    channel.payload("eco", from_me=True, provider_id=message_id)["data"],
                    now=channel.now[0],
                ),
                now=channel.now[0],
            )

    channel.sender.during_send = echo_before_response
    assert await channel.say("oi") == texts.MENU
    conversation = await channel.conversation()
    assert conversation.mode == "bot"
    async with channel.sessions() as session, session.begin():
        unknown = await session.scalar(
            select(func.count())
            .select_from(WhatsAppMessage)
            .where(WhatsAppMessage.origin == "unknown")
        )
    assert unknown == 0


async def test_staff_typing_while_the_bot_sends_pauses_it_as_soon_as_the_send_ends(
    channel: Channelled,
) -> None:
    async def staff_types_meanwhile(message_id: str) -> None:
        async with channel.sessions() as session:
            await record(
                session,
                parse_messages(
                    channel.payload("Oi, é a Michele!", from_me=True)["data"], now=channel.now[0]
                ),
                now=channel.now[0],
            )
        assert (await channel.conversation()).mode == "bot"  # undecided while we send

    channel.sender.during_send = staff_types_meanwhile
    assert await channel.say("oi") == texts.MENU
    conversation = await channel.conversation()
    assert (conversation.mode, conversation.mode_reason) == ("human", "manual_reply")


async def test_staff_reply_pauses_the_bot_until_staff_send_hash_bot(channel: Channelled) -> None:
    await channel.say("oi")
    await channel.post(channel.payload("Olá, aqui é a Munique!", from_me=True))
    conversation = await channel.conversation()
    assert (conversation.mode, conversation.mode_reason) == ("human", "manual_reply")
    assert await channel.say("quero agendar") == ""  # the team is talking
    assert await channel.say("#bot") == ""  # the client cannot switch the bot back on
    assert (await channel.conversation()).mode == "human"

    await channel.post(channel.payload("#bot", from_me=True))
    assert (await channel.conversation()).mode == "bot"
    assert await channel.say("oi") == texts.MENU


async def test_pause_command_from_the_clinic_phone(channel: Channelled) -> None:
    await channel.say("oi")
    await channel.post(channel.payload("#pausa", from_me=True))
    conversation = await channel.conversation()
    assert (conversation.mode, conversation.mode_reason) == ("human", "pause_command")


async def test_unrecognized_from_me_during_a_send_waits_then_counts_as_staff(
    channel: Channelled,
) -> None:
    await channel.say("oi")
    conversation = await channel.conversation()
    async with channel.sessions() as session, session.begin():
        session.add(
            WhatsAppMessage(
                conversation_id=conversation.id,
                dedupe_key="synthetic-in-flight",
                direction="out",
                origin="bot",
                purpose="reply",
                conversation_version=conversation.version,
                status="sending",
                occurred_at=channel.now[0],
            )
        )
    await channel.post(channel.payload("digitado no celular", from_me=True))
    assert (await channel.conversation()).mode == "bot"  # undecided yet
    async with channel.sessions() as session:
        blocked = await send_automatic(
            session,
            channel.sender,
            conversation.id,
            "automática",
            purpose="test",
            dedupe_key="synthetic-blocked",
            now=channel.now[0],
        )
        assert blocked == "skipped_wait"
        assert await settle_unknown(session, now=channel.now[0]) == 0  # within grace
        assert await settle_unknown(session, now=channel.now[0] + SEND_GRACE) == 1
    assert (await channel.conversation()).mode == "human"


async def test_whole_booking_through_whatsapp(channel: Channelled) -> None:
    assert await channel.say("Olá") == texts.MENU
    services = await channel.say("2")
    assert "Synthetic procedure" in services and services.startswith("Escolha o procedimento")
    detail = await channel.say("1")
    assert "Synthetic approved description" in detail and "avaliação" in detail
    assert await channel.say("1") == texts.HEALTH_QUESTION
    days = await channel.say("2")
    assert days.startswith("Escolha o dia") and "1. segunda, 05/10" in days
    times = await channel.say("2")  # Tuesday
    assert "terça, 06/10" in times and "1. 08:00" in times
    assert await channel.say("1") == texts.ASK_NAME
    summary = await channel.say("Maria Sintética")
    assert "terça, 06/10, às 08:00" in summary and "R$ 50,00" in summary
    assert await channel.say("1") == texts.HOLD_REQUESTED

    async with channel.sessions() as session, session.begin():
        booking = await session.scalar(select(Booking))
        contact = await session.scalar(select(Contact))
        conversation = await session.scalar(select(Conversation))
    assert booking is not None and booking.starts_at == local(TUESDAY, 8)
    assert contact is not None and (contact.phone_e164, contact.name) == (PHONE, "Maria Sintética")
    assert conversation is not None and "name" not in conversation.state

    async with channel.sessions() as session:
        notifier = WhatsAppNotifier(session, channel.sender, channel.app.state.settings, now=NOW)
        await deliver_due(session, calendar=channel.world.calendar, notifier=None, now=NOW)
        await deliver_due(session, calendar=None, notifier=notifier, now=NOW)
    messages = channel.sender.texts()
    assert any(text.startswith("Seu horário de Synthetic procedure") for text in messages)
    assert any(text.startswith("Sobre o sinal de R$ 50,00") for text in messages)
    assert all(chat == CHAT for chat, _, _ in channel.sender.sent)


@pytest.mark.parametrize("text", ["Estou grávida, posso fazer?", "tomo remédio para pressão alta"])
async def test_health_mentions_go_to_the_team_without_questions(
    channel: Channelled, text: str
) -> None:
    await channel.say("oi")
    assert await channel.say(text) == texts.HEALTH_HANDOFF
    conversation = await channel.conversation()
    assert (conversation.mode, conversation.mode_reason) == ("human", "health_condition")
    assert await channel.say("e então?") == ""


async def test_health_question_yes_and_requests_for_a_person_hand_off(channel: Channelled) -> None:
    for answer in ("Olá", "2", "1", "1"):
        await channel.say(answer)
    assert await channel.say("1") == texts.HEALTH_HANDOFF
    assert (await channel.conversation()).mode == "human"


async def test_asking_for_the_team_and_stop(channel: Channelled) -> None:
    await channel.say("oi")
    assert await channel.say("STOP") == texts.OPT_OUT
    conversation = await channel.conversation()
    assert conversation.marketing_opt_out_at is not None and conversation.mode == "bot"
    assert await channel.say("quero falar com uma atendente") == texts.HANDOFF
    assert (await channel.conversation()).mode_reason == "requested"


async def test_media_and_old_history_are_not_answered_blindly(channel: Channelled) -> None:
    assert await channel.say(None) == texts.NON_TEXT
    old = channel.now[0] - timedelta(hours=25)
    assert await channel.say("mensagem antiga", at=old) == ""


async def test_notifications_respect_human_mode(channel: Channelled) -> None:
    world = channel.world
    booking = await held(world, local(TUESDAY, 10), phone=PHONE)
    await channel.say("oi")
    await channel.post(channel.payload("Oi! Já te respondo.", from_me=True))
    async with channel.sessions() as session:
        notifier = WhatsAppNotifier(session, channel.sender, channel.app.state.settings, now=NOW)
        assert await notifier.send("hold_created", booking.id) == "human_mode"
    await channel.post(channel.payload("#bot", from_me=True))
    async with channel.sessions() as session:
        notifier = WhatsAppNotifier(session, channel.sender, channel.app.state.settings, now=NOW)
        assert await notifier.send("manage_link", booking.id) is None
        assert await notifier.send("manage_link", booking.id) is None  # once only
        assert await notifier.send("human_handoff", booking.id) is None
    link_messages = [text for text in channel.sender.texts() if "/reserva#" in text]
    assert len(link_messages) == 1
    conversation = await channel.conversation()
    assert (conversation.mode, conversation.mode_reason) == ("human", "booking_handoff")


async def test_outbox_records_why_a_notification_was_not_sent(channel: Channelled) -> None:
    world = channel.world
    booking = await held(world, local(TUESDAY, 10), phone=PHONE)
    await channel.say("oi")
    await channel.post(channel.payload("Oi! Aqui é a equipe.", from_me=True))
    async with channel.sessions() as session:
        notifier = WhatsAppNotifier(session, channel.sender, channel.app.state.settings, now=NOW)
        report = await deliver_due(session, calendar=None, notifier=notifier, now=NOW)
    assert report.skipped >= 1 and "human_mode" in report.notes
    async with channel.sessions() as session, session.begin():
        notes = set(
            await session.scalars(
                select(OutboxJob.last_error).where(
                    OutboxJob.booking_id == booking.id, OutboxJob.kind == "notification"
                )
            )
        )
    assert "human_mode" in notes


async def test_reply_lost_in_an_outage_is_resent_only_if_still_current(channel: Channelled) -> None:
    channel.sender.unavailable = 1
    assert await channel.say("oi") == ""
    async with channel.sessions() as session:
        assert await retry_failed_replies(session, channel.sender, now=NOW) == 1
    assert channel.sender.texts() == [texts.MENU]

    channel.sender.unavailable = 1
    await channel.say("2")  # fails
    channel.sender.unavailable = 1
    await channel.say("1")  # newer message, also fails: the first reply is now stale
    async with channel.sessions() as session:
        assert await retry_failed_replies(session, channel.sender, now=NOW) == 1
    assert len(channel.sender.sent) == 2


async def test_connection_state_is_shown_to_the_team(channel: Channelled) -> None:
    status = (await channel.http.get("/api/admin/integrations")).json()
    assert status["whatsapp"] == {
        "configured": True,
        "state": None,
        "needs_attention": True,
        "changed_at": None,
        "human_mode_conversations": 0,
    }
    assert status["calendar_configured"] is True and status["self_service_configured"] is True
    for event, data, state, attention in [
        ("connection.update", {"state": "open"}, "open", False),
        ("CONNECTION_UPDATE", {"state": "close", "statusReason": 401}, "close", True),
        ("qrcode.updated", {"qrcode": {"base64": "synthetic"}}, "qr_required", True),
        ("connection.update", {"state": "open"}, "open", False),
    ]:
        response = await channel.post({"event": event, "instance": INSTANCE, "data": data})
        assert response.status_code == 200
        whatsapp = (await channel.http.get("/api/admin/integrations")).json()["whatsapp"]
        assert (whatsapp["state"], whatsapp["needs_attention"]) == (state, attention)
    await channel.say("oi")
    await channel.post(channel.payload("equipe aqui", from_me=True))
    whatsapp = (await channel.http.get("/api/admin/integrations")).json()["whatsapp"]
    assert whatsapp["human_mode_conversations"] == 1


async def test_rejected_number_is_not_retried(channel: Channelled) -> None:
    channel.sender.reject = True
    assert await channel.say("oi") == ""
    channel.sender.reject = False
    async with channel.sessions() as session:
        assert await retry_failed_replies(session, channel.sender, now=NOW) == 0


async def test_logs_carry_no_phone_or_text(
    channel: Channelled, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level("DEBUG")
    channel.sender.unavailable = 1
    await channel.say("Meu segredo sintético 123")
    await channel.post(channel.payload("Mensagem da equipe sintética", from_me=True))
    logged = caplog.text
    assert (
        "988887777" not in logged and "segredo" not in logged and "equipe sintética" not in logged
    )


async def test_worker_answers_what_the_webhook_fast_path_missed(
    integration_settings: Settings,
) -> None:
    from sqlalchemy import delete
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from lumini.booking.jobs import run_tick

    url = integration_settings.sqlalchemy_url()
    assert url is not None
    engine = create_async_engine(url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    chat = "5521900000999@s.whatsapp.net"
    sender = FakeSender()
    try:
        async with sessions() as session:
            # Stored by the webhook, but the background reply never ran (process restarted).
            await record(
                session,
                parse_messages(
                    {
                        "key": {"remoteJid": chat, "fromMe": False, "id": "SYNTHWORKER01"},
                        "message": {"conversation": "oi"},
                        "messageTimestamp": int((NOW - timedelta(minutes=1)).timestamp()),
                    },
                    now=NOW - timedelta(minutes=1),
                ),
                now=NOW - timedelta(minutes=1),
            )
        report = await run_tick(
            integration_settings, calendar=None, sender=sender, clock=lambda: NOW
        )
        assert report is not None
        assert sender.sent == [(chat, texts.MENU, "BOTSYNTH000001")]
    finally:
        async with sessions() as session, session.begin():
            ids = select(Conversation.id).where(Conversation.chat_id == chat)
            await session.execute(
                delete(WhatsAppMessage).where(WhatsAppMessage.conversation_id.in_(ids))
            )
            await session.execute(delete(Conversation).where(Conversation.chat_id == chat))
        await engine.dispose()


@dataclass
class FakeAssistant:
    classification: Any = None
    answer_text: str | None = None
    questions: list[str] = field(default_factory=list)

    async def classify(self, session: Any, request: Any) -> Any:
        self.questions.append(request.text)
        return self.classification

    async def answer(self, session: Any, request: Any) -> str | None:
        self.questions.append(request.question)
        return self.answer_text


def classified(intent: str, service_id: Any, confidence: float) -> Any:
    from lumini.ai.contracts import Classification

    return Classification(
        intent=intent,  # type: ignore[arg-type]
        service_id=str(service_id) if service_id else None,
        confidence=confidence,
    )


async def test_free_text_is_routed_by_the_model_only_with_enough_confidence(
    channel: Channelled,
) -> None:
    service_id = channel.world.service_id
    model = FakeAssistant(classified("service_info", service_id, 0.95))
    channel.app.state.assistant = model
    await channel.say("oi")
    detail = await channel.say("queria saber da limpeza, me liga 21 99999-0000")
    assert detail.startswith("Synthetic procedure")
    assert all("99999" not in text for text in model.questions)  # redacted before leaving

    await channel.say("0")
    model.classification = classified("book", service_id, 0.7)  # medium: confirm first
    clarify = await channel.say("quero marcar aquele procedimento")
    assert clarify.startswith("Você está falando de Synthetic procedure?")
    assert await channel.say("1") == texts.HEALTH_QUESTION

    await channel.say("0")
    model.classification = classified("book", service_id, 0.4)  # low: deterministic path
    assert await channel.say("hmm talvez algo") == texts.NOT_UNDERSTOOD

    model.classification = classified("health", None, 0.9)
    assert await channel.say("uma dúvida sobre um problema") == texts.HEALTH_HANDOFF
    assert (await channel.conversation()).mode == "human"


async def test_questions_about_a_service_use_only_checked_wording(channel: Channelled) -> None:
    from lumini.whatsapp.flow import NOT_IN_FACTS

    model = FakeAssistant(answer_text="A orientação aprovada é vir sem maquiagem.")
    channel.app.state.assistant = model
    for text in ("oi", "1", "1"):
        await channel.say(text)
    reply = await channel.say("precisa ir sem maquiagem?")
    assert reply.startswith("A orientação aprovada é vir sem maquiagem.") and "1. Agendar" in reply
    model.answer_text = None  # blocked or not in the facts
    assert (await channel.say("e quanto tempo dura o efeito?")).startswith(NOT_IN_FACTS)


async def test_model_is_never_asked_during_numbered_booking_or_names(channel: Channelled) -> None:
    class Forbidden:
        async def classify(self, session: Any, request: Any) -> Any:
            raise AssertionError("model consulted")

        async def answer(self, session: Any, request: Any) -> Any:
            raise AssertionError("model consulted")

    channel.app.state.assistant = Forbidden()
    for text in ("Olá", "2", "1", "1", "2", "2", "1", "Maria Sintética"):
        assert await channel.say(text) != ""


async def test_model_calls_are_accounted_without_text(channel: Channelled) -> None:
    from lumini.ai.assistant import ModelAssistant
    from lumini.ai.client import AIUnavailable, Completion
    from lumini.models import AICall

    @dataclass
    class Scripted:
        replies: list[Any]

        async def complete(self, model: str, system: str, user: str, *, max_tokens: int) -> Any:
            reply = self.replies.pop(0)
            if isinstance(reply, Exception):
                raise reply
            return Completion(reply, 42, 300, 20)

    client = Scripted(
        [
            {
                "intent": "service_info",
                "service_id": str(channel.world.service_id),
                "confidence": 0.9,
            },
            AIUnavailable("synthetic"),
        ]
    )
    channel.app.state.assistant = ModelAssistant(client, "synthetic-classifier", "synthetic-writer")  # type: ignore[arg-type]
    await channel.say("oi")
    assert (await channel.say("conta da limpeza")).startswith("Synthetic procedure")
    await channel.say("0")
    assert await channel.say("outra coisa qualquer") == texts.NOT_UNDERSTOOD
    async with channel.sessions() as session, session.begin():
        rows = (
            await session.execute(
                select(AICall.purpose, AICall.model, AICall.outcome, AICall.prompt_tokens)
            )
        ).all()
    assert sorted(tuple(row) for row in rows) == [
        ("classify", "synthetic-classifier", "ok", 300),
        ("classify", "synthetic-classifier", "unavailable", None),
    ]
    assert set(AICall.__table__.columns.keys()) == {
        "id",
        "purpose",
        "model",
        "outcome",
        "latency_ms",
        "prompt_tokens",
        "completion_tokens",
        "created_at",
    }


async def test_deposit_instructions_require_explicit_site_review(channel: Channelled) -> None:
    from lumini.auth import AdminPrincipal
    from lumini.site.service import (
        SiteContent,
        SitePublish,
        SiteUpdate,
        approve_site,
        publish_site,
        put_site,
    )

    actor = AdminPrincipal("s", "s@example.invalid", (channel.world.professional_id,))

    booking = await held(channel.world, local(TUESDAY, 10), phone=PHONE)
    async with channel.sessions() as session:
        notifier = WhatsAppNotifier(session, channel.sender, channel.app.state.settings, now=NOW)
        assert await notifier.send("deposit_instructions", booking.id) is None
    assert channel.sender.texts()[-1].startswith("Sobre o sinal de R$ 50,00: a equipe")

    other = await held(channel.world, local(TUESDAY, 15), phone=PHONE)
    async with channel.sessions() as session:
        await put_site(
            session,
            actor,
            SiteUpdate(
                expected_revision=0,
                content=SiteContent(deposit_instructions="Pix sintético: chave-ficticia-123"),
            ),
            now=NOW,
        )
        notifier = WhatsAppNotifier(session, channel.sender, channel.app.state.settings, now=NOW)
        assert await notifier.send("deposit_instructions", other.id) is None
    last = channel.sender.texts()[-1]
    assert "chave-ficticia" not in last and last.startswith("Sobre o sinal")
    async with channel.sessions() as session:
        review = SitePublish(
            expected_revision=1,
            professional_id=channel.world.professional_id,
            review_confirmed=True,
        )
        await approve_site(session, actor, review, now=NOW, media_origins=[])
        await publish_site(session, actor, review, now=NOW, media_origins=[])
    final = await held(channel.world, local(TUESDAY, 18), phone=PHONE)
    async with channel.sessions() as session:
        notifier = WhatsAppNotifier(session, channel.sender, channel.app.state.settings, now=NOW)
        assert await notifier.send("deposit_instructions", final.id) is None
    last = channel.sender.texts()[-1]
    assert "chave-ficticia-123" in last and "comprovante não confirma sozinho" in last


async def test_only_published_operational_copy_is_used_and_guardrails_stay_fixed(
    channel: Channelled,
) -> None:
    from lumini.auth import AdminPrincipal
    from lumini.site.service import (
        SiteContent,
        SitePublish,
        SiteUpdate,
        approve_site,
        publish_site,
        put_site,
    )

    actor = AdminPrincipal("s", "s@example.invalid", (channel.world.professional_id,))
    async with channel.sessions() as session:
        await put_site(
            session,
            actor,
            SiteUpdate(
                expected_revision=0,
                content=SiteContent(
                    bot_texts={
                        "menu": "Saudação sintética aprovada.\n{options}",
                        "handoff": "A equipe continuará seu atendimento por aqui.",
                    },
                ),
            ),
            now=NOW,
        )
    assert await channel.say("oi") == texts.MENU
    async with channel.sessions() as session:
        review = SitePublish(
            expected_revision=1,
            professional_id=channel.world.professional_id,
            review_confirmed=True,
        )
        await approve_site(session, actor, review, now=NOW, media_origins=[])
        await publish_site(session, actor, review, now=NOW, media_origins=[])
    menu = await channel.say("menu")
    assert menu.startswith("Saudação sintética aprovada") and "3. Falar com a equipe" in menu
    assert await channel.say("equipe") == "A equipe continuará seu atendimento por aqui."
    assert (await channel.conversation()).mode == "human"
    await channel.post(channel.payload("#bot", from_me=True))
    assert await channel.say("STOP") == texts.OPT_OUT
    assert await channel.say("estou grávida") == texts.HEALTH_HANDOFF


@pytest.mark.parametrize("action", ["edit", "withdraw"])
async def test_outage_cannot_retry_a_reply_after_site_review_is_withdrawn(
    channel: Channelled,
    action: str,
) -> None:
    from lumini.auth import AdminPrincipal
    from lumini.site.service import (
        SiteContent,
        SitePublish,
        SiteUpdate,
        SiteVersion,
        approve_site,
        publish_site,
        put_site,
        unpublish_site,
    )

    actor = AdminPrincipal("s", "s@example.invalid", (channel.world.professional_id,))
    content = SiteContent(bot_texts={"menu": "Saudação sintética que será retirada.\n{options}"})
    async with channel.sessions() as session:
        await put_site(session, actor, SiteUpdate(expected_revision=0, content=content), now=NOW)
        review = SitePublish(
            expected_revision=1,
            professional_id=channel.world.professional_id,
            review_confirmed=True,
        )
        await approve_site(session, actor, review, now=NOW, media_origins=[])
        await publish_site(session, actor, review, now=NOW, media_origins=[])
    channel.sender.unavailable = 1
    assert await channel.say("oi") == ""
    async with channel.sessions() as session, session.begin():
        queued = await session.scalar(
            select(WhatsAppMessage).where(WhatsAppMessage.status == "failed")
        )
        assert queued is not None and queued.body is not None
        assert "Saudação sintética que será retirada" in queued.body
    async with channel.sessions() as session:
        if action == "edit":
            await put_site(
                session, actor, SiteUpdate(expected_revision=1, content=SiteContent()), now=NOW
            )
        else:
            await unpublish_site(session, actor, SiteVersion(expected_revision=1))
        assert (
            await retry_failed_replies(session, channel.sender, now=NOW + timedelta(seconds=20))
            == 0
        )
    assert channel.sender.sent == []
    async with channel.sessions() as session, session.begin():
        remaining = await session.scalar(
            select(WhatsAppMessage).where(WhatsAppMessage.id == queued.id)
        )
        assert remaining is not None and remaining.status == "skipped" and remaining.body is None
