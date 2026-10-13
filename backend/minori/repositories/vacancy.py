"""Concrete vacancy repositories returning detached domain values."""

from dataclasses import asdict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from minori.db.models import Vacancy, VacancyDraft, VacancyLanguageRequirement
from minori.domain.catalogs import DraftStatus, Program, VacancyStatus
from minori.domain.entities import (
    VacancyData,
    VacancyDraftData,
    VacancyDraftRecord,
    VacancyRecord,
)
from minori.repositories.mapping import pagination, preserve_identity, require_row, to_record
from minori.schemas.vacancy import VacancyCreate, VacancyDraftCreate


class SqlAlchemyVacancyRepository:
    """Persistence operations; flush writes and leave commit/rollback to the caller."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, data: VacancyData) -> VacancyRecord:
        values = VacancyCreate.model_validate(asdict(data)).model_dump()
        values["language_requirements"] = [
            VacancyLanguageRequirement(**item) for item in values["language_requirements"]
        ]
        row = Vacancy(**values)
        self._session.add(row)
        self._session.flush()
        return to_record(row, VacancyRecord)

    def get(self, identifier: UUID) -> VacancyRecord | None:
        row = self._session.get(Vacancy, identifier)
        return None if row is None else to_record(row, VacancyRecord)

    def get_by_reference(self, reference: str) -> VacancyRecord | None:
        row = self._session.scalar(select(Vacancy).where(Vacancy.reference == reference))
        return None if row is None else to_record(row, VacancyRecord)

    def list(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        program: Program | None = None,
        status: VacancyStatus | None = None,
    ) -> list[VacancyRecord]:
        pagination(limit, offset)
        query = select(Vacancy)
        if program is not None:
            query = query.where(Vacancy.program == program)
        if status is not None:
            query = query.where(Vacancy.status == status)
        rows = self._session.scalars(
            query.order_by(Vacancy.created_at, Vacancy.id).limit(limit).offset(offset)
        ).all()
        return [to_record(row, VacancyRecord) for row in rows]

    def replace(self, identifier: UUID, data: VacancyData) -> VacancyRecord:
        row = require_row(self._session.get(Vacancy, identifier), identifier)
        values = VacancyCreate.model_validate(asdict(data)).model_dump()
        preserve_identity(row, values, ("reference",))
        values["language_requirements"] = [
            VacancyLanguageRequirement(**item) for item in values["language_requirements"]
        ]
        row.language_requirements.clear()
        self._session.flush()
        for field, value in values.items():
            setattr(row, field, value)
        self._session.flush()
        return to_record(row, VacancyRecord)

    def archive(self, identifier: UUID) -> VacancyRecord:
        row = require_row(self._session.get(Vacancy, identifier), identifier)
        row.status = VacancyStatus.CLOSED
        self._session.flush()
        return to_record(row, VacancyRecord)


class SqlAlchemyVacancyDraftRepository:
    """Persistence operations; flush writes and leave commit/rollback to the caller."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, data: VacancyDraftData) -> VacancyDraftRecord:
        values = asdict(VacancyDraftCreate.model_validate(asdict(data)).to_domain())
        row = VacancyDraft(**values)
        self._session.add(row)
        self._session.flush()
        return to_record(row, VacancyDraftRecord)

    def get(self, identifier: UUID) -> VacancyDraftRecord | None:
        row = self._session.get(VacancyDraft, identifier)
        return None if row is None else to_record(row, VacancyDraftRecord)

    def get_by_reference(self, reference: str) -> VacancyDraftRecord | None:
        row = self._session.scalar(select(VacancyDraft).where(VacancyDraft.reference == reference))
        return None if row is None else to_record(row, VacancyDraftRecord)

    def list(
        self, *, limit: int = 100, offset: int = 0, status: DraftStatus | None = None
    ) -> list[VacancyDraftRecord]:
        pagination(limit, offset)
        query = select(VacancyDraft)
        if status is not None:
            query = query.where(VacancyDraft.status == status)
        rows = self._session.scalars(
            query.order_by(VacancyDraft.created_at, VacancyDraft.id).limit(limit).offset(offset)
        ).all()
        return [to_record(row, VacancyDraftRecord) for row in rows]

    def replace(self, identifier: UUID, data: VacancyDraftData) -> VacancyDraftRecord:
        row = require_row(self._session.get(VacancyDraft, identifier), identifier)
        values = asdict(VacancyDraftCreate.model_validate(asdict(data)).to_domain())
        preserve_identity(row, values, ("reference", "source_channel", "source_reference"))
        for field, value in values.items():
            setattr(row, field, value)
        self._session.flush()
        return to_record(row, VacancyDraftRecord)
