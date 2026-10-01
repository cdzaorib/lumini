from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from lumini.settings import Settings


def test_secret_urls_are_masked_in_representations() -> None:
    settings = Settings(
        database_url=SecretStr("postgresql://test_user:synthetic-secret@localhost/lumini_test"),
        redis_url=SecretStr("redis://:synthetic-redis-secret@localhost:6379/0"),
    )
    assert "synthetic-secret" not in repr(settings)
    assert "synthetic-redis-secret" not in settings.model_dump_json()
    url = settings.sqlalchemy_url()
    assert url is not None
    assert url.drivername == "postgresql+asyncpg"


@pytest.mark.parametrize(
    "raw",
    ["sqlite:///test.db", "not-a-url-synthetic-secret", "postgresql://host", "mysql://host/db"],
)
def test_database_rejects_unsupported_configuration_without_echoing_input(raw: str) -> None:
    with pytest.raises(ValidationError) as caught:
        Settings(database_url=SecretStr(raw))
    assert raw not in str(caught.value)


@pytest.mark.parametrize("raw", ["https://host/synthetic-secret", "redis://", "redis://host:nope"])
def test_redis_rejects_unsupported_configuration_without_echoing_input(raw: str) -> None:
    with pytest.raises(ValidationError) as caught:
        Settings(redis_url=SecretStr(raw))
    assert raw not in str(caught.value)


@pytest.mark.parametrize("query", ["ssl_cert_reqs=none", "ssl_check_hostname=false"])
def test_redis_url_cannot_override_certificate_verification(query: str) -> None:
    with pytest.raises(ValidationError, match="cannot override TLS verification"):
        Settings(redis_url=SecretStr(f"rediss://localhost:6380/0?{query}"))


@pytest.mark.parametrize(
    "origin", ["*", "https://user:secret@example.invalid", "https://host/path"]
)
def test_cors_rejects_unsafe_origins(origin: str) -> None:
    with pytest.raises(ValidationError):
        Settings(cors_origins=[origin])


def test_only_prefixed_process_environment_is_loaded(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("LUMINI_ENVIRONMENT=production\n")
    monkeypatch.setenv("DATABASE_URL", "postgresql://unrelated/other")
    settings = Settings()
    assert settings.environment == "development"
    assert settings.database_url is None
    monkeypatch.setenv("LUMINI_ENVIRONMENT", "test")
    assert Settings().environment == "test"
