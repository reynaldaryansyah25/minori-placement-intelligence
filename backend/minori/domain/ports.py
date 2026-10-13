"""Ports implemented by infrastructure adapters."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol


class DatabaseProbe(Protocol):
    """Read-only database readiness contract."""

    def is_ready(self) -> bool:
        """Return whether a database query succeeds."""
        ...


@dataclass(frozen=True)
class ChatMessage:
    role: Literal["system", "user", "assistant"]
    content: str


class ChatCompletionGateway(Protocol):
    """Provider-independent text completion contract for future use cases."""

    def complete(self, messages: Sequence[ChatMessage]) -> str:
        """Return text from an explicitly supplied conversation."""
        ...
