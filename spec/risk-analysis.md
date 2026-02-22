# SIMS Plus -- Sprint 1-2 Comprehensive Risk Analysis

**Version:** 1.0
**Date:** 15 February 2026
**Author:** Risk Analyst (AI-Assisted TPM)
**Sprint:** 1-2 (Core Infrastructure + Multi-Tenancy Foundation)
**Sprint Duration:** 4 weeks (2 x 2-week sprints)

---

## Executive Summary

Sprint 1-2 represents the **highest-risk phase of the entire project**. Every downstream sprint depends on the correctness of the multi-tenant infrastructure, RLS policies, and subdomain routing established here. Based on my examination of the existing codebase, the project has a substantial head start -- Docker, backend scaffolding, database models, CI/CD pipelines, and tenant middleware already exist. However, several critical gaps remain:

1. **The RLS policies in the comprehensive migration still contain a NULL bypass vulnerability** (file: `/Users/harrymcninson/Documents/projects/sims-plus/backend/alembic/versions/20260104_0500_comprehensive_rls.py`, lines 82-84)
2. **`get_db()` does not enforce tenant context presence on protected routes** (file: `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/api/deps.py`, lines 41-46)
3. **No Nginx wildcard configuration exists** -- the docker-compose entry is commented out (file: `/Users/harrymcninson/Documents/projects/sims-plus/docker-compose.yml`, lines 114-125)
4. **No Terraform IaC has been written** -- the `/infrastructure` directory is empty
5. **No `.env.example` file exists** for developer onboarding

These are not hypothetical risks. They are observable issues in the current code.

**Overall Risk Level: MEDIUM-HIGH.** The existing code provides strong scaffolding, but the security-critical RLS layer needs rework before Sprint 1-2 can be considered complete. The estimated total effort is **38-52 developer-days** across all tracks, with a realistic 4-week timeline requiring at least 3 developers working in parallel.

---

## 1. Sprint 1-2 Component Breakdown

### Sprint 1: Project Setup and Infrastructure

| # | Component | Description | Complexity | Effort (dev-days) | Dependencies | Owner |
|---|-----------|-------------|------------|-------------------|--------------|-------|
| S1-01 | Git Repository and Branching Strategy | Monorepo setup, branch protection rules, PR templates, CODEOWNERS | Low | 0.5 | None | Tech Lead |
| S1-02 | Docker Environment | Finalize docker-compose.yml, add Nginx container, health checks, `.env.example` | Medium | 2 | S1-01 | DevOps |
| S1-03 | FastAPI Backend Scaffolding | Verify existing structure, add missing middleware registration, logging config | Low | 1 | S1-02 | Backend 1 |
| S1-04 | Next.js 16 Frontend Setup | Verify App Router config, add Next.js middleware for subdomain detection, verify Turbopack | Medium | 2 | S1-02 | Frontend 1 |
| S1-05 | PostgreSQL Database Setup | Rework `init-db.sql` (add app_user role, fix dual function issue), verify extensions | Medium | 1.5 | S1-02 | Backend 2 |
| S1-06 | CI/CD Pipeline (GitHub Actions) | Fix Node version in frontend-ci.yml, add migration test step, add RLS verification | Medium | 2 | S1-01 | DevOps |
| S1-07 | Cloudflare DNS Wildcard | Configure wildcard CNAME `*.simsplus.io`, SSL cert | Medium | 1 | External: Domain registrar | DevOps |
| S1-08 | Wildcard SSL Certificate | Cloudflare Universal SSL or Let's Encrypt wildcard via DNS challenge | Medium | 1 | S1-07 | DevOps |
| S1-09 | Nginx Wildcard Subdomain Routing | Create `nginx.conf` for wildcard subdomain routing to backend + frontend | High | 3 | S1-02, S1-07 | DevOps |
| S1-10 | Local Development Subdomain Setup | Document and script `*.localhost` or `dnsmasq` approach for local testing | Medium | 1.5 | S1-09 | DevOps + Tech Lead |

**Sprint 1 Subtotal: 15.5 developer-days**

### Sprint 2: Multi-Tenancy Foundation

| # | Component | Description | Complexity | Effort (dev-days) | Dependencies | Owner |
|---|-----------|-------------|------------|-------------------|--------------|-------|
| S2-01 | Tenants Table and Model | Already exists -- verify schema, add missing indexes, ensure soft delete works | Low | 0.5 | S1-05 | Backend 1 |
| S2-02 | Reserved Subdomains Table | Already exists -- verify seed data, add any missing entries | Low | 0.5 | S1-05 | Backend 1 |
| S2-03 | RLS Policies (REWORK) | Remove NULL bypass, remove is_platform_admin bypass, implement two-DB-user pattern | Very High | 5 | S1-05 | Backend 2 + Tech Lead |
| S2-04 | `set_tenant_context()` / `get_current_tenant_id()` Functions | Fix dual function issue (init-db.sql vs migration), ensure atomic context setting | High | 2 | S2-03 | Backend 2 |
| S2-05 | Schools Table and Model | Already exists -- verify FK to tenants, add composite indexes | Low | 0.5 | S2-01 | Backend 1 |
| S2-06 | Users Table with tenant_id | Already exists -- verify composite unique (email + tenant_id), FK constraints | Low | 0.5 | S2-01 | Backend 1 |
| S2-07 | `get_db()` Tenant Enforcement | Add mandatory tenant context check for non-public routes, raise 400 if missing | High | 2 | S2-03, S2-04 | Backend 2 |
| S2-08 | Alembic Migration Consolidation | Clean up 40+ migrations, create single baseline migration for fresh deploys | Medium | 2 | S2-01 through S2-06 | Backend 1 |
| S2-09 | Next.js Middleware for Subdomain Detection | Create `middleware.ts` at app root to extract subdomain from Host header, set cookie | High | 3 | S1-04, S1-09 | Frontend 1 |
| S2-10 | React Tenant Context Provider | Already exists -- verify integration with Next.js middleware, add error boundaries | Medium | 1.5 | S2-09 | Frontend 1 |
| S2-11 | Tenant Lookup Caching (Redis) | Cache tenant lookups with tenant-prefixed keys, TTL, invalidation on tenant update | High | 2 | S2-01, S1-02 (Redis) | Backend 2 |
| S2-12 | Multi-Tenant Integration Tests | RLS isolation tests, cross-tenant access tests, NULL context tests, two-tenant scenarios | Very High | 5 | S2-03, S2-07 | QA + Backend 2 |
| S2-13 | API Health Check Enhancement | Add DB connectivity, Redis connectivity, tenant resolution checks to `/health` | Low | 1 | S2-04 | Backend 1 |

