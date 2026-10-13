"""Verify full schema migrations, rollback safety, and preservation of existing data."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from minori.db.inspection import inspect_database, migration_heads
from minori.db.models import MODEL_TYPES
from sqlalchemy import create_engine, inspect, text

ROOT = Path(__file__).resolve().parents[2]


def test_empty_database_migration_round_trip(tmp_path):
    url = "sqlite:///" + (tmp_path / "migration.db").as_posix()
    environment = {**os.environ, "DATABASE_URL": url, "LLM_ENABLED": "false"}
    engine = create_engine(url)
    try:
        for target in ("head", "base", "head"):
            command = "downgrade" if target == "base" else "upgrade"
            completed = subprocess.run(
                [sys.executable, "-m", "alembic", command, target],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
            )
            assert completed.returncode == 0, completed.stdout + completed.stderr
            with engine.connect() as connection:
                versions = connection.execute(text("SELECT version_num FROM alembic_version")).all()
                assert {version[0] for version in versions} == (
                    set() if target == "base" else migration_heads()
                )
                expected = {"alembic_version"}
                if target == "head":
                    expected.update(model.__tablename__ for model in MODEL_TYPES)
                assert set(inspect(connection).get_table_names()) == expected
        drift = subprocess.run(
            [sys.executable, "-m", "alembic", "check"],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
        )
        assert drift.returncode == 0, drift.stdout + drift.stderr
    finally:
        engine.dispose()


def test_additive_upgrade_preserves_existing_unrelated_data(settings):
    configuration = Config(str(ROOT / "alembic.ini"))
    command.upgrade(configuration, "foundation")
    engine = create_engine(settings.database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text("CREATE TABLE existing_records (id INTEGER PRIMARY KEY, value TEXT)")
            )
            connection.execute(text("INSERT INTO existing_records VALUES (1, 'preserved')"))
        command.upgrade(configuration, "head")
        with engine.connect() as connection:
            assert (
                connection.execute(text("SELECT value FROM existing_records")).scalar_one()
                == "preserved"
            )
    finally:
        engine.dispose()


@pytest.mark.parametrize("target", ["foundation", "base", "-2"])
def test_populated_downgrade_is_refused_before_any_data_is_removed(seeded_database, target):
    before = inspect_database(seeded_database)
    with pytest.raises(RuntimeError, match="Refusing downgrade"):
        command.downgrade(Config(str(ROOT / "alembic.ini")), target)
    after = inspect_database(seeded_database)
    assert after["counts"] == before["counts"]
    assert after["migration_revision"] == before["migration_revision"]
