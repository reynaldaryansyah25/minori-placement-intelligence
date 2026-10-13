"""Vacancy requirement and draft contracts, independent of inference."""

from typing import Self
from uuid import UUID

from pydantic import AwareDatetime, Field, StrictInt, model_validator

from minori.domain.catalogs import (
    DraftStatus,
    LanguageTestType,
    Program,
    VacancyStatus,
    validate_language_level,
)
from minori.domain.entities import LanguageRequirementData, VacancyData, VacancyDraftData
from minori.schemas.common import Code, InputSchema, NonBlank, RecordFields, Reference


class LanguageRequirementCreate(InputSchema):
    test_type: LanguageTestType
    minimum_level: str

    @model_validator(mode="after")
    def validate_level(self) -> Self:
        validate_language_level(self.test_type, self.minimum_level)
        return self


class VacancyCreate(InputSchema):
    reference: Reference
    title: NonBlank
    employer_name: NonBlank
    program: Program
    sector: str = Field(min_length=1, max_length=80)
    prefecture: str = Field(min_length=1, max_length=80)
    quota: StrictInt = Field(gt=0)
    minimum_experience_months: StrictInt = Field(default=0, ge=0)
    required_skills: list[Code] = Field(default_factory=list, max_length=50)
    required_certifications: list[Code] = Field(default_factory=list, max_length=50)
    preferred_skills: list[Code] = Field(default_factory=list, max_length=50)
    preferred_certifications: list[Code] = Field(default_factory=list, max_length=50)
    language_test_max_age_months: StrictInt | None = Field(default=None, gt=0, le=1200)
    language_requirements: list[LanguageRequirementCreate] = Field(
        default_factory=list, max_length=2
    )
    status: VacancyStatus = VacancyStatus.OPEN
    application_deadline: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_unique_requirements(self) -> Self:
        groups = [
            self.required_skills,
            self.required_certifications,
            self.preferred_skills,
            self.preferred_certifications,
            [item.test_type for item in self.language_requirements],
        ]
        if any(len(items) != len(set(items)) for items in groups):
            raise ValueError("Duplicate vacancy requirements")
        return self

    def to_domain(self, data_type=VacancyData) -> VacancyData:
        values = self.model_dump(exclude={"language_requirements"})
        values["required_skills"] = tuple(self.required_skills)
        values["required_certifications"] = tuple(self.required_certifications)
        values["preferred_skills"] = tuple(self.preferred_skills)
        values["preferred_certifications"] = tuple(self.preferred_certifications)
        return data_type(
            **values,
            language_requirements=tuple(
                item.to_domain(LanguageRequirementData) for item in self.language_requirements
            ),
        )


class VacancyRead(VacancyCreate, RecordFields):
    """Normalized requirements represented as a detached aggregate."""


class VacancyDraftCreate(InputSchema):
    reference: Reference
    source_channel: Code
    source_reference: str = Field(min_length=1, max_length=120)
    proposed_data: VacancyCreate
    status: DraftStatus = DraftStatus.DRAFT
    published_vacancy_id: UUID | None = None

    @model_validator(mode="after")
    def validate_publication(self) -> Self:
        if (self.status == DraftStatus.PUBLISHED) != (self.published_vacancy_id is not None):
            raise ValueError("Only published drafts must link to a published vacancy")
        return self

    def to_domain(self, data_type=VacancyDraftData) -> VacancyDraftData:
        values = self.model_dump()
        values["proposed_data"] = self.proposed_data.model_dump(mode="json")
        return data_type(**values)


class VacancyDraftRead(VacancyDraftCreate, RecordFields):
    """Reviewed source data without raw documents or extracted private content."""
