"""Build synthetic profile fingerprints from the trusted seed in a disposable database."""

import json
import tempfile
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from minori.core.config import PROJECT_ROOT, Settings
from minori.db.professional_demo import seed_professional_demo
from minori.db.session import Database
from minori.repositories.provider import provide_repositories
from minori_frontend.public_data import profile_digest


def main():
    with tempfile.TemporaryDirectory(prefix="minori-public-catalog-") as directory:
        settings = Settings(
            _env_file=None,
            app_env="test",
            database_url="sqlite:///" + (Path(directory) / "catalog.db").as_posix(),
        )
        config = Config(str(PROJECT_ROOT / "alembic.ini"))
        database = Database(settings)
        try:
            # Existing Alembic env obtains Settings directly, rather than Config's URL.
            with patch("minori.core.config.get_settings", return_value=settings):
                command.upgrade(config, "head")
            seed_professional_demo(database, anchor=datetime(2026, 10, 14, 5, tzinfo=UTC))
            with database.session_factory() as session:
                ports = provide_repositories(session)
                catalog = {
                    kind: {
                        r.reference: profile_digest(json.loads(json.dumps(asdict(r), default=str)))
                        for r in repo.list(limit=100)
                    }
                    for kind, repo in [
                        ("candidates", ports.candidate),
                        ("vacancies", ports.vacancy),
                        ("drafts", ports.vacancy_draft),
                    ]
                }
        finally:
            database.dispose()
    path = PROJECT_ROOT / "frontend/minori_frontend/public_catalog.py"
    path.write_text(
        '"""Fingerprints of verified synthetic seed profiles; never contains live records."""\n\nCATALOG = '
        + repr(catalog)
        + "\n",
        encoding="utf-8",
    )
    print("Synthetic public catalog built from an isolated temporary database.")


if __name__ == "__main__":
    main()
