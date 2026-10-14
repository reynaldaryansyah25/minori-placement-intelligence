"""Candidate -> live matching -> explicit approval -> placement -> approved activity email."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from minori.api.dependencies import get_matching_service
from minori.core.config import Settings
from minori.db.models import Notification
from minori.main import create_app
from sqlalchemy import update

NOW = datetime(2026, 10, 14, 5, tzinfo=UTC)
TOKEN = "synthetic-recruitment-flow-token-" + "x" * 32


@pytest.fixture
def flow_client(settings, migrated_database):
    configured = Settings(
        _env_file=None,
        **{
            **settings.model_dump(),
            "internal_api_token": TOKEN,
            "reviewer_api_token": "synthetic-flow-reviewer",
            "demo_clock_at": NOW,
        },
    )
    with TestClient(create_app(configured), headers={"Authorization": "Bearer " + TOKEN}) as client:
        yield client


def create_pair(client, candidate_payload, vacancy_payload):
    vacancy = deepcopy(vacancy_payload)
    vacancy.update(
        reference="DEMO-FLOW-VAC",
        quota=3,
        application_deadline=(NOW + timedelta(days=90)).isoformat(),
    )
    response = client.post("/vacancies", json=vacancy)
    assert response.status_code == 201
    vacancy = response.json()
    candidate = deepcopy(candidate_payload)
    candidate.update(reference="DEMO-FLOW-CAND", full_name="Peserta Uji Alur Sintetis")
    response = client.post("/candidates", json=candidate)
    assert response.status_code == 201
    return response.json(), vacancy


def place(client, candidate, vacancy):
    decision = client.post(
        "/matching/decisions",
        json={
            "candidate_id": candidate["id"],
            "vacancy_id": vacancy["id"],
            "decision": "approved",
            "actor_reference": "staff.synthetic",
        },
    )
    assert decision.status_code == 200
    waiting = client.get("/placements/approved-candidates").json()
    assert len(waiting) == 1 and waiting[0]["can_start"]
    response = client.post(
        "/placements",
        json={
            "reference": "DEMO-FLOW-PLC",
            "match_id": decision.json()["id"],
            "actor_reference": "staff.synthetic",
        },
    )
    assert response.status_code == 200
    assert client.get("/placements/approved-candidates").json() == []
    return response.json()


def test_candidate_write_refreshes_matching_but_never_approves_or_places(
    flow_client, candidate_payload, vacancy_payload
):
    client = flow_client
    candidate, vacancy = create_pair(client, candidate_payload, vacancy_payload)
    results = client.get("/matching/results", params={"candidate_id": candidate["id"]}).json()
    assert len(results) == 1 and results[0]["eligibility_status"] == "ELIGIBLE"
    assert results[0]["staff_status"] == "proposed"
    assert client.get("/placements").json() == []
    assert client.get("/placements/approved-candidates").json() == []
    incomplete = {
        **candidate_payload,
        "reference": "DEMO-FLOW-INCOMPLETE",
        "language_tests": [],
        "certifications": [],
        "experiences": [],
    }
    new = client.post("/candidates", json=incomplete).json()
    current = client.get(f"/matching/vacancies/{vacancy['id']}/candidates").json()
    assert {row["candidate_id"] for row in current} == {candidate["id"], new["id"]}
    assert (
        next(row for row in current if row["candidate_id"] == new["id"])["eligibility_status"]
        != "ELIGIBLE"
    )
    updated = client.put(
        f"/candidates/{new['id']}", json={**candidate_payload, "reference": incomplete["reference"]}
    )
    assert updated.status_code == 200
    latest = client.get("/matching/results", params={"candidate_id": new["id"]}).json()[0]
    assert latest["eligibility_status"] == "ELIGIBLE" and latest["staff_status"] == "proposed"
    place(client, candidate, vacancy)


def test_candidate_and_automatic_evaluation_rollback_together(
    flow_client, vacancy_payload, candidate_payload
):
    client = flow_client
    assert client.post("/vacancies", json=vacancy_payload).status_code == 201

    class BrokenMatching:
        def refresh_candidate(self, identifier):
            raise ValueError("Synthetic matching failure")

    client.app.dependency_overrides[get_matching_service] = lambda: BrokenMatching()
    assert client.post("/candidates", json=candidate_payload).status_code == 422
    assert client.get("/candidates").json() == []


@pytest.mark.parametrize(
    "kind", ["interview", "medical_check", "documents", "orientation", "departure"]
)
def test_every_activity_email_requires_review_and_uses_existing_queue(
    flow_client, migrated_database, candidate_payload, vacancy_payload, kind
):
    client = flow_client
    candidate, vacancy = create_pair(client, candidate_payload, vacancy_payload)
    placement = place(client, candidate, vacancy)
    activity = client.post(
        f"/placements/{placement['id']}/activities",
        json={
            "code": "DEMO_FLOW_ACTIVITY",
            "step_type": kind,
            "sequence_number": 1,
            "scheduled_at": (NOW + timedelta(days=7)).isoformat(),
            "location": "Ruang Uji Sintetis",
            "actor_reference": "staff.synthetic",
        },
    ).json()
    path = f"/placements/{placement['id']}/activities/{activity['id']}/email/prepare"
    denied = client.post(path, headers={"Authorization": "Bearer synthetic-flow-reviewer"})
    assert denied.status_code == 403
    response = client.post(path)
    assert response.status_code == 200
    reminder = response.json()
    assert client.post(path).json()["id"] == reminder["id"]
    assert (
        client.post("/internal/reminders/claim", json={"notification_id": reminder["id"]}).json()
        is None
    )
    if kind in {"documents", "orientation", "departure"}:
        # Defense in depth: even an accidentally early availability cannot send an unapproved manual message.
        with migrated_database.session_factory.begin() as session:
            session.execute(
                update(Notification)
                .where(Notification.id == UUID(reminder["id"]))
                .values(available_at=NOW)
            )
        assert reminder["id"] not in {
            row["id"] for row in client.get("/internal/reminders/due").json()
        }
        assert (
            client.post(
                "/internal/reminders/claim", json={"notification_id": reminder["id"]}
            ).json()
            is None
        )
    preview = client.get(f"/reminders/{reminder['id']}/email/template").json()
    assert "WIB" in preview["body"] and "Ruang Uji Sintetis" in preview["body"]
    payload = {
        "subject": preview["subject"],
        "body": preview["body"] + "\nDitinjau staf.",
        "facts_fingerprint": preview["facts_fingerprint"],
        "idempotency_key": uuid4().hex,
        "confirmed": False,
    }
    approval = f"/reminders/{reminder['id']}/email/approve"
    assert client.post(approval, json=payload).status_code == 422
    payload["confirmed"] = True
    assert client.post(approval, json=payload).status_code == 200
    assert client.post(approval, json=payload).status_code == 200
    claimed = client.post(
        "/internal/reminders/claim", json={"notification_id": reminder["id"]}
    ).json()
    assert claimed["message"]["body"] == payload["body"]
    assert claimed["notification"]["dry_run"] is True
    assert claimed["recipient_routing"]["delivery_allowed"] is False
    callback = {"claim_token": claimed["claim_token"], "outcome": "simulated"}
    assert (
        client.post(f"/internal/reminders/{reminder['id']}/complete", json=callback).json()[
            "status"
        ]
        == "simulated"
    )
    assert client.post(path).status_code == 409
