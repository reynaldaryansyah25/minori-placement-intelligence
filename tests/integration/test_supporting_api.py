"""Test supporting backend APIs: candidates, vacancies, drafts, overview, auth, and RBAC."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from minori.main import create_app
from pydantic import SecretStr

AS_OF = datetime(2026, 10, 13, 0, 0, tzinfo=UTC)
ADMIN_TOKEN = "test-internal-token-secret-12345"
REVIEWER_TOKEN = "test-reviewer-token-secret-67890"


@pytest.fixture
def auth_settings(settings):
    return settings.model_copy(
        update={
            "internal_api_token": SecretStr(ADMIN_TOKEN),
            "reviewer_api_token": SecretStr(REVIEWER_TOKEN),
            "app_env": "production",  # enforce auth
        }
    )


@pytest.fixture
def auth_client(seeded_database, auth_settings):
    with TestClient(create_app(auth_settings)) as client:
        yield client


def test_auth_me_endpoint(auth_client):
    # Missing token -> 401
    resp = auth_client.get("/auth/me")
    assert resp.status_code == 401

    # Invalid token -> 401
    resp = auth_client.get("/auth/me", headers={"Authorization": "Bearer bad-token"})
    assert resp.status_code == 401

    # Reviewer token -> role=reviewer
    resp = auth_client.get("/auth/me", headers={"Authorization": f"Bearer {REVIEWER_TOKEN}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "reviewer"
    assert data["can_write"] is False

    # Admin token -> role=admin
    resp = auth_client.get("/auth/me", headers={"Authorization": f"Bearer {ADMIN_TOKEN}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "admin"
    assert data["can_write"] is True


def test_overview_summary_endpoint(auth_client):
    headers = {"Authorization": f"Bearer {REVIEWER_TOKEN}"}
    resp = auth_client.get("/overview/summary", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["total_candidates"] >= 8
    assert data["active_vacancies"] >= 4
    assert "ready_candidates" in data
    assert "active_placements" in data
    assert "eligible_matches" in data
    assert "needs_review_matches" in data
    assert "pending_reminders" in data
    assert isinstance(data["vacancies_by_status"], dict)
    assert isinstance(data["placements_by_status"], dict)
    assert isinstance(data["upcoming_activities"], list)


def test_candidate_crud_and_rbac(auth_client):
    admin_headers = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
    reviewer_headers = {"Authorization": f"Bearer {REVIEWER_TOKEN}"}

    # Reviewer can list candidates
    resp = auth_client.get("/candidates", headers=reviewer_headers)
    assert resp.status_code == 200
    candidates = resp.json()
    assert len(candidates) >= 8

    # Query search
    resp = auth_client.get("/candidates?query=AGRI", headers=reviewer_headers)
    assert resp.status_code == 200
    matched = resp.json()
    assert len(matched) >= 1
    target_id = matched[0]["id"]

    # Get by ID
    resp = auth_client.get(f"/candidates/{target_id}", headers=reviewer_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == target_id

    # Reviewer attempts POST -> 403 Forbidden
    new_candidate = {
        "reference": f"TEST-CAND-{uuid4().hex[:6].upper()}",
        "full_name": "Budi Santoso",
        "preferred_program": "titp",
        "education_level": "SMK Pertanian",
        "domicile_city": "Semarang",
        "status": "ready",
        "skills": ["AGRI_01"],
        "preferred_prefectures": ["Ibaraki"],
        "language_tests": [],
        "certifications": [],
        "experiences": [],
    }
    resp = auth_client.post("/candidates", json=new_candidate, headers=reviewer_headers)
    assert resp.status_code == 403

    # Admin creates candidate -> 201 Created
    resp = auth_client.post("/candidates", json=new_candidate, headers=admin_headers)
    assert resp.status_code == 201
    created_id = resp.json()["id"]

    # Admin updates candidate -> 200
    update_payload = dict(new_candidate)
    update_payload["domicile_city"] = "Surakarta"
    resp = auth_client.put(f"/candidates/{created_id}", json=update_payload, headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["domicile_city"] == "Surakarta"

    # Reviewer attempts archive -> 403
    resp = auth_client.delete(f"/candidates/{created_id}", headers=reviewer_headers)
    assert resp.status_code == 403

    # Admin archives candidate -> 200
    resp = auth_client.delete(f"/candidates/{created_id}", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "inactive"


def test_vacancy_crud_and_draft_workflow(auth_client):
    admin_headers = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
    reviewer_headers = {"Authorization": f"Bearer {REVIEWER_TOKEN}"}

    # Reviewer can list vacancies
    resp = auth_client.get("/vacancies", headers=reviewer_headers)
    assert resp.status_code == 200
    vacancies = resp.json()
    assert len(vacancies) >= 5

    # Filter query
    resp = auth_client.get("/vacancies?query=Pertanian", headers=reviewer_headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1

    # Reviewer attempts to create draft -> 403
    draft_payload = {
        "reference": f"DRAFT-VAC-{uuid4().hex[:6].upper()}",
        "source_channel": "MANUAL",
        "source_reference": "INPUT-2026-10",
        "status": "draft",
        "proposed_data": {
            "reference": f"PROP-VAC-{uuid4().hex[:6].upper()}",
            "title": "Staf Pertanian Ibaraki",
            "employer_name": "Ibaraki Agri Corp",
            "program": "titp",
            "sector": "Pertanian",
            "prefecture": "Ibaraki",
            "quota": 3,
            "minimum_experience_months": 0,
            "required_skills": [],
            "required_certifications": [],
            "preferred_skills": [],
            "preferred_certifications": [],
            "language_requirements": [],
            "status": "open",
        },
    }
    resp = auth_client.post("/vacancies/drafts", json=draft_payload, headers=reviewer_headers)
    assert resp.status_code == 403

    # Admin creates draft -> 201
    resp = auth_client.post("/vacancies/drafts", json=draft_payload, headers=admin_headers)
    assert resp.status_code == 201
    draft = resp.json()
    draft_id = draft["id"]
    assert draft["status"] == "draft"

    # Admin updates draft -> 200
    update_draft = dict(draft_payload)
    update_draft["proposed_data"]["quota"] = 5
    resp = auth_client.put(
        f"/vacancies/drafts/{draft_id}", json=update_draft, headers=admin_headers
    )
    assert resp.status_code == 200
    assert resp.json()["proposed_data"]["quota"] == 5

    # Reviewer attempts publish -> 403
    resp = auth_client.post(f"/vacancies/drafts/{draft_id}/publish", headers=reviewer_headers)
    assert resp.status_code == 403

    # Admin publishes draft -> 201 (Vacancy created, draft published)
    resp = auth_client.post(f"/vacancies/drafts/{draft_id}/publish", headers=admin_headers)
    assert resp.status_code == 201
    published_vacancy = resp.json()
    assert published_vacancy["title"] == "Staf Pertanian Ibaraki"
    assert published_vacancy["status"] == "open"
    published_vacancy_id = published_vacancy["id"]

    # Verify draft status is now published
    draft_resp = auth_client.get(f"/vacancies/drafts/{draft_id}", headers=admin_headers)
    assert draft_resp.json()["status"] == "published"

    # Admin closes vacancy -> 200
    resp = auth_client.delete(f"/vacancies/{published_vacancy_id}", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "closed"


def test_matching_and_placement_rbac(auth_client):
    admin_headers = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
    reviewer_headers = {"Authorization": f"Bearer {REVIEWER_TOKEN}"}

    # Both admin and reviewer can view matching results
    assert auth_client.get("/matching/results", headers=admin_headers).status_code == 200
    resp = auth_client.get("/matching/results", headers=reviewer_headers)
    assert resp.status_code == 200

    # Reviewer cannot decide match -> 403
    decision_payload = {
        "candidate_id": str(uuid4()),
        "vacancy_id": str(uuid4()),
        "decision": "approved",
        "actor_reference": "REV-01",
    }
    resp = auth_client.post("/matching/decisions", json=decision_payload, headers=reviewer_headers)
    assert resp.status_code == 403

    # Reviewer cannot create placement -> 403
    placement_payload = {
        "reference": "PLC-TEST-01",
        "match_id": str(uuid4()),
        "actor_reference": "REV-01",
    }
    resp = auth_client.post("/placements", json=placement_payload, headers=reviewer_headers)
    assert resp.status_code == 403
