"""Append/read adapter for immutable evaluation history."""

from dataclasses import asdict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from minori.db.models import MatchEvaluation
from minori.domain.matching import EvaluationRecord, MatchingEvaluation
from minori.repositories.mapping import pagination, to_record
from minori.schemas.matching import EvaluationCreate


class SqlAlchemyEvaluationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def append(self, evaluation: MatchingEvaluation) -> EvaluationRecord:
        values = EvaluationCreate.model_validate(asdict(evaluation)).model_dump(mode="python")
        row = MatchEvaluation(**values)
        self._session.add(row)
        self._session.flush()
        return to_record(row, EvaluationRecord)

    def find_identical(self, evaluation: MatchingEvaluation) -> EvaluationRecord | None:
        row = self._session.scalar(
            select(MatchEvaluation).where(
                MatchEvaluation.candidate_id == evaluation.candidate_id,
                MatchEvaluation.vacancy_id == evaluation.vacancy_id,
                MatchEvaluation.input_fingerprint == evaluation.input_fingerprint,
                MatchEvaluation.evaluated_at == evaluation.evaluated_at,
                MatchEvaluation.algorithm_version == evaluation.algorithm_version,
            )
        )
        return None if row is None else to_record(row, EvaluationRecord)

    def get(self, identifier: UUID) -> EvaluationRecord | None:
        row = self._session.get(MatchEvaluation, identifier)
        return None if row is None else to_record(row, EvaluationRecord)

    def latest(self, candidate_id: UUID, vacancy_id: UUID) -> EvaluationRecord | None:
        records = self.list(candidate_id=candidate_id, vacancy_id=vacancy_id, limit=1)
        return records[0] if records else None

    def list(
        self,
        *,
        candidate_id: UUID | None = None,
        vacancy_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EvaluationRecord]:
        pagination(limit, offset)
        query = select(MatchEvaluation)
        if candidate_id is not None:
            query = query.where(MatchEvaluation.candidate_id == candidate_id)
        if vacancy_id is not None:
            query = query.where(MatchEvaluation.vacancy_id == vacancy_id)
        rows = self._session.scalars(
            query.order_by(
                MatchEvaluation.evaluated_at.desc(),
                MatchEvaluation.created_at.desc(),
                MatchEvaluation.id,
            )
            .limit(limit)
            .offset(offset)
        ).all()
        return [to_record(row, EvaluationRecord) for row in rows]
