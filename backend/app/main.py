"""
SIMS Plus - FastAPI Application Entry Point

School Information Management System for Ghana.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.config import settings
from app.middleware.tenant import TenantMiddleware
from app.middleware.rate_limit import RateLimitMiddleware, close_redis_connection

# Configure logging
logger = logging.getLogger(__name__)

# Store rate limit middleware reference for cleanup
_rate_limit_middleware: RateLimitMiddleware | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager for startup/shutdown events."""
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")

    yield

    # Shutdown
    logger.info(f"Shutting down {settings.APP_NAME}")

    # Close Redis connection if rate limiting was enabled
    global _rate_limit_middleware
    if _rate_limit_middleware:
        await close_redis_connection(_rate_limit_middleware)


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
# Middleware (order matters - last added runs first)
# =========================

# CORS middleware (runs first - must allow preflight requests)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Subdomain",
        "X-Request-ID",
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

# Rate limiting middleware (runs second)
_rate_limit_middleware = RateLimitMiddleware(app)
app.add_middleware(RateLimitMiddleware)

# Tenant context middleware (runs last - extracts subdomain and sets RLS context)
app.add_middleware(TenantMiddleware)


# =========================
# Health Check
# =========================
@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    """Health check endpoint for load balancers and monitoring."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }


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
    # In production, don't expose error details
    if settings.is_production:
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
    )
