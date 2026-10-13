"""Readiness endpoint; no external AI request is involved."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response

from minori import __version__
from minori.api.dependencies import get_app_settings, get_health_service
from minori.core.config import Settings
from minori.domain.health import HealthStatus
from minori.schemas.health import HealthResponse
from minori.services.health import HealthService

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, responses={503: {"model": HealthResponse}})
def get_health(
    response: Response,
    settings: Annotated[Settings, Depends(get_app_settings)],
    health_service: Annotated[HealthService, Depends(get_health_service)],
) -> HealthResponse:
    report = health_service.check()
    if report.status != HealthStatus.OK:
        response.status_code = 503
    return HealthResponse(
        status=report.status,
        application=settings.app_name,
        version=__version__,
        database=report.database,
    )
