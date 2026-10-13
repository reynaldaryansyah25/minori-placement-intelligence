"""Public health response contract."""

from pydantic import BaseModel, ConfigDict

from minori.domain.health import DatabaseStatus, HealthStatus


class HealthResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: HealthStatus
    application: str
    version: str
    database: DatabaseStatus
