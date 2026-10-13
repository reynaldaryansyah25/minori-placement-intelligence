"""Concrete placement repositories returning detached domain values."""

from dataclasses import asdict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from minori.db.models import Placement, PlacementStage
from minori.domain.entities import (
    PlacementData,
    PlacementRecord,
    PlacementStageData,
    PlacementStageRecord,
)
from minori.repositories.mapping import pagination, preserve_identity, require_row, to_record
from minori.schemas.placement import PlacementCreate, PlacementStageCreate


class SqlAlchemyPlacementRepository:
    """Persistence operations; flush writes and leave commit/rollback to the caller."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, data: PlacementData) -> PlacementRecord:
        values = PlacementCreate.model_validate(asdict(data)).model_dump()
        row = Placement(**values)
        self._session.add(row)
        self._session.flush()
        return to_record(row, PlacementRecord)

    def get(self, identifier: UUID) -> PlacementRecord | None:
        row = self._session.get(Placement, identifier)
        return None if row is None else to_record(row, PlacementRecord)

    def get_by_reference(self, reference: str) -> PlacementRecord | None:
        row = self._session.scalar(select(Placement).where(Placement.reference == reference))
        return None if row is None else to_record(row, PlacementRecord)

    def list_for_candidate(
        self, candidate_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> list[PlacementRecord]:
        pagination(limit, offset)
        query = select(Placement)
        query = query.where(Placement.candidate_id == candidate_id)
        rows = self._session.scalars(
            query.order_by(Placement.created_at, Placement.id).limit(limit).offset(offset)
        ).all()
        return [to_record(row, PlacementRecord) for row in rows]

    def replace(self, identifier: UUID, data: PlacementData) -> PlacementRecord:
        row = require_row(self._session.get(Placement, identifier), identifier)
        values = PlacementCreate.model_validate(asdict(data)).model_dump()
        preserve_identity(row, values, ("reference", "candidate_id", "vacancy_id", "match_id"))
        for field, value in values.items():
            setattr(row, field, value)
        self._session.flush()
        return to_record(row, PlacementRecord)


class SqlAlchemyPlacementStageRepository:
    """Persistence operations; flush writes and leave commit/rollback to the caller."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, data: PlacementStageData) -> PlacementStageRecord:
        values = PlacementStageCreate.model_validate(asdict(data)).model_dump()
        row = PlacementStage(**values)
        self._session.add(row)
        self._session.flush()
        return to_record(row, PlacementStageRecord)

    def get(self, identifier: UUID) -> PlacementStageRecord | None:
        row = self._session.get(PlacementStage, identifier)
        return None if row is None else to_record(row, PlacementStageRecord)

    def get_by_code(self, placement_id: UUID, code: str) -> PlacementStageRecord | None:
        row = self._session.scalar(
            select(PlacementStage).where(
                PlacementStage.placement_id == placement_id,
                PlacementStage.code == code,
            )
        )
        return None if row is None else to_record(row, PlacementStageRecord)

    def list_for_placement(
        self, placement_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> list[PlacementStageRecord]:
        pagination(limit, offset)
        query = select(PlacementStage)
        query = query.where(PlacementStage.placement_id == placement_id)
        rows = self._session.scalars(
            query.order_by(PlacementStage.sequence_number, PlacementStage.id)
            .limit(limit)
            .offset(offset)
        ).all()
        return [to_record(row, PlacementStageRecord) for row in rows]

    def replace(self, identifier: UUID, data: PlacementStageData) -> PlacementStageRecord:
        row = require_row(self._session.get(PlacementStage, identifier), identifier)
        values = PlacementStageCreate.model_validate(asdict(data)).model_dump()
        preserve_identity(row, values, ("placement_id", "code"))
        for field, value in values.items():
            setattr(row, field, value)
        self._session.flush()
        return to_record(row, PlacementStageRecord)
