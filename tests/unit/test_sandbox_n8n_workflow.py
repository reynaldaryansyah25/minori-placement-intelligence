"""Exercise the shipped native workflow guards with adversarial delivery inputs."""

import json
import shutil
import subprocess
from copy import deepcopy
from pathlib import Path

import pytest

WORKFLOW = json.loads(
    (Path(__file__).resolve().parents[2] / "workflows/sandbox/reminders.json").read_text(
        encoding="utf-8"
    )
)
NODES = {node["name"]: node for node in WORKFLOW["nodes"]}


def run_code(name, items, lookups=None):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for native n8n Code-node guard tests")
    script = """
const data=JSON.parse(process.argv[1]);
const input={all:()=>data.items,first:()=>data.items[0]};
const lookup=name=>({itemMatching:i=>data.lookups[name][i]});
const result=new Function('$input','$',data.code)(input,lookup);
process.stdout.write(JSON.stringify(result));
"""
    result = subprocess.run(
        [
            node,
            "-e",
            script,
            json.dumps(
                dict(items=items, lookups=lookups or {}, code=NODES[name]["parameters"]["jsCode"])
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return json.loads(result.stdout)


def claim():
    return dict(
        session_id="a" * 32,
        notification=dict(
            delivery_kind="automatic", template_code="interview_h3", managed=True, dry_run=False
        ),
        recipient_routing=dict(
            delivery_allowed=True,
            routing_mode="mailpit",
            effective_recipient="mailpit@minori.local",
        ),
        message=dict(subject="Pengingat wawancara", body="Jadwal sintetis yang dikonfirmasi."),
    )


@pytest.mark.parametrize(
    "override",
    [
        {"recipient_routing": {"delivery_allowed": False}},
        {"recipient_routing": {"effective_recipient": "person@example.com"}},
        {"recipient_routing": {"routing_mode": "demo_recipient"}},
        {"notification": {"dry_run": True}},
        {"notification": {"managed": False}},
        {"notification": {"template_code": "documents_schedule"}},
        {"notification": {"delivery_kind": "manual"}},
        {"message": {"subject": "test\r\nBcc: person@example.com"}},
        {"message": {"body": "x" * 8001}},
    ],
)
def test_native_guard_blocks_external_or_unapproved_delivery(override):
    unsafe = deepcopy(claim())
    for section, fields in override.items():
        unsafe[section].update(fields)
    safe, rejected = run_code("Validasi Tujuan", [{"json": claim()}, {"json": unsafe}])
    assert safe["json"]["route_allowed"] is True
    assert rejected["json"]["route_allowed"] is False


def test_manual_email_requires_snapshot_and_approval_identity():
    manual = claim()
    manual["notification"].update(
        delivery_kind="manual",
        approved_message=manual["message"],
        approved_at="2026-10-14T02:00:00Z",
        approved_by="demo.operator",
    )
    assert run_code("Validasi Tujuan", [{"json": manual}])[0]["json"]["route_allowed"]


def test_multi_session_due_fanout_keeps_session_pairing():
    items = [
        {"json": {"statusCode": 200, "body": [{"id": "first"}, {"id": "second"}]}},
        {"json": {"statusCode": 200, "body": [{"id": "third"}]}},
    ]
    result = run_code(
        "Pisahkan Pengingat",
        items,
        {"Sesi Siap": [{"json": {"session_id": "a" * 32}}, {"json": {"session_id": "b" * 32}}]},
    )
    assert [r["json"]["session_id"] for r in result] == ["a" * 32, "a" * 32, "b" * 32]
    assert [r["pairedItem"]["item"] for r in result] == [0, 0, 1]


def test_smtp_receipt_requires_accepted_local_recipient_and_message_id():
    items = [
        {"json": {"accepted": ["mailpit@minori.local"], "messageId": "<local@minori.invalid>"}},
        {"json": {"accepted": ["elsewhere@example.com"], "messageId": "fake"}},
        {"json": {"accepted": ["mailpit@minori.local"]}},
    ]
    result = run_code("Hasil SMTP", items, {"Validasi Klaim": [{"json": claim()}] * 3})
    assert [r["json"]["smtp_sent"] for r in result] == [True, False, False]
    assert result[0]["json"]["provider_reference"] == "mailpit:localminori.invalid"


def test_callback_retry_and_schedule_are_bounded_without_smtp_retry():
    assert WORKFLOW["settings"]["timezone"] == "Asia/Jakarta"
    assert WORKFLOW["settings"]["saveDataSuccessExecution"] == "none"
    assert WORKFLOW["settings"]["saveDataErrorExecution"] == "none"
    assert not NODES["SMTP Mailpit Sandbox"].get("retryOnFail")
    for name in ("Catat Terkirim", "Catat Gagal", "Catat Simulasi"):
        assert NODES[name]["retryOnFail"] and NODES[name]["maxTries"] == 3
    intervals = NODES["Polling 15 detik"]["parameters"]["rule"]["interval"]
    assert {"field": "cronExpression", "expression": "0 9 * * *"} in intervals
    assert all("$env" not in json.dumps(n) for n in WORKFLOW["nodes"])
