# SIMS Plus -- Multi-Tenancy Architecture Design Document

**Version:** 1.0 | **Date:** 2026-02-15 | **Sprint Scope:** Sprint 0 (Greenfield Foundation)

---

## 1. Architecture Overview

SIMS Plus uses a **shared-everything** multi-tenant model: one PostgreSQL database, one application cluster, one Redis instance, one S3 bucket. Every school (tenant) accesses the platform via a unique subdomain (`{school-code}.simsplus.io`). Data isolation is enforced through seven complementary layers, each of which is necessary and none of which is sufficient alone.

```
                          Request: presec.simsplus.io
                                    |
  LAYER 1  --------  Cloudflare DNS Wildcard (*.simsplus.io)
                                    |
  LAYER 1  --------  Nginx extracts subdomain, sets X-Subdomain header
                                    |
  LAYER 1  --------  Next.js middleware validates subdomain, routes to tenant UI
                                    |
  LAYER 2  --------  FastAPI TenantMiddleware resolves subdomain -> tenant_id
                      Sets app.current_tenant_id via set_config()
                                    |
  LAYER 5  --------  JWT validation: token.tenant_id must match request tenant_id
                                    |
  LAYER 4  --------  Service layer adds explicit .filter(Model.tenant_id == tenant_id)
                                    |
  LAYER 3  --------  PostgreSQL RLS: tenant_id = get_current_tenant_id()
                      Database refuses to return rows from other tenants
                                    |
  LAYER 6  --------  Redis keys prefixed: tenant:{tenant_id}:resource:id
                                    |
  LAYER 7  --------  S3 paths prefixed: {tenant_id}/resource_type/file
```

**Key principle:** Every layer assumes the layers above it have failed. RLS does not trust middleware. The service layer does not trust RLS. The JWT check does not trust the subdomain routing. This is defense-in-depth.

---

## 2. Layer 1: Subdomain Routing (DNS + Reverse Proxy + Frontend)

### 2.1 Cloudflare DNS Configuration

```
# Cloudflare DNS Records
# Type    Name              Content              Proxy
A         simsplus.io       <ELB IP>             Proxied
CNAME     *.simsplus.io     simsplus.io          Proxied
A         api.simsplus.io   <ELB IP>             Proxied
```

Cloudflare is configured with:
- **SSL/TLS:** Full (Strict) mode -- Cloudflare terminates SSL, re-encrypts to origin
- **Wildcard certificate:** Covers `*.simsplus.io` (included with Cloudflare Advanced Certificate Manager)
- **Page rules:** Cache static assets, bypass cache for API routes

### 2.2 Nginx Reverse Proxy Configuration

```nginx
# /etc/nginx/conf.d/simsplus.conf

upstream frontend {
    server frontend:3000;
    keepalive 32;
}

upstream backend {
    server backend:8000;
    keepalive 32;
}

limit_req_zone $binary_remote_addr zone=api_limit:10m rate=100r/s;
limit_req_zone $binary_remote_addr zone=auth_limit:10m rate=5r/m;

server {
    listen 80;
    server_name *.simsplus.io;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name *.simsplus.io;

    ssl_certificate     /etc/nginx/ssl/origin.pem;
    ssl_certificate_key /etc/nginx/ssl/origin-key.pem;

    # Extract subdomain from Host header
    set $subdomain "";
    if ($host ~* ^([a-z0-9][a-z0-9-]*[a-z0-9])\.simsplus\.io$) {
        set $subdomain $1;
    }
    if ($host ~* ^([a-z0-9])\.simsplus\.io$) {
        set $subdomain $1;
    }

    # Security headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # API routes -> FastAPI backend
    location /api/ {
        limit_req zone=api_limit burst=20 nodelay;
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Subdomain $subdomain;
        proxy_connect_timeout 10s;
        proxy_read_timeout 60s;
    }

    # Auth routes -- stricter rate limits
    location /api/v1/auth/ {
        limit_req zone=auth_limit burst=3 nodelay;
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Subdomain $subdomain;
    }

    # Health check (no rate limit)
    location /health {
        proxy_pass http://backend;
        proxy_set_header Host $host;
    }

    # Everything else -> Next.js frontend
    location / {
        proxy_pass http://frontend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Subdomain $subdomain;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    client_max_body_size 10M;
}

# Bare domain -- marketing site
server {
    listen 443 ssl http2;
    server_name simsplus.io www.simsplus.io;
    ssl_certificate     /etc/nginx/ssl/origin.pem;
    ssl_certificate_key /etc/nginx/ssl/origin-key.pem;
    location / {
        return 302 https://app.simsplus.io;
    }
}

# Central API -- requires X-Subdomain from client
server {
    listen 443 ssl http2;
    server_name api.simsplus.io;
    ssl_certificate     /etc/nginx/ssl/origin.pem;
    ssl_certificate_key /etc/nginx/ssl/origin-key.pem;
    location / {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 2.3 Next.js Middleware (Frontend Subdomain Extraction)

This file would live at `frontend/middleware.ts`:

```typescript
import { NextRequest, NextResponse } from "next/server";

const RESERVED_SUBDOMAINS = new Set([
  "www", "app", "api", "admin", "mail", "ftp", "status", "blog",
  "help", "support", "docs", "cdn", "assets", "staging", "dev",
  "test", "demo", "sandbox", "beta", "alpha", "portal", "login",
  "register", "signup", "dashboard", "billing", "payments",
  "webhooks", "graphql", "ws", "static", "media", "images",
  "files", "downloads", "uploads",
]);

const SUBDOMAIN_REGEX = /^[a-z0-9](?:[a-z0-9-]{2,61}[a-z0-9])?$/;
const PUBLIC_PATHS = ["/", "/login", "/register", "/forgot-password"];

