"""Concrete match repositories returning detached domain values."""

from dataclasses import asdict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from minori.db.models import Match
from minori.domain.entities import (
    MatchData,
    MatchRecord,
)
from minori.repositories.mapping import pagination, preserve_identity, require_row, to_record
from minori.schemas.match import MatchCreate


class SqlAlchemyMatchRepository:
    """Persistence operations; flush writes and leave commit/rollback to the caller."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, data: MatchData) -> MatchRecord:
        values = MatchCreate.model_validate(asdict(data)).model_dump()
        row = Match(**values)
        self._session.add(row)
        self._session.flush()
        return to_record(row, MatchRecord)

    def get(self, identifier: UUID) -> MatchRecord | None:
        row = self._session.get(Match, identifier)
        return None if row is None else to_record(row, MatchRecord)

    def get_by_pair(self, candidate_id: UUID, vacancy_id: UUID) -> MatchRecord | None:
        row = self._session.scalar(
            select(Match).where(
                Match.candidate_id == candidate_id,
                Match.vacancy_id == vacancy_id,
            )
        )
        return None if row is None else to_record(row, MatchRecord)

    def list_for_candidate(
        self, candidate_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> list[MatchRecord]:
        pagination(limit, offset)
        query = select(Match)
        query = query.where(Match.candidate_id == candidate_id)
        rows = self._session.scalars(
            query.order_by(Match.created_at, Match.id).limit(limit).offset(offset)
        ).all()
        return [to_record(row, MatchRecord) for row in rows]

    def replace(self, identifier: UUID, data: MatchData) -> MatchRecord:
        row = require_row(self._session.get(Match, identifier), identifier)
        values = MatchCreate.model_validate(asdict(data)).model_dump()
        preserve_identity(row, values, ("candidate_id", "vacancy_id"))
        for field, value in values.items():
            setattr(row, field, value)
        self._session.flush()
        return to_record(row, MatchRecord)
