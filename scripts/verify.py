"""Run reproducible foundation checks and preserve real command results."""

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    results = ROOT / "test-results"
    results.mkdir(exist_ok=True)
    checks = [
        ("dependencies", [sys.executable, "-m", "pip", "check"]),
        ("lint", [sys.executable, "-m", "ruff", "check", "."]),
        ("format", [sys.executable, "-m", "ruff", "format", "--check", "."]),
        (
            "tests",
            [
                sys.executable,
                "-m",
                "pytest",
                "--junitxml=test-results/pytest.xml",
                "--cov",
                "--cov-report=term-missing",
                "--cov-report=xml:test-results/coverage.xml",
                "--cov-report=html:test-results/coverage",
            ],
        ),
        ("migration", [sys.executable, "-m", "alembic", "upgrade", "head"]),
        ("migration_drift", [sys.executable, "-m", "alembic", "check"]),
        ("seed_initial", [sys.executable, str(ROOT / "scripts/seed_database.py")]),
        ("seed_repeat", [sys.executable, str(ROOT / "scripts/seed_database.py")]),
        ("database", [sys.executable, str(ROOT / "scripts/check_database.py")]),
        ("matching", [sys.executable, str(ROOT / "scripts/verify_matching.py")]),
        ("reminders", [sys.executable, str(ROOT / "scripts/verify_reminders.py")]),
    ]
    records = []
    seed_results = {}
    for name, command in checks:
        print(f"Running {name}...", flush=True)
        completed = subprocess.run(
            command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        output = completed.stdout + completed.stderr
        (results / f"{name}.log").write_text(output, encoding="utf-8")
        print(output, end="")
        if name in {"seed_initial", "seed_repeat"} and completed.returncode == 0:
            seed_results[name] = json.loads(completed.stdout)
        records.append(
            {
                "name": name,
                "command": command[1:],
                "exit_code": completed.returncode,
                "log": f"{name}.log",
            }
        )
    passed = all(record["exit_code"] == 0 for record in records)
    idempotent = (
        len(seed_results) == 2
        and seed_results["seed_initial"]["counts"] == seed_results["seed_repeat"]["counts"]
        and seed_results["seed_repeat"]["inserted_records"] == 0
    )
    passed = passed and idempotent
    (results / "checks.json").write_text(
        json.dumps(
            {
                "executed_at": datetime.now(timezone(timedelta(hours=7))).isoformat(),
                "python_version": sys.version.split()[0],
                "passed": passed,
                "seed_idempotent": idempotent,
                "checks": records,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
