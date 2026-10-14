"""Run the complete reminder scenario over real HTTP with an isolated SQLite database."""

import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from alembic import command
from alembic.config import Config
from minori.core.config import PROJECT_ROOT, Settings, get_settings
from minori.db.inspection import inspect_database
from minori.db.session import Database
from minori.repositories.provider import provide_repositories
from minori.schemas.candidate import CandidateCreate
from minori.schemas.vacancy import VacancyCreate


def run_scenario(client, candidate_id, vacancy_id):
    actor = "staff.simulation"
    now = datetime.now(UTC)
    zone = ZoneInfo("Asia/Jakarta")
    local = now.astimezone(zone)
    # Before 09:00 use a late catch-up reminder, so the demo is executable at any hour.
    days = 3 if local.hour >= 9 else 2
    interview = (local + timedelta(days=days)).replace(hour=14, minute=0, second=0, microsecond=0)

    def request(method, path, payload=None, **kwargs):
        response = client.request(method, path, json=payload, **kwargs)
        if response.status_code != 200:
            raise RuntimeError(f"Unexpected HTTP {response.status_code}: {method} {path}")
        return response.json()

    match = request(
        "POST",
        "/matching/decisions",
        {
            "candidate_id": str(candidate_id),
            "vacancy_id": str(vacancy_id),
            "decision": "approved",
            "actor_reference": actor,
        },
    )
    placement = request(
        "POST",
        "/placements",
        {"reference": "DEMO-PLACEMENT-REMINDER", "match_id": match["id"], "actor_reference": actor},
    )
    base = f"/placements/{placement['id']}/activities"
    activity = request(
        "POST",
        base,
        {
            "code": "INTERVIEW",
            "step_type": "interview",
            "sequence_number": 1,
            "scheduled_at": interview.isoformat(),
            "location": "Ruang Contoh",
            "actor_reference": actor,
        },
    )
    first = request("POST", "/internal/reminders/generate")
    second = request("POST", "/internal/reminders/generate")
    assert [row["id"] for row in first] == [row["id"] for row in second]
    due = request("GET", "/internal/reminders/due")
    assert len(due) == 1 and due[0]["template_code"] == "interview_h3"
    reminder = due[0]
    claim = request("POST", "/internal/reminders/claim", {"notification_id": reminder["id"]})
    assert claim and claim["notification"]["status"] == "processing"
    assert request("POST", "/internal/reminders/claim", {"notification_id": reminder["id"]}) is None
    result = request(
        "POST",
        f"/internal/reminders/{reminder['id']}/complete",
        {"claim_token": claim["claim_token"], "outcome": "simulated"},
    )
    assert result["status"] == "simulated" and result["sent_at"] is None
    history = request("GET", f"/reminders/{reminder['id']}/attempts")
    assert len(history) == 1 and history[0]["status"] == "simulated"
    changed = request(
        "PATCH",
        f"{base}/{activity['id']}",
        {"actor_reference": actor, "scheduled_at": (interview + timedelta(days=2)).isoformat()},
    )
    repeat = request(
        "PATCH",
        f"{base}/{activity['id']}",
        {"actor_reference": actor, "scheduled_at": (interview + timedelta(days=2)).isoformat()},
    )
    assert changed["schedule_revision"] == repeat["schedule_revision"] == 2
    rows = request("GET", "/reminders", params={"placement_id": placement["id"]})
    assert (
        len(
            [
                row
                for row in rows
                if row["template_code"] == "interview_h3" and row["status"] == "pending"
            ]
        )
        == 1
    )
    medical_at = now + timedelta(hours=2)
    medical = request(
        "POST",
        base,
        {
            "code": "MEDICAL",
            "step_type": "medical_check",
            "sequence_number": 2,
            "scheduled_at": medical_at.isoformat(),
            "actor_reference": actor,
        },
    )
    rows = request("GET", "/reminders", params={"placement_id": placement["id"]})
    medical_row = next(row for row in rows if row["template_code"] == "medical_h1")
    simulated = request(
        "POST", "/internal/reminders/simulate", {"notification_id": medical_row["id"]}
    )
    assert simulated["status"] == "simulated"
    all_attempts = request("GET", f"/reminders/{medical_row['id']}/attempts")
    activities = request("GET", base)
    audit = request("GET", "/audit-logs")
    return {
        "passed": True,
        "transport": "real HTTP",
        "dry_run": True,
        "staff_decision": match["status"],
        "placement_status": placement["status"],
        "interview_reminder_at": reminder["scheduled_at"],
        "interview_status": result["status"],
        "interview_attempts": len(history),
        "schedule_revision": changed["schedule_revision"],
        "pending_interview_count": 1,
        "medical_reminder_at": medical_row["scheduled_at"],
        "medical_status": simulated["status"],
        "medical_attempts": len(all_attempts),
        "activity_count": len(activities),
        "audit_count": len(audit),
        "api_history_verified": True,
        "claim_exclusivity_verified": True,
        "generation_idempotent": True,
        "medical_activity_id": medical["id"],
    }


