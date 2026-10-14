"""Server-owned demo sessions, private SQLite copies, and bounded resource budgets."""

import hashlib
import json
import secrets
import sqlite3
import time
from collections import deque
from dataclasses import dataclass, field
from threading import RLock

from alembic import command
from alembic.config import Config

from minori.core.config import PROJECT_ROOT
from minori.db.professional_demo import seed_professional_demo
from minori.db.session import Database


class SandboxDenied(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message
        super().__init__(message)


@dataclass
class DemoSession:
    identifier: str
    digest: str
    database: Database
    created: float
    touched: float
    counts: dict = field(
        default_factory=lambda: dict(ai=0, writes=0, emails=0, uploads=0, resets=0)
    )
    email_keys: set = field(default_factory=set)
    active: int = 0
    revoked: bool = False
    requests: deque = field(default_factory=deque)


class DemoSandbox:
    """One backend process owns sessions. Restart invalidates access; resets retain budgets."""

    def __init__(self, settings, clock=time.time):
        self.settings, self.clock = settings, clock
        self.root = settings.sandbox_root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        marker = self.root / ".minori-sandbox"
        if not marker.exists() and any(self.root.iterdir()):
            raise RuntimeError("Refusing an unverified sandbox directory")
        marker.write_text("Synthetic demo databases only\n", encoding="utf-8")
        self.lock = RLock()
        self.sessions = {}
        self.births = deque()
        self.global_usage = dict(ai=deque(), emails=deque())
        self.journal = self.root / "resource-usage.json"
        if self.journal.exists():
            saved = json.loads(self.journal.read_text(encoding="utf-8"))
            self.births.extend(saved.get("births", []))
            for key in self.global_usage:
                self.global_usage[key].extend(saved.get(key, []))
        # Only our own previous session files can be reclaimed after a process restart.
        for path in self.root.glob("session-*.db*"):
            if path.is_file():
                path.unlink()
        self.template = self.root / "template.db"
        for suffix in ("", "-wal", "-shm"):
            self.template.with_name(self.template.name + suffix).unlink(missing_ok=True)
        config = Config(str(PROJECT_ROOT / "alembic.ini"))
        config.attributes["settings"] = settings
        command.upgrade(config, "head")
        template_db = Database(settings)
        try:
            seed_professional_demo(template_db, dry_run=False)
        finally:
            template_db.dispose()

    def _persist_usage(self):
        saved = {key: list(values) for key, values in self.global_usage.items()}
        saved["births"] = list(self.births)
        temporary = self.journal.with_suffix(".tmp")
        temporary.write_text(json.dumps(saved), encoding="utf-8")
        temporary.replace(self.journal)

    def _trim(self):
        now = self.clock()
        for values in (self.births, *self.global_usage.values()):
            while values and values[0] <= now - 3600:
                values.popleft()
        for identifier, row in list(self.sessions.items()):
            if not row.active and now > row.touched + self.settings.sandbox_session_seconds + 300:
                self._dispose(row)
                del self.sessions[identifier]

    def _alive(self, row):
        now = self.clock()
        return (
            not row.revoked
            and now - row.created < self.settings.sandbox_session_seconds
            and now - row.touched < self.settings.sandbox_idle_seconds
        )

    def _copy(self, identifier, generation=0):
        path = self.root / f"session-{identifier}-{generation}.db"
        with sqlite3.connect(self.template) as source, sqlite3.connect(path) as target:
            source.backup(target)
            if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("Sandbox copy integrity failed")
            if target.execute("PRAGMA foreign_key_check").fetchall():
                raise RuntimeError("Sandbox copy relations failed")
        settings = self.settings.model_copy(update={"database_url": "sqlite:///" + path.as_posix()})
        return Database(settings)

    def create(self):
        with self.lock:
            self._trim()
            if (
                len(self.births) >= 12
                or sum(self._alive(r) for r in self.sessions.values())
                >= self.settings.sandbox_max_sessions
            ):
                raise SandboxDenied(429, "Kapasitas sesi demo sedang penuh. Coba kembali nanti.")
            token, identifier = secrets.token_urlsafe(32), secrets.token_hex(16)
            now = self.clock()
            row = DemoSession(
                identifier,
                hashlib.sha256(token.encode()).hexdigest(),
                self._copy(identifier),
                now,
                now,
            )
            self.sessions[identifier] = row
            self.births.append(now)
            self._persist_usage()
            return token, row

    def authenticate(self, token):
        digest = hashlib.sha256(token.encode()).hexdigest()
        with self.lock:
            self._trim()
            row = next(
                (r for r in self.sessions.values() if secrets.compare_digest(r.digest, digest)),
                None,
            )
            if row is None or not self._alive(row):
                raise SandboxDenied(401, "Sesi demo berakhir. Silakan masuk kembali.")
            return row

    def worker_session(self, identifier, *, callback=False):
        with self.lock:
            row = self.sessions.get(identifier)
            if row is None or (not callback and not self._alive(row)):
                raise SandboxDenied(401, "Sesi demo tidak tersedia.")
            return row

    def begin(self, row, *, touch=True):
        with self.lock:
            if touch:
                if not self._alive(row):
                    raise SandboxDenied(401, "Sesi demo berakhir. Silakan masuk kembali.")
                now = self.clock()
                while row.requests and row.requests[0] < now - 60:
                    row.requests.popleft()
                if len(row.requests) >= 120:
                    raise SandboxDenied(429, "Terlalu banyak permintaan. Tunggu satu menit.")
                row.requests.append(now)
            row.active += 1
            if touch:
                row.touched = self.clock()

    def finish(self, row):
        with self.lock:
            row.active -= 1

    def consume(self, row, kind, amount=1, *, key=None):
        with self.lock:
            self._trim()
            if key and key in row.email_keys:
                return
            limit = getattr(
                self.settings,
                f"sandbox_{ {'ai': 'ai', 'writes': 'write', 'emails': 'email', 'uploads': 'upload'}[kind] }_limit",
            )
            if row.counts[kind] + amount > limit:
                raise SandboxDenied(
                    429,
                    "Batas penggunaan sesi demo tercapai. Reset data tidak menghapus batas penggunaan.",
                )
            if kind in self.global_usage:
                values = self.global_usage[kind]
                cap = getattr(
                    self.settings, f"sandbox_hourly_{'ai' if kind == 'ai' else 'email'}_limit"
                )
                if len(values) + amount > cap:
                    raise SandboxDenied(
                        429, "Batas layanan demo per jam tercapai. Coba kembali nanti."
                    )
                values.extend([self.clock()] * amount)
                self._persist_usage()
            row.counts[kind] += amount
            if key:
                row.email_keys.add(key)

    def usage(self, row):
        return {
            "environment": "sandbox",
            "role": "demo_operator",
            "used": dict(row.counts),
            "limits": dict(
                ai=self.settings.sandbox_ai_limit,
                writes=self.settings.sandbox_write_limit,
                emails=self.settings.sandbox_email_limit,
                uploads=self.settings.sandbox_upload_limit,
                resets=2,
            ),
        }

    def reset(self, row):
        with self.lock:
            if row.active or row.counts["resets"] >= 2:
                raise SandboxDenied(
                    409, "Reset belum tersedia: tunggu proses selesai atau batas reset tercapai."
                )
            with row.database.engine.connect() as connection:
                if connection.exec_driver_sql(
                    "SELECT count(*) FROM notifications WHERE status='processing'"
                ).scalar():
                    raise SandboxDenied(
                        409, "Tunggu pengiriman yang sedang diproses sebelum reset."
                    )
            row.counts["resets"] += 1
            replacement = self._copy(row.identifier, row.counts["resets"])
            # Original copy is retained as a private backup until the session is reclaimed.
            row.database.dispose()
            row.database = replacement
            return self.usage(row)

    def revoke(self, row):
        with self.lock:
            row.revoked = True

    def _dispose(self, row):
        row.database.dispose()
        for path in self.root.glob(f"session-{row.identifier}-*.db*"):
            if path.is_file():
                path.unlink()

    def close(self):
        for row in self.sessions.values():
            row.database.dispose()
