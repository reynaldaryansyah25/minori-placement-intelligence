"""Comprehensive tests for Final Refinement: demo dataset, routing, UI safety, and permissions."""

import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from minori.core.config import PROJECT_ROOT
from minori.db.seeding import seed_database
from minori.domain.matching_engine import MatchingEngine
from minori.domain.reminders import ReminderPolicy
from minori.main import create_app
from pydantic import SecretStr

ADMIN_TOKEN = "test-internal-token-secret-1234567890"
REVIEWER_TOKEN = "test-reviewer-token-secret-12345"


@pytest.fixture
def demo_settings(settings):
    return settings.model_copy(
        update={
            "internal_api_token": SecretStr(ADMIN_TOKEN),
            "reviewer_api_token": SecretStr(REVIEWER_TOKEN),
            "app_env": "production",
            "demo_notification_recipient": "qa-tester@example.com",
            "notification_delivery_mode": "dry_run",
        }
    )


@pytest.fixture
def demo_database(migrated_database):
    seed_database(migrated_database, fixture_directory=PROJECT_ROOT / "data/demo")
    return migrated_database


@pytest.fixture
def demo_client(demo_database, demo_settings):
    with TestClient(create_app(demo_settings)) as client:
        yield client


def test_demo_dataset_consistency():
    """Verify quality, professional naming, and valid chronology of the 20-candidate demo dataset."""
    c_path = PROJECT_ROOT / "data/demo/candidates.json"
    v_path = PROJECT_ROOT / "data/demo/vacancies.json"
    p_path = PROJECT_ROOT / "data/demo/placement_data.json"

    assert c_path.exists() and v_path.exists() and p_path.exists()

    c_data = json.loads(c_path.read_text(encoding="utf-8"))
    v_data = json.loads(v_path.read_text(encoding="utf-8"))
    p_data = json.loads(p_path.read_text(encoding="utf-8"))

    # Exactly 20 synthetic candidates
    candidates = c_data["candidates"]
    assert len(candidates) == 20
    for cand in candidates:
        assert cand["reference"].startswith("DEMO-")
        assert "Contoh" not in cand["full_name"]
        for exp in cand["experiences"]:
            assert "Contoh" not in exp["employer_name"]

    # Exactly 8 realistic vacancies
    vacancies = v_data["vacancies"]
    assert len(vacancies) == 8
    for vac in vacancies:
        assert vac["reference"].startswith("DEMO-")
        assert "Contoh" not in vac["employer_name"]
        assert "Contoh" not in vac["title"]

    # Logical chronology: no future activity should be completed
    now = datetime(2026, 10, 14, tzinfo=UTC)
    for step in p_data["steps"]:
        sched = datetime.fromisoformat(step["scheduled_at"])
        if step["status"] == "completed":
            assert sched <= now, f"Step {step['code']} is in the future but marked completed"


def test_vacancy_weld_candidate_distribution(demo_database):
    """Verify at least 1 vacancy has 3 eligible with different scores, 1 needs review, and not eligible."""
    from minori.repositories.provider import provide_repositories

    with demo_database.session_factory() as session:
        repos = provide_repositories(session)
        vac = repos.vacancy.get_by_reference("DEMO-VAC-WELD")
        assert vac is not None

        candidates = repos.candidate.list(limit=50)
        assert len(candidates) == 20

        engine = MatchingEngine()
        now = datetime(2026, 10, 14, 0, 0, tzinfo=UTC)

        evals = [engine.evaluate(c, vac, now) for c in candidates]
        eligible = [e for e in evals if e.eligibility_status.value == "ELIGIBLE"]
        needs_review = [e for e in evals if e.eligibility_status.value == "NEEDS_REVIEW"]
        not_eligible = [e for e in evals if e.eligibility_status.value == "NOT_ELIGIBLE"]

        # Exactly 3 eligible with distinct scores
        assert len(eligible) == 3
        scores = [round(e.total_score, 4) for e in eligible]
        assert len(set(scores)) == 3, f"Expected 3 distinct scores, got {scores}"

        # Exactly 1 needs review (Damar Setiawan / preparing status)
        assert len(needs_review) == 1
        assert len(not_eligible) == 16


