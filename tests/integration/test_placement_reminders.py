"""Database/API workflows, quota locking, scheduling, claims, and callback safety."""

import json
import os
import subprocess
import sys
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from minori.api.dependencies import get_placement_service, get_reminder_service
from minori.db.inspection import inspect_database
from minori.db.models import AuditLog, Notification, NotificationAttempt
from minori.db.session import immediate_transaction
from minori.domain.catalogs import (
    AttemptStatus,
    MatchStatus,
    NotificationStatus,
    PlacementStatus,
    PlacementStepStatus,
    PlacementStepType,
)
from minori.domain.entities import MatchData, PlacementStageData
from minori.domain.errors import BusinessConflictError
from minori.domain.operations import record_data
from minori.domain.reminders import DeliveryErrorCode, ReminderPolicy
from minori.main import create_app
from minori.repositories.provider import provide_repositories
from minori.schemas.candidate import CandidateCreate
from minori.schemas.vacancy import VacancyCreate
from minori.services.placements import PlacementService
from minori.services.reminders import ReminderService
from pydantic import SecretStr
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 10, 13, 3, 0, tzinfo=UTC)
TOKEN = "test-only-internal-token-" + "x" * 40


class Scenario:
    def __init__(self, database):
        self.database = database
        self.now = NOW
        self.policy = ReminderPolicy(lease_seconds=30, retry_base_seconds=10, retry_max_seconds=40)

    def services(self, session):
        ports = provide_repositories(session)

        def transaction():
            return immediate_transaction(session)

        reminder = ReminderService(ports, transaction, self.policy, lambda: self.now)
        placement = PlacementService(ports, transaction, reminder, lambda: self.now)
        return placement, reminder

    def call(self, kind, method, *args, **kwargs):
        with self.database.session_factory() as session:
            service = self.services(session)[0 if kind == "placement" else 1]
            return getattr(service, method)(*args, **kwargs)

    def approve(self):
        return self.call(
            "placement",
            "decide",
            self.candidate.id,
            self.vacancy.id,
            MatchStatus.APPROVED,
            "staff.synthetic",
        )

    def place(self):
        match = self.approve()
        return self.call("placement", "create", "DEMO-PLACEMENT-TEST", match.id, "staff.synthetic")

    def schedule(self, *, kind=PlacementStepType.INTERVIEW, delta=timedelta(days=3, hours=4)):
        placement = self.place()
        data = PlacementStageData(
            placement_id=placement.id,
            code=kind.value.upper(),
            step_type=kind,
            sequence_number=1,
            status=PlacementStepStatus.SCHEDULED,
            scheduled_at=self.now + delta,
            location="Ruang Simulasi",
        )
        activity = self.call("placement", "create_activity", placement.id, data, "staff.synthetic")
        rows = self.call("reminder", "list", placement_id=placement.id)
        return placement, activity, rows[0]


@pytest.fixture
def scenario(migrated_database, candidate_payload, vacancy_payload):
    value = Scenario(migrated_database)
    with migrated_database.session_factory.begin() as session:
        ports = provide_repositories(session)
        value.candidate = ports.candidate.create(CandidateCreate(**candidate_payload).to_domain())
        value.vacancy = ports.vacancy.create(VacancyCreate(**vacancy_payload).to_domain())
    return value


def test_human_approval_placement_creation_idempotence_and_audit(scenario):
    with scenario.database.session_factory.begin() as session:
        proposed = provide_repositories(session).match.create(
            MatchData(candidate_id=scenario.candidate.id, vacancy_id=scenario.vacancy.id)
        )
    with pytest.raises(BusinessConflictError, match="approval"):
        scenario.call("placement", "create", "DEMO-PLACEMENT-TEST", proposed.id, "staff.synthetic")
    placement = scenario.place()
    assert scenario.place().id == placement.id
    with scenario.database.session_factory() as session:
        actions = list(session.scalars(select(AuditLog.action)))
    assert actions.count("match.reviewed") == 1
    assert actions.count("placement.created") == 1
    with pytest.raises(BusinessConflictError, match="Cancel"):
        scenario.call(
            "placement",
            "decide",
            scenario.candidate.id,
            scenario.vacancy.id,
            MatchStatus.REJECTED,
            "staff.synthetic",
        )


