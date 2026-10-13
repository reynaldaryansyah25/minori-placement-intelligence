"""Real SQLite matching persistence, API responses, rollback, and legacy-data regressions."""

from collections import Counter
from dataclasses import asdict, fields, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from minori.api.dependencies import get_matching_service
from minori.db.inspection import inspect_database
from minori.db.models import Candidate, Match, MatchEvaluation, Placement
from minori.domain.catalogs import CandidateStatus, MatchStatus, VacancyStatus
from minori.domain.entities import CandidateData, MatchData, VacancyData
from minori.domain.matching_engine import MatchingEngine
from minori.main import create_app
from minori.repositories.provider import provide_repositories
from minori.schemas.matching import EvaluationCreate
from minori.services.matching import MatchingService
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, OperationalError

ROOT = Path(__file__).resolve().parents[2]
AS_OF = datetime(2026, 10, 13, 0, 0, tzinfo=UTC)


def data(record, data_type):
    return data_type(**{item.name: getattr(record, item.name) for item in fields(data_type)})


def service(session, now=AS_OF):
    repos = provide_repositories(session)
    return MatchingService(
        repos.candidate, repos.vacancy, repos.match, repos.evaluation, session.begin, lambda: now
    )


def pair(database):
    with database.session_factory() as session:
        repos = provide_repositories(session)
        return (
            repos.candidate.get_by_reference("DEMO-CAND-AGRI"),
            repos.vacancy.get_by_reference("DEMO-VAC-AGRI"),
        )


def test_all_pairs_persist_idempotently_without_changing_staff_decisions(seeded_database):
    with seeded_database.session_factory() as session:
        old = [
            asdict(item)
            for item in session.scalars(select(Match))
            for item in [provide_repositories(session).match.get(item.id)]
        ]
    with seeded_database.session_factory() as session:
        results = service(session).evaluate(as_of=AS_OF)
        repeated = service(session).evaluate(as_of=AS_OF)
    assert len(results) == 40
    assert Counter(item["eligibility_status"] for item in results) == {
        "ELIGIBLE": 2,
        "NOT_ELIGIBLE": 36,
        "NEEDS_REVIEW": 2,
    }
    assert [item["evaluation_id"] for item in results] == [
        item["evaluation_id"] for item in repeated
    ]
    with seeded_database.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(MatchEvaluation)) == 40
        new = [
            asdict(provide_repositories(session).match.get(item.id))
            for item in session.scalars(select(Match))
        ]
        assert old == new
    assert inspect_database(seeded_database)["integrity"] == "ok"


def test_historical_evaluations_and_time_changes_are_stale(seeded_database):
    candidate, vacancy = pair(seeded_database)
    with seeded_database.session_factory() as session:
        stored = service(session).evaluate(candidate_id=candidate.id, vacancy_id=vacancy.id)[0]
    after_deadline = vacancy.application_deadline + timedelta(seconds=1)
    with seeded_database.session_factory() as session:
        matching = service(session, after_deadline)
        assert matching.result(stored["evaluation_id"])["is_stale"]
        assert not matching.result(stored["evaluation_id"])["active_recommendation"]
        assert matching.ranking(vacancy.id) == []


def test_changed_candidate_recalculates_impacted_pairs_and_preserves_history(seeded_database):
    candidate, vacancy = pair(seeded_database)
    with seeded_database.session_factory() as session:
        matching = service(session)
        stored = matching.evaluate(candidate_id=candidate.id)[0]
        updated = matching.replace_candidate(
            candidate.id, replace(data(candidate, CandidateData), status=CandidateStatus.INACTIVE)
        )
    assert len(updated) == 5
    assert all(item["eligibility_status"] == "NOT_ELIGIBLE" for item in updated)
    with seeded_database.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(MatchEvaluation)) == 10
        matching = service(session)
        assert matching.result(stored["evaluation_id"])["is_stale"]
        assert matching.ranking(vacancy.id) == []


def test_changed_vacancy_recalculates_eight_pairs(seeded_database):
    _, vacancy = pair(seeded_database)
    with seeded_database.session_factory() as session:
        results = service(session).replace_vacancy(
            vacancy.id, replace(data(vacancy, VacancyData), status=VacancyStatus.CLOSED)
        )
    assert len(results) == 8
    assert all(not item["active_recommendation"] for item in results)


def test_external_repository_edit_cannot_leave_active_stale_recommendation(seeded_database):
    candidate, vacancy = pair(seeded_database)
    with seeded_database.session_factory() as session:
        record = service(session).evaluate(candidate_id=candidate.id, vacancy_id=vacancy.id)[0]
    with seeded_database.session_factory.begin() as session:
        provide_repositories(session).candidate.archive(candidate.id)
    with seeded_database.session_factory() as session:
        matching = service(session)
        assert matching.result(record["evaluation_id"])["is_stale"]
        assert matching.ranking(vacancy.id) == []