**Sprint 2 Subtotal: 25.5 developer-days**

### Total Estimates

| Metric | Value |
|--------|-------|
| **Total Estimated Effort** | **41 developer-days** |
| **Confidence Level** | **Medium** -- existing code reduces unknowns, but RLS rework and Nginx config are under-specified |
| **Recommended Buffer** | **25%** (10.25 days) -- RLS security work has high unknowns; local subdomain testing historically burns time |
| **Buffered Total** | **~51 developer-days** |
| **Required Team** | Minimum 3 developers (1 DevOps, 1 Backend, 1 Frontend) working full-time for 4 weeks = 60 available days. This leaves approximately 9 days slack. |

---

## 2. Risk Register

| Risk ID | Category | Description | Likelihood (1-5) | Impact (1-5) | Score | Mitigation Strategy | Owner |
|---------|----------|-------------|-------------------|--------------|-------|---------------------|-------|
| **R01** | **Security** | **RLS NULL bypass still active in comprehensive_rls migration.** The `USING` clause contains `OR (get_current_tenant_id() IS NULL)` allowing full table access when no tenant context is set. This is in `/Users/harrymcninson/Documents/projects/sims-plus/backend/alembic/versions/20260104_0500_comprehensive_rls.py` lines 82-84. | 5 | 5 | **25** | Write new migration that drops all existing RLS policies and recreates them with ONLY `tenant_id = get_current_tenant_id()`. No NULL fallback. No is_platform_admin bypass. Use a superuser DB role (BYPASSRLS) for admin operations. Test with a script that attempts to query without context and verifies zero rows returned. | Tech Lead |
| **R02** | **Security** | **`get_db()` silently proceeds without tenant context.** In `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/api/deps.py` lines 41-46, if `request.state.tenant_id` is None, the session is yielded without any tenant context set. Combined with R01, this leaks all tenant data. | 5 | 5 | **25** | Add explicit check: if the endpoint is NOT in a whitelist of public paths AND `tenant_id` is None, raise HTTP 400. Implement an `UnscopedDatabaseSession` dependency for the few endpoints that genuinely need unscoped access (onboarding, platform admin). | Backend 2 |
| **R03** | **Security** | **`is_platform_admin` session variable bypass.** The RLS policy allows any session that sets `app.is_platform_admin = 'true'` to bypass tenant isolation. If an attacker controls a session variable (e.g., through SQL injection), they gain cross-tenant access. Present in comprehensive_rls migration lines 86-87. | 3 | 5 | **15** | Remove `is_platform_admin` from RLS policies entirely. Platform admin operations should use a separate PostgreSQL role with `BYPASSRLS` privilege, not a session variable. | Backend 2 |
| **R04** | **Technical** | **Dual `current_tenant_id()` functions.** `/Users/harrymcninson/Documents/projects/sims-plus/backend/scripts/init-db.sql` creates `current_tenant_id()` while migrations create `get_current_tenant_id()`. These are different functions. If code references the wrong one, RLS silently fails. | 4 | 4 | **16** | Standardize on `get_current_tenant_id()` everywhere. Remove `current_tenant_id()` from `init-db.sql`. Add a migration that drops the old function. Add a CI check that greps for the old function name. | Backend 1 |
| **R05** | **Infrastructure** | **No Nginx wildcard configuration exists.** The docker-compose.yml has Nginx commented out (lines 114-125) and no `docker/nginx/nginx.conf` file exists. Without this, subdomain routing cannot work in any environment beyond localhost. | 5 | 4 | **20** | Create Nginx config immediately in Sprint 1, week 1. Template: wildcard `server_name ~^(?<subdomain>.+)\.simsplus\.io$`, proxy_pass to frontend with `X-Subdomain` header injection. Test with at least 3 different subdomains locally. | DevOps |
| **R06** | **Infrastructure** | **No Terraform/IaC exists.** The `/infrastructure` directory is empty. AWS provisioning (EKS, RDS, ElastiCache, S3) cannot begin until IaC is written. Lead time for EKS cluster provisioning is typically 2-4 weeks. | 4 | 4 | **16** | Begin Terraform module development in Sprint 1. Start with RDS + ElastiCache (lowest risk). Defer EKS to Sprint 3-4 if timeline pressure exists -- use EC2 or ECS Fargate as interim. | DevOps |
| **R07** | **Technical** | **Connection pool tenant context leaking.** `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/db/session.py` uses a connection pool (pool_size=10, max_overflow=20). PostgreSQL session variables persist on the connection. If `clear_tenant_context()` fails (line 55-58 in `deps.py` catches and ignores errors), the next request on that connection inherits the previous tenant's context. | 3 | 5 | **15** | Add a connection pool event listener (`pool_checkout`) that resets ALL session variables. Add an integration test that verifies context does not leak between sequential requests. See Appendix B.3 for implementation. | Backend 2 |
| **R08** | **Technical** | **Redis cache key collision between tenants.** No tenant-prefixed key strategy is visible in the codebase. If tenant-scoped data is cached without tenant prefix, School A could see School B's cached data. | 3 | 5 | **15** | Establish convention: all Redis keys MUST use format `{tenant_id}:{feature}:{key}`. Audit existing Redis usage in rate_limit.py and token_blacklist. Create a `TenantRedis` wrapper class that automatically prefixes keys. | Backend 1 |
| **R09** | **Infrastructure** | **Local development subdomain testing is difficult.** Developers cannot use `presec.simsplus.io` locally. The tenant middleware supports `*.localhost` but many browsers and tools handle `.localhost` subdomains inconsistently. | 4 | 3 | **12** | Document two approaches: (1) `/etc/hosts` entries for `presec.localhost`. (2) `X-Subdomain` header in development mode. Create a `scripts/setup-local-dns.sh` helper. | DevOps |
| **R10** | **Integration** | **Cloudflare DNS propagation delay.** Wildcard DNS records can take 1-48 hours to propagate. If the domain is newly registered, nameserver delegation may take additional time. | 3 | 3 | **9** | Register domain and configure Cloudflare BEFORE Sprint 1 starts. Use Cloudflare proxied mode for immediate resolution. Have fallback: use `X-Subdomain` header in staging until DNS propagates. | DevOps |
| **R11** | **Performance** | **Tenant lookup on every request.** TenantMiddleware queries the DB on every request (line 269-278 in `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/middleware/tenant.py`). At 100 req/sec, this adds 100 DB queries/sec just for tenant resolution. | 4 | 3 | **12** | Implement Redis caching for tenant lookups (S2-11). Cache key: `tenant:subdomain:{subdomain}`. TTL: 5 minutes. Target: < 1ms for cached lookups vs current ~5-10ms for DB. | Backend 2 |
| **R12** | **Knowledge** | **Team unfamiliarity with PostgreSQL RLS.** RLS is a specialized PostgreSQL feature. Misconfiguration is silent -- data appears to work but isolation is broken. The existing codebase shows evidence of multiple RLS rework attempts (3 separate migrations touching RLS). | 4 | 5 | **20** | Conduct a 2-hour team workshop on PostgreSQL RLS before Sprint 1. Create an "RLS Testing Playbook" document. Require every PR that touches a tenant-scoped table to include an RLS isolation test. | Tech Lead |
| **R13** | **Schedule** | **Alembic migration chain complexity.** 40+ existing migrations create a complex dependency chain. Consolidating them risks data loss on existing development databases. Running them sequentially on fresh databases is slow. | 3 | 3 | **9** | Do NOT consolidate migrations that have been applied to any shared environment. Create a `squash_to_baseline.py` script for fresh installations only. Add CI step that runs all migrations on a clean database. | Backend 1 |
| **R14** | **Technical** | **`db/base.py` model import list is incomplete.** Only `Tenant` and `User` are imported in `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/db/base.py`. All other models (School, Student, Staff, etc.) are commented out. Alembic autogenerate will not detect changes to unimported models. | 4 | 3 | **12** | Uncomment and import ALL model classes in `db/base.py`. Add a CI check that verifies all models in `app/models/` are imported in `db/base.py`. | Backend 1 |
| **R15** | **Technical** | **Frontend CI uses Node 20, but Next.js 16 may require Node 22.** `/Users/harrymcninson/Documents/projects/sims-plus/.github/workflows/frontend-ci.yml` line 32 specifies `node-version: '20'`. Next.js 16.1.1 targets Node 22 LTS. | 3 | 2 | **6** | Verify Next.js 16 Node.js compatibility matrix. Update `frontend-ci.yml` to match the version used in the frontend Dockerfile. | Frontend 1 |
| **R16** | **Security** | **JWT token forging risk with weak SECRET_KEY.** In CI, SECRET_KEY is `test-secret-key` (backend-ci.yml line 97). If this value leaks to production, tokens can be forged. | 3 | 5 | **15** | Enforce minimum SECRET_KEY length (64+ characters) via Pydantic validator. Generate with `openssl rand -base64 64`. Store in AWS Secrets Manager. | Tech Lead |
| **R17** | **Technical** | **BaseHTTPMiddleware limitations.** The tenant middleware uses Starlette's `BaseHTTPMiddleware`, which reads the entire request body into memory and creates a new task per request (can break contextvars patterns). | 3 | 3 | **9** | For Sprint 1-2, this is acceptable. Plan migration to pure ASGI middleware in Sprint 5-6 when performance becomes critical. | Backend 1 |
| **R18** | **Schedule** | **No `.env.example` file exists.** New developers cannot set up the project without manually discovering required environment variables from `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/config.py`. | 5 | 2 | **10** | Create `.env.example` on Sprint 1, day 1 with all required variables and safe defaults. Add to README. | Tech Lead |
| **R19** | **Security** | **Subdomain validation allows 4+ character subdomains only.** The `extract_subdomain_from_host()` function requires `len(subdomain) >= 4`. This blocks legitimate short school codes like "aci" or "gis". | 2 | 2 | **4** | Reduce minimum to 3 characters. Add validation for `[a-z0-9-]` only, no leading/trailing hyphen. | Backend 1 |
| **R20** | **Performance** | **Database connection pool exhaustion under load.** Each request uses 2 connections: one from TenantMiddleware (line 218 of tenant.py) and one from `get_db()`. Pool of 30 (10+20) is exhausted at just 15 concurrent requests. | 3 | 4 | **12** | Cache tenant lookups in Redis (S2-11) to eliminate the middleware DB connection. Alternatively, refactor TenantMiddleware to use a lightweight single-use connection outside the pool. Increase pool_size for production. | Backend 2 |
| **R21** | **Technical** | **CORS configuration does not support wildcard subdomains.** `CORS_ALLOW_SUBDOMAIN_PATTERN` regex exists in config but is NOT used in the CORS middleware setup in `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/main.py` (line 63). Each school subdomain has a different origin that is not in the allowed list. | 4 | 3 | **12** | Implement dynamic CORS origin validation using a custom middleware that validates origins against the `*.simsplus.io` regex pattern. | Backend 1 |
| **R22** | **Infrastructure** | **No monitoring or alerting infrastructure.** Prometheus, Grafana, and Loki are mentioned in docs but nothing is provisioned. Without monitoring, RLS failures and pool exhaustion go undetected. | 3 | 3 | **9** | Defer full monitoring to Sprint 3-4. For now: add structured logging (structlog is in requirements), set up Sentry (config exists in settings), add basic CloudWatch metrics. | DevOps |
| **R23** | **Compliance** | **Student data protection requirements not yet codified.** Ghana Data Protection Act 2012 applies to student PII. No classification policy or consent mechanism exists. | 2 | 4 | **8** | Not a Sprint 1-2 blocker. Must be addressed before beta launch (Sprint 17-18). Create data classification document identifying PII fields. | PM |
| **R24** | **Technical** | **`from __future__ import annotations` gotcha.** Causes `AssertionError` on 204 responses. No automated check exists. | 3 | 3 | **9** | Add a CI lint rule that flags this import in any file under `app/api/v1/endpoints/`. | Backend 1 |
| **R25** | **Technical** | **FastAPI version is outdated.** `requirements.txt` pins `fastapi==0.109.2` (February 2024). Current FastAPI is 0.115.x+ with security patches. | 2 | 3 | **6** | Audit changelog for security fixes. If none critical, defer upgrade to Sprint 5-6. If patches exist, upgrade in Sprint 1 with full test run. | Tech Lead |

