"""Business-rule edges, hand-calculated scoring, and all synthetic pair expectations."""

import json
from dataclasses import fields, replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import pytest
from minori.domain.catalogs import CandidateStatus, LanguageTestType, VacancyStatus
from minori.domain.eligibility import MONTH_DAYS, relevant_experience, subtract_months
from minori.domain.entities import (
    CandidateRecord,
    CertificationData,
    ExperienceData,
    LanguageRequirementData,
    LanguageTestData,
    VacancyRecord,
)
from minori.domain.matching import EligibilityStatus as Eligibility
from minori.domain.matching_engine import MatchingEngine, RankingEngine, input_fingerprint
from minori.schemas.candidate import CandidateCreate
from minori.schemas.vacancy import VacancyCreate

ROOT = Path(__file__).resolve().parents[2]
AS_OF = datetime(2026, 10, 13, 0, 0, tzinfo=UTC)


def records(filename, key, schema, record_type):
    values = json.loads((ROOT / "data/dummy" / filename).read_text())[key]
    result = {}
    for item in values:
        data = schema(**item).to_domain()
        result[data.reference] = record_type(
            **{field.name: getattr(data, field.name) for field in fields(data)},
            id=uuid5(NAMESPACE_URL, data.reference),
            created_at=AS_OF,
            updated_at=AS_OF,
        )
    return result


CANDIDATES = records("candidates.json", "candidates", CandidateCreate, CandidateRecord)
VACANCIES = records("vacancies.json", "vacancies", VacancyCreate, VacancyRecord)


@pytest.fixture
def pair():
    return CANDIDATES["DEMO-CAND-AGRI"], VACANCIES["DEMO-VAC-AGRI"]


def evaluate(candidate, vacancy, as_of=AS_OF):
    return MatchingEngine().evaluate(candidate, vacancy, as_of)


def codes(result):
    return result.explanation["reason_codes"]


@pytest.mark.parametrize("candidate_reference", list(CANDIDATES))
@pytest.mark.parametrize("vacancy_reference", list(VACANCIES))
def test_all_forty_dummy_pairs(candidate_reference, vacancy_reference):
    candidate, vacancy = CANDIDATES[candidate_reference], VACANCIES[vacancy_reference]
    expected = {
        ("DEMO-CAND-AGRI", "DEMO-VAC-AGRI"): Eligibility.ELIGIBLE,
        ("DEMO-CAND-FOOD", "DEMO-VAC-FOOD"): Eligibility.ELIGIBLE,
        ("DEMO-CAND-CARE", "DEMO-VAC-CARE"): Eligibility.NEEDS_REVIEW,
        ("DEMO-CAND-WELD", "DEMO-VAC-WELD"): Eligibility.NEEDS_REVIEW,
    }.get((candidate_reference, vacancy_reference), Eligibility.NOT_ELIGIBLE)
    first = evaluate(candidate, vacancy)
    assert first.eligibility_status == expected
    assert evaluate(candidate, vacancy) == first
    assert (first.total_score is not None) == (expected == Eligibility.ELIGIBLE)
    if first.total_score is not None:
        assert first.total_score == pytest.approx(0.8375)
    assert len(codes(first)) == len(set(codes(first)))
    assert all(0 <= item["score"] <= 1 for item in first.explanation["score_components"])


@pytest.mark.parametrize("status", [VacancyStatus.PAUSED, VacancyStatus.CLOSED])
def test_unavailable_vacancies_cannot_rank(pair, status):
    candidate, vacancy = pair
    result = evaluate(candidate, replace(vacancy, status=status))
    assert result.eligibility_status == Eligibility.NOT_ELIGIBLE
    assert RankingEngine().rank([(candidate, result)]) == []


def test_deadline_boundary_and_timezone(pair):
    candidate, vacancy = pair
    vacancy = replace(vacancy, application_deadline=AS_OF)
    assert evaluate(candidate, vacancy).eligibility_status == Eligibility.ELIGIBLE
    assert (
        evaluate(candidate, vacancy, AS_OF + timedelta(microseconds=1)).eligibility_status
        == Eligibility.NOT_ELIGIBLE
    )
    equivalent = AS_OF.astimezone(datetime.fromisoformat("2026-10-13T09:00:00+09:00").tzinfo)
    assert evaluate(candidate, vacancy, equivalent) == evaluate(candidate, vacancy)
    with pytest.raises(ValueError, match="timezone"):
        evaluate(candidate, vacancy, AS_OF.replace(tzinfo=None))


