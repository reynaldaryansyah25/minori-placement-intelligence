"""Validate frontend rendering, navigation, and HTTP client boundary without network calls."""

from copy import deepcopy
from pathlib import Path
from unittest.mock import MagicMock
from urllib.parse import urlsplit

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


@pytest.fixture
def frontend_backend(monkeypatch, candidate_payload, vacancy_payload):
    candidate = {**candidate_payload, "id": "candidate-private-id"}
    vacancy = {**vacancy_payload, "id": "vacancy-private-id"}
    placement = {
        "id": "placement-private-id",
        "candidate_id": candidate["id"],
        "vacancy_id": vacancy["id"],
        "reference": "INTERNAL-PLACEMENT",
        "status": "in_progress",
    }
    reminder = {
        "id": "notification-private-id",
        "candidate_id": candidate["id"],
        "reference": "INTERNAL-NOTIFICATION",
        "template_code": "interview_h3",
        "status": "pending",
        "dry_run": True,
        "attempt_count": 0,
        "max_attempts": 3,
    }
    evaluation = {
        "candidate_id": candidate["id"],
        "vacancy_id": vacancy["id"],
        "eligibility_status": "ELIGIBLE",
        "staff_status": "proposed",
        "total_score": 0.85,
        "explanation": {"checks": [], "score_components": []},
    }
    data = {
        "/health": HEALTH,
        "_calls": [],
        "_allowed_posts": {},
        "/overview/summary": {
            "total_candidates": 1,
            "ready_candidates": 1,
            "active_vacancies": 1,
            "active_placements": 1,
            "pending_reminders": 1,
        },
        "/candidates": [candidate],
        "/vacancies": [vacancy],
        "/placements": [placement],
        "/reminders": [reminder],
        "/vacancies/drafts": [],
        "/matching/results": [evaluation],
        f"/matching/vacancies/{vacancy['id']}/ranking": [evaluation],
        f"/matching/candidates/{candidate['id']}/vacancies/{vacancy['id']}/explanation": evaluation,
        f"/placements/{placement['id']}/activities": [],
        f"/reminders/{reminder['id']}/attempts": [],
        f"/reminders/{reminder['id']}/routing": {
            "routing_mode": "dry_run",
            "delivery_allowed": False,
        },
    }

    def request(self, method, url, **kwargs):
        path = urlsplit(str(url)).path
        data["_calls"].append((method, path, kwargs.get("json")))
        assert method == "GET" or path in data["_allowed_posts"], (
            f"Unexpected mutation: {method} {path}"
        )
        assert path in data or path in data["_allowed_posts"], f"Unexpected endpoint: {path}"
        payload = data[path] if method == "GET" else data["_allowed_posts"][path]
        status = (
            payload.pop("_http_status", 200)
            if isinstance(payload, dict) and "_http_status" in payload
            else 200
        )
        return httpx.Response(status, json=deepcopy(payload), request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.Client, "request", request)
    return data


def rendered_html(app):
    return "".join(element.proto.body for element in app.get("html"))


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


def test_frontend_renders_app_and_sidebar(monkeypatch, frontend_backend):
    monkeypatch.setattr(BackendClient, "get_health", lambda self: HEALTH)
    app = AppTest.from_file(str(ROOT / "frontend/app.py"), default_timeout=15).run()
    assert not app.exception
    # Check sidebar contains MINORI Group branding and operational status
    sidebar_text = rendered_html(app.sidebar)
    assert "MINORI Group" in sidebar_text
    assert "Sistem terhubung" in sidebar_text
    assert "WIB (UTC+7)" in sidebar_text