### Risk Heat Map

```
                    Impact
          1     2     3     4     5
        +-----+-----+-----+-----+-----+
    5   |     | R18 |     | R05 |R01  |
        |     |     |     |     |R02  |
L   4   |     |     |R14  | R06 |R12  |
i       |     |     |R21  | R04 |     |
k   3   |     |     |R09  | R20 |R03  |
e       |     |     |R13  |     |R07  |
l   2   |     |     |R25  | R23 |R16  |
i       |     | R19 |     |     |     |
h   1   |     |     |     |     |     |
o       |     |     |     |     |     |
o       +-----+-----+-----+-----+-----+
d
```

**Critical Risks (Score >= 15):** R01, R02, R03, R04, R05, R06, R07, R08, R12, R16

**High Risks (Score 10-14):** R09, R11, R14, R18, R20, R21

**Medium Risks (Score 6-9):** R10, R13, R15, R17, R22, R24, R25

**Low Risks (Score < 6):** R19, R23

---

## 3. Dependency Map

### Internal Dependency Chain

```
S1-01 (Git Repo)
  |
  +---> S1-02 (Docker Environment)
  |       |
  |       +---> S1-03 (FastAPI Scaffold)
  |       |       |
  |       |       +---> S2-01 (Tenants Table)
  |       |       |       |
  |       |       |       +---> S2-02 (Reserved Subdomains)
  |       |       |       +---> S2-05 (Schools Table)
  |       |       |       +---> S2-06 (Users Table)
  |       |       |       +---> S2-11 (Tenant Cache)
  |       |       |
  |       |       +---> S2-03 (RLS Policies) *** CRITICAL PATH ***
  |       |               |
  |       |               +---> S2-04 (Tenant Context Functions)
  |       |               |       |
  |       |               |       +---> S2-07 (get_db Enforcement)
  |       |               |               |
  |       |               |               +---> S2-12 (Integration Tests) *** CRITICAL PATH ***
  |       |               |
  |       |               +---> S2-08 (Migration Consolidation)
  |       |
  |       +---> S1-04 (Next.js Setup)
  |       |       |
  |       |       +---> S2-09 (Next.js Middleware)
  |       |               |
  |       |               +---> S2-10 (Tenant Provider)
  |       |
  |       +---> S1-05 (PostgreSQL Setup)
  |               |
  |               +---> S2-03 (RLS Policies)
  |
  +---> S1-06 (CI/CD Pipeline)
  |
  +---> S1-07 (Cloudflare DNS) --- EXTERNAL DEPENDENCY
          |
          +---> S1-08 (SSL Certificate)
                  |
                  +---> S1-09 (Nginx Config)
                          |
                          +---> S1-10 (Local Dev Setup)
                          +---> S2-09 (Next.js Middleware)
```

