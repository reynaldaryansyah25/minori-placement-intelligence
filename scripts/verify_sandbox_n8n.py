"""Opt-in native n8n workflow + real SMTP verification in an isolated Compose project."""

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = "minori-n8n-sandbox-test"
WORKFLOW_ID = "MinoriSandboxReminders"
COMPOSE = [
    "docker",
    "compose",
    "-p",
    PROJECT,
    "-f",
    "compose.public-demo.yaml",
    "-f",
    "compose.n8n-sandbox-test.yaml",
]

PREAMBLE = """
import json,os,httpx
from pathlib import Path
from minori.core.config import get_settings
s=get_settings()
assert s.app_env=='test' and s.sandbox_enabled
state_file=Path('/tmp/minori-n8n-e2e.json')
state=json.loads(state_file.read_text()) if state_file.exists() else {}
c=httpx.Client(base_url='http://127.0.0.1:8000',timeout=30)
def call(path,method='GET',token=None,session=None,**kwargs):
 headers={'Authorization':'Bearer '+(token or s.sandbox_worker_token.get_secret_value())}
 if session: headers['X-Sandbox-Session']=session['id']
 r=c.request(method,path,headers=headers,**kwargs)
 r.raise_for_status()
 return r.json() if r.content else None
def public(index,path,method='GET',**kwargs):
 return call(path,method,token=state['sessions'][index]['token'],**kwargs)
def clock(when):
 call('/internal/demo/clock','POST',session=state['sessions'][0],json={'now':when})
def manual(index,template):
 rows=public(index,'/reminders')
 row=next(r for r in rows if r['delivery_kind']=='automatic' and r['template_code']==template and r['status'] in {'pending','sent'})
 return public(index,'/placements/'+row['placement_id']+'/activities/'+row['placement_stage_id']+'/email/prepare','POST')
def approve(index,row,key):
 preview=public(index,'/reminders/'+row['id']+'/email/template')
 payload={k:preview[k] for k in ('subject','body','facts_fingerprint')}
 payload.update(confirmed=True,idempotency_key=key)
 return public(index,'/reminders/'+row['id']+'/email/approve','POST',json=payload)
"""


