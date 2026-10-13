"""Frontend settings isolated from backend credentials."""

import os
from pathlib import Path

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(
    os.environ.get("MINORI_PROJECT_ROOT", str(Path(__file__).resolve().parents[2]))
).resolve()


class FrontendSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    backend_base_url: AnyHttpUrl = AnyHttpUrl("http://127.0.0.1:8000")
    http_timeout_seconds: float = Field(default=5, gt=0, le=60)
