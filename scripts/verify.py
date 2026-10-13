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
        ("database", [sys.executable, str(ROOT / "scripts/check_database.py")]),
    ]
    records = []
    for name, command in checks:
        print(f"Running {name}...", flush=True)
        completed = subprocess.run(
            command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        output = completed.stdout + completed.stderr
        (results / f"{name}.log").write_text(output, encoding="utf-8")
        print(output, end="")
        records.append(
            {
                "name": name,
                "command": command[1:],
                "exit_code": completed.returncode,
                "log": f"{name}.log",
            }
        )
    passed = all(record["exit_code"] == 0 for record in records)
    (results / "checks.json").write_text(
        json.dumps(
            {
                "executed_at": datetime.now(timezone(timedelta(hours=7))).isoformat(),
                "python_version": sys.version.split()[0],
                "passed": passed,
                "checks": records,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
