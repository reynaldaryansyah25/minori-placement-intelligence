"""Bounded HTTP requests for the operational frontend."""

import httpx

from minori_frontend.config import FrontendSettings


class BackendClient:
    def __init__(self, settings: FrontendSettings) -> None:
        self._settings = settings

    def get_health(self) -> dict[str, object]:
        url = str(self._settings.backend_base_url).rstrip("/") + "/health"
        response = httpx.get(url, timeout=self._settings.http_timeout_seconds)
        response.raise_for_status()
        return response.json()
