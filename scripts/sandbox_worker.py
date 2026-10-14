"""Isolated HTTP queue worker: SMTP only to its private Mailpit service, never the internet."""

import logging
import os
import smtplib
import time
from email.message import EmailMessage

import httpx

logger = logging.getLogger("sandbox-worker")
INBOX = "mailpit@minori.local"


def process_session(client, identifier, smtp_factory=smtplib.SMTP):
    headers = {"X-Sandbox-Session": identifier}

    def request(method, path, payload=None):
        response = client.request(method, path, headers=headers, json=payload)
        response.raise_for_status()
        return response.json() if response.content else None

    request("POST", "/internal/reminders/recover")
    rows = request("GET", "/internal/reminders/due")
    processed = 0
    for row in rows[:5]:
        claimed = request("POST", "/internal/reminders/claim", {"notification_id": row["id"]})
        if not claimed:
            continue
        notification = claimed["notification"]
        token = claimed["claim_token"]
        path = "/internal/reminders/" + notification["id"]
        routing = claimed["recipient_routing"]
        if notification["dry_run"]:
            request("POST", path + "/complete", {"claim_token": token, "outcome": "simulated"})
            continue
        if (
            not routing["delivery_allowed"]
            or routing["routing_mode"] != "mailpit"
            or routing["effective_recipient"] != INBOX
        ):
            request(
                "POST", path + "/fail", {"claim_token": token, "error_code": "PROVIDER_REJECTED"}
            )
            continue
        # The recipient/SMTP host cannot be supplied by a reviewer, schedule, or LLM.
        message = EmailMessage()
        message["From"] = "MINORI Placement Intelligence <sandbox@minori.invalid>"
        message["To"] = INBOX
        message["Subject"] = claimed["message"]["subject"]
        reference = f"mailpit:sandbox-{notification['id']}-{notification['attempt_count']}"
        message["Message-ID"] = (
            f"<sandbox-{notification['id']}-{notification['attempt_count']}@minori.invalid>"
        )
        message.set_content(claimed["message"]["body"])
        try:
            with smtp_factory("mailpit-sandbox", 1025, timeout=10) as smtp:
                smtp.send_message(message)
        except (OSError, smtplib.SMTPException):
            request(
                "POST", path + "/fail", {"claim_token": token, "error_code": "PROVIDER_UNAVAILABLE"}
            )
            logger.warning("Sandbox SMTP failed; bounded queue retry scheduled")
            continue
        # Never report SMTP failure after SMTP accepted a message. A failed callback
        # remains an uncertain result; lease recovery may retry and duplicate it.
        request(
            "POST",
            path + "/complete",
            {"claim_token": token, "outcome": "sent", "provider_reference": reference},
        )
        processed += 1
    return processed


def main():
    logging.basicConfig(level=logging.WARNING)
    token = os.environ["SANDBOX_WORKER_TOKEN"]
    with httpx.Client(
        base_url="http://backend-sandbox:8000",
        timeout=30,
        headers={"Authorization": "Bearer " + token},
    ) as client:
        while True:
            try:
                response = client.get("/sandbox/worker/sessions")
                response.raise_for_status()
                for identifier in response.json()["sessions"]:
                    try:
                        process_session(client, identifier)
                    except httpx.HTTPError:
                        logger.warning("Sandbox queue unavailable; no sensitive details logged")
            except httpx.HTTPError:
                logger.warning("Sandbox backend unavailable")
            time.sleep(3)


if __name__ == "__main__":
    main()
