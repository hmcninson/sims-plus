"""
SIMS Plus - FastAPI Application Entry Point

School Information Management System for Ghana.
"""

import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import redis.asyncio as aioredis
import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.v1.router import api_router
from app.config import settings
from app.core.logging import configure_logging
from app.core.sentry import init_sentry
from app.db.session import async_session_maker
from app.middleware.logging import RequestLoggingMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.tenant import TenantMiddleware
from app.middleware.rate_limit import RateLimitMiddleware

# Initialize Sentry before app creation so it captures startup errors
init_sentry()

# Configure structured logging (structlog with JSON output)
configure_logging()

# Module-level structured logger for lifespan events
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager for startup/shutdown events."""
    # Startup
    logger.info("app_starting", app_name=settings.APP_NAME, version=settings.APP_VERSION)
    logger.info("app_environment", environment=settings.ENVIRONMENT)

    # Shared Redis client for health checks, tenant caching, etc.
    # decode_responses=True so callers get str instead of bytes from GET commands.
    app.state.redis = aioredis.from_url(str(settings.REDIS_URL), decode_responses=True)

    yield

    # Shutdown
    await app.state.redis.close()
    logger.info("app_shutting_down", app_name=settings.APP_NAME)


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="School Information Management System for Ghana - Multi-tenant SaaS",
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
    openapi_url="/openapi.json" if settings.is_development else None,
    lifespan=lifespan,
)

# =========================
# Middleware (order matters - last added runs first / outermost)
# =========================
# Execution order (outermost to innermost):
#   SecurityHeaders -> CORS -> RateLimit -> Tenant -> RequestLogging
#
# SecurityHeaders is added LAST so it wraps everything, ensuring
# security headers appear on ALL responses including CORS preflight.
# RequestLogging is added FIRST (innermost) to time the full lifecycle.

# 1. Request logging (added first = innermost, times everything)
app.add_middleware(RequestLoggingMiddleware)

# 1b. GZip compression (innermost, compresses all responses > 1KB)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 2. Tenant context (extracts subdomain and sets RLS context)
app.add_middleware(TenantMiddleware)

# 3. Rate limiting
app.add_middleware(RateLimitMiddleware)

# 4. CORS (must run before security headers so preflight responses get headers)
# Uses allow_origin_regex to support wildcard subdomains.
# Matches: http://presec.localhost:3000, https://presec.simsplus.io, etc.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,  # Explicit origins (localhost:3000, etc.)
    allow_origin_regex=r"https?://[a-z0-9][a-z0-9-]{2,}[a-z0-9]\.(simsplus\.io|localhost)(:\d+)?",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Subdomain",
        "X-Request-ID",
        "X-Active-School",
        "Accept",
        "Accept-Language",
        "Origin",
    ],
    expose_headers=[
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Reset",
        "X-Request-ID",
    ],
)

# 5. Security headers (added LAST = outermost, headers on ALL responses incl. preflight)
app.add_middleware(SecurityHeadersMiddleware)


# =========================
# Health Check
# =========================
@app.get("/health", tags=["Health"])
async def health_check(request: Request):
    """Health check endpoint.

    Returns structured status of all critical dependencies with latency
    measurements. Does NOT require tenant context or authentication.

    Status logic:
        - "healthy"   — all checks pass
        - "degraded"  — Redis is down but PostgreSQL is up (app works, just slower)
        - "unhealthy" — PostgreSQL is down

    Returns:
        200 for "healthy" or "degraded"
        503 for "unhealthy"
    """
    db_check = {"status": "down", "latency_ms": 0.0}
    redis_check = {"status": "down", "latency_ms": 0.0}
    migration_check = {"status": "unknown", "head": None}

    # --- PostgreSQL connectivity + migration revision in a single session ---
    try:
        async with async_session_maker() as session:
            # Database ping
            t0 = time.monotonic()
            result = await session.execute(text("SELECT 1"))
            result.scalar()
            db_check["latency_ms"] = round((time.monotonic() - t0) * 1000, 1)
            db_check["status"] = "up"

            # Alembic migration revision (reuse the same session to avoid extra checkout)
            try:
                row = (
                    await session.execute(
                        text("SELECT version_num FROM alembic_version LIMIT 1")
                    )
                ).fetchone()
                if row:
                    migration_check["head"] = row[0]
                    migration_check["status"] = "current"
                else:
                    migration_check["status"] = "no_revision"
            except Exception:
                # Table may not exist yet (fresh DB before first migration)
                migration_check["status"] = "unable_to_check"
    except Exception:
        # DB is completely unreachable
        logger.error("health_check_db_failed", exc_info=True)

    # --- Redis connectivity ---
    try:
        redis_client = getattr(request.app.state, "redis", None)
        if redis_client is not None:
            t0 = time.monotonic()
            await redis_client.ping()
            redis_check["latency_ms"] = round((time.monotonic() - t0) * 1000, 1)
            redis_check["status"] = "up"
        else:
            redis_check["status"] = "not_configured"
    except Exception:
        # Redis failure is non-fatal (app degrades gracefully)
        logger.warning("health_check_redis_failed", exc_info=True)

    # --- Determine overall status ---
    if db_check["status"] != "up":
        overall_status = "unhealthy"
    elif redis_check["status"] not in ("up", "not_configured"):
        overall_status = "degraded"
    else:
        overall_status = "healthy"

    # 200 for healthy/degraded, 503 for unhealthy
    status_code = 200 if overall_status != "unhealthy" else 503

    payload: dict = {
        "status": overall_status,
        "version": settings.APP_VERSION,
        "checks": {
            "database": db_check,
            "redis": redis_check,
            "migrations": migration_check,
        },
    }

    # Only expose environment and migration revision in development
    if settings.is_development:
        payload["environment"] = settings.ENVIRONMENT
    else:
        # Redact migration revision hash in production (info disclosure)
        payload["checks"]["migrations"].pop("head", None)

    return JSONResponse(content=payload, status_code=status_code)


@app.get("/", tags=["Root"])
async def root() -> dict[str, str]:
    """Root endpoint with API information."""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs" if settings.is_development else "disabled",
        "health": "/health",
        "api": "/api/v1",
    }


# =========================
# API Routes
# =========================
app.include_router(api_router, prefix="/api/v1")


# =========================
# Exception Handlers
# =========================
@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception) -> JSONResponse:
    """Global exception handler for unhandled errors."""
    logger.error(
        "unhandled_exception",
        exc_type=type(exc).__name__,
        exc_message=str(exc),
        exc_info=True,
    )

    # Include request_id so clients can reference it in support tickets
    request_id = request.headers.get("X-Request-ID", "")

    # Only expose exception details in development (staging may be accessible to QA/beta users)
    if settings.is_development:
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc), "request_id": request_id},
        )

    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "request_id": request_id},
    )
