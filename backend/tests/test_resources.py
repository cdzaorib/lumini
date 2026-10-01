import traceback
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncEngine

from lumini.resources import open_resources
from lumini.settings import Settings


async def test_resources_remain_lazy_and_close_both_clients_on_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = MagicMock(spec=AsyncEngine)
    engine.dispose = AsyncMock()
    redis = MagicMock()
    redis.aclose = AsyncMock()
    redis.ping = AsyncMock(return_value=True)
    monkeypatch.setattr("lumini.resources.create_async_engine", lambda *args, **kwargs: engine)
    monkeypatch.setattr("lumini.resources.Redis.from_url", lambda *args, **kwargs: redis)
    settings = Settings(
        database_url=SecretStr("postgresql://localhost/lumini_test"),
        redis_url=SecretStr("redis://localhost:6379/1"),
    )
    async with open_resources(settings) as resources:
        assert resources.sessions is not None
        assert resources.database is not None
        assert resources.redis is not None
        engine.connect.assert_not_called()
        redis.ping.assert_not_called()
    engine.dispose.assert_awaited_once()
    redis.aclose.assert_awaited_once()


async def test_database_is_disposed_even_when_redis_cleanup_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = MagicMock(spec=AsyncEngine)
    engine.dispose = AsyncMock()
    redis = MagicMock()
    redis.aclose = AsyncMock(side_effect=RuntimeError("synthetic cleanup error"))
    monkeypatch.setattr("lumini.resources.create_async_engine", lambda *args, **kwargs: engine)
    monkeypatch.setattr("lumini.resources.Redis.from_url", lambda *args, **kwargs: redis)
    settings = Settings(
        database_url=SecretStr("postgresql://localhost/lumini_test"),
        redis_url=SecretStr("redis://localhost:6379/1"),
    )
    with pytest.raises(RuntimeError, match="synthetic cleanup error"):
        async with open_resources(settings):
            pass
    engine.dispose.assert_awaited_once()


async def test_redis_client_constructor_failure_is_sanitized_and_engine_is_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sensitive = "synthetic-sensitive-query-value"
    engine = MagicMock(spec=AsyncEngine)
    engine.dispose = AsyncMock()
    monkeypatch.setattr("lumini.resources.create_async_engine", lambda *args, **kwargs: engine)
    settings = Settings(
        database_url=SecretStr("postgresql://localhost/lumini_test"),
        redis_url=SecretStr(f"redis://localhost/0?socket_timeout={sensitive}"),
    )
    with pytest.raises(RuntimeError, match="Dependency client initialization failed") as caught:
        async with open_resources(settings):
            pytest.fail("Invalid URL option must fail during client construction")
    rendered = "".join(traceback.format_exception(caught.value))
    assert sensitive not in rendered
    assert caught.value.__suppress_context__ is True
    engine.dispose.assert_awaited_once()


async def test_sqlalchemy_client_constructor_failure_is_sanitized() -> None:
    sensitive = "synthetic-sensitive-query-value"
    settings = Settings(
        database_url=SecretStr(f"postgresql://localhost/lumini_test?async_fallback={sensitive}")
    )
    with pytest.raises(RuntimeError, match="Dependency client initialization failed") as caught:
        async with open_resources(settings):
            pytest.fail("Invalid URL option must fail during client construction")
    assert sensitive not in "".join(traceback.format_exception(caught.value))
    assert caught.value.__suppress_context__ is True
