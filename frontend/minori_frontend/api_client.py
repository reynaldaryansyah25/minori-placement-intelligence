"""HTTP client connecting the Streamlit frontend to the FastAPI backend."""

from typing import Any

import httpx

from minori_frontend.config import FrontendSettings


class ApiClientError(Exception):
    """Structured error carrying HTTP status and humanized detail."""

    def __init__(self, status_code: int, message: str, detail: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.detail = detail or message


class BackendClient:
    """Robust client with connection pooling, server-side auth, and error mapping."""

    def __init__(self, settings: FrontendSettings) -> None:
        self._settings = settings
        self._base_url = str(settings.backend_base_url).rstrip("/")
        self._timeout = settings.http_timeout_seconds

    def _headers(self, token: str | None = None) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        # Read token passed explicitly, or from session_state if available, or settings
        chosen_token = token
        if not chosen_token:
            try:
                import streamlit as st

                chosen_token = st.session_state.get("auth_token")
            except Exception:
                pass
        if not chosen_token and self._settings.internal_api_token:
            chosen_token = self._settings.internal_api_token.get_secret_value()

        if chosen_token:
            headers["Authorization"] = f"Bearer {chosen_token}"
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        token: str | None = None,
    ) -> Any:
        url = f"{self._base_url}{path}"
        cleaned_params = {k: str(v) for k, v in params.items() if v is not None} if params else None
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.request(
                    method=method,
                    url=url,
                    params=cleaned_params,
                    json=json,
                    headers=self._headers(token),
                )
        except httpx.ConnectError as exc:
            raise ApiClientError(
                503,
                "Tidak dapat terhubung ke server backend. Pastikan backend aktif.",
                str(exc),
            ) from exc
        except httpx.TimeoutException as exc:
            raise ApiClientError(
                504,
                "Permintaan ke backend timeout. Coba beberapa saat lagi.",
                str(exc),
            ) from exc
        except httpx.HTTPError as exc:
            raise ApiClientError(
                500,
                f"Kesalahan komunikasi HTTP: {exc}",
                str(exc),
            ) from exc

        if response.status_code >= 400:
            error_detail = "Terjadi kesalahan"
            try:
                payload = response.json()
                if isinstance(payload, dict):
                    error_detail = payload.get("detail", str(payload))
            except Exception:
                error_detail = response.text or f"HTTP {response.status_code}"

            if response.status_code == 401:
                msg = "Akses ditolak: Token autentikasi tidak valid atau belum diisi."
            elif response.status_code == 403:
                msg = "Akses dibatasi: Anda berada dalam mode Read-Only / Reviewer."
            elif response.status_code == 404:
                msg = f"Data tidak ditemukan: {error_detail}"
            elif response.status_code == 409:
                msg = f"Konflik bisnis / aturan database: {error_detail}"
            elif response.status_code == 422:
                msg = f"Data masukan tidak valid: {error_detail}"
            elif response.status_code == 503:
                msg = "Layanan backend atau database sedang tidak tersedia."
            else:
                msg = f"Error {response.status_code}: {error_detail}"

            raise ApiClientError(response.status_code, msg, error_detail)

        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    # --- Health & Auth ---
    def get_health(self) -> dict[str, Any]:
        url = f"{self._base_url}/health"
        try:
            response = httpx.get(url, timeout=self._timeout)
            response.raise_for_status()
            return response.json()
        except httpx.ConnectError as exc:
            raise ApiClientError(
                503,
                "Tidak dapat terhubung ke server backend. Pastikan backend aktif.",
                str(exc),
            ) from exc
        except httpx.HTTPError as exc:
            raise ApiClientError(
                500,
                f"Kesalahan komunikasi HTTP: {exc}",
                str(exc),
            ) from exc

    def verify_token(self, token: str) -> dict[str, Any]:
        return self._request("GET", "/auth/me", token=token)

    # --- Overview ---
    def get_overview_summary(self) -> dict[str, Any]:
        return self._request("GET", "/overview/summary")

    # --- Candidates ---
    def list_candidates(
        self,
        *,
        query: str | None = None,
        program: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        return self._request(
            "GET",
            "/candidates",
            params={
                "query": query,
                "preferred_program": program,
                "status": status,
                "limit": limit,
                "offset": offset,
            },
        )

    def get_candidate(self, candidate_id: str) -> dict[str, Any]:
        return self._request("GET", f"/candidates/{candidate_id}")

    def create_candidate(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/candidates", json=payload)

    def replace_candidate(self, candidate_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("PUT", f"/candidates/{candidate_id}", json=payload)

    def archive_candidate(self, candidate_id: str) -> dict[str, Any]:
        return self._request("DELETE", f"/candidates/{candidate_id}")

    # --- Vacancies ---
    def list_vacancies(
        self,
        *,
        query: str | None = None,
        program: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        return self._request(
            "GET",
            "/vacancies",
            params={
                "query": query,
                "program": program,
                "status": status,
                "limit": limit,
                "offset": offset,
            },
        )

    def get_vacancy(self, vacancy_id: str) -> dict[str, Any]:
        return self._request("GET", f"/vacancies/{vacancy_id}")

    def create_vacancy(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/vacancies", json=payload)

    def replace_vacancy(self, vacancy_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("PUT", f"/vacancies/{vacancy_id}", json=payload)

    def close_vacancy(self, vacancy_id: str) -> dict[str, Any]:
        return self._request("DELETE", f"/vacancies/{vacancy_id}")

    # --- Vacancy Drafts ---
    def list_vacancy_drafts(
        self,
        *,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        return self._request(
            "GET",
            "/vacancies/drafts",
            params={"status": status, "limit": limit, "offset": offset},
        )

    def get_vacancy_draft(self, draft_id: str) -> dict[str, Any]:
        return self._request("GET", f"/vacancies/drafts/{draft_id}")

    def create_vacancy_draft(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/vacancies/drafts", json=payload)

    def update_vacancy_draft(self, draft_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("PUT", f"/vacancies/drafts/{draft_id}", json=payload)

    def publish_vacancy_draft(self, draft_id: str) -> dict[str, Any]:
        return self._request("POST", f"/vacancies/drafts/{draft_id}/publish")

    # --- Matching ---
    def evaluate_matching(
        self,
        *,
        candidate_id: str | None = None,
        vacancy_id: str | None = None,
        as_of: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {}
        if candidate_id:
            body["candidate_id"] = candidate_id
        if vacancy_id:
            body["vacancy_id"] = vacancy_id
        if as_of:
            body["as_of"] = as_of
        return self._request("POST", "/matching/evaluations", json=body)

    def list_matching_results(
        self,
        *,
        candidate_id: str | None = None,
        vacancy_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        return self._request(
            "GET",
            "/matching/results",
            params={
                "candidate_id": candidate_id,
                "vacancy_id": vacancy_id,
                "limit": limit,
                "offset": offset,
            },
        )

    def get_matching_result(self, evaluation_id: str) -> dict[str, Any]:
        return self._request("GET", f"/matching/results/{evaluation_id}")

    def get_ranking(
        self, vacancy_id: str, *, limit: int = 100, offset: int = 0
    ) -> list[dict[str, Any]]:
        return self._request(
            "GET",
            f"/matching/vacancies/{vacancy_id}/ranking",
            params={"limit": limit, "offset": offset},
        )

    def get_explanation(self, candidate_id: str, vacancy_id: str) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/matching/candidates/{candidate_id}/vacancies/{vacancy_id}/explanation",
        )

    def decide_match(
        self,
        candidate_id: str,
        vacancy_id: str,
        decision: str,
        actor_reference: str,
        reason_code: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "candidate_id": candidate_id,
            "vacancy_id": vacancy_id,
            "decision": decision,
            "actor_reference": actor_reference,
        }
        if reason_code:
            payload["reason_code"] = reason_code
        return self._request("POST", "/matching/decisions", json=payload)

    # --- Placements ---
    def list_placements(
        self,
        *,
        query: str | None = None,
        status: str | None = None,
        candidate_id: str | None = None,
        vacancy_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        return self._request(
            "GET",
            "/placements",
            params={
                "query": query,
                "status": status,
                "candidate_id": candidate_id,
                "vacancy_id": vacancy_id,
                "limit": limit,
                "offset": offset,
            },
        )

    def get_placement(self, placement_id: str) -> dict[str, Any]:
        return self._request("GET", f"/placements/{placement_id}")

    def create_placement(
        self,
        reference: str,
        match_id: str,
        actor_reference: str,
        planned_departure_at: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "reference": reference,
            "match_id": match_id,
            "actor_reference": actor_reference,
        }
        if planned_departure_at:
            payload["planned_departure_at"] = planned_departure_at
        return self._request("POST", "/placements", json=payload)

    def update_placement(
        self,
        placement_id: str,
        actor_reference: str,
        *,
        status: str | None = None,
        planned_departure_at: str | None = None,
        actual_departure_at: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"actor_reference": actor_reference}
        if status:
            payload["status"] = status
        if planned_departure_at:
            payload["planned_departure_at"] = planned_departure_at
        if actual_departure_at:
            payload["actual_departure_at"] = actual_departure_at
        return self._request("PATCH", f"/placements/{placement_id}", json=payload)

    def cancel_placement(self, placement_id: str, actor_reference: str) -> dict[str, Any]:
        return self._request(
            "DELETE",
            f"/placements/{placement_id}",
            json={"actor_reference": actor_reference},
        )

    def list_activities(self, placement_id: str) -> list[dict[str, Any]]:
        return self._request("GET", f"/placements/{placement_id}/activities")

    def create_activity(self, placement_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", f"/placements/{placement_id}/activities", json=payload)

    def update_activity(
        self, placement_id: str, activity_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return self._request(
            "PATCH", f"/placements/{placement_id}/activities/{activity_id}", json=payload
        )

    # --- Reminders ---
    def list_reminders(
        self,
        *,
        status: str | None = None,
        due_before: str | None = None,
        placement_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        return self._request(
            "GET",
            "/reminders",
            params={
                "status": status,
                "due_before": due_before,
                "placement_id": placement_id,
                "limit": limit,
                "offset": offset,
            },
        )

    def get_reminder(self, notification_id: str) -> dict[str, Any]:
        return self._request("GET", f"/reminders/{notification_id}")

    def get_reminder_attempts(
        self, notification_id: str, *, limit: int = 100, offset: int = 0
    ) -> list[dict[str, Any]]:
        return self._request(
            "GET",
            f"/reminders/{notification_id}/attempts",
            params={"limit": limit, "offset": offset},
        )

    def get_recipient_routing(self, notification_id: str) -> dict[str, Any]:
        return self._request("GET", f"/reminders/{notification_id}/routing")

    def generate_reminders(self) -> list[dict[str, Any]]:
        return self._request("POST", "/internal/reminders/generate")

    def recover_reminders(self) -> dict[str, Any]:
        return self._request("POST", "/internal/reminders/recover")

    def simulate_reminder(self, notification_id: str | None = None) -> dict[str, Any] | None:
        payload = {"notification_id": notification_id} if notification_id else {}
        return self._request("POST", "/internal/reminders/simulate", json=payload)

    # --- Audit Logs ---
    def list_audit_logs(
        self,
        *,
        entity_type: str | None = None,
        entity_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        return self._request(
            "GET",
            "/audit-logs",
            params={
                "entity_type": entity_type,
                "entity_id": entity_id,
                "limit": limit,
                "offset": offset,
            },
        )
