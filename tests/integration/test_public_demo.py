"""Real RBAC enforcement and public UI gates without real LLM/network calls."""

import json
import re
import time
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from minori.core.config import Settings
from minori.db.professional_demo import seed_professional_demo
from minori.main import create_app
from minori_frontend.api_client import ApiClientError, BackendClient
from minori_frontend.config import FrontendSettings
from minori_frontend.public_auth import LoginThrottle, credential_fingerprint, password_hash
from minori_frontend.public_data import PublicDemoData
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[2]
PASSWORD = "Synthetic-public-password-for-tests"
ADMIN = "synthetic-staff-token-for-public-test"
REVIEWER = "synthetic-reviewer-token-for-public-test"


@pytest.fixture
def public_environment(monkeypatch):
    # FrontendSettings must not load developer credentials from the ignored .env in tests.
    monkeypatch.setitem(FrontendSettings.model_config, "env_file", None)
    monkeypatch.delenv("INTERNAL_API_TOKEN", raising=False)
    monkeypatch.setenv("PUBLIC_REVIEWER_MODE", "true")
    monkeypatch.setenv("REVIEWER_API_TOKEN", REVIEWER)
    monkeypatch.setenv("PUBLIC_DEMO_USERNAME", "synthetic-reviewer")
    monkeypatch.setenv("PUBLIC_DEMO_PASSWORD_HASH", password_hash(PASSWORD))
    import minori_frontend.public_auth as auth

    monkeypatch.setattr(auth, "LOGIN_THROTTLE", LoginThrottle())
    return FrontendSettings()


def app_test():
    return AppTest.from_file(str(ROOT / "frontend/app.py"), default_timeout=20)


def authenticate_ui(app):
    app.text_input[0].set_value("synthetic-reviewer")
    app.text_input[1].set_value(PASSWORD)
    app.button[0].click().run()
    return app


def test_anonymous_sees_login_only_and_makes_no_backend_calls(public_environment, monkeypatch):
    calls = []
    monkeypatch.setattr(
        BackendClient, "_transport_request", lambda *args, **kwargs: calls.append(args)
    )
    app = app_test().run()
    assert not app.exception and len(app.text_input) == 2
    assert not app.sidebar.markdown and not app.dataframe
    assert not calls and "auth_token" not in app.session_state
    assert "Ringkasan operasional" not in str(app)


def test_public_role_cannot_escalate_or_accept_custom_token(public_environment, monkeypatch):
    import minori_frontend.auth as auth
    from minori_frontend.auth import (
        apply_custom_token,
        get_current_role,
        init_auth_state,
        switch_demo_role,
    )

    state = {"auth_role": "admin", "auth_token": ADMIN}
    monkeypatch.setattr(auth.st, "session_state", state)

    # Attribute-style state methods are used by the existing staff session implementation.
    class State(dict):
        __getattr__ = dict.get
        __setattr__ = dict.__setitem__

    state = State(state)
    monkeypatch.setattr(auth.st, "session_state", state)
    init_auth_state(public_environment)
    assert get_current_role() == "reviewer" and "auth_token" not in state
    switch_demo_role("admin", public_environment)
    assert get_current_role() == "reviewer" and "auth_token" not in state
    client = BackendClient(public_environment)
    assert client._headers(ADMIN)["Authorization"] == "Bearer " + REVIEWER
    assert not apply_custom_token(ADMIN, client)


def test_frontend_public_client_blocks_writes_before_http(public_environment, monkeypatch):
    import streamlit as st

    monkeypatch.setattr(
        st,
        "session_state",
        {
            "public_authenticated_at": time.monotonic(),
            "public_last_activity": time.monotonic(),
            "public_credential_fingerprint": credential_fingerprint(public_environment),
        },
    )
    client = BackendClient(public_environment)
    monkeypatch.setattr(
        client, "_transport_request", lambda *args, **kwargs: pytest.fail("HTTP mutation attempted")
    )
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        with pytest.raises(ApiClientError) as error:
            client._request(method, "/candidates", json={})
        assert error.value.status_code == 403
    with pytest.raises(ApiClientError) as error:
        client._request("GET", "/internal/reminders/due")
    assert error.value.status_code == 403
    st.session_state.clear()
    with pytest.raises(ApiClientError) as error:
        client.list_candidates()
    assert error.value.status_code == 401


def test_valid_public_login_is_reviewer_and_logout_erases_session(public_environment, monkeypatch):
    monkeypatch.setattr(BackendClient, "verify_public_reviewer", lambda self: {"role": "reviewer"})
    monkeypatch.setattr(BackendClient, "get_health", lambda self: {"status": "ok"})
    monkeypatch.setattr(BackendClient, "_request", lambda *args, **kwargs: {})
    app = authenticate_ui(app_test().run())
    assert not app.exception and app.session_state["auth_role"] == "reviewer"
    assert "auth_token" not in app.session_state
    assert not app.text_input
    assert any(b.label == "Keluar dari demo" for b in app.sidebar.button)
    app.sidebar.button[0].click().run()
    assert len(app.text_input) == 2 and "public_authenticated_at" not in app.session_state


