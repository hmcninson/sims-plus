# Sprint 1-2: Core Infrastructure -- Technical Architecture

**Document Version:** 1.0
**Date:** 2026-02-15
**Author:** Solution Architect
**Status:** Implementation-Ready

---

## Table of Contents

1. [Overview](#1-overview)
2. [System Architecture](#2-system-architecture)
3. [Backend Architecture](#3-backend-architecture)
4. [Database Architecture](#4-database-architecture)
5. [Authentication System Design](#5-authentication-system-design)
6. [Multi-Tenant Request Lifecycle](#6-multi-tenant-request-lifecycle)
7. [Onboarding Flow](#7-onboarding-flow)
8. [Frontend Architecture](#8-frontend-architecture)
9. [Docker and Dev Environment](#9-docker-and-dev-environment)
10. [API Contracts](#10-api-contracts)
11. [Module Boundaries](#11-module-boundaries)
12. [Critical Design Decisions](#12-critical-design-decisions)
13. [Component Breakdown with Parallel Tracks](#13-component-breakdown-with-parallel-tracks)

---

## 1. Overview

### What We Are Building

Sprint 1-2 establishes the foundational infrastructure for SIMS Plus -- a multi-tenant SaaS school management system. Every subsequent sprint builds on top of these decisions. The goal is to deliver:

- A running FastAPI backend with PostgreSQL RLS-based multi-tenancy
- A running Next.js 16 frontend with subdomain-based tenant routing
- A Docker-based local development environment
- Core tables (tenants, reserved_subdomains, schools, users) with RLS policies
- JWT authentication with tenant isolation
- School onboarding (registration) flow
- CI/CD pipeline skeleton

### Guiding Constraints

1. **One database, one cluster, many tenants.** Data isolation is enforced at the PostgreSQL level through Row-Level Security, not through separate databases.
2. **Subdomain routing is the tenant identifier.** `presec.simsplus.io` maps to tenant `presec`. Every request must resolve a tenant before any data access occurs.
3. **No client-side API calls from Next.js.** All data fetching happens through Server Actions (`*.action.ts` files) that call the backend API server-side.
4. **Security by default.** Rate limiting, Argon2id password hashing, token blacklisting, audit logging, and account lockout are all part of Sprint 1-2, not "added later."

### Sprint Scope

| Sprint | Scope | Deliverables |
|--------|-------|-------------|
| **Sprint 1** | Project scaffolding, Docker, database, CI/CD, DNS | Running dev environment, PostgreSQL + Redis, FastAPI app shell, Next.js app shell, Cloudflare wildcard DNS, Nginx config |
| **Sprint 2** | Core tables, RLS, tenant middleware, auth, onboarding, frontend auth flow | tenants/users/schools tables, RLS policies, `set_tenant_context()`, JWT auth, login/register UI, subdomain middleware |

---

## 2. System Architecture

### High-Level Component Diagram

```
                            Internet
                               |
                               v
                    +-----------------------+
                    |   Cloudflare          |
                    |   - DNS (*.simsplus.io)|
                    |   - SSL Termination   |
                    |   - DDoS Protection   |
                    |   - WAF Rules         |
                    +-----------+-----------+
                                |
                                v
                    +-----------------------+
                    |   Load Balancer       |
                    |   (ALB / Nginx)       |
                    +-----------+-----------+
                                |
                    +-----------+-----------+
                    |                       |
                    v                       v
         +------------------+    +------------------+
         |  Next.js Pods    |    |  FastAPI Pods    |
         |  (Frontend)      |    |  (Backend API)   |
         |                  |    |                  |
         |  proxy.ts:       |    |  Middleware:      |
         |  - Subdomain     |    |  1. Tenant       |
         |    extraction    |    |  2. RateLimit    |
         |  - Cookie set    |    |  3. CORS         |
         |                  |    |                  |
         |  Server Actions: |    |  Endpoints:      |
         |  - auth.action   |--->|  /api/v1/auth    |
         |  - school.action |    |  /api/v1/tenant  |
         |                  |    |  /api/v1/onboard |
         +------------------+    +---------+--------+
                                           |
                              +------------+------------+
                              |                         |
                              v                         v
                   +------------------+      +------------------+
                   |  PostgreSQL 16   |      |  Redis 7         |
                   |                  |      |                  |
                   |  Tables:         |      |  - Rate limits   |
                   |  - tenants       |      |  - Token blackl. |
                   |  - users         |      |  - Session cache |
                   |  - schools       |      |  - Audit events  |
                   |  - reserved_sub. |      |                  |
                   |                  |      +------------------+
                   |  RLS Policies:   |
                   |  - tenant_id     |      +------------------+
                   |    filtering     |      |  AWS S3          |
                   +------------------+      |  (File Storage)  |
                                             |  - Logos         |
                                             |  - Documents     |
                                             +------------------+
```

### Data Flow: Typical Authenticated Request

```
1. Browser: GET https://presec.simsplus.io/dashboard
       |
2. Cloudflare: DNS resolves *.simsplus.io -> ALB IP, terminates SSL
       |
3. ALB: Routes to Next.js pod (port 3000)
       |
4. Next.js proxy.ts:
       - Extracts "presec" from hostname
       - Sets x-subdomain header + cookie
       - Passes request to page
       |
5. Next.js Server Component:
       - Reads access_token from HttpOnly cookie
       - Calls Server Action (e.g., getDashboardData)
       |
6. Server Action:
       - Calls FastAPI: GET /api/v1/dashboard
       - Includes: Authorization: Bearer <token>
       - Includes: X-Subdomain: presec
       |
7. FastAPI Middleware Stack (execution order):
       a. TenantMiddleware:
          - Reads X-Subdomain header -> "presec"
          - Queries: SELECT id, subdomain, name, is_active
            FROM tenants WHERE subdomain = 'presec'
          - Validates tenant is active
          - Stores tenant_id in request.state
       b. RateLimitMiddleware:
          - Checks Redis: rate_limit:default:tenant:<id>:ip:<ip>
          - Allows or returns 429
       c. CORSMiddleware:
          - Validates Origin header
       |
8. FastAPI Endpoint:
       - get_db() dependency:
         - Creates AsyncSession
         - Calls: SELECT set_tenant_context('<tenant-uuid>')
         - Now PostgreSQL RLS is armed for this session
       - get_current_user_id() dependency:
         - Decodes JWT, validates signature + expiry
         - Checks token blacklist in Redis
         - Returns user_id
       - validate_token_tenant() dependency:
         - Compares JWT tenant_id with request.state.tenant_id
         - Rejects if mismatch (cross-tenant attack prevention)
       |
9. Service Layer:
       - Queries include explicit: .filter(Model.tenant_id == tenant_id)
       - PostgreSQL RLS enforces: WHERE tenant_id = get_current_tenant_id()
       - Double barrier: application filter + database RLS
       |
10. Response flows back through middleware -> Next.js -> Browser
```

### Network Topology (Production)

```
                    Cloudflare Edge
                    *.simsplus.io
                         |
                    +----+----+
                    |   ALB   |
                    +----+----+
                         |
              +----------+----------+
              |                     |
         +----+----+          +----+----+
         | Target  |          | Target  |
         | Group 1 |          | Group 2 |
         | :3000   |          | :8000   |
         +----+----+          +----+----+
              |                     |
     +--------+--------+    +------+------+
     |  Next.js Pod 1  |    | FastAPI Pod1|
     |  Next.js Pod 2  |    | FastAPI Pod2|
     |  Next.js Pod 3  |    | FastAPI Pod3|
     +-----------------+    +------+------+
                                   |
                          +--------+--------+
                          |                 |
                     +----+----+      +----+----+
                     | RDS     |      | Elasti- |
                     | PG 16   |      | Cache   |
                     | Multi-AZ|      | Redis 7 |
                     +---------+      +---------+
```

---

## 3. Backend Architecture

### Application Structure

The existing codebase at `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/` is already organized correctly:

```
backend/
  app/
    __init__.py
    main.py                        # FastAPI creation, middleware, lifespan
    config.py                      # Pydantic Settings (env-driven)
    api/
      deps.py                      # Shared dependencies (get_db, auth, tenant)
      v1/
        router.py                  # APIRouter aggregating all modules
        endpoints/
          auth.py                  # Login, refresh, logout, me, password flows
          tenant.py                # Subdomain validation, public tenant info
          onboarding.py            # School registration, subdomain suggestions
          schools.py               # School profile CRUD
          users.py                 # User CRUD within tenant
          media.py                 # File upload to S3
    core/
      security.py                  # Argon2id, JWT create/decode
      exceptions.py                # Custom exception classes
    db/
      session.py                   # AsyncEngine, async_session_maker
    models/
      base.py                      # Base, TenantMixin, SoftDeleteMixin, AuditMixin
      tenant.py                    # Tenant (NO tenant_id -- root entity)
      user.py                      # User (HAS tenant_id)
      school.py                    # School (HAS tenant_id)
      reserved_subdomain.py        # ReservedSubdomain (NO tenant_id -- global)
    schemas/
      auth.py                      # LoginRequest, LoginResponse, etc.
      tenant.py                    # TenantResponse, SubdomainCheckResponse
      onboarding.py                # Registration request/response
      school.py                    # SchoolResponse, SchoolUpdate
      user.py                      # UserCreate, UserResponse, UserUpdate
    services/
      auth.py                      # AuthService (login, register, refresh)
      tenant.py                    # TenantService (subdomain validation)
      onboarding.py                # OnboardingService (register_school)
      audit.py                     # AuditService (security event logging)
      token_blacklist.py           # TokenBlacklistService (Redis)
      password_reset.py            # PasswordResetService
      email_verification.py        # EmailVerificationService
      email.py                     # EmailService (SMTP)
      s3.py                        # S3Service (file upload/download)
    middleware/
      tenant.py                    # TenantMiddleware
      rate_limit.py                # RateLimitMiddleware (Redis sliding window)
    utils/
      sanitize.py                  # escape_ilike(), input sanitization
    templates/
      email/                       # HTML email templates
```

### Middleware Stack

As implemented in `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/main.py`, the middleware execution order is critical. FastAPI applies middleware in **reverse registration order** (last added runs first):

```python
# main.py lines 60-88 -- Applied in reverse order

# 3. CORS (runs FIRST -- must handle OPTIONS preflight before any auth check)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Subdomain",
                   "X-Request-ID", "Accept", "Accept-Language", "Origin"],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining",
                    "X-RateLimit-Reset", "X-Request-ID"],
)

# 2. Rate Limiting (runs SECOND -- check limits before expensive DB lookups)
app.add_middleware(RateLimitMiddleware)

# 1. Tenant Context (runs THIRD -- sets tenant before endpoint logic)
app.add_middleware(TenantMiddleware)
```

**Why this order matters:**
- CORS must run first to return proper headers on OPTIONS preflight requests. If Tenant runs first, it would reject OPTIONS requests that have no subdomain header.
- Rate limiting runs before tenant resolution so we rate-limit by IP even for invalid subdomains, preventing brute-force subdomain scanning.
- Tenant context runs last (closest to the endpoint), so by the time the endpoint executes, `request.state.tenant_id` is populated.

### Dependency Injection Pattern

The existing `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/api/deps.py` establishes the core dependency chain:

```python
# 1. Database session with RLS context
async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Creates AsyncSession, arms PostgreSQL RLS via set_tenant_context().
       Commits on success, rolls back on exception, clears context in finally."""

DatabaseSession = Annotated[AsyncSession, Depends(get_db)]

# 2. Current user from JWT
async def get_current_user_id(token: ...) -> str:
    """Decodes JWT, checks blacklist, returns user_id."""

CurrentUserId = Annotated[str, Depends(get_current_user_id)]

# 3. Tenant from request state (set by middleware)
async def get_tenant_from_request(request: Request) -> TenantContext:
    """Returns TenantContext from request.state."""

RequestTenant = Annotated[TenantContext, Depends(get_tenant_from_request)]

# 4. Cross-tenant validation (CRITICAL SECURITY)
async def validate_token_tenant(request: Request, token: ...) -> None:
    """Compares JWT tenant_id with request.state.tenant_id. Rejects mismatch."""

ValidatedTokenTenant = Annotated[None, Depends(validate_token_tenant)]

# 5. Full user validation (recommended for most endpoints)
async def get_validated_current_user(request: Request, token: ...) -> dict:
    """JWT validation + blacklist check + cross-tenant check in one dependency."""

ValidatedUser = Annotated[dict, Depends(get_validated_current_user)]

# 6. Permission check factory
def require_permissions(*required_permissions: str):
    """Returns a dependency that validates user has required permissions."""
```

**Usage in endpoints:**

```python
@router.get("/students")
async def list_students(
    db: DatabaseSession,                   # Auto-sets RLS context
    user: ValidatedUser,                   # JWT + blacklist + cross-tenant
    _: Annotated[None, Depends(require_permissions("students.read"))],
) -> list[StudentResponse]:
    service = StudentService(db)
    return await service.list_students(tenant_id=user["tenant_id"])
```

### Service Layer Pattern

As established across all existing services in the codebase:

```python
class ExampleService:
    """Service for example operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_thing(self, tenant_id: UUID, **kwargs) -> Thing:
        """
        Rules:
        1. Use flush()/refresh() NOT commit() -- get_db() handles commit
        2. Always filter by tenant_id explicitly (defense-in-depth)
        3. Raise custom errors (ExampleError), not HTTPException
        4. Use selectinload()/joinedload() for relationships (lazy="raise")
        """
        thing = Thing(tenant_id=tenant_id, **kwargs)
        self.db.add(thing)
        await self.db.flush()
        await self.db.refresh(thing)
        return thing

    async def get_thing(self, thing_id: UUID, tenant_id: UUID) -> Thing | None:
        result = await self.db.execute(
            select(Thing).where(
                Thing.id == thing_id,
                Thing.tenant_id == tenant_id,      # Defense-in-depth
                Thing.deleted_at.is_(None),         # Soft delete filter
            )
        )
        return result.scalar_one_or_none()


class ExampleError(Exception):
    def __init__(self, message: str, code: str = "example_error"):
        self.message = message
        self.code = code
        super().__init__(message)
```

### Error Handling Strategy

```
Layer           | Error Type                | HTTP Response
----------------|---------------------------|---------------------------
Pydantic        | ValidationError           | 422 (auto by FastAPI)
Endpoint        | HTTPException             | Specified status code
Service         | Custom Error classes      | Caught in endpoint, mapped to HTTP
Database        | IntegrityError            | Caught in get_db(), rollback
Global          | Exception (unhandled)     | 500 (sanitized in production)
```

The global exception handler in `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/main.py` (lines 126-139) suppresses error details in production.

---

## 4. Database Architecture

### Core Tables

Four tables in Sprint 1-2, split into two categories:

**Global tables (NO tenant_id, NO RLS):**
- `tenants` -- The root multi-tenant entity
- `reserved_subdomains` -- Protected subdomain list

**Tenant-scoped tables (HAS tenant_id, HAS RLS):**
- `users` -- All system users, isolated by tenant
- `schools` -- Schools within a tenant, isolated by tenant

### Complete CREATE TABLE SQL

#### tenants

```sql
CREATE TABLE tenants (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    name                VARCHAR(255)    NOT NULL,
    subdomain           VARCHAR(63)     NOT NULL UNIQUE,
    slug                VARCHAR(100)    NOT NULL UNIQUE,
    tenant_type         tenanttype      NOT NULL DEFAULT 'SINGLE_SCHOOL',
    subscription_tier   subscriptiontier NOT NULL DEFAULT 'TRIAL',
    subscription_start  DATE,
    subscription_end    DATE,
    max_students        INTEGER         NOT NULL DEFAULT 100,
    email               VARCHAR(255),
    phone               VARCHAR(20),
    is_active           BOOLEAN         NOT NULL DEFAULT TRUE,
    settings            TEXT,
    logo_url            VARCHAR(500),
    primary_color       VARCHAR(7)      DEFAULT '#1B4F72',
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at          TIMESTAMPTZ
);

CREATE TYPE tenanttype AS ENUM ('SINGLE_SCHOOL', 'SCHOOL_CHAIN');
CREATE TYPE subscriptiontier AS ENUM ('TRIAL', 'STARTER', 'PROFESSIONAL', 'ENTERPRISE');

CREATE UNIQUE INDEX ix_tenants_subdomain ON tenants (subdomain);
CREATE UNIQUE INDEX ix_tenants_slug ON tenants (slug);
CREATE INDEX ix_tenants_is_active ON tenants (is_active) WHERE is_active = TRUE;
```

**Design notes:**
- No `tenant_id` column -- this IS the root entity.
- No RLS -- the TenantMiddleware queries this table with raw SQL before RLS context is set.
- `subdomain` is the primary lookup key (indexed, unique). Must be 4-63 chars, lowercase, alphanumeric + hyphens.
- `slug` exists for URL-friendly display. Initially same as subdomain but could diverge.
- `settings` is a TEXT column (JSON stored as string). Flexible for tenant-specific config without schema changes.
- `subscription_tier` controls feature access. Checked at the application layer.

#### reserved_subdomains

```sql
CREATE TABLE reserved_subdomains (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    subdomain       VARCHAR(63)     NOT NULL UNIQUE,
    reason          TEXT,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX ix_reserved_subdomains_subdomain
    ON reserved_subdomains (subdomain);
```

Seeded with 36 reserved subdomains as defined in `/Users/harrymcninson/Documents/projects/sims-plus/backend/alembic/versions/20260104_0200_add_subdomain_rls.py` (lines 29-66): www, api, app, admin, mail, ftp, status, blog, help, support, docs, cdn, assets, staging, dev, test, demo, sandbox, beta, alpha, portal, login, register, signup, dashboard, billing, payments, webhooks, graphql, ws, static, media, images, files, downloads, uploads.

#### users

```sql
CREATE TABLE users (
    id                      UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id               UUID            NOT NULL,
    email                   VARCHAR(255)    NOT NULL,
    password_hash           VARCHAR(255)    NOT NULL,
    first_name              VARCHAR(100)    NOT NULL,
    last_name               VARCHAR(100)    NOT NULL,
    phone                   VARCHAR(20),
    role                    userrole        NOT NULL DEFAULT 'TEACHER',
    status                  userstatus      NOT NULL DEFAULT 'PENDING',
    school_id               UUID,
    email_verified          BOOLEAN         NOT NULL DEFAULT FALSE,
    email_verified_at       TIMESTAMPTZ,
    mfa_enabled             BOOLEAN         NOT NULL DEFAULT FALSE,
    mfa_secret              VARCHAR(255),
    last_login              TIMESTAMPTZ,
    failed_login_attempts   INTEGER         NOT NULL DEFAULT 0,
    locked_until            TIMESTAMPTZ,
    avatar_url              VARCHAR(500),
    timezone                VARCHAR(50)     NOT NULL DEFAULT 'Africa/Accra',
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at              TIMESTAMPTZ
);

CREATE TYPE userrole AS ENUM (
    'PLATFORM_ADMIN', 'CHAIN_ADMIN', 'SCHOOL_ADMIN', 'ACADEMIC_HEAD',
    'FINANCE_OFFICER', 'TEACHER', 'HOUSE_PARENT', 'PARENT', 'STUDENT'
);
CREATE TYPE userstatus AS ENUM ('PENDING', 'ACTIVE', 'SUSPENDED', 'DEACTIVATED');

CREATE UNIQUE INDEX ix_users_email ON users (email);
CREATE INDEX ix_users_tenant_id ON users (tenant_id);
CREATE INDEX ix_users_school_id ON users (school_id);
CREATE INDEX ix_users_role ON users (role);
CREATE INDEX ix_users_tenant_email ON users (tenant_id, email)
    WHERE deleted_at IS NULL;

-- RLS
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_policy ON users
    FOR ALL
    USING (tenant_id = get_current_tenant_id())
    WITH CHECK (tenant_id = get_current_tenant_id());
```

**Important note on `ix_users_email`:** The email index is globally unique, meaning a user cannot have the same email across different tenants. This is deliberate -- it prevents confusion during onboarding. If cross-tenant email reuse is needed later (e.g., a teacher at two schools), this index would need to become a composite unique on `(email, tenant_id)`.

#### schools

```sql
CREATE TABLE schools (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID            NOT NULL,
    name                VARCHAR(255)    NOT NULL,
    slug                VARCHAR(100)    NOT NULL,
    code                VARCHAR(50),
    school_type         schooltype      NOT NULL DEFAULT 'basic',
    status              schoolstatus    NOT NULL DEFAULT 'active',
    email               VARCHAR(255),
    phone               VARCHAR(20),
    website             VARCHAR(255),
    address             TEXT,
    city                VARCHAR(100),
    region              VARCHAR(100),
    gps_address         VARCHAR(50),
    logo_url            VARCHAR(500),
    primary_color       VARCHAR(7),
    motto               VARCHAR(255),
    description         TEXT,
    year_established    INTEGER,
    uses_boarding       BOOLEAN         NOT NULL DEFAULT FALSE,
    uses_transport      BOOLEAN         NOT NULL DEFAULT FALSE,
    student_id_prefix   VARCHAR(10)     NOT NULL DEFAULT 'STU',
    staff_id_prefix     VARCHAR(10)     NOT NULL DEFAULT 'STF',
    preschool_settings  JSONB,
    is_active           BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at          TIMESTAMPTZ
);

CREATE TYPE schooltype AS ENUM (
    'preschool', 'primary', 'preschool_primary', 'jhs', 'shs',
    'basic', 'basic_preschool', 'basic_shs', 'international', 'technical'
);
CREATE TYPE schoolstatus AS ENUM ('active', 'inactive', 'suspended');

CREATE INDEX ix_schools_tenant_id ON schools (tenant_id);
CREATE INDEX ix_schools_slug ON schools (slug);

ALTER TABLE schools ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_policy ON schools
    FOR ALL
    USING (tenant_id = get_current_tenant_id())
    WITH CHECK (tenant_id = get_current_tenant_id());
```

### PostgreSQL Functions for RLS

Implemented in the migration at `/Users/harrymcninson/Documents/projects/sims-plus/backend/alembic/versions/20260104_0200_add_subdomain_rls.py`:

```sql
-- Set tenant context on the current database session
CREATE OR REPLACE FUNCTION set_tenant_context(tenant_uuid UUID)
RETURNS VOID AS $$
BEGIN
    PERFORM set_config('app.current_tenant_id', tenant_uuid::TEXT, false);
END;
$$ LANGUAGE plpgsql;

-- Read current tenant context (used by RLS policies)
CREATE OR REPLACE FUNCTION get_current_tenant_id()
RETURNS UUID AS $$
BEGIN
    RETURN NULLIF(current_setting('app.current_tenant_id', true), '')::UUID;
EXCEPTION
    WHEN OTHERS THEN
        RETURN NULL;
END;
$$ LANGUAGE plpgsql STABLE;

-- Clear tenant context (called in finally block)
CREATE OR REPLACE FUNCTION clear_tenant_context()
RETURNS VOID AS $$
BEGIN
    PERFORM set_config('app.current_tenant_id', '', false);
END;
$$ LANGUAGE plpgsql;
```

### RLS Security Notes

**Critical:** The existing codebase initially had a NULL bypass policy (`USING (get_current_tenant_id() IS NULL)`) and a platform admin bypass. Both were removed in security hardening migrations (`fix_rls_null_bypass` and `remove_platform_admin_bypass`). New tables MUST NOT include these bypass policies.

**What happens when `get_current_tenant_id()` returns NULL:**
- The RLS policy evaluates `tenant_id = NULL`, which is always FALSE in SQL.
- No rows are returned -- this is the correct safe default.
- The `get_db()` dependency raises a 400 error if no tenant context is available for protected endpoints.

### Entity Relationship Diagram

```
+------------------+          +------------------+
|    tenants       |          | reserved_        |
|    (global)      |          | subdomains       |
|                  |          | (global)         |
| id          PK   |          |                  |
| name             |          | id          PK   |
| subdomain   UQ   |          | subdomain   UQ   |
| slug        UQ   |          | reason           |
| tenant_type      |          +------------------+
| subscription_tier|
| max_students     |
| is_active        |
+--------+---------+
         |
         | 1:N (tenant_id)
         |
+--------+---------+          +------------------+
|    schools       |          |    users         |
|    (tenant-scoped)|         |    (tenant-scoped)|
|                  |          |                  |
| id          PK   |  1:N    | id          PK   |
| tenant_id       <+-------- | tenant_id        |
| name             |          | school_id   FK  -+
| slug             |          | email       UQ   |
| school_type      |          | password_hash    |
| status           |          | role             |
+------------------+          | status           |
                              +------------------+
```

### Alembic Migration Strategy

**Migration naming convention:** `YYYYMMDD_HHMM_<revision_id>_<description>.py`

Existing migration chain (from memory):
```
8176a9079aeb (initial) -> add_subdomain_rls -> security_fixes_001 ->
add_schools_table -> 549287f1f9df -> sprint3_4_academic ->
fix_rls_null_bypass -> remove_platform_admin_bypass -> ...
```

**Test database:** The `init-db.sql` script at `/Users/harrymcninson/Documents/projects/sims-plus/backend/scripts/init-db.sql` creates `sims_plus_test`. Tests use a two-engine pattern: admin engine (superuser for DDL) + app_user engine (non-superuser, RLS enforced).

---

## 5. Authentication System Design

### JWT Token Structure

**Access Token (15-minute expiry):**

```json
{
    "sub": "550e8400-e29b-41d4-a716-446655440000",
    "type": "access",
    "tenant_id": "660e8400-e29b-41d4-a716-446655440001",
    "school_id": "770e8400-e29b-41d4-a716-446655440002",
    "role": "school_admin",
    "permissions": ["school.read", "school.update", "users.*", "students.*"],
    "email": "admin@presec.edu.gh",
    "tenant_subdomain": "presec",
    "iat": 1704067200,
    "exp": 1704068100
}
```

**Refresh Token (7-day expiry):**

```json
{
    "sub": "550e8400-e29b-41d4-a716-446655440000",
    "type": "refresh",
    "tenant_id": "660e8400-e29b-41d4-a716-446655440001",
    "iat": 1704067200,
    "exp": 1704672000
}
```

**Key design decisions:**
- `type` field distinguishes access from refresh tokens -- prevents using a refresh token as an access token.
- `tenant_id` is in BOTH tokens -- enables cross-tenant validation on refresh.
- Permissions are embedded in the access token to avoid a DB lookup on every request. Recalculated on refresh.
- `tenant_subdomain` in the access token allows the frontend to validate it matches the current subdomain without a DB call.

Implementation in `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/core/security.py` (lines 55-144).

### Token Lifecycle

```
                    Login
                      |
                      v
              +---------------+
              | Access Token  |--- 15 min ---> Expired
              | (HttpOnly     |                    |
              |  cookie)      |                    v
              +---------------+           +----------------+
                                          | Try Refresh    |
              +---------------+           | (refresh token |
              | Refresh Token |---------->|  from cookie)  |
              | (HttpOnly     |           +----------------+
              |  cookie only) |                    |
              +---------------+           +--------+--------+
                                          |                 |
                                   Success              Failure
                                     |                     |
                                     v                     v
                              New Access Token       Redirect to
                              New Refresh Token      /login
                              (rotation)
```

### Login Flow

Implemented in `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/api/v1/endpoints/auth.py` (lines 68-139) and `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/services/auth.py` (lines 118-262):

1. TenantMiddleware resolves subdomain to `tenant_id`
2. `AuthService.authenticate()`:
   a. Find user by email + tenant_id (defense-in-depth query)
   b. Check account lock status (`locked_until`)
   c. Verify Argon2id hash
   d. Check user status (ACTIVE required)
   e. Reset `failed_login_attempts`, update `last_login`
   f. Log audit event via `AuditService`
   g. Generate access + refresh tokens with full claims
3. Return `LoginResponse` with tokens and user info

### Password Hashing

From `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/core/security.py` (lines 17-21):

```python
password_hasher = PasswordHasher(
    time_cost=2,        # 2 iterations
    memory_cost=65536,  # 64 MB
    parallelism=1,      # 1 thread
)
```

### Account Lockout

From `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/services/auth.py` (lines 40-41):
- `MAX_FAILED_ATTEMPTS = 5`
- `LOCKOUT_DURATION_MINUTES = 30`
- After 5 failures: `locked_until = now + 30 minutes`, audit event logged
- Counter resets on next successful login

### Token Blacklisting (Redis)

```
Keys:
  blacklist:token:<token_hash>          -> "1"  (TTL = token remaining lifetime)
  blacklist:user:<user_id>:revoked_at   -> <timestamp>  (TTL = max token lifetime)

Operations:
  - Logout:          blacklist the current access token
  - Password change: set user revoked_at (invalidates ALL tokens issued before)
```

### Role-Permission Mapping

From `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/services/auth.py` (lines 44-107):

```python
ROLE_PERMISSIONS = {
    "platform_admin":  ["*"],
    "chain_admin":     ["schools.*", "users.*", "students.*", "staff.*",
                        "academics.*", "subjects.*", "grading.*",
                        "finance.*", "reports.*"],
    "school_admin":    ["school.read", "school.update", "users.*",
                        "students.*", "staff.*", "classes.*", "academics.*",
                        "subjects.*", "grading.*", "attendance.*",
                        "exams.*", "finance.*", "reports.*"],
    "academic_head":   ["students.read", "students.update", "classes.*",
                        "academics.*", "subjects.*", "grading.*",
                        "attendance.*", "exams.*", "reports.academic"],
    "finance_officer": ["students.read", "finance.*", "reports.financial"],
    "teacher":         ["students.read", "classes.read", "subjects.read",
                        "grading.read", "attendance.mark", "exams.scores"],
    "house_parent":    ["students.read", "boarding.*"],
    "parent":          ["children.read", "finance.invoices.read"],
    "student":         ["self.read"],
}
```

---

## 6. Multi-Tenant Request Lifecycle

### Complete Request Flow (Step by Step)

**Step 1: DNS and SSL (Cloudflare)**
```
*.simsplus.io -> Cloudflare proxy -> Origin IP (ALB)
SSL terminated at Cloudflare edge (Full Strict mode)
WAF rules filter malicious requests
```

**Step 2: Load Balancer (ALB)**
```
Path /api/* -> Target Group: fastapi-pods (port 8000)
All other paths -> Target Group: next-js-pods (port 3000)
```

**Step 3: Next.js proxy.ts**

From `/Users/harrymcninson/Documents/projects/sims-plus/frontend/proxy.ts`:
```
Production:  "presec.simsplus.io" -> parts = ["presec","simsplus","io"] -> "presec"
Dev option A: "presec.localhost:3000" -> "presec"
Dev option B: "localhost:3000?subdomain=presec" -> "presec"
Dev option C: Cookie x-subdomain=presec -> "presec"

Actions:
  1. Validate format (4-63 chars, lowercase, not reserved)
  2. Set request header: x-subdomain = presec
  3. Set response cookie: x-subdomain = presec
  4. No subdomain + non-public route -> redirect to /login?error=no_school
```

**Step 4: FastAPI TenantMiddleware**

From `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/middleware/tenant.py`:
```
1. Clear previous tenant context (contextvars)
2. Skip OPTIONS requests (CORS preflight)
3. Skip public paths (/health, /docs, /api/v1/onboarding/*, etc.)
4. Read X-Subdomain header (or extract from Host header fallback)
5. If no subdomain and path requires tenant: return 400
6. Raw SQL query (NOT through RLS):
   SELECT id, subdomain, name, is_active FROM tenants
   WHERE subdomain = :subdomain AND deleted_at IS NULL
7. If not found: return 404 "School not found"
8. If not active: return 403 "School account suspended"
9. Set: request.state.tenant_id, request.state.tenant_subdomain
10. Process request; clear context in finally block
```

**Step 5: Database RLS Arming (get_db dependency)**

From `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/api/deps.py` (lines 26-59):
```
1. Create AsyncSession
2. Read request.state.tenant_id
3. EXECUTE: SELECT set_tenant_context(:tenant_id)
   -> SET app.current_tenant_id = '<uuid>'
4. Yield session to endpoint
5. On success: session.commit()
6. On exception: session.rollback()
7. Finally: SELECT clear_tenant_context(); session.close()
```

**Step 6: Defense-in-Depth**
```
Even though RLS filters at the DB level, services add explicit filtering:

  result = await self.db.execute(
      select(Student).where(
          Student.id == student_id,
          Student.tenant_id == tenant_id,      # Explicit filter
          Student.deleted_at.is_(None),         # Soft delete
      )
  )

Two barriers: application filter + database RLS
An attacker would need to defeat BOTH simultaneously
```

**Step 7: Cross-Tenant Token Validation**

From `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/api/deps.py` (lines 198-245):
```
1. Decode JWT -> extract tenant_id from claims
2. Read request.state.tenant_id (from middleware)
3. Compare: str(token_tenant_id) == str(request_tenant_id)
4. If mismatch: return 403 "Token not valid for this school"

Attack prevented: User logs into presec, tries to use token on achimota -> rejected
```

---

## 7. Onboarding Flow

### Registration Sequence

As implemented in `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/services/onboarding.py`:

```
User visits /register
  |
  1. Enter school name
  2. Auto-suggest subdomains ----> GET /api/v1/onboarding/suggest-subdomain
                                   <-- ["presec", "presecgh", "presec1"]
  3. Select/type subdomain
  4. Real-time validation -------> GET /api/v1/tenant/check-subdomain?subdomain=presec
                                   <-- {available: true}
  5. Enter admin details (name, email, password)
  6. Select school type
  7. Submit --------------------> POST /api/v1/onboarding/register
                                        |
                                  OnboardingService.register_school():
                                        |
                                  1. Validate subdomain (format + reserved + taken)
                                  2. Check email not used in any tenant
                                  3. Create Tenant (trial, 30 days, 100 students)
                                  4. Create School (within tenant)
                                  5. Create Admin User (SCHOOL_ADMIN, auto-verified)
                                  6. Send welcome email (async, non-blocking)
                                        |
                                  Return: {
                                    success: true,
                                    subdomain: "presec",
                                    portal_url: "https://presec.simsplus.io",
                                    trial_ends_at: "2026-03-15T..."
                                  }
  |
  8. Show success page with portal link
  9. User navigates to presec.simsplus.io/login
```

### Subdomain Validation Rules

```
Format: 4-63 chars, ^[a-z0-9][a-z0-9-]*[a-z0-9]$ | ^[a-z0-9]+$
Not in reserved_subdomains table
Not in tenants table

Suggestion algorithm (from OnboardingService._clean_subdomain):
  Input:   "Presbyterian Boys' Secondary School"
  Cleaned: "presbyterianboyssecondaryschool"
  Candidates: base, truncated(20), base+"gh", base+"edu", base+1..9
  Return first N that pass availability check
```

### Trial Configuration

From `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/services/onboarding.py` (lines 38-47):
```python
TRIAL_DAYS = 30
MAX_STUDENTS_BY_PLAN = {
    "trial": 100,
    "starter": 300,
    "professional": 1000,
    "enterprise": 10000,
}
```

### Default Data Seeding

In Sprint 1-2, only tenant + school + admin user are created. The setup wizard (Sprint 4) handles academic year creation, term definitions, class structure, subject assignments, and grading scale selection. This keeps the onboarding transaction lightweight.

---

## 8. Frontend Architecture

### Next.js 16 App Router Structure

From `/Users/harrymcninson/Documents/projects/sims-plus/frontend/`:

```
frontend/
  app/
    layout.tsx                     # Root layout: ThemeProvider, Toaster
    page.tsx                       # Landing page
    not-found.tsx                  # 404 page
    (auth)/                        # Route group: auth pages
      layout.tsx                   # TenantProvider wrapper
      login/page.tsx
      register/page.tsx
      register/success/page.tsx
      forgot-password/page.tsx
      reset-password/page.tsx
      verify-email/page.tsx
    (dashboard)/                   # Route group: protected
      layout.tsx                   # Sidebar + Header + AuthGuard
      dashboard/page.tsx
      settings/page.tsx
      students/                    # Future sprints
      staff/
      ...

  actions/
    auth.action.ts                 # login, logout, refresh, getCurrentUser
    school.action.ts               # getSchool, updateSchool
    tenant.action.ts               # checkSubdomain, suggestSubdomains

  components/
    providers/
      ThemeProvider.tsx
      TenantProvider.tsx           # Client-side tenant context
    ui/                            # Shadcn/ui
    dashboard/
      Sidebar.tsx
      Header.tsx

  lib/
    api.ts                         # apiFetch, apiGet, apiPost, etc.

  types/
    index.ts                       # All TypeScript types

  proxy.ts                         # Subdomain detection (replaces middleware.ts)
```

### proxy.ts (Subdomain Detection)

From `/Users/harrymcninson/Documents/projects/sims-plus/frontend/proxy.ts`:

The proxy runs on every request and handles three development modes:
1. `presec.localhost:3000` -- Subdomain from hostname
2. `localhost:3000?subdomain=presec` -- Query parameter
3. Cookie `x-subdomain=presec` -- Persists across navigation

Key behavior:
- Sets `x-subdomain` header for server components
- Sets `x-subdomain` cookie (httpOnly: false) for client components (TenantProvider)
- Redirects non-public routes without subdomain to `/login?error=no_school`

### Server Actions Pattern

From `/Users/harrymcninson/Documents/projects/sims-plus/frontend/actions/auth.action.ts`:

```typescript
"use server";

import { cookies } from "next/headers";
import { apiPost } from "@/lib/api";

export async function login(credentials: LoginCredentials): Promise<ActionResult<User>> {
    const subdomain = await getSubdomainFromCookies();
    const response = await apiPost<AuthResponse>("/auth/login", credentials, { subdomain });

    // Store tokens in HttpOnly cookies (NEVER exposed to client JS)
    const cookieStore = await cookies();
    cookieStore.set("access_token", response.access_token, {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production",
        sameSite: "lax",
        maxAge: 60 * 15,  // 15 minutes
    });
    cookieStore.set("refresh_token", response.refresh_token, {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production",
        sameSite: "lax",
        maxAge: 60 * 60 * 24 * 7,  // 7 days
    });

    return { success: true, data: response.user };
}
```

**Why Server Actions, not client-side fetch:**
1. Security: Access tokens in HttpOnly cookies, never exposed to client JavaScript
2. No CORS issues (server-to-server calls)
3. No API client in the browser bundle
4. X-Subdomain header added server-side, no client manipulation possible

### API Client

From `/Users/harrymcninson/Documents/projects/sims-plus/frontend/lib/api.ts`:

```typescript
const API_BASE_URL = process.env.API_URL || "http://localhost:8000/api/v1";

// Note: API_URL (server-only) = "http://backend:8000/api/v1" (Docker internal)
// NEXT_PUBLIC_API_URL (client) = "http://localhost:8000/api/v1" (TenantProvider only)
```

All functions (`apiFetch`, `apiGet`, `apiPost`, `apiPut`, `apiPatch`, `apiDelete`, `apiUpload`) set `cache: "no-store"` to disable Next.js fetch caching for API calls.

### TenantProvider

From `/Users/harrymcninson/Documents/projects/sims-plus/frontend/components/providers/TenantProvider.tsx`:

- Reads `x-subdomain` cookie (set by proxy.ts)
- Fetches tenant info from `GET /api/v1/tenant/validate/{subdomain}`
- Provides context: `{ tenant, subdomain, isLoading, error, isTenantContext, refreshTenant }`
- Applies tenant branding via CSS custom property: `--tenant-primary-color`

### Component Hierarchy for Login Page

```
RootLayout (layout.tsx)
  ThemeProvider
  Toaster
  AuthLayout ((auth)/layout.tsx)
    TenantProvider
    LoginPage ((auth)/login/page.tsx)
      TenantBranding (logo, school name, colors)
      LoginForm
        Email input (React Hook Form + Zod)
        Password input
        Submit button -> calls login() Server Action
        "Forgot password?" link
        Error display
```

---

## 9. Docker and Dev Environment

### docker-compose.yml

From `/Users/harrymcninson/Documents/projects/sims-plus/docker-compose.yml`:

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| `db` | postgres:16-alpine | 5432 | PostgreSQL with health check |
| `redis` | redis:7-alpine | 6379 | Rate limiting, token blacklist |
| `backend` | Custom (Dockerfile) | 8000 | FastAPI with hot reload |
| `frontend` | Custom (Dockerfile) | 3000 | Next.js dev server |
| `adminer` | adminer:latest | 8080 | DB GUI (profile: tools) |

Key configuration:
- Backend `DATABASE_URL` uses Docker service name `db` for hostname
- Frontend `API_URL=http://backend:8000/api/v1` uses Docker internal network
- Frontend `NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1` for client-side calls
- Named volumes for postgres data, redis data, node_modules, and .next cache

### init-db.sql

From `/Users/harrymcninson/Documents/projects/sims-plus/backend/scripts/init-db.sql`:
- Creates extensions: `uuid-ossp`, `pgcrypto`
- Creates test database: `sims_plus_test`
- Creates helper function: `current_tenant_id()`

### Dockerfile Patterns

**Backend** (`/Users/harrymcninson/Documents/projects/sims-plus/backend/Dockerfile`):
- Multi-stage: `base` -> `development` (with dev deps, hot reload) -> `production` (non-root user, 4 workers)
- Includes WeasyPrint system dependencies for PDF generation

**Frontend** (`/Users/harrymcninson/Documents/projects/sims-plus/frontend/Dockerfile`):
- Multi-stage: `deps` (npm ci) -> `development` -> `builder` (npm run build) -> `production` (standalone, non-root)

### Local Subdomain Testing

**Recommended: `*.localhost`**
Modern browsers resolve `presec.localhost` to `127.0.0.1` automatically:
```
http://presec.localhost:3000  ->  proxy.ts extracts "presec"
```

**Quick switching: Query parameter**
```
http://localhost:3000?subdomain=presec
```

**Production-like: `/etc/hosts`**
```
127.0.0.1   presec.simsplus.local
```
(Requires updating CORS_ORIGINS.)

### Development Workflow

```bash
cp env .env                      # Copy and edit environment variables
docker-compose up -d             # Start all services
docker exec sims-plus-backend alembic upgrade head  # Run migrations

# Access points:
# Frontend:  http://localhost:3000
# Backend:   http://localhost:8000
# API Docs:  http://localhost:8000/docs
# Adminer:   docker-compose --profile tools up adminer -> http://localhost:8080

# Register a test school:
# POST http://localhost:8000/api/v1/onboarding/register
# Access: http://presec.localhost:3000
```

---

## 10. API Contracts

### POST /api/v1/auth/login

**Purpose:** Authenticate user, return JWT tokens.
**Auth:** None (requires tenant context from subdomain).
**Rate Limit:** 5 req/min (auth).

**Request:**
```json
{
    "email": "admin@presec.edu.gh",
    "password": "SecureP@ss1"
}
```

**Response (200):**
```json
{
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer",
    "expires_in": 900,
    "user": {
        "id": "550e8400-...",
        "email": "admin@presec.edu.gh",
        "first_name": "Kwame",
        "last_name": "Asante",
        "phone": "+233244123456",
        "role": "school_admin",
        "status": "active",
        "tenant_id": "660e8400-...",
        "school_id": "770e8400-...",
        "avatar_url": null,
        "email_verified": true,
        "mfa_enabled": false,
        "created_at": "2026-01-15T10:00:00Z",
        "updated_at": "2026-01-15T10:00:00Z"
    }
}
```

**Errors:** 400 (no tenant), 401 (invalid credentials / locked / unverified / suspended), 429 (rate limited).

### POST /api/v1/auth/refresh

**Purpose:** Token rotation -- new access + refresh tokens from valid refresh token.
**Auth:** None (refresh token is the credential).
**Rate Limit:** 5 req/min.

**Request:** `{ "refresh_token": "eyJ..." }`
**Response (200):** `{ "access_token": "...", "refresh_token": "...", "token_type": "bearer", "expires_in": 900 }`
**Errors:** 400 (no tenant), 401 (invalid/expired token, tenant mismatch, inactive account).

### POST /api/v1/auth/logout

**Purpose:** Blacklist current access token.
**Auth:** Bearer token required.
**Response:** 204 No Content.

### GET /api/v1/auth/me

**Purpose:** Current user profile + tenant info + permissions.
**Auth:** Bearer token + cross-tenant validation.

**Response (200):**
```json
{
    "user": { /* UserResponse */ },
    "tenant": {
        "id": "660e8400-...",
        "name": "Presbyterian Boys' Secondary School",
        "subdomain": "presec",
        "subscription_tier": "trial",
        "logo_url": null,
        "primary_color": "#1B4F72"
    },
    "permissions": ["school.read", "school.update", "users.*", ...]
}
```

### GET /api/v1/tenant/validate/{subdomain}

**Purpose:** Validate tenant and return public info (for branded login).
**Auth:** None.
**Rate Limit:** 20 req/min.

**Response (200):**
```json
{
    "valid": true,
    "tenant": {
        "id": "660e8400-...",
        "name": "Presbyterian Boys' Secondary School",
        "subdomain": "presec",
        "subscription_tier": "trial",
        "branding": {
            "logo_url": "https://...",
            "primary_color": "#1B4F72"
        }
    }
}
```

### GET /api/v1/tenant/check-subdomain

**Purpose:** Check subdomain availability for registration.
**Auth:** None.
**Rate Limit:** 20 req/min.

**Query:** `?subdomain=presec`
**Response (200):** `{ "subdomain": "presec", "available": false, "reason": "This subdomain is already registered" }`

### POST /api/v1/onboarding/register

**Purpose:** Register new school (creates tenant + school + admin).
**Auth:** None.
**Rate Limit:** 5 req/min.

**Request:**
```json
{
    "school_name": "Presbyterian Boys' Secondary School",
    "subdomain": "presec",
    "school_type": "shs",
    "admin_email": "admin@presec.edu.gh",
    "admin_first_name": "Kwame",
    "admin_last_name": "Asante",
    "admin_password": "SecureP@ss1",
    "admin_phone": "+233244123456",
    "plan": "trial"
}
```

**Response (201):**
```json
{
    "success": true,
    "message": "School 'Presbyterian Boys' Secondary School' registered successfully!...",
    "tenant_id": "660e8400-...",
    "school_id": "770e8400-...",
    "admin_user_id": "550e8400-...",
    "subdomain": "presec",
    "portal_url": "https://presec.simsplus.io",
    "admin_email": "admin@presec.edu.gh",
    "trial_ends_at": "2026-03-15T10:00:00Z"
}
```

**Errors:** 400 (subdomain taken, email exists, invalid format), 422 (validation).

### GET /api/v1/onboarding/suggest-subdomain

**Purpose:** Generate available subdomain suggestions.
**Auth:** None.
**Rate Limit:** 20 req/min.

**Query:** `?school_name=Achimota School&count=3`
**Response (200):** `{ "school_name": "Achimota School", "suggestions": ["achimotaschool", "achimotaschoolgh", "achimotaschool1"] }`

---

## 11. Module Boundaries

### Module Definition

Each module follows this structure:
```
Module = {
    Endpoints:  api/v1/endpoints/{module}.py     # HTTP handlers
    Schemas:    schemas/{module}.py               # Request/response validation
    Service:    services/{module}.py              # Business logic
    Models:     models/{module}.py                # Database models
    Tests:      tests/test_{module}.py            # Module tests
}
```

### Sprint 1-2 Modules

| Module | Endpoints | Service | Responsibility |
|--------|-----------|---------|----------------|
| **Auth** | `auth.py` | `auth.py` | Login, logout, refresh, password change, email verification, password reset |
| **Tenant** | `tenant.py` | `tenant.py` | Subdomain validation, tenant lookup, public tenant info |
| **Onboarding** | `onboarding.py` | `onboarding.py` | School registration, subdomain suggestions, plan info |
| **School** | `schools.py` | (via onboarding) | School profile read/update |
| **User** | `users.py` | (via auth) | User CRUD within tenant |

### Dependency Graph

```
+-----------+     +-----------+     +-----------+
|   Auth    |---->|  Tenant   |<----| Onboarding|
+-----------+     +-----------+     +-----------+
  |     |                                |
  |     v                                v
  |  +-----------+                +-----------+
  |  | Token     |                | Email     |
  |  | Blacklist |                | Service   |
  |  | (Redis)   |                | (SMTP)    |
  |  +-----------+                +-----------+
  v
+-----------+
|  Audit    |
|  Service  |
+-----------+
```

**Rules:**
1. Auth depends on Tenant (for subdomain -> tenant_id).
2. Auth depends on Audit (for security event logging).
3. Auth depends on Token Blacklist (for logout/revocation).
4. Onboarding depends on Tenant (for subdomain availability).
5. Onboarding depends on Email (for welcome email).
6. No circular dependencies.
7. Modules communicate through service interfaces, never by importing endpoint functions.

### Module Interface Contracts

```python
# Auth
class AuthService:
    authenticate(email, password, tenant_id, ...) -> (User, access_token, refresh_token)
    register_user(email, password, tenant_id, role, ...) -> User
    refresh_tokens(refresh_token, tenant_id) -> (access_token, refresh_token)
    change_password(user_id, current, new) -> bool
    verify_email(user_id) -> bool
    get_user_by_id(user_id) -> User | None
    get_role_permissions(role) -> list[str]  # classmethod

# Tenant
class TenantService:
    validate_subdomain_format(subdomain) -> (bool, error_msg)
    is_subdomain_reserved(subdomain) -> bool
    is_subdomain_taken(subdomain) -> bool
    check_subdomain_availability(subdomain) -> (bool, reason)
    get_tenant_by_subdomain(subdomain) -> Tenant | None
    get_tenant_by_id(tenant_id) -> Tenant | None
    validate_tenant(subdomain) -> (bool, Tenant | None, error_msg)

# Onboarding
class OnboardingService:
    register_school(school_name, subdomain, school_type, admin_*, plan)
        -> (Tenant, School, User)
    generate_subdomain_suggestions(school_name, count) -> list[str]
    get_portal_url(subdomain) -> str
```

---

## 12. Critical Design Decisions

### Decision 1: Shared Database vs Database-Per-Tenant

| Aspect | Shared DB (CHOSEN) | DB-Per-Tenant |
|--------|-------------------|--------------|
| Data Isolation | PostgreSQL RLS | Physical separation |
| Operational Cost | One DB to manage | N databases |
| Schema Migrations | Run once | Run N times |
| Cross-Tenant Queries | Possible (platform admin) | Requires federation |
| Connection Pooling | One pool, efficient | N pools, connection explosion |
| Scale Limit | ~50K tenants before sharding | Independent per tenant |

**Rationale:** For hundreds to low thousands of Ghanaian schools, the operational simplicity of one database far outweighs the theoretical security benefit of physical separation. RLS + defense-in-depth provides sufficient isolation. The platform admin RLS bypass was intentionally removed to close even that attack surface.

### Decision 2: Subdomain vs Path-Based Routing

| Aspect | Subdomain (CHOSEN) | Path-Based |
|--------|-------------------|-----------|
| URL | `presec.simsplus.io` | `simsplus.io/school/presec` |
| Branding | Feels like "their" site | Feels like shared platform |
| Cookies | Scoped to subdomain naturally | Must scope manually |
| Local Dev | Requires `*.localhost` | Simple localhost |

**Rationale:** Schools want ownership. `presec.simsplus.io` communicates "this is Presec's system." Minor local dev complexity solved by `*.localhost` and query parameter fallback.

### Decision 3: JWT vs Server Sessions

**Chosen: JWT.** Aligns with stateless pod architecture. Blacklist overhead is minimal (Redis SET with TTL). Embedding permissions avoids DB lookup on every request. Natural mobile app support.

### Decision 4: Argon2id vs bcrypt

**Chosen: Argon2id.** OWASP #1 recommendation, won Password Hashing Competition. Memory-hard (GPU-resistant) + side-channel resistant. `argon2-cffi` library is well-maintained.

### Decision 5: Next.js proxy.ts vs middleware.ts

**Chosen: proxy.ts.** Next.js 16 introduced proxy.ts running on Node.js runtime (not Edge), giving full access to cookies, headers, and filesystem. The subdomain extraction and cookie logic works naturally here.

### Decision 6: Server Actions vs Client-Side API Calls

**Chosen: Server Actions.** Tokens stay in HttpOnly cookies (never exposed to client JS). No CORS issues. No API client in browser bundle. X-Subdomain header cannot be manipulated by client.

### Decision 7: Enum Value Casing

Existing inconsistency:
- `userrole`, `userstatus`, `tenanttype`, `subscriptiontier`: UPPERCASE values in DB
- `schooltype`, `schoolstatus`: lowercase values in DB

**Rule for new enums:** Use `values_callable=lambda x: [e.value for e in x]` and define Python enum values as **lowercase** strings. This matches the Sprint 3+ pattern and REST API conventions.

```python
class ExampleStatus(str, Enum):
    ACTIVE = "active"       # Python name: UPPERCASE, value: lowercase
    INACTIVE = "inactive"

# In model
status: Mapped[ExampleStatus] = mapped_column(
    SQLEnum(
        ExampleStatus,
        name="examplestatus",
        values_callable=lambda x: [e.value for e in x],
    ),
)
```

---

## 13. Component Breakdown with Parallel Tracks

### Sprint 1 -- Foundation (Week 1-2)

```
Track A: Backend Setup (Backend Developer)
  Week 1:
    1. Python project scaffolding (pyproject.toml, requirements.txt)
    2. FastAPI app shell (main.py, config.py, health endpoint)
    3. SQLAlchemy async engine (db/session.py)
    4. Base models (Base, TenantMixin, SoftDeleteMixin)
    5. Alembic configuration
    6. init-db.sql
  Week 2:
    7. Tenant model + initial migration
    8. ReservedSubdomain model + seed data
    9. User model
    10. School model
    11. set_tenant_context() / get_current_tenant_id() functions
    12. RLS policies for users and schools

Track B: Frontend Setup (Frontend Developer)
  Week 1:
    1. Next.js 16 project (App Router, TypeScript, Tailwind v4)
    2. Shadcn/ui installation (New York style)
    3. Root layout with ThemeProvider
    4. proxy.ts with subdomain extraction
    5. lib/api.ts (server-side API client)
    6. TypeScript types (types/index.ts)
  Week 2:
    7. (auth) route group and layout
    8. Login page with form (React Hook Form + Zod)
    9. Register page (registration wizard)
    10. TenantProvider component
    11. (dashboard) route group with sidebar layout
    12. Basic dashboard page (placeholder)

Track C: Infrastructure (DevOps / Shared)
  Week 1:
    1. docker-compose.yml with all services
    2. Dockerfiles (backend + frontend, multi-stage)
    3. .env template
    4. Cloudflare DNS wildcard record
    5. SSL configuration
  Week 2:
    6. GitHub Actions CI pipeline (lint, test)
    7. Pre-commit hooks (black, ruff, mypy)
    8. Makefile or scripts for common commands
    9. README documentation
```

### Sprint 2 -- Core Features (Week 3-4)

```
Track A: Backend Auth & Middleware (Backend Developer)
  Week 3:
    1. TenantMiddleware (subdomain extraction, validation, context)
    2. RateLimitMiddleware (Redis sliding window)
    3. core/security.py (Argon2id, JWT)
    4. api/deps.py (get_db, get_current_user_id, validate_token_tenant)
    5. AuthService (authenticate, register_user, refresh_tokens)
    6. AuditService (security event logging)
  Week 4:
    7. TokenBlacklistService (Redis)
    8. PasswordResetService
    9. EmailVerificationService
    10. EmailService (SMTP)
    11. TenantService (subdomain validation)
    12. OnboardingService (register_school)
    13. All auth endpoints
    14. Tenant endpoints
    15. Onboarding endpoints

Track B: Frontend Auth Flow (Frontend Developer)
  Week 3:
    1. auth.action.ts (login, logout, refresh, getCurrentUser)
    2. LoginForm with tenant branding
    3. RegistrationForm (multi-step wizard)
    4. Token management (HttpOnly cookies in Server Actions)
    5. AuthGuard for dashboard protection
  Week 4:
    6. Forgot/reset password pages
    7. Email verification page
    8. Registration success page
    9. Dashboard sidebar navigation
    10. User menu with logout
    11. School settings page
    12. End-to-end test: register -> login -> dashboard

Track C: Testing & Integration (Shared)
  Week 3:
    1. conftest.py with two-engine pattern
    2. Tenant middleware tests
    3. Auth service unit tests
    4. Onboarding service tests
  Week 4:
    5. Integration tests (register -> login -> protected endpoints)
    6. RLS verification tests (cross-tenant isolation)
    7. Rate limiting tests
    8. End-to-end Docker Compose testing
```

### Task Dependencies (Critical Path)

```
Docker Setup -> Backend Shell -> DB Models -> RLS Functions ->
TenantMiddleware -> deps.py -> AuthService -> Auth Endpoints ->
Frontend Server Actions -> Integration Tests
```

**Estimated duration:** 4 weeks (2 per sprint).
**Parallelism savings:** ~1 week (frontend and infrastructure start in parallel with backend).

---

## Appendix A: Security Checklist

- [ ] All tenant-scoped tables have `tenant_id` NOT NULL
- [ ] RLS enabled on users and schools with NO NULL bypass
- [ ] `get_db()` calls `set_tenant_context()` and clears in `finally`
- [ ] All services filter by `tenant_id` explicitly (defense-in-depth)
- [ ] JWT access tokens: 15-minute expiry
- [ ] JWT refresh tokens: 7-day expiry with rotation
- [ ] Refresh validates tenant_id match
- [ ] Token blacklisting for logout and password change
- [ ] Account lockout: 5 failures -> 30-minute lock
- [ ] Password policy: 8+ chars, upper/lower/digit/special
- [ ] Argon2id hashing (not bcrypt)
- [ ] Rate limiting: auth 5/min, subdomain 20/min, default 100/min
- [ ] CORS restricted to known origins
- [ ] Security headers in Next.js config
- [ ] Access tokens in HttpOnly cookies only
- [ ] No `from __future__ import annotations` in endpoint files
- [ ] Audit logging for all auth events
- [ ] Password reset prevents email enumeration
- [ ] Global exception handler sanitizes errors in production

## Appendix B: Performance Targets

| Metric | Target | Approach |
|--------|--------|----------|
| Login response | < 300ms | Argon2id ~100ms, JWT ~5ms, DB ~10ms |
| Tenant middleware | < 10ms | Raw SQL with indexed subdomain |
| RLS overhead | < 2ms | Session variable read (STABLE function) |
| Rate limit check | < 5ms | Redis ZADD/ZCARD pipeline |
| Token validation | < 10ms | JWT decode + Redis blacklist check |
| Page load (3G) | < 3s | Server Components, no client API calls |
| Concurrent users/tenant | 500 | Stateless pods, pool 10+20 overflow |

---

*End of Sprint 1-2 Architecture Document*

---

Now let me update my agent memory with the key patterns discovered during this analysis.
The complete Sprint 1-2 architecture document is above. Here is a summary of what it covers and the key files I examined to produce it:

**Key source files examined:**

| File | Purpose |
|------|---------|
| `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/main.py` | FastAPI app creation, middleware stack order |
| `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/config.py` | All environment variables, settings |
| `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/models/base.py` | Base, TenantMixin, SoftDeleteMixin patterns |
| `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/models/tenant.py` | Tenant model (root entity, no tenant_id) |
| `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/models/user.py` | User model with all fields and enums |
| `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/models/school.py` | School model with school types |
| `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/middleware/tenant.py` | TenantMiddleware, context var management, subdomain extraction |
| `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/middleware/rate_limit.py` | Redis sliding window rate limiting |
| `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/api/deps.py` | All dependency injection (get_db, auth, tenant validation, permissions) |
| `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/core/security.py` | Argon2id hashing, JWT creation/decode |
| `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/services/auth.py` | Full auth service (login, register, refresh, role permissions) |
| `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/services/onboarding.py` | School registration flow |
| `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/services/tenant.py` | Subdomain validation logic |
| `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/api/v1/endpoints/auth.py` | All auth endpoint implementations |
| `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/api/v1/endpoints/onboarding.py` | Registration endpoint |
| `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/api/v1/router.py` | Router aggregation pattern |
| `/Users/harrymcninson/Documents/projects/sims-plus/backend/alembic/versions/20260104_0011_8176a9079aeb_initial_schema.py` | Initial migration (tenants + users) |
| `/Users/harrymcninson/Documents/projects/sims-plus/backend/alembic/versions/20260104_0200_add_subdomain_rls.py` | RLS functions, reserved subdomains seed |
| `/Users/harrymcninson/Documents/projects/sims-plus/backend/scripts/init-db.sql` | Database bootstrap |
| `/Users/harrymcninson/Documents/projects/sims-plus/docker-compose.yml` | All Docker services |
| `/Users/harrymcninson/Documents/projects/sims-plus/backend/Dockerfile` | Backend multi-stage build |
| `/Users/harrymcninson/Documents/projects/sims-plus/frontend/Dockerfile` | Frontend multi-stage build |
| `/Users/harrymcninson/Documents/projects/sims-plus/frontend/proxy.ts` | Subdomain detection (replaces middleware.ts) |
| `/Users/harrymcninson/Documents/projects/sims-plus/frontend/lib/api.ts` | Server-side API client |
| `/Users/harrymcninson/Documents/projects/sims-plus/frontend/actions/auth.action.ts` | Login, logout, token management |
| `/Users/harrymcninson/Documents/projects/sims-plus/frontend/components/providers/TenantProvider.tsx` | Client-side tenant context |
| `/Users/harrymcninson/Documents/projects/sims-plus/frontend/next.config.ts` | Security headers, image patterns |
| `/Users/harrymcninson/Documents/projects/sims-plus/frontend/types/index.ts` | TypeScript type definitions |
| `/Users/harrymcninson/Documents/projects/sims-plus/env` | Environment variable template |

The document was not written to the filesystem due to a permission restriction. If you would like it saved as a file, you can grant write permission and I will write it to `/Users/harrymcninson/Documents/projects/sims-plus/docs/architecture/sprint-1-2-core-infrastructure.md`.