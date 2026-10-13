"""Readiness use case with dependency inversion."""

from minori.domain.health import DatabaseStatus, HealthReport, HealthStatus
from minori.domain.ports import DatabaseProbe


class HealthService:
    def __init__(self, database_probe: DatabaseProbe) -> None:
        self._database_probe = database_probe

    def check(self) -> HealthReport:
        ready = self._database_probe.is_ready()
        return HealthReport(
            status=HealthStatus.OK if ready else HealthStatus.DEGRADED,
            database=DatabaseStatus.OK if ready else DatabaseStatus.UNAVAILABLE,
        )