def test_rejected_and_current_ineligible_candidate_cannot_be_placed(scenario):
    match = scenario.call(
        "placement",
        "decide",
        scenario.candidate.id,
        scenario.vacancy.id,
        MatchStatus.REJECTED,
        "staff.synthetic",
    )
    with pytest.raises(BusinessConflictError):
        scenario.call("placement", "create", "DEMO-PLACEMENT-TEST", match.id, "staff.synthetic")
    match = scenario.approve()
    with scenario.database.session_factory.begin() as session:
        provide_repositories(session).candidate.archive(scenario.candidate.id)
    with pytest.raises(BusinessConflictError, match="eligible"):
        scenario.call("placement", "create", "DEMO-PLACEMENT-TEST", match.id, "staff.synthetic")


def test_capacity_and_one_active_placement_are_enforced(
    scenario, candidate_payload, vacancy_payload
):
    with scenario.database.session_factory.begin() as session:
        ports = provide_repositories(session)
        ports.vacancy.replace(
            scenario.vacancy.id,
            replace(
                record_data(scenario.vacancy, type(VacancyCreate(**vacancy_payload).to_domain())),
                quota=1,
            ),
        )
        other = ports.candidate.create(
            CandidateCreate(**{**candidate_payload, "reference": "DEMO-CAND-OTHER"}).to_domain()
        )
        other_vacancy = ports.vacancy.create(
            VacancyCreate(**{**vacancy_payload, "reference": "DEMO-VAC-OTHER"}).to_domain()
        )
    placement = scenario.place()
    match = scenario.call(
        "placement",
        "decide",
        other.id,
        scenario.vacancy.id,
        MatchStatus.APPROVED,
        "staff.synthetic",
    )
    with pytest.raises(BusinessConflictError, match="capacity"):
        scenario.call("placement", "create", "DEMO-PLACEMENT-OTHER", match.id, "staff.synthetic")
    second = scenario.call(
        "placement",
        "decide",
        scenario.candidate.id,
        other_vacancy.id,
        MatchStatus.APPROVED,
        "staff.synthetic",
    )
    with pytest.raises(BusinessConflictError, match="active placement"):
        scenario.call("placement", "create", "DEMO-PLACEMENT-DUP", second.id, "staff.synthetic")
    scenario.call(
        "placement", "update", placement.id, "staff.synthetic", status=PlacementStatus.CANCELLED
    )
    assert scenario.call("placement", "create", "DEMO-PLACEMENT-OTHER", match.id, "staff.synthetic")


def test_lifecycle_and_document_deadline(scenario):
    placement = scenario.place()
    with pytest.raises(BusinessConflictError):
        scenario.call(
            "placement", "update", placement.id, "staff.synthetic", status=PlacementStatus.COMPLETED
        )
    data = PlacementStageData(
        placement_id=placement.id,
        code="DOCUMENTS",
        step_type=PlacementStepType.DOCUMENTS,
        sequence_number=1,
        status=PlacementStepStatus.SCHEDULED,
        scheduled_at=NOW + timedelta(hours=1),
        due_at=NOW + timedelta(days=7),
    )
    activity = scenario.call("placement", "create_activity", placement.id, data, "staff.synthetic")
    assert scenario.call("reminder", "list", placement_id=placement.id) == []
    scenario.call(
        "placement", "update", placement.id, "staff.synthetic", status=PlacementStatus.IN_PROGRESS
    )
    with pytest.raises(BusinessConflictError, match="outstanding"):
        scenario.call(
            "placement", "update", placement.id, "staff.synthetic", status=PlacementStatus.COMPLETED
        )
    scenario.now += timedelta(hours=2)
    completed = scenario.call(
        "placement",
        "update_activity",
        placement.id,
        activity.id,
        "staff.synthetic",
        status=PlacementStepStatus.COMPLETED,
    )
    assert completed.completed_at == scenario.now
    assert (
        scenario.call(
            "placement", "update", placement.id, "staff.synthetic", status=PlacementStatus.COMPLETED
        ).status
        == PlacementStatus.COMPLETED
    )


