"""SQLite engine with bounded waits and explicit session ownership."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from minori.core.config import PROJECT_ROOT, Settings


@contextmanager
def immediate_transaction(session: Session):
    """Reserve SQLite's writer before quota or queue reads; commit or rollback as one unit."""
    if session.in_transaction():
        raise RuntimeError("An immediate transaction requires a fresh session")
    try:
        session.connection().exec_driver_sql("BEGIN IMMEDIATE")
        yield
        session.commit()
    except BaseException:
        session.rollback()
        raise


def resolve_database_url(value: str, root: Path = PROJECT_ROOT) -> URL:
    """Resolve relative SQLite files against the repository, not the shell cwd."""
    url = make_url(value)
    if url.database and url.database != ":memory:":
        location = Path(url.database).expanduser()
        if not location.is_absolute():
            location = root / location
        url = url.set(database=str(location.resolve()))
    return url


class Database:
    """Own an engine and sessions; schema changes belong exclusively to Alembic."""

    def __init__(self, settings: Settings) -> None:
        url = resolve_database_url(settings.database_url)
        in_memory = not url.database or url.database == ":memory:"
        if not in_memory:
            Path(url.database).parent.mkdir(parents=True, exist_ok=True)
        options = {"poolclass": StaticPool} if in_memory else {}
        self.engine: Engine = create_engine(
            url,
            connect_args={
                "check_same_thread": False,
                "timeout": settings.sqlite_timeout_seconds,
            },
            pool_pre_ping=True,
            **options,
        )
        timeout_ms = int(settings.sqlite_timeout_seconds * 1000)

        @event.listens_for(self.engine, "connect")
        def configure_sqlite(connection, _connection_record) -> None:
            cursor = connection.cursor()
            try:
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute(f"PRAGMA busy_timeout={timeout_ms}")
                if not in_memory:
                    cursor.execute("PRAGMA journal_mode=WAL")
            finally:
                cursor.close()

        self.session_factory = sessionmaker(
            bind=self.engine, autoflush=False, expire_on_commit=False
        )

    def sessions(self) -> Iterator[Session]:
        """Yield a session and always close it; writes must commit explicitly."""
        with self.session_factory() as session:
            yield session

    def dispose(self) -> None:
        self.engine.dispose()
