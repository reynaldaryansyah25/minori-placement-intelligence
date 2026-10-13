"""Concrete candidate repositories returning detached domain values."""

from dataclasses import asdict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from minori.db.models import (
    Candidate,
    CandidateCertification,
    CandidateExperience,
    CandidateLanguageTest,
)
from minori.domain.catalogs import CandidateStatus, Program
from minori.domain.entities import (
    CandidateData,
    CandidateRecord,
)
from minori.repositories.mapping import pagination, preserve_identity, require_row, to_record
from minori.schemas.candidate import CandidateCreate


class SqlAlchemyCandidateRepository:
    """Persistence operations; flush writes and leave commit/rollback to the caller."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, data: CandidateData) -> CandidateRecord:
        values = CandidateCreate.model_validate(asdict(data)).model_dump()
        values["language_tests"] = [
            CandidateLanguageTest(**item) for item in values["language_tests"]
        ]
        values["certifications"] = [
            CandidateCertification(**item) for item in values["certifications"]
        ]
        values["experiences"] = [CandidateExperience(**item) for item in values["experiences"]]
        row = Candidate(**values)
        self._session.add(row)
        self._session.flush()
        return to_record(row, CandidateRecord)

    def get(self, identifier: UUID) -> CandidateRecord | None:
        row = self._session.get(Candidate, identifier)
        return None if row is None else to_record(row, CandidateRecord)

    def get_by_reference(self, reference: str) -> CandidateRecord | None:
        row = self._session.scalar(select(Candidate).where(Candidate.reference == reference))
        return None if row is None else to_record(row, CandidateRecord)

    def list(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        preferred_program: Program | None = None,
        status: CandidateStatus | None = None,
    ) -> list[CandidateRecord]:
        pagination(limit, offset)
        query = select(Candidate)
        if preferred_program is not None:
            query = query.where(Candidate.preferred_program == preferred_program)
        if status is not None:
            query = query.where(Candidate.status == status)
        rows = self._session.scalars(
            query.order_by(Candidate.created_at, Candidate.id).limit(limit).offset(offset)
        ).all()
        return [to_record(row, CandidateRecord) for row in rows]

    def replace(self, identifier: UUID, data: CandidateData) -> CandidateRecord:
        row = require_row(self._session.get(Candidate, identifier), identifier)
        values = CandidateCreate.model_validate(asdict(data)).model_dump()
        preserve_identity(row, values, ("reference",))
        values["language_tests"] = [
            CandidateLanguageTest(**item) for item in values["language_tests"]
        ]
        values["certifications"] = [
            CandidateCertification(**item) for item in values["certifications"]
        ]
        values["experiences"] = [CandidateExperience(**item) for item in values["experiences"]]
        row.language_tests.clear()
        row.certifications.clear()
        row.experiences.clear()
        self._session.flush()
        for field, value in values.items():
            setattr(row, field, value)
        self._session.flush()
        return to_record(row, CandidateRecord)

    def archive(self, identifier: UUID) -> CandidateRecord:
        row = require_row(self._session.get(Candidate, identifier), identifier)
        row.status = CandidateStatus.INACTIVE
        self._session.flush()
        return to_record(row, CandidateRecord)
