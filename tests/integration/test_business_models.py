"""Database-level constraints, timezone storage, and relationship ownership."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from minori.db.models import (
    MODEL_TYPES,
    Candidate,
    CandidateCertification,
    CandidateExperience,
    CandidateLanguageTest,
    Match,
    Notification,
    NotificationAttempt,
    Placement,
    PlacementStage,
    Vacancy,
    VacancyDraft,
)
from sqlalchemy import inspect, select, update
from sqlalchemy.exc import IntegrityError, StatementError


@pytest.mark.parametrize(
    "model,values",
    [
        (Vacancy, {"quota": 0}),
        (Vacancy, {"minimum_experience_months": -1}),
        (Candidate, {"full_name": " "}),
        (CandidateLanguageTest, {"test_type": "jft_basic", "level": "N4"}),
        (CandidateLanguageTest, {"score": 251}),
        (CandidateCertification, {"expires_on": datetime(2020, 1, 1).date()}),
        (CandidateExperience, {"ended_on": datetime(2020, 1, 1).date()}),
        (Match, {"score": 1.1}),
        (Match, {"reviewed_at": None}),
        (PlacementStage, {"sequence_number": 0}),
        (PlacementStage, {"due_at": datetime(2020, 1, 1, tzinfo=UTC)}),
        (NotificationAttempt, {"attempt_number": 0}),
        (NotificationAttempt, {"finished_at": datetime(2020, 1, 1, tzinfo=UTC)}),
        (VacancyDraft, {"status": "published", "published_vacancy_id": None}),
    ],
)
def test_invalid_rows_are_rejected_by_sqlite(seeded_database, model, values):
    with seeded_database.session_factory.begin() as session:
        row = session.scalar(select(model))
        with pytest.raises(IntegrityError):
            with session.begin_nested():
                session.execute(update(model).where(model.id == row.id).values(**values))


@pytest.mark.parametrize(
    "model",
    [
        Candidate,
        Vacancy,
        VacancyDraft,
        Match,
        Placement,
        PlacementStage,
        Notification,
        NotificationAttempt,
        CandidateLanguageTest,
    ],
)
def test_unique_natural_keys_cannot_be_duplicated(seeded_database, model):
    with seeded_database.session_factory.begin() as session:
        row = session.scalar(select(model))
        values = {
            column.name: getattr(row, column.name)
            for column in model.__table__.columns
            if column.name not in {"id", "created_at", "updated_at"}
        }
        with pytest.raises(IntegrityError):
            with session.begin_nested():
                session.add(model(**values))
                session.flush()


def test_composite_foreign_keys_reject_cross_candidate_and_cross_placement_links(seeded_database):
    with seeded_database.session_factory.begin() as session:
        placements = session.scalars(select(Placement)).all()
        first, second = placements[:2]
        intent = session.scalar(select(Notification))
        wrong_step = session.scalar(
            select(PlacementStage).where(PlacementStage.placement_id != intent.placement_id)
        )
        invalid_updates = [
            (Placement, first.id, {"match_id": second.match_id}),
            (
                Notification,
                intent.id,
                {
                    "candidate_id": next(
                        row.candidate_id
                        for row in placements
                        if row.candidate_id != intent.candidate_id
                    )
                },
            ),
            (Notification, intent.id, {"placement_stage_id": wrong_step.id}),
        ]
        for model, identifier, values in invalid_updates:
            with pytest.raises(IntegrityError):
                with session.begin_nested():
                    session.execute(update(model).where(model.id == identifier).values(**values))


def test_parent_deletion_cannot_erase_placement_history(seeded_database):
    with seeded_database.session_factory.begin() as session:
        placement = session.scalar(select(Placement))
        with pytest.raises(IntegrityError):
            with session.begin_nested():
                session.delete(placement.candidate)
                session.flush()


def test_all_tables_have_ids_timestamps_and_expected_relationships(seeded_database):
    inspector = inspect(seeded_database.engine)
    for model in MODEL_TYPES:
        assert inspector.get_pk_constraint(model.__tablename__)["constrained_columns"] == ["id"]
        assert {"created_at", "updated_at"}.issubset(
            {column["name"] for column in inspector.get_columns(model.__tablename__)}
        )
    with seeded_database.session_factory() as session:
        placement = session.scalar(select(Placement))
        assert placement.match.candidate_id == placement.candidate.id
        assert placement.match.vacancy_id == placement.vacancy.id
        assert placement.steps
        notification = session.scalar(select(Notification))
        assert notification.placement_stage.placement_id == notification.placement.id
        assert notification.candidate.id == notification.placement.candidate_id
        assert notification.attempts or notification.status == "pending"


def test_sqlite_round_trips_aware_utc_and_rejects_naive_timestamps(seeded_database):
    with seeded_database.session_factory.begin() as session:
        step = session.scalar(select(PlacementStage))
        identifier = step.id
        assert step.scheduled_at.tzinfo == UTC
        with pytest.raises(StatementError, match="Timezone-aware"):
            with session.begin_nested():
                session.execute(
                    update(PlacementStage)
                    .where(PlacementStage.id == identifier)
                    .values(scheduled_at=datetime(2026, 11, 5, 9))
                )
    with seeded_database.session_factory() as session:
        step = session.get(PlacementStage, identifier)
        assert step.scheduled_at.tzinfo == UTC
        assert step.created_at.tzinfo == UTC


def test_missing_parent_foreign_key_fails(migrated_database):
    with migrated_database.session_factory.begin() as session:
        with pytest.raises(IntegrityError):
            with session.begin_nested():
                session.add(
                    PlacementStage(
                        placement_id=uuid4(),
                        code="interview",
                        step_type="interview",
                        sequence_number=1,
                        status="pending",
                    )
                )
                session.flush()


@pytest.mark.parametrize("changes", [{"code": "new_code"}, {"sequence_number": 3}])
def test_placement_step_code_and_order_are_independently_unique(seeded_database, changes):
    with seeded_database.session_factory.begin() as session:
        row = session.scalar(select(PlacementStage))
        values = {
            column.name: getattr(row, column.name)
            for column in PlacementStage.__table__.columns
            if column.name not in {"id", "created_at", "updated_at"}
        }
        with pytest.raises(IntegrityError):
            with session.begin_nested():
                session.add(PlacementStage(**(values | changes)))
                session.flush()