def test_rejected_manual_association_excluded_without_overwrite(seeded_database):
    candidate, vacancy = pair(seeded_database)
    with seeded_database.session_factory.begin() as session:
        repos = provide_repositories(session)
        manual = repos.match.get_by_pair(candidate.id, vacancy.id)
        repos.match.replace(
            manual.id,
            replace(data(manual, MatchData), status=MatchStatus.REJECTED, reviewed_at=AS_OF),
        )
    with seeded_database.session_factory() as session:
        results = service(session).evaluate(candidate_id=candidate.id, vacancy_id=vacancy.id)
        assert results[0]["staff_status"] == MatchStatus.REJECTED
        assert results[0]["eligibility_status"] == "ELIGIBLE"
        assert not results[0]["active_recommendation"]
        assert service(session).ranking(vacancy.id) == []


def test_evaluation_and_profile_update_rollback_together(seeded_database, monkeypatch):
    candidate, _ = pair(seeded_database)
    with seeded_database.session_factory() as session:
        matching = service(session)
        original_append = matching.evaluations.append
        calls = 0

        def failing_append(evaluation):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("Synthetic persistence failure")
            return original_append(evaluation)

        monkeypatch.setattr(matching.evaluations, "append", failing_append)
        with pytest.raises(RuntimeError, match="Synthetic"):
            matching.replace_candidate(
                candidate.id,
                replace(data(candidate, CandidateData), status=CandidateStatus.INACTIVE),
            )
    with seeded_database.session_factory() as session:
        assert session.get(Candidate, candidate.id).status == CandidateStatus.READY
        assert session.scalar(select(func.count()).select_from(MatchEvaluation)) == 0


def test_evaluation_constraints_and_foreign_keys(seeded_database):
    candidate, vacancy = pair(seeded_database)
    evaluation = MatchingEngine().evaluate(candidate, vacancy, AS_OF)
    with seeded_database.session_factory.begin() as session:
        provide_repositories(session).evaluation.append(evaluation)
    with seeded_database.session_factory.begin() as session:
        with pytest.raises(IntegrityError), session.begin_nested():
            provide_repositories(session).evaluation.append(evaluation)
        with pytest.raises(IntegrityError), session.begin_nested():
            provide_repositories(session).evaluation.append(
                replace(evaluation, candidate_id=uuid4())
            )
        for assignment in (
            "total_score = 2",
            "total_score = NULL",
            "eligibility_status = 'UNKNOWN'",
        ):
            with pytest.raises(IntegrityError), session.begin_nested():
                session.execute(text(f"UPDATE match_evaluations SET {assignment}"))


def test_evaluation_validation_rejects_bad_contributions(seeded_database):
    candidate, vacancy = pair(seeded_database)
    payload = asdict(MatchingEngine().evaluate(candidate, vacancy, AS_OF))
    payload["explanation"]["score_components"][0]["contribution"] = 0.99
    with pytest.raises(ValueError, match="contribution"):
        EvaluationCreate(**payload)


@pytest.mark.parametrize("change", ["eligibility", "reason_codes", "component_names", "weights"])
def test_evaluation_contract_rejects_inconsistent_explanations(seeded_database, change):
    candidate, vacancy = pair(seeded_database)
    payload = asdict(MatchingEngine().evaluate(candidate, vacancy, AS_OF))
    if change == "eligibility":
        payload["eligibility_status"] = "NEEDS_REVIEW"
    elif change == "reason_codes":
        payload["explanation"]["reason_codes"] = []
    elif change == "component_names":
        payload["explanation"]["score_components"][0]["name"] = "unpublished"
    else:
        payload["explanation"]["score_components"][0]["weight"] = 0.1
    with pytest.raises(ValueError):
        EvaluationCreate(**payload)


def test_evaluation_latest_uses_evaluation_time_and_lists_filtered_history(seeded_database):
    candidate, vacancy = pair(seeded_database)
    newer = MatchingEngine().evaluate(candidate, vacancy, AS_OF)
    older = replace(newer, evaluated_at=AS_OF - timedelta(days=1))
    with seeded_database.session_factory.begin() as session:
        repository = provide_repositories(session).evaluation
        expected = repository.append(newer)
        repository.append(older)
        assert repository.latest(candidate.id, vacancy.id).id == expected.id
        assert len(repository.list(vacancy_id=vacancy.id)) == 2
        assert repository.latest(uuid4(), vacancy.id) is None


def test_api_uses_production_dependency_injection_with_real_transactions(seeded_database, settings):
    with TestClient(create_app(settings)) as client:
        response = client.post("/matching/evaluations", json={"as_of": AS_OF.isoformat()})
        assert response.status_code == 200, response.text
        assert response.json()["evaluated_count"] == 40
        assert len(client.get("/matching/results").json()) == 40