export function middleware(request: NextRequest) {
  const hostname = request.headers.get("host") || "";
  const hostnameWithoutPort = hostname.split(":")[0];
  let subdomain: string | null = null;

  // Production: extract from *.simsplus.io
  if (hostnameWithoutPort.endsWith(".simsplus.io")) {
    const parts = hostnameWithoutPort.split(".");
    if (parts.length >= 3) {
      subdomain = parts[0].toLowerCase();
    }
  }

  // Development: extract from *.localhost
  if (hostnameWithoutPort.endsWith(".localhost")) {
    subdomain = hostnameWithoutPort.replace(".localhost", "").toLowerCase();
  }

  // Validate
  if (subdomain) {
    if (RESERVED_SUBDOMAINS.has(subdomain) || !SUBDOMAIN_REGEX.test(subdomain)) {
      subdomain = null;
    }
  }

  const pathname = request.nextUrl.pathname;
  if (!subdomain && !PUBLIC_PATHS.some((p) => pathname.startsWith(p))) {
    return NextResponse.redirect(new URL("https://app.simsplus.io/login"));
  }

  const requestHeaders = new Headers(request.headers);
  if (subdomain) {
    requestHeaders.set("x-subdomain", subdomain);
  }

  const response = NextResponse.next({ request: { headers: requestHeaders } });

  if (subdomain) {
    response.cookies.set("tenant-subdomain", subdomain, {
      httpOnly: false,
      secure: true,
      sameSite: "lax",
      path: "/",
      maxAge: 60 * 60 * 24,
    });
  }

  return response;
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
```

### 2.4 Development Environment: Local Subdomain Testing

**Option A (recommended): `*.localhost`** -- Modern browsers resolve `*.localhost` to `127.0.0.1` natively. Access as `http://presec.localhost:3000` (frontend) or `http://presec.localhost:8000` (backend). The existing `TenantMiddleware.extract_subdomain_from_host()` at line 127 of `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/middleware/tenant.py` already handles this.

**Option B: `/etc/hosts`** -- Add entries like `127.0.0.1 presec.localhost`.

**Option C: dnsmasq** -- `brew install dnsmasq` with `address=/localhost/127.0.0.1` for teams needing many subdomains.

### 2.5 Reserved Subdomain Protection -- Three-Level Sync

Reserved subdomains are protected at three levels that MUST be kept in sync:

1. **Database table** (`reserved_subdomains`) -- Authoritative source. Checked during onboarding.
2. **Python in-memory set** (`RESERVED_SUBDOMAINS` in `backend/app/middleware/tenant.py` line 86-90) -- Fast-path rejection without DB hit.
3. **TypeScript set** (`RESERVED_SUBDOMAINS` in `frontend/middleware.ts`) -- Prevents frontend from loading tenant context for reserved names.

---

## 3. Layer 2: Backend Middleware (Tenant Context Injection)

### 3.1 Middleware Execution Order

From `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/main.py` lines 87-88 -- middleware is applied in reverse order (last added runs first):

```python
app.add_middleware(TenantMiddleware)      # Runs 1st
app.add_middleware(RateLimitMiddleware)   # Runs 2nd
app.add_middleware(CORSMiddleware, ...)   # Runs 3rd
```

### 3.2 TenantMiddleware Detailed Flow

```
Request arrives
    |
    v
Clear previous tenant context (ContextVar)
    |
    v
OPTIONS request? --> Pass through (CORS preflight)
    |
    v
Public path? (PUBLIC_PATHS / PUBLIC_PATH_PREFIXES) --> Pass through
    |
    v
Extract subdomain from X-Subdomain header (set by nginx)
    |
    v
No X-Subdomain? --> Extract from Host header via extract_subdomain_from_host()
    |
    v
No subdomain? + /api/v1/* path? --> HTTP 400 "Tenant context required"
    |
    v
Query tenants table (raw SQL, unscoped session -- tenants has no RLS):
    SELECT id, subdomain, name, is_active FROM tenants
    WHERE subdomain = :subdomain AND deleted_at IS NULL
    |
    v
Not found? --> HTTP 404 "School not found"
Not active? --> HTTP 403 "School account suspended"
    |
    v
Set ContextVar: _tenant_context = { tenant_id, subdomain, name, is_active }
Set request.state: tenant_id, tenant_subdomain, tenant_name
    |
    v
Call next handler --> Finally: clear_tenant_context()
```

**Key detail:** The tenant lookup uses an **unscoped session** (`async_session_maker()` directly, without calling `set_tenant_context()`). This is correct because the `tenants` table has no RLS and the lookup occurs before tenant identity is known.

### 3.3 How `app.current_tenant_id` Is Set Per Request

The PostgreSQL session variable is set in `get_db()` (`/Users/harrymcninson/Documents/projects/sims-plus/backend/app/api/deps.py` lines 26-59), NOT in the middleware. The middleware stores `tenant_id` in `request.state`, and `get_db()` reads it:

```python
async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        try:
            tenant_id = getattr(request.state, "tenant_id", None)
            if tenant_id:
                await session.execute(
                    text("SELECT set_tenant_context(:tenant_id)"),
                    {"tenant_id": str(tenant_id)},
                )
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            try:
                await session.execute(text("SELECT clear_tenant_context()"))
            except Exception:
                pass
            await session.close()
```

### 3.4 SECURITY CONCERN (HIGH): Missing Tenant Context Guard in get_db()

The current `get_db()` does NOT raise an error when `tenant_id` is `None` for non-public routes. A middleware bug could silently allow queries without tenant context. Although RLS with NULL-bypass prevention means zero rows would be returned (not a data leak), it would cause silent failures.

**Recommended hardening:**

```python
async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        try:
            tenant_id = getattr(request.state, "tenant_id", None)
            if tenant_id:
                await session.execute(
                    text("SELECT set_tenant_context(:tenant_id)"),
                    {"tenant_id": str(tenant_id)},
                )
            else:
                path = request.url.path
                if path.startswith("/api/v1/") and not is_public_path(path):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Tenant context required but not set.",
                    )
            yield session
            await session.commit()
        except HTTPException:
            raise
        except Exception:
            await session.rollback()
            raise
        finally:
            try:
                await session.execute(text("SELECT clear_tenant_context()"))
            except Exception:
                pass
            await session.close()
```

### 3.5 UnscopedDatabaseSession

For operations that access data across tenants or before tenant context is known:

```python
async def get_unscoped_db() -> AsyncGenerator[AsyncSession, None]:
    """Database session WITHOUT tenant RLS context.

    Use ONLY for:
    - Tenant lookup in middleware (tenants table has no RLS)
    - Onboarding (creating new tenant + school + admin)
    - Platform admin operations (via separate audited superuser connection)
    - Audit log insertion (audit_logs has no RLS)
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

UnscopedDatabaseSession = Annotated[AsyncSession, Depends(get_unscoped_db)]
```

**CRITICAL:** With `FORCE ROW LEVEL SECURITY` and a non-superuser `sims_app_user`, an unscoped session CANNOT read/write tenant-scoped tables (schools, users, etc.) because `tenant_id = get_current_tenant_id()` evaluates to `tenant_id = NULL` which is FALSE. The unscoped session only works for non-RLS tables (tenants, reserved_subdomains, audit_logs). For onboarding, see Section 11.

---

## 4. Layer 3: Database RLS (PostgreSQL Row-Level Security)

### 4.1 Database Functions

```sql
-- =============================================================================
-- FUNCTION: set_tenant_context(tenant_uuid UUID)
-- Called by: get_db() dependency on every request with tenant context.
-- =============================================================================
CREATE OR REPLACE FUNCTION set_tenant_context(tenant_uuid UUID)
RETURNS VOID AS $$
BEGIN
    PERFORM set_config('app.current_tenant_id', tenant_uuid::TEXT, false);
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- FUNCTION: clear_tenant_context()
-- Called in: finally block of get_db().
-- =============================================================================
CREATE OR REPLACE FUNCTION clear_tenant_context()
RETURNS VOID AS $$
BEGIN
    PERFORM set_config('app.current_tenant_id', '', false);
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- FUNCTION: get_current_tenant_id()
-- Used by: ALL RLS policies.
--
-- SECURITY: Returns NULL when no tenant context is set.
--   The policy `tenant_id = get_current_tenant_id()` naturally prevents
--   access because `tenant_id = NULL` evaluates to FALSE in SQL.
--   There is NO `OR get_current_tenant_id() IS NULL` bypass.
-- =============================================================================
CREATE OR REPLACE FUNCTION get_current_tenant_id()
RETURNS UUID AS $$
DECLARE
    tenant_str TEXT;
    tenant_uuid UUID;
BEGIN
    tenant_str := current_setting('app.current_tenant_id', true);

    IF tenant_str IS NULL OR tenant_str = '' THEN
        RETURN NULL;
    END IF;

    BEGIN
        tenant_uuid := tenant_str::UUID;
        RETURN tenant_uuid;
    EXCEPTION WHEN OTHERS THEN
        RETURN NULL;
    END;
END;
$$ LANGUAGE plpgsql STABLE;
```

### 4.2 RLS Policy Template (Used for EVERY Tenant-Scoped Table)

```sql
-- USING clause: controls which rows can be SEEN (SELECT, UPDATE, DELETE)
-- WITH CHECK clause: controls which rows can be WRITTEN (INSERT, UPDATE)
--
-- NULL BYPASS PREVENTION:
--   When get_current_tenant_id() returns NULL (no context),
--   `tenant_id = NULL` evaluates to FALSE. No rows visible.
--   There is NO `OR get_current_tenant_id() IS NULL` clause.
--
-- NO PLATFORM ADMIN BYPASS:
--   Platform admin uses a superuser connection (bypasses FORCE ROW LEVEL
--   SECURITY by PostgreSQL design). No RLS policy bypass needed.

ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_{table_name} ON {table_name}
    FOR ALL
    USING (tenant_id = get_current_tenant_id())
    WITH CHECK (tenant_id = get_current_tenant_id());

GRANT SELECT, INSERT, UPDATE, DELETE ON {table_name} TO sims_app_user;
```

### 4.3 Why NULL Bypass Is Prevented

```
Scenario: Request arrives without tenant context (middleware bug, direct API call)

1. get_db() does not call set_tenant_context()
2. get_current_tenant_id() returns NULL
3. RLS evaluates: tenant_id = NULL
4. In SQL, NULL = NULL is FALSE (three-valued logic)
5. ZERO rows returned. No data leaked.

PRIOR VULNERABILITY (F1 CRITICAL, now fixed):
  The comprehensive_rls migration at line 82-84 had:
    OR (get_current_tenant_id() IS NULL)
  This meant ANY request without tenant context could see ALL rows.
  Removed in fix_rls_null_bypass migration.
```

### 4.4 Sprint 1-2 Table RLS Policies

```sql
-- tenants: NO RLS (global registry, queried before tenant is known)
-- reserved_subdomains: NO RLS (platform configuration)
-- audit_logs: NO RLS (cross-tenant, nullable tenant_id for filtering only)

-- schools: YES
ALTER TABLE schools ENABLE ROW LEVEL SECURITY;
ALTER TABLE schools FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_schools ON schools
    FOR ALL
    USING (tenant_id = get_current_tenant_id())
    WITH CHECK (tenant_id = get_current_tenant_id());
GRANT SELECT, INSERT, UPDATE, DELETE ON schools TO sims_app_user;

-- users: YES
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE users FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_users ON users
    FOR ALL
    USING (tenant_id = get_current_tenant_id())
    WITH CHECK (tenant_id = get_current_tenant_id());
GRANT SELECT, INSERT, UPDATE, DELETE ON users TO sims_app_user;
```

### 4.5 Reusable Migration Helper

```python
# Use in every migration that creates a new tenant-scoped table

from sqlalchemy import text

def enable_rls_for_table(connection, table_name: str) -> None:
    """Enable RLS with the standard tenant isolation policy."""
    connection.execute(text(f"""
        DO $$
        BEGIN
            EXECUTE (
                SELECT COALESCE(
                    string_agg(
                        'DROP POLICY IF EXISTS ' || policyname || ' ON {table_name};',
                        E'\\n'
                    ),
                    ''
                )
                FROM pg_policies
                WHERE tablename = '{table_name}'
            );
        EXCEPTION WHEN OTHERS THEN NULL;
        END $$;
    """))
    connection.execute(text(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY"))
    connection.execute(text(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY"))
    connection.execute(text(f"""
        CREATE POLICY tenant_isolation_{table_name} ON {table_name}
        FOR ALL
        USING (tenant_id = get_current_tenant_id())
        WITH CHECK (tenant_id = get_current_tenant_id())
    """))
    connection.execute(text(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table_name} TO sims_app_user"
    ))

def disable_rls_for_table(connection, table_name: str) -> None:
    """Remove RLS (for downgrade)."""
    connection.execute(text(
        f"DROP POLICY IF EXISTS tenant_isolation_{table_name} ON {table_name}"
    ))
    connection.execute(text(f"ALTER TABLE {table_name} NO FORCE ROW LEVEL SECURITY"))
    connection.execute(text(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY"))
```

### 4.6 Index Design for RLS Performance

```sql
-- Every tenant-scoped table needs at minimum:
CREATE INDEX ix_{table}_tenant_id ON {table} (tenant_id);

-- For active records queries:
CREATE INDEX ix_{table}_tenant_active ON {table} (tenant_id)
    WHERE deleted_at IS NULL;

-- Unique constraints MUST include tenant_id:
-- WRONG: UNIQUE(student_id_number)
-- RIGHT: UNIQUE(tenant_id, student_id_number) WHERE deleted_at IS NULL
```

**Special case -- `users.email`:** Currently globally unique (`unique=True` on the column). This is intentional to prevent the same person having accounts across schools with the same email. If this requirement changes, switch to `UNIQUE(tenant_id, email) WHERE deleted_at IS NULL`.

---

## 5. Layer 4: Application Service Layer (Defense-in-Depth)

### 5.1 Explicit `tenant_id` Filtering Pattern

```python
# CORRECT -- defense-in-depth
class StudentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_student(self, student_id: UUID, tenant_id: UUID) -> Student | None:
        result = await self.db.execute(
            select(Student).where(
                Student.id == student_id,
                Student.tenant_id == tenant_id,  # EXPLICIT tenant filter
                Student.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def create_student(self, tenant_id: UUID, **data) -> Student:
        student = Student(
            tenant_id=tenant_id,  # EXPLICIT tenant assignment
            **data,
        )
        self.db.add(student)
        await self.db.flush()
        await self.db.refresh(student)
        return student
```

```python
# WRONG -- relying solely on RLS (violates defense-in-depth)
async def get_student(self, student_id: UUID) -> Student | None:
    result = await self.db.execute(
        select(Student).where(Student.id == student_id)
    )
    return result.scalar_one_or_none()
```

### 5.2 Service Layer Rules

1. **Every query** on a tenant-scoped table MUST include `.where(Model.tenant_id == tenant_id)`.
2. **Every insert** MUST set `tenant_id=tenant_id` on the model.
3. **IDOR prevention:** When a URL has nested IDs (e.g., `/classes/{class_id}/students/{student_id}`), verify the child belongs to the parent within the same tenant.
4. **Race conditions:** Use `pg_advisory_xact_lock` for sequential ID generation (student IDs, invoice numbers). Use `.with_for_update()` for read-modify-write patterns.
5. **Soft deletes:** Always include `Model.deleted_at.is_(None)` in queries.
6. **`flush()/refresh()` not `commit()`** -- endpoint middleware handles commit.
7. **ILIKE searches** must use `escape_ilike()` from `app.utils.sanitize`.

---

## 6. Layer 5: JWT Validation (Auth Token Tenant Binding)

### 6.1 Token Structure

**Access Token (15-minute expiry):**

```json
{
  "sub": "550e8400-e29b-41d4-a716-446655440000",
  "tenant_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "tenant_subdomain": "presec",
  "school_id": "a3bb189e-8bf9-3888-9912-ace4e6543002",
  "role": "school_admin",
  "permissions": ["school.read", "school.update", "users.*", "students.*"],
  "email": "admin@presec.edu.gh",
  "type": "access",
  "iat": 1739577600,
  "exp": 1739578500
}
```

**Refresh Token (7-day expiry):**

```json
{
  "sub": "550e8400-e29b-41d4-a716-446655440000",
  "tenant_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "type": "refresh",
  "iat": 1739577600,
  "exp": 1740182400
}
```

### 6.2 Cross-Tenant Token Rejection

From `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/api/deps.py` lines 198-241:

The `validate_token_tenant` dependency compares `token.tenant_id` with `request.state.tenant_id`. If they do not match, HTTP 403 is returned.

**Attack scenario prevented:** A teacher at `presec.simsplus.io` gets a valid JWT. They try `achimota.simsplus.io/api/v1/students` with the same JWT. Middleware resolves `achimota` to tenant B's UUID. JWT contains tenant A's UUID. Comparison fails. HTTP 403.

### 6.3 Recommended Auth Dependency for All Protected Endpoints

Use `ValidatedUser` (`/Users/harrymcninson/Documents/projects/sims-plus/backend/app/api/deps.py` line 340). It performs:
1. JWT signature and expiry validation
2. Token type check (`type == "access"`)
3. Token blacklist check (Redis)
4. User-level mass revocation check
5. Cross-tenant validation (`token.tenant_id == request.state.tenant_id`)

### 6.4 Token Blacklisting via Redis

From `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/services/token_blacklist.py`:

| Key Pattern | Value | TTL | Trigger |
|-------------|-------|-----|---------|
| `token_blacklist:{sha256(token)}` | `"1"` | Token remaining TTL + 60s | Logout |
| `user_token_blacklist:{user_id}` | Unix timestamp | 7 days | Password change, account suspension |

**Triggers for token invalidation:**
- **Logout:** Individual token blacklisted.
- **Password change:** All user tokens mass-revoked.
- **Account suspension:** All user tokens mass-revoked.
- **Tenant suspension:** Should invalidate all sessions (future: `tenant_token_blacklist:{tenant_id}`).

### 6.5 Refresh Token Tenant Scoping

During token refresh (`/Users/harrymcninson/Documents/projects/sims-plus/backend/app/services/auth.py` lines 322-412):
1. Decode refresh token
2. Verify `payload.type == "refresh"`
3. Look up user by `payload.sub`
4. Verify `user.tenant_id == request tenant_id`
5. Verify `payload.tenant_id == request tenant_id`
6. Issue new access + refresh pair

---

## 7. Layer 6: Cache Isolation (Redis)

### 7.1 Key Naming Convention

| Key Pattern | TTL | Purpose |
|-------------|-----|---------|
| `tenant:{tenant_id}:school:{school_id}` | 1 hour | Cached school profile |
| `tenant:{tenant_id}:user:{user_id}` | 15 min | Cached user profile |
| `tenant:{tenant_id}:students:count` | 5 min | Student count for limits |
| `tenant:{tenant_id}:academic:current_year` | 1 hour | Current academic year |
| `tenant:{tenant_id}:academic:current_term` | 1 hour | Current term |
| `tenant:{tenant_id}:settings:{key}` | 1 hour | Tenant-specific settings |
| `tenant:subdomain:{subdomain}` | 10 min | Subdomain-to-tenant_id lookup |
| `rate_limit:{type}:{identifier}` | Per config | Rate limiting counters |
| `token_blacklist:{token_hash}` | Token TTL | Blacklisted JWT hashes |
| `user_token_blacklist:{user_id}` | 7 days | Mass token revocation |

### 7.2 Cache Key Generator

```python
class CacheKeys:
    """Centralized cache key generation for tenant-scoped Redis keys."""

    @staticmethod
    def school(tenant_id: str, school_id: str) -> str:
        return f"tenant:{tenant_id}:school:{school_id}"

    @staticmethod
    def user(tenant_id: str, user_id: str) -> str:
        return f"tenant:{tenant_id}:user:{user_id}"

    @staticmethod
    def student_count(tenant_id: str) -> str:
        return f"tenant:{tenant_id}:students:count"

    @staticmethod
    def tenant_by_subdomain(subdomain: str) -> str:
        return f"tenant:subdomain:{subdomain}"

    @staticmethod
    def rate_limit(limit_type: str, identifier: str) -> str:
        return f"rate_limit:{limit_type}:{identifier}"

    @staticmethod
    def token_blacklist(token_hash: str) -> str:
        return f"token_blacklist:{token_hash}"
```

### 7.3 Cache Isolation Rules

1. **NEVER construct a tenant-scoped cache key without `tenant_id`.** The `tenant:{tenant_id}:...` prefix makes cross-tenant bleed impossible.
2. **NEVER use user-provided values as the first key segment.**
3. **Flush tenant cache on suspension/deletion:** `SCAN` for keys matching `tenant:{tenant_id}:*` and delete.

### 7.4 Tenant Subdomain Lookup Cache

The middleware queries the `tenants` table on every request. To reduce database load, cache the result:

```python
async def _get_tenant_by_subdomain(self, db, subdomain):
    cache_key = f"tenant:subdomain:{subdomain}"
    cached = await self.redis.get(cache_key)
    if cached:
        return json.loads(cached)

    result = await db.execute(...)
    tenant = ...

    if tenant:
        await self.redis.setex(cache_key, 600, json.dumps(tenant))  # 10 min

    return tenant
```

Invalidate on tenant suspension/deactivation/deletion.

---

## 8. Layer 7: Storage Isolation (S3)

### 8.1 Path Structure

| File Type | Path Pattern | Example |
|-----------|-------------|---------|
| School logo | `{tenant_id}/logos/{uuid}.{ext}` | `7c9e.../logos/a1b2c3.png` |
| User avatar | `{tenant_id}/avatars/{uuid}.{ext}` | `7c9e.../avatars/d4e5f6.jpg` |
| Student photo | `{tenant_id}/photos/students/{uuid}.{ext}` | `7c9e.../photos/students/g7h8.jpg` |
| Staff photo | `{tenant_id}/photos/staff/{uuid}.{ext}` | `7c9e.../photos/staff/i9j0.jpg` |
| CSV import | `{tenant_id}/documents/imports/{year}/{uuid}.csv` | `7c9e.../documents/imports/2026/k1l2.csv` |
| Report card | `{tenant_id}/documents/reports/{year}/{term}/report-cards/{student_id}.pdf` | |
| Invoice PDF | `{tenant_id}/documents/invoices/{year}/{term}/{invoice_no}.pdf` | |
| Excel export | `{tenant_id}/exports/{year}/{uuid}.xlsx` | |

### 8.2 Current S3 Service Issue (MEDIUM)

The current `S3Service.generate_unique_key()` at `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/services/s3.py` line 214-233 uses `{folder}/{tenant_id}/{uuid}.{ext}` (e.g., `logos/7c9e.../a1b2.png`).

**Recommended change:** Switch to `{tenant_id}/{folder}/{uuid}.{ext}`. The tenant-first pattern enables:
- IAM policies scoped to `{tenant_id}/*` prefix
- Easier per-tenant data export (copy entire `{tenant_id}/` prefix)
- Consistent "tenant as namespace" mental model

```python
def generate_unique_key(
    self, folder: str, tenant_id: str, original_filename: str
) -> str:
    ext = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else "png"
    unique_id = uuid.uuid4().hex
    return f"{tenant_id}/{folder}/{unique_id}.{ext}"  # tenant-first
```

### 8.3 Content Validation

```python
UPLOAD_LIMITS = {
    "logos":     {"max_size": 2 * 1024 * 1024,  "allowed_types": {"image/png", "image/jpeg", "image/webp", "image/svg+xml"}},
    "avatars":   {"max_size": 1 * 1024 * 1024,  "allowed_types": {"image/png", "image/jpeg", "image/webp"}},
    "photos":    {"max_size": 5 * 1024 * 1024,  "allowed_types": {"image/png", "image/jpeg", "image/webp"}},
    "documents": {"max_size": 10 * 1024 * 1024, "allowed_types": {"application/pdf", "text/csv", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}},
}
```

### 8.4 Pre-Signed URLs for Private Files

```python
def generate_presigned_url(self, key: str, expiry_seconds: int = 3600) -> str:
    """Generate a pre-signed URL. The key MUST start with {tenant_id}/ prefix."""
    return self.client.generate_presigned_url(
        "get_object",
        Params={"Bucket": self.bucket, "Key": key},
        ExpiresIn=expiry_seconds,
    )
```

---

## 9. Database User Separation

### 9.1 Two-User Strategy

| Role | Type | RLS Behavior | Used By |
|------|------|-------------|---------|
| `sims_admin` / `postgres` | Superuser | Bypasses all RLS | Alembic migrations, DBA operations, platform admin |
| `sims_app_user` | Non-superuser | Subject to RLS | FastAPI application, Celery workers |

### 9.2 Database Initialization Script

The current script at `/Users/harrymcninson/Documents/projects/sims-plus/backend/scripts/init-db.sql` does NOT create `sims_app_user`. It needs to be updated:

```sql
-- Create application user (NON-SUPERUSER, RLS enforced)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'sims_app_user') THEN
        CREATE ROLE sims_app_user WITH LOGIN PASSWORD 'CHANGE_ME_IN_PRODUCTION';
    END IF;
END $$;

GRANT CONNECT ON DATABASE sims_plus TO sims_app_user;
GRANT CONNECT ON DATABASE sims_plus_test TO sims_app_user;
GRANT USAGE ON SCHEMA public TO sims_app_user;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO sims_app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO sims_app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT EXECUTE ON FUNCTIONS TO sims_app_user;
```

### 9.3 Connection Strings

```bash
# Application (RLS enforced)
DATABASE_URL=postgresql+asyncpg://sims_app_user:password@db:5432/sims_plus

# Alembic (superuser, bypasses RLS)
ALEMBIC_DATABASE_URL=postgresql+asyncpg://postgres:admin_password@db:5432/sims_plus
```

### 9.4 CRITICAL: Current docker-compose uses `postgres` superuser

The `docker-compose.yml` at `/Users/harrymcninson/Documents/projects/sims-plus/docker-compose.yml` line 57 connects the backend as the postgres superuser. This means RLS is completely bypassed in development. **For staging/production, the backend MUST connect as `sims_app_user`.**

---

## 10. Database Session Management

### 10.1 Transaction Lifecycle

```
Request arrives
    |
get_db() creates AsyncSession from pool
    |
set_tenant_context(tenant_id) -- sets app.current_tenant_id on connection
    |
Endpoint handler + service layer run: add(), flush(), refresh()
    |
Success? --> session.commit() | Failure? --> session.rollback()
    |
clear_tenant_context() in finally block
    |
session.close() -- returns connection to pool
```

### 10.2 `set_config` Scope

`set_config('app.current_tenant_id', ..., false)` sets the variable at **session level** (persists until connection closed or value changed). The `clear_tenant_context()` in `finally` resets it. Even if clearing fails, the next request's `set_tenant_context()` call overwrites the stale value.

---

## 11. Onboarding Tenant Creation Flow

### 11.1 Step-by-Step

```
1. POST /api/v1/onboarding/check-subdomain (public, no tenant context)
   - Validates format, checks reserved_subdomains, checks tenants table
   - Returns { available: true/false, suggestions: [...] }

2. POST /api/v1/onboarding/register (public, no tenant context)
   OnboardingService.register_school():
   a. Validate subdomain availability (race condition safe with unique constraint)
   b. Check email does not exist globally
   c. CREATE tenant (tenants table, NO RLS)
   d. SET TENANT CONTEXT for the new tenant:
      await db.execute(text("SELECT set_tenant_context(:tid)"), {"tid": str(tenant.id)})
   e. CREATE school (schools table, HAS RLS -- now matches context)
   f. CREATE admin user (users table, HAS RLS -- now matches context)
   g. flush() + refresh() all three records
   h. Send welcome email (non-blocking)
   i. Return { tenant, school, admin_user, portal_url }

3. Frontend redirects to: https://{subdomain}.simsplus.io/login
```

### 11.2 CRITICAL: Onboarding Must Set Context After Tenant Creation

The current `OnboardingService` at `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/services/onboarding.py` creates the tenant, school, and admin user without calling `set_tenant_context()`. With `FORCE ROW LEVEL SECURITY` and a non-superuser, the INSERT into `schools` and `users` would fail because `WITH CHECK (tenant_id = get_current_tenant_id())` would evaluate as `tenant_id = NULL` which is FALSE.

**Fix needed in `register_school()`:** Add this after `await self.db.flush()` on the tenant:

```python
# Set tenant context so RLS allows inserts into schools and users
await self.db.execute(
    text("SELECT set_tenant_context(:tenant_id)"),
    {"tenant_id": str(tenant.id)},
)
```

### 11.3 Subdomain Validation Rules

From `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/services/tenant.py`:

- Length: 4-63 characters
- Characters: lowercase letters (a-z), digits (0-9), hyphens (-)
- Cannot start or end with a hyphen
- Regex: `^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]+$`
- Not in reserved_subdomains table
- Not already taken by another tenant

---

## 12. Table Classification

| Table | Tenant-Scoped? | RLS? | Soft Delete? | Notes |
|-------|:-:|:-:|:-:|-------|
| `tenants` | NO | NO | YES | Global registry |
| `reserved_subdomains` | NO | NO | NO | Platform config |
| `audit_logs` | NO | NO | NO (immutable) | Nullable `tenant_id` for filtering |
| `schools` | YES | YES | YES | One+ per tenant |
| `users` | YES | YES | YES | All accounts |
| `students` | YES | YES | YES | Student profiles |
| `guardians` | YES | YES | YES | Guardian records |
| `student_guardians` | YES | YES | NO (junction) | Hard delete |
| `academic_years` | YES | YES | YES | Year definitions |
| `terms` | YES | YES | YES | Term periods |
| `classes` | YES | YES | YES | Class levels |
| `class_sections` | YES | YES | YES | Sections |
| `subjects` | YES | YES | YES | Subject catalog |
| `class_subjects` | YES | YES | NO (junction) | Hard delete |
| `grading_scales` | YES | YES | YES | Grade systems |
| `grades` | YES | YES | YES | Grade definitions |
| `departments` | YES | YES | YES | Staff departments |
| `staff` | YES | YES | YES | Staff profiles |
| `exams` | YES | YES | YES | Exam definitions |
| `exam_scores` | YES | YES | NO | Student scores |
| `continuous_assessments` | YES | YES | NO | CA scores |
| `term_reports` | YES | YES | YES | Report cards |
| `fee_types` | YES | YES | YES | Fee categories |
| `fee_structures` | YES | YES | YES | Fee templates |
| `invoices` | YES | YES | YES | Student invoices |
| `payments` | YES | YES | YES | Payment records |
| `scholarships` | YES | YES | YES | Scholarships |
| `credit_notes` | YES | YES | YES | Credit notes |
| `finance_audit_log` | YES | YES | NO (immutable) | Finance audit |
| *All other module tables* | YES | YES | See above | Per convention |

### Tables Without `tenant_id` -- Justification

| Table | Justification |
|-------|---------------|
| `tenants` | IS the tenant entity; scoping it to itself is circular |
| `reserved_subdomains` | Platform configuration shared across all tenants |
| `audit_logs` | Must be writable without tenant context (failed auth). Cross-tenant queryable by platform admins. |

---

## 13. Security Hardening Checklist

### CRITICAL

- [x] **NULL tenant_id bypass prevention.** `tenant_id = get_current_tenant_id()` with no `IS NULL` fallback.
- [x] **No `is_platform_admin` RLS bypass.** Removed. Platform admin uses superuser connection.
- [ ] **Database user separation in production.** Backend MUST connect as `sims_app_user`, not `postgres`. Current docker-compose uses `postgres`.

### HIGH

- [x] **Cross-tenant token validation.** `validate_token_tenant` rejects mismatched tokens.
- [ ] **`get_db()` should raise 400 without tenant context** for non-public routes (recommended in Section 3.4).
- [x] **Token blacklisting.** Logout/password change invalidates tokens via Redis.
- [x] **Account lockout.** 5 failed attempts = 30-minute lockout.
- [x] **Audit logging.** Auth events logged with separate DB connection.
- [ ] **Onboarding must set tenant context after creating tenant** (Section 11.2).

### MEDIUM

- [x] **Error sanitization.** Production returns generic "Internal server error".
- [ ] **CORS for wildcard subdomains.** Use `allow_origin_regex=r"https://[a-z0-9][a-z0-9-]*[a-z0-9]\.simsplus\.io"` for production.
- [ ] **S3 path structure.** Migrate from `{folder}/{tenant_id}/` to `{tenant_id}/{folder}/`.
- [x] **Rate limiting.** Redis sliding window implemented.

### LOW

- [ ] **Reserved subdomain sync.** Keep database, Python set, and TypeScript set aligned.
- [ ] **Celery worker tenant context.** Background tasks must call `set_tenant_context()` before and `clear_tenant_context()` after.
- [ ] **Connection pool cleanup.** Verify `clear_tenant_context()` always executes.

---

## 14. Testing Strategy

### 14.1 Two-Engine Test Pattern

```python
# Admin engine (superuser) -- for DDL: create tables, enable RLS, seed data
admin_engine = create_async_engine(
    "postgresql+asyncpg://postgres:password@localhost:5432/sims_plus_test",
    poolclass=NullPool,
)

# App engine (non-superuser) -- for test queries (RLS enforced)
app_engine = create_async_engine(
    "postgresql+asyncpg://sims_app_user:password@localhost:5432/sims_plus_test",
    poolclass=NullPool,
)
```

### 14.2 Tenant Isolation Test Pattern

```python
@pytest.mark.asyncio
async def test_rls_prevents_cross_tenant_access(app_session):
    tenant_a_id, tenant_b_id = uuid4(), uuid4()

    # Insert as Tenant A
    await app_session.execute(
        text("SELECT set_tenant_context(CAST(:tid AS uuid))"),
        {"tid": str(tenant_a_id)},
    )
    await app_session.execute(
        text("INSERT INTO students (...) VALUES (CAST(:tid AS uuid), ...)"),
        {"tid": str(tenant_a_id)},
    )

    # Insert as Tenant B
    await app_session.execute(
        text("SELECT set_tenant_context(CAST(:tid AS uuid))"),
        {"tid": str(tenant_b_id)},
    )
    await app_session.execute(
        text("INSERT INTO students (...) VALUES (CAST(:tid AS uuid), ...)"),
        {"tid": str(tenant_b_id)},
    )

    # Query as Tenant A -- should only see Tenant A's data
    await app_session.execute(
        text("SELECT set_tenant_context(CAST(:tid AS uuid))"),
        {"tid": str(tenant_a_id)},
    )
    app_session.expire_all()  # CRITICAL after context switch
    result = await app_session.execute(text("SELECT * FROM students"))
    assert len(result.fetchall()) == 1

    # Query with no context -- should see zero rows
    await app_session.execute(text("SELECT clear_tenant_context()"))
    app_session.expire_all()
    result = await app_session.execute(text("SELECT * FROM students"))
    assert len(result.fetchall()) == 0
```

### 14.3 Test Infrastructure Notes

1. **`CAST(:param AS uuid)`:** asyncpg sends Python `str` as PostgreSQL `VARCHAR`. Without explicit cast, UUID comparisons in RLS fail silently.
2. **`expire_all()` after context switch:** SQLAlchemy identity map caches loaded objects. Must expire after changing tenant context.
3. **`TENANT_SCOPED_TABLES` list:** Test conftest must maintain a complete list of all tenant-scoped tables for comprehensive RLS verification.

---

## 15. Platform Admin Access Patterns

Platform admins need cross-tenant access for support, analytics, and management. This MUST NOT use RLS policy bypasses.

### Separate Superuser Connection Pool

```python
# backend/app/db/admin_session.py
admin_engine = create_async_engine(
    str(settings.ADMIN_DATABASE_URL),
    pool_size=2,      # Minimal pool -- limit exposure
    max_overflow=3,
)
admin_session_maker = async_sessionmaker(admin_engine, class_=AsyncSession, expire_on_commit=False)
```

### Platform Admin Endpoints

```python
@router.get("/platform-admin/tenants", dependencies=[Depends(require_permissions("*"))])
async def list_all_tenants(user: ValidatedUser, db: AdminDatabaseSession):
    await audit_service.log(event_type="platform_admin.tenants.list", user_id=UUID(user["user_id"]))
    result = await db.execute(select(Tenant))
    return result.scalars().all()
```

Every cross-tenant access is fully audited: who, what, which tenant, when, from where.

---

## 16. Edge Cases and Operational Concerns

### 16.1 Tenant Data Export

Use superuser connection with explicit `tenant_id` filter:
```sql
SELECT set_config('app.current_tenant_id', '7c9e...', false);
COPY (SELECT * FROM students) TO '/tmp/students.csv' CSV HEADER;
```

### 16.2 Tenant Deactivation

1. Set `tenants.is_active = false`
2. Delete Redis keys matching `tenant:{tenant_id}:*`
3. Delete `tenant:subdomain:{subdomain}` cache
4. Mass-revoke all tokens: `tenant_token_blacklist:{tenant_id}`
5. Do NOT delete data (tenant may reactivate)

### 16.3 Background Jobs (Celery)

Every Celery task MUST:
```python
await session.execute(text("SELECT set_tenant_context(CAST(:tid AS uuid))"), {"tid": tenant_id})
# ... do work with defense-in-depth tenant_id filtering ...
await session.execute(text("SELECT clear_tenant_context()"))
```

### 16.4 Webhooks / External Callbacks

Extract `tenant_id` from your own stored metadata (not from the webhook payload). Validate webhook signature. Set tenant context before processing.

### 16.5 CORS for Production

```python
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https://[a-z0-9][a-z0-9-]*[a-z0-9]\.simsplus\.io",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Subdomain", "X-Request-ID", "Accept"],
)
```

---

## Appendix A: Migration Chain

```
8176a9079aeb (initial schema)
  -> add_subdomain_rls (subdomain, reserved_subdomains, set_tenant_context, RLS on users)
    -> security_fixes_001
      -> add_schools_table
        -> comprehensive_rls (RLS on schools+users, BUT with NULL bypass -- VULNERABLE)
          -> 549287f1f9df
            -> sprint3_4_academic
              -> fix_rls_null_bypass (REMOVE NULL bypass -- CRITICAL FIX)
                -> remove_platform_admin_bypass (REMOVE is_platform_admin -- HIGH FIX)
                  -> [Sprint 5+ migrations...]
```

## Appendix B: Quick Reference -- Adding New Tables

1. Add `TenantMixin` (adds `tenant_id UUID NOT NULL`)
2. Add `SoftDeleteMixin` for entity tables (skip for junction tables)
3. Use `lazy="raise"` on all relationships
4. Use `values_callable=lambda x: [e.value for e in x]` for enums
5. In migration: call `enable_rls_for_table(connection, table_name)`
6. Add composite index: `(tenant_id, id)` minimum
7. Include `tenant_id` in unique constraints
8. In service layer: ALWAYS filter by `tenant_id`
9. Update `TENANT_SCOPED_TABLES` in test conftest

## Appendix C: Threat Model

| Threat | Mitigation | Layer |
|--------|-----------|-------|
| Access another tenant's subdomain with stolen token | JWT cross-tenant validation rejects | JWT |
| Middleware bug skips tenant context | `tenant_id = NULL` is FALSE, zero rows | RLS |
| Developer forgets tenant filter in service | RLS prevents cross-tenant access | RLS |
| Cache bleed between tenants | All keys include `tenant:{tenant_id}:` | Cache |
| S3 file from Tenant A accessible to Tenant B | Paths include `{tenant_id}/` prefix | Storage |
| Platform admin bypass exploited | No bypass exists; uses superuser connection | RLS |
| Stale context on recycled connection | `clear_tenant_context()` in finally; next request overwrites | Middleware |

---

Now let me save key findings to agent memory.
The directory exists but is empty. Let me note: I was unable to write the design document to `/Users/harrymcninson/Documents/projects/sims-plus/docs/MULTI_TENANCY_DESIGN.md` because Write permissions were denied. The complete document is provided above in my response. You can save it to that location manually, or grant me Write permissions and I can create the file.

Here is a summary of **security findings discovered during the codebase review** that require immediate attention:

---

### Findings Requiring Action

**1. CRITICAL -- `docker-compose.yml` uses `postgres` superuser for the application**
File: `/Users/harrymcninson/Documents/projects/sims-plus/docker-compose.yml` line 57
The backend connects as the postgres superuser, which means `FORCE ROW LEVEL SECURITY` is completely bypassed. In staging and production, the backend MUST connect as `sims_app_user` (non-superuser).

**2. CRITICAL -- `init-db.sql` does not create `sims_app_user`**
File: `/Users/harrymcninson/Documents/projects/sims-plus/backend/scripts/init-db.sql`
The initialization script creates extensions and a test database but does not create the `sims_app_user` role needed for RLS enforcement. The SQL for creating this role is provided in Section 9.2 of the document.

**3. HIGH -- Onboarding service does not set tenant context before inserting into RLS-protected tables**
File: `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/services/onboarding.py` lines 131-168
After creating the tenant record (which succeeds because `tenants` has no RLS), the service inserts into `schools` and `users` without calling `set_tenant_context()`. With `FORCE ROW LEVEL SECURITY` and a non-superuser, these inserts would be rejected by the `WITH CHECK` clause. This only works today because the application connects as `postgres` (superuser). Once you switch to `sims_app_user`, onboarding will break unless you add `set_tenant_context()` after the tenant flush.

**4. HIGH -- `get_db()` does not raise an error when tenant context is missing for non-public routes**
File: `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/api/deps.py` lines 26-59
If middleware has a bug and `request.state.tenant_id` is None, `get_db()` silently proceeds without setting tenant context. While RLS prevents data leakage (NULL = NULL is FALSE), queries will return empty results without any error. The recommended fix is in Section 3.4.

**5. MEDIUM -- S3 path structure is `{folder}/{tenant_id}/` instead of `{tenant_id}/{folder}/`**
File: `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/services/s3.py` line 233
The tenant-first path enables IAM scoping, easier per-tenant export, and a consistent namespace model.

**6. MEDIUM -- `comprehensive_rls` migration still has NULL bypass and platform admin bypass in its source**
File: `/Users/harrymcninson/Documents/projects/sims-plus/backend/alembic/versions/20260104_0500_comprehensive_rls.py` lines 80-98
The later migrations (`fix_rls_null_bypass`, `remove_platform_admin_bypass`) fix this, but the original migration source is misleading. The actual database state is correct after all migrations run.