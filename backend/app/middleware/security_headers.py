"""
SIMS Plus - Security Headers Middleware

Adds standard HTTP security response headers to every response.

These headers provide defense-in-depth against common web attacks:
- XSS (Content-Security-Policy, X-XSS-Protection)
- Clickjacking (X-Frame-Options)
- MIME-type sniffing (X-Content-Type-Options)
- Referrer leakage (Referrer-Policy)
- Device API abuse (Permissions-Policy)
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


# Paths that serve HTML documentation (Swagger UI, ReDoc) and need a relaxed
# CSP so the browser can load their external JS/CSS/font assets.
_DOCS_PATHS = frozenset({"/docs", "/docs/oauth2-redirect", "/redoc", "/openapi.json"})

# CSP for API responses: no resources should ever be loaded by a browser
_API_CSP = "default-src 'none'; frame-ancestors 'none'"

# CSP for documentation pages: allows only the specific CDN origins that
# Swagger UI and ReDoc require. 'unsafe-inline' covers the small init
# <script> block and <style> block that FastAPI embeds in the HTML.
_DOCS_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
    "font-src https://fonts.gstatic.com; "
    "img-src 'self' https://fastapi.tiangolo.com data:; "
    "connect-src 'self'; "
    "worker-src blob:; "
    "frame-ancestors 'none'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware that sets HTTP security headers on every response.

    Added outermost in the middleware stack so that security headers
    are present on ALL responses, including CORS preflight.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # HSTS is set by Nginx in production — not duplicated here

        # Prevent browsers from MIME-sniffing the response away from the declared Content-Type
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Block all framing to prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # Legacy XSS filter for older browsers (modern browsers use CSP instead)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Use a permissive CSP for documentation pages so Swagger UI and ReDoc
        # can load their JS/CSS from cdn.jsdelivr.net and fonts from Google.
        # All other routes get the strict API-only CSP (default-src 'none').
        if request.url.path in _DOCS_PATHS:
            response.headers["Content-Security-Policy"] = _DOCS_CSP
        else:
            response.headers["Content-Security-Policy"] = _API_CSP

        # Only send the origin on cross-origin requests; full URL on same-origin
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Deny access to sensitive browser APIs this backend never needs
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )

        return response