def test_frontend_reports_connection_failure_gracefully(monkeypatch, frontend_backend):
    def disconnected(self):
        raise ApiClientError(503, "Backend Offline", "Connection refused")

    monkeypatch.setattr(BackendClient, "get_health", disconnected)
    monkeypatch.setattr(
        httpx, "get", lambda *args, **kwargs: (_ for _ in ()).throw(httpx.ConnectError("Offline"))
    )
    app = AppTest.from_file(str(ROOT / "frontend/app.py"), default_timeout=15).run()
    assert not app.exception
    sidebar_text = rendered_html(app.sidebar)
    assert "Layanan belum terhubung" in sidebar_text


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
def test_all_pages_render_without_exception(page_filename, frontend_backend):
    page_path = ROOT / "frontend/minori_frontend/pages" / page_filename
    app = AppTest.from_file(str(page_path), default_timeout=15).run()
    assert not app.exception, f"Page {page_filename} raised exception: {app.exception}"
    assert not app.get("iframe")
    output = rendered_html(app)
    for hidden in (
        "candidate-private-id",
        "vacancy-private-id",
        "INTERNAL-PLACEMENT",
        "INTERNAL-NOTIFICATION",
    ):
        assert hidden not in output
        assert all(hidden not in table.value.to_string() for table in app.dataframe)


def test_ai_analysis_button_populates_review_form(frontend_backend):
    from minori.schemas.ai import VacancyAnalysis

    frontend_backend["_allowed_posts"]["/ai/vacancies/analyze"] = VacancyAnalysis.model_validate(
        {
            "extraction": {
                "title": "Staf pertanian",
                "employer_name": "Perusahaan Demo Sintetis",
                "program": "ssw",
                "sector": "agriculture",
                "prefecture": "Hokkaido",
                "quota": 3,
                "minimum_experience_months": 12,
                "language_requirements": [{"test_type": "jlpt", "minimum_level": "N4"}],
            },
            "translation": "Lowongan demo sintetis membutuhkan JLPT N4.",
            "review": {"questions": ["Konfirmasi tenggat."]},
        }
    ).model_dump(mode="json")
    app = AppTest.from_file(
        str(ROOT / "frontend/minori_frontend/pages/ai_vacancy_intelligence.py")
    ).run()
    app.text_area(key="vacancy_source_text").set_value("日本語能力試験N4以上。").run()
    next(button for button in app.button if button.label == "Analisis dengan AI").click().run()
    assert not app.exception
    assert [tab.label for tab in app.tabs] == [
        "Hasil Ekstraksi",
        "Terjemahan Indonesia",
        "Pemeriksaan Persyaratan",
    ]
    assert (
        next(field for field in app.text_input if field.label == "Posisi pekerjaan *").value
        == "Staf pertanian"
    )
    assert any(call[1] == "/ai/vacancies/analyze" for call in frontend_backend["_calls"])


def test_no_token_leakage_in_rendered_ui(monkeypatch, frontend_backend):
    secret_token = "super-secret-token-not-to-be-leaked"
    monkeypatch.setenv("INTERNAL_API_TOKEN", secret_token)
    app = AppTest.from_file(str(ROOT / "frontend/app.py"), default_timeout=15).run()
    assert not app.exception

    all_markdown = "".join(m.value for m in app.markdown)
    all_sidebar = "".join(m.value for m in app.sidebar.markdown)
    full_output = all_markdown + all_sidebar + rendered_html(app)

    assert secret_token not in full_output


def test_pagination_preserves_candidate_identity(frontend_backend):
    sample = frontend_backend["/candidates"][0]
    frontend_backend["/candidates"] = [
        {**sample, "id": f"private-{index}", "full_name": f"Peserta {index + 1}"}
        for index in range(25)
    ]
    app = AppTest.from_file(str(ROOT / "frontend/minori_frontend/pages/candidates.py")).run()
    assert len(app.dataframe[0].value) == 10
    assert "id" not in app.dataframe[0].value.columns
    app.button(key="candidates_table_next").click().run()
    assert not app.exception
    assert app.dataframe[0].value.iloc[0]["Nama kandidat"] == "Peserta 11"
    assert "Peserta 11" in rendered_html(app)


