"""Centralised logging configuration.

JSON output in production for log aggregators (Loki, ELK, Datadog), plain
text in dev. A correlation-id filter pulls ``request_id`` from
``flask.g`` so every line emitted during a request can be traced back to
the originating call.
"""
from __future__ import annotations

import logging
import os

try:
    from flask import g, has_request_context
except ImportError:  # pragma: no cover — flask is always present in this project
    g = None  # type: ignore[assignment]

    def has_request_context() -> bool:  # type: ignore[no-redef]
        return False


_PRODUCTION_ENVS = {"production", "prod"}


class RequestIdFilter(logging.Filter):
    """Stamp every log record with the current request's correlation id."""

    def filter(self, record: logging.LogRecord) -> bool:
        request_id = "-"
        if has_request_context():
            request_id = getattr(g, "request_id", None) or "-"
        record.request_id = request_id
        return True


def _is_production() -> bool:
    env = (
        os.getenv("APP_ENV") or os.getenv("FLASK_ENV") or os.getenv("ENV") or ""
    ).strip().lower()
    return env in _PRODUCTION_ENVS


def configure_logging() -> None:
    """Install handlers + filters on the root logger. Idempotent."""
    root = logging.getLogger()

    # Idempotent: clear our previous handlers before reconfiguring so reload
    # in tests doesn't compound formatters.
    for existing in list(root.handlers):
        root.removeHandler(existing)

    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    root.setLevel(log_level)

    handler = logging.StreamHandler()
    handler.addFilter(RequestIdFilter())

    if _is_production():
        try:
            from pythonjsonlogger.json import JsonFormatter
        except ImportError:  # pragma: no cover — fallback if dep missing
            from pythonjsonlogger.jsonlogger import JsonFormatter

        formatter = JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(request_id)s %(message)s",
            rename_fields={"asctime": "timestamp", "levelname": "level"},
        )
    else:
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s %(name)s [%(request_id)s] %(message)s"
        )

    handler.setFormatter(formatter)
    root.addHandler(handler)
