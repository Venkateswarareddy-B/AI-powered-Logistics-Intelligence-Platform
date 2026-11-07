"""Structured logging configuration.

Uses the standard library ``logging`` module with a JSON formatter so logs
are machine-parseable in production while remaining readable in local/debug
mode. No third-party logging dependency is introduced on purpose.
"""

import json
import logging
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """Emit log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Attach any structured ``extra`` fields the caller provided.
        if hasattr(record, "props") and isinstance(record.props, dict):
            payload.update(record.props)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO", debug: bool = False) -> None:
    """Configure the root logger.

    In debug mode a human-readable format is used; otherwise logs are emitted
    as JSON. Idempotent: existing handlers are removed before reconfiguration.
    """
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    if debug:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
    else:
        handler.setFormatter(JsonFormatter())

    root.addHandler(handler)
    root.setLevel(getattr(logging, str(level).upper(), logging.INFO))


def get_logger(name: str) -> logging.Logger:
    """Return a named logger."""
    return logging.getLogger(name)
