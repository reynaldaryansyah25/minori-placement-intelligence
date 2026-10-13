"""Minimal 9Router adapter without prompts, model defaults, or business logic."""

from collections.abc import Sequence
from typing import cast

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

from minori.core.config import Settings
from minori.domain.ports import ChatMessage


class RouterConfigurationError(RuntimeError):
    """Raised when an application attempts to use a disabled LLM adapter."""


class NineRouterClient:
    """Explicitly configured client; construction does not make an API request."""

    def __init__(self, settings: Settings) -> None:
        if not settings.llm_enabled:
            raise RouterConfigurationError("Enable and configure 9Router before using the client")
        if not (
            settings.nine_router_base_url
            and settings.nine_router_api_key
            and settings.nine_router_model
        ):
            raise RouterConfigurationError("9Router connection settings are incomplete")
        self._model = settings.nine_router_model
        self._client = OpenAI(
            base_url=str(settings.nine_router_base_url),
            api_key=settings.nine_router_api_key.get_secret_value(),
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )

    def complete(self, messages: Sequence[ChatMessage]) -> str:
        if not messages:
            raise ValueError("At least one chat message is required")
        payload = [
            cast(ChatCompletionMessageParam, {"role": item.role, "content": item.content})
            for item in messages
        ]
        completion = self._client.chat.completions.create(model=self._model, messages=payload)
        if not completion.choices or completion.choices[0].message.content is None:
            raise ValueError("9Router returned no text completion")
        return completion.choices[0].message.content

    def close(self) -> None:
        self._client.close()
