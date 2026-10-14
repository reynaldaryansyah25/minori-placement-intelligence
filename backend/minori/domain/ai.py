"""AI ports and safe failures; models cannot perform application actions."""

from typing import Protocol


class AiUnavailableError(RuntimeError):
    """Gateway unavailable or not configured."""


class AiOutputError(ValueError):
    """Model output violates the bounded structured contract."""


class StructuredAiGateway(Protocol):
    def generate(self, task: str, facts: dict) -> dict: ...
