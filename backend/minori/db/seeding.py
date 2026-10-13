"""Atomic synthetic fixtures using repositories and stable natural keys."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import Field

from minori.core.config import PROJECT_ROOT, get_settings
from minori.db.inspection import inspect_database
from minori.db.session import Database
from minori.domain.entities import (
    MatchData,
    NotificationAttemptData,
    NotificationData,
    PlacementData,
    PlacementStageData,
)
from minori.repositories.provider import provide_repositories
from minori.schemas.audit import AuditLogCreate
from minori.schemas.candidate import CandidateCreate
from minori.schemas.common import InputSchema
from minori.schemas.match import MatchCreate
from minori.schemas.notification import NotificationAttemptCreate, NotificationCreate
from minori.schemas.placement import PlacementCreate, PlacementStageCreate
from minori.schemas.vacancy import VacancyCreate, VacancyDraftCreate


class CandidateFixtures(InputSchema):
    synthetic: Literal[True]
    description: str
    candidates: list[CandidateCreate] = Field(min_length=5)


class VacancyFixtures(InputSchema):
    synthetic: Literal[True]
    description: str
    vacancies: list[VacancyCreate] = Field(min_length=3)


class PlacementFixtures(InputSchema):
    synthetic: Literal[True]
    description: str
    matches: list[dict[str, object]]
    placements: list[dict[str, object]]
    steps: list[dict[str, object]]
    drafts: list[dict[str, object]]
    notifications: list[dict[str, object]]
    attempts: list[dict[str, object]]


def read_fixture(path: Path, schema_type):
    return schema_type.model_validate_json(path.read_text(encoding="utf-8"))


def seed_database(database: Database, fixture_directory: Path | None = None) -> dict[str, object]:
    """Insert missing fixture keys only, preserving existing values and IDs."""
    inspect_database(database)
    directory = fixture_directory or PROJECT_ROOT / "data/dummy"
    candidate_file = read_fixture(directory / "candidates.json", CandidateFixtures)
    vacancy_file = read_fixture(directory / "vacancies.json", VacancyFixtures)
    planning = read_fixture(directory / "placement_data.json", PlacementFixtures)
    for records in (candidate_file.candidates, vacancy_file.vacancies):
        refs = [item.reference for item in records]
        if len(refs) != len(set(refs)) or any(not ref.startswith("DEMO-") for ref in refs):
            raise ValueError("Fixtures require unique DEMO references")
    inserted = 0
    preserved = 0
    with database.session_factory.begin() as session:
        repos = provide_repositories(session)

        def audit(record, entity_type):
            reference = "DEMO-AUDIT-" + record.reference.removeprefix("DEMO-")
            if repos.audit_log.get_by_reference(reference) is None:
                repos.audit_log.append(
                    AuditLogCreate(
                        reference=reference,
                        actor_reference="fixture.seed",
                        action="fixture.created",
                        entity_type=entity_type,
                        entity_id=record.id,
                        occurred_at=datetime.now(UTC),
                        context={"synthetic": True, "fixture": "placement_fixture"},
                    ).to_domain()
                )

        def remember(existing, creator, *, entity_type=None):
            nonlocal inserted, preserved
            if existing is None:
                record = creator()
                inserted += 1
            else:
                record = existing
                preserved += 1
            if entity_type:
                audit(record, entity_type)
            return record

        candidates = {
            item.reference: remember(
                repos.candidate.get_by_reference(item.reference),
                lambda item=item: repos.candidate.create(item.to_domain()),
                entity_type="candidate",
            )
            for item in candidate_file.candidates
        }
        vacancies = {
            item.reference: remember(
                repos.vacancy.get_by_reference(item.reference),
                lambda item=item: repos.vacancy.create(item.to_domain()),
                entity_type="vacancy",
            )
            for item in vacancy_file.vacancies
        }
        matches = {}
        for entry in planning.matches:
            values = dict(entry)
            candidate = candidates[values.pop("candidate_reference")]
            vacancy = vacancies[values.pop("vacancy_reference")]
            data = MatchCreate(
                candidate_id=candidate.id, vacancy_id=vacancy.id, **values
            ).to_domain(MatchData)
            matches[(candidate.reference, vacancy.reference)] = remember(
                repos.match.get_by_pair(candidate.id, vacancy.id),
                lambda data=data: repos.match.create(data),
            )
        placements = {}
        for entry in planning.placements:
            values = dict(entry)
            candidate = candidates[values.pop("candidate_reference")]
            vacancy = vacancies[values.pop("vacancy_reference")]
            match = matches.get((candidate.reference, vacancy.reference))
            use_match = values.pop("use_match")
            if not isinstance(use_match, bool) or (use_match and match is None):
                raise ValueError("Placement fixture requires an explicit valid association")
            data = PlacementCreate(
                candidate_id=candidate.id,
                vacancy_id=vacancy.id,
                match_id=match.id if use_match else None,
                **values,
            ).to_domain(PlacementData)
            placements[data.reference] = remember(
                repos.placement.get_by_reference(data.reference),
                lambda data=data: repos.placement.create(data),
                entity_type="placement",
            )
        steps = {}
        for entry in planning.steps:
            values = dict(entry)
            placement = placements[values.pop("placement_reference")]
            data = PlacementStageCreate(placement_id=placement.id, **values).to_domain(
                PlacementStageData
            )
            steps[(placement.reference, data.code)] = remember(
                repos.placement_stage.get_by_code(placement.id, data.code),
                lambda data=data: repos.placement_stage.create(data),
            )
        for entry in planning.drafts:
            values = dict(entry)
            published_ref = values.pop("published_vacancy_reference")
            data = VacancyDraftCreate(
                published_vacancy_id=vacancies[published_ref].id if published_ref else None,
                **values,
            ).to_domain()
            remember(
                repos.vacancy_draft.get_by_reference(data.reference),
                lambda data=data: repos.vacancy_draft.create(data),
            )
        notifications = {}
        for entry in planning.notifications:
            values = dict(entry)
            candidate = candidates[values.pop("candidate_reference")]
            placement = placements[values.pop("placement_reference")]
            step = steps[(placement.reference, values.pop("step_code"))]
            data = NotificationCreate(
                candidate_id=candidate.id,
                placement_id=placement.id,
                placement_stage_id=step.id,
                **values,
            ).to_domain(NotificationData)
            notifications[data.reference] = remember(
                repos.notification.get_by_deduplication_key(data.deduplication_key),
                lambda data=data: repos.notification.create(data),
                entity_type="notification",
            )
        for entry in planning.attempts:
            values = dict(entry)
            notification = notifications[values.pop("notification_reference")]
            data = NotificationAttemptCreate(notification_id=notification.id, **values).to_domain(
                NotificationAttemptData
            )
            remember(
                repos.notification_attempt.get_by_number(notification.id, data.attempt_number),
                lambda data=data: repos.notification_attempt.append(data),
            )
    return {
        "inserted_records": inserted,
        "preserved_records": preserved,
        "counts": inspect_database(database)["counts"],
    }


def main() -> None:
    settings = get_settings()
    if settings.app_env == "production":
        raise SystemExit("Synthetic fixtures are restricted to development and test environments")
    database = Database(settings)
    try:
        print(json.dumps(seed_database(database), indent=2))
    finally:
        database.dispose()
