"""Verify migration heads, registered business tables, and SQLite integrity."""

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import func, inspect, select, text

from minori.core.config import PROJECT_ROOT
from minori.db.models import MODEL_TYPES
from minori.db.session import Database


def migration_heads() -> set[str]:
    return set(ScriptDirectory.from_config(Config(str(PROJECT_ROOT / "alembic.ini"))).get_heads())


def inspect_database(database: Database) -> dict[str, object]:
    with database.engine.connect() as connection:
        tables = set(inspect(connection).get_table_names())
        required = {model.__tablename__ for model in MODEL_TYPES}.union({"alembic_version"})
        if not required.issubset(tables):
            raise RuntimeError("Required tables are missing; run Alembic upgrade head")
        versions = set(
            connection.execute(text("SELECT version_num FROM alembic_version")).scalars()
        )
        if versions != migration_heads():
            raise RuntimeError("Database is not at the current Alembic head")
        if connection.execute(text("PRAGMA foreign_key_check")).all():
            raise RuntimeError("Database contains foreign key violations")
        if connection.execute(text("PRAGMA integrity_check")).scalar_one() != "ok":
            raise RuntimeError("SQLite integrity check failed")
        foreign_keys = connection.execute(text("PRAGMA foreign_keys")).scalar_one()
        if foreign_keys != 1:
            raise RuntimeError("Foreign key enforcement is disabled")
        counts = {
            model.__tablename__: connection.scalar(select(func.count()).select_from(model))
            for model in MODEL_TYPES
        }
        for model in MODEL_TYPES:
            actual = {col["name"] for col in inspect(connection).get_columns(model.__tablename__)}
            if not set(model.__table__.columns.keys()).issubset(actual):
                raise RuntimeError(f"Required columns missing from {model.__tablename__}")
        return {
            "select_one": connection.execute(text("SELECT 1")).scalar_one(),
            "foreign_keys": foreign_keys,
            "journal_mode": connection.execute(text("PRAGMA journal_mode")).scalar_one(),
            "migration_revision": sorted(versions),
            "expected_heads": sorted(migration_heads()),
            "tables": sorted(tables),
            "counts": counts,
            "integrity": "ok",
        }
