"""Strict transport validation and explicit conversion into immutable domain values."""

from datetime import datetime
from typing import Annotated, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

NonBlank = Annotated[str, Field(min_length=1, max_length=160)]
Code = Annotated[str, Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.:-]+$")]
Reference = Annotated[str, Field(min_length=2, max_length=64, pattern=r"^[A-Z][A-Z0-9_-]+$")]
T = TypeVar("T")


class InputSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_default=True,
        from_attributes=True,
        allow_inf_nan=False,
        hide_input_in_errors=True,
    )

    def to_domain(self, data_type: type[T]) -> T:
        return data_type(**self.model_dump())


class RecordFields(InputSchema):
    id: UUID
    created_at: datetime
    updated_at: datetime
