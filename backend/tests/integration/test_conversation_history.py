import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from lumini.booking.metrics import collect
from lumini.models import Conversation
from lumini.whatsapp.conversations import discard_pending_replies, send_automatic, set_mode
from lumini.whatsapp.evolution import WhatsAppUnavailable
from lumini.whatsapp.history import ConversationEvent
from tests.integration.test_booking_flow import NOW
from tests.integration.test_whatsapp import FakeSender

pytestmark = pytest.mark.integration


async def test_handoff_history_survives_resume_and_metrics_count_events(
    connection: AsyncConnection,
) -> None:
    async with AsyncSession(
        bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    ) as session:
        conversation = Conversation(
            id=uuid.uuid4(),
            chat_id=f"synthetic-history-{uuid.uuid4()}",
            mode="bot",
            version=1,
            state={"step": "service", "service_id": str(uuid.uuid4()), "name": "Sintética"},
        )
        async with session.begin():
            session.add(conversation)
            await session.flush()
            set_mode(conversation, "human", "requested", NOW)
            set_mode(conversation, "human", "requested", NOW)  # same mode is no new handoff
            set_mode(conversation, "bot", None, NOW)
            conversation.state = {}
        async with session.begin():
            rows = list(
                await session.scalars(
                    select(ConversationEvent)
                    .where(ConversationEvent.conversation_id == conversation.id)
                    .order_by(ConversationEvent.occurred_at, ConversationEvent.version)
                )
            )
        assert [row.kind for row in rows] == ["human", "bot"]
        assert [row.version for row in rows] == [2, 3]
        assert rows[0].summary["step"] == "service" and "name" not in rows[0].summary
        result = await collect(session, now=NOW + timedelta(seconds=2), days=1)
        assert {item.key: item.count for item in result.handoffs_by_reason}["requested"] >= 1


async def test_withdrawn_reply_cannot_be_resurrected_from_a_retry_snapshot(
    connection: AsyncConnection,
) -> None:
    async with AsyncSession(
        bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    ) as session:
        conversation = Conversation(
            id=uuid.uuid4(),
            chat_id=f"synthetic-retry-{uuid.uuid4()}",
            mode="bot",
            version=1,
            state={},
        )
        async with session.begin():
            session.add(conversation)
        sender = FakeSender(unavailable=1)
        dedupe_key = f"synthetic-reply-{uuid.uuid4()}"

        async def dispatch(version: int) -> str:
            return await send_automatic(
                session,
                sender,
                conversation.id,
                "Aviso sintético antigo",
                purpose="reply",
                dedupe_key=dedupe_key,
                now=NOW,
                expected_version=version,
                keep_text=True,
            )

        with pytest.raises(WhatsAppUnavailable):
            await dispatch(1)
        async with session.begin():
            await discard_pending_replies(session)
        assert await dispatch(1) == "skipped_stale"
        assert not sender.sent
        assert await dispatch(conversation.version) == "skipped_stale"
        assert not sender.sent
