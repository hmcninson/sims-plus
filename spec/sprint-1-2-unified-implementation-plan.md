# SIMS Plus -- Sprint 1-2 Unified Implementation Plan

**Version:** 1.0
**Date:** 15 February 2026
**Status:** Ready for Implementation
**Sprint Duration:** 4 weeks (2 x 2-week sprints)
**Synthesized From:** Solution Architecture, Multi-Tenancy Architecture, Risk Analysis

---

## Executive Summary

Sprint 1-2 establishes the foundational infrastructure for SIMS Plus -- a multi-tenant SaaS school management system for Ghanaian schools. This is the **highest-risk phase** of the project because every downstream sprint depends on the correctness of the multi-tenant infrastructure, RLS policies, and subdomain routing established here.

The existing codebase provides a substantial head start (40+ migrations, 15 endpoint files, 260+ frontend files), but several **critical security gaps** must be resolved before Sprint 1-2 can be considered complete.

**Overall Risk Level: MEDIUM-HIGH**
**Estimated Effort: 41-51 developer-days (with 25% buffer)**
**Minimum Team: 3 developers (1 DevOps, 1 Backend, 1 Frontend) full-time for 4 weeks**

---

## 1. Critical Findings Requiring Immediate Action

These were independently identified by both the Tenancy Architect and Risk Analyst:

| # | Severity | Finding | File | Action Required |
|---|----------|---------|------|-----------------|
| F1 | **CRITICAL** | RLS policies contain NULL bypass (`OR get_current_tenant_id() IS NULL`) | `alembic/versions/20260104_0500_comprehensive_rls.py` L82-84 | Write new migration: drop all policies, recreate with ONLY `tenant_id = get_current_tenant_id()`. No NULL fallback. |
| F2 | **CRITICAL** | `docker-compose.yml` connects as `postgres` superuser -- RLS completely bypassed | `docker-compose.yml` L57 | Create `sims_app_user` role in `init-db.sql`. Backend must connect as non-superuser. |
| F3 | **HIGH** | `get_db()` silently proceeds without tenant context | `backend/app/api/deps.py` L41-46 | Raise HTTP 400 if `tenant_id` is None on non-public routes. Create separate `get_unscoped_db()` for platform operations. |
| F4 | **HIGH** | Onboarding service inserts into RLS-protected tables without setting tenant context | `backend/app/services/onboarding.py` L131-168 | Add `set_tenant_context()` call after tenant creation flush, before school/user inserts. |
| F5 | **HIGH** | `is_platform_admin` session variable bypass in RLS | `comprehensive_rls.py` L86-87 | Remove entirely. Platform admin uses superuser DB role, not session variable. |
| F6 | **MEDIUM** | No Nginx wildcard configuration exists | `docker-compose.yml` L114-125 (commented out) | Create `docker/nginx/nginx.conf` with wildcard subdomain routing. |
| F7 | **MEDIUM** | No `.env.example` file | Root directory | Create on Day 1 with all required variables. |
| F8 | **MEDIUM** | `db/base.py` only imports 2 of 14 models | `backend/app/db/base.py` | Import ALL model classes for Alembic autogenerate. |
| F9 | **MEDIUM** | Dual tenant context functions (`current_tenant_id()` vs `get_current_tenant_id()`) | `init-db.sql` vs migrations | Standardize on `get_current_tenant_id()`. Remove the other. |
| F10 | **MEDIUM** | CORS not configured for wildcard subdomains | `backend/app/main.py` L63 | Implement `allow_origin_regex` for `*.simsplus.io`. |

---

## 2. Architecture Decisions (Confirmed by All Three Agents)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Multi-tenancy model** | Shared database with PostgreSQL RLS | Operational simplicity for 100s-1000s of schools. One DB to manage, migrate, backup. |
| **Tenant identification** | Subdomain-based (`{school}.simsplus.io`) | Schools feel ownership. Natural cookie scoping. Wildcard DNS/SSL covers all. |
| **Authentication** | JWT (15-min access / 7-day refresh) with Argon2id hashing | Stateless, mobile-friendly, GPU-resistant hashing. Blacklist via Redis. |
| **Data isolation** | 7-layer defense-in-depth | DNS → Nginx → Next.js middleware → FastAPI middleware → JWT validation → Service layer filter → PostgreSQL RLS |
| **Frontend data fetching** | Server Actions (no client-side API calls) | Tokens stay in HttpOnly cookies. No CORS issues. No API client in browser bundle. |
| **Database users** | Two-user pattern: `sims_admin` (superuser, migrations) + `sims_app_user` (non-superuser, RLS enforced) | RLS is only enforced for non-superuser connections. |
| **Frontend subdomain** | Next.js 16 `proxy.ts` | Runs on Node.js runtime (not Edge), full access to cookies/headers/filesystem. |

