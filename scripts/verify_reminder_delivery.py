"""Verify isolated Compose HTTP callbacks and optional delivery ONLY to test Mailpit."""

import argparse
import json
import smtplib
import time
from datetime import UTC, datetime
from email.message import EmailMessage
from email.utils import make_msgid

import httpx
from minori.core.config import get_settings
from prepare_reminder_demo import prepare_demo, request


def verify(client, *, send_mailpit=False):
    scenario = prepare_demo(client, datetime.now(UTC).strftime("%Y%m%d%H%M%S%f"))
    rows = scenario["reminders"]
    assert all(row["dry_run"] != send_mailpit for row in rows)
    processed = []
    for index, row in enumerate(rows):
        identifier = row["id"]
        claim = request(
            client, "POST", "/internal/reminders/claim", {"notification_id": identifier}
        )
        assert claim["notification"]["status"] == "processing"
        assert (
            request(client, "POST", "/internal/reminders/claim", {"notification_id": identifier})
            is None
        )
        if index == 1:
            failure = {"claim_token": claim["claim_token"], "error_code": "PROVIDER_TIMEOUT"}
            failed = request(client, "POST", f"/internal/reminders/{identifier}/fail", failure)
            assert failed["status"] == "pending" and failed["last_error_code"] == "PROVIDER_TIMEOUT"
            assert (
                request(client, "POST", f"/internal/reminders/{identifier}/fail", failure) == failed
            )
            assert (
                request(
                    client, "POST", "/internal/reminders/claim", {"notification_id": identifier}
                )
                is None
            )
            available = datetime.fromisoformat(failed["available_at"])
            delay = (available - datetime.now(UTC)).total_seconds()
            assert delay < 5, "Use the isolated Compose retry settings"
            time.sleep(max(0, delay) + 0.1)
            claim = request(
                client, "POST", "/internal/reminders/claim", {"notification_id": identifier}
            )
            assert claim["notification"]["attempt_count"] == 2
            stale = client.post(
                f"/internal/reminders/{identifier}/complete",
                json={
                    "claim_token": failure["claim_token"],
                    "outcome": "sent" if send_mailpit else "simulated",
                    **({"provider_reference": "stale"} if send_mailpit else {}),
                },
            )
            assert stale.status_code == 409
        routing = claim["recipient_routing"]
        callback = {"claim_token": claim["claim_token"], "outcome": "simulated"}
        if send_mailpit:
            assert routing["routing_mode"] == "mailpit" and routing["delivery_allowed"] is True
            assert routing["effective_recipient"] == "mailpit@minori.local"
            message = EmailMessage()
            message["From"] = "reminder-test@minori.local"
            message["To"] = routing["effective_recipient"]
            message["Subject"] = claim["message"]["subject"]
            message["Message-ID"] = make_msgid(domain="minori.local")
            message["X-Minori-Notification-ID"] = identifier
            message.set_content(claim["message"]["body"])
            # Fixed local Compose host, no provider URL/recipient CLI override, no relay config.
            with smtplib.SMTP("mailpit-reminder-test", 1025, timeout=5) as smtp:
                assert not smtp.send_message(message)
            with httpx.Client(base_url="http://mailpit-reminder-test:8025", timeout=5) as mailpit:
                messages = mailpit.get("/api/v1/messages").json()["messages"]
                captured = next(
                    item
                    for item in messages
                    if item["MessageID"] == str(message["Message-ID"]).strip("<>")
                )
                assert [item["Address"] for item in captured["To"]] == [
                    routing["effective_recipient"]
                ]
            callback.update(outcome="sent", provider_reference="mailpit:" + captured["ID"])
        else:
            assert routing["delivery_allowed"] is False and routing["effective_recipient"] is None
        result = request(client, "POST", f"/internal/reminders/{identifier}/complete", callback)
        assert result["status"] == ("sent" if send_mailpit else "simulated")
        assert bool(result["sent_at"]) == send_mailpit
        assert (
            request(client, "POST", f"/internal/reminders/{identifier}/complete", callback)
            == result
        )
        attempts = request(client, "GET", f"/reminders/{identifier}/attempts")
        assert len(attempts) == index + 1
        assert attempts[-1]["status"] == ("succeeded" if send_mailpit else "simulated")
        assert (
            request(client, "POST", "/internal/reminders/claim", {"notification_id": identifier})
            is None
        )
        processed.append(
            {
                "template": row["template_code"],
                "status": result["status"],
                "attempts": len(attempts),
            }
        )
    assert not {row["id"] for row in rows} & {
        row["id"] for row in request(client, "GET", "/internal/reminders/due")
    }
    return {
        "passed": True,
        "initial_due_count": 2,
        "mailpit_verified": send_mailpit,
        "processed": processed,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--send-mailpit", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    if settings.app_env != "test" or not settings.database_url.endswith("/reminder-test.db"):
        raise SystemExit("Run only inside the isolated backend-reminder-test service")
    with httpx.Client(
        base_url="http://127.0.0.1:8000",
        timeout=10,
        headers={"Authorization": "Bearer " + settings.internal_api_token.get_secret_value()},
    ) as client:
        print(json.dumps(verify(client, send_mailpit=args.send_mailpit), indent=2))


if __name__ == "__main__":
    main()
