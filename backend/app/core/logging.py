"""
Structured logging configuration.

Configures Python logging with JSON-structured output for machine-parseable
log streams. Each record includes ts, level, logger, msg, and any extra
context fields (run_id, job_id, algorithm, event) injected via LoggerAdapter.
"""

import json
import logging
import sys
from datetime import UTC, datetime


class _JsonFormatter(logging.Formatter):
    """Emit one JSON object per log record on stdout."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Carry through any extra context set via LoggerAdapter (run_id, job_id, etc.)
        for key in ("run_id", "job_id", "algorithm", "event"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def setup_logging(log_level: str = "INFO") -> None:
    """Configure JSON-structured logging on stdout.

    Args:
        log_level: Logging level name (e.g., "DEBUG", "INFO", "WARNING", "ERROR")
    """
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(_JsonFormatter())
    root_logger.addHandler(console_handler)

    # Suppress per-request PubChem transport logs; app-level sync logs remain.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("qiskit_runtime_service._discover_account").setLevel(logging.ERROR)


def make_run_logger(base_logger: logging.Logger, run_id: str, **extra) -> logging.LoggerAdapter:
    """Return a LoggerAdapter that stamps run_id (and optional extras) on every record."""
    return logging.LoggerAdapter(base_logger, {"run_id": run_id, **extra})