---

## 3. Parallel Work Tracks

### Week 1: Environment + Security Foundation

```
Track A (DevOps):
  Day 1:    S1-01  Git repo setup, branch protection, .env.example
  Day 1-2:  S1-02  Docker environment (fix docker-compose, add Nginx container)
  Day 3-5:  S1-07  Cloudflare DNS wildcard + SSL
  Day 5-7:  S1-09  Nginx wildcard subdomain config

Track B (Backend):
  Day 1-2:  S1-03  Verify FastAPI scaffold, fix middleware registration
  Day 2-3:  S1-05  Fix init-db.sql (add sims_app_user, standardize functions)
  Day 3-7:  S2-03  BEGIN RLS policy rework (critical path -- 5 days)

Track C (Frontend):
  Day 1-2:  S1-04  Verify Next.js 16 setup, Turbopack, Tailwind v4
  Day 3-5:  S2-09  BEGIN Next.js proxy.ts subdomain extraction
  Day 5-7:  S2-10  Tenant context provider integration
```

**Week 1 Exit Criteria:**
- [ ] `docker-compose up` starts all services (PostgreSQL, Redis, FastAPI, Next.js, Nginx)
- [ ] Nginx routes `presec.localhost` to frontend with `X-Subdomain: presec` header
- [ ] `init-db.sql` creates `sims_app_user` role and `get_current_tenant_id()` function
- [ ] `.env.example` exists with documented variables
- [ ] RLS policy rework design documented and implementation started

### Week 2: Tables + RLS + Routing

```
Track A (DevOps):
  Day 8-9:  S1-10  Local development subdomain docs + setup script
  Day 9-10: S1-06  CI/CD pipeline (lint, test, migration check)

Track B (Backend):
  Day 8-9:  S2-03  COMPLETE RLS policy rework (migration written + tested)
  Day 9-10: S2-04  Tenant context functions (set/get/clear)
  Day 10:   S2-01  Verify tenants table + S2-02 reserved_subdomains

Track C (Frontend):
  Day 8-10: S2-09  COMPLETE Next.js proxy.ts (cookie + header setting)
  Day 10:   S2-10  TenantProvider fetches and displays tenant branding
```

**Week 2 Convergence:** RLS policies hardened. Nginx routing working. Frontend subdomain detection complete. All tracks can begin integration.

### Week 3: Auth + Services + Integration

```
Track A (Backend):
  Day 11-12: S2-05 + S2-06  Verify schools + users tables
  Day 12-13: S2-07  get_db() tenant enforcement (raise 400 without context)
  Day 13-15: Auth   TenantMiddleware + AuthService + JWT endpoints

Track B (Frontend):
  Day 11-12: Auth   auth.action.ts (login, logout, refresh)
  Day 12-14: Auth   Login page with tenant branding, registration wizard
  Day 14-15: Auth   Dashboard layout + sidebar + auth guard

Track C (QA / Backend):
  Day 11-13: S2-11  Tenant lookup caching (Redis)
  Day 13-15: S2-12  BEGIN integration tests (RLS isolation, cross-tenant)
```

### Week 4: Testing + Hardening + Buffer

```
All Tracks:
  Day 16-17: S2-12  Complete integration tests (10+ RLS tests)
  Day 17-18: S2-08  Migration consolidation (optional, defer if needed)
  Day 18-19: S2-13  Health check enhancement + monitoring
  Day 19-20: Buffer  Bug fixes, documentation, sprint review
```

---

## 4. Component Breakdown with Estimates

### Sprint 1: Project Setup & Infrastructure (15.5 dev-days)

