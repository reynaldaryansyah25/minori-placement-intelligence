"""Exercise real migrated SQLite, detached records, ownership, and caller-owned transactions."""

from dataclasses import asdict, replace
from datetime import UTC, datetime
from typing import Annotated
from uuid import uuid4

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from minori.api.dependencies import get_repositories
from minori.db.models import Candidate
from minori.domain.catalogs import CandidateStatus, Program, VacancyStatus
from minori.domain.entities import MatchData, NotificationData, PlacementData, PlacementStageData
from minori.domain.errors import RecordNotFoundError
from minori.main import create_app
from minori.repositories.provider import Repositories, provide_repositories
from minori.schemas.candidate import CandidateCreate, CandidateRead
from minori.schemas.match import MatchCreate
from minori.schemas.notification import NotificationCreate
from minori.schemas.placement import PlacementCreate, PlacementStageCreate
from minori.schemas.vacancy import VacancyCreate, VacancyDraftCreate
from sqlalchemy import select

NOW = datetime(2026, 10, 13, 9, tzinfo=UTC)


def test_candidate_and_vacancy_aggregate_reads_updates_and_archiving(
    migrated_database, candidate_payload, vacancy_payload
):
    with migrated_database.session_factory.begin() as session:
        repos = provide_repositories(session)
        candidate = repos.candidate.create(CandidateCreate(**candidate_payload).to_domain())
        vacancy = repos.vacancy.create(VacancyCreate(**vacancy_payload).to_domain())
        assert candidate.language_tests and candidate.certifications and candidate.experiences
        assert len(repos.candidate.list(preferred_program=Program.SSW)) == 1
        assert not repos.candidate.list(status=CandidateStatus.INACTIVE)
        assert repos.candidate.get_by_reference(candidate.reference) == candidate
        assert repos.candidate.get(uuid4()) is None
        values = asdict(candidate)
        for field in ("id", "created_at", "updated_at"):
            values.pop(field)
        values["full_name"] = "Nama Fiktif Diubah"
        updated = repos.candidate.replace(candidate.id, CandidateCreate(**values).to_domain())
        assert updated.full_name == "Nama Fiktif Diubah"
        assert updated.updated_at >= candidate.updated_at
        assert len(updated.language_tests) == len(candidate.language_tests)
        repos.candidate.archive(candidate.id)
        repos.vacancy.archive(vacancy.id)
        assert repos.vacancy.list(status=VacancyStatus.CLOSED)[0].id == vacancy.id
        assert repos.candidate.list(status=CandidateStatus.INACTIVE)[0].id == candidate.id
    session.close()
    assert CandidateRead.model_validate(updated).language_tests[0].test_type == "jft_basic"


def test_repositories_never_commit_and_can_be_rolled_back(migrated_database, candidate_payload):
    with migrated_database.session_factory() as session:
        repo = provide_repositories(session).candidate
        item = repo.create(CandidateCreate(**candidate_payload).to_domain())
        session.rollback()
        assert repo.get(item.id) is None


def test_reference_and_pagination_are_protected(migrated_database, candidate_payload):
    with migrated_database.session_factory.begin() as session:
        repo = provide_repositories(session).candidate
        data = CandidateCreate(**candidate_payload).to_domain()
        row = repo.create(data)
        with pytest.raises(ValueError, match="reference"):
            repo.replace(row.id, replace(data, reference="TEST-OTHER"))
        with pytest.raises(ValueError, match="limit"):
            repo.list(limit=0)
        with pytest.raises(RecordNotFoundError):
            repo.archive(uuid4())
        assert repo.list(limit=1, offset=1) == []


def test_all_repository_records_can_be_read_detached(seeded_database):
    with seeded_database.session_factory() as session:
        repos = provide_repositories(session)
        candidate = repos.candidate.get_by_reference("DEMO-CAND-AGRI")
        vacancy = repos.vacancy.get_by_reference("DEMO-VAC-AGRI")
        placement = repos.placement.get_by_reference("DEMO-PLC-AGRI")
        draft = repos.vacancy_draft.list()[0]
        association = repos.match.get_by_pair(candidate.id, vacancy.id)
        steps = repos.placement_stage.list_for_placement(placement.id)
        intent = repos.notification.get_by_deduplication_key("fixture.agri.interview")
        attempts = repos.notification_attempt.list_for_notification(intent.id)
        audit = repos.audit_log.list(entity_id=candidate.id)[0]
        assert repos.match.list_for_candidate(candidate.id)[0].id == association.id
        assert repos.placement.list_for_candidate(candidate.id)[0].id == placement.id
        assert repos.notification.list_for_candidate(candidate.id)[0].id == intent.id
        for port, row in [
            (repos.vacancy, vacancy),
            (repos.vacancy_draft, draft),
            (repos.match, association),
            (repos.placement, placement),
            (repos.placement_stage, steps[0]),
            (repos.notification, intent),
            (repos.notification_attempt, attempts[0]),
            (repos.audit_log, audit),
        ]:
            assert port.get(row.id).id == row.id
            assert port.get(uuid4()) is None
        assert [step.sequence_number for step in steps] == [1, 2]
        assert len(attempts) == 2
        assert not hasattr(repos.audit_log, "replace")
        assert not hasattr(repos.notification_attempt, "replace")
    assert placement.candidate_id == candidate.id
    assert audit.context["synthetic"] is True


