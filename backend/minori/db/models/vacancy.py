"""Vacancy requirements and reviewed draft storage."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import JSON, CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from minori.db.base import Base
from minori.db.models.common import IdentityTimestampMixin, ReferenceMixin, UTCDateTime, enum_type
from minori.domain.catalogs import DraftStatus, LanguageTestType, Program, VacancyStatus

if TYPE_CHECKING:
    from minori.db.models.match import Match
    from minori.db.models.placement import Placement


class Vacancy(ReferenceMixin, IdentityTimestampMixin, Base):
    __tablename__ = "vacancies"
    __table_args__ = (
        CheckConstraint("quota > 0", name="positive_quota"),
        CheckConstraint("minimum_experience_months >= 0", name="nonnegative_experience"),
        CheckConstraint("length(trim(title)) > 0", name="title_not_blank"),
        CheckConstraint("length(trim(reference)) > 0", name="reference_not_blank"),
    )

    title: Mapped[str] = mapped_column(String(160))
    employer_name: Mapped[str] = mapped_column(String(160))
    program: Mapped[Program] = mapped_column(enum_type(Program, "vacancy_program"), index=True)
    sector: Mapped[str] = mapped_column(String(80), index=True)
    prefecture: Mapped[str] = mapped_column(String(80))
    quota: Mapped[int]
    minimum_experience_months: Mapped[int] = mapped_column(default=0)
    required_skills: Mapped[list[str]] = mapped_column(JSON, default=list)
    required_certifications: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[VacancyStatus] = mapped_column(
        enum_type(VacancyStatus, "vacancy_status"), default=VacancyStatus.OPEN, index=True
    )
    application_deadline: Mapped[datetime | None] = mapped_column(UTCDateTime(), index=True)
    language_requirements: Mapped[list[VacancyLanguageRequirement]] = relationship(
        back_populates="vacancy", cascade="all, delete-orphan", lazy="selectin"
    )
    drafts: Mapped[list[VacancyDraft]] = relationship(back_populates="published_vacancy")
    matches: Mapped[list[Match]] = relationship(back_populates="vacancy", passive_deletes="all")
    placements: Mapped[list[Placement]] = relationship(
        back_populates="vacancy", passive_deletes="all"
    )


class VacancyLanguageRequirement(IdentityTimestampMixin, Base):
    __tablename__ = "vacancy_language_requirements"
    __table_args__ = (
        UniqueConstraint("vacancy_id", "test_type"),
        CheckConstraint(
            "(test_type = 'jlpt' AND minimum_level IN ('N1','N2','N3','N4','N5')) OR "
            "(test_type = 'jft_basic' AND minimum_level IN ('A1','A2.1','A2.2'))",
            name="test_level_pair",
        ),
    )

    vacancy_id: Mapped[UUID] = mapped_column(
        ForeignKey("vacancies.id", ondelete="CASCADE"), index=True
    )
    test_type: Mapped[LanguageTestType] = mapped_column(
        enum_type(LanguageTestType, "requirement_test_type")
    )
    minimum_level: Mapped[str] = mapped_column(String(8))
    vacancy: Mapped[Vacancy] = relationship(back_populates="language_requirements")


class VacancyDraft(ReferenceMixin, IdentityTimestampMixin, Base):
    __tablename__ = "vacancy_drafts"
    __table_args__ = (
        UniqueConstraint("source_channel", "source_reference"),
        CheckConstraint(
            "(status = 'published' AND published_vacancy_id IS NOT NULL) OR "
            "(status != 'published' AND published_vacancy_id IS NULL)",
            name="publication_link",
        ),
    )

    source_channel: Mapped[str] = mapped_column(String(80))
    source_reference: Mapped[str] = mapped_column(String(120))
    proposed_data: Mapped[dict[str, object]] = mapped_column(JSON)
    status: Mapped[DraftStatus] = mapped_column(
        enum_type(DraftStatus, "draft_status"), default=DraftStatus.DRAFT, index=True
    )
    published_vacancy_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("vacancies.id", ondelete="RESTRICT"), unique=True
    )
    published_vacancy: Mapped[Vacancy | None] = relationship(back_populates="drafts")