| ID | Component | Complexity | Effort | Owner | Dependencies |
|----|-----------|-----------|--------|-------|-------------|
| S1-01 | Git repo, branching, `.env.example` | Low | 0.5d | Tech Lead | None |
| S1-02 | Docker env (fix compose, add Nginx, health checks) | Medium | 2d | DevOps | S1-01 |
| S1-03 | FastAPI scaffold verification | Low | 1d | Backend | S1-02 |
| S1-04 | Next.js 16 setup verification | Medium | 2d | Frontend | S1-02 |
| S1-05 | PostgreSQL setup (fix init-db.sql, add app_user) | Medium | 1.5d | Backend | S1-02 |
| S1-06 | CI/CD pipeline (GitHub Actions) | Medium | 2d | DevOps | S1-01 |
| S1-07 | Cloudflare DNS wildcard | Medium | 1d | DevOps | External: domain |
| S1-08 | SSL certificate config | Medium | 1d | DevOps | S1-07 |
| S1-09 | Nginx wildcard subdomain routing | High | 3d | DevOps | S1-02, S1-07 |
| S1-10 | Local dev subdomain setup + docs | Medium | 1.5d | DevOps | S1-09 |

### Sprint 2: Multi-Tenancy Foundation (25.5 dev-days)

| ID | Component | Complexity | Effort | Owner | Dependencies |
|----|-----------|-----------|--------|-------|-------------|
| S2-01 | Tenants table verification + indexes | Low | 0.5d | Backend | S1-05 |
| S2-02 | Reserved subdomains verification + seed | Low | 0.5d | Backend | S1-05 |
| S2-03 | **RLS policy rework** (no NULL bypass, no admin bypass) | **Very High** | **5d** | Backend + Tech Lead | S1-05 |
| S2-04 | Tenant context functions (set/get/clear) | High | 2d | Backend | S2-03 |
| S2-05 | Schools table verification | Low | 0.5d | Backend | S2-01 |
| S2-06 | Users table verification | Low | 0.5d | Backend | S2-01 |
| S2-07 | `get_db()` tenant enforcement | High | 2d | Backend | S2-03, S2-04 |
| S2-08 | Alembic migration consolidation | Medium | 2d | Backend | S2-01—S2-06 |
| S2-09 | Next.js proxy.ts subdomain detection | High | 3d | Frontend | S1-04, S1-09 |
| S2-10 | React tenant context provider | Medium | 1.5d | Frontend | S2-09 |
| S2-11 | Tenant lookup caching (Redis) | High | 2d | Backend | S2-01 |
| S2-12 | **Multi-tenant integration tests** | **Very High** | **5d** | QA + Backend | S2-03, S2-07 |
| S2-13 | Health check enhancement | Low | 1d | Backend | S2-04 |

### Total Estimates

| Scenario | Developer-Days | Notes |
|----------|---------------|-------|
| Optimistic | 21 | Everything works first try |
| **Realistic** | **41** | Normal debugging, one external blocker |
| Pessimistic | 67 | RLS takes 8d, Nginx takes 5d, DNS delays |
| **Buffered (25%)** | **51** | Recommended planning target |

With 3 developers x 4 weeks = 60 available days. **Buffered realistic (51 days) fits with 9 days slack.**

---

## 5. Critical Path

```
S1-01 → S1-02 → S1-05 → S2-03 → S2-04 → S2-07 → S2-12
(0.5d)   (2d)    (1.5d)   (5d)    (2d)    (2d)    (5d)
                                                   = 18 days SEQUENTIAL
```

The critical path is **18 working days** of sequential work. The 4-week (20-day) window leaves only 2 days of slack on the critical path. **No slippage tolerance on RLS rework (S2-03) or integration tests (S2-12).**

---

## 6. Risk Register (Top 10)

