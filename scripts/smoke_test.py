"""Start real backend and Streamlit processes, verify HTTP, then stop both."""

import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def available_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def wait_for_http(url: str, process: subprocess.Popen) -> bytes:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Service exited before its health endpoint was ready")
        try:
            with urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return response.read()
        except (URLError, TimeoutError, ConnectionError):
            time.sleep(0.25)
    raise RuntimeError("Service did not become ready within 30 seconds")


def main() -> None:
    results = ROOT / "test-results"
    results.mkdir(exist_ok=True)
    backend_port, frontend_port = available_port(), available_port()
    environment = os.environ.copy()
    environment["LLM_ENABLED"] = "false"
    environment["BACKEND_BASE_URL"] = f"http://127.0.0.1:{backend_port}"
    processes = []
    report = {
        "executed_at": datetime.now(timezone(timedelta(hours=7))).isoformat(),
        "passed": False,
    }
    with (
        (results / "backend_runtime.log").open("w", encoding="utf-8") as backend_log,
        (results / "frontend_runtime.log").open("w", encoding="utf-8") as frontend_log,
    ):
        try:
            backend = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "minori.main:create_app",
                    "--factory",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(backend_port),
                ],
                cwd=ROOT,
                env=environment,
                stdout=backend_log,
                stderr=subprocess.STDOUT,
            )
            processes.append(backend)
            health = json.loads(wait_for_http(f"http://127.0.0.1:{backend_port}/health", backend))
            assert health["status"] == "ok" and health["database"] == "ok"
            frontend = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "streamlit",
                    "run",
                    "minori_frontend/app.py",
                    "--server.address=127.0.0.1",
                    f"--server.port={frontend_port}",
                ],
                cwd=ROOT / "frontend",
                env=environment,
                stdout=frontend_log,
                stderr=subprocess.STDOUT,
            )
            processes.append(frontend)
            streamlit_health = wait_for_http(
                f"http://127.0.0.1:{frontend_port}/_stcore/health", frontend
            ).decode()
            assert streamlit_health == "ok"
            with urlopen(f"http://127.0.0.1:{frontend_port}", timeout=5) as response:
                assert response.status == 200
            report.update(
                {
                    "passed": True,
                    "backend_health": health,
                    "streamlit_health": streamlit_health,
                    "frontend_http_status": 200,
                }
            )
        except Exception as error:
            report["error"] = type(error).__name__
            raise
        finally:
            for process in reversed(processes):
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            (results / "smoke.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
