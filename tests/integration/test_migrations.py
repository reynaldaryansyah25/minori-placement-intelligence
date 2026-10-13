"""Verify migration upgrade, downgrade, and absence of business tables."""

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

ROOT = Path(__file__).resolve().parents[2]


def test_foundation_migration_round_trip(tmp_path):
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
                assert versions == ([] if target == "base" else [("foundation",)])
                assert inspect(connection).get_table_names() == ["alembic_version"]
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