def test_placement_search_without_matches_has_no_traceback(frontend_backend):
    app = AppTest.from_file(
        str(ROOT / "frontend/minori_frontend/pages/placement_pipeline.py")
    ).run()
    app.text_input(key="plc_search").set_value("tidak-ada-hasil").run()
    assert not app.exception
    assert not app.dataframe
    assert "Penempatan tidak ditemukan" in rendered_html(app)


def test_backend_error_is_not_exposed_to_staff(monkeypatch, frontend_backend):
    frontend_backend["/candidates"] = {
        "_http_status": 422,
        "detail": "Traceback candidate-private-id secret",
    }
    app = AppTest.from_file(str(ROOT / "frontend/minori_frontend/pages/candidates.py")).run()
    assert not app.exception
    assert any(path == "/candidates" for _, path, _ in frontend_backend["_calls"])
    assert app.error
    assert "secret" not in app.error[0].value and "Traceback" not in app.error[0].value


def test_profile_escapes_backend_text(frontend_backend):
    frontend_backend["/candidates"][0]["full_name"] = '<img src=x onerror="alert(1)">'
    app = AppTest.from_file(str(ROOT / "frontend/minori_frontend/pages/candidates.py")).run()
    assert not app.exception
    assert "<img src=x" not in rendered_html(app)
    assert "&lt;img" in rendered_html(app)


def test_simulation_button_calls_existing_backend_contract(monkeypatch, frontend_backend):
    frontend_backend["_allowed_posts"]["/internal/reminders/simulate"] = None
    app = AppTest.from_file(str(ROOT / "frontend/minori_frontend/pages/reminder_center.py")).run()
    next(button for button in app.button if button.label == "Uji simulasi").click().run()
    assert not app.exception
    assert [
        (method, path, payload)
        for method, path, payload in frontend_backend["_calls"]
        if method == "POST"
    ] == [("POST", "/internal/reminders/simulate", {})]


def test_manual_draft_save_uses_backend_api(monkeypatch, frontend_backend):
    frontend_backend["_allowed_posts"]["/vacancies/drafts"] = {"id": "new-draft"}
    app = AppTest.from_file(
        str(ROOT / "frontend/minori_frontend/pages/ai_vacancy_intelligence.py")
    ).run()
    app.text_input(key="draft_new_title").set_value("Operator pertanian")
    app.text_input(key="draft_new_employer").set_value("Perusahaan Uji")
    next(button for button in app.button if button.label == "Simpan draf").click().run()
    assert not app.exception
    calls = [
        payload
        for method, path, payload in frontend_backend["_calls"]
        if method == "POST" and path == "/vacancies/drafts"
    ]
    assert len(calls) == 1
    assert calls[0]["proposed_data"]["title"] == "Operator pertanian"
    assert calls[0]["status"] == "draft"


def test_csv_quotes_fields_and_neutralizes_formulas():
    import csv
    import io

    from minori_frontend.pages.reports import to_csv

    result = list(
        csv.DictReader(io.StringIO(to_csv([{"Nama": 'Ayu, "Lestari"', "Catatan": "=1+1"}])))
    )
    assert result == [{"Nama": 'Ayu, "Lestari"', "Catatan": "'=1+1"}]


def test_frontend_reads_beyond_first_api_page():
    from minori_frontend.api_client import read_all

    source = [{"id": str(index)} for index in range(205)]
    offsets = []

    def page(*, limit, offset):
        offsets.append(offset)
        return source[offset : offset + limit]

    assert read_all(page) == source
    assert offsets == [0, 100, 200]


def test_reviewer_cannot_trigger_staff_operations(frontend_backend):
    app = AppTest.from_file(str(ROOT / "frontend/minori_frontend/pages/reminder_center.py"))
    app.session_state["auth_role"] = "reviewer"
    app.run()
    assert not app.exception
    assert all(
        button.disabled
        for button in app.button
        if button.label in {"Sinkronkan jadwal", "Pulihkan antrean", "Uji simulasi"}
    )
    assert not any(method == "POST" for method, _, _ in frontend_backend["_calls"])


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
