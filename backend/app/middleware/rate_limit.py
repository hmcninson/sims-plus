"""
SIMS Plus - Rate Limiting Middleware

Implements Redis-based rate limiting for API endpoints.
"""

import time
from typing import Callable, Optional, Tuple

import redis.asyncio as redis
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware using Redis sliding window algorithm.

    Different rate limits are applied based on endpoint type:
    - Auth endpoints (/auth/login, /auth/register): Strict limits
    - Subdomain check (/tenant/check-subdomain): Moderate limits
    - General API: Default limits
    """

    # Endpoint patterns and their rate limit configurations
    ENDPOINT_LIMITS = {
        "/api/v1/auth/login": ("auth", "auth"),
        "/api/v1/auth/refresh": ("auth", "auth"),
        "/api/v1/onboarding/register": ("auth", "register"),
        "/api/v1/onboarding/resend-verification": ("auth", "onboarding_resend"),
        "/api/v1/tenant/check-subdomain": ("subdomain", "subdomain"),
        "/api/v1/tenant/validate": ("subdomain", "subdomain"),
        "/api/v1/onboarding/suggest-subdomain": ("subdomain", "subdomain"),
        "/api/v1/tenant/search": ("search", "search"),
        # OTP and MFA endpoints — auth-tier limits to prevent brute-force
        "/api/v1/auth/forgot-password-sms": ("auth", "auth"),
        "/api/v1/auth/reset-password-sms": ("auth", "auth"),
        "/api/v1/auth/mfa/verify": ("auth", "auth"),
        "/api/v1/auth/send-phone-otp": ("auth", "auth"),
        "/api/v1/auth/verify-phone": ("auth", "auth"),
        # Admissions — strict limits on public application submission
        "/api/v1/admissions/public/applications": ("admissions_submit", "admissions_submit"),
        # Applicant account rate limits — separate from general auth limits
        "/api/v1/admissions/public/applicant/register": ("applicant_register", "applicant_register"),
        "/api/v1/admissions/public/applicant/login": ("auth", "auth"),
        "/api/v1/admissions/public/applicant/forgot-password": ("applicant_register", "applicant_register"),
        "/api/v1/admissions/public/applicant/reset-password": ("applicant_register", "applicant_register"),
        "/api/v1/admissions/public/applicant/verify-email": ("applicant_register", "applicant_register"),
        "/api/v1/admissions/public/applicant/resend-verification": ("applicant_resend", "applicant_resend"),
        # Subscription — strict limits on payment initiation (M3)
        "/api/v1/subscription/upgrade": ("subscription", "subscription"),
        "/api/v1/subscription/addon": ("subscription", "subscription"),
        "/api/v1/subscription/calculate-cost": ("subscription", "subscription"),
        # M4: Webhook rate-limited to auth tier — signature verification is
        # expensive (HMAC-SHA512), so cap invalid request volume
        "/api/v1/subscription/webhook/paystack": ("auth", "subscription_webhook"),
        # Platform admin endpoints
        "/api/v1/platform/login": ("auth", "auth"),
        "/api/v1/platform/refresh": ("auth", "auth"),
        "/api/v1/platform/mfa/verify": ("auth", "auth"),
        "/api/v1/platform/mfa/setup": ("auth", "auth"),
        "/api/v1/platform/mfa/generate": ("auth", "auth"),  # Prevent brute-force secret generation
        # Impersonation: bulk tier (10/min). A compromised admin at higher rates
        # could impersonate many tenants quickly. Audit log alerts can trigger.
        "/api/v1/platform/impersonate": ("bulk", "bulk"),
        "/api/v1/platform/tenants": ("default", "default"),
        "/api/v1/platform/analytics": ("bulk", "bulk"),
    }

    # Endpoints that should be excluded from rate limiting.
    # /auth/me is excluded because it is called on every page load by the
    # frontend dashboard layout for session validation. Including it in the
    # general rate limit bucket causes false 429 responses during normal
    # navigation, which the frontend misinterprets as a session expiry.
    EXCLUDED_ENDPOINTS = {
        "/health",
        "/status",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/api/v1/auth/me",
    }

    def __init__(self, app, redis_client: Optional[redis.Redis] = None):
        super().__init__(app)
        self.redis_client = redis_client
        self._redis_connected = False

    async def _get_redis(self) -> Optional[redis.Redis]:
        """Get or create Redis connection."""
        if self.redis_client is None:
            try:
                self.redis_client = redis.from_url(
                    str(settings.REDIS_URL),
                    encoding="utf-8",
                    decode_responses=True,
                )
                # Test connection
                await self.redis_client.ping()
                self._redis_connected = True
            except Exception:
                # Redis not available - rate limiting disabled
                self._redis_connected = False
                return None
        return self.redis_client

    def _get_client_identifier(self, request: Request) -> str:
        """
        Get unique client identifier for rate limiting.

        Priority:
        1. Authenticated user ID (from token)
        2. Tenant ID + IP (for tenant-scoped requests)
        3. IP address only (for public endpoints)
        """
        # Try to get user ID from request state (set by auth)
        user_id = getattr(request.state, "user_id", None)
        if user_id:
            return f"user:{user_id}"

        # Get IP address
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else "unknown"

        # Try to get tenant context
        tenant_id = getattr(request.state, "tenant_id", None)
        if tenant_id:
            return f"tenant:{tenant_id}:ip:{ip}"

        return f"ip:{ip}"

    def _get_rate_limit_config(self, path: str) -> Tuple[int, int, str]:
        """
        Get rate limit configuration for a path.

        Returns: (max_requests, window_seconds, limit_type)
        """
        # Check for exact match first
        if path in self.ENDPOINT_LIMITS:
            limit_type, key_prefix = self.ENDPOINT_LIMITS[path]
            if limit_type == "auth":
                return (
                    settings.RATE_LIMIT_AUTH_REQUESTS,
                    settings.RATE_LIMIT_AUTH_WINDOW,
                    key_prefix,
                )
            elif limit_type == "subdomain":
                return (
                    settings.RATE_LIMIT_SUBDOMAIN_CHECK_REQUESTS,
                    settings.RATE_LIMIT_SUBDOMAIN_CHECK_WINDOW,
                    key_prefix,
                )
            elif limit_type == "search":
                return (
                    settings.RATE_LIMIT_SEARCH_REQUESTS,
                    settings.RATE_LIMIT_SEARCH_WINDOW,
                    key_prefix,
                )
            elif limit_type == "admissions_submit":
                return (
                    settings.RATE_LIMIT_ADMISSIONS_SUBMIT_REQUESTS,
                    settings.RATE_LIMIT_ADMISSIONS_SUBMIT_WINDOW,
                    key_prefix,
                )
            elif limit_type == "applicant_register":
                return (
                    settings.RATE_LIMIT_APPLICANT_REGISTER_REQUESTS,
                    settings.RATE_LIMIT_APPLICANT_REGISTER_WINDOW,
                    key_prefix,
                )
            elif limit_type == "applicant_resend":
                return (
                    settings.RATE_LIMIT_APPLICANT_RESEND_REQUESTS,
                    settings.RATE_LIMIT_APPLICANT_RESEND_WINDOW,
                    key_prefix,
                )
            elif limit_type == "subscription":
                return (
                    settings.RATE_LIMIT_SUBSCRIPTION_REQUESTS,
                    settings.RATE_LIMIT_SUBSCRIPTION_WINDOW,
                    key_prefix,
                )
            elif limit_type == "bulk":
                return (
                    settings.RATE_LIMIT_BULK_REQUESTS,
                    settings.RATE_LIMIT_BULK_WINDOW,
                    key_prefix,
                )

        # Check for prefix matches
        for endpoint, (limit_type, key_prefix) in self.ENDPOINT_LIMITS.items():
            if path.startswith(endpoint):
                if limit_type == "auth":
                    return (
                        settings.RATE_LIMIT_AUTH_REQUESTS,
                        settings.RATE_LIMIT_AUTH_WINDOW,
                        key_prefix,
                    )
                elif limit_type == "subdomain":
                    return (
                        settings.RATE_LIMIT_SUBDOMAIN_CHECK_REQUESTS,
                        settings.RATE_LIMIT_SUBDOMAIN_CHECK_WINDOW,
                        key_prefix,
                    )
                elif limit_type == "search":
                    return (
                        settings.RATE_LIMIT_SEARCH_REQUESTS,
                        settings.RATE_LIMIT_SEARCH_WINDOW,
                        key_prefix,
                    )
                elif limit_type == "admissions_submit":
                    return (
                        settings.RATE_LIMIT_ADMISSIONS_SUBMIT_REQUESTS,
                        settings.RATE_LIMIT_ADMISSIONS_SUBMIT_WINDOW,
                        key_prefix,
                    )
                elif limit_type == "applicant_register":
                    return (
                        settings.RATE_LIMIT_APPLICANT_REGISTER_REQUESTS,
                        settings.RATE_LIMIT_APPLICANT_REGISTER_WINDOW,
                        key_prefix,
                    )
                elif limit_type == "applicant_resend":
                    return (
                        settings.RATE_LIMIT_APPLICANT_RESEND_REQUESTS,
                        settings.RATE_LIMIT_APPLICANT_RESEND_WINDOW,
                        key_prefix,
                    )
                elif limit_type == "subscription":
                    return (
                        settings.RATE_LIMIT_SUBSCRIPTION_REQUESTS,
                        settings.RATE_LIMIT_SUBSCRIPTION_WINDOW,
                        key_prefix,
                    )
                elif limit_type == "bulk":
                    return (
                        settings.RATE_LIMIT_BULK_REQUESTS,
                        settings.RATE_LIMIT_BULK_WINDOW,
                        key_prefix,
                    )

        # Default rate limit
        return (
            settings.RATE_LIMIT_DEFAULT_REQUESTS,
            settings.RATE_LIMIT_DEFAULT_WINDOW,
            "default",
        )

    async def _check_rate_limit(
        self,
        redis_client: redis.Redis,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> Tuple[bool, int, int]:
        """
        Check if request is within rate limit using sliding window.

        Returns: (allowed, remaining, reset_time)
        """
        now = time.time()
        window_start = now - window_seconds

        # Use a Redis pipeline for atomic operations
        pipe = redis_client.pipeline()

        # Remove old entries outside the window
        pipe.zremrangebyscore(key, 0, window_start)

        # Count current requests in window
        pipe.zcard(key)

        # Add current request
        pipe.zadd(key, {str(now): now})

        # Set expiry on the key
        pipe.expire(key, window_seconds + 1)

        results = await pipe.execute()
        current_count = results[1]

        if current_count >= max_requests:
            # Rate limit exceeded
            # Get oldest entry to calculate reset time
            oldest = await redis_client.zrange(key, 0, 0, withscores=True)
            if oldest:
                reset_time = int(oldest[0][1] + window_seconds - now)
            else:
                reset_time = window_seconds
            return False, 0, reset_time

        remaining = max_requests - current_count - 1
        return True, remaining, window_seconds

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        """Process request with rate limiting."""
        # Skip if rate limiting is disabled
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)

        # Skip excluded endpoints
        path = request.url.path
        if path in self.EXCLUDED_ENDPOINTS:
            return await call_next(request)

        # Skip non-API endpoints
        if not path.startswith("/api/"):
            return await call_next(request)

        # Get Redis connection
        redis_client = await self._get_redis()
        if redis_client is None:
            # Redis unavailable - allow request but log warning
            return await call_next(request)

        # Get rate limit configuration
        max_requests, window_seconds, limit_type = self._get_rate_limit_config(path)

        # Build rate limit key
        client_id = self._get_client_identifier(request)
        rate_key = f"rate_limit:{limit_type}:{client_id}"

        try:
            allowed, remaining, reset_time = await self._check_rate_limit(
                redis_client, rate_key, max_requests, window_seconds
            )
        except Exception:
            # Redis error - allow request
            return await call_next(request)

        if not allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Rate limit exceeded. Please try again later.",
                    "retry_after": reset_time,
                },
                headers={
                    "Retry-After": str(reset_time),
                    "X-RateLimit-Limit": str(max_requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time()) + reset_time),
                },
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers to response
        response.headers["X-RateLimit-Limit"] = str(max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(
            int(time.time()) + window_seconds
        )

        return response


async def close_redis_connection(middleware: RateLimitMiddleware) -> None:
    """Close Redis connection on shutdown."""
    if middleware.redis_client:
        await middleware.redis_client.close()