def test_request_dependency_shares_session_without_new_business_routes(
    migrated_database, settings, candidate_payload
):
    with migrated_database.session_factory.begin() as session:
        provide_repositories(session).candidate.create(
            CandidateCreate(**candidate_payload).to_domain()
        )
    application = create_app(settings)

    @application.get("/repository-probe")
    def probe(repos: Annotated[Repositories, Depends(get_repositories)]):
        return {"count": len(repos.candidate.list())}

    with TestClient(application) as client:
        assert client.get("/repository-probe").json() == {"count": 1}


def test_replacement_for_placement_and_notification_keeps_ownership(seeded_database):
    with seeded_database.session_factory.begin() as session:
        repos = provide_repositories(session)
        placement = repos.placement.get_by_reference("DEMO-PLC-FOOD")
        values = asdict(placement)
        for key in ("id", "created_at", "updated_at"):
            values.pop(key)
        data = PlacementCreate(**values).to_domain(PlacementData)
        assert (
            repos.placement.replace(placement.id, replace(data, status="preparing")).status
            == "preparing"
        )
        with pytest.raises(ValueError, match="candidate_id"):
            repos.placement.replace(placement.id, replace(data, candidate_id=uuid4()))
        step = repos.placement_stage.get_by_code(placement.id, "employer_interview")
        values = asdict(step)
        for key in ("id", "created_at", "updated_at"):
            values.pop(key)
        step_data = PlacementStageCreate(**values).to_domain(PlacementStageData)
        assert (
            repos.placement_stage.replace(
                step.id, replace(step_data, location="Ruang Contoh Baru")
            ).location
            == "Ruang Contoh Baru"
        )
        intent = repos.notification.get_by_deduplication_key("fixture.food.interview")
        values = asdict(intent)
        for key in ("id", "created_at", "updated_at"):
            values.pop(key)
        notification_data = NotificationCreate(**values).to_domain(NotificationData)
        assert (
            repos.notification.replace(
                intent.id, replace(notification_data, status="cancelled")
            ).status
            == "cancelled"
        )
        association = repos.match.get_by_pair(placement.candidate_id, placement.vacancy_id)
        values = asdict(association)
        for key in ("id", "created_at", "updated_at"):
            values.pop(key)
        match_data = MatchCreate(**values).to_domain(MatchData)
        assert repos.match.replace(association.id, replace(match_data, score=0.5)).score == 0.5


def test_nested_snapshot_mutations_do_not_write_to_database(seeded_database):
    with seeded_database.session_factory() as session:
        repos = provide_repositories(session)
        audit = repos.audit_log.list()[0]
        audit.context["synthetic"] = False
        session.expire_all()
        assert repos.audit_log.get(audit.id).context["synthetic"] is True
        row = session.scalar(select(Candidate).where(Candidate.reference == "DEMO-CAND-AGRI"))
        assert row.language_tests[0].taken_on is not None


def test_vacancy_requirement_replacement_and_draft_publication(seeded_database):
    with seeded_database.session_factory.begin() as session:
        repos = provide_repositories(session)
        vacancy = repos.vacancy.get_by_reference("DEMO-VAC-FOOD")
        values = asdict(vacancy)
        for field in ("id", "created_at", "updated_at"):
            values.pop(field)
        data = VacancyCreate(**values).to_domain()
        updated = repos.vacancy.replace(vacancy.id, replace(data, quota=7))
        assert updated.quota == 7
        assert updated.language_requirements == vacancy.language_requirements
        draft = repos.vacancy_draft.get_by_reference("DEMO-DRAFT-FOOD")
        values = asdict(draft)
        for field in ("id", "created_at", "updated_at"):
            values.pop(field)
        draft_data = VacancyDraftCreate(**values).to_domain()
        published = repos.vacancy_draft.replace(
            draft.id, replace(draft_data, status="published", published_vacancy_id=vacancy.id)
        )
        assert published.published_vacancy_id == vacancy.id
        assert repos.vacancy_draft.list(status="published")
        assert repos.vacancy.list(program=Program.SSW)
        with pytest.raises(ValueError, match="source_reference"):
            repos.vacancy_draft.replace(
                draft.id, replace(draft_data, source_reference="changed.source")
            )