def test_reminders_are_idempotent_and_dry_run_has_attempt_history(scenario):
    placement, activity, reminder = scenario.schedule()
    assert reminder.scheduled_at == datetime(2026, 10, 13, 2, 0, tzinfo=UTC)
    for _ in range(2):
        scenario.call("reminder", "generate")
    assert len(scenario.call("reminder", "list", placement_id=placement.id)) == 1
    claimed = scenario.call("reminder", "claim", reminder.id)
    assert claimed["notification"].status == NotificationStatus.PROCESSING
    assert scenario.call("reminder", "claim", reminder.id) is None
    result = scenario.call(
        "reminder", "complete", reminder.id, claimed["claim_token"], simulated=True
    )
    assert result.status == NotificationStatus.SIMULATED and result.sent_at is None
    assert (
        scenario.call(
            "reminder", "complete", reminder.id, claimed["claim_token"], simulated=True
        ).id
        == result.id
    )
    history = scenario.call("reminder", "attempts", reminder.id)
    assert len(history) == 1 and history[0].status == AttemptStatus.SIMULATED
    assert history[0].finished_at == scenario.now


def test_unsent_reschedule_reuses_notification_and_cancels_old_claim(scenario):
    placement, activity, reminder = scenario.schedule()
    claim = scenario.call("reminder", "claim", reminder.id)
    changed = scenario.call(
        "placement",
        "update_activity",
        placement.id,
        activity.id,
        "staff.synthetic",
        scheduled_at=activity.scheduled_at + timedelta(days=2),
    )
    notifications = scenario.call("reminder", "list", placement_id=placement.id)
    assert len(notifications) == 1
    assert notifications[0].id == reminder.id
    assert notifications[0].schedule_revision == changed.schedule_revision == 2
    assert notifications[0].status == NotificationStatus.PENDING
    with pytest.raises(BusinessConflictError):
        scenario.call("reminder", "complete", reminder.id, claim["claim_token"], simulated=True)
    assert scenario.call("reminder", "attempts", reminder.id)[0].error_code == "SCHEDULE_CHANGED"


def test_sent_history_is_preserved_and_change_notice_is_idempotent(scenario):
    placement, activity, reminder = scenario.schedule()
    scenario.call("reminder", "simulate", reminder.id)
    changed = scenario.call(
        "placement",
        "update_activity",
        placement.id,
        activity.id,
        "staff.synthetic",
        scheduled_at=activity.scheduled_at + timedelta(days=2),
    )
    scenario.call("reminder", "generate")
    rows = scenario.call("reminder", "list", placement_id=placement.id)
    assert len(rows) == 3
    assert [row.template_code for row in rows].count("schedule_changed") == 1
    assert scenario.call("reminder", "get", reminder.id).status == NotificationStatus.SIMULATED
    scenario.call(
        "placement",
        "update_activity",
        placement.id,
        changed.id,
        "staff.synthetic",
        status=PlacementStepStatus.CANCELLED,
    )
    rows = scenario.call("reminder", "list", placement_id=placement.id)
    assert len([row for row in rows if row.template_code == "schedule_cancelled"]) == 1
    assert len([row for row in rows if row.status == NotificationStatus.PENDING]) == 1


def test_activity_and_placement_cancellation_stop_pending_reminders(scenario):
    placement, activity, reminder = scenario.schedule()
    scenario.call(
        "placement", "update", placement.id, "staff.synthetic", status=PlacementStatus.CANCELLED
    )
    assert scenario.call("reminder", "get", reminder.id).status == NotificationStatus.CANCELLED
    assert scenario.call("reminder", "claim", reminder.id) is None


def test_medical_h1_catch_up_and_missed_event(scenario):
    placement, activity, reminder = scenario.schedule(
        kind=PlacementStepType.MEDICAL_CHECK, delta=timedelta(hours=4)
    )
    assert reminder.scheduled_at == datetime(2026, 10, 12, 2, tzinfo=UTC)
    assert reminder.available_at == NOW
    scenario.now = activity.scheduled_at
    scenario.call("reminder", "recover")
    assert scenario.call("reminder", "get", reminder.id).status == NotificationStatus.MISSED
    assert scenario.call("reminder", "claim", reminder.id) is None


