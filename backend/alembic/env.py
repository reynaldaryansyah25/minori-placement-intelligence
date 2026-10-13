"""Alembic configuration sharing the application's SQLite engine settings."""

from alembic import context
from minori.core.config import get_settings
from minori.core.logging import configure_logging
from minori.db import models  # noqa: F401 -- register ORM metadata
from minori.db.base import Base
from minori.db.models.common import UTCDateTime
from minori.db.session import Database, resolve_database_url

# Models are registered above so autogenerate sees every business table.
target_metadata = Base.metadata
settings = get_settings()
configure_logging(settings.log_level)


def render_type(kind, value, autogen_context):
    """Freeze SQLite storage types rather than importing mutable application types."""
    if kind == "type" and isinstance(value, UTCDateTime):
        return "sa.DateTime()"
    return False


def run_migrations_offline() -> None:
    context.configure(
        url=resolve_database_url(settings.database_url),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    database = Database(settings)
    try:
        with database.engine.connect() as connection:
            # SQLite batch rebuilds referenced tables. Disable FK enforcement only for
            # this migration connection, use transactional DDL, and validate before commit.
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            connection.commit()
            try:
                connection.exec_driver_sql("BEGIN IMMEDIATE")
                context.configure(
                    connection=connection,
                    target_metadata=target_metadata,
                    render_as_batch=True,
                    compare_type=True,
                    render_item=render_type,
                )
                with context.begin_transaction():
                    context.run_migrations()
                if connection.exec_driver_sql("PRAGMA foreign_key_check").all():
                    raise RuntimeError("Migration produced foreign key violations")
                connection.commit()
            except BaseException:
                connection.rollback()
                raise
            finally:
                connection.exec_driver_sql("PRAGMA foreign_keys=ON")
                connection.commit()
    finally:
        database.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
