"""Pagination completeness and bounded optional-input validation."""

from dataclasses import dataclass

import pytest
from minori.schemas.candidate import CandidateCreate
from minori.schemas.vacancy import VacancyCreate
from minori.services.matching import MatchingService


def test_matching_reads_every_page_and_orders_by_stable_reference():
    @dataclass
    class Row:
        reference: str
        id: int

    rows = [Row(reference=f"DEMO-CAND-{number:03}", id=number) for number in range(205)]

    class Repository:
        def list(self, *, limit, offset):
            return list(reversed(rows))[offset : offset + limit]

    assert MatchingService._all(Repository()) == rows


@pytest.mark.parametrize("preferences", [[""], ["Osaka", "osaka"], ["X" * 81]])
def test_prefecture_preferences_reject_invalid_values(candidate_payload, preferences):
    with pytest.raises(ValueError):
        CandidateCreate(**{**candidate_payload, "preferred_prefectures": preferences})


@pytest.mark.parametrize("value", [0, -1, 1201, True])
def test_language_age_policy_rejects_invalid_limits(vacancy_payload, value):
    with pytest.raises(ValueError):
        VacancyCreate(**{**vacancy_payload, "language_test_max_age_months": value})
