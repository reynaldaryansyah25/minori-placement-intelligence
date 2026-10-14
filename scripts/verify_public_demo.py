"""Read-only runtime preflight. Never starts Funnel, modifies data, or logs credentials."""

import json
import re
import subprocess
from pathlib import Path
from uuid import uuid4

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def verify():
    cfg = dotenv_values(ROOT / ".env")
    reviewer, admin = cfg.get("REVIEWER_API_TOKEN"), cfg.get("INTERNAL_API_TOKEN")
    if not reviewer or not admin or reviewer == admin:
        raise RuntimeError("Distinct configured reviewer/staff credentials are required")
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=30) as client:
        assert client.get("/candidates").status_code == 401
        for token, role in [(reviewer, "reviewer"), (admin, "admin")]:
            identity = client.get("/auth/me", headers={"Authorization": "Bearer " + token})
            assert identity.is_success and identity.json()["role"] == role
        assert client.get("/candidates", headers={"Authorization": "Bearer " + reviewer}).is_success
        # These are rejected by authorization before any operation executes.
        checked = 0
        schema = client.get("/openapi.json").json()
        for path, operations in schema["paths"].items():
            target = re.sub(r"\{[^}]+\}", lambda _: str(uuid4()), path)
            for method in {key.upper() for key in operations} & {"POST", "PUT", "PATCH", "DELETE"}:
                expected = 401 if path.startswith("/internal/") else 403
                assert (
                    client.request(
                        method, target, json={}, headers={"Authorization": "Bearer " + reviewer}
                    ).status_code
                    == expected
                ), (method, path)
                assert client.request(method, target, json={}).status_code == 401, (method, path)
                checked += 1
        assert checked >= 20
        assert client.get("http://127.0.0.1:8502/_stcore/health").status_code == 200
        assert client.get("http://127.0.0.1:8501/_stcore/health").status_code == 200
    raw = subprocess.check_output(
        ["docker", "inspect", "minori-placement-intelligence-frontend-public-1"], text=True
    )
    container = json.loads(raw)[0]
    names = {entry.split("=", 1)[0] for entry in container["Config"]["Env"]}
    environment = dict(entry.split("=", 1) for entry in container["Config"]["Env"])
    assert "INTERNAL_API_TOKEN" not in names
    assert not names & {"NINE_ROUTER_API_KEY", "N8N_ENCRYPTION_KEY", "DATABASE_URL"}
    assert "REVIEWER_API_TOKEN" in names and container["HostConfig"]["ReadonlyRootfs"]
    assert environment["PUBLIC_REVIEWER_MODE"] == "true"
    assert environment["REVIEWER_API_TOKEN"] == reviewer
    assert environment["PUBLIC_DEMO_USERNAME"] == cfg["PUBLIC_DEMO_USERNAME"]
    assert environment["PUBLIC_DEMO_PASSWORD_HASH"] == cfg["PUBLIC_DEMO_PASSWORD_HASH"]
    assert environment["STREAMLIT_SERVER_ENABLE_CORS"] == "true"
    assert environment["STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION"] == "true"
    assert environment["STREAMLIT_BROWSER_SERVER_ADDRESS"] == cfg.get(
        "PUBLIC_DEMO_HOST", "localhost"
    )
    assert container["HostConfig"]["RestartPolicy"]["Name"] == "unless-stopped"
    assert container["State"]["Health"]["Status"] == "healthy"
    assert all(mount["Type"] == "tmpfs" for mount in container["Mounts"])
    project_ids = subprocess.check_output(
        [
            "docker",
            "ps",
            "-q",
            "--filter",
            "label=com.docker.compose.project=minori-placement-intelligence",
        ],
        text=True,
    ).split()
    for identifier in project_ids:
        service = json.loads(subprocess.check_output(["docker", "inspect", identifier], text=True))[
            0
        ]
        for mappings in (service["HostConfig"]["PortBindings"] or {}).values():
            assert all(m["HostIp"] in {"127.0.0.1", "::1"} for m in mappings), service["Name"]
    print(
        json.dumps(
            {
                "passed": True,
                "write_routes_rejected_for_reviewer_and_anonymous": checked,
                "reviewer_read": True,
                "staff_role": "admin",
                "staff_frontend_healthy": True,
                "public_frontend_healthy": True,
                "public_admin_credentials_absent": True,
                "docker_host_ports_loopback_only": True,
                "funnel_started_by_script": False,
            }
        )
    )


if __name__ == "__main__":
    verify()
