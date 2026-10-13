"""Generate due reminders or simulate delivery through authenticated HTTP, without n8n."""

import argparse
import json

import httpx
from minori.core.config import get_settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--simulate", action="store_true")
    parser.add_argument("--limit", type=int, default=20)
    arguments = parser.parse_args()
    settings = get_settings()
    if settings.internal_api_token is None:
        raise SystemExit(
            "Configure INTERNAL_API_TOKEN in the environment before running the worker"
        )
    if not 1 <= arguments.limit <= 100:
        raise SystemExit("Limit must be 1..100")
    with httpx.Client(
        base_url=arguments.base_url,
        timeout=30,
        headers={"Authorization": "Bearer " + settings.internal_api_token.get_secret_value()},
    ) as client:

        def request(method, path, payload=None):
            response = client.request(method, path, json=payload)
            if response.status_code != 200:
                raise SystemExit(f"Worker request failed with HTTP {response.status_code}")
            return response.json()

        if arguments.generate:
            request("POST", "/internal/reminders/generate")
        request("POST", "/internal/reminders/recover")
        due = request("GET", "/internal/reminders/due")
        processed = []
        if arguments.simulate:
            for row in due[: arguments.limit]:
                result = request(
                    "POST", "/internal/reminders/simulate", {"notification_id": row["id"]}
                )
                if result:
                    attempts = request("GET", f"/reminders/{row['id']}/attempts")
                    processed.append(
                        {
                            "notification_id": row["id"],
                            "status": result["status"],
                            "attempt_count": len(attempts),
                        }
                    )
        print(json.dumps({"due_count": len(due), "processed": processed}, indent=2))


if __name__ == "__main__":
    main()
