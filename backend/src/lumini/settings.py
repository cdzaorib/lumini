"""Process environment only; no implicit .env or inherited project configuration."""

from typing import Literal
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

from pydantic import Field, SecretStr, field_validator, model_validator
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
    google_client_id: str | None = Field(default=None, max_length=256)
    admin_emails: list[str] = Field(default_factory=list, repr=False)
    reviewer_assignments: dict[str, list[UUID]] = Field(default_factory=dict, repr=False)

    @field_validator("google_client_id")
    @classmethod
    def validate_google_client_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value or any(char.isspace() for char in value):
            raise ValueError("google_client_id must be a nonempty identifier")
        return value

    @field_validator("admin_emails")
    @classmethod
    def normalize_admin_emails(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(normalize_email(value) for value in values))

    @field_validator("reviewer_assignments")
    @classmethod
    def normalize_reviewer_assignments(cls, values: dict[str, list[UUID]]) -> dict[str, list[UUID]]:
        result: dict[str, list[UUID]] = {}
        for email, ids in values.items():
            normalized = normalize_email(email)
            if normalized in result:
                raise ValueError("reviewer_assignments contains duplicate normalized identities")
            result[normalized] = list(dict.fromkeys(ids))
        return result

    @model_validator(mode="after")
    def validate_reviewer_allowlist(self) -> "Settings":
        if not self.reviewer_assignments.keys() <= set(self.admin_emails):
            raise ValueError("reviewer assignments require an allowed administrator")
        return self

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


def normalize_email(value: str) -> str:
    """Conservative identifier normalization, never provider-specific dot/alias rewriting."""
    normalized = value.strip().lower()
    parts = normalized.split("@")
    if (
        len(normalized) > 254
        or len(parts) != 2
        or not all(parts)
        or any(char.isspace() or ord(char) < 32 for char in normalized)
        or "." not in parts[1]
    ):
        raise ValueError("a valid administrative email is required")
    return normalized
