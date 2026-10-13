"""Exercise all synthetic pairs locally or through the running FastAPI service."""

import argparse
import json
from collections import Counter
from datetime import UTC, datetime

import httpx
from minori.core.config import get_settings
from minori.db.inspection import inspect_database
from minori.db.session import Database
from minori.repositories.provider import provide_repositories
from minori.schemas.matching import MatchingResultRead
from minori.services.matching import MatchingService

AS_OF = datetime(2026, 10, 13, 0, 0, tzinfo=UTC)


def check(first, second):
    assert len(first) == len(second) == 40, "Expected the unchanged 8-candidate/5-vacancy fixture"

    def key(item):
        return item["candidate_reference"], item["vacancy_reference"]

    first = sorted(first, key=key)
    second = sorted(second, key=key)
    assert {key(item) for item in first} == {key(item) for item in second}
    assert all(item["candidate_reference"].startswith("DEMO-") for item in first)
    assert all(item["vacancy_reference"].startswith("DEMO-") for item in first)
    expected = {"ELIGIBLE": 2, "NOT_ELIGIBLE": 36, "NEEDS_REVIEW": 2}
    assert Counter(item["eligibility_status"] for item in first) == expected
    for left, right in zip(first, second, strict=True):
        MatchingResultRead.model_validate(left)
        assert left["evaluation_id"] == right["evaluation_id"]
        assert left["explanation"] == right["explanation"]
        assert left["total_score"] == right["total_score"]
        assert left["staff_status"] == right["staff_status"]
    return {
        "passed": True,
        "as_of": AS_OF.isoformat(),
        "pairs": 40,
        "eligibility_counts": expected,
        "repeat_preserved_ids": True,
        "matrix": [
            {
                "candidate": item["candidate_reference"],
                "vacancy": item["vacancy_reference"],
                "eligibility": item["eligibility_status"],
                "score": item["total_score"],
                "staff_status": item["staff_status"],
                "reason_codes": item["explanation"]["reason_codes"],
            }
            for item in first
        ],
    }


def verify_http(base_url):
    with httpx.Client(base_url=base_url, timeout=30) as client:
        outcomes = []
        for _ in range(2):
            response = client.post("/matching/evaluations", json={"as_of": AS_OF.isoformat()})
            response.raise_for_status()
            outcomes.append(response.json()["results"])
        report = check(*outcomes)
        rankings = {}
        for item in outcomes[0]:
            detail = client.get(f"/matching/results/{item['evaluation_id']}")
            detail.raise_for_status()
            assert detail.json()["explanation"] == item["explanation"]
            explanation = client.get(
                f"/matching/candidates/{item['candidate_id']}/vacancies/{item['vacancy_id']}/explanation"
            )
            explanation.raise_for_status()
            MatchingResultRead.model_validate(explanation.json())
            if item["vacancy_reference"] not in rankings:
                response = client.get(f"/matching/vacancies/{item['vacancy_id']}/ranking")
                response.raise_for_status()
                rankings[item["vacancy_reference"]] = [
                    {
                        "rank": row["rank"],
                        "candidate": row["candidate_reference"],
                        "score": row["total_score"],
                    }
                    for row in response.json()
                ]
                assert all(
                    row["active_recommendation"] and not row["is_stale"] for row in response.json()
                )
        listing = client.get("/matching/results", params={"limit": 100})
        listing.raise_for_status()
        assert len(listing.json()) >= 40
        report.update({"api_verified": True, "ranking": rankings})
        return report


def verify_local():
    database = Database(get_settings())
    try:
        inspect_database(database)
        with database.session_factory() as session:
            repos = provide_repositories(session)
            matching = MatchingService(
                repos.candidate, repos.vacancy, repos.match, repos.evaluation, session.begin
            )
            first = matching.evaluate(as_of=AS_OF)
            second = matching.evaluate(as_of=AS_OF)
        report = check(first, second)
        report["database"] = inspect_database(database)
        return report
    finally:
        database.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url", help="Use the running matching API instead of local repositories"
    )
    arguments = parser.parse_args()
    if get_settings().app_env == "production":
        raise SystemExit("Synthetic matching verification is restricted to development and test")
    report = verify_http(arguments.base_url) if arguments.base_url else verify_local()
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
