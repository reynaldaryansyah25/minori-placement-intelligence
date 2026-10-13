"""Sequential idempotence, atomic failure, preservation, and installed entry points."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from minori.db.inspection import inspect_database
from minori.db.models import MODEL_TYPES, Candidate
from minori.db.seeding import seed_database
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[2]


def identities(database):
    with database.session_factory() as session:
        return {
            model.__tablename__: set(session.scalars(select(model.id))) for model in MODEL_TYPES
        }


def test_seed_twice_preserves_all_ids_counts_and_user_edits(migrated_database):
    first = seed_database(migrated_database)
    original_ids = identities(migrated_database)
    with migrated_database.session_factory.begin() as session:
        candidate = session.scalar(select(Candidate).where(Candidate.reference == "DEMO-CAND-AGRI"))
        candidate.full_name = "Nama Fiktif Hasil Penyuntingan"
    second = seed_database(migrated_database)
    assert first["inserted_records"] == 35
    assert second["inserted_records"] == 0
    assert second["preserved_records"] == 35
    assert second["counts"] == first["counts"]
    assert identities(migrated_database) == original_ids
    assert second["counts"]["candidates"] == 8
    assert second["counts"]["vacancies"] == 5
    assert second["counts"]["placement_stages"] == 8
    with migrated_database.session_factory() as session:
        assert (
            session.scalar(
                select(Candidate.full_name).where(Candidate.reference == "DEMO-CAND-AGRI")
            )
            == "Nama Fiktif Hasil Penyuntingan"
        )


def test_seed_failure_rolls_back_every_insert(migrated_database, tmp_path):
    target = tmp_path / "bad-fixtures"
    shutil.copytree(ROOT / "data/dummy", target)
    path = target / "placement_data.json"
    payload = json.loads(path.read_text())
    payload["steps"][0]["sequence_number"] = 0
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        seed_database(migrated_database, target)
    assert all(value == 0 for value in inspect_database(migrated_database)["counts"].values())


def test_seed_rejects_non_synthetic_envelope(migrated_database, tmp_path):
    target = tmp_path / "bad-fixtures"
    shutil.copytree(ROOT / "data/dummy", target)
    path = target / "candidates.json"
    payload = json.loads(path.read_text())
    payload["synthetic"] = False
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        seed_database(migrated_database, target)


def test_duplicate_fixture_references_are_rejected_before_writes(migrated_database, tmp_path):
    target = tmp_path / "duplicate-fixtures"
    shutil.copytree(ROOT / "data/dummy", target)
    path = target / "candidates.json"
    payload = json.loads(path.read_text())
    payload["candidates"][1]["reference"] = payload["candidates"][0]["reference"]
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="unique DEMO"):
        seed_database(migrated_database, target)
    assert all(value == 0 for value in inspect_database(migrated_database)["counts"].values())


def test_seed_cli_is_idempotent_and_works_from_any_working_directory(migrated_database, tmp_path):
    outcomes = []
    for _ in range(2):
        completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts/seed_database.py")],
            cwd=tmp_path,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
        outcomes.append(json.loads(completed.stdout))
    assert outcomes[0]["counts"] == outcomes[1]["counts"]
    assert outcomes[1]["inserted_records"] == 0
