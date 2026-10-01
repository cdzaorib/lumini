"""Process environment only; no implicit .env or inherited project configuration."""

from typing import Literal
from urllib.parse import parse_qs, urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LUMINI_", env_file=None, extra="ignore", hide_input_in_errors=True
    )

    environment: Literal["development", "test", "production"] = "development"
    database_url: SecretStr | None = None
    redis_url: SecretStr | None = None
    cors_origins: list[str] = Field(default_factory=list)
    dependency_timeout_seconds: float = Field(default=2.0, gt=0, le=10)

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return value
        try:
            url = make_url(value.get_secret_value())
            valid = url.drivername in {"postgres", "postgresql", "postgresql+asyncpg"}
            if not valid or not url.host or not url.database:
                raise ValueError
            _ = url.port
        except (ValueError, TypeError, ArgumentError):
            raise ValueError(
                "database_url must reference PostgreSQL with host and database"
            ) from None
        return value

    @field_validator("redis_url")
    @classmethod
    def validate_redis_url(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return value
        try:
            url = urlsplit(value.get_secret_value())
            if url.scheme not in {"redis", "rediss"} or not url.hostname:
                raise ValueError
            _ = url.port
            # URL parameters override transport kwargs in Redis/Kombu. Keep the
            # certificate and hostname policy under application control.
            if {"ssl_cert_reqs", "ssl_check_hostname"} & parse_qs(
                url.query, keep_blank_values=True
            ).keys():
                raise ValueError
        except ValueError:
            raise ValueError(
                "redis_url must reference a Redis host and cannot override TLS verification"
            ) from None
        return value

    @field_validator("cors_origins")
    @classmethod
    def validate_origins(cls, values: list[str]) -> list[str]:
        for value in values:
            url = urlsplit(value)
            if (
                url.scheme not in {"http", "https"}
                or not url.hostname
                or url.username
                or url.password
                or url.path not in {"", "/"}
                or url.query
                or url.fragment
            ):
                raise ValueError(
                    "CORS requires explicit HTTP(S) origins without credentials or path"
                )
        return [value.rstrip("/") for value in values]

    def sqlalchemy_url(self) -> URL | None:
        if self.database_url is None:
            return None
        return make_url(self.database_url.get_secret_value()).set(drivername="postgresql+asyncpg")
