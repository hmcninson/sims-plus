"""
Centralized cache key generation.

ALL Redis keys in SIMS Plus go through this module.
This prevents key collisions and makes it easy to audit all Redis usage.

Key naming convention:
    {namespace}:{identifier}:{sub-identifier}

Tenant-scoped keys MUST include the tenant_id to prevent cross-tenant
cache pollution.
"""


class CacheKeys:
    """Redis cache key generator."""

    # TTL constants (seconds)
    TENANT_LOOKUP_TTL = 600       # 10 minutes
    USER_SESSION_TTL = 900        # 15 minutes
    STUDENT_COUNT_TTL = 300       # 5 minutes
    RATE_LIMIT_TTL = 60           # 1 minute
    ACTIVE_YEAR_TTL = 3600        # 1 hour
    PERMISSIONS_TTL = 300         # 5 minutes
    GRADING_SCALE_TTL = 3600      # 1 hour
    DASHBOARD_STATS_TTL = 60      # 1 minute

    @staticmethod
    def tenant_by_subdomain(subdomain: str) -> str:
        """Key for cached tenant lookup by subdomain."""
        return f"tenant:subdomain:{subdomain.lower()}"

    @staticmethod
    def school(tenant_id: str, school_id: str) -> str:
        """Key for cached school data."""
        return f"tenant:{tenant_id}:school:{school_id}"

    @staticmethod
    def user(tenant_id: str, user_id: str) -> str:
        """Key for cached user data."""
        return f"tenant:{tenant_id}:user:{user_id}"

    @staticmethod
    def student_count(tenant_id: str) -> str:
        """Key for cached student count (for limit enforcement)."""
        return f"tenant:{tenant_id}:students:count"

    @staticmethod
    def rate_limit(limit_type: str, identifier: str) -> str:
        """Key for rate limiting."""
        return f"rate_limit:{limit_type}:{identifier}"

    @staticmethod
    def token_blacklist(token_hash: str) -> str:
        """Key for blacklisted JWT token."""
        return f"token_blacklist:{token_hash}"

    @staticmethod
    def user_token_blacklist(user_id: str) -> str:
        """Key for user-level token revocation timestamp."""
        return f"user_token_blacklist:{user_id}"

    @staticmethod
    def active_academic_year(tenant_id: str) -> str:
        """Key for cached active academic year."""
        return f"tenant:{tenant_id}:academic_year:active"

    @staticmethod
    def user_permissions(tenant_id: str, user_id: str) -> str:
        """Key for cached user permissions."""
        return f"tenant:{tenant_id}:user:{user_id}:permissions"

    @staticmethod
    def grading_scale(tenant_id: str) -> str:
        """Key for cached default grading scale."""
        return f"tenant:{tenant_id}:grading_scale:default"

    @staticmethod
    def dashboard_stats(tenant_id: str) -> str:
        """Key for cached dashboard overview stats."""
        return f"tenant:{tenant_id}:dashboard:stats"