def test_missing_language_needs_review_but_failures_take_precedence(pair):
    candidate, vacancy = pair
    result = evaluate(replace(candidate, language_tests=()), vacancy)
    assert result.eligibility_status == Eligibility.NEEDS_REVIEW
    assert "LANGUAGE_EVIDENCE_MISSING" in codes(result)
    blocked = evaluate(replace(candidate, language_tests=(), skills=()), vacancy)
    assert blocked.eligibility_status == Eligibility.NOT_ELIGIBLE
    assert blocked.explanation["verification_needed"]
    assert blocked.explanation["unmet_requirements"]


def test_language_alternatives_best_history_and_no_conversion(pair):
    candidate, vacancy = pair
    tests = (
        LanguageTestData(test_type=LanguageTestType.JLPT, level="N2", taken_on=date(2025, 7, 1)),
        LanguageTestData(test_type=LanguageTestType.JLPT, level="N5", taken_on=date(2026, 7, 1)),
    )
    candidate = replace(candidate, language_tests=tests)
    result = evaluate(candidate, vacancy)
    assert result.eligibility_status == Eligibility.ELIGIBLE
    assert result.explanation["score_components"][0]["score"] == pytest.approx(0.866667)
    only_jft = replace(
        vacancy,
        language_requirements=(
            LanguageRequirementData(test_type=LanguageTestType.JFT_BASIC, minimum_level="A2.2"),
        ),
    )
    assert evaluate(candidate, only_jft).eligibility_status == Eligibility.NEEDS_REVIEW


@pytest.mark.parametrize("level,expected", [("N5", 0.6), ("N3", 0.8), ("N1", 1.0)])
def test_jlpt_normalizes_relative_to_employer_minimum(pair, level, expected):
    candidate, vacancy = pair
    candidate = replace(
        candidate,
        language_tests=(
            LanguageTestData(
                test_type=LanguageTestType.JLPT, level=level, taken_on=date(2026, 7, 1)
            ),
        ),
    )
    vacancy = replace(
        vacancy,
        language_requirements=(
            LanguageRequirementData(test_type=LanguageTestType.JLPT, minimum_level="N5"),
        ),
    )
    assert evaluate(candidate, vacancy).explanation["score_components"][0]["score"] == expected


def test_jft_surplus_and_below_threshold(pair):
    candidate, vacancy = pair
    vacancy = replace(
        vacancy,
        language_requirements=(
            LanguageRequirementData(test_type=LanguageTestType.JFT_BASIC, minimum_level="A2.1"),
        ),
    )
    assert evaluate(candidate, vacancy).explanation["score_components"][0]["score"] == 1
    candidate = replace(
        candidate,
        language_tests=(
            LanguageTestData(
                test_type=LanguageTestType.JFT_BASIC, level="A1", taken_on=date(2026, 9, 1)
            ),
        ),
    )
    result = evaluate(candidate, vacancy)
    assert result.eligibility_status == Eligibility.NOT_ELIGIBLE
    assert "LANGUAGE_BELOW_MINIMUM" in codes(result)


def test_language_age_and_future_test_review(pair):
    candidate, vacancy = pair
    old = replace(candidate.language_tests[0], taken_on=date(2025, 1, 1))
    candidate = replace(candidate, language_tests=(old,))
    assert evaluate(candidate, vacancy).eligibility_status == Eligibility.ELIGIBLE
    aged = evaluate(candidate, replace(vacancy, language_test_max_age_months=12))
    assert "LANGUAGE_EVIDENCE_OUTDATED" in codes(aged)
    future = evaluate(
        replace(candidate, language_tests=(replace(old, taken_on=date(2027, 1, 1)),)), vacancy
    )
    assert "FUTURE_LANGUAGE_TEST" in codes(future)
    assert future.eligibility_status == Eligibility.NEEDS_REVIEW
    assert subtract_months(date(2024, 3, 31), 1) == date(2024, 2, 29)


def test_certification_expiry_renewals_and_future_issuance(pair):
    candidate, vacancy = pair
    cert = candidate.certifications[0]
    assert (
        evaluate(
            replace(candidate, certifications=(replace(cert, expires_on=AS_OF.date()),)), vacancy
        ).eligibility_status
        == Eligibility.ELIGIBLE
    )
    expired = replace(cert, expires_on=date(2026, 10, 12))
    assert "CERTIFICATION_EXPIRED" in codes(
        evaluate(replace(candidate, certifications=(expired,)), vacancy)
    )
    renewal = replace(cert, issued_on=date(2026, 10, 13))
    assert (
        evaluate(replace(candidate, certifications=(expired, renewal)), vacancy).eligibility_status
        == Eligibility.ELIGIBLE
    )
    future = replace(cert, issued_on=date(2026, 11, 1))
    assert (
        evaluate(replace(candidate, certifications=(future,)), vacancy).eligibility_status
        == Eligibility.NEEDS_REVIEW
    )


