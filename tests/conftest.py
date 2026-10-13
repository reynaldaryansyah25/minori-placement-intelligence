"""Isolate tests from developer credentials and persistent databases."""

import json
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from minori.core.config import Settings, get_settings
from minori.db.seeding import seed_database
from minori.db.session import Database


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch, tmp_path):
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)
    for name in ("OPENAI_API_KEY", "OPENAI_ORG_ID", "OPENAI_PROJECT_ID", "OPENAI_BASE_URL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///" + (tmp_path / "minori.db").as_posix())
    monkeypatch.setenv("LLM_ENABLED", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def settings():
    return Settings(_env_file=None)


@pytest.fixture
def migrated_database(settings):
    root = Path(__file__).resolve().parents[1]
    command.upgrade(Config(str(root / "alembic.ini")), "head")
    database = Database(settings)
    try:
        yield database
    finally:
        database.dispose()


@pytest.fixture
def seeded_database(migrated_database):
    seed_database(migrated_database)
    return migrated_database


@pytest.fixture
def candidate_payload():
    root = Path(__file__).resolve().parents[1]
    return json.loads((root / "data/dummy/candidates.json").read_text())["candidates"][0]


@pytest.fixture
def vacancy_payload():
    root = Path(__file__).resolve().parents[1]
    return json.loads((root / "data/dummy/vacancies.json").read_text())["vacancies"][0]
