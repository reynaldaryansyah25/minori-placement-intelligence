"""Verify the configured SQLite database without logging its location or credentials."""

import json

from minori.core.config import get_settings
from minori.db.session import Database
from sqlalchemy import inspect, text


def main() -> None:
    database = Database(get_settings())
    try:
        with database.engine.connect() as connection:
            scalar = connection.execute(text("SELECT 1")).scalar_one()
            foreign_keys = connection.execute(text("PRAGMA foreign_keys")).scalar_one()
            journal_mode = connection.execute(text("PRAGMA journal_mode")).scalar_one()
            revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            tables = inspect(connection).get_table_names()
        assert scalar == 1
        assert foreign_keys == 1
        assert revision == "foundation"
        print(
            json.dumps(
                {
                    "select_one": scalar,
                    "foreign_keys": foreign_keys,
                    "journal_mode": journal_mode,
                    "migration_revision": revision,
                    "tables": tables,
                }
            )
        )
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
