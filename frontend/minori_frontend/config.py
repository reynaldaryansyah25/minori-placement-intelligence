"""Frontend settings isolated from backend internal dependencies."""

import os
from pathlib import Path

from pydantic import AnyHttpUrl, Field, SecretStr, model_validator
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
    internal_api_token: SecretStr | None = None
    reviewer_api_token: SecretStr | None = None
    demo_mode: bool = True
    public_reviewer_mode: bool = False
    interactive_demo_mode: bool = False
    sandbox_gateway_token: SecretStr | None = None
    public_demo_username: SecretStr | None = None
    public_demo_password_hash: SecretStr | None = None
    public_session_idle_seconds: int = Field(default=900, ge=30, le=3600)
    public_session_max_seconds: int = Field(default=3600, ge=60, le=28800)
    public_login_max_attempts: int = Field(default=5, ge=2, le=10)
    public_login_window_seconds: int = Field(default=300, ge=30, le=3600)
    public_login_lockout_seconds: int = Field(default=300, ge=30, le=3600)

    @model_validator(mode="after")
    def isolate_public_credentials(self):
        if self.interactive_demo_mode:
            if (
                not self.public_reviewer_mode
                or self.reviewer_api_token
                or not self.sandbox_gateway_token
            ):
                raise ValueError(
                    "Sandbox publik memerlukan login dan kredensial sandbox tersendiri."
                )
            if self.backend_base_url.host != "backend-sandbox":
                raise ValueError("Frontend sandbox hanya dapat terhubung ke backend-sandbox.")
        if self.public_reviewer_mode:
            # Fail closed even if an operator accidentally injects an admin credential.
            if self.internal_api_token is not None:
                raise ValueError("Frontend publik tidak boleh menerima kredential administrator.")
            if (
                not (
                    self.sandbox_gateway_token
                    if self.interactive_demo_mode
                    else self.reviewer_api_token
                )
                or not self.public_demo_username
                or not self.public_demo_password_hash
            ):
                raise ValueError("Konfigurasi autentikasi demo publik belum lengkap.")
            from minori_frontend.public_auth import valid_password_hash

            if not valid_password_hash(self.public_demo_password_hash.get_secret_value()):
                raise ValueError("Konfigurasi autentikasi demo publik belum valid.")
        return self
