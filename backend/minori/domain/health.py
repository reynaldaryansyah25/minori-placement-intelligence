"""Health values independent of HTTP and persistence libraries."""

from dataclasses import dataclass
from enum import StrEnum


class HealthStatus(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"


class DatabaseStatus(StrEnum):
    OK = "ok"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class HealthReport:
    status: HealthStatus
    database: DatabaseStatus
