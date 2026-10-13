"""Typed qualifications, schedule invariants, and bounded transport input."""

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from minori.domain.catalogs import LanguageTestType, validate_language_level
from minori.schemas.audit import AuditContext
from minori.schemas.candidate import CertificationCreate, ExperienceCreate, LanguageTestCreate
from minori.schemas.match import MatchCreate
from minori.schemas.notification import NotificationAttemptCreate, NotificationCreate
from minori.schemas.placement import PlacementStageCreate
from minori.schemas.vacancy import LanguageRequirementCreate, VacancyDraftCreate
from pydantic import ValidationError

NOW = datetime(2026, 10, 13, 9, tzinfo=UTC)


@pytest.mark.parametrize("test_type,level", [("jlpt", "A2.2"), ("jft_basic", "N4"), ("jlpt", "N6")])
def test_language_scales_cannot_be_mixed(test_type, level):
    with pytest.raises(ValueError):
        validate_language_level(LanguageTestType(test_type), level)
    with pytest.raises(ValidationError):
        LanguageRequirementCreate(test_type=test_type, minimum_level=level)


@pytest.mark.parametrize("level,score", [("A1", 160), ("A2.1", 180), ("A2.2", 218)])
def test_jft_has_its_own_assessed_levels(level, score):
    result = LanguageTestCreate(
        test_type="jft_basic", level=level, score=score, taken_on=date(2026, 9, 15)
    )
    assert result.level == level


@pytest.mark.parametrize(
    "test_type,level,score",
    [
        ("jlpt", "N4", 181),
        ("jft_basic", "A2.2", 251),
        ("jft_basic", "A2.2", 160),
    ],
)
def test_invalid_test_scores_are_rejected(test_type, level, score):
    with pytest.raises(ValidationError):
        LanguageTestCreate(test_type=test_type, level=level, score=score, taken_on="2026-09-15")


def test_certification_and_experience_dates():
    with pytest.raises(ValidationError):
        CertificationCreate(
            code="test",
            name="Example",
            issuer="Example",
            issued_on="2026-01-01",
            expires_on="2025-01-01",
        )
    with pytest.raises(ValidationError):
        ExperienceCreate(
            employer_name="Example",
            sector="food",
            role="Cook",
            started_on="2026-01-01",
            ended_on="2025-01-01",
        )


@pytest.mark.parametrize(
    "change",
    [
        {"sequence_number": 0},
        {"status": "scheduled"},
        {"due_at": NOW},
        {"completed_at": NOW},
        {"status": "completed"},
        {"scheduled_at": NOW.replace(tzinfo=None)},
        {"status": "completed", "scheduled_at": NOW, "completed_at": NOW - timedelta(hours=1)},
        {"diagnosis": "forbidden-synthetic-field"},
    ],
)
def test_invalid_placement_schedule_or_medical_payload(change):
    values = {
        "placement_id": uuid4(),
        "code": "interview",
        "step_type": "interview",
        "sequence_number": 1,
    }
    with pytest.raises(ValidationError):
        PlacementStageCreate(**(values | change))


def test_notification_and_attempt_invariants():
    with pytest.raises(ValidationError):
        NotificationCreate(
            reference="TEST-NOTIFY",
            deduplication_key="test",
            candidate_id=uuid4(),
            template_code="test",
            scheduled_at=NOW,
            placement_stage_id=uuid4(),
        )
    with pytest.raises(ValidationError):
        NotificationAttemptCreate(
            notification_id=uuid4(),
            attempt_number=0,
            status="failed",
            attempted_at=NOW,
            finished_at=NOW,
            error_code="TEST",
        )
    with pytest.raises(ValidationError):
        NotificationAttemptCreate(
            notification_id=uuid4(),
            attempt_number=1,
            status="succeeded",
            attempted_at=NOW,
            finished_at=NOW,
            error_code="TEST",
        )


def test_match_storage_does_not_accept_missing_review_or_invalid_score():
    with pytest.raises(ValidationError):
        MatchCreate(candidate_id=uuid4(), vacancy_id=uuid4(), status="approved")
    with pytest.raises(ValidationError):
        MatchCreate(candidate_id=uuid4(), vacancy_id=uuid4(), score=1.1)


def test_audit_context_rejects_sensitive_and_arbitrary_payloads():
    with pytest.raises(ValidationError):
        AuditContext(diagnosis="forbidden")
    with pytest.raises(ValidationError):
        AuditContext(provider_payload={"secret": "synthetic"})


def test_published_draft_requires_a_vacancy_link(vacancy_payload):
    with pytest.raises(ValidationError):
        VacancyDraftCreate(
            reference="TEST-DRAFT",
            source_channel="test",
            source_reference="source",
            proposed_data=vacancy_payload,
            status="published",
        )
