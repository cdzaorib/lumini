"""Explicitly selected test services only. Never uses deployment DATABASE_URL settings."""

import os
from collections.abc import AsyncIterator

import pytest
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from lumini.settings import Settings


@pytest.fixture(scope="session")
def integration_settings() -> Settings:
    database_url = os.environ.get("LUMINI_INTEGRATION_DATABASE_URL")
    redis_url = os.environ.get("LUMINI_INTEGRATION_REDIS_URL")
    if not database_url or not redis_url:
        pytest.fail(
            "Integration tests require LUMINI_INTEGRATION_DATABASE_URL and "
            "LUMINI_INTEGRATION_REDIS_URL pointing to isolated test instances."
        )
    settings = Settings(
        environment="test",
        database_url=SecretStr(database_url),
        redis_url=SecretStr(redis_url),
    )
    parsed_url = settings.sqlalchemy_url()
    if parsed_url is None or not (parsed_url.database or "").endswith("_test"):
        pytest.fail("Refusing integration writes: database name must end with _test.")
    return settings


@pytest.fixture
async def connection(integration_settings: Settings) -> AsyncIterator[AsyncConnection]:
    url = integration_settings.sqlalchemy_url()
    assert url is not None
    engine = create_async_engine(url, echo=False, hide_parameters=True)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                yield connection
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()
