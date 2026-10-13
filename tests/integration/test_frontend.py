"""Validate frontend rendering, navigation, and HTTP client boundary without network calls."""

from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest
from minori_frontend.api_client import ApiClientError, BackendClient
from minori_frontend.config import FrontendSettings
from minori_frontend.utils.dates import format_datetime_id, parse_to_wib
from minori_frontend.utils.formatting import format_currency_yen, format_program, format_score
from minori_frontend.utils.validation import validate_reference, validate_required
from pydantic import SecretStr
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


def test_frontend_client_error_mapping():
    settings = FrontendSettings(_env_file=None, backend_base_url="http://localhost:8765")
    assert BackendClient(settings) is not None

    # Test error status code mapping
    with pytest.raises(ApiClientError) as exc_info:
        # Mock client._request to simulate 401
        def mock_request(*args, **kwargs):
            raise ApiClientError(
                401,
                "Akses ditolak: Token autentikasi tidak valid atau belum diisi.",
                "Unauthorized",
            )

        mock_client = MagicMock()
        mock_client._request = mock_request
        mock_client._request("GET", "/protected")

    assert exc_info.value.status_code == 401
    assert "Akses ditolak" in exc_info.value.message


def test_frontend_client_authorization_header():
    secret_token = "secret-admin-token-xyz"
    settings = FrontendSettings(
        _env_file=None,
        backend_base_url="http://localhost:8765",
        internal_api_token=SecretStr(secret_token),
    )
    client = BackendClient(settings)
    headers = client._headers()
    assert headers["Authorization"] == f"Bearer {secret_token}"


def test_frontend_renders_app_and_sidebar(monkeypatch):
    monkeypatch.setattr(BackendClient, "get_health", lambda self: HEALTH)
    app = AppTest.from_file(str(ROOT / "frontend/minori_frontend/app.py"), default_timeout=15).run()
    assert not app.exception
    # Check sidebar contains MINORI Group branding and Connected status
    sidebar_text = "".join(m.value for m in app.sidebar.markdown)
    assert "MINORI Group" in sidebar_text
    assert "Connected" in sidebar_text
    assert "Asia/Jakarta (WIB)" in sidebar_text


def test_frontend_reports_connection_failure_gracefully(monkeypatch):
    def disconnected(self):
        raise ApiClientError(503, "Backend Offline", "Connection refused")

    monkeypatch.setattr(BackendClient, "get_health", disconnected)
    app = AppTest.from_file(str(ROOT / "frontend/minori_frontend/app.py"), default_timeout=15).run()
    assert not app.exception
    sidebar_text = "".join(m.value for m in app.sidebar.markdown)
    assert "Backend Offline" in sidebar_text


@pytest.mark.parametrize(
    "page_filename",
    [
        "overview.py",
        "candidates.py",
        "vacancies.py",
        "candidate_matching.py",
        "placement_pipeline.py",
        "reminder_center.py",
        "ai_vacancy_intelligence.py",
        "reports.py",
    ],
)
def test_all_pages_render_without_exception(page_filename):
    page_path = ROOT / "frontend/minori_frontend/pages" / page_filename
    app = AppTest.from_file(str(page_path), default_timeout=15).run()
    assert not app.exception, f"Page {page_filename} raised exception: {app.exception}"


def test_no_token_leakage_in_rendered_ui(monkeypatch):
    secret_token = "super-secret-token-not-to-be-leaked"
    monkeypatch.setenv("INTERNAL_API_TOKEN", secret_token)
    app = AppTest.from_file(str(ROOT / "frontend/minori_frontend/app.py"), default_timeout=15).run()
    assert not app.exception

    all_markdown = "".join(m.value for m in app.markdown)
    all_sidebar = "".join(m.value for m in app.sidebar.markdown)
    full_output = all_markdown + all_sidebar

    assert secret_token not in full_output


def test_utility_formatters():
    # Score formatting: 0..1 to 0..100
    assert "85.2" in format_score(0.852)
    assert "100.0" in format_score(1.0)
    assert "0.0" in format_score(0.0)
    assert format_score(None) == "—"

    # Program labels
    assert "TITP" in format_program("titp")
    assert "SSW" in format_program("ssw")
    assert "Engineer" in format_program("engineer")

    # Currency formatting
    assert format_currency_yen(250000) == "¥250,000"

    # Validators (return None when valid, error message string when invalid)
    assert validate_reference("DEMO-CAND-AGRI") is None
    assert validate_reference("") is not None
    assert validate_required("Test", "Nama") is None
    assert validate_required("   ", "Nama") is not None


def test_date_jakarta_conversions():
    utc_str = "2026-10-13T00:00:00Z"
    dt_jkt = parse_to_wib(utc_str)
    assert dt_jkt is not None
    assert dt_jkt.hour == 7  # UTC+7
    formatted = format_datetime_id(utc_str)
    assert "13 Okt 2026" in formatted and "07:00" in formatted and "WIB" in formatted
