"""Structured JSON logger for the RAG Platform.

Every log entry includes:
  - timestamp     : ISO-8601 UTC timestamp
  - level         : log level name
  - logger        : logger name (module)
  - request_id    : AWS Lambda request ID (or 'local')
  - session_id    : chat session ID (optional)
  - document_id   : document ID being processed (optional)
  - action        : name of the high-level operation
  - duration_ms   : elapsed time in milliseconds (optional)
  - status        : 'ok', 'error', 'stub', etc.
  - error_code    : short error identifier (optional)
  - message       : human-readable description

Usage:
    from shared.logger import get_logger

    logger = get_logger(__name__)
    log = logger.bind(request_id="abc-123", action="document_processor")
    log.info("processing_document", bucket="my-bucket", key="doc.pdf")
    log.error("processing_failed", error="timeout", error_code="TIMEOUT")
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Optional


class _JsonFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        # Base fields always present
        entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
        }

        # Merge bound context fields (attached by BoundLogger)
        context: dict = getattr(record, "_context", {})
        entry.update(context)

        # The message is the event/action label; extra details come from context
        entry["message"] = record.getMessage()

        # Include exception info if present
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(entry, default=str)


class BoundLogger:
    """A logger that carries pre-bound context fields into every log call."""

    def __init__(self, logger: logging.Logger, context: dict[str, Any]) -> None:
        self._logger = logger
        self._context: dict[str, Any] = context

    def bind(self, **kwargs: Any) -> "BoundLogger":
        """Return a new BoundLogger with additional context fields."""
        merged = {**self._context, **kwargs}
        return BoundLogger(self._logger, merged)

    def _log(self, level: int, event: str, **kwargs: Any) -> None:
        extra_context = {**self._context, **kwargs}
        record = self._logger.makeRecord(
            name=self._logger.name,
            level=level,
            fn="",
            lno=0,
            msg=event,
            args=(),
            exc_info=kwargs.pop("exc_info", None),
        )
        record._context = extra_context  # type: ignore[attr-defined]
        record.msg = event
        record.args = ()
        self._logger.handle(record)

    def debug(self, event: str, **kwargs: Any) -> None:
        if self._logger.isEnabledFor(logging.DEBUG):
            self._log(logging.DEBUG, event, **kwargs)

    def info(self, event: str, **kwargs: Any) -> None:
        if self._logger.isEnabledFor(logging.INFO):
            self._log(logging.INFO, event, **kwargs)

    def warning(self, event: str, **kwargs: Any) -> None:
        if self._logger.isEnabledFor(logging.WARNING):
            self._log(logging.WARNING, event, **kwargs)

    def error(self, event: str, **kwargs: Any) -> None:
        if self._logger.isEnabledFor(logging.ERROR):
            self._log(logging.ERROR, event, **kwargs)

    def critical(self, event: str, **kwargs: Any) -> None:
        if self._logger.isEnabledFor(logging.CRITICAL):
            self._log(logging.CRITICAL, event, **kwargs)


def get_logger(name: str, level: Optional[str] = None) -> BoundLogger:
    """Create or retrieve a structured JSON logger.

    Args:
        name: Logger name, typically ``__name__``.
        level: Log level string. Falls back to ``LOG_LEVEL`` env var, then INFO.

    Returns:
        BoundLogger: A logger that produces structured JSON output.
    """
    log_level_str = level or os.environ.get("LOG_LEVEL", "INFO")
    log_level = getattr(logging, log_level_str.upper(), logging.INFO)

    underlying = logging.getLogger(name)

    if not underlying.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(_JsonFormatter())
        underlying.addHandler(handler)
        underlying.propagate = False

    underlying.setLevel(log_level)

    return BoundLogger(underlying, {})
