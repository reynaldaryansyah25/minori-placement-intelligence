"""Read-only runtime evidence: primary DB, workflow, credentials, and Funnel remain unchanged."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "minori-placement-intelligence-"
BASELINE = ROOT / "test-results" / "sandbox-isolation-baseline.json"


def output(*args):
    return subprocess.check_output(list(args), text=True).strip()


def inspect(service):
    return json.loads(output("docker", "inspect", PREFIX + service + "-1"))[0]


def snapshot():
    containers = {}
    for name in ("backend", "frontend", "n8n", "mailpit-demo"):
        item = inspect(name)
        containers[name] = {
            "id": item["Id"],
            "credentials_digest": hashlib.sha256(
                json.dumps(item["Config"]["Env"], sort_keys=True).encode()
            ).hexdigest(),
        }
    code = "import sqlite3,hashlib; from minori.core.config import get_settings; from sqlalchemy.engine import make_url; p=make_url(get_settings().database_url).database; c=sqlite3.connect('file:'+p+'?mode=ro',uri=True); print(hashlib.sha256('\\n'.join(c.iterdump()).encode()).hexdigest())"
    database = output("docker", "exec", PREFIX + "backend-1", "python", "-c", code)
    # Read only workflow definitions, not execution logs or credential values.
    code = "const fs=require('fs');const crypto=require('crypto');const {DatabaseSync}=require('node:sqlite');const d=new DatabaseSync('/home/node/.n8n/database.sqlite',{readOnly:true});const r=d.prepare('SELECT id,name,active,nodes,connections FROM workflow_entity ORDER BY id').all();process.stdout.write(crypto.createHash('sha256').update(JSON.stringify(r)).digest('hex'));"
    workflow = output("docker", "exec", PREFIX + "n8n-1", "node", "--no-warnings", "-e", code)
    tailscale = Path("C:/Program Files/Tailscale/tailscale.exe")
    funnel = output(str(tailscale), "serve", "status", "--json")
    return {
        "primary_containers": containers,
        "database_digest": database,
        "workflow_digest": workflow,
        "funnel_digest": hashlib.sha256(funnel.encode()).hexdigest(),
    }


def verify_boundaries():
    cfg = dotenv_values(ROOT / ".env")
    frontend = inspect("frontend-public")
    environment = dict(item.split("=", 1) for item in frontend["Config"]["Env"])
    assert environment["BACKEND_BASE_URL"] == "http://backend-sandbox:8000"
    assert (
        not {
            "INTERNAL_API_TOKEN",
            "REVIEWER_API_TOKEN",
            "NINE_ROUTER_API_KEY",
            "SANDBOX_WORKER_TOKEN",
            "DATABASE_URL",
        }
        & environment.keys()
    )
    main_networks = set(inspect("backend")["NetworkSettings"]["Networks"])
    main_mounts = {m["Source"] for m in inspect("backend")["Mounts"]}
    for name in ("frontend-public", "backend-sandbox", "n8n-sandbox", "mailpit-sandbox"):
        item = inspect(name)
        assert not main_networks & set(item["NetworkSettings"]["Networks"])
        assert not main_mounts & {m["Source"] for m in item["Mounts"]}
        if name != "frontend-public":
            assert not item["HostConfig"]["PortBindings"]
    sandbox_n8n = inspect("n8n-sandbox")
    n8n_env = dict(item.split("=", 1) for item in sandbox_n8n["Config"]["Env"])
    main_n8n = inspect("n8n")
    main_n8n_env = dict(item.split("=", 1) for item in main_n8n["Config"]["Env"])
    assert n8n_env["N8N_ENCRYPTION_KEY"] != main_n8n_env["N8N_ENCRYPTION_KEY"]
    assert (
        not {
            "INTERNAL_API_TOKEN",
            "REVIEWER_API_TOKEN",
            "SANDBOX_GATEWAY_TOKEN",
            "NINE_ROUTER_API_KEY",
        }
        & n8n_env.keys()
    )
    assert not {m["Source"] for m in main_n8n["Mounts"]} & {
        m["Source"] for m in sandbox_n8n["Mounts"]
    }
    for network in sandbox_n8n["NetworkSettings"]["Networks"]:
        assert json.loads(output("docker", "network", "inspect", network))[0]["Internal"]
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=30) as client:
        for name in ("SANDBOX_GATEWAY_TOKEN", "SANDBOX_WORKER_TOKEN"):
            headers = {"Authorization": "Bearer " + cfg[name]}
            assert client.get("/candidates", headers=headers).status_code == 401
            assert client.post("/candidates", headers=headers, json={}).status_code == 401
        assert (
            client.get(
                "/auth/me", headers={"Authorization": "Bearer " + cfg["INTERNAL_API_TOKEN"]}
            ).json()["role"]
            == "admin"
        )
    assert httpx.get("http://127.0.0.1:8501/_stcore/health").status_code == 200
    print(
        "PASS: sandbox has no main credentials, volumes, networks, or host API ports; primary rejects sandbox credentials; local admin healthy."
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", action="store_true")
    args = parser.parse_args()
    current = snapshot()
    if args.record:
        if BASELINE.exists():
            raise SystemExit("Baseline already exists; do not overwrite evidence")
        BASELINE.parent.mkdir(exist_ok=True)
        BASELINE.write_text(json.dumps(current, indent=2), encoding="utf-8")
        print("Recorded primary-system fingerprints; no credentials or business data exported.")
    else:
        assert current == json.loads(BASELINE.read_text(encoding="utf-8")), (
            "Primary system changed; compare digests before proceeding"
        )
        verify_boundaries()
        print(
            "PASS: primary containers, DB, n8n workflow definitions, credentials, and Funnel configuration unchanged."
        )


if __name__ == "__main__":
    main()
