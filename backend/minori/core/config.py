"""Environment-backed application settings with explicit validation."""

import os
from datetime import time
from functools import lru_cache
from pathlib import Path
from typing import Literal, Self
from zoneinfo import ZoneInfo

from pydantic import AnyHttpUrl, AwareDatetime, Field, SecretStr, field_validator, model_validator
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
    app_env: Literal["development", "demo", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    database_url: str = "sqlite:///./data/runtime/minori.db"
    sqlite_timeout_seconds: float = Field(default=5, gt=0, le=60)
    llm_enabled: bool = False
    nine_router_base_url: AnyHttpUrl | None = None
    nine_router_api_key: SecretStr | None = None
    nine_router_model: str | None = None
    nine_router_fallback_models: str = ""
    llm_timeout_seconds: float = Field(default=30, gt=0, le=300)
    llm_attempt_timeout_seconds: float = Field(default=30, gt=0, le=300)
    llm_max_retries: int = Field(default=2, ge=0, le=5)
    business_timezone: str = "Asia/Jakarta"
    reminder_delivery_time: time = time(9, 0)
    notification_dry_run: bool = True
    notification_lease_seconds: int = Field(default=120, ge=10, le=3600)
    notification_max_attempts: int = Field(default=3, ge=1, le=20)
    notification_retry_base_seconds: int = Field(default=60, ge=1, le=86400)
    notification_retry_max_seconds: int = Field(default=3600, ge=1, le=86400)
    demo_notification_recipient: str | None = None
    notification_delivery_mode: Literal["dry_run", "mailpit", "demo_recipient"] = "dry_run"
    mailpit_inbox_email: str = "mailpit@minori.local"
    internal_api_token: SecretStr | None = None
    reviewer_api_token: SecretStr | None = None
    demo_clock_at: AwareDatetime | None = None
    sandbox_enabled: bool = False
    sandbox_root: Path = Path("/app/data/sandbox")
    sandbox_gateway_token: SecretStr | None = None
    sandbox_worker_token: SecretStr | None = None
    sandbox_session_seconds: int = Field(default=3600, ge=60, le=28800)
    sandbox_idle_seconds: int = Field(default=900, ge=30, le=3600)
    sandbox_max_sessions: int = Field(default=8, ge=1, le=20)
    sandbox_ai_limit: int = Field(default=12, ge=1, le=30)
    sandbox_write_limit: int = Field(default=80, ge=1, le=200)
    sandbox_email_limit: int = Field(default=5, ge=1, le=10)
    sandbox_upload_limit: int = Field(default=10, ge=1, le=20)
    sandbox_hourly_ai_limit: int = Field(default=60, ge=1, le=200)
    sandbox_hourly_email_limit: int = Field(default=30, ge=1, le=60)

    @field_validator("demo_clock_at", mode="before")
    @classmethod
    def normalize_demo_clock(cls, value):
        return None if value == "" else value

    @field_validator("nine_router_fallback_models")
    @classmethod
    def validate_fallback_models(cls, value: str) -> str:
        models = [item.strip() for item in value.split(",") if item.strip()]
        if len(models) > 3 or len(models) != len(set(models)):
            raise ValueError("Configure at most three distinct fallback model IDs")
        if any(len(model) > 160 or any(char.isspace() for char in model) for model in models):
            raise ValueError("Fallback model IDs must be short and contain no whitespace")
        return ",".join(models)

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
        "nine_router_base_url",
        "nine_router_api_key",
        "nine_router_model",
        "demo_notification_recipient",
        mode="before",
    )
    @classmethod
    def normalize_optional_values(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value

    @model_validator(mode="after")
    def validate_router_configuration(self) -> Self:
        if self.sandbox_enabled:
            if (
                self.app_env not in {"demo", "test"}
                or self.internal_api_token
                or self.reviewer_api_token
            ):
                raise ValueError("Sandbox requires demo/test and separate sandbox credentials")
            tokens = (self.sandbox_gateway_token, self.sandbox_worker_token)
            if not all(token and len(token.get_secret_value()) >= 32 for token in tokens):
                raise ValueError(
                    "Sandbox gateway and worker secrets must have at least 32 characters"
                )
            if tokens[0] == tokens[1]:
                raise ValueError("Sandbox gateway and worker credentials must differ")
            if self.notification_delivery_mode != "mailpit" or self.notification_dry_run:
                raise ValueError("Sandbox delivery must use isolated Mailpit")
            root = self.sandbox_root.resolve()
            database = Path(make_url(self.database_url).database or "").resolve()
            if not database.is_relative_to(root) or database.name != "template.db":
                raise ValueError("Sandbox template database must be inside SANDBOX_ROOT")
            if self.demo_clock_at and self.app_env != "test":
                raise ValueError("Sandbox clock control is restricted to isolated tests")
        if self.app_env == "production" and self.notification_delivery_mode != "dry_run":
            raise ValueError(
                "Production email delivery requires a separately authorized verified-recipient adapter"
            )
        if self.demo_clock_at is not None and self.app_env not in {"demo", "test"}:
            raise ValueError("DEMO_CLOCK_AT is restricted to demo/test environments")
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
