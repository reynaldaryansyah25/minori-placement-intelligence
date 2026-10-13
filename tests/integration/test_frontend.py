"""Validate frontend rendering and its HTTP boundary without external network access."""

from pathlib import Path

import httpx
from minori_frontend.api_client import BackendClient
from minori_frontend.config import FrontendSettings
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[2]
HEALTH = {
    "status": "ok",
    "database": "ok",
    "application": "MINORI Placement Intelligence",
    "version": "0.1.0",
}


def test_frontend_client_uses_http_and_timeout(monkeypatch):
    captured = []

    def response(url, timeout):
        captured.append((url, timeout))
        return httpx.Response(200, json=HEALTH, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", response)
    settings = FrontendSettings(_env_file=None, backend_base_url="http://localhost:8765")
    assert BackendClient(settings).get_health() == HEALTH
    assert captured == [("http://localhost:8765/health", 5)]


def test_frontend_renders_backend_health(monkeypatch):
    monkeypatch.setattr(BackendClient, "get_health", lambda self: HEALTH)
    app = AppTest.from_file(str(ROOT / "frontend/minori_frontend/app.py"), default_timeout=15).run()
    assert not app.exception
    assert app.title[0].value == "MINORI Placement Intelligence"
    assert [metric.value for metric in app.metric] == ["ok", "ok", "0.1.0"]
    assert len(app.success) == 1
    app.button[0].click().run()
    assert not app.exception


def test_frontend_reports_connection_failure(monkeypatch):
    def disconnected(self):
        raise httpx.ConnectError("synthetic failure")

    monkeypatch.setattr(BackendClient, "get_health", disconnected)
    app = AppTest.from_file(str(ROOT / "frontend/minori_frontend/app.py"), default_timeout=15).run()
    assert not app.exception
    assert len(app.error) == 1
    assert not app.success
