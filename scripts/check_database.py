"""Verify registered business tables against the current Alembic head."""

import json

from minori.core.config import get_settings
from minori.db.inspection import inspect_database
from minori.db.session import Database


def main() -> None:
    database = Database(get_settings())
    try:
        print(json.dumps(inspect_database(database), indent=2))
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