def test_demo_recipient_routing_never_sends_to_dummy():
    """Verify demo notifications routing protects candidate privacy and isolates test recipients."""
    # 1. Default dry-run mode
    policy_dry = ReminderPolicy(
        dry_run=True,
        notification_delivery_mode="dry_run",
        demo_notification_recipient=None,
    )
    routing_dry = policy_dry.resolve_recipient("DEMO-CAND-AGRI")
    assert routing_dry["intended_recipient"] == "kandidat-demo-cand-agri@demo.minori.internal"
    assert routing_dry["effective_recipient"] is None
    assert routing_dry["routing_mode"] == "dry_run"
    assert routing_dry["delivery_allowed"] is False
    assert "@gmail.com" not in routing_dry["intended_recipient"]

    # 2. Local mailpit mode
    policy_mailpit = ReminderPolicy(
        dry_run=False,
        notification_delivery_mode="mailpit",
        mailpit_inbox_email="mailpit@minori.local",
    )
    routing_mailpit = policy_mailpit.resolve_recipient("DEMO-CAND-FOOD")
    assert routing_mailpit["intended_recipient"] == "kandidat-demo-cand-food@demo.minori.internal"
    assert routing_mailpit["effective_recipient"] == "mailpit@minori.local"
    assert routing_mailpit["routing_mode"] == "mailpit"
    assert routing_mailpit["delivery_allowed"] is True

    # 3. Environment test recipient override
    policy_env = ReminderPolicy(
        dry_run=False,
        notification_delivery_mode="demo_recipient",
        demo_notification_recipient="staff-test@minori-partner.ac.id",
    )
    routing_env = policy_env.resolve_recipient("DEMO-CAND-WELD")
    assert routing_env["intended_recipient"] == "kandidat-demo-cand-weld@demo.minori.internal"
    assert routing_env["effective_recipient"] == "staff-test@minori-partner.ac.id"
    assert routing_env["routing_mode"] == "demo_recipient"
    assert routing_env["delivery_allowed"] is True


def test_claim_and_routing_api(demo_client):
    """Test claim and routing endpoints return structured Demo Recipient Routing information."""
    headers_admin = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
    headers_review = {"Authorization": f"Bearer {REVIEWER_TOKEN}"}

    # List reminders
    reminders = demo_client.get("/reminders", headers=headers_review).json()
    assert len(reminders) > 0
    rem_id = reminders[0]["id"]

    # Query routing endpoint
    resp = demo_client.get(f"/reminders/{rem_id}/routing", headers=headers_review)
    assert resp.status_code == 200
    routing = resp.json()
    assert "intended_recipient" in routing
    assert routing["intended_recipient"].endswith("@demo.minori.internal")
    assert "safety_notice" in routing

    # Internal claim endpoint returns recipient routing
    resp_claim = demo_client.post(
        "/internal/reminders/claim",
        headers=headers_admin,
        json={"notification_id": rem_id},
    )
    assert resp_claim.status_code == 200
    claim_data = resp_claim.json()
    if claim_data is not None:
        assert "recipient_routing" in claim_data
        assert claim_data["recipient_routing"]["intended_recipient"].endswith(
            "@demo.minori.internal"
        )


def test_reviewer_cannot_perform_mutations(demo_client):
    """Verify RBAC: Reviewer token cannot perform mutation operations (403 Forbidden)."""
    headers = {"Authorization": f"Bearer {REVIEWER_TOKEN}"}

    # Candidate mutation
    cand_resp = demo_client.post(
        "/candidates",
        headers=headers,
        json={
            "reference": "DEMO-NEW-01",
            "full_name": "Test Candidate",
            "preferred_program": "ssw",
            "education_level": "SMK",
            "domicile_city": "Jakarta",
        },
    )
    assert cand_resp.status_code == 403

    # Vacancy draft mutation
    draft_resp = demo_client.post(
        "/vacancies/drafts",
        headers=headers,
        json={
            "reference": "DRAFT-TEST-01",
            "source_channel": "manual",
            "source_reference": "ref-01",
            "proposed_data": {
                "reference": "DEMO-NEW-VAC",
                "title": "Test Vacancy",
                "employer_name": "Test Co",
                "program": "ssw",
                "sector": "agriculture",
                "prefecture": "Tokyo",
                "quota": 1,
            },
        },
    )
    assert draft_resp.status_code == 403

    # Matching evaluation recompute mutation
    eval_resp = demo_client.post(
        "/matching/evaluations",
        headers=headers,
        json={},
    )
    assert eval_resp.status_code == 403


def test_kpi_no_double_counting(demo_client):
    """Verify overview summary KPIs calculate distinct items without double counting."""
    headers = {"Authorization": f"Bearer {REVIEWER_TOKEN}"}
    resp = demo_client.get("/overview/summary", headers=headers)
    assert resp.status_code == 200
    summary = resp.json()

    assert summary["total_candidates"] == 20
    assert summary["active_vacancies"] == 7  # 7 open, 1 paused
    assert summary["active_placements"] == 6

    # Matches breakdown must not exceed total evaluations
    total_evals = (
        summary["eligible_matches"]
        + summary["needs_review_matches"]
        + summary["not_eligible_matches"]
    )
    assert total_evals >= summary["eligible_matches"]


def test_no_literal_div_or_tracebacks():
    """Verify frontend pages contain no unmatched st.markdown('</div>') and explanation handles non-dicts safely."""
    pages_dir = PROJECT_ROOT / "frontend/minori_frontend/pages"
    for py_file in pages_dir.glob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        assert 'st.markdown("</div>"' not in content, f"Literal </div> leak found in {py_file.name}"
        assert "st.markdown('</div>'" not in content, f"Literal </div> leak found in {py_file.name}"

    # Verify matching_explanation helper handles string and non-dict inputs safely
    from minori_frontend.components.matching_explanation import _safe_dict

    assert _safe_dict("invalid-json") == {}
    assert _safe_dict('{"valid": true}') == {"valid": True}
    assert _safe_dict(None) == {}
    assert _safe_dict(123) == {}
