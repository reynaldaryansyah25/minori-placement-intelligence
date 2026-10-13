"""Snapshot mapping and validation helpers; no generic CRUD repository."""

from copy import deepcopy
from dataclasses import fields

from minori.domain.entities import (
    CertificationData,
    ExperienceData,
    LanguageRequirementData,
    LanguageTestData,
)
from minori.domain.errors import RecordNotFoundError

CHILD_VALUES = {
    "language_tests": LanguageTestData,
    "certifications": CertificationData,
    "experiences": ExperienceData,
    "language_requirements": LanguageRequirementData,
}


def to_record(row, record_type):
    values = {}
    for descriptor in fields(record_type):
        value = getattr(row, descriptor.name)
        if descriptor.name in CHILD_VALUES:
            child_type = CHILD_VALUES[descriptor.name]
            value = tuple(
                child_type(
                    **{field.name: getattr(child, field.name) for field in fields(child_type)}
                )
                for child in value
            )
        elif isinstance(value, list):
            value = tuple(value)
        elif isinstance(value, dict):
            value = deepcopy(value)
        values[descriptor.name] = value
    return record_type(**values)


def require_row(row, identifier):
    if row is None:
        raise RecordNotFoundError(f"Record {identifier} does not exist")
    return row


def preserve_identity(row, values: dict, immutable_fields: tuple[str, ...]) -> None:
    for field in immutable_fields:
        if getattr(row, field) != values[field]:
            raise ValueError(f"{field} cannot be changed by replacement")


def pagination(limit: int, offset: int) -> None:
    if not 1 <= limit <= 100 or offset < 0:
        raise ValueError("limit must be 1..100 and offset must be nonnegative")
