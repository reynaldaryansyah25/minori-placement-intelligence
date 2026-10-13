"""Verify running Compose services without exporting environment secrets."""

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import urlopen

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]


class ContainerPorts(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    backend_port: int = Field(default=8000, ge=1, le=65535)
    frontend_port: int = Field(default=8501, ge=1, le=65535)
    n8n_port: int = Field(default=5678, ge=1, le=65535)


def compose(*arguments: str) -> str:
    completed = subprocess.run(
        ["docker", "compose", *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode:
        raise RuntimeError(f"Docker Compose {' '.join(arguments[:2])} failed")
    return completed.stdout.strip()


def get_http(port: int, path: str) -> tuple[int, str]:
    with urlopen(f"http://127.0.0.1:{port}{path}", timeout=10) as response:
        return response.status, response.read().decode()


def main() -> None:
    results = ROOT / "test-results"
    results.mkdir(exist_ok=True)
    report = {
        "executed_at": datetime.now(timezone(timedelta(hours=7))).isoformat(),
        "passed": False,
    }
    try:
        compose("config", "--quiet")
        rows = compose("ps", "--format", "json")
        containers = (
            json.loads(rows)
            if rows.startswith("[")
            else [json.loads(line) for line in rows.splitlines()]
        )
        services = {
            item["Service"]: {"state": item["State"], "health": item.get("Health", "")}
            for item in containers
        }
        for name in ("backend", "frontend", "n8n"):
            assert services[name] == {"state": "running", "health": "healthy"}
        ports = ContainerPorts()
        _, backend_text = get_http(ports.backend_port, "/health")
        backend_health = json.loads(backend_text)
        assert backend_health["status"] == "ok" and backend_health["database"] == "ok"
        _, frontend_health = get_http(ports.frontend_port, "/_stcore/health")
        assert frontend_health == "ok"
        frontend_status, _ = get_http(ports.frontend_port, "/")
        _, n8n_text = get_http(ports.n8n_port, "/healthz/readiness")
        n8n_health = json.loads(n8n_text)
        assert n8n_health["status"] == "ok"
        network_probe = json.loads(
            compose(
                "exec",
                "-T",
                "frontend",
                "python",
                "-c",
                "import urllib.request; "
                "print(urllib.request.urlopen('http://backend:8000/health', "
                "timeout=5).read().decode())",
            )
        )
        assert network_probe["database"] == "ok"
        n8n_network_probe = json.loads(
            compose(
                "exec",
                "-T",
                "n8n",
                "node",
                "-e",
                "fetch('http://backend:8000/health', {signal: AbortSignal.timeout(5000)})"
                ".then(r=>r.json()).then(d=>console.log(JSON.stringify(d)))"
                ".catch(()=>process.exit(1))",
            )
        )
        assert n8n_network_probe["status"] == "ok" and n8n_network_probe["database"] == "ok"
        backend_dependency_check = compose("exec", "-T", "backend", "python", "-m", "pip", "check")
        frontend_dependency_check = compose(
            "exec", "-T", "frontend", "python", "-m", "pip", "check"
        )
        database_probe = json.loads(
            compose(
                "exec",
                "-T",
                "backend",
                "python",
                "scripts/check_database.py",
            )
        )
        assert database_probe["migration_revision"] == database_probe["expected_heads"]
        assert database_probe["foreign_keys"] == 1 and database_probe["journal_mode"] == "wal"
        assert database_probe["integrity"] == "ok"
        report.update(
            {
                "passed": True,
                "services": services,
                "backend_health": backend_health,
                "frontend_health": frontend_health,
                "frontend_http_status": frontend_status,
                "n8n_health": n8n_health,
                "frontend_to_backend": network_probe["status"],
                "n8n_to_backend": n8n_network_probe["status"],
                "database": database_probe,
                "backend_dependencies": backend_dependency_check,
                "frontend_dependencies": frontend_dependency_check,
                "container_python": compose("exec", "-T", "backend", "python", "--version"),
                "n8n_version": compose("exec", "-T", "n8n", "n8n", "--version"),
            }
        )
    except Exception as error:
        report["error"] = type(error).__name__
        raise
    finally:
        (results / "containers.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