def test_upgrade_preserves_populated_legacy_graph_and_manual_scores(seeded_database):
    configuration = Config(str(ROOT / "alembic.ini"))
    before = inspect_database(seeded_database)
    with seeded_database.session_factory.begin() as session:
        row = session.scalar(select(Match).limit(1))
        row.score = 0.1234
        identifier = row.id
        placement_ids = set(session.scalars(select(Placement.id)))
    command.downgrade(configuration, "placement_database")
    command.upgrade(configuration, "head")
    assert inspect_database(seeded_database)["counts"] == before["counts"]
    with seeded_database.session_factory() as session:
        assert session.get(Match, identifier).score == 0.1234
        assert set(session.scalars(select(Placement.id))) == placement_ids
    command.check(configuration)


def test_matching_downgrade_refuses_stored_evaluations(seeded_database):
    with seeded_database.session_factory() as session:
        service(session).evaluate()
    before = inspect_database(seeded_database)
    with pytest.raises(RuntimeError, match="Refusing downgrade"):
        command.downgrade(Config(str(ROOT / "alembic.ini")), "placement_database")
    assert inspect_database(seeded_database) == before


@pytest.fixture
def client(seeded_database, settings):
    application = create_app(settings)

    def dependency():
        with seeded_database.session_factory() as session:
            yield service(session)

    application.dependency_overrides[get_matching_service] = dependency
    with TestClient(application) as test_client:
        yield test_client


def test_matching_api_batch_history_explanation_ranking_and_updates(client, seeded_database):
    response = client.post("/matching/evaluations", json={"as_of": AS_OF.isoformat()})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["evaluated_count"] == 40
    candidate, vacancy = pair(seeded_database)
    detail = client.get(f"/matching/candidates/{candidate.id}/vacancies/{vacancy.id}/explanation")
    assert detail.status_code == 200
    assert detail.json()["total_score"] == 0.8375
    assert detail.json()["explanation"]["score_components"][0]["weight"] == 0.35
    history = client.get(
        "/matching/results", params={"candidate_id": str(candidate.id), "limit": 2}
    )
    assert history.status_code == 200 and len(history.json()) == 2
    record = client.get(f"/matching/results/{payload['results'][0]['evaluation_id']}")
    assert record.status_code == 200
    ranking = client.get(f"/matching/vacancies/{vacancy.id}/ranking")
    assert ranking.status_code == 200
    assert ranking.json()[0]["candidate_id"] == str(candidate.id)
    assert ranking.json()[0]["rank"] == 1
    values = asdict(candidate)
    for key in ("id", "created_at", "updated_at"):
        values.pop(key)
    from minori.schemas.candidate import CandidateCreate

    candidate_payload = CandidateCreate(**values).model_dump(mode="json")
    candidate_payload["status"] = "inactive"
    updated = client.put(f"/matching/candidates/{candidate.id}", json=candidate_payload)
    assert updated.status_code == 200 and updated.json()["evaluated_count"] == 5
    assert client.get(f"/matching/vacancies/{vacancy.id}/ranking").json() == []
    from minori.schemas.vacancy import VacancyCreate

    values = asdict(vacancy)
    for key in ("id", "created_at", "updated_at"):
        values.pop(key)
    vacancy_payload = VacancyCreate(**values).model_dump(mode="json")
    vacancy_payload["status"] = "paused"
    updated = client.put(f"/matching/vacancies/{vacancy.id}", json=vacancy_payload)
    assert updated.status_code == 200 and updated.json()["evaluated_count"] == 8


@pytest.mark.parametrize(
    "payload",
    [
        {"candidate_id": "invalid"},
        {"as_of": "2026-10-13T00:00:00"},
        {"as_of": "2099-01-01T00:00:00Z"},
        {"unknown": True},
    ],
)
def test_matching_api_rejects_invalid_inputs(client, payload):
    assert client.post("/matching/evaluations", json=payload).status_code == 422


def test_matching_api_unknown_ids_and_pagination(client):
    unknown = uuid4()
    assert (
        client.post("/matching/evaluations", json={"candidate_id": str(unknown)}).status_code == 404
    )
    assert (
        client.post("/matching/evaluations", json={"vacancy_id": str(unknown)}).status_code == 404
    )
    assert client.get(f"/matching/results/{unknown}").status_code == 404
    assert client.get(f"/matching/vacancies/{unknown}/ranking").status_code == 404
    assert client.get("/matching/results", params={"limit": 101}).status_code == 422
    assert client.get("/matching/results", params={"offset": -1}).status_code == 422


def test_api_database_errors_are_sanitized(client, monkeypatch):
    for error, status in (
        (IntegrityError("private SQL", {}, Exception("private")), 409),
        (OperationalError("private SQL", {}, Exception("private")), 503),
    ):

        def fail(self, failure=error, **kwargs):
            raise failure

        monkeypatch.setattr(MatchingService, "evaluate", fail)
        response = client.post("/matching/evaluations", json={})
        assert response.status_code == status
        assert "private" not in response.text
