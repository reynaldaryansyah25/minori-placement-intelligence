"""FastAPI composition root and application resource lifecycle."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from minori import __version__
from minori.api.ai_input_limits import AiInputLimitMiddleware
from minori.api.routes.ai import router as ai_router
from minori.api.routes.auth import router as auth_router
from minori.api.routes.candidates import router as candidate_router
from minori.api.routes.health import router as health_router
from minori.api.routes.matching import router as matching_router
from minori.api.routes.overview import router as overview_router
from minori.api.routes.placements import router as placement_router
from minori.api.routes.reminders import internal_router
from minori.api.routes.reminders import router as reminder_router
from minori.api.routes.vacancies import router as vacancy_router
from minori.core.config import Settings, get_settings
from minori.core.logging import configure_logging
from minori.db.session import Database

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create an isolated app; initialize and dispose database resources in lifespan."""
    configuration = settings if settings is not None else get_settings()
    configure_logging(configuration.log_level)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        database = Database(configuration)
        application.state.database = database
        logger.info("MINORI backend started")
        try:
            yield
        finally:
            database.dispose()
            logger.info("MINORI backend stopped")

    application = FastAPI(
        title=configuration.app_name,
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs" if configuration.app_env != "production" else None,
        redoc_url=None,
        openapi_url="/openapi.json" if configuration.app_env != "production" else None,
    )
    application.state.settings = configuration

    application.add_middleware(AiInputLimitMiddleware)

    @application.exception_handler(RequestValidationError)
    async def safe_ai_validation(request: Request, exc: RequestValidationError):
        if request.url.path.startswith("/ai/") or "/email/" in request.url.path:
            return JSONResponse(
                status_code=422,
                content={"detail": "Periksa format masukan dan batas ukuran dokumen."},
            )
        from fastapi.exception_handlers import request_validation_exception_handler

        return await request_validation_exception_handler(request, exc)

    application.include_router(health_router)
    application.include_router(auth_router)
    application.include_router(ai_router)
    application.include_router(overview_router)
    application.include_router(candidate_router)
    application.include_router(vacancy_router)
    application.include_router(matching_router)
    application.include_router(placement_router)
    application.include_router(reminder_router)
    application.include_router(internal_router)
    return application
