"""Create a separate synthetic reminder scenario via HTTP, preserving existing records."""

import argparse
import json
import re
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from minori.core.config import PROJECT_ROOT, get_settings


def request(client, method, path, payload=None, **kwargs):
    response = client.request(method, path, json=payload, **kwargs)
    if response.status_code not in {200, 201}:
        # Do not include response bodies containing candidate or configuration data.
        raise RuntimeError(f"HTTP {response.status_code}: {method} {path}")
    return response.json()


def activity_times(now, timezone="Asia/Jakarta"):
    """For a given anchor, both calendar reminders are due and both events are future."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Anchor must have a timezone")
    local = now.astimezone(ZoneInfo(timezone))
    before_delivery = (local.hour, local.minute) < (9, 0)
    return {
        "interview": (local + timedelta(days=2 if before_delivery else 3)).replace(
            hour=14, minute=0, second=0, microsecond=0
        ),
        "medical_check": (local + timedelta(days=0 if before_delivery else 1)).replace(
            hour=14, minute=0, second=0, microsecond=0
        ),
    }


def prepare_demo(client, run_id, now=None):
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9-]{0,24}", run_id):
        raise ValueError("Run ID must be 1..25 uppercase letters, digits or hyphens")
    now = now or datetime.now(UTC)
    prefix = "DEMO-RMD-" + run_id
    # Refuse collisions before the first write. Never PUT, DELETE or update old records.
    for endpoint, suffix in (("candidates", "CAND"), ("vacancies", "VAC"), ("placements", "PLC")):
        reference = f"{prefix}-{suffix}"
        if any(
            row["reference"] == reference
            for row in request(client, "GET", f"/{endpoint}", params={"query": reference})
        ):
            raise ValueError("Run ID already exists; use a new Run ID to preserve its history")
    candidate = json.loads((PROJECT_ROOT / "data/dummy/candidates.json").read_text())["candidates"][
        0
    ]
    vacancy = json.loads((PROJECT_ROOT / "data/dummy/vacancies.json").read_text())["vacancies"][0]
    candidate.update(reference=prefix + "-CAND", full_name="Kandidat Uji Reminder", status="ready")
    vacancy.update(
        reference=prefix + "-VAC",
        status="open",
        quota=1,
        application_deadline=(now + timedelta(days=365)).isoformat(),
    )
    candidate = request(client, "POST", "/candidates", candidate)
    vacancy = request(client, "POST", "/vacancies", vacancy)
    actor = "staff.reminder_test"
    match = request(
        client,
        "POST",
        "/matching/decisions",
        {
            "candidate_id": candidate["id"],
            "vacancy_id": vacancy["id"],
            "decision": "approved",
            "actor_reference": actor,
        },
    )
    placement = request(
        client,
        "POST",
        "/placements",
        {
            "reference": prefix + "-PLC",
            "match_id": match["id"],
            "actor_reference": actor,
        },
    )
    activities = []
    for sequence, (kind, scheduled_at) in enumerate(activity_times(now).items(), 1):
        activities.append(
            request(
                client,
                "POST",
                f"/placements/{placement['id']}/activities",
                {
                    "code": "INTERVIEW_UJI_H3_01" if kind == "interview" else "MEDICAL_UJI_H1_01",
                    "step_type": kind,
                    "sequence_number": sequence,
                    "scheduled_at": scheduled_at.isoformat(),
                    "location": "Ruang Uji Lokal",
                    "actor_reference": actor,
                },
            )
        )
    reminders = request(client, "GET", "/reminders", params={"placement_id": placement["id"]})
    # No /generate call: activity creation itself must persist both notifications.
    assert len(reminders) == 2
    assert {row["template_code"] for row in reminders} == {"interview_h3", "medical_h1"}
    assert {row["placement_stage_id"] for row in reminders} == {row["id"] for row in activities}
    due = request(client, "GET", "/internal/reminders/due")
    assert {row["id"] for row in reminders} <= {row["id"] for row in due}
    return {
        "placement_id": placement["id"],
        "placement_reference": placement["reference"],
        "anchor": now.isoformat(),
        "due_count": len(reminders),
        "reminders": [
            {
                key: row[key]
                for key in ("id", "template_code", "scheduled_at", "event_at", "dry_run")
            }
            for row in reminders
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--run-id", default=datetime.now(UTC).strftime("%Y%m%d%H%M%S"))
    parser.add_argument("--at", type=datetime.fromisoformat)
    args = parser.parse_args()
    settings = get_settings()
    if settings.app_env == "production" or not settings.internal_api_token:
        raise SystemExit("Requires a development/test environment and INTERNAL_API_TOKEN")
    with httpx.Client(
        base_url=args.base_url,
        timeout=15,
        headers={"Authorization": "Bearer " + settings.internal_api_token.get_secret_value()},
    ) as client:
        print(json.dumps(prepare_demo(client, args.run_id, args.at), indent=2))


if __name__ == "__main__":
    main()
