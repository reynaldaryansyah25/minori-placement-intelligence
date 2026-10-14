"""Minimal 9Router adapter without prompts, model defaults, or business logic."""

import logging
from collections.abc import Sequence
from time import monotonic
from typing import cast

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI
from openai.types.chat import ChatCompletionMessageParam

from minori.core.config import Settings
from minori.domain.ports import ChatMessage

logger = logging.getLogger(__name__)


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
        self._models = tuple(
            dict.fromkeys([self._model, *settings.nine_router_fallback_models.split(",")])
        )
        self._models = tuple(model for model in self._models if model)
        self._timeout = settings.llm_timeout_seconds
        self._attempt_timeout = settings.llm_attempt_timeout_seconds
        self.last_model: str | None = None
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
        self.last_model = None
        deadline = monotonic() + self._timeout
        last_error = None
        for model in self._models:
            remaining = deadline - monotonic()
            if remaining <= 0:
                break
            # With fallback, spend the configured budget across models rather than
            # exhausting it on SDK retries of the same unavailable provider.
            options = (
                {"timeout": min(remaining, self._attempt_timeout), "max_retries": 0}
                if len(self._models) > 1
                else {}
            )
            try:
                completion = self._client.with_options(**options).chat.completions.create(
                    model=model, messages=payload, stream=False
                )
            except (APIConnectionError, APITimeoutError, APIStatusError) as error:
                if isinstance(error, APIStatusError) and error.status_code not in {
                    408,
                    429,
                    500,
                    502,
                    503,
                    504,
                }:
                    raise
                # Never log provider response bodies: these can contain input or secrets.
                logger.warning(
                    "9Router attempt failed: model=%s failure=%s status=%s",
                    model,
                    type(error).__name__,
                    getattr(error, "status_code", None),
                )
                last_error = error
                continue
            if not completion.choices or completion.choices[0].message.content is None:
                raise ValueError("9Router returned no text completion")
            self.last_model = model
            logger.info("9Router completion succeeded: model=%s", model)
            return completion.choices[0].message.content
        if last_error is None:
            raise TimeoutError("9Router request budget exhausted")
        raise last_error

    def close(self) -> None:
        self._client.close()