def test_retry_backoff_exhaustion_and_lease_recovery(scenario):
    _, _, reminder = scenario.schedule()
    first = scenario.call("reminder", "claim", reminder.id)
    failed = scenario.call(
        "reminder",
        "complete",
        reminder.id,
        first["claim_token"],
        error_code=DeliveryErrorCode.PROVIDER_TIMEOUT,
    )
    assert failed.status == NotificationStatus.PENDING and failed.available_at == NOW + timedelta(
        seconds=10
    )
    assert scenario.call("reminder", "claim", reminder.id) is None
    scenario.now += timedelta(seconds=10)
    second = scenario.call("reminder", "claim", reminder.id)
    scenario.now += timedelta(seconds=31)
    assert scenario.call("reminder", "recover")["recovered_count"] == 1
    with pytest.raises(BusinessConflictError):
        scenario.call("reminder", "complete", reminder.id, second["claim_token"], simulated=True)
    scenario.now += timedelta(seconds=20)
    third = scenario.call("reminder", "claim", reminder.id)
    final = scenario.call(
        "reminder",
        "complete",
        reminder.id,
        third["claim_token"],
        error_code=DeliveryErrorCode.PROVIDER_UNAVAILABLE,
    )
    assert final.status == NotificationStatus.FAILED
    assert scenario.call("reminder", "claim", reminder.id) is None
    assert [row.status for row in scenario.call("reminder", "attempts", reminder.id)] == [
        AttemptStatus.FAILED,
        AttemptStatus.ABANDONED,
        AttemptStatus.FAILED,
    ]


def test_invalid_claim_and_delivery_mode_callbacks_are_rejected(scenario):
    _, _, reminder = scenario.schedule()
    claim = scenario.call("reminder", "claim", reminder.id)
    with pytest.raises(BusinessConflictError):
        scenario.call("reminder", "complete", reminder.id, "invalid" * 8, simulated=True)
    with pytest.raises(BusinessConflictError, match="mode"):
        scenario.call("reminder", "complete", reminder.id, claim["claim_token"], simulated=False)
    assert scenario.call("reminder", "get", reminder.id).status == NotificationStatus.PROCESSING


def test_expired_callback_commits_recovery_before_rejecting_old_token(scenario):
    _, _, reminder = scenario.schedule()
    claim = scenario.call("reminder", "claim", reminder.id)
    scenario.now += timedelta(seconds=31)
    with pytest.raises(BusinessConflictError):
        scenario.call("reminder", "complete", reminder.id, claim["claim_token"], simulated=True)
    assert scenario.call("reminder", "get", reminder.id).status == NotificationStatus.PENDING
    assert scenario.call("reminder", "attempts", reminder.id)[0].status == AttemptStatus.ABANDONED


def test_two_independent_processes_cannot_claim_the_same_reminder(scenario, tmp_path):
    _, _, reminder = scenario.schedule()
    barrier = tmp_path / "claim_start"
    code = """
import json, sys, time
from datetime import datetime
from pathlib import Path
from uuid import UUID
from minori.core.config import Settings
from minori.db.session import Database, immediate_transaction
from minori.domain.reminders import ReminderPolicy
from minori.repositories.provider import provide_repositories
from minori.services.reminders import ReminderService
database = Database(Settings(_env_file=None))
while not Path(sys.argv[2]).exists():
    time.sleep(0.01)
with database.session_factory() as session:
    service = ReminderService(provide_repositories(session), lambda: immediate_transaction(session),
                              ReminderPolicy(), lambda: datetime.fromisoformat(sys.argv[3]))
    result = service.claim(UUID(sys.argv[1]))
    print(json.dumps({"claimed": result is not None}))
database.dispose()
"""
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", code, str(reminder.id), str(barrier), NOW.isoformat()],
            cwd=ROOT,
            env=os.environ.copy(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(2)
    ]
    barrier.write_text("ready")
    outputs = []
    try:
        for process in processes:
            stdout, stderr = process.communicate(timeout=30)
            assert process.returncode == 0, stderr
            outputs.append(json.loads(stdout)["claimed"])
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.wait()
    assert sorted(outputs) == [False, True]
    assert len(scenario.call("reminder", "attempts", reminder.id)) == 1


@pytest.fixture
def client(scenario, settings):
    application = create_app(settings.model_copy(update={"internal_api_token": SecretStr(TOKEN)}))

    def placements():
        with scenario.database.session_factory() as session:
            yield scenario.services(session)[0]

    def reminders():
        with scenario.database.session_factory() as session:
            yield scenario.services(session)[1]

    application.dependency_overrides[get_placement_service] = placements
    application.dependency_overrides[get_reminder_service] = reminders
    with TestClient(application) as test_client:
        yield test_client


