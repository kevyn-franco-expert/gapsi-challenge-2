"""Structured JSON logging configuration shared across services."""
from __future__ import annotations
import logging
import sys
from typing import Optional

import structlog


def _add_service_name(logger, method_name: str, event_dict: dict) -> dict:
    """Inject service name from environment if not already present."""
    from shared.config import get_settings

    settings = get_settings()
    event_dict.setdefault("service", settings.service_name)
    event_dict.setdefault("environment", settings.environment)
    return event_dict


def configure_logging(log_level: Optional[str] = None, service_name: Optional[str] = None) -> None:
    """Configure structlog to emit JSON logs with timestamp, level and trace_id."""
    from shared.config import get_settings

    settings = get_settings()
    level = (log_level or settings.log_level).upper()

    # Keep stdlib logging aligned so third-party libs are also formatted.
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level, logging.INFO),
    )

    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _add_service_name,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # In local/dev with a TTY keep human-readable logs; otherwise JSON.
    if sys.stdout.isatty():
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level, logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    if service_name:
        structlog.contextvars.bind_contextvars(service=service_name)


def get_logger(name: Optional[str] = None):
    """Return a structlog logger with optional name binding."""
    logger = structlog.get_logger(name)
    return logger
