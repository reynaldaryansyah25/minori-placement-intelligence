"""Environment-backed application settings with explicit validation."""

import os
from datetime import time
from functools import lru_cache
from pathlib import Path
from typing import Literal, Self
from zoneinfo import ZoneInfo

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

PROJECT_ROOT = Path(
    os.environ.get("MINORI_PROJECT_ROOT", str(Path(__file__).resolve().parents[3]))
).resolve()


class Settings(BaseSettings):
    """Settings loaded from process environment, then the repository .env file."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    app_name: str = "MINORI Placement Intelligence"
    app_env: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    database_url: str = "sqlite:///./data/runtime/minori.db"
    sqlite_timeout_seconds: float = Field(default=5, gt=0, le=60)
    llm_enabled: bool = False
    nine_router_base_url: AnyHttpUrl | None = None
    nine_router_api_key: SecretStr | None = None
    nine_router_model: str | None = None
    llm_timeout_seconds: float = Field(default=30, gt=0, le=300)
    llm_max_retries: int = Field(default=2, ge=0, le=5)
    business_timezone: str = "Asia/Jakarta"
    reminder_delivery_time: time = time(9, 0)
    notification_dry_run: bool = True
    notification_lease_seconds: int = Field(default=120, ge=10, le=3600)
    notification_max_attempts: int = Field(default=3, ge=1, le=20)
    notification_retry_base_seconds: int = Field(default=60, ge=1, le=86400)
    notification_retry_max_seconds: int = Field(default=3600, ge=1, le=86400)
    internal_api_token: SecretStr | None = None
    reviewer_api_token: SecretStr | None = None

    @field_validator("business_timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ValueError, KeyError) as error:
            raise ValueError("Unknown business timezone") from error
        return value

    @field_validator("reminder_delivery_time")
    @classmethod
    def validate_delivery_time(cls, value: time) -> time:
        if value.tzinfo is not None or value.second or value.microsecond:
            raise ValueError("Reminder delivery time must be local HH:MM")
        return value

    @field_validator("internal_api_token", mode="before")
    @classmethod
    def validate_internal_token(cls, value):
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None
            if len(value) < 32:
                raise ValueError("Internal API token must have at least 32 characters")
        return value

    @field_validator("reviewer_api_token", mode="before")
    @classmethod
    def validate_reviewer_token(cls, value):
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None
            if len(value) < 16:
                raise ValueError("Reviewer API token must have at least 16 characters")
        return value

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        if make_url(value).drivername not in {"sqlite", "sqlite+pysqlite"}:
            raise ValueError("DATABASE_URL must use the synchronous SQLite driver")
        return value

    @field_validator(
        "nine_router_base_url", "nine_router_api_key", "nine_router_model", mode="before"
    )
    @classmethod
    def normalize_optional_values(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value

    @model_validator(mode="after")
    def validate_router_configuration(self) -> Self:
        if self.llm_enabled and not all(
            (self.nine_router_base_url, self.nine_router_api_key, self.nine_router_model)
        ):
            raise ValueError(
                "LLM_ENABLED requires NINE_ROUTER_BASE_URL, NINE_ROUTER_API_KEY, "
                "and NINE_ROUTER_MODEL"
            )
        if self.nine_router_base_url and (
            self.nine_router_base_url.username or self.nine_router_base_url.password
        ):
            raise ValueError("Use NINE_ROUTER_API_KEY instead of credentials in the base URL")
        return self


@lru_cache
def get_settings() -> Settings:
    """Load and reuse process settings without creating external clients."""
    return Settings()