def execute(service, command, code=None, *, environment=()):
    result = subprocess.run(
        [
            *COMPOSE,
            "exec",
            "-T",
            *[part for item in environment for part in ("-e", item)],
            service,
            *command,
        ],
        cwd=ROOT,
        input=code,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    if result.returncode:
        # Inputs/execution results can include claim tokens: never print subprocess output.
        diagnostics = re.findall(
            r"(?:line \d+|\b(?:AssertionError|KeyError|HTTPStatusError|TypeError|NodeOperationError)\b|\b[45]\d\d (?:Unauthorized|Forbidden|Unprocessable Entity|Conflict|Not Found))",
            result.stderr + result.stdout,
        )
        raise RuntimeError(
            f"Isolated {service} verification failed (exit {result.returncode}; {', '.join(diagnostics[-8:])})"
        )
    return result.stdout


def phase(code):
    value = execute(
        "backend-sandbox",
        ["python", "-"],
        PREAMBLE
        + "\n"
        + code
        + "\nstate_file.write_text(json.dumps(state));state_file.chmod(0o600)\n",
    )
    return json.loads(value)


def workflow():
    execute(
        "n8n-sandbox",
        ["n8n", "execute", "--id=" + WORKFLOW_ID],
        environment=(
            "N8N_RUNNERS_BROKER_PORT=5680",
            "N8N_LOG_LEVEL=info",
            "N8N_DISABLED_MODULES=mcp-registry",
        ),
    )


def mailbox():
    code = "fetch('http://mailpit-sandbox:8025/api/v1/messages').then(r=>r.json()).then(d=>console.log(JSON.stringify(d))).catch(()=>process.exit(1))"
    data = json.loads(execute("n8n-sandbox", ["node", "-e", code]))
    assert all(t["Address"] == "mailpit@minori.local" for m in data["messages"] for t in m["To"])
    return data


def smtp_port(port):
    # A closed port on the SAME local Mailpit hostname creates a real refused SMTP connection.
    credential = dict(
        id="MinoriSandboxSmtp",
        name="MINORI Sandbox Mailpit",
        type="smtp",
        data=dict(
            host="mailpit-sandbox",
            port=port,
            secure=False,
            disableStartTls=True,
            user="",
            password="",
        ),
    )
    code = (
        "const fs=require('fs');fs.writeFileSync('/tmp/smtp-test.json',JSON.stringify("
        + json.dumps([credential])
        + "),{mode:0o600});"
    )
    execute("n8n-sandbox", ["node", "-e", code])
    try:
        execute("n8n-sandbox", ["n8n", "import:credentials", "--input=/tmp/smtp-test.json"])
    finally:
        execute("n8n-sandbox", ["node", "-e", "require('fs').unlinkSync('/tmp/smtp-test.json')"])


def main():
    result_file = ROOT / "test-results/n8n-sandbox-e2e.json"
    result_file.parent.mkdir(exist_ok=True)
    result_file.unlink(missing_ok=True)
    report = []
    report.append(
        phase("""
state={'sessions':[]}
for index in range(2):
 before=set(call('/sandbox/worker/sessions')['sessions'])
 login=call('/sandbox/sessions','POST',token=s.sandbox_gateway_token.get_secret_value())
 identifier=(set(call('/sandbox/worker/sessions')['sessions'])-before).pop()
 state['sessions'].append({'id':identifier,'token':login['session_token']})
 # Move seeded catch-up demo schedules through the business API to exactly today's H-3/H-1.
 for row in public(index,'/reminders'):
  if row['delivery_kind']=='automatic' and row['scheduled_at']<'2026-10-14T02:00:00':
   when='2026-10-17T14:00:00+07:00' if row['template_code']=='interview_h3' else '2026-10-15T14:00:00+07:00'
   public(index,'/placements/'+row['placement_id']+'/activities/'+row['placement_stage_id'],'PATCH',json={'actor_reference':'demo.e2e','scheduled_at':when})
 assert call('/internal/reminders/due',session=state['sessions'][-1])==[]
row=manual(0,'interview_h3')
assert row['delivery_kind']=='manual'
state['manual']=row
print(json.dumps({'before_0900_due':0,'sessions':2,'manual_draft_unapproved':True}))
""")
    )
    workflow()
    assert mailbox()["total"] == 0
    phase("clock('2026-10-14T02:00:00Z');print('{}')")
    workflow()
    box = mailbox()
    assert box["total"] == 4
    references = [
        "mailpit:" + "".join(c for c in m["MessageID"] if c.isalnum() or c in "_.:-")[:100]
        for m in box["messages"]
    ]
    report.append(
        phase(
            """
for index in range(2):
 rows=public(index,'/reminders')
 sent=[r for r in rows if r['delivery_kind']=='automatic' and r['status']=='sent']
 assert len(sent)==2 and all(not r['approved_message'] and r['attempt_count']==1 for r in sent)
 for row in sent:
  attempt=public(index,'/reminders/'+row['id']+'/attempts')[0]
  assert attempt['provider_reference'] in """
            + repr(references)
            + """
assert public(0,'/reminders/'+state['manual']['id'])['status']=='pending'
assert public(0,'/reminders/'+state['manual']['id'])['attempt_count']==0
print(json.dumps({'automatic_0900_sent':4,'smtp_message_ids_verified':True,'unapproved_manual_not_sent':True}))
"""
        )
    )
    workflow()
    assert mailbox()["total"] == 4
    phase("approve(0,state['manual'],'e2e-manual-approved-001');print('{}')")
    workflow()
    assert mailbox()["total"] == 5
    report.append(
        phase("""
assert public(0,'/reminders/'+state['manual']['id'])['status']=='sent'
r=c.get('/reminders/'+state['manual']['id'],headers={'Authorization':'Bearer '+state['sessions'][1]['token']})
assert r.status_code==404
row=manual(1,'medical_h1');approve(1,row,'e2e-retry-approved-001');state['retry']=row
print(json.dumps({'manual_approved_sent':1,'cross_session_read_denied':True}))
""")
    )
    smtp_port(1026)
    try:
        workflow()
        report.append(
            phase("""
row=public(1,'/reminders/'+state['retry']['id'])
assert row['status']=='pending' and row['attempt_count']==1 and row['last_error_code']=='PROVIDER_UNAVAILABLE'
print(json.dumps({'real_smtp_failure_recorded':True,'retry_pending':True}))
""")
        )
    finally:
        smtp_port(1025)
    phase("clock('2026-10-14T02:00:11Z');print('{}')")
    workflow()
    assert mailbox()["total"] == 6
    report.append(
        phase("""
row=public(1,'/reminders/'+state['retry']['id'])
assert row['status']=='sent' and row['attempt_count']==2
assert len(public(1,'/reminders/'+row['id']+'/attempts'))==2
row=manual(1,'interview_h3');approve(1,row,'e2e-bounded-approved-001');state['failed']=row
print(json.dumps({'real_retry_smtp_sent':True,'attempts':2}))
""")
    )
    smtp_port(1026)
    try:
        for when in ("2026-10-14T02:00:11Z", "2026-10-14T02:00:22Z", "2026-10-14T02:00:43Z"):
            phase("clock(" + repr(when) + ");print('{}')")
            workflow()
        report.append(
            phase("""
row=public(1,'/reminders/'+state['failed']['id'])
assert row['status']=='failed' and row['attempt_count']==3
assert len(public(1,'/reminders/'+row['id']+'/attempts'))==3
assert public(0,'/sandbox/session')['used']['emails']==3
assert public(1,'/sandbox/session')['used']['emails']==4
print(json.dumps({'bounded_failure_attempts':3,'retry_does_not_spend_email_budget_again':True}))
""")
        )
        workflow()
        assert mailbox()["total"] == 6
    finally:
        smtp_port(1025)
    result = dict(
        passed=True,
        project=PROJECT,
        real_smtp_received=6,
        all_effective_recipients="mailpit@minori.local",
        workflow_engine="native n8n",
        phases=report,
        no_duplicate_after_repeat=True,
    )
    result_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
