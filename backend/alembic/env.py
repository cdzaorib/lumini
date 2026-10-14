"""Migrations use process configuration; offline SQL generation needs no credential."""

import asyncio

from sqlalchemy import Connection, pool
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from alembic import context
from lumini.models import Base
from lumini.settings import Settings
from lumini.whatsapp.history import ConversationEvent  # noqa: F401 - registers metadata

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        dialect_name="postgresql",
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_with_connection(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    url = Settings().sqlalchemy_url()
    if url is None:
        raise RuntimeError("LUMINI_DATABASE_URL is required for online migrations")
    engine: AsyncEngine | None = None
    try:
        engine = create_async_engine(url, poolclass=pool.NullPool, echo=False, hide_parameters=True)
        async with engine.connect() as connection:
            await connection.run_sync(run_with_connection)
    except Exception:
        # Connection/driver exception text can contain credentials or provider URLs.
        raise RuntimeError(
            "Migration failed; check database availability and migration state"
        ) from None
    finally:
        if engine is not None:
            await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
