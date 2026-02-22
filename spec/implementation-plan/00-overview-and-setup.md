# SIMS Plus -- Implementation Plan: Overview & Setup

**Document:** 00 of 04 (Master Document)
**Version:** 1.0
**Date:** 15 February 2026
**Author:** Harry McNinson
**Status:** Ready for Implementation
**Sprint Window:** 4 weeks (2 x 2-week sprints)

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture Decisions](#2-architecture-decisions-already-made)
3. [Technology Stack](#3-technology-stack-fixed)
4. [Team Structure & Roles](#4-team-structure--roles)
5. [Sprint Structure](#5-sprint-structure)
6. [Critical Path](#6-critical-path)
7. [Pre-Sprint Checklist](#7-pre-sprint-checklist)
8. [Infrastructure Requirements](#8-infrastructure-requirements)
9. [Document Index](#9-document-index)
10. [7-Layer Defense-in-Depth Architecture](#10-7-layer-defense-in-depth-architecture)
11. [Known Issues in Existing Codebase](#11-known-issues-in-existing-codebase-must-fix-in-sprint-1-2)
12. [Project Structure](#12-project-structure)

---

## 1. Project Overview

**SIMS Plus** (School Information Management System Plus) is a multi-tenant SaaS platform for managing schools in Ghana. It supports educational institutions from Preschool through to Senior High School (SHS), serving both public and private sectors.

### Core Architecture Principles

- **Subdomain-based multi-tenancy:** Each school operates at its own subdomain -- `{school-code}.simsplus.io`. Presbyterian Boys' Secondary School is at `presec.simsplus.io`, Achimota School is at `achimota.simsplus.io`, and so on.
- **Shared infrastructure:** ONE PostgreSQL database, ONE application cluster, ONE Redis instance. All schools share the same running infrastructure. There is no per-tenant provisioning.
- **Data isolation via PostgreSQL Row-Level Security (RLS):** Every tenant-scoped table has a `tenant_id` column. The database itself enforces that queries can only see rows belonging to the current tenant. Cross-tenant data access is impossible at the database level.
- **Defense-in-depth:** Seven layers of tenant isolation (DNS through to RLS) ensure that a failure in any single layer does not expose another school's data.

### Target Market

| School Level | Examples |
|---|---|
| Preschool / Kindergarten | Creche, Nursery, KG1, KG2 |
| Primary | Primary 1 through Primary 6 |
| Junior High School (JHS) | JHS 1 through JHS 3 |
| Senior High School (SHS) | SHS 1 through SHS 3 |

### What These Sprints Deliver

Sprint 1-2 establishes the **foundational infrastructure** that every downstream feature depends on. By the end of Week 4, the team will have:

- A fully containerized local development environment (Docker Compose)
- Nginx wildcard subdomain routing
- PostgreSQL with hardened RLS policies (no NULL bypass, no admin bypass)
- Two-database-user pattern enforced (superuser for migrations, non-superuser for application)
- FastAPI with tenant middleware, JWT authentication, and cross-tenant validation
- Next.js 16 with `proxy.ts` subdomain detection and tenant context propagation
- Integration tests proving tenant isolation at the database level
- CI/CD pipeline (GitHub Actions)
- Cloudflare DNS and SSL configured

---

## 2. Architecture Decisions (ALREADY MADE)

These decisions are final. Do not re-litigate them during implementation. Each was evaluated against the specific requirements of a multi-tenant school management system targeting hundreds to low thousands of Ghanaian schools.

### Decision 1: Shared Database vs Database-Per-Tenant

| | |
|---|---|
| **CHOSEN** | Shared database with PostgreSQL Row-Level Security |
| **Rejected** | Database-per-tenant, Schema-per-tenant |
| **Rationale** | For hundreds to low thousands of schools, operational simplicity of one database far outweighs the theoretical security of physical separation. One database means one backup strategy, one migration pipeline, one connection pool, one monitoring target. RLS combined with defense-in-depth (explicit service-layer filters + hardened policies with no NULL bypass) provides sufficient isolation. Schema-per-tenant was rejected because it does not scale beyond ~500 tenants on a single PostgreSQL instance (too many schemas cause catalog bloat and `pg_dump` issues). Database-per-tenant was rejected because it requires per-tenant provisioning, connection management, and migration orchestration -- all of which are operationally expensive for a small team. |

### Decision 2: Subdomain vs Path-Based Routing

| | |
|---|---|
| **CHOSEN** | Subdomain-based (`presec.simsplus.io`) |
| **Rejected** | Path-based (`simsplus.io/school/presec`) |
| **Rationale** | Schools want an ownership feel -- their own URL that looks like their own website. Cookies are naturally scoped to the subdomain, which prevents accidental cross-tenant cookie leakage. Wildcard DNS and wildcard SSL (via Cloudflare) make subdomain provisioning zero-effort: no DNS record needed per school, no certificate needed per school. Path-based routing requires careful rewriting and does not scope cookies naturally. |

### Decision 3: JWT vs Server Sessions

| | |
|---|---|
| **CHOSEN** | JWT with 15-minute access tokens and 7-day refresh tokens |
| **Rejected** | Server-side sessions (Redis-backed) |
| **Rationale** | JWT enables stateless pod architecture: any pod can validate any token without hitting Redis. The 15-minute access token expiry limits the damage window of a compromised token. Refresh tokens (stored as HttpOnly cookies) are rotated on each use. A minimal Redis blacklist handles explicit logout and password-change invalidation. JWT naturally extends to mobile clients (Phase 4) without requiring session cookie management. The token contains `tenant_id` and `tenant_subdomain`, enabling cross-tenant validation at the middleware layer without a database lookup. |

### Decision 4: Argon2id vs bcrypt

| | |
|---|---|
| **CHOSEN** | Argon2id (OWASP recommendation #1) |
| **Rejected** | bcrypt, scrypt |
| **Rationale** | Argon2id is memory-hard (resistant to GPU/ASIC attacks) and side-channel resistant (resistant to timing attacks). It won the Password Hashing Competition (2015) and is OWASP's top recommendation. bcrypt is not memory-hard and has a 72-byte password limit. |

**Argon2id Settings:**

```
time_cost    = 2        # 2 iterations
memory_cost  = 65536    # 64 MB
parallelism  = 1        # 1 thread
hash_length  = 32       # 256-bit hash
salt_length  = 16       # 128-bit salt
```

### Decision 5: Next.js proxy.ts vs middleware.ts

| | |
|---|---|
| **CHOSEN** | `proxy.ts` (Next.js 16) |
| **Rejected** | `middleware.ts` (Next.js 14/15 Edge Runtime) |
| **Rationale** | Next.js 16 introduced `proxy.ts` as a replacement for `middleware.ts`. It runs on the Node.js runtime (not Edge), which provides full access to cookies, headers, the filesystem, and Node.js APIs. The Edge Runtime restriction in `middleware.ts` prevented use of many npm packages and required workarounds for cookie manipulation. `proxy.ts` has none of these limitations. The existing codebase already uses `proxy.ts` at `frontend/proxy.ts`. |

### Decision 6: Server Actions vs Client-Side API Calls

| | |
|---|---|
| **CHOSEN** | Server Actions |
| **Rejected** | Client-side `fetch()` to the backend API |
| **Rationale** | Server Actions keep authentication tokens in HttpOnly cookies on the server side -- they never reach the browser's JavaScript context. This eliminates an entire class of XSS token-theft attacks. Server Actions also avoid CORS issues entirely (the request goes from Next.js server to FastAPI server, both within the same Docker network). No API client library needs to be shipped in the browser bundle. The existing codebase follows this pattern with files like `actions/auth.action.ts`, `actions/students.action.ts`, etc. |

### Decision 7: Enum Value Casing

| | |
|---|---|
| **Convention** | New enums use **lowercase** values in the database |
| **Legacy** | `userrole` and `userstatus` enums use **UPPERCASE** values (TEACHER, ACTIVE, etc.) |
| **Implementation** | All enum columns use `values_callable=lambda x: [e.value for e in x]` in the SQLAlchemy `Enum()` type |

**Why this matters:** Raw SQL in tests and migrations must use the correct casing or comparisons will silently fail. When writing test assertions or seed data, always check the enum definition to determine if values are uppercase or lowercase.

### Decision 8: Two-Database-User Pattern

| | |
|---|---|
| **`sims_admin`** | Superuser role. Used ONLY by Alembic for migrations and by DBA operations. RLS is **not enforced** for superusers. |
| **`sims_app_user`** | Non-superuser role. Used by the FastAPI application at runtime. RLS **is enforced** for this role. |
| **Critical Rule** | The application (`docker-compose.yml`, FastAPI `DATABASE_URL`) MUST connect as `sims_app_user`, **never** as `postgres` or `sims_admin`. If the application connects as a superuser, RLS policies are silently bypassed and all tenant data is visible to all requests. |

This is the single most important security invariant in the system. If you remember nothing else from this document, remember this: **the backend connects as `sims_app_user`.**

---

## 3. Technology Stack (FIXED)

These versions are locked for Sprint 1-2. Do not upgrade without a Tech Lead decision and a tested migration path.

### Backend

| Layer | Technology | Version | Notes |
|---|---|---|---|
| Runtime | Python | 3.12 | Use `python:3.12-slim` Docker image |
| Framework | FastAPI | 0.109.2+ | Async, OpenAPI 3.1 |
| ORM | SQLAlchemy | 2.0 (async) | `asyncpg` driver for PostgreSQL |
| Migrations | Alembic | Latest | Runs as `sims_admin` superuser |
| Validation | Pydantic | v2 | `pydantic-settings` for config |
| Password Hashing | Argon2id | `argon2-cffi` | See Decision 4 settings |
| JWT | python-jose | Latest | HS256 algorithm |
| Task Queue | Celery + Redis | Latest | Deferred to Sprint 3+ |
| HTTP Client | httpx | Latest | For internal service calls |

### Frontend

| Layer | Technology | Version | Notes |
|---|---|---|---|
| Framework | Next.js | 16 | App Router, Turbopack |
| React | React | 19 | Server Components |
| Language | TypeScript | 5.x | Strict mode |
| Styling | Tailwind CSS | v4 | OKLCH color space |
| UI Components | Shadcn/ui | Latest | New York style variant |
| Forms | React Hook Form + Zod | Latest | Server-side validation via Server Actions |
| Data Tables | TanStack Table | Latest | |
| Charts | Recharts | Latest | |

### Infrastructure

| Layer | Technology | Version | Notes |
|---|---|---|---|
| Database | PostgreSQL | 16 | `postgres:16-alpine` Docker image |
| Cache | Redis | 7 | `redis:7-alpine` Docker image |
| Reverse Proxy | Nginx | Alpine | Wildcard subdomain routing |
| Containerization | Docker Compose | v2 | Local development |
| CI/CD | GitHub Actions | N/A | Lint, test, migration check |
| DNS + SSL | Cloudflare | N/A | Free tier, wildcard DNS, Universal SSL |
| Error Tracking | Sentry | Latest | Free tier for development |
| Cloud (Staging) | AWS | N/A | RDS, ElastiCache, S3, ECR |

---

## 4. Team Structure & Roles

### Four Parallel Tracks

The work is organized into four parallel tracks that converge during integration testing in Week 4.

| Track | Focus | Owner | Key Deliverables |
|---|---|---|---|
| **Track A (DevOps)** | Docker, Nginx, CI/CD, DNS, SSL | DevOps Engineer | Docker Compose with all services, Nginx wildcard config, GitHub Actions pipeline, Cloudflare setup, local dev subdomain tooling |
| **Track B (Backend 1)** | Models, tables, migrations, services | Backend Developer | `init-db.sql` rewrite, model imports in `db/base.py`, tenant context functions, Alembic migration chain, auth service |
| **Track C (Backend 2 / Security Lead)** | RLS policies, tenant context enforcement, security hardening | Backend Developer / Tech Lead | RLS migration (drop NULL bypass, drop admin bypass), `get_db()` enforcement, cross-tenant JWT validation, connection pool safety |
| **Track D (Frontend)** | Next.js setup, subdomain detection, auth UI, tenant context | Frontend Developer | `proxy.ts` verification, `TenantProvider` component, login/register pages, dashboard layout, Server Actions |

### Staffing

| Metric | Value |
|---|---|
| Minimum team size | 3 developers full-time for 4 weeks |
| Available capacity | 3 developers x 20 days = **60 developer-days** |
| Buffered realistic effort | **51 developer-days** (41 realistic + 25% buffer) |
| Slack | **9 developer-days** |
| Track overlap | Developers may work across tracks. Track C (Security Lead) is often the same person as Track B (Backend 1). |

### Key Responsibilities

**Tech Lead (doubles as Track C):**
- Reviews all RLS-related code before merge
- Approves any change to `init-db.sql`, `docker-compose.yml`, or `deps.py`
- Makes the call on migration consolidation timing
- Owns the integration test suite design

**DevOps (Track A):**
- Owns `docker-compose.yml`, `nginx.conf`, `.env.example`, and GitHub Actions workflows
- Responsible for local development experience (it must be a single `docker-compose up`)
- DNS and SSL configuration

**Backend Developer (Track B):**
- Owns all SQLAlchemy models, Alembic migrations, and Pydantic schemas
- Implements service-layer business logic
- Writes unit tests for service methods

**Frontend Developer (Track D):**
- Owns `proxy.ts`, all pages under `app/`, all Server Actions under `actions/`
- Implements responsive UI with Shadcn/ui components
- Writes Playwright E2E tests for auth flows

---

## 5. Sprint Structure

### Sprint 1: Environment + Security Foundation (Weeks 1-2)

**Goal:** Every developer can run `docker-compose up` and access `presec.localhost:3000` with a working tenant context pipeline from browser to database.

| Week | Track A (DevOps) | Track B (Backend 1) | Track C (Security) | Track D (Frontend) |
|---|---|---|---|---|
| **Week 1** | S1-01: Git repo + `.env.example` (0.5d) | S1-03: Verify FastAPI scaffold (1d) | Begin S2-03: RLS policy rework (5d total) | S1-04: Verify Next.js 16 setup (2d) |
| | S1-02: Docker env fix (2d) | S1-05: Fix `init-db.sql` (1.5d) | | Begin S2-09: proxy.ts subdomain (3d total) |
| | S1-07: Cloudflare DNS wildcard (1d) | Begin S2-03: RLS policy rework | | |
| **Week 2** | S1-08: SSL config (1d) | S2-01: Tenants table verification (0.5d) | Complete S2-03: RLS policy rework | Complete S2-09: proxy.ts |
| | S1-09: Nginx wildcard config (3d) | S2-02: Reserved subdomains seed (0.5d) | S2-04: Tenant context functions (2d) | S2-10: TenantProvider (1.5d) |
| | S1-10: Local dev subdomain docs (1.5d) | | | |
| | S1-06: CI/CD pipeline (2d) | | | |

**Sprint 1 Total:** 15.5 developer-days (Track A) + varies (Tracks B/C/D overlap)

### Sprint 2: Multi-Tenant Data Layer + Integration (Weeks 3-4)

**Goal:** RLS is hardened and proven via integration tests. Auth flow works end-to-end through all 7 layers. Health checks verify database and Redis connectivity.

| Week | Track A+B (Backend) | Track C (Security/QA) | Track D (Frontend) |
|---|---|---|---|
| **Week 3** | S2-05: Schools table verification (0.5d) | S2-07: `get_db()` enforcement (2d) | Auth: Login page with tenant branding |
| | S2-06: Users table verification (0.5d) | S2-11: Tenant lookup caching (2d) | Auth: Registration wizard |
| | Auth: TenantMiddleware + AuthService + JWT | Begin S2-12: Integration tests (5d total) | Auth: `auth.action.ts` |
| **Week 4** | S2-08: Migration consolidation (2d, optional) | Complete S2-12: Integration tests | Auth: Dashboard layout + sidebar |
| | S2-13: Health check enhancement (1d) | Bug fixes from test findings | Auth guard + protected routes |
| | Buffer: Documentation, sprint review | | |

**Sprint 2 Total:** 25.5 developer-days

### Combined Totals

| Scenario | Developer-Days | Notes |
|---|---|---|
| Optimistic | 21 | Everything works on the first try, no external blockers |
| **Realistic** | **41** | Normal debugging, one external blocker (DNS propagation, etc.) |
| Pessimistic | 67 | RLS takes 8d, Nginx takes 5d, DNS delays |
| **Buffered (25%)** | **51** | **Recommended planning target** |

With 3 developers x 4 weeks = 60 available days, the buffered realistic estimate of 51 days fits with **9 days of slack**.

---

## 6. Critical Path

The critical path is the longest chain of sequential dependencies. No parallelization can shorten it.

```
S1-01 (Git) --> S1-02 (Docker) --> S1-05 (PostgreSQL) --> S2-03 (RLS) --> S2-04 (Context Fns) --> S2-07 (get_db) --> S2-12 (Integration Tests)
 (0.5d)          (2d)               (1.5d)                (5d)            (2d)                    (2d)               (5d)
                                                                                                                    = 18 days SEQUENTIAL
```

**Analysis:**

- The critical path is **18 working days** of sequential work.
- The 4-week (20 working day) window leaves **2 days of slack** on the critical path.
- **There is zero slippage tolerance on S2-03 (RLS rework)** -- it is both the highest-risk and longest single task.
- **S2-12 (Integration tests)** cannot start until S2-07 is complete, because the tests validate the exact behavior that S2-07 implements.
- Track A (DevOps) and Track D (Frontend) work runs in parallel to the critical path and does not affect it, as long as Nginx is ready by the time integration tests need it.

### Mitigation for Critical Path Risk

1. **S2-03 (RLS rework) starts on Day 3**, not Day 8. The Backend developer begins design work as soon as `init-db.sql` is fixed.
2. **S2-12 (Integration tests)** test infrastructure is set up in Week 2, before the tests themselves are written. The two-engine test pattern (admin engine + app_user engine) is configured first.
3. If S2-03 exceeds 5 days, the Tech Lead immediately pairs with the Backend developer. No other work takes priority.

---

## 7. Pre-Sprint Checklist

Every item below MUST be completed before Sprint 1, Day 1. The Tech Lead is responsible for verifying completion.

```
[ ] Domain `simsplus.io` registered and nameservers pointed to Cloudflare
[ ] Cloudflare account created with domain added (free tier)
[ ] AWS account created with IAM admin user (budget alert set at $50/month)
[ ] GitHub repository created with branch protection on `main`:
    - Require pull request reviews (1 reviewer minimum)
    - Require status checks to pass (CI pipeline)
    - No force pushes to main
[ ] GitHub Actions secrets configured:
    - DATABASE_URL (for CI test database)
    - SECRET_KEY (64+ character random string)
    - REDIS_URL (for CI Redis instance)
[ ] All developers have installed locally:
    - Docker Desktop (latest stable)
    - Python 3.12 (via pyenv or system install)
    - Node.js 22 (via nvm or system install)
    - git (2.40+)
    - psql client (PostgreSQL 16 client tools)
    - A REST client (Postman, Insomnia, or httpie)
[ ] Team has completed a 2-hour PostgreSQL RLS workshop covering:
    - How RLS policies work (USING vs WITH CHECK)
    - How `set_config()` and `current_setting()` work
    - Why superuser connections bypass RLS
    - How to test RLS with two database roles
[ ] Tech Lead has created `.env.example` with all required variables documented
[ ] Product Owner has confirmed Sprint 1-2 scope (this document)
[ ] Team has read this document and the three companion documents (see Section 9)
```

---

## 8. Infrastructure Requirements

### Pre-Sprint Infrastructure (procure before Day 1)

| # | Requirement | Lead Time | Monthly Cost | One-Time Cost | Notes |
|---|---|---|---|---|---|
| I-01 | Domain `simsplus.io` | 1-2 days | -- | ~$15/year | Register via Namecheap, Google Domains, or Cloudflare Registrar |
| I-02 | Cloudflare account | < 1 hour | $0 (free tier) | $0 | Free plan includes wildcard DNS and Universal SSL |
| I-03 | GitHub repository + Actions | < 1 hour | $4/user/month | $0 | Team plan for private repos with Actions minutes |
| I-04 | AWS account | 1-3 days | Budget: $50/month | $0 | IAM admin user, MFA enabled, billing alerts configured |
| I-05 | Developer machines | 1-2 hrs/machine | $0 | $0 | Docker Desktop, Python 3.12, Node.js 22, git, psql |

### Sprint Infrastructure (provision during sprints)

| # | Requirement | Monthly Cost | When Needed | Provisioned By |
|---|---|---|---|---|
| I-07 | Cloudflare wildcard DNS (`*.simsplus.io`) | $0 | Sprint 1, Week 1 | DevOps |
| I-08 | Cloudflare Universal SSL (covers `*.simsplus.io`) | $0-$10/month | Sprint 1, Week 1 | DevOps |
| I-09 | AWS RDS PostgreSQL 16 (staging: `db.t3.micro`) | ~$30/month | Sprint 1, Week 2 | DevOps |
| I-10 | AWS ElastiCache Redis 7 (staging: `cache.t3.micro`) | ~$15/month | Sprint 1, Week 2 | DevOps |
| I-11 | AWS S3 bucket (`sims-plus-files`) | ~$5/month | Sprint 2, Week 1 | DevOps |
| I-12 | AWS ECR repository (container images) | ~$2/month | Sprint 1, Week 2 | DevOps |
| I-13 | SendGrid account (development tier) | $0 (free tier) | Sprint 2 | Backend |
| I-14 | Sentry project (error tracking) | $0 (free tier) | Sprint 1, Week 1 | Tech Lead |

### Cost Summary

| Period | Monthly Cost |
|---|---|
| Pre-Sprint | ~$12/month (GitHub Teams for 3 developers) |
| Sprint 1-2 (development) | ~$64/month (GitHub + AWS staging) |
| Post-Sprint (staging running) | ~$73/month |

---

## 9. Document Index

This implementation plan is split across four documents. This is the master document (00). The other three contain the detailed implementation specifications.

| Document | File | Contents |
|---|---|---|
| **00 - Overview & Setup** (this document) | `00-overview-and-setup.md` | Project overview, architecture decisions, technology stack, team structure, sprint plan, critical path, pre-sprint checklist, infrastructure, known issues |
| **01 - Sprint 1: Infrastructure** | `01-sprint-1-infrastructure.md` | Sprint 1 task breakdown with acceptance criteria. Docker Compose rewrite, `init-db.sql` rewrite, Nginx wildcard configuration, Cloudflare DNS/SSL, CI/CD pipeline, local development setup. |
| **02 - Sprint 2: Multi-Tenancy** | `02-sprint-2-multi-tenancy.md` | Sprint 2 task breakdown with acceptance criteria. RLS policy rework, tenant context functions, `get_db()` enforcement, table verifications, Next.js proxy.ts, TenantProvider, auth flow, tenant lookup caching, migration consolidation, health checks. |
| **03 - Technical Reference** | `03-technical-reference.md` | Code patterns (service layer, enum handling, soft deletes), SQL templates (RLS policies, tenant context functions), configuration files (`nginx.conf`, `.env.example`, `docker-compose.yml`), API contracts (auth endpoints, tenant endpoints). |
| **04 - Testing & Quality** | `04-testing-and-quality.md` | Testing strategy (unit, integration, E2E), two-engine test pattern, RLS test playbook, quality gates per sprint, risk register (25 risks with mitigations), definition of done. |

### Reading Order

1. Read this document (00) first -- it provides the full context.
2. Read 03 (Technical Reference) next -- it contains the exact code patterns and configurations you will implement.
3. Read 01 (Sprint 1) and 02 (Sprint 2) for your specific tasks.
4. Read 04 (Testing & Quality) before writing any tests.

---

## 10. 7-Layer Defense-in-Depth Architecture

Every request passes through seven layers of tenant isolation. Each layer assumes all layers above it have failed. This is defense-in-depth: no single point of failure can expose another school's data.

```
REQUEST: https://presec.simsplus.io/api/v1/students
         |
         v
LAYER 1: DNS Wildcard
         *.simsplus.io --> Cloudflare --> AWS ELB
         Cloudflare resolves all subdomains to the same IP.
         No per-tenant DNS configuration needed.
         |
         v
LAYER 2: Nginx Reverse Proxy
         Extracts subdomain from Host header.
         Sets X-Subdomain: presec header on proxied request.
         Rejects requests with no valid subdomain (returns 400).
         |
         v
LAYER 3: Next.js proxy.ts
         Validates subdomain format (4-63 chars, alphanumeric + hyphens).
         Rejects reserved subdomains (www, api, admin, etc.).
         Sets x-subdomain header and cookie for downstream use.
         Redirects unauthenticated users on tenant subdomains to /login.
         |
         v
LAYER 4: FastAPI TenantMiddleware
         Reads X-Subdomain header (or extracts from Host header).
         Queries database: SELECT * FROM tenants WHERE subdomain = 'presec'.
         Validates tenant is active (not suspended, not deleted).
         Sets PostgreSQL session variable: SET app.current_tenant_id = '<uuid>'.
         Stores tenant_id in request.state for downstream dependencies.
         |
         v
LAYER 5: JWT Validation
         Decodes JWT access token from Authorization header.
         Extracts token.tenant_id from JWT payload.
         Compares token.tenant_id with request.state.tenant_id.
         REJECTS the request if they do not match (HTTP 403).
         This prevents a user who has a valid token for School A
         from using it to access School B's data.
         |
         v
LAYER 6: Service Layer
         Every service method includes an explicit filter:
         .filter(Model.tenant_id == tenant_id)
         This is defense-in-depth -- even if RLS somehow failed,
         the application code would still filter by tenant.
         |
         v
LAYER 7: PostgreSQL Row-Level Security
         RLS policy on every tenant-scoped table:
         USING (tenant_id = get_current_tenant_id())
         The database REFUSES to return rows where tenant_id
         does not match the session variable.
         This is the last line of defense. Even if Layers 4-6
         all failed, the database would still protect the data.
```

### Why 7 Layers?

A common objection is: "If RLS works, why do we need the other layers?" The answer is that RLS only works if:

1. The application connects as a **non-superuser** (superusers bypass RLS)
2. The session variable `app.current_tenant_id` is **set correctly** (if unset, the hardened policy returns zero rows -- safe but broken)
3. The session variable is **not leaked** between requests (connection pool reuse)

Layers 1-6 ensure that conditions 1-3 are met. Layer 7 (RLS) is the safety net if any of the above layers fail.

---

## 11. Known Issues in Existing Codebase (MUST FIX in Sprint 1-2)

The existing codebase provides a substantial head start (40+ migrations, 15 endpoint files, 260+ frontend components), but contains **10 security and infrastructure issues** that must be resolved before Sprint 2 can be considered complete.

These findings were independently identified through architecture review and risk analysis. They are ordered by severity.

| # | Severity | Issue | File | Line(s) | Fix Required | Sprint Task |
|---|---|---|---|---|---|---|
| **F1** | **CRITICAL** | RLS policies contain a NULL bypass: `OR get_current_tenant_id() IS NULL`. If the tenant context is not set (e.g., connection pool reuse, missing middleware), RLS returns ALL rows from ALL tenants. | `backend/alembic/versions/20260104_0500_comprehensive_rls.py` | L82-84, L94 | Write a new migration that drops ALL existing RLS policies and recreates them with ONLY `tenant_id = get_current_tenant_id()`. No NULL fallback. No exceptions. | S2-03 |
| **F2** | **CRITICAL** | `docker-compose.yml` connects the backend to PostgreSQL as the `postgres` superuser via `DATABASE_URL`. Superusers bypass RLS entirely, making all RLS policies meaningless at runtime. | `docker-compose.yml` | L57 | Create `sims_app_user` role in `init-db.sql` with `GRANT` on all tables. Change `DATABASE_URL` in `docker-compose.yml` to connect as `sims_app_user`. | S1-05 |
| **F3** | **HIGH** | `get_db()` silently proceeds without tenant context. If `request.state.tenant_id` is `None`, the session is yielded without calling `set_tenant_context()`. With the hardened RLS (no NULL bypass), this means queries return zero rows -- a silent data loss bug. | `backend/app/api/deps.py` | L41-46 | Raise HTTP 400 if `tenant_id` is `None` on non-public routes. Create a separate `get_unscoped_db()` dependency for platform-level operations (onboarding, tenant lookup). | S2-07 |
| **F4** | **HIGH** | The onboarding service inserts into RLS-protected tables (`schools`, `users`) without first setting the tenant context. After the tenant is created and flushed (L132), the subsequent `school` and `admin_user` inserts (L145-163) happen without `set_tenant_context()`, so with hardened RLS they will be rejected. | `backend/app/services/onboarding.py` | L131-168 | After `await self.db.flush()` on L132, add `await set_db_tenant_context(self.db, tenant.id)` before creating the school and user. | S2-04 |
| **F5** | **HIGH** | RLS policies contain an `is_platform_admin` session variable bypass: `OR current_setting('app.is_platform_admin', true) = 'true'`. Any code that sets this session variable bypasses all tenant isolation. | `backend/alembic/versions/20260104_0500_comprehensive_rls.py` | L86-87, L97 | Remove the `is_platform_admin` bypass from all RLS policies entirely. Platform admin operations use the superuser database connection (`sims_admin`), not a session variable. Drop the `is_platform_admin()` helper function. | S2-03 |
| **F6** | **MEDIUM** | No Nginx wildcard subdomain configuration exists. The Nginx service is commented out in `docker-compose.yml`. Without Nginx, subdomain routing in local development requires manual `/etc/hosts` entries and does not match the production architecture. | `docker-compose.yml` | L114-125 | Create `docker/nginx/nginx.conf` with wildcard subdomain routing. Uncomment and configure the Nginx service in `docker-compose.yml`. | S1-09 |
| **F7** | **MEDIUM** | No `.env.example` file exists. New developers have no reference for required environment variables, leading to configuration errors and wasted setup time. | Project root | N/A | Create `.env.example` with all required variables, safe defaults, and documentation comments. Include `POSTGRES_USER`, `POSTGRES_PASSWORD`, `SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`, and all SMTP/AWS/MoMo variables. | S1-01 |
| **F8** | **MEDIUM** | `db/base.py` only imports 2 of 14 model files (`Tenant`, `User`). Alembic's autogenerate feature relies on all models being imported in `db/base.py` to detect schema changes. The remaining 12 model files are commented out. | `backend/app/db/base.py` | L14-21 | Uncomment and import ALL model classes: `School`, `Student`, `Guardian`, `Staff`, `AcademicYear`, `Term`, `Class`, `Section`, `Subject`, `Exam`, `Attendance`, `Finance`, etc. | S1-03 |
| **F9** | **MEDIUM** | Two different tenant context functions exist: `current_tenant_id()` in `init-db.sql` (L16-21) and `get_current_tenant_id()` in the comprehensive RLS migration. They have slightly different implementations and naming. This creates confusion about which function is the canonical one. | `backend/scripts/init-db.sql` L16-21 vs `backend/alembic/versions/20260104_0500_comprehensive_rls.py` L118-141 | N/A | Standardize on `get_current_tenant_id()` everywhere. Remove `current_tenant_id()` from `init-db.sql`. Ensure all RLS policies, helper functions, and application code reference the same function name. | S1-05 |
| **F10** | **MEDIUM** | CORS is configured with a static list of origins (`allow_origins=settings.CORS_ORIGINS`), which defaults to `["http://localhost:3000"]`. In production, every school subdomain (`presec.simsplus.io`, `achimota.simsplus.io`, etc.) is a different origin. A static list cannot accommodate dynamically created subdomains. | `backend/app/main.py` | L63 | Replace the static `allow_origins` with `allow_origin_regex=r"https?://[\w-]+\.simsplus\.io"` (already defined in `config.py` as `CORS_ALLOW_SUBDOMAIN_PATTERN`). Keep localhost origins for development. | S1-03 |

### Severity Legend

| Severity | Meaning | SLA |
|---|---|---|
| **CRITICAL** | Active security vulnerability. Tenant data isolation is broken or can be trivially bypassed. | Must fix in Sprint 1, Week 1-2 |
| **HIGH** | Security gap that would cause data loss, silent failures, or make other fixes ineffective. | Must fix in Sprint 2, Week 1 |
| **MEDIUM** | Infrastructure gap, developer experience issue, or technical debt that blocks downstream work. | Must fix by end of Sprint 2 |

---

## 12. Project Structure

The directory structure below reflects the target state at the end of Sprint 2. Items marked with `[NEW]` do not yet exist and must be created. Items marked with `[FIX]` exist but require modification.

```
sims-plus/
|
|-- backend/
|   |-- app/
|   |   |-- api/
|   |   |   |-- v1/
|   |   |   |   |-- endpoints/
|   |   |   |   |   |-- auth.py              # Authentication (login, register, refresh, logout)
|   |   |   |   |   |-- academic.py          # Classes, subjects, grading, holidays
|   |   |   |   |   |-- students.py          # Student CRUD, guardians, import/export
|   |   |   |   |   |-- staff.py             # Staff management, departments
|   |   |   |   |   |-- attendance.py        # Attendance marking and reports
|   |   |   |   |   |-- exams.py             # Exams, CA, report cards
|   |   |   |   |   |-- timetable.py         # Class timetables
|   |   |   |   |   |-- preschool.py         # Preschool module
|   |   |   |   |   |-- finance.py           # Fee structures, invoices, payments
|   |   |   |   |   |-- schools.py           # School settings and branding
|   |   |   |   |   |-- users.py             # User management
|   |   |   |   |   `-- media.py             # File uploads (S3)
|   |   |   |   `-- router.py                # API router aggregation
|   |   |   `-- deps.py                      # [FIX] Dependencies (get_db, get_unscoped_db)
|   |   |
|   |   |-- core/
|   |   |   |-- config.py                    # [FIX] Pydantic settings (add CORS regex)
|   |   |   `-- security.py                  # Password hashing (Argon2id), JWT utilities
|   |   |
|   |   |-- db/
|   |   |   |-- base.py                      # [FIX] Import ALL models for Alembic
|   |   |   `-- session.py                   # Async session factory
|   |   |
|   |   |-- models/
|   |   |   |-- base.py                      # Base model with id, timestamps, soft delete
|   |   |   |-- tenant.py                    # Tenant model
|   |   |   |-- user.py                      # User model
|   |   |   |-- school.py                    # School model
|   |   |   |-- student.py                   # Student, Guardian models
|   |   |   |-- staff.py                     # Staff, Department models
|   |   |   |-- academic.py                  # AcademicYear, Term, Class, Section, Subject
|   |   |   |-- exam.py                      # Exam, Score, Report models
|   |   |   |-- attendance.py                # Attendance model
|   |   |   |-- preschool.py                 # Preschool models
|   |   |   |-- finance.py                   # Finance models
|   |   |   |-- reserved_subdomain.py        # Reserved subdomain model
|   |   |   `-- audit_log.py                 # Audit log model
|   |   |
|   |   |-- schemas/                         # Pydantic v2 request/response schemas
|   |   |
|   |   |-- services/
|   |   |   |-- auth.py                      # Authentication service
|   |   |   |-- onboarding.py                # [FIX] School onboarding (add tenant context)
|   |   |   |-- tenant.py                    # Tenant lookup and validation
|   |   |   |-- student.py                   # Student service
|   |   |   |-- staff.py                     # Staff service
|   |   |   |-- academic.py                  # Academic service
|   |   |   |-- exam.py                      # Exam service
|   |   |   |-- timetable.py                 # Timetable service
|   |   |   |-- preschool.py                 # Preschool service
|   |   |   |-- finance.py                   # Finance service
|   |   |   |-- email.py                     # Email sending service
|   |   |   |-- token_blacklist.py           # Redis token blacklist
|   |   |   |-- pdf.py                       # PDF generation (WeasyPrint)
|   |   |   `-- s3.py                        # S3 upload service
|   |   |
|   |   |-- middleware/
|   |   |   |-- tenant.py                    # Tenant context middleware
|   |   |   `-- rate_limit.py                # Redis sliding window rate limiter
|   |   |
|   |   |-- templates/                       # Jinja2/WeasyPrint PDF templates
|   |   |
|   |   `-- main.py                          # [FIX] FastAPI app entry point (CORS regex)
|   |
|   |-- alembic/
|   |   |-- versions/                        # Migration files (40+)
|   |   |   |-- 20260104_0500_comprehensive_rls.py  # [FIX] RLS policies (remove bypasses)
|   |   |   `-- ...
|   |   `-- env.py                           # Alembic environment config
|   |
|   |-- scripts/
|   |   `-- init-db.sql                      # [FIX] DB init (add sims_app_user, fix functions)
|   |
|   |-- tests/                               # [NEW] pytest test suite
|   |   |-- conftest.py                      # Two-engine test fixtures
|   |   |-- test_rls.py                      # RLS isolation tests
|   |   `-- test_auth.py                     # Auth flow tests
|   |
|   |-- Dockerfile
|   `-- requirements.txt
|
|-- frontend/
|   |-- app/
|   |   |-- (auth)/                          # Login, register, password reset pages
|   |   `-- (dashboard)/                     # Protected dashboard pages
|   |       |-- dashboard/
|   |       |-- calendar/
|   |       |-- students/
|   |       |-- staff/
|   |       |-- classes/
|   |       |-- attendance/
|   |       |-- exams/
|   |       |-- preschool/
|   |       |-- finance/
|   |       |-- boarding/                    # Placeholder
|   |       |-- transport/                   # Placeholder
|   |       |-- messages/                    # Placeholder
|   |       |-- reports/                     # Placeholder
|   |       `-- settings/
|   |
|   |-- components/
|   |   |-- ui/                              # Shadcn/ui components
|   |   |-- dashboard/                       # Sidebar, header, layout
|   |   |-- academic/                        # Academic settings components
|   |   |-- preschool/                       # Preschool components
|   |   `-- setup-wizard/                    # School setup wizard
|   |
|   |-- actions/                             # Server Actions
|   |   |-- auth.action.ts
|   |   |-- students.action.ts
|   |   |-- staff.action.ts
|   |   |-- academic.action.ts
|   |   |-- school.action.ts
|   |   |-- exams.action.ts
|   |   |-- timetable.action.ts
|   |   |-- preschool.action.ts
|   |   `-- finance.action.ts
|   |
|   |-- contexts/                            # React context providers
|   |-- hooks/                               # Custom React hooks
|   |-- lib/                                 # Utilities (api.ts, etc.)
|   |-- types/                               # TypeScript type definitions
|   |-- proxy.ts                             # [VERIFY] Subdomain detection (Next.js 16)
|   |-- next.config.ts
|   |-- package.json
|   |-- tsconfig.json
|   `-- Dockerfile
|
|-- docker/                                  # [NEW] Docker configuration
|   `-- nginx/
|       `-- nginx.conf                       # [NEW] Wildcard subdomain routing
|
|-- docker-compose.yml                       # [FIX] Add Nginx, fix DATABASE_URL
|-- .env.example                             # [NEW] Environment variable template
|-- .github/
|   `-- workflows/
|       `-- ci.yml                           # [NEW] GitHub Actions CI pipeline
|-- CLAUDE.md                                # Project guide (this file)
`-- spec/
    |-- implementation-plan/
    |   |-- 00-overview-and-setup.md         # This document
    |   |-- 01-sprint-1-infrastructure.md
    |   |-- 02-sprint-2-multi-tenancy.md
    |   |-- 03-technical-reference.md
    |   `-- 04-testing-and-quality.md
    |-- solution-architecture.md
    |-- multi-tenancy-architecture.md
    |-- risk-analysis.md
    `-- sprint-1-2-unified-implementation-plan.md
```

---

## Appendix A: Glossary

| Term | Definition |
|---|---|
| **Tenant** | A single organization (school or school chain) that has its own subdomain, users, and data. |
| **RLS** | Row-Level Security. A PostgreSQL feature that automatically filters table rows based on the current session context. |
| **RLS bypass** | A condition in an RLS policy that allows access without matching the tenant_id. The NULL bypass (`get_current_tenant_id() IS NULL`) is the most dangerous because it fires whenever the tenant context is not set. |
| **Defense-in-depth** | A security strategy where multiple independent layers each enforce the same security invariant. Failure of any single layer does not compromise the invariant. |
| **Superuser** | A PostgreSQL role with `SUPERUSER` privilege. Superusers bypass ALL security policies, including RLS. The application must NEVER connect as a superuser. |
| **Session variable** | A PostgreSQL per-connection setting (e.g., `app.current_tenant_id`) that persists for the duration of a database session. Used to pass the tenant context from the application to RLS policies. |
| **Server Action** | A Next.js feature where a function marked with `"use server"` runs on the server and can be called directly from React components. Used to keep API tokens out of the browser. |
| **proxy.ts** | The Next.js 16 replacement for `middleware.ts`. Runs on the Node.js runtime (not Edge) and has access to the full Node.js API. |

## Appendix B: Key File Quick Reference

For developers who need to quickly find the right file to modify:

| I need to... | File |
|---|---|
| Change database connection settings | `backend/app/core/config.py` (`DATABASE_URL`) |
| Change how tenant context is extracted from requests | `backend/app/middleware/tenant.py` |
| Change how database sessions get tenant context | `backend/app/api/deps.py` (`get_db()`) |
| Change RLS policies | Write a new Alembic migration in `backend/alembic/versions/` |
| Change subdomain detection in the frontend | `frontend/proxy.ts` |
| Add a new API endpoint | `backend/app/api/v1/endpoints/` + register in `router.py` |
| Add a new Server Action | `frontend/actions/{module}.action.ts` |
| Add a new SQLAlchemy model | `backend/app/models/` + import in `backend/app/db/base.py` |
| Change Docker services | `docker-compose.yml` |
| Change Nginx routing | `docker/nginx/nginx.conf` |
| Add a CI/CD step | `.github/workflows/ci.yml` |
| Add environment variables | `.env.example` + `backend/app/core/config.py` |

---

*End of Document 00. Proceed to `01-sprint-1-infrastructure.md` for Sprint 1 task details.*