def main():
    if get_settings().app_env == "production":
        raise SystemExit("Reminder verification is restricted to development and test")
    with tempfile.TemporaryDirectory(prefix="minori-reminders-") as directory:
        path = Path(directory)
        url = "sqlite:///" + (path / "simulation.db").as_posix()
        token = secrets.token_urlsafe(48)
        environment = {
            **os.environ,
            "DATABASE_URL": url,
            "APP_ENV": "test",
            "LLM_ENABLED": "false",
            "DEMO_CLOCK_AT": "",
            "INTERNAL_API_TOKEN": token,
            "NOTIFICATION_DRY_RUN": "true",
            "BUSINESS_TIMEZONE": "Asia/Jakarta",
            "REMINDER_DELIVERY_TIME": "09:00",
        }
        # Alembic uses process environment; restore every changed setting after verification.
        previous = {
            key: os.environ.get(key)
            for key in environment
            if os.environ.get(key) != environment[key]
        }
        os.environ.update(environment)
        get_settings.cache_clear()
        database = None
        process = None
        try:
            command.upgrade(Config(str(PROJECT_ROOT / "alembic.ini")), "head")
            database = Database(Settings(_env_file=None))
            candidate = json.loads((PROJECT_ROOT / "data/dummy/candidates.json").read_text())[
                "candidates"
            ][0]
            vacancy = json.loads((PROJECT_ROOT / "data/dummy/vacancies.json").read_text())[
                "vacancies"
            ][0]
            candidate["reference"] = "DEMO-CAND-REMINDER"
            vacancy["reference"] = "DEMO-VAC-REMINDER"
            vacancy["application_deadline"] = (datetime.now(UTC) + timedelta(days=365)).isoformat()
            with database.session_factory.begin() as session:
                ports = provide_repositories(session)
                candidate = ports.candidate.create(CandidateCreate(**candidate).to_domain())
                vacancy = ports.vacancy.create(VacancyCreate(**vacancy).to_domain())
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                port = listener.getsockname()[1]
            with (path / "server.log").open("w", encoding="utf-8") as log:
                process = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "uvicorn",
                        "minori.main:create_app",
                        "--factory",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(port),
                    ],
                    cwd=PROJECT_ROOT,
                    env=environment,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                )
                with httpx.Client(
                    base_url=f"http://127.0.0.1:{port}",
                    timeout=15,
                    headers={"Authorization": "Bearer " + token},
                ) as client:
                    deadline = time.monotonic() + 30
                    while True:
                        if process.poll() is not None:
                            raise RuntimeError("Simulation backend exited before readiness")
                        try:
                            if client.get("/health").status_code == 200:
                                break
                        except httpx.TransportError:
                            pass
                        if time.monotonic() >= deadline:
                            raise RuntimeError("Simulation backend readiness timed out")
                        time.sleep(0.1)
                    report = run_scenario(client, candidate.id, vacancy.id)
                    report["database"] = inspect_database(database)
                    print(json.dumps(report, indent=2, default=str))
        finally:
            if process is not None:
                if os.name == "nt":
                    # The Windows venv launcher can leave its Python child holding server.log.
                    # Stop only the process tree launched by this verification run.
                    subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        capture_output=True,
                        check=False,
                    )
                else:
                    process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            if database is not None:
                database.dispose()
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            get_settings.cache_clear()


if __name__ == "__main__":
    main()