### Critical Path

```
S1-01 --> S1-02 --> S1-05 --> S2-03 --> S2-04 --> S2-07 --> S2-12
(0.5d)    (2d)      (1.5d)    (5d)      (2d)      (2d)     (5d)
                                                          = 18 days SEQUENTIAL
```

**The critical path is 18 developer-days of sequential work.** This means even with infinite developers, Sprint 1-2 cannot complete in less than 18 working days (approximately 3.5 weeks). The 4-week window is tight but feasible with no slippage.

### External Dependencies

| Dependency | Owner | Risk Level | Lead Time | Notes |
|------------|-------|------------|-----------|-------|
| Domain registration (`simsplus.io`) | PM/Founder | Medium | 1-2 days | Must verify if already registered |
| Cloudflare account + plan | PM/DevOps | Low | < 1 hour | Free plan supports wildcard DNS |
| AWS account + IAM setup | DevOps | Medium | 1-3 days | Cannot begin IaC without this |
| GitHub repository + Actions secrets | Tech Lead | Low | < 1 hour | Verify secrets are configured |
| PostgreSQL 16 RLS knowledge | Backend team | High | Ongoing | Book 2-hour workshop before Sprint 1 |

---

## 4. Parallel Work Tracks

### Week 1

```
Track A (DevOps):        S1-01 --> S1-02 --> S1-07 (Cloudflare) --> S1-08 (SSL)
Track B (Backend 1):     S1-03 (FastAPI verify) --> S1-05 (PostgreSQL setup)
Track C (Backend 2):     RLS research + workshop prep --> Begin S2-03 (RLS rework design)
Track D (Frontend 1):    S1-04 (Next.js verify) --> Begin S2-09 (middleware design)
```

**Convergence Point:** End of Week 1 -- Docker environment + DB must be working for all tracks.

### Week 2

```
Track A (DevOps):        S1-09 (Nginx config) --> S1-10 (Local dev setup) --> S1-06 (CI/CD)
Track B (Backend 1):     S2-01 --> S2-02 --> S2-05 --> S2-06 (Table verification)
Track C (Backend 2):     S2-03 (RLS implementation) --> S2-04 (Context functions)
Track D (Frontend 1):    S2-09 (Next.js middleware) --> S2-10 (Tenant Provider)
```

**Convergence Point:** End of Week 2 -- RLS policies and Nginx routing must be working. Frontend team needs working subdomain routing to test.

### Week 3

```
Track A (DevOps):        S2-13 (Health checks) --> Infrastructure monitoring
Track B (Backend 1):     S2-08 (Migration consolidation) --> S2-11 (Tenant cache)
Track C (Backend 2):     S2-07 (get_db enforcement) --> Begin S2-12 (Integration tests)
Track D (Frontend 1):    Integration testing with backend --> Fix cross-origin issues
Track E (QA):            S2-12 (RLS isolation tests) --> Cross-tenant access tests
```