| ID | Category | Risk | Score | Mitigation |
|----|----------|------|-------|------------|
| R01 | Security | RLS NULL bypass active in comprehensive_rls migration | **25** | New migration: drop+recreate all policies without NULL fallback |
| R02 | Security | `get_db()` silently proceeds without tenant context | **25** | Add mandatory tenant context check, raise 400 |
| R05 | Infrastructure | No Nginx wildcard config exists | **20** | Create in Sprint 1 Week 1, test with 3+ subdomains |
| R12 | Knowledge | Team unfamiliarity with PostgreSQL RLS | **20** | 2-hour workshop before Sprint 1. RLS Testing Playbook. |
| R04 | Technical | Dual `current_tenant_id()` functions | **16** | Standardize on `get_current_tenant_id()`, drop the other |
| R06 | Infrastructure | No Terraform/IaC exists | **16** | Begin in Sprint 1, defer EKS to Sprint 3-4 |
| R03 | Security | `is_platform_admin` session variable bypass | **15** | Remove from RLS entirely. Use superuser role for admin. |
| R07 | Technical | Connection pool tenant context leaking | **15** | Add `pool_checkout` event listener that resets all session vars |
| R08 | Technical | Redis cache key collision between tenants | **15** | Convention: `{tenant_id}:{feature}:{key}`. Create wrapper class. |
| R16 | Security | Weak SECRET_KEY could leak to production | **15** | Enforce 64+ char minimum via Pydantic validator |

Full risk register with 25 risks available in `spec/risk-analysis.md`.

---

## 7. Multi-Tenancy Isolation Design (7 Layers)

```
                      Request: presec.simsplus.io
                                |
LAYER 1  --------  Cloudflare DNS Wildcard (*.simsplus.io)
                   Nginx extracts subdomain, sets X-Subdomain header
                   Next.js proxy.ts validates subdomain, sets cookie
                                |
LAYER 2  --------  FastAPI TenantMiddleware resolves subdomain → tenant_id
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

**Key principle:** Every layer assumes the layers above it have failed. This is defense-in-depth.

### Hardened RLS Policy (No Bypasses)

```sql
-- Function (NULL-safe)
CREATE OR REPLACE FUNCTION get_current_tenant_id() RETURNS UUID AS $$
BEGIN
    RETURN NULLIF(current_setting('app.current_tenant_id', true), '')::UUID;
EXCEPTION
    WHEN OTHERS THEN RETURN NULL;
END;
$$ LANGUAGE plpgsql STABLE;

-- Policy template (applied to EVERY tenant-scoped table)
CREATE POLICY tenant_strict_{table} ON {table}
    FOR ALL TO sims_app_user
    USING (tenant_id = get_current_tenant_id())
    WITH CHECK (tenant_id = get_current_tenant_id());

-- If get_current_tenant_id() returns NULL:
--   tenant_id = NULL  →  NULL (treated as FALSE)  →  ZERO rows returned
-- This is the SAFE default. No bypasses.
```

### Table Classification

| Table | Tenant-Scoped? | Has RLS? | Notes |
|-------|---------------|----------|-------|
| `tenants` | NO (global) | NO | Root entity, queried by middleware |
| `reserved_subdomains` | NO (global) | NO | Protected subdomain names |
| `schools` | YES | YES | `tenant_id` FK to tenants |
| `users` | YES | YES | `tenant_id` FK to tenants |
| All module tables | YES | YES | `tenant_id` via TenantMixin |

---

## 8. Quality Gates

### Sprint 1 Exit Criteria

- [ ] `docker-compose up` starts all services without errors within 2 minutes
- [ ] `curl http://localhost:8000/health` returns `{"status": "healthy"}`
- [ ] Nginx routes `http://presec.localhost/api/v1/health` to backend with `X-Subdomain: presec`
- [ ] `init-db.sql` creates `sims_app_user` role (non-superuser)
- [ ] `get_current_tenant_id()` is the ONLY tenant context function
- [ ] `.env.example` exists with all documented variables
- [ ] Backend CI pipeline passes (lint + test + build)
- [ ] Frontend CI pipeline passes (lint + typecheck + build)
- [ ] RLS policies do NOT have NULL bypass or admin bypass
- [ ] Cloudflare DNS wildcard resolves (or documented workaround exists)

### Sprint 2 Exit Criteria

