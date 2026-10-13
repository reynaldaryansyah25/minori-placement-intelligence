"""Structured console logging without request bodies or environment dumps."""

import json
import logging
from datetime import UTC, datetime
from logging.config import dictConfig


class JsonFormatter(logging.Formatter):
    """Serialize operational log metadata as JSON."""

    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            },
            ensure_ascii=False,
        )


def configure_logging(level: str) -> None:
    """Configure the application and suppress verbose third-party HTTP logs."""
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"json": {"()": JsonFormatter}},
            "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "json"}},
            "root": {"level": level, "handlers": ["console"]},
            "loggers": {
                name: {"level": "WARNING", "handlers": [], "propagate": True}
                for name in ("httpx", "httpx2", "httpcore", "openai")
            },
        }
    )