@pytest.mark.parametrize("role", ["admin", None])
def test_wrong_backend_role_cannot_open_public_dashboard(public_environment, monkeypatch, role):
    monkeypatch.setattr(BackendClient, "verify_public_reviewer", lambda self: {"role": role})
    app = authenticate_ui(app_test().run())
    assert not app.exception and app.error
    assert "public_authenticated_at" not in app.session_state and not app.dataframe


def test_public_session_expiry_returns_login_and_clears_page_data(public_environment, monkeypatch):
    app = app_test()
    app.session_state["public_authenticated_at"] = time.monotonic() - 4000
    app.session_state["public_last_activity"] = time.monotonic()
    app.session_state["public_credential_fingerprint"] = credential_fingerprint(public_environment)
    app.session_state["auth_token"] = ADMIN
    app.session_state["private_cached_payload"] = {"sensitive": "never-visible"}
    app.run()
    assert not app.exception and len(app.text_input) == 2
    assert (
        "auth_token" not in app.session_state and "private_cached_payload" not in app.session_state
    )


@pytest.fixture
def rbac_app(settings, migrated_database):
    configured = Settings(
        _env_file=None,
        **{
            **settings.model_dump(),
            "internal_api_token": ADMIN,
            "reviewer_api_token": REVIEWER,
            "demo_clock_at": datetime(2026, 10, 14, 5, tzinfo=UTC),
        },
    )
    with TestClient(create_app(configured)) as client:
        yield client


def test_all_backend_mutations_reject_reviewer_and_anonymous(rbac_app, candidate_payload):
    client = rbac_app
    count = 0
    for route_path, operations in client.app.openapi()["paths"].items():
        path = re.sub(r"\{[^}]+\}", lambda _: str(uuid4()), route_path)
        for method in {key.upper() for key in operations} & {"POST", "PUT", "PATCH", "DELETE"}:
            reviewer = client.request(
                method, path, json={}, headers={"Authorization": "Bearer " + REVIEWER}
            )
            assert reviewer.status_code == (401 if path.startswith("/internal/") else 403), (
                method,
                route_path,
                reviewer.status_code,
            )
            assert client.request(method, path, json={}).status_code == 401, (method, route_path)
            count += 1
    assert count >= 20
    assert client.get("/candidates").status_code == 401
    assert (
        client.get("/candidates", headers={"Authorization": "Bearer " + REVIEWER}).status_code
        == 200
    )
    assert (
        client.post(
            "/candidates", json=candidate_payload, headers={"Authorization": "Bearer " + ADMIN}
        ).status_code
        == 201
    )
    assert (
        client.get("/auth/me", headers={"Authorization": "Bearer " + ADMIN}).json()["role"]
        == "admin"
    )


def test_public_projection_filters_non_demo_and_modified_profiles(
    rbac_app, migrated_database, candidate_payload
):
    seed_professional_demo(migrated_database, anchor=datetime(2026, 10, 14, 5, tzinfo=UTC))
    client = rbac_app
    admin = {"Authorization": "Bearer " + ADMIN}
    non_demo = deepcopy(candidate_payload)
    non_demo.update(
        reference="DEMO-PRO-CAND-99",
        full_name="Non-demo identity must stay private",
        email="private@example.invalid",
    )
    assert client.post("/candidates", json=non_demo, headers=admin).status_code == 201

    def fetch(method, path, **kwargs):
        response = client.request(
            method, path, headers={"Authorization": "Bearer " + REVIEWER}, **kwargs
        )
        assert response.is_success, (path, response.status_code)
        return response.json()

    public = PublicDemoData(fetch)
    candidates = public.request("/candidates")
    assert len(candidates) == 24
    assert len(public.request("/vacancies")) == 10
    assert len(public.request("/vacancies/drafts")) == 3
    assert len(public.request("/placements")) == 8
    assert len(public.request("/reminders")) == 16
    assert all("email" not in c for c in candidates)
    assert "Non-demo identity" not in json.dumps(public.summary())
    assert public.summary()["total_candidates"] == 24
    candidate = fetch("GET", "/candidates/" + candidates[0]["id"])
    changed = {k: v for k, v in candidate.items() if k not in {"id", "created_at", "updated_at"}}
    changed["experiences"][0]["employer_name"] = "Private employer must not be published"
    assert (
        client.put("/candidates/" + candidate["id"], json=changed, headers=admin).status_code == 200
    )
    public = PublicDemoData(fetch)
    assert len(public.request("/candidates")) == 23
    with pytest.raises(ApiClientError):
        public.request("/candidates/" + candidate["id"])
    assert "Private employer" not in json.dumps(public.summary())