- [ ] All tenant-scoped tables have RLS policies (verified via `pg_policies`)
- [ ] **CRITICAL:** Connect as `sims_app_user` without tenant context → `SELECT * FROM users` returns **0 rows**
- [ ] **CRITICAL:** Set context to Tenant A → queries return ONLY Tenant A data
- [ ] **CRITICAL:** Set context to Tenant A → `INSERT ... VALUES (Tenant_B_ID)` is **REJECTED**
- [ ] `get_db()` raises HTTP 400 on non-public routes without tenant context
- [ ] `clear_tenant_context()` executes reliably after every request
- [ ] Next.js proxy.ts extracts subdomain from Host header
- [ ] TenantProvider fetches and displays tenant branding
- [ ] Tenant lookup cached in Redis (< 1ms p95)
- [ ] At least 10 integration tests for multi-tenant isolation
- [ ] All existing tests continue to pass

---

## 9. Pre-Sprint Checklist (Blockers)

### Hard Blockers (Cannot Start Without)

- [ ] Domain `simsplus.io` registered and nameservers pointed to Cloudflare
- [ ] Cloudflare account activated with domain added
- [ ] GitHub repository with Actions enabled and secrets configured
- [ ] All developers have: Docker Desktop, Python 3.12, Node 22, git

### Recommended Before Sprint Start

- [ ] AWS account created with billing alerts and IAM admin user
- [ ] Team completes 2-hour PostgreSQL RLS workshop
- [ ] Tech Lead creates `.env.example`
- [ ] Product owner confirms Sprint 1-2 scope

### Knowledge Gaps to Address

| Gap | Resolution | Time |
|-----|-----------|------|
| PostgreSQL RLS | Workshop + pair programming | 4-8 hours |
| Async SQLAlchemy 2.0 | Review docs + examine existing services | 2-4 hours |
| Next.js 16 proxy.ts | Next.js 16 docs + migration guide | 2-4 hours |
| Nginx wildcard config | Nginx docs + tested examples | 2-4 hours |

---

## 10. Deferral List (Can Wait for Sprint 3-4)

| Component | Why It Can Wait |
|-----------|----------------|
| Migration consolidation (S2-08) | Not blocking functionality |
| Full monitoring (Prometheus/Grafana) | Sentry + CloudWatch sufficient initially |
| Terraform IaC for EKS | Docker Compose sufficient for development |
| CORS wildcard subdomain production config | `X-Subdomain` header works in development |
| Celery worker tenant context | No background jobs in Sprint 1-2 |
| Full S3 path restructuring | Can be done when file uploads are needed |

---

## 11. Reference Documents

| Document | Location | Contents |
|----------|----------|----------|
| Solution Architecture | `spec/solution-architecture.md` | Full technical architecture: system design, backend/frontend patterns, API contracts, middleware stack, auth flow, Docker setup, module boundaries, design decisions |
| Multi-Tenancy Architecture | `spec/multi-tenancy-architecture.md` | 7-layer isolation design, RLS SQL, Redis key patterns, S3 paths, JWT claims, subdomain routing, Nginx config, session management, onboarding flow, testing strategy |
| Risk Analysis | `spec/risk-analysis.md` | 25-risk register with scores, component breakdown with estimates, dependency map, parallel tracks, time estimates (optimistic/realistic/pessimistic), infrastructure requirements, quality gates, pre-sprint checklist |
| Development Roadmap | `docs/SIMS_Plus_Development_Roadmap_v2.md` | Full 12-month roadmap across 4 phases |
| Requirements Spec | `docs/SIMS_Plus_Requirements_Specification_v2.md` | Functional and non-functional requirements for all modules |
| Technical Architecture | `docs/SIMS_Plus_Technical_Architecture_v2.1.md` | Infrastructure overview, DNS/SSL, request flow, scaling strategy |

---

## 12. Sprint 1-2 Success Metrics

| Metric | Target |
|--------|--------|
| Tenant isolation verified | 100% (automated tests) |
| Cross-tenant access attempts blocked | 100% |
| Docker environment setup time (new developer) | < 15 minutes |
| API response time (health check) | < 50ms |
| Tenant lookup latency (cached) | < 1ms |
| CI/CD pipeline execution time | < 5 minutes |
| RLS tests passing | 10+ tests, all green |
| Critical security findings resolved | 5/5 (F1-F5) |

---

*This document synthesizes findings from the Solution Architect, Multi-Tenancy Architect, and Risk Analyst. It should be reviewed by the Tech Lead before Sprint 1 kickoff and updated after Sprint 1-2 retrospective with actual vs estimated effort data.*