def test_api_end_to_end_without_n8n(client, scenario):
    headers = {"Authorization": "Bearer " + TOKEN}
    response = client.post(
        "/matching/decisions",
        headers=headers,
        json={
            "candidate_id": str(scenario.candidate.id),
            "vacancy_id": str(scenario.vacancy.id),
            "decision": "approved",
            "actor_reference": "staff.synthetic",
        },
    )
    assert response.status_code == 200, response.text
    placement = client.post(
        "/placements",
        headers=headers,
        json={
            "reference": "DEMO-PLACEMENT-API",
            "match_id": response.json()["id"],
            "actor_reference": "staff.synthetic",
        },
    )
    assert placement.status_code == 200, placement.text
    identifier = placement.json()["id"]
    activity = client.post(
        f"/placements/{identifier}/activities",
        headers=headers,
        json={
            "actor_reference": "staff.synthetic",
            "code": "INTERVIEW",
            "step_type": "interview",
            "sequence_number": 1,
            "scheduled_at": (NOW + timedelta(days=3, hours=4)).isoformat(),
        },
    )
    assert activity.status_code == 200, activity.text
    assert client.post("/internal/reminders/generate", headers=headers).status_code == 200
    due = client.get("/internal/reminders/due", headers=headers)
    assert len(due.json()) == 1
    claim = client.post("/internal/reminders/claim", headers=headers, json={})
    assert claim.status_code == 200, claim.text
    claimed = claim.json()
    reminder_id = claimed["notification"]["id"]
    assert "claim_token_hash" not in claimed["notification"]
    completed = client.post(
        f"/internal/reminders/{reminder_id}/complete",
        headers=headers,
        json={"claim_token": claimed["claim_token"], "outcome": "simulated"},
    )
    assert completed.status_code == 200 and completed.json()["status"] == "simulated"
    attempts = client.get(f"/reminders/{reminder_id}/attempts")
    assert attempts.json()[0]["status"] == "simulated"
    assert "claim_token_hash" not in attempts.json()[0]
    changed = client.patch(
        f"/placements/{identifier}/activities/{activity.json()['id']}",
        headers=headers,
        json={
            "actor_reference": "staff.synthetic",
            "scheduled_at": (NOW + timedelta(days=5)).isoformat(),
        },
    )
    assert changed.status_code == 200, changed.text
    medical = client.post(
        f"/placements/{identifier}/activities",
        headers=headers,
        json={
            "actor_reference": "staff.synthetic",
            "code": "MEDICAL",
            "step_type": "medical_check",
            "sequence_number": 2,
            "scheduled_at": (NOW + timedelta(hours=5)).isoformat(),
        },
    )
    assert medical.status_code == 200, medical.text
    simulated = client.post("/internal/reminders/simulate", headers=headers, json={})
    assert simulated.status_code == 200
    assert (
        client.get("/placements", params={"query": "DEMO-PLACEMENT-API"}).json()[0]["id"]
        == identifier
    )
    assert client.get("/audit-logs").status_code == 200
    assert inspect_database(scenario.database)["integrity"] == "ok"


@pytest.mark.parametrize(
    "path,method,payload",
    [
        ("/internal/reminders/claim", "post", {}),
        ("/internal/reminders/generate", "post", None),
        ("/internal/reminders/recover", "post", None),
        ("/internal/reminders/simulate", "post", {}),
        ("/internal/reminders/due", "get", None),
        (
            f"/internal/reminders/{uuid4()}/complete",
            "post",
            {"claim_token": "x" * 40, "outcome": "simulated"},
        ),
        (
            f"/internal/reminders/{uuid4()}/fail",
            "post",
            {"claim_token": "x" * 40, "error_code": "PROVIDER_TIMEOUT"},
        ),
    ],
)
def test_internal_api_authentication(client, path, method, payload):
    kwargs = {"json": payload} if payload is not None else {}
    assert getattr(client, method)(path, **kwargs).status_code == 401
    assert (
        getattr(client, method)(
            path, headers={"Authorization": "Bearer invalid"}, **kwargs
        ).status_code
        == 401
    )


