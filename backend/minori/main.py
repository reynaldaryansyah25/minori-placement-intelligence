"""FastAPI composition root and application resource lifecycle."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from minori import __version__
from minori.api.routes.health import router as health_router
from minori.api.routes.matching import router as matching_router
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
    application.include_router(health_router)
    application.include_router(matching_router)
    return application
