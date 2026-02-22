"""
SIMS Plus - Structured Logging Configuration

Uses structlog for structured log entries. In production/staging, output
is JSON for machine parsing. In development, output uses a human-readable
console format for easier debugging.

Context variables (request_id, tenant_subdomain) are bound per-request
in the RequestLoggingMiddleware and automatically included in all log
entries within that request's scope.
"""

import logging

import structlog

from app.config import settings


def configure_logging():
    # Resolve the configured LOG_LEVEL (e.g. "DEBUG", "INFO") to a numeric level
    log_level = logging.getLevelName(settings.LOG_LEVEL)

    # Human-readable console output in development, JSON in production/staging
    if settings.is_development:
        renderer = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