def test_api_validates_unknown_inputs_and_sanitized_error_codes(client):
    headers = {"Authorization": "Bearer " + TOKEN}
    assert (
        client.post(
            "/internal/reminders/claim", headers=headers, json={"notification_id": "bad"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/internal/reminders/{uuid4()}/fail",
            headers=headers,
            json={"claim_token": "x" * 40, "error_code": "private SQL or patient diagnosis"},
        ).status_code
        == 422
    )
    assert client.get(f"/placements/{uuid4()}").status_code == 404
    assert client.get("/placements", params={"limit": 101}).status_code == 422
    assert client.get("/reminders", params={"due_before": "2026-01-01T00:00:00"}).status_code == 422


def test_missing_internal_token_fails_closed(scenario, settings):
    with TestClient(create_app(settings)) as client:
        assert client.post("/internal/reminders/claim", json={}).status_code == 503


def test_audit_failure_rolls_back_schedule_and_reminder(scenario, monkeypatch):
    placement = scenario.place()
    with scenario.database.session_factory() as session:
        service, _ = scenario.services(session)

        def fail(*args, **kwargs):
            raise RuntimeError("Synthetic audit failure")

        monkeypatch.setattr(service.ports.audit_log, "append", fail)
        with pytest.raises(RuntimeError):
            service.create_activity(
                placement.id,
                PlacementStageData(
                    placement_id=placement.id,
                    code="INTERVIEW",
                    step_type=PlacementStepType.INTERVIEW,
                    sequence_number=1,
                    status=PlacementStepStatus.SCHEDULED,
                    scheduled_at=NOW + timedelta(days=3),
                ),
                "staff.synthetic",
            )
    assert scenario.call("placement", "activities", placement.id) == []
    with scenario.database.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Notification)) == 0
        assert session.scalar(select(func.count()).select_from(NotificationAttempt)) == 0
        assert session.execute(text("PRAGMA foreign_key_check")).all() == []


def test_inactive_candidate_invalidates_due_reminders(scenario):
    _, _, reminder = scenario.schedule()
    with scenario.database.session_factory.begin() as session:
        provide_repositories(session).candidate.archive(scenario.candidate.id)
    assert scenario.call("reminder", "due") == []
    assert scenario.call("reminder", "get", reminder.id).status == NotificationStatus.CANCELLED


def test_pending_activity_can_be_scheduled_then_cannot_start_early(scenario):
    placement = scenario.place()
    activity = scenario.call(
        "placement",
        "create_activity",
        placement.id,
        PlacementStageData(
            placement_id=placement.id,
            code="INTERVIEW",
            step_type=PlacementStepType.INTERVIEW,
            sequence_number=1,
        ),
        "staff.synthetic",
    )
    scheduled = scenario.call(
        "placement",
        "update_activity",
        placement.id,
        activity.id,
        "staff.synthetic",
        scheduled_at=NOW + timedelta(days=3),
    )
    assert scheduled.status == PlacementStepStatus.SCHEDULED
    with pytest.raises(BusinessConflictError, match="before"):
        scenario.call(
            "placement",
            "update_activity",
            placement.id,
            activity.id,
            "staff.synthetic",
            status=PlacementStepStatus.IN_PROGRESS,
        )
    with pytest.raises(BusinessConflictError, match="Completion"):
        scenario.call(
            "placement",
            "update_activity",
            placement.id,
            activity.id,
            "staff.synthetic",
            status=PlacementStepStatus.COMPLETED,
        )


def test_real_delivery_acknowledgement_requires_explicit_mode_and_provider_reference(scenario):
    scenario.policy = replace(scenario.policy, dry_run=False)
    _, _, reminder = scenario.schedule()
    with pytest.raises(BusinessConflictError, match="dry-run"):
        scenario.call("reminder", "simulate", reminder.id)
    claimed = scenario.call("reminder", "claim", reminder.id)
    with pytest.raises(BusinessConflictError, match="reference"):
        scenario.call("reminder", "complete", reminder.id, claimed["claim_token"])
    result = scenario.call(
        "reminder",
        "complete",
        reminder.id,
        claimed["claim_token"],
        provider_reference="synthetic-provider-ack",
    )
    assert result.status == NotificationStatus.SENT and result.sent_at == NOW
    assert scenario.call("reminder", "attempts", reminder.id)[0].status == AttemptStatus.SUCCEEDED


def test_simulation_never_claims_a_real_delivery_notification(scenario):
    scenario.policy = replace(scenario.policy, dry_run=False)
    _, _, reminder = scenario.schedule()
    scenario.policy = replace(scenario.policy, dry_run=True)
    assert scenario.call("reminder", "simulate", reminder.id) is None
    assert scenario.call("reminder", "get", reminder.id).attempt_count == 0


