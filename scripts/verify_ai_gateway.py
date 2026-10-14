"""Opt-in real gateway smoke test using a synthetic Japanese vacancy only."""

import argparse
import json
import sys

import httpx
from minori.core.config import get_settings
from minori.integrations.nine_router.client import NineRouterClient
from minori.integrations.nine_router.structured import ValidatedAiGateway
from minori.services.ai import AiService

SYNTHETIC_SOURCE = "【架空のデモ求人】農業スタッフ募集。会社名：ミノリデモ農園株式会社（架空）。勤務地：北海道。特定技能。日本語能力試験N4以上。募集人数3名。農業経験12か月以上。野菜栽培の技能が必要。チームワーク歓迎。"


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--discover", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    headers = (
        {"Authorization": "Bearer " + settings.nine_router_api_key.get_secret_value()}
        if settings.nine_router_api_key
        else {}
    )
    response = httpx.get(
        str(settings.nine_router_base_url).rstrip("/") + "/models",
        headers=headers,
        timeout=settings.llm_timeout_seconds,
    )
    if not response.is_success:
        raise SystemExit(f"Discovery failed: HTTP {response.status_code}")
    models = [item["id"] for item in response.json()["data"]]
    if args.discover:
        print(json.dumps({"available_models": models}))
        return
    if settings.nine_router_model not in models:
        raise SystemExit("Configured model was not present in router discovery")
    client = NineRouterClient(settings)
    try:
        result = AiService(None, ValidatedAiGateway(client)).analyze(SYNTHETIC_SOURCE)
    finally:
        client.close()
    print(
        json.dumps(
            {"passed": True, "model": settings.nine_router_model, "synthetic_result": result},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
