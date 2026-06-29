"""
app/core/logging.py — Structured JSON (or text) logging setup.

Call `setup_logging()` once at application startup.
Use `get_logger(__name__)` everywhere else.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

from pythonjsonlogger import jsonlogger  # type: ignore[import]

from app.core.config import get_settings

_CONFIGURED = False


class _CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Adds a 'service' field to every log record."""

    def add_fields(
        self,
        log_record: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        super().add_fields(log_record, record, message_dict)
        log_record["service"] = "enterprise-knowledge-assistant"
        log_record["logger"] = record.name
        if record.exc_info and not log_record.get("exc_info"):
            log_record["exc_info"] = self.formatException(record.exc_info)


def setup_logging() -> None:
    """Configure the root logger once; subsequent calls are no-ops."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True

    settings = get_settings()
    level = getattr(logging, settings.log_level, logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    if settings.log_format == "json":
        fmt = _CustomJsonFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    else:
        fmt = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    handler.setFormatter(fmt)
    root.addHandler(handler)

    # Suppress noisy third-party loggers
    for noisy in ("httpx", "httpcore", "chromadb", "urllib3", "PIL"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a module-level logger. Call setup_logging() before first use."""
    return logging.getLogger(name)