def test_new_queue_constraints_are_enforced_by_sqlite(scenario):
    _, activity, reminder = scenario.schedule()
    scenario.call("reminder", "claim", reminder.id)
    with scenario.database.session_factory.begin() as session:
        for statement in (
            "UPDATE notifications SET lease_expires_at = claimed_at",
            "UPDATE notifications SET attempt_count = -1",
            "UPDATE notifications SET status = 'invalid'",
            "UPDATE notification_attempts SET status = 'succeeded'",
            "UPDATE notification_attempts SET error_code = 'UNSAFE'",
            "UPDATE placement_stages SET schedule_revision = 0",
        ):
            with pytest.raises(IntegrityError), session.begin_nested():
                session.execute(text(statement))


def test_reminder_migration_preserves_legacy_rows_and_relations(seeded_database):
    configuration = Config(str(ROOT / "alembic.ini"))
    before = inspect_database(seeded_database)
    with seeded_database.engine.connect() as connection:
        notifications = connection.execute(
            text("SELECT id, status, sent_at FROM notifications ORDER BY id")
        ).all()
        attempts = connection.execute(
            text("SELECT id, notification_id, status FROM notification_attempts ORDER BY id")
        ).all()
    command.downgrade(configuration, "explainable_matching")
    command.upgrade(configuration, "head")
    assert inspect_database(seeded_database)["counts"] == before["counts"]
    with seeded_database.engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT id, status, sent_at FROM notifications ORDER BY id")
            ).all()
            == notifications
        )
        assert (
            connection.execute(
                text("SELECT id, notification_id, status FROM notification_attempts ORDER BY id")
            ).all()
            == attempts
        )
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
    command.check(configuration)


def test_reminder_history_downgrade_is_refused_atomically(scenario):
    scenario.schedule()
    before = inspect_database(scenario.database)
    with pytest.raises(RuntimeError, match="Refusing downgrade"):
        command.downgrade(Config(str(ROOT / "alembic.ini")), "explainable_matching")
    assert inspect_database(scenario.database) == before


def test_two_processes_competing_for_last_vacancy_seat_cannot_overbook(
    scenario, candidate_payload, tmp_path
):
    with scenario.database.session_factory.begin() as session:
        ports = provide_repositories(session)
        from minori.domain.entities import VacancyData

        ports.vacancy.replace(
            scenario.vacancy.id, replace(record_data(scenario.vacancy, VacancyData), quota=1)
        )
        other = ports.candidate.create(
            CandidateCreate(**{**candidate_payload, "reference": "DEMO-CAND-COMPETING"}).to_domain()
        )
    first = scenario.approve()
    second = scenario.call(
        "placement",
        "decide",
        other.id,
        scenario.vacancy.id,
        MatchStatus.APPROVED,
        "staff.synthetic",
    )
    barrier = tmp_path / "capacity_start"
    code = """
import json, sys, time
from datetime import datetime
from pathlib import Path
from uuid import UUID
from minori.core.config import Settings
from minori.db.session import Database, immediate_transaction
from minori.domain.errors import BusinessConflictError
from minori.domain.reminders import ReminderPolicy
from minori.repositories.provider import provide_repositories
from minori.services.placements import PlacementService
from minori.services.reminders import ReminderService
database = Database(Settings(_env_file=None))
while not Path(sys.argv[3]).exists():
    time.sleep(0.01)
with database.session_factory() as session:
    ports = provide_repositories(session)
    transaction = lambda: immediate_transaction(session)
    now = lambda: datetime.fromisoformat(sys.argv[4])
    reminders = ReminderService(ports, transaction, ReminderPolicy(), now)
    service = PlacementService(ports, transaction, reminders, now)
    try:
        service.create(sys.argv[2], UUID(sys.argv[1]), "staff.synthetic")
        print(json.dumps({"created": True}))
    except BusinessConflictError:
        print(json.dumps({"created": False}))
database.dispose()
"""
    processes = [
        subprocess.Popen(
            [
                sys.executable,
                "-c",
                code,
                str(match.id),
                f"DEMO-PLACEMENT-{index}",
                str(barrier),
                NOW.isoformat(),
            ],
            cwd=ROOT,
            env=os.environ.copy(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for index, match in enumerate((first, second))
    ]
    barrier.write_text("ready")
    outputs = []
    try:
        for process in processes:
            stdout, stderr = process.communicate(timeout=30)
            assert process.returncode == 0, stderr
            outputs.append(json.loads(stdout)["created"])
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.wait()
    assert sorted(outputs) == [False, True]
    assert len(scenario.call("placement", "list")) == 1
