"""Exercise real FastAPI lifecycle and SQLite, including a failed database query."""

from fastapi.testclient import TestClient
from minori import __version__
from minori.main import create_app
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session


def test_health_uses_sqlite_without_llm(settings, monkeypatch):
    def forbidden_router(*args, **kwargs):
        raise AssertionError("Health must not construct an LLM client")

    monkeypatch.setattr("minori.integrations.nine_router.client.OpenAI", forbidden_router)
    with TestClient(create_app(settings)) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {
            "status": "ok",
            "application": settings.app_name,
            "version": __version__,
            "database": "ok",
        }
        schema = client.get("/openapi.json").json()
        assert "/health" in schema["paths"]


def test_health_returns_503_and_sanitizes_database_failure(settings, monkeypatch):
    def unavailable(*args, **kwargs):
        raise OperationalError("SELECT 1", {}, RuntimeError("synthetic-sensitive-database-path"))

    with TestClient(create_app(settings)) as client:
        monkeypatch.setattr(Session, "execute", unavailable)
        response = client.get("/health")
        assert response.status_code == 503
        assert response.json()["database"] == "unavailable"
        assert response.json()["status"] == "degraded"
        assert "synthetic-sensitive-database-path" not in response.text


def test_production_does_not_expose_interactive_docs(settings):
    settings.app_env = "production"
    with TestClient(create_app(settings)) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/docs").status_code == 404
        assert client.get("/openapi.json").status_code == 404