**Convergence Point:** End of Week 3 -- All backend + frontend components integrated. RLS tests passing.

### Week 4 (Buffer + Quality)

```
All Tracks:              S2-12 continued --> Bug fixes --> Documentation
                         Performance testing --> Security audit --> Sprint review
```

### Handoff Points

| From | To | What | When |
|------|----|------|------|
| DevOps (S1-02) | All teams | Working Docker environment with `.env.example` | End of Day 2 |
| DevOps (S1-09) | Frontend (S2-09) | Working Nginx wildcard config | End of Week 1 |
| Backend 2 (S2-03) | Backend 1, QA | Verified RLS policies | Mid-Week 2 |
| Backend 2 (S2-04) | Backend 2 (S2-07) | Tenant context functions | End of Week 2 |
| Frontend (S2-09) | QA | Working subdomain detection | End of Week 2 |
| All backend (S2-01-07) | QA (S2-12) | Complete backend ready for integration tests | Start of Week 3 |

---

## 5. Time Estimates

| Component | Optimistic | Realistic | Pessimistic | Confidence |
|-----------|-----------|-----------|-------------|------------|
| **S1-01** Git Repo | 0.25d | 0.5d | 1d | 90% |
| **S1-02** Docker | 1d | 2d | 3d | 80% |
| **S1-03** FastAPI Scaffold | 0.5d | 1d | 2d | 85% |
| **S1-04** Next.js Setup | 1d | 2d | 3d | 75% -- Next.js 16 is relatively new |
| **S1-05** PostgreSQL Setup | 1d | 1.5d | 3d | 75% -- dual function issue needs care |
| **S1-06** CI/CD Pipeline | 1d | 2d | 4d | 70% -- CI debugging is unpredictable |
| **S1-07** Cloudflare DNS | 0.5d | 1d | 3d | 65% -- external dependency |
| **S1-08** SSL Certificate | 0.5d | 1d | 2d | 75% |
| **S1-09** Nginx Wildcard | 1.5d | 3d | 5d | 60% -- wildcard regex + proxy config is fiddly |
| **S1-10** Local Dev Setup | 0.5d | 1.5d | 3d | 60% -- OS-specific issues |
| **S2-01** Tenants Table | 0.25d | 0.5d | 1d | 90% -- already exists |
| **S2-02** Reserved Subdomains | 0.25d | 0.5d | 1d | 90% -- already exists |
| **S2-03** RLS Rework | 3d | 5d | 8d | **50% -- HIGHEST RISK** |
| **S2-04** Context Functions | 1d | 2d | 3d | 70% |
| **S2-05** Schools Table | 0.25d | 0.5d | 1d | 90% -- already exists |
| **S2-06** Users Table | 0.25d | 0.5d | 1d | 90% -- already exists |
| **S2-07** get_db Enforcement | 1d | 2d | 3d | 70% |
| **S2-08** Migration Consolidation | 1d | 2d | 4d | 65% |
| **S2-09** Next.js Middleware | 1.5d | 3d | 5d | 60% -- Next.js 16 middleware API |
| **S2-10** Tenant Provider | 0.5d | 1.5d | 2.5d | 75% -- already exists |
| **S2-11** Tenant Cache | 1d | 2d | 3d | 70% |
| **S2-12** Integration Tests | 3d | 5d | 8d | **50% -- testing RLS is subtle** |
| **S2-13** Health Checks | 0.5d | 1d | 1.5d | 85% |

### Aggregate Estimates

| Scenario | Total | Notes |
|----------|-------|-------|
| **Optimistic** | 21 dev-days | Everything works first try. No blockers. |
| **Realistic** | 41 dev-days | Normal debugging. One external blocker. |
| **Pessimistic** | 67 dev-days | RLS takes 8 days. Nginx takes 5 days. CI issues. DNS delays. |
| **Buffered Realistic (25%)** | 51 dev-days | Recommended planning target. |

### Can This Fit in 4 Weeks?

With **3 developers** full-time for 4 weeks = **60 developer-days** of capacity.

- **Realistic (41 days):** Fits with 19 days slack. Comfortable.
- **Pessimistic (67 days):** Does NOT fit. Would need 4 developers or scope reduction.
- **Buffered realistic (51 days):** Fits with 9 days slack. Tight but manageable.

**Recommendation:** Plan for the buffered realistic scenario (51 days). The 9 days of slack account for meetings, context switching, code reviews, and unforeseen issues. If the team has no prior RLS experience, add a 4th developer or defer S2-08 (migration consolidation) and S2-11 (tenant cache) to Sprint 3.

---

## 6. Infrastructure Requirements

### Pre-Sprint Requirements (Must Be Done BEFORE Sprint 1 Starts)

| # | Requirement | Purpose | Lead Time | Cost | Status |
|---|-------------|---------|-----------|------|--------|
| I-01 | Domain `simsplus.io` registered | DNS, SSL, all environments | 1-2 days | ~$15/year | **VERIFY** |
| I-02 | Cloudflare account activated | DNS management, WAF, CDN | < 1 hour | Free | **VERIFY** |
| I-03 | GitHub repository with Actions enabled | CI/CD, code hosting | < 1 hour | $4/user/mo private | **VERIFY** |
| I-04 | AWS account with billing alerts | Infrastructure provisioning | 1-3 days | Budget: $50/mo initial | **VERIFY** |
| I-05 | Development machines set up | Docker, Python 3.12, Node 22, psql client | 1-2 hrs/machine | $0 | **VERIFY** |
| I-06 | `.env.example` file created | Developer onboarding | 30 minutes | $0 | **MISSING** |

### Sprint 1-2 Infrastructure

