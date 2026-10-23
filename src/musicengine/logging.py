"""structlog JSON logging: every line has timestamp, level, event, job_id, correlation_id."""
import logging
import sys

import structlog


def _ensure_ids(_, __, event_dict):
    event_dict.setdefault("job_id", None)
    event_dict.setdefault("correlation_id", None)
    return event_dict


def configure(level: str = "INFO") -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level.upper())
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _ensure_ids,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level.upper())),
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=False,
    )


def get_logger(name: str = "musicengine"):
    return structlog.get_logger(name)
