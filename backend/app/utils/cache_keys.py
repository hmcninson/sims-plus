"""
Centralized cache key generation.

ALL Redis keys in SIMS Plus go through this module.
This prevents key collisions and makes it easy to audit all Redis usage.

Key naming convention:
    {namespace}:{identifier}:{sub-identifier}

Tenant-scoped keys MUST include the tenant_id to prevent cross-tenant
cache pollution.

School-scoped keys MUST include the school_id to prevent cross-school
cache pollution within chain tenants (1 tenant = N schools).
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
    CHAIN_ACCESSIBLE_TTL = 300    # 5 minutes

    # --- Tenant-wide keys (no school scoping needed) ---

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
    def user_permissions(tenant_id: str, user_id: str) -> str:
        """Key for cached user permissions (tenant-wide, not school-specific)."""
        return f"tenant:{tenant_id}:user:{user_id}:permissions"

    @staticmethod
    def chain_accessible_schools(tenant_id: str, user_id: str) -> str:
        """Key for cached accessible schools list (school switcher dropdown)."""
        return f"chain:accessible:{tenant_id}:{user_id}"

    # --- School-scoped keys ---
    #
    # Chain tenants (1 tenant = N schools) share a single tenant_id.
    # Without school_id in the key, switching from School A to School B
    # serves stale cached data from School A.
    #
    # For backward compatibility with single-school tenants, school_id
    # defaults to "all" so existing callers that don't pass it still get
    # a deterministic key (and it naturally separates from school-specific
    # keys since no real UUID equals "all").

    @staticmethod
    def student_count(tenant_id: str, school_id: str | None = None) -> str:
        """Key for cached student count (for limit enforcement).

        School-scoped: chain tenants track student counts per school.
        """
        scope = school_id or "all"
        return f"tenant:{tenant_id}:school:{scope}:students:count"

    @staticmethod
    def active_academic_year(tenant_id: str, school_id: str | None = None) -> str:
        """Key for cached active academic year.

        School-scoped: each school in a chain can have its own academic year.
        """
        scope = school_id or "all"
        return f"tenant:{tenant_id}:school:{scope}:academic_year:active"

    @staticmethod
    def grading_scale(tenant_id: str, school_id: str | None = None) -> str:
        """Key for cached default grading scale.

        School-scoped: each school in a chain can have its own grading scale.
        """
        scope = school_id or "all"
        return f"tenant:{tenant_id}:school:{scope}:grading_scale:default"

    @staticmethod
    def dashboard_stats(tenant_id: str, school_id: str | None = None) -> str:
        """Key for cached dashboard overview stats.

        School-scoped: dashboard stats are per-school (student counts,
        attendance, finance). Without school_id, chain admins switching
        schools would see stale data from the previous school.
        """
        scope = school_id or "all"
        return f"tenant:{tenant_id}:school:{scope}:dashboard:stats"

    # --- Invalidation helpers ---

    @staticmethod
    def school_cache_pattern(tenant_id: str, school_id: str) -> str:
        """Glob pattern to invalidate ALL cached data for a specific school.

        Use with CacheService.invalidate() when school-wide data changes
        (e.g., school settings update, bulk operations).

        TODO: Wire into school settings update and bulk operations endpoints.
        """
        return f"tenant:{tenant_id}:school:{school_id}:*"

    @staticmethod
    def tenant_school_cache_pattern(tenant_id: str) -> str:
        """Glob pattern to invalidate ALL school-scoped data for a tenant.

        Use with CacheService.invalidate() when tenant-wide changes affect
        all schools (e.g., subscription tier change, tenant deactivation).

        TODO: Wire into tenant-wide operations (e.g., academic year changes).
        """
        return f"tenant:{tenant_id}:school:*"