| # | Requirement | Purpose | Lead Time | Monthly Cost | When Needed |
|---|-------------|---------|-----------|-------------|-------------|
| I-07 | Cloudflare wildcard DNS | Subdomain routing | 1 hr + propagation | $0 | Sprint 1, Week 1 |
| I-08 | Cloudflare Universal SSL | HTTPS for all subdomains | Automatic | $0-$10 | Sprint 1, Week 1 |
| I-09 | AWS RDS PostgreSQL 16 (staging) | Staging database | 30 min | ~$30/mo | Sprint 1, Week 2 |
| I-10 | AWS ElastiCache Redis 7 (staging) | Staging cache | 30 min | ~$15/mo | Sprint 1, Week 2 |
| I-11 | AWS S3 bucket | File uploads | 5 min | ~$5/mo | Sprint 2, Week 1 |
| I-12 | AWS ECR repository | Docker image registry | 5 min | ~$2/mo | Sprint 1, Week 2 |
| I-13 | SendGrid account (dev tier) | Email verification | 1 hour | Free | Sprint 2 |
| I-14 | Sentry project | Error tracking | 15 min | Free | Sprint 1, Week 1 |

**Total Infrastructure Cost for Sprint 1-2: approximately $73/month** -- well within the $392/month budget.

---

## 7. Multi-Tenancy Specific Risks -- Deep Dive

### 7.1 RLS Policy Misconfiguration Scenarios

**Current State (VULNERABLE):** The comprehensive RLS policy in `/Users/harrymcninson/Documents/projects/sims-plus/backend/alembic/versions/20260104_0500_comprehensive_rls.py` creates this policy on every tenant-scoped table:

```sql
CREATE POLICY tenant_isolation_{table} ON {table}
FOR ALL TO PUBLIC
USING (
    (tenant_id = get_current_tenant_id())
    OR (get_current_tenant_id() IS NULL)         -- VULNERABILITY
    OR (current_setting('app.is_platform_admin', true) = 'true')  -- VULNERABILITY
)
```

**Scenario 1 -- No Tenant Context Set:**
A request arrives without a subdomain (e.g., hitting the API directly via IP). TenantMiddleware skips context for "public paths" but the classification may be wrong. `get_db()` proceeds without setting tenant context. `get_current_tenant_id()` returns NULL. RLS evaluates `NULL IS NULL` = TRUE. **Result: ALL tenant data across ALL schools is returned.**

**Scenario 2 -- Session Variable Injection:**
An attacker finds a way to execute `SET app.is_platform_admin = 'true'`. RLS evaluates the condition as TRUE. **Result: Full cross-tenant data access.**

**Scenario 3 -- Connection Pool Context Leak:**
Request A completes but `clear_tenant_context()` fails silently (the except clause in deps.py catches all exceptions). Request B gets the same pooled connection with stale context. **Result: Request B sees the wrong tenant's data.**

**Recommended Fix (All Three Scenarios):**

```sql
-- Hardened RLS policy (no bypasses)
CREATE POLICY tenant_strict_isolation ON {table}
FOR ALL TO app_user
USING (tenant_id = get_current_tenant_id())
WITH CHECK (tenant_id = get_current_tenant_id());
```

Combined with two database roles:
- `app_user`: Non-superuser, RLS enforced. Used by application.
- `sims_admin`: Superuser with BYPASSRLS. Used only by Alembic migrations. Never used by application code.

If `get_current_tenant_id()` returns NULL, the USING clause evaluates `tenant_id = NULL` which is NULL (false). No rows returned. **Safe default.**

### 7.2 NULL tenant_id Bypass Vectors

| Vector | Probability | Severity | Mitigation |
|--------|-------------|----------|------------|
| Direct API access without subdomain | High | Critical | TenantMiddleware blocks most paths, but PUBLIC_PATHS may be too permissive |
| Background job (Celery) without tenant context | High (when implemented) | Critical | Celery tasks MUST accept `tenant_id` as first argument. Decorator to set DB context. |
| Webhook handler without subdomain | Medium | Critical | Webhook endpoints must extract tenant_id from payload, not subdomain |
| Test fixture setup | Medium | Low (test only) | Test fixtures must use admin engine for setup, app_user engine for verification |

### 7.3 Cache Key Collision Risks

Current Redis usage:
1. **Rate limiting** -- keyed by IP + path (global, not tenant-specific): LOW risk
2. **Token blacklist** -- keyed by token string (globally unique): LOW risk
3. **Future tenant cache (S2-11)** -- MUST use tenant-prefixed keys

**Required Convention:**
```
{tenant_id}:{feature}:{specific_key}    -- Tenant-scoped data
global:{feature}:{key}                   -- Global data (rate limits, blacklist)
```

### 7.4 JWT Token Risks

| Attack | Current Protection | Gap | Fix |
|--------|-------------------|-----|-----|
| Token forging | HS256 + SECRET_KEY | Weak key in CI | Enforce 64+ char key |
| Cross-tenant replay | `validate_token_tenant` dependency | Only used when explicitly included | Make cross-tenant check the DEFAULT |
| Refresh token cross-tenant | Refresh includes tenant_id | Not verified in refresh endpoint | Add tenant_id check to refresh |

### 7.5 Subdomain Spoofing

| Scenario | Risk | Mitigation |
|----------|------|------------|
| Similar subdomain registration | Low | Validate against reserved list + existing tenants |
| IDN homograph attack | Low | Regex only allows `[a-z0-9-]`. No Unicode. |
| Subdomain takeover on soft delete | Medium | Check both active AND soft-deleted tenants |

### 7.6 Tenant Suspension Enforcement Gaps

The middleware checks `is_active` on every request. However:

1. **Existing JWT tokens remain valid after suspension** -- users can continue for up to 15 minutes (access token TTL) or 7 days (refresh token TTL).
2. **No webhook to notify users of suspension** -- confusing 403 errors.
3. **Background jobs continue running** for suspended tenants.

**Mitigations:**
1. On suspension: mass-revoke all tokens via Redis blacklist
2. Add `tenant_suspended_at` timestamp for grace period notifications
3. Celery tasks should check tenant status before processing

---

## 8. Recommended Sprint Sequencing

### Should Sprint 1-2 Be Split Differently?

**Yes.** The current split is suboptimal. Here is the recommended restructuring:

### Recommended Sprint 1 (Weeks 1-2): "Environment + Security Foundation"

**Goal:** Every developer can run the project locally with working subdomain routing. RLS is hardened.

