"""E2E backend: the real app on a throwaway PostgreSQL database with synthetic identity, calendar
and WhatsApp sender. Synthetic data only; refuses anything but a local *_test database.

Environment: LUMINI_E2E_ADMIN_DATABASE_URL (maintenance database on the local test server),
LUMINI_E2E_REDIS_URL, E2E_API_PORT (default 8100), E2E_SITE (default http://127.0.0.1:3100).
"""

import asyncio
import os
import sys
import time
from datetime import UTC, date, datetime, timedelta
from datetime import time as dtime
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

import asyncpg
import uvicorn
from alembic import command
from alembic.config import Config
from lumini.app import create_app
from lumini.auth import InvalidIdentityToken
from lumini.booking.policy import CLINIC_TZ
from lumini.booking.service import (
    Actor,
    HoldRequest,
    confirm_deposit,
    create_hold,
    sync_calendar,
)
from lumini.settings import Settings
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from tests.booking_fakes import FakeCalendar
from tests.integration.test_booking_flow import (
    CAL,
    professional,
    published_service,
)

CLIENT_ID = "123456789-synthetic.apps.googleusercontent.com"
TOKEN = "e2e.synthetic.token"  # accepted only by the synthetic verifier below
EMAIL = "e2e.synthetic@gmail.com"
SITE = os.environ.get("E2E_SITE", "http://127.0.0.1:3100")
PORT = int(os.environ.get("E2E_API_PORT", "8100"))
ADMIN_URL = os.environ["LUMINI_E2E_ADMIN_DATABASE_URL"]
REDIS_URL = os.environ["LUMINI_E2E_REDIS_URL"]
DB_NAME = "lumini_e2e_test"
DB = ADMIN_URL.rsplit("/", 1)[0] + "/" + DB_NAME


async def recreate_database() -> None:
    host = urlsplit(ADMIN_URL).hostname
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise SystemExit("E2E refuses non-local databases")
    connection = await asyncpg.connect(ADMIN_URL)
    try:
        await connection.execute(f"DROP DATABASE IF EXISTS {DB_NAME}")
        await connection.execute(f"CREATE DATABASE {DB_NAME}")
    finally:
        await connection.close()
    os.environ["LUMINI_DATABASE_URL"] = DB
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    await asyncio.to_thread(command.upgrade, config, "head")


class RecordingSender:
    """Stands in for Evolution: accepts every message and returns a synthetic id."""

    def __init__(self) -> None:
        self.count = 0

    async def send_text(self, chat_id: str, text: str) -> str:
        self.count += 1
        return f"E2EBOT{self.count:06d}"


class Verifier:
    def verify(self, token: str) -> dict[str, object]:
        if token != TOKEN:
            raise InvalidIdentityToken("Invalid identity token")
        now = int(time.time())
        return {
            "iss": "https://accounts.google.com",
            "aud": CLIENT_ID,
            "exp": now + 3600,
            "iat": now,
            "sub": "e2e-synthetic-subject",
            "email": EMAIL,
            "email_verified": True,
        }


def at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, dtime(hour, minute), tzinfo=CLINIC_TZ).astimezone(UTC)


async def seed(calendar: FakeCalendar) -> UUID:
    engine = create_async_engine(DB.replace("postgresql:", "postgresql+asyncpg:"))
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(UTC)
    tomorrow = now.astimezone(CLINIC_TZ).date() + timedelta(days=1)
    after = tomorrow + timedelta(days=1)
    async with sessions() as session:
        async with session.begin():
            person = await professional(session)
            service_id = await published_service(session, person)
        keys = iter(range(1, 100))

        async def hold(starts: datetime, name: str, phone: str):
            request = HoldRequest(
                f"e2e-key-{next(keys):04d}", service_id, person, starts, name, phone
            )
            booking = await create_hold(session, calendar, request, now=now)
            await sync_calendar(session, calendar, booking.id, now=now)
            return booking

        await hold(at(tomorrow, 10), "Cliente Sintética Aguardando", "+5521900000001")
        await hold(at(tomorrow, 16), "Cliente Sintética Cancelar", "+5521900000004")
        conflict = await create_hold(
            session,
            calendar,
            HoldRequest(
                "e2e-key-conflict",
                service_id,
                person,
                at(tomorrow, 14),
                "Cliente Sintética Conflito",
                "+5521900000002",
            ),
            now=now,
        )
        calendar.add_manual(CAL, at(tomorrow, 14, 30), at(tomorrow, 15))
        await sync_calendar(session, calendar, conflict.id, now=now)
        paid = await hold(
            at(after, 10), "Cliente Sintética Confirmada", "+5521900000003"
        )
        async with session.begin():
            await session.refresh(paid)
        await confirm_deposit(
            session,
            paid.id,
            actor=Actor.staff("seed"),
            expected_version=paid.version,
            amount_brl=Decimal("50.00"),
            now=now,
        )
        await sync_calendar(session, calendar, paid.id, now=now)
        # An appointment two days ago, so staff can record attendance.
        earlier = now - timedelta(days=3)
        past_day = (now - timedelta(days=2)).astimezone(CLINIC_TZ).date()
        past = await create_hold(
            session,
            calendar,
            HoldRequest(
                "e2e-key-past",
                service_id,
                person,
                at(past_day, 10),
                "Cliente Sintética Passada",
                "+5521900000005",
            ),
            now=earlier,
        )
        await sync_calendar(session, calendar, past.id, now=earlier)
        async with session.begin():
            await session.refresh(past)
        await confirm_deposit(
            session,
            past.id,
            actor=Actor.staff("seed"),
            expected_version=past.version,
            amount_brl=Decimal("50.00"),
            now=earlier,
        )
        await sync_calendar(session, calendar, past.id, now=earlier)
    await engine.dispose()
    return person


def main() -> None:
    asyncio.run(recreate_database())
    calendar = FakeCalendar()
    reviewer = asyncio.run(seed(calendar))
    settings = Settings(
        environment="development",
        database_url=SecretStr(DB),
        redis_url=SecretStr(REDIS_URL),
        google_client_id=CLIENT_ID,
        admin_emails=[EMAIL],
        reviewer_assignments={EMAIL: [reviewer]},
        cors_origins=[SITE],
        manage_link_secret=SecretStr("e2e-synthetic-manage-link-secret-0123456789"),
        public_site_url=SITE,
        evolution_base_url="https://evolution.synthetic.invalid",
        evolution_instance="lumini-e2e",
        evolution_api_key=SecretStr("e2e-synthetic-evolution-key"),
        evolution_webhook_token=SecretStr(
            "e2e-synthetic-webhook-token-0123456789abcdef"
        ),
    )
    app = create_app(settings)
    app.state.identity_verifier = Verifier()
    app.state.calendar = calendar
    app.state.whatsapp = RecordingSender()
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
