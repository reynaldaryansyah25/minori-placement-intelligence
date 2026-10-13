"""Configuration validation and protection against implicit LLM defaults."""

import pytest
from minori.core.config import Settings
from pydantic import ValidationError


def test_disabled_router_accepts_blank_connection():
    settings = Settings(
        _env_file=None, nine_router_base_url="", nine_router_api_key="", nine_router_model=""
    )
    assert not settings.llm_enabled
    assert settings.nine_router_api_key is None
    assert settings.nine_router_model is None


@pytest.mark.parametrize(
    "missing", ["nine_router_base_url", "nine_router_api_key", "nine_router_model"]
)
def test_enabled_router_requires_complete_configuration(missing):
    values = {
        "nine_router_base_url": "http://127.0.0.1:20128/v1",
        "nine_router_api_key": "synthetic-test-key",
        "nine_router_model": "synthetic-model",
    }
    values[missing] = ""
    with pytest.raises(ValidationError, match="LLM_ENABLED requires"):
        Settings(_env_file=None, llm_enabled=True, **values)


def test_secrets_are_masked_and_environment_wins(monkeypatch, tmp_path):
    env = tmp_path / ".env"
    env.write_text("APP_NAME=From file\n", encoding="utf-8")
    monkeypatch.setenv("APP_NAME", "From process")
    settings = Settings(_env_file=env, nine_router_api_key="synthetic-private-value")
    assert settings.app_name == "From process"
    assert "synthetic-private-value" not in repr(settings)
    assert settings.nine_router_api_key.get_secret_value() == "synthetic-private-value"


@pytest.mark.parametrize("url", ["postgresql://localhost/minori", "sqlite+aiosqlite:///:memory:"])
def test_database_rejects_other_technologies(url):
    with pytest.raises(ValidationError, match="SQLite"):
        Settings(_env_file=None, database_url=url)


def test_router_url_rejects_embedded_credentials():
    with pytest.raises(ValidationError, match="credentials"):
        Settings(_env_file=None, nine_router_base_url="http://user:secret@localhost:20128/v1")


@pytest.mark.parametrize("field,value", [("llm_timeout_seconds", 0), ("llm_max_retries", -1)])
def test_invalid_request_limits_are_rejected(field, value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: value})