| Priority | Component | Rationale |
|----------|-----------|-----------|
| P0 (Day 1) | S1-01, S1-06 skeleton, `.env.example` | Unblocks all developers |
| P0 (Day 1-2) | S1-02 Docker + Nginx | Unblocks local development |
| P0 (Day 1-3) | S1-05 PostgreSQL (fix dual function, add app_user) | Unblocks RLS work |
| P1 (Day 2-5) | S2-03 RLS policy rework | CRITICAL security foundation |
| P1 (Day 3-5) | S1-07 + S1-08 Cloudflare | Can proceed in parallel |
| P1 (Day 5-7) | S1-09 Nginx wildcard | Depends on DNS |
| P1 (Day 5-7) | S2-04 Context functions | Depends on S1-05 |
| P2 (Day 7-10) | S1-10 Local dev docs, S1-03, S1-04 | Can be quick |

**Sprint 1 Exit Criteria:**
- `docker-compose up` starts all services
- Nginx routes `presec.localhost` to frontend
- RLS policies are hardened (no NULL bypass)
- `init-db.sql` creates correct functions and roles
- CI pipeline runs lint + basic tests
- `.env.example` exists

### Recommended Sprint 2 (Weeks 3-4): "Multi-Tenant Data Layer + Integration"

**Goal:** Complete tenant isolation verified by automated tests.

| Priority | Component | Rationale |
|----------|-----------|-----------|
| P0 (Day 1-2) | S2-01/02/05/06 Tables | Quick wins, already exist |
| P0 (Day 1-3) | S2-07 get_db enforcement | Critical security |
| P1 (Day 2-5) | S2-09 Next.js middleware | Frontend subdomain detection |
| P1 (Day 3-5) | S2-10, S2-11 | Provider + cache |
| P2 (Day 5-8) | S2-12 Integration tests | Validates everything |
| P2 (Day 6-8) | S2-08, S2-13 | Nice-to-have |

**Sprint 2 Exit Criteria:**
- All tenant-scoped tables have RLS policies
- Cross-tenant access test passes
- NULL context test passes (no context = no data)
- Next.js middleware extracts subdomain
- Tenant lookup cached in Redis (< 1ms p95)
- CI includes RLS isolation tests

### What Can Be Deferred to Sprint 3-4

| Component | Why It Can Wait |
|-----------|-----------------|
| S2-08 Migration consolidation | Not blocking any functionality |
| Full monitoring (Prometheus/Grafana) | Sentry + CloudWatch sufficient |
| Terraform IaC for EKS | Docker Compose sufficient for development |
| CORS wildcard subdomain support | Use `X-Subdomain` header in development |

---

## 9. Quality Gates

### Sprint 1 Quality Gates

- [ ] **QG-1.1:** `docker-compose up` starts all 4 services without errors within 2 minutes
- [ ] **QG-1.2:** `curl http://localhost:8000/health` returns `{"status": "healthy"}`
- [ ] **QG-1.3:** `curl http://localhost:3000` returns the Next.js page
- [ ] **QG-1.4:** Nginx routes `http://presec.localhost/api/v1/health` to backend with `X-Subdomain: presec`
- [ ] **QG-1.5:** `init-db.sql` creates `app_user` role and correct tenant context functions
- [ ] **QG-1.6:** `init-db.sql` does NOT create the old `current_tenant_id()` function
- [ ] **QG-1.7:** `.env.example` file exists with documented variables
- [ ] **QG-1.8:** Backend CI pipeline passes: lint, test, build
- [ ] **QG-1.9:** Frontend CI pipeline passes: lint, type-check, build
- [ ] **QG-1.10:** RLS policies do NOT have NULL bypass
- [ ] **QG-1.11:** Two PostgreSQL roles exist: admin (superuser) and app_user (RLS enforced)
- [ ] **QG-1.12:** Cloudflare DNS wildcard resolves (or documented workaround exists)

### Sprint 2 Quality Gates

- [ ] **QG-2.1:** All tenant-scoped tables have RLS policies (verified by querying `pg_policies`)
- [ ] **QG-2.2:** **CRITICAL:** Connect as `app_user` without setting tenant context. `SELECT * FROM users` returns **0 rows**
- [ ] **QG-2.3:** **CRITICAL:** Set context to Tenant A. `SELECT * FROM users` returns ONLY Tenant A users
- [ ] **QG-2.4:** **CRITICAL:** Set context to Tenant A. `INSERT INTO users (..., tenant_id) VALUES (..., Tenant_B_ID)` is REJECTED
- [ ] **QG-2.5:** `get_db()` raises HTTP 400 on non-public route without tenant context
- [ ] **QG-2.6:** `clear_tenant_context()` is called reliably after every request
- [ ] **QG-2.7:** Next.js middleware extracts subdomain from Host header
- [ ] **QG-2.8:** TenantProvider successfully fetches and provides tenant data
- [ ] **QG-2.9:** Tenant lookup is cached in Redis with TTL
- [ ] **QG-2.10:** All existing tests pass
- [ ] **QG-2.11:** At least 10 new tests specifically for multi-tenant isolation
- [ ] **QG-2.12:** No regression in existing endpoint behavior

---

## 10. Blockers and Pre-requisites

### Hard Blockers (Sprint Cannot Start Without These)

| # | Blocker | Resolution | ETA |
|---|---------|------------|-----|
| B-01 | Domain `simsplus.io` must be registered | Register via Namecheap/GoDaddy | 1-2 days |
| B-02 | All developers must have Docker Desktop | Install Docker Desktop 4.x | 2 hrs/dev |
| B-03 | Python 3.12 available on all dev machines | Install via `pyenv` | 1 hr/dev |
| B-04 | Node.js 22 LTS available | Install via `nvm install 22` | 30 min/dev |
| B-05 | GitHub Actions enabled | Verify in repo Settings | 15 min |

### Soft Blockers

