"""Alembic configuration sharing the application's SQLite engine settings."""

from alembic import context
from minori.core.config import get_settings
from minori.core.logging import configure_logging
from minori.db.base import Base
from minori.db.session import Database, resolve_database_url

# Import future ORM models here so autogenerate can see their metadata.
target_metadata = Base.metadata
settings = get_settings()
configure_logging(settings.log_level)


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
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                render_as_batch=True,
                compare_type=True,
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        database.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
