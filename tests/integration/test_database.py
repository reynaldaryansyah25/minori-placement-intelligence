"""Verify SQLite pragmas, path resolution, and memory database behavior."""

from minori.core.config import Settings
from minori.db.session import Database, resolve_database_url
from sqlalchemy import text


def test_file_database_has_foreign_keys_and_wal(settings):
    database = Database(settings)
    try:
        with database.engine.connect() as connection:
            assert connection.execute(text("SELECT 1")).scalar_one() == 1
            assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
            assert connection.execute(text("PRAGMA journal_mode")).scalar_one() == "wal"
            assert connection.execute(text("PRAGMA busy_timeout")).scalar_one() == 5000
    finally:
        database.dispose()


def test_relative_database_paths_do_not_depend_on_shell_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path.parent)
    url = resolve_database_url("sqlite:///./runtime/minori.db", root=tmp_path)
    assert url.database == str((tmp_path / "runtime/minori.db").resolve())


def test_memory_database_is_shared_across_sessions():
    database = Database(Settings(_env_file=None, database_url="sqlite:///:memory:"))
    try:
        with database.session_factory() as session:
            session.execute(text("CREATE TABLE connection_probe (value INTEGER)"))
            session.execute(text("INSERT INTO connection_probe VALUES (1)"))
            session.commit()
        with database.session_factory() as session:
            assert session.execute(text("SELECT value FROM connection_probe")).scalar_one() == 1
    finally:
        database.dispose()