| # | Blocker | Workaround | Impact of Not Resolving |
|---|---------|------------|------------------------|
| B-06 | No team member has RLS production experience | Workshop + pair programming | 2-3x longer RLS implementation |
| B-07 | AWS account may lack IAM permissions | Use root account (not recommended) | Security risk |
| B-08 | DNS propagation delay (up to 48 hours) | Use `/etc/hosts` or `X-Subdomain` header | Frontend blocked on subdomain testing |
| B-09 | No `.env.example` exists | Reverse-engineer from config.py | 1-2 hrs lost per developer |

### Knowledge Gaps

| Gap | Resolution Strategy | Time to Resolve |
|-----|---------------------|----------------|
| PostgreSQL RLS policies | Workshop + docs + pair programming | 4-8 hours |
| Async SQLAlchemy 2.0 | Review docs, examine existing services | 2-4 hours |
| Next.js 16 middleware | Next.js 16 docs, migration guide from 15 | 2-4 hours |
| Nginx wildcard config | Nginx docs + tested example configs | 2-4 hours |

### Pre-Sprint Checklist

```
[ ] Domain registered and nameservers pointed to Cloudflare
[ ] Cloudflare account created with domain added
[ ] AWS account created with IAM admin user
[ ] GitHub repo has branch protection on main
[ ] GitHub Actions secrets configured
[ ] All developers have: Docker, Python 3.12, Node 22, git
[ ] Team has completed 2-hour RLS workshop
[ ] Tech Lead has created .env.example
[ ] Product owner has confirmed Sprint 1-2 scope
```

---

## Appendix A: Specific Code Issues Found During Analysis

### Issue 1: `get_db()` Does Not Enforce Tenant Context

**File:** `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/api/deps.py`, lines 41-46

```python
# Current code (VULNERABLE):
tenant_id = getattr(request.state, "tenant_id", None)
if tenant_id:
    await session.execute(...)
# If tenant_id is None, session proceeds WITHOUT context
```

**Recommended Fix:** Create two dependencies -- `get_db()` that raises 400 without context, and `get_unscoped_db()` for platform-level operations:

```python
async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Tenant-scoped DB session. Raises 400 if no tenant context."""
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Tenant context required")
    # ... set context and yield session

async def get_unscoped_db() -> AsyncGenerator[AsyncSession, None]:
    """Unscoped DB session for platform operations. Use sparingly."""
    # ... yield session without tenant context
```

### Issue 2: Comprehensive RLS Migration Overwrites Security Fixes

**Migration chain problem:**
1. `security_fixes_001` -- Removes NULL bypass
2. `add_schools_table` -- No RLS changes
3. `comprehensive_rls` -- **Drops ALL policies and recreates WITH NULL bypass**

The security fix in step 1 is effectively **reversed** by step 3.

### Issue 3: `db/base.py` Only Imports 2 of 14 Models

**File:** `/Users/harrymcninson/Documents/projects/sims-plus/backend/app/db/base.py`

Only `Tenant` and `User` are imported. All other models are commented out. Alembic autogenerate will miss changes to School, Student, Staff, Academic, Exam, Finance, Preschool, and Attendance models.

### Issue 4: Frontend CI Uses Node 20

**File:** `/Users/harrymcninson/Documents/projects/sims-plus/.github/workflows/frontend-ci.yml`, line 32

Specifies `node-version: '20'` but `package.json` has Next.js 16.1.1 which targets Node 22 LTS.

---

## Appendix B: Recommended Architecture Changes

### B.1: Two-Database-User Pattern

```sql
-- In init-db.sql:
CREATE USER sims_admin WITH PASSWORD '...' SUPERUSER;  -- Migrations only
CREATE USER app_user WITH PASSWORD '...';               -- Application only
GRANT CONNECT ON DATABASE sims_plus TO app_user;
GRANT USAGE ON SCHEMA public TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user;
-- FORCE RLS on all tenant tables (even for table owner)
ALTER TABLE users FORCE ROW LEVEL SECURITY;
ALTER TABLE schools FORCE ROW LEVEL SECURITY;
```

### B.2: Hardened RLS Policy Template

```sql
CREATE POLICY tenant_strict_{table} ON {table}
FOR ALL TO app_user
USING (tenant_id = get_current_tenant_id())
WITH CHECK (tenant_id = get_current_tenant_id());
-- No NULL fallback. No is_platform_admin. No bypasses.
-- NULL context = NULL comparison = FALSE = no rows. Safe.
```

### B.3: Connection Pool Reset Handler

```python
# In session.py -- prevents tenant context leaking between requests
from sqlalchemy import event

@event.listens_for(engine.sync_engine, "checkout")
def reset_tenant_context(dbapi_connection, connection_record, connection_proxy):
    cursor = dbapi_connection.cursor()
    cursor.execute("SELECT clear_tenant_context()")
    cursor.close()
```

---

## Appendix C: Sprint 1-2 Test Plan Outline

### Critical RLS Isolation Tests

```python
class TestRLSIsolation:
    async def test_no_context_returns_zero_rows(self, app_user_session):
        """Without tenant context, queries return 0 rows."""
        result = await app_user_session.execute(text("SELECT * FROM users"))
        assert result.fetchall() == []

    async def test_tenant_a_cannot_see_tenant_b(self, ...):
        """Tenant A's data is invisible to Tenant B."""

    async def test_tenant_cannot_insert_other_tenant_data(self, ...):
        """Tenant A cannot insert data with Tenant B's tenant_id."""

    async def test_context_cleared_between_requests(self, ...):
        """Tenant context is properly cleared after each request."""
```

### Tenant Middleware Tests

```python
class TestTenantMiddleware:
    async def test_valid_subdomain_sets_context(self, client): ...
    async def test_invalid_subdomain_returns_404(self, client): ...
    async def test_suspended_tenant_returns_403(self, client): ...
    async def test_reserved_subdomain_ignored(self, client): ...
    async def test_x_subdomain_header_accepted(self, client): ...
    async def test_public_paths_skip_tenant(self, client): ...
```

### Cross-Tenant Auth Tests

```python
class TestCrossTenantAuth:
    async def test_token_from_tenant_a_rejected_on_tenant_b(self, client): ...
    async def test_token_without_tenant_id_rejected(self, client): ...
```

---

*This document should be reviewed by the Tech Lead and updated after Sprint 1-2 retrospective with actual versus estimated effort data.*