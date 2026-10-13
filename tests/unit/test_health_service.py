"""Health behavior depends on an injected port, without infrastructure imports."""

import pytest
from minori.domain.health import DatabaseStatus, HealthStatus
from minori.services.health import HealthService


class StubDatabaseProbe:
    def __init__(self, ready: bool):
        self.ready = ready

    def is_ready(self) -> bool:
        return self.ready


@pytest.mark.parametrize("ready", [True, False])
def test_health_reports_database_readiness(ready):
    report = HealthService(StubDatabaseProbe(ready)).check()
    assert report.status == (HealthStatus.OK if ready else HealthStatus.DEGRADED)
    assert report.database == (DatabaseStatus.OK if ready else DatabaseStatus.UNAVAILABLE)