def test_experience_union_is_inclusive_clipped_and_sector_specific(pair):
    candidate, vacancy = pair
    first = ExperienceData(
        employer_name="Synthetic",
        sector=vacancy.sector,
        role="Operator",
        started_on=date(2026, 1, 1),
        ended_on=date(2026, 6, 30),
    )
    second = replace(first, employer_name="Other", started_on=date(2026, 4, 1), ended_on=None)
    unrelated = replace(first, sector="other", started_on=date(2000, 1, 1))
    candidate = replace(candidate, experiences=(second, first, unrelated))
    days, overlap, future = relevant_experience(candidate, vacancy.sector, AS_OF.date())
    assert days == (AS_OF.date() - date(2026, 1, 1)).days + 1
    assert overlap and not future
    result = evaluate(candidate, replace(vacancy, minimum_experience_months=6))
    assert "EXPERIENCE_OVERLAP_MERGED" in codes(result)
    assert result.explanation["score_components"][1]["score"] == round(days / MONTH_DAYS / 24, 6)
    assert input_fingerprint(candidate, vacancy) == input_fingerprint(
        replace(candidate, experiences=tuple(reversed(candidate.experiences))), vacancy
    )


def test_insufficient_missing_and_future_experience(pair):
    candidate, vacancy = pair
    assert (
        evaluate(replace(candidate, experiences=()), vacancy).eligibility_status
        == Eligibility.NEEDS_REVIEW
    )
    short = replace(candidate.experiences[0], started_on=date(2026, 8, 1))
    assert "EXPERIENCE_INSUFFICIENT" in codes(
        evaluate(replace(candidate, experiences=(short,)), vacancy)
    )
    future = replace(short, started_on=date(2027, 1, 1), ended_on=None)
    result = evaluate(replace(candidate, experiences=(future,)), vacancy)
    assert result.eligibility_status == Eligibility.NEEDS_REVIEW
    assert "FUTURE_EXPERIENCE_IGNORED" in codes(result)


def test_optional_qualifications_and_preference_exact_score(pair):
    candidate, vacancy = pair
    vacancy = replace(
        vacancy,
        preferred_skills=("optional_one", "optional_two"),
        preferred_certifications=("optional_cert",),
    )
    cert = CertificationData(
        code="optional_cert",
        name="Synthetic",
        issuer="Synthetic",
        issued_on=date(2020, 1, 1),
        expires_on=date(2026, 10, 12),
    )
    candidate = replace(
        candidate,
        skills=(*candidate.skills, "optional_one"),
        certifications=(*candidate.certifications, cert),
        preferred_prefectures=(vacancy.prefecture,),
    )
    result = evaluate(candidate, vacancy)
    components = {item["name"]: item for item in result.explanation["score_components"]}
    assert components["additional_qualifications"]["score"] == 0.25
    assert components["preference_readiness"]["score"] == 1
    assert result.total_score == pytest.approx(0.21 + 0.30 + 0.05 + 0.15)


def test_no_language_requirement_is_neutral_and_irrelevant_certificates_do_not_boost(pair):
    candidate, vacancy = pair
    vacancy = replace(vacancy, language_requirements=())
    result = evaluate(candidate, vacancy)
    assert result.explanation["score_components"][0]["score"] == 1
    assert result.total_score == pytest.approx(0.9775)


def test_tie_break_reference_then_uuid_and_permutation_determinism(pair):
    candidate, vacancy = pair
    other = replace(candidate, reference="DEMO-CAND-AA", id=uuid5(NAMESPACE_URL, "other"))
    entries = [(candidate, evaluate(candidate, vacancy)), (other, evaluate(other, vacancy))]
    assert RankingEngine().rank(entries) == RankingEngine().rank(list(reversed(entries)))
    assert RankingEngine().rank(entries)[0].candidate_id == other.id
    same_reference = replace(candidate, id=uuid5(NAMESPACE_URL, "same-ref"))
    tied = [
        (candidate, evaluate(candidate, vacancy)),
        (same_reference, evaluate(same_reference, vacancy)),
    ]
    assert RankingEngine().rank(tied)[0].candidate_id == min(
        candidate.id, same_reference.id, key=str
    )


def test_preparing_candidate_is_review_and_inactive_cannot_rank(pair):
    candidate, vacancy = pair
    assert (
        evaluate(replace(candidate, status=CandidateStatus.PREPARING), vacancy).eligibility_status
        == Eligibility.NEEDS_REVIEW
    )
    result = evaluate(replace(candidate, status=CandidateStatus.INACTIVE), vacancy)
    assert result.total_score is None
    assert "CANDIDATE_INACTIVE" in codes(result)
    assert RankingEngine().rank([(candidate, result)]) == []
