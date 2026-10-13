"""Read-only reminder diagnostics; never print tokens or candidate payloads."""

import argparse
import hashlib
import inspect
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from minori.core.config import PROJECT_ROOT, Settings
from minori.db.session import resolve_database_url
from minori.services.placements import PlacementService
from minori.services.reminders import ReminderService


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--placement-reference", default="DEMO-PLC-AGRI")
    args = parser.parse_args()
    settings = Settings()
    path = Path(resolve_database_url(settings.database_url).database)
    sources = {}
    for service in (PlacementService, ReminderService):
        loaded = Path(inspect.getfile(service))
        checkout = PROJECT_ROOT / "backend/minori/services" / loaded.name
        sources[service.__name__] = {
            "loaded_path": str(loaded),
            "loaded_sha256": hashlib.sha256(loaded.read_bytes()).hexdigest(),
            "checkout_sha256": hashlib.sha256(checkout.read_bytes()).hexdigest(),
        }
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row

        def rows(sql, parameters=()):
            return [dict(row) for row in connection.execute(sql, parameters)]

        placements = rows(
            "SELECT id, status FROM placements WHERE reference = ?",
            (args.placement_reference,),
        )
        report = {
            "utc_now": datetime.now(UTC).isoformat(),
            "database_path": str(path),
            "schema": rows("SELECT version_num FROM alembic_version"),
            "sources": sources,
            "routing": {
                "dry_run": settings.notification_dry_run,
                "mode": settings.notification_delivery_mode,
                "demo_override_set": bool(settings.demo_notification_recipient),
            },
            "placements": placements,
        }
        if placements:
            params = (placements[0]["id"],)
            report["activities"] = rows(
                "SELECT code, step_type, status, scheduled_at, schedule_revision "
                "FROM placement_stages WHERE placement_id = ?",
                params,
            )
            report["notifications"] = rows(
                "SELECT template_code, status, scheduled_at, available_at, event_at, managed "
                "FROM notifications WHERE placement_id = ?",
                params,
            )
            report["candidate_status"] = rows(
                "SELECT status FROM candidates WHERE id = "
                "(SELECT candidate_id FROM placements WHERE id = ?)",
                params,
            )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
