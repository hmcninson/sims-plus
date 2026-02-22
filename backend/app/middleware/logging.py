"""
SIMS Plus - Request Logging Middleware

Logs every HTTP request with a unique request ID, method, path,
tenant subdomain, response status, and duration. The request ID
is also returned in the X-Request-ID response header for client-side
correlation.

This middleware is the innermost in the stack (added first in
FastAPI's add_middleware chain) so it wraps the route handler
directly. Tenant subdomain is available on request.state because
TenantMiddleware runs before this middleware sees the response.
"""

import time
import structlog
from uuid import uuid4
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger()

# Paths where successful requests are logged at debug level to reduce noise
_QUIET_PATHS = frozenset({"/health", "/"})


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Accept upstream X-Request-ID (e.g. from a load balancer) or generate one
        request_id = request.headers.get("X-Request-ID") or str(uuid4())

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        start_time = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            # Ensure a log entry is created even when the handler raises
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "request_failed",
                duration_ms=round(duration_ms, 2),
                exc_info=True,
            )
            raise

        duration_ms = (time.perf_counter() - start_time) * 1000

        # Read the resolved tenant subdomain set by TenantMiddleware
        # (which runs after this middleware in the inbound direction).
        # Falls back to X-Subdomain header if tenant middleware did not run.
        tenant_subdomain = (
            getattr(request.state, "tenant_subdomain", None)
            or request.headers.get("X-Subdomain", "none")
        )
        structlog.contextvars.bind_contextvars(tenant_subdomain=tenant_subdomain)

        log_kwargs = {
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 2),
        }

        # Downgrade health-check logs to debug level to reduce noise
        if request.url.path in _QUIET_PATHS:
            logger.debug("request_completed", **log_kwargs)
        else:
            logger.info("request_completed", **log_kwargs)

        response.headers["X-Request-ID"] = request_id
        return response
