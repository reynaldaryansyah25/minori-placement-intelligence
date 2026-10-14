"""Real session DBs and HTTP/queue boundaries; LLM and SMTP are mocks in regression tests."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from minori.api.dependencies import get_ai_gateway
from minori.core.config import Settings
from minori.integrations.nine_router.structured import ValidatedAiGateway
from minori.main import create_app
from pydantic import ValidationError

INBOX = "mailpit@minori.local"

GATEWAY = "synthetic-sandbox-gateway-" + "a" * 40
WORKER = "synthetic-sandbox-worker-" + "b" * 40
SOURCE = "農業スタッフ。日本語能力試験N4以上。募集人数3名。"


class FakeLlm:
    def __init__(self):
        self.calls = 0

    def complete(self, messages):
        self.calls += 1
        if "Extract ONLY" in messages[0].content:
            return json.dumps(
                {
                    "extraction": {
                        "title": "Staf pertanian",
                        "quota": 3,
                        "language_requirements": [{"test_type": "jlpt", "minimum_level": "N4"}],
                        "evidence": [
                            {"field": "title", "quote": "農業スタッフ"},
                            {"field": "language_requirements", "quote": "日本語能力試験N4以上"},
                            {"field": "quota", "quote": "募集人数3名"},
                        ],
                    },
                    "translation": "Staf pertanian. JLPT N4. Kuota tiga orang.",
                    "review": {
                        "mandatory": ["JLPT N4"],
                        "questions": ["Konfirmasikan perusahaan dan lokasi."],
                    },
                }
            )
        if "Explain official" in messages[0].content:
            return json.dumps(
                {
                    "summary": "Penjelasan mengikuti hasil resmi.",
                    "strengths": [],
                    "unmet_requirements": [],
                    "verification_needed": [],
                    "next_steps": ["Tinjau administrasi penempatan."],
                }
            )
        return json.dumps(
            {
                "introduction": "Kami mengingatkan jadwal kegiatan Anda.",
                "closing": "Terima kasih atas perhatian Anda.",
            }
        )


@pytest.fixture
def sandbox(tmp_path):
    root = tmp_path / "sandbox"
    settings = Settings(
        _env_file=None,
        sandbox_enabled=True,
        sandbox_root=root,
        database_url="sqlite:///" + (root / "template.db").as_posix(),
        sandbox_gateway_token=GATEWAY,
        sandbox_worker_token=WORKER,
        notification_dry_run=False,
        notification_delivery_mode="mailpit",
        notification_retry_base_seconds=1,
        demo_clock_at=datetime(2026, 10, 14, 2, 0, tzinfo=UTC),
    )
    app = create_app(settings)
    fake = FakeLlm()
    app.dependency_overrides[get_ai_gateway] = lambda: ValidatedAiGateway(fake)
    with TestClient(app) as client:
        response = client.post("/sandbox/sessions", headers={"Authorization": "Bearer " + GATEWAY})
        assert response.status_code == 200
        token = response.json()["session_token"]
        client.headers["Authorization"] = "Bearer " + token
        yield client, app.state.sandbox, fake, token


def worker_headers(manager, **extra):
    identifier = next(iter(manager.sessions))
    return {"Authorization": "Bearer " + WORKER, "X-Sandbox-Session": identifier, **extra}


def approve_first(client):
    row = next(r for r in client.get("/reminders").json() if r["status"] == "pending")
    preview = client.get(f"/reminders/{row['id']}/email/template").json()
    approval = {k: preview[k] for k in ("subject", "body", "facts_fingerprint")}
    approval.update(confirmed=True, idempotency_key="synthetic-approval-key")
    response = client.post(f"/reminders/{row['id']}/email/approve", json=approval)
    assert response.status_code == 200, response.text
    return row, approval


def test_private_session_data_reset_and_revocation(sandbox, candidate_payload):
    client, manager, _, first_token = sandbox
    assert client.get("/auth/me").json()["role"] == "demo_operator"
    assert len(client.get("/candidates").json()) == 24
    assert len(client.get("/vacancies").json()) == 10
    assert len(client.get("/placements").json()) == 8
    added = client.post("/candidates", json=candidate_payload)
    assert added.status_code == 201
    second = client.post(
        "/sandbox/sessions", headers={"Authorization": "Bearer " + GATEWAY}
    ).json()["session_token"]
    assert (
        len(client.get("/candidates", headers={"Authorization": "Bearer " + second}).json()) == 24
    )
    assert (
        client.get(
            "/candidates/" + added.json()["id"], headers={"Authorization": "Bearer " + second}
        ).status_code
        == 404
    )
    before = client.get("/sandbox/session").json()["used"]
    assert client.post("/sandbox/reset", json={"confirmed": False}).status_code == 422
    assert client.post("/sandbox/reset", json={"confirmed": True}).status_code == 200
    assert len(client.get("/candidates").json()) == 24
    assert client.get("/sandbox/session").json()["used"]["writes"] == before["writes"]
    assert len(list(manager.root.glob("session-*.db"))) == 3  # two sessions plus reset backup
    assert client.post("/sandbox/logout").status_code == 204
    assert (
        client.get("/candidates", headers={"Authorization": "Bearer " + first_token}).status_code
        == 401
    )
    assert (
        client.get("/candidates", headers={"Authorization": "Bearer " + second}).status_code == 200
    )


@pytest.mark.parametrize("token", ["", GATEWAY, WORKER, "synthetic-main-admin-" + "z" * 40])
def test_no_shared_admin_access(sandbox, token):
    client, _, _, _ = sandbox
    assert client.get("/candidates", headers={"Authorization": "Bearer " + token}).status_code in {
        401,
        403,
    }
    assert client.post(
        "/candidates", json={}, headers={"Authorization": "Bearer " + token}
    ).status_code in {401, 403}


def test_participant_cannot_call_internal_worker_or_clock(sandbox):
    client, manager, _, _ = sandbox
    for path in (
        "/internal/reminders/due",
        "/internal/reminders/claim",
        "/internal/demo/clock",
        "/sandbox/worker/sessions",
    ):
        assert (
            client.request(
                "POST" if path != "/internal/reminders/due" else "GET", path, json={}
            ).status_code
            == 403
        )
    assert (
        client.get("/sandbox/worker/sessions", headers=worker_headers(manager)).status_code == 200
    )
    assert (
        client.post(
            "/sandbox/reset", headers=worker_headers(manager), json={"confirmed": True}
        ).status_code
        == 403
    )


def test_expiry_enforced_on_backend_without_frontend(sandbox):
    client, manager, _, _ = sandbox
    row = next(iter(manager.sessions.values()))
    manager.clock = lambda: row.created + manager.settings.sandbox_session_seconds + 1
    assert client.get("/candidates").status_code == 401
    assert client.post("/candidates", json={}).status_code == 401


def test_mocked_upload_ai_batch_and_quota_before_gateway(sandbox):
    client, manager, fake, _ = sandbox
    manager.settings.sandbox_ai_limit = 2
    assert (
        client.post(
            "/ai/documents/preview", files={"file": ("lowongan.txt", SOURCE.encode(), "text/plain")}
        ).status_code
        == 200
    )
    result = client.post("/ai/vacancies/batch", json={"texts": [SOURCE, SOURCE]})
    assert result.status_code == 200
    assert result.json()[0]["extraction"]["language_requirements"][0]["test_type"] == "jlpt"
    assert result.json()[0]["translation"] and result.json()[0]["review"]["questions"]
    assert client.post("/ai/vacancies/analyze", json={"text": SOURCE}).status_code == 429
    assert fake.calls == 2
    assert client.post("/sandbox/reset", json={"confirmed": True}).status_code == 200
    assert client.post("/ai/vacancies/analyze", json={"text": SOURCE}).status_code == 429


def test_upload_and_write_limits(sandbox):
    client, manager, _, _ = sandbox
    assert (
        client.post(
            "/ai/documents/preview",
            files={"file": ("oversize.txt", b"x" * (2 * 1024 * 1024 + 65536))},
        ).status_code
        == 413
    )
    manager.settings.sandbox_upload_limit = 1
    assert (
        client.post("/ai/documents/preview", files={"file": ("ok.txt", b"demo")}).status_code == 200
    )
    assert (
        client.post("/ai/documents/preview", files={"file": ("ok.txt", b"demo")}).status_code == 429
    )
    manager.settings.sandbox_write_limit = next(iter(manager.sessions.values())).counts["writes"]
    assert client.post("/candidates", json={}).status_code == 429
    assert client.post("/sandbox/reset", json={"confirmed": True}).status_code == 200
    assert client.post("/candidates", json={}).status_code == 429
    assert client.post("/sandbox/logout").status_code == 204
    assert client.get("/candidates").status_code == 401


def test_ai_explanation_never_changes_official_result(sandbox):
    client, _, _, _ = sandbox
    result = client.get("/matching/results").json()[0]
    response = client.post(
        "/ai/matching/explanation",
        json={"candidate_id": result["candidate_id"], "vacancy_id": result["vacancy_id"]},
    )
    assert response.status_code == 200, response.text
    assert client.get("/matching/results").json()[0] == result


def test_approved_mailpit_job_claim_retry_and_callback(sandbox):
    client, manager, _, _ = sandbox
    headers = worker_headers(manager)
    pending = client.get("/reminders").json()[0]
    pending = client.post(
        f"/placements/{pending['placement_id']}/activities/{pending['placement_stage_id']}/email/prepare"
    ).json()
    assert (
        client.post(
            "/internal/reminders/claim", headers=headers, json={"notification_id": pending["id"]}
        ).status_code
        == 409
    )
    preview = client.get(f"/reminders/{pending['id']}/email/template").json()
    approval = {k: preview[k] for k in ("subject", "body", "facts_fingerprint")}
    approval.update(confirmed=True, idempotency_key="synthetic-manual-approval-key")
    assert (
        client.post(f"/reminders/{pending['id']}/email/approve", json=approval).status_code == 200
    )
    row = pending
    path = f"/reminders/{row['id']}"
    assert client.post(path + "/email/approve", json=approval).status_code == 200
    assert client.get("/sandbox/session").json()["used"]["emails"] == 1
    claim = client.post(
        "/internal/reminders/claim", headers=headers, json={"notification_id": row["id"]}
    ).json()
    assert claim["recipient_routing"]["effective_recipient"] == INBOX
    assert not claim["notification"]["dry_run"]
    assert (
        client.post(
            "/internal/reminders/claim", headers=headers, json={"notification_id": row["id"]}
        ).json()
        is None
    )
    assert client.post("/sandbox/reset", json={"confirmed": True}).status_code == 409
    callback = f"/internal/reminders/{row['id']}"
    assert (
        client.post(
            callback + "/complete",
            headers=headers,
            json={
                "claim_token": "wrong" * 10,
                "outcome": "sent",
                "provider_reference": "synthetic-smtp",
            },
        ).status_code
        == 409
    )
    assert (
        client.post(
            callback + "/fail",
            headers=headers,
            json={"claim_token": claim["claim_token"], "error_code": "PROVIDER_UNAVAILABLE"},
        ).status_code
        == 200
    )
    clock = manager.settings.demo_clock_at + timedelta(seconds=2)
    manager.settings.demo_clock_at = clock
    retry = client.post(
        "/internal/reminders/claim", headers=headers, json={"notification_id": row["id"]}
    ).json()
    assert retry["notification"]["attempt_count"] == 2
    done = {
        "claim_token": retry["claim_token"],
        "outcome": "sent",
        "provider_reference": "mailpit:synthetic-test-message",
    }
    assert (
        client.post(callback + "/complete", headers=headers, json=done).json()["status"] == "sent"
    )
    assert client.post(callback + "/complete", headers=headers, json=done).status_code == 200
    assert len(client.get(path + "/attempts").json()) == 2


def test_calendar_jobs_at_nine_without_manual_approval(sandbox):
    client, manager, _, _ = sandbox
    rows = client.get("/reminders").json()
    automatic = [r for r in rows if r["delivery_kind"] == "automatic"]
    assert automatic
    # Use the first due calendar date from the real seeded schedule.
    due = min(datetime.fromisoformat(r["scheduled_at"]) for r in automatic)
    manager.settings.demo_clock_at = due - timedelta(seconds=1)
    headers = worker_headers(manager)
    assert client.get("/internal/reminders/due", headers=headers).json() == []
    manager.settings.demo_clock_at = due
    ready = client.get("/internal/reminders/due", headers=headers).json()
    assert {r["template_code"] for r in ready} == {"interview_h3", "medical_h1"}
    for row in ready:
        assert not row["approved_message"]
        claim = client.post(
            "/internal/reminders/claim", headers=headers, json={"notification_id": row["id"]}
        )
        assert claim.status_code == 200
        assert claim.json()["notification"]["delivery_kind"] == "automatic"
    assert client.get("/sandbox/session").json()["used"]["emails"] == len(ready)


def test_automatic_dispatch_cannot_exceed_email_budget(sandbox):
    client, manager, _, _ = sandbox
    manager.settings.sandbox_email_limit = 1
    manager.settings.demo_clock_at = datetime(2026, 10, 14, 2, 0, tzinfo=UTC)
    ready = client.get("/internal/reminders/due", headers=worker_headers(manager)).json()
    assert len(ready) == 2
    headers = worker_headers(manager)
    first = client.post(
        "/internal/reminders/claim", headers=headers, json={"notification_id": ready[0]["id"]}
    )
    assert first.status_code == 200
    second = client.post(
        "/internal/reminders/claim", headers=headers, json={"notification_id": ready[1]["id"]}
    )
    assert second.status_code == 429
    assert client.get(f"/reminders/{ready[1]['id']}").json()["status"] == "pending"


def test_reset_cannot_reuse_email_budget_by_replaying_seed_identifier(sandbox):
    client, manager, _, _ = sandbox
    manager.settings.sandbox_email_limit = 1
    row, _ = approve_first(client)
    assert client.post("/sandbox/reset", json={"confirmed": True}).status_code == 200
    preview = client.get(f"/reminders/{row['id']}/email/template").json()
    payload = {key: preview[key] for key in ("subject", "body", "facts_fingerprint")}
    payload.update(confirmed=True, idempotency_key="synthetic-second-approval")
    assert client.post(f"/reminders/{row['id']}/email/approve", json=payload).status_code == 429


def test_atomic_quota_and_hourly_limits_cannot_be_reset_by_relogin(sandbox):
    _, manager, _, _ = sandbox
    row = next(iter(manager.sessions.values()))
    manager.settings.sandbox_ai_limit = 2

    def spend(_):
        try:
            manager.consume(row, "ai")
            return True
        except Exception:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(spend, range(20))) == 2
    manager.settings.sandbox_hourly_ai_limit = 2
    _, second = manager.create()
    with pytest.raises(Exception, match="per jam"):
        manager.consume(second, "ai")


def test_sandbox_credentials_cannot_access_primary_database(
    sandbox, settings, migrated_database, candidate_payload
):
    _, _, _, token = sandbox
    values = settings.model_dump()
    values.update(
        internal_api_token="synthetic-primary-admin-" + "x" * 40,
        reviewer_api_token="synthetic-primary-reviewer-token",
    )
    with TestClient(create_app(Settings(_env_file=None, **values))) as primary:
        for secret in (token, GATEWAY, WORKER):
            headers = {"Authorization": "Bearer " + secret}
            assert primary.get("/candidates", headers=headers).status_code == 401
            assert (
                primary.post("/candidates", headers=headers, json=candidate_payload).status_code
                == 401
            )
        assert (
            primary.get(
                "/candidates", headers={"Authorization": "Bearer " + values["internal_api_token"]}
            ).json()
            == []
        )


def test_settings_refuse_primary_database_or_credentials(sandbox):
    values = sandbox[1].settings.model_dump()
    for override in (
        {"internal_api_token": GATEWAY},
        {"reviewer_api_token": GATEWAY},
        {"database_url": "sqlite:///main.db"},
        {"notification_delivery_mode": "demo_recipient"},
    ):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, **{**values, **override})


def test_compose_has_no_main_credentials_volume_or_network():
    value = (Path(__file__).resolve().parents[2] / "compose.public-demo.yaml").read_text()
    assert "INTERNAL_API_TOKEN" not in value and "REVIEWER_API_TOKEN" not in value
    assert "professional_demo_data" not in value and "n8n_data" not in value
    assert "127.0.0.1:8502:8501" in value
    assert value.count("ports:") == 1


def test_streamlit_reset_preserves_auth_without_restoring_button_state(tmp_path):
    from streamlit.testing.v1 import AppTest

    source = tmp_path / "reset_ui.py"
    source.write_text(
        """
import streamlit as st
from types import SimpleNamespace
from minori_frontend.auth import render_public_logout
from minori_frontend.components.sandbox import render_sandbox_controls
st.session_state.setdefault("sandbox_session_token", "synthetic-server-session")
st.session_state.setdefault("public_authenticated_at", 100.0)
class Client:
    def sandbox_status(self):
        return {"used":dict(ai=1,writes=3,emails=0,uploads=1,resets=0), "limits":dict(ai=12,writes=80,emails=5,uploads=10,resets=2)}
    def reset_sandbox(self):
        return None
render_public_logout(SimpleNamespace(public_reviewer_mode=True,interactive_demo_mode=False))
render_sandbox_controls(Client())
render_sandbox_controls(Client(), key_prefix="sandbox_mobile")
""",
        encoding="utf-8",
    )
    ui = AppTest.from_file(str(source)).run()
    assert not ui.exception
    ui.checkbox(key="sandbox_mobile_confirm").check().run()
    ui.button(key="sandbox_mobile_reset").click().run()
    assert not ui.exception
    assert ui.session_state["sandbox_session_token"] == "synthetic-server-session"
    assert ui.session_state["public_authenticated_at"] == 100.0
