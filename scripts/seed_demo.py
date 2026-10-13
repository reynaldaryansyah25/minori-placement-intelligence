"""Seed rich demo fixtures explicitly and idempotently without duplicating records."""

import json

from minori.core.config import PROJECT_ROOT, get_settings
from minori.db.seeding import seed_database
from minori.db.session import Database


def main() -> None:
    settings = get_settings()
    database = Database(settings)
    try:
        result = seed_database(database, fixture_directory=PROJECT_ROOT / "data/demo")
        print(json.dumps(result, indent=2))
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
