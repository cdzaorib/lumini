"""Lazy clients owned by the application lifespan; no credentials in probe responses."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Literal, Protocol

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from lumini.settings import Settings

DependencyStatus = Literal["ok", "not_configured", "unavailable"]


class Probe(Protocol):
    async def ping(self) -> None: ...


@dataclass
class DatabaseProbe:
    engine: AsyncEngine

    async def ping(self) -> None:
        async with self.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))


@dataclass
class RedisProbe:
    client: Redis

    async def ping(self) -> None:
        if not await self.client.ping():
            raise RuntimeError("Redis did not acknowledge ping")


@dataclass
class Resources:
    database: Probe | None = None
    redis: Probe | None = None
    sessions: async_sessionmaker[AsyncSession] | None = None


async def check_dependency(probe: Probe | None, deadline_seconds: float) -> DependencyStatus:
    if probe is None:
        return "not_configured"
    try:
        async with asyncio.timeout(deadline_seconds):
            await probe.ping()
    except Exception:
        # Libraries may include connection URLs or credentials in exception text.
        # Report a bounded state, never serialize/log the exception or its repr.
        return "unavailable"
    return "ok"


@asynccontextmanager
async def open_resources(settings: Settings) -> AsyncIterator[Resources]:
    resources = Resources()
    engine: AsyncEngine | None = None
    redis: Redis | None = None
    try:
        try:
            database_url = settings.sqlalchemy_url()
            if database_url is not None:
                engine = create_async_engine(
                    database_url, pool_pre_ping=True, echo=False, hide_parameters=True
                )
                resources.database = DatabaseProbe(engine)
                resources.sessions = async_sessionmaker(engine, expire_on_commit=False)
            if settings.redis_url is not None:
                redis = Redis.from_url(
                    settings.redis_url.get_secret_value(),
                    decode_responses=True,
                    socket_connect_timeout=settings.dependency_timeout_seconds,
                    socket_timeout=settings.dependency_timeout_seconds,
                )
                resources.redis = RedisProbe(redis)
        except Exception:
            # Invalid URL options can echo sensitive query values before a
            # connection is attempted. Do not display the driver exception chain.
            raise RuntimeError(
                "Dependency client initialization failed; check configuration"
            ) from None
        yield resources
    finally:
        try:
            if redis is not None:
                await redis.aclose()
        finally:
            if engine is not None:
                await engine.dispose()
