"""Preview, back up, then atomically replace a verified demo-only database."""

import argparse
import hashlib
import json
import os
import sqlite3
import tempfile
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from minori.core.config import PROJECT_ROOT, Settings, get_settings
from minori.db.base import Base
from minori.db.inspection import inspect_database, migration_heads
from minori.db.models import MODEL_TYPES
from minori.db.professional_demo import NAMES, seed_professional_demo
from minori.db.session import Database, resolve_database_url

CONFIRMATION = "RESET-MINORI-DEMO"


def verify_demo(connection, settings, path):
    if settings.app_env != "demo" or path.name != "professional-demo.db":
        raise RuntimeError(
            "Reset requires APP_ENV=demo and the dedicated professional-demo.db file"
        )
    tables = {
        x[0]
        for x in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    expected = {x.__tablename__ for x in MODEL_TYPES} | {"alembic_version"}
    if tables != expected:
        raise RuntimeError("Unverified schema or unrelated tables; reset refused")
    if {
        row[0] for row in connection.execute("SELECT version_num FROM alembic_version")
    } != migration_heads():
        raise RuntimeError("Unverified migration revision; reset refused")
    for table in ("candidates", "vacancies", "placements", "vacancy_drafts"):
        if connection.execute(
            f"SELECT count(*) FROM \"{table}\" WHERE reference NOT LIKE 'DEMO-%'"
        ).fetchone()[0]:
            raise RuntimeError("Non-demo records detected; reset refused")
    expected_candidates = {f"DEMO-PRO-CAND-{i + 1:02}": name for i, name in enumerate(NAMES)}
    for reference, name in connection.execute("SELECT reference, full_name FROM candidates"):
        if expected_candidates.get(reference) != name:
            raise RuntimeError("Unverified demo identity detected; reset refused")
    roots = {
        "vacancies": {f"DEMO-PRO-VAC-{i + 1:02}" for i in range(10)},
        "placements": {f"DEMO-PRO-PLC-{i + 1:02}" for i in range(8)},
        "vacancy_drafts": {f"DEMO-PRO-DRAFT-{i + 1:02}" for i in range(3)},
    }
    for table, allowed in roots.items():
        if any(
            reference not in allowed
            for (reference,) in connection.execute(f'SELECT reference FROM "{table}"')
        ):
            raise RuntimeError("Unverified demo root record detected; reset refused")
    if connection.execute(
        "SELECT count(*) FROM candidates WHERE email IS NOT NULL AND email NOT LIKE '%.invalid'"
    ).fetchone()[0]:
        raise RuntimeError("Non-synthetic contacts detected; reset refused")
    if (
        connection.execute("PRAGMA foreign_key_check").fetchall()
        or connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok"
    ):
        raise RuntimeError("Database integrity failed; reset refused")
    counts, payload = {}, []
    for table in sorted(expected):
        rows = connection.execute(f'SELECT * FROM "{table}" ORDER BY rowid').fetchall()
        counts[table] = len(rows)
        payload.append((table, rows))
    return {
        "counts": counts,
        "fingerprint": hashlib.sha256(json.dumps(payload, default=str).encode()).hexdigest(),
    }


def reset(settings, *, confirmation=None, anchor=None):
    path = Path(resolve_database_url(settings.database_url).database).resolve()
    if not path.is_file():
        raise RuntimeError("Migrate the selected demo database before preview/reset")
    with closing(sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)) as check:
        preview = verify_demo(check, settings, path)
    if confirmation is None:
        return {
            "preview": True,
            "database": str(path),
            **preview,
            "confirmation_required": CONFIRMATION,
        }
    if confirmation != CONFIRMATION:
        raise RuntimeError("Explicit reset confirmation is required")
    anchor = anchor or settings.demo_clock_at or datetime.now(UTC)
    # Build and validate the complete replacement before touching the selected demo.
    with tempfile.TemporaryDirectory(prefix="minori-demo-build-") as directory:
        staged_path = Path(directory) / "stage.db"
        staged_url = "sqlite:///" + staged_path.as_posix()
        previous = {
            name: os.environ.get(name) for name in ("DATABASE_URL", "APP_ENV", "LLM_ENABLED")
        }
        try:
            os.environ.update(DATABASE_URL=staged_url, APP_ENV="test", LLM_ENABLED="false")
            get_settings.cache_clear()
            command.upgrade(Config(str(PROJECT_ROOT / "alembic.ini")), "head")
        finally:
            for name, value in previous.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value
            get_settings.cache_clear()
        stage = Database(
            Settings(_env_file=None, app_env="test", database_url=staged_url, llm_enabled=False)
        )
        try:
            result = seed_professional_demo(
                stage, anchor=anchor, dry_run=settings.notification_dry_run
            )
            repeated = seed_professional_demo(
                stage, anchor=anchor, dry_run=settings.notification_dry_run
            )
            if (
                repeated["counts"] != result["counts"]
                or result["counts"]["candidates"] != 24
                or result["counts"]["placements"] != 8
            ):
                raise RuntimeError("Seed idempotency/count verification failed")
        finally:
            stage.dispose()
        backup_dir = path.parent / "demo-backups"
        backup_dir.mkdir(exist_ok=True)
        backup_path = backup_dir / (datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ") + ".db")
        with (
            closing(sqlite3.connect(path)) as source,
            closing(sqlite3.connect(backup_path)) as backup,
        ):
            source.backup(backup)
        with closing(sqlite3.connect(path, timeout=5)) as target:
            target.execute("PRAGMA foreign_keys=ON")
            target.execute("ATTACH DATABASE ? AS replacement", (str(staged_path),))
            target.execute("BEGIN IMMEDIATE")
            if verify_demo(target, settings, path)["fingerprint"] != preview["fingerprint"]:
                raise RuntimeError("Database changed after preview; reset aborted safely")
            tables = list(Base.metadata.sorted_tables)
            for table in reversed(tables):
                target.execute(f'DELETE FROM "{table.name}"')
            for table in tables:
                target.execute(
                    f'INSERT INTO "{table.name}" SELECT * FROM replacement."{table.name}"'
                )
            if target.execute("PRAGMA foreign_key_check").fetchall():
                raise RuntimeError("Replacement foreign keys failed; transaction rolled back")
            target.commit()
        selected = Database(settings)
        try:
            inspect_database(selected)
        finally:
            selected.dispose()
    return {"reset": True, "backup": str(backup_path), **result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm", choices=[CONFIRMATION])
    parser.add_argument(
        "--anchor", help="ISO timestamp with timezone; never modifies the Windows clock"
    )
    args = parser.parse_args()
    settings = get_settings()
    result = reset(
        settings,
        confirmation=args.confirm,
        anchor=datetime.fromisoformat(args.anchor) if args.anchor else None,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
