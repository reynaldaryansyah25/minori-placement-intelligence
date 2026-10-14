"""Seed the isolated verification database, without resets or SMTP."""

import json

from minori.core.config import get_settings
from minori.db.professional_demo import seed_professional_demo
from minori.db.session import Database


def main():
    settings = get_settings()
    if settings.app_env not in {"demo", "test"}:
        raise SystemExit("Professional synthetic seed is restricted to demo/test")
    database = Database(settings)
    try:
        print(
            json.dumps(
                seed_professional_demo(
                    database, anchor=settings.demo_clock_at, dry_run=settings.notification_dry_run
                ),
                indent=2,
            )
        )
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
