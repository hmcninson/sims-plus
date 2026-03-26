# Platform Admin & Chain Admin Login — Implementation Plan

**Date:** 2026-03-22
**Author:** Harry McNinson (via Claude Code)
**Status:** Approved
**Scope:** Platform admin portal, central admin domain, tenant impersonation, chain admin verification

---

## Executive Summary

SIMS Plus uses subdomain-based multi-tenancy where every request requires a school subdomain (e.g., `presec.simsplus.io`). This works perfectly for school-level users but creates two gaps:

1. **Platform Admin** — a system-wide administrator who manages ALL tenants has no way to log in. The `platform_admin` role exists with wildcard `["*"]` permissions, but there is no central domain, no portal, and no mechanism for cross-tenant operations.

2. **Chain Admin** — manages multiple schools within one chain tenant. This flow **already works**: login via chain subdomain, school switching via `X-Active-School` header, `/chain/accessible` endpoint. **No changes needed.**

This plan closes the Platform Admin gap across 4 phases.

---

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Platform admin user storage | Users table with platform tenant_id | Reuses existing User model, TenantMixin, auth infrastructure. Avoids duplicating auth logic. |
| Platform tenant subdomain | `_platform` (underscore-prefixed) | Fails SUBDOMAIN_PATTERN validation (`^[a-z0-9]...`), so it's unreachable via normal subdomain routing. Preserves TenantMixin's NOT NULL invariant. |
| Central admin domain | `admin.simsplus.io` | Already in RESERVED_SUBDOMAINS. Remove from reserved list, handle as special case in proxy.ts and middleware. |
| Cross-tenant reads | Dedicated superuser engine (`sims_admin` role) | Hardened RLS with `FORCE` prevents `sims_app_user` from reading tenant-scoped tables without context. `sims_admin` bypasses RLS by design (RLS policies target `TO sims_app_user`). |
| Impersonation | Short-lived JWT (30 min) with target tenant_id | Stateless, consistent with existing architecture. Token passes `ValidatedTokenTenant` because its `tenant_id` matches the target subdomain. All existing endpoints work unchanged. |
| Platform admin creation | CLI management command only | Most secure approach. No API surface for creating the highest-privilege accounts. |
| MFA enforcement | Mandatory for platform admins | Given the access level, MFA cannot be optional. Enforced on first login. |
| Impersonation scope | Full read-write with audit logging | Platform admins may need to fix data, reset passwords, create users on behalf of schools. All actions logged. |
| Separate cookie names | `platform_access_token` / `platform_refresh_token` | Prevents conflicts when a platform admin also has a school account in the same browser. |
| Chain admin changes | None | Existing flow is complete and functional. |

---

## Scope

### In Scope

| Item | Phase |
|------|-------|
| Platform tenant seed (`_platform`) | Phase 1 |
| `platform_audit_log` table | Phase 1 |
| CLI to create platform admin users | Phase 1 |
| Platform admin login endpoint (`/api/v1/platform/login`) | Phase 2 |
| `PlatformAdminUser` dependency | Phase 2 |
| PlatformService (auth, tenant CRUD, impersonation, analytics) | Phase 2 |
| Platform admin endpoints (tenants, impersonate, analytics, audit log) | Phase 2 |
| Superuser connection pool for cross-tenant queries | Phase 2 |
| Frontend platform portal (admin.simsplus.io) | Phase 3 |
| proxy.ts admin subdomain handling | Phase 3 |
| Impersonation banner in school dashboard | Phase 3 |
| Tests + security review | Phase 4 |

### Out of Scope

| Item | Reason |
|------|--------|
| Chain admin login changes | Already working correctly |
| SSO/OAuth for platform admins | Future sprint (Enterprise feature) |
| Platform admin API keys | Future sprint |
| Advanced platform analytics (revenue, trends) | Future sprint — start with basic counts |
| Platform admin mobile app | Not planned |

---

## Architecture

```
                    ┌─────────────────────────────────────────┐
                    │            admin.simsplus.io            │
                    │         (Platform Admin Portal)         │
                    └─────────────────┬───────────────────────┘
                                      │
                    ┌─────────────────▼───────────────────────┐
                    │              proxy.ts                    │
                    │  Detects "admin" subdomain               │
                    │  Sets x-platform-admin: true header      │
                    │  Does NOT set x-subdomain                │
                    │  Stores platform_access_token cookie      │
                    └─────────────────┬───────────────────────┘
                                      │
                    ┌─────────────────▼───────────────────────┐
                    │           TenantMiddleware               │
                    │  /api/v1/platform/* in PUBLIC_PREFIXES   │
                    │  → Skips tenant resolution               │
                    └─────────────────┬───────────────────────┘
                                      │
              ┌───────────────────────┼───────────────────────┐
              │                       │                       │
    ┌─────────▼─────────┐   ┌────────▼────────┐   ┌─────────▼─────────┐
    │  /platform/login   │   │ /platform/      │   │ /platform/        │
    │                    │   │ tenants          │   │ impersonate/{id}  │
    │  UnscopedDB        │   │                 │   │                   │
    │  Queries users     │   │ SuperuserEngine  │   │  Creates JWT      │
    │  WHERE tenant_id   │   │ (sims_admin)     │   │  with target      │
    │  = _platform       │   │ Bypasses RLS     │   │  tenant_id        │
    │  AND role =        │   │ Cross-tenant     │   │                   │
    │  platform_admin    │   │ analytics        │   │  is_impersonation │
    └────────────────────┘   └─────────────────┘   │  = true           │
                                                    │  30-min expiry    │
                                                    │  Non-refreshable  │
                                                    └────────┬──────────┘
                                                             │
                                                    ┌────────▼──────────┐
                                                    │  Redirect to      │
                                                    │  target.simsplus  │
                                                    │  .io with token   │
                                                    │                   │
                                                    │  Token passes     │
                                                    │  ValidatedToken   │
                                                    │  Tenant check     │
                                                    │  (tenant_id       │
                                                    │  matches target)  │
                                                    │                   │
                                                    │  All existing     │
                                                    │  endpoints work   │
                                                    │  unchanged        │
                                                    └───────────────────┘
```

---

## Phase Dependencies

```
Phase 1: Infrastructure (migration, models, CLI)
  └── No dependencies

Phase 2: Backend (auth, endpoints, service)
  └── Depends on Phase 1

Phase 3: Frontend (portal, proxy.ts, impersonation UI)
  └── Depends on Phase 2

Phase 4: Testing + Security Review
  └── Depends on Phase 3
```

---

## Estimated Timeline

| Phase | Items | Effort | Parallelizable |
|-------|-------|--------|----------------|
| Phase 1 | Infrastructure | 2 days | No |
| Phase 2 | Backend auth + endpoints + MFA flow | 5-7 days | No (depends on Phase 1) |
| Phase 3 | Frontend portal | 4-5 days | No (depends on Phase 2) |
| Phase 4 | Tests + security review | 3-4 days | No (depends on Phase 3) |
| **Total** | | **~17-20 days** | |

**Risk Analysis Note:** The original 12-day estimate was revised upward by ~50%.
Root causes: (1) MFA endpoints were missing from Phase 2 (+2 days), (2) testing
6 test files at 6-12 tests each requires 3-4 days, (3) superuser engine
testing adds complexity. See `/docs/PLATFORM_ADMIN_LOGIN_RISK_ANALYSIS.md` for
the full risk register and detailed estimates.

---

## New Dependencies

None — all required packages are already installed (`python-jose`, `argon2-cffi`, `structlog`, `httpx`, etc.).

---

## File Index

| Document | Contents |
|----------|----------|
| [00-overview.md](00-overview.md) | This file — overview, decisions, architecture |
| [01-phase-1-infrastructure.md](01-phase-1-infrastructure.md) | Migration, models, CLI, platform tenant seed |
| [02-phase-2-backend.md](02-phase-2-backend.md) | Auth, PlatformService, endpoints, deps, middleware |
| [03-phase-3-frontend.md](03-phase-3-frontend.md) | proxy.ts, platform portal pages, impersonation banner |
| [04-phase-4-testing.md](04-phase-4-testing.md) | Test cases, security review checklist |

---

## Risk Summary

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| Superuser engine SQL injection | CRITICAL | LOW | Parameterized queries (ANY(CAST(:ids AS uuid[]))), table name allowlist validation |
| MFA bypass via setup/pending token | CRITICAL | MEDIUM | PlatformAdminUser rejects mfa_setup_required and mfa_pending tokens; MFA setup token has no permissions claim |
| Superuser engine leaking to non-platform code | HIGH | LOW | Engine lives in `PlatformService` module-level var, never exposed as dependency |
| Impersonation token escalation loop | HIGH | LOW | PlatformAdminUser rejects is_impersonation=True tokens at /platform/* endpoints |
| Impersonation token refresh | HIGH | LOW | No refresh token issued; AuthService.refresh_tokens() rejects by tenant_id mismatch; token type check |
| Platform admin credential compromise | HIGH | LOW | MFA mandatory, CLI-only creation, separate cookies, DB liveness check on every request (cached 60s) |
| Tenant update bypass via status field | HIGH | LOW | status excluded from TenantUpdateRequest; update_tenant uses field allowlist |
| Account enumeration via error messages | HIGH | MEDIUM | All login failures return generic "Invalid email or password" (except lockout which returns 429) |
| Platform audit log readable by school endpoints | MEDIUM | LOW | sims_app_user has INSERT only (no SELECT); audit reads go through superuser engine |
| Accidental cross-tenant data modification during impersonation | MEDIUM | MEDIUM | All actions audited, impersonation banner shown, token is tenant-scoped so RLS active |
| Breaking existing login flows | MEDIUM | LOW | Platform endpoints in separate `/platform/*` namespace, no changes to existing auth |

| ALEMBIC_DATABASE_URL sync driver prefix crashes async engine | HIGH | HIGH | Auto-convert postgresql:// to postgresql+asyncpg:// (RISK FIX R3) |
| authenticate() unreachable _issue_tokens() | CRITICAL | CERTAIN | Fixed: MFA verify/setup endpoints added (RISK FIX BUG-1/BUG-5) |
| Missing MFA endpoints (setup, verify, generate) | CRITICAL | CERTAIN | Fixed: Added to Phase 2 (RISK FIX BUG-5) |
| ALEMBIC_DATABASE_URL not set on prod app servers | HIGH | MEDIUM | Startup validation + separate docs (RISK FIX R7) |
| "admin" in proxy.ts RESERVED_SUBDOMAINS removal causes cookie persistence | MEDIUM | MEDIUM | Fixed: keep "admin" in proxy.ts reserved set (RISK FIX R-BC3) |
| Platform tenant deletion breaks all admin auth silently | HIGH | LOW | Startup health check warning (RISK FIX R-OP1) |
| Missing settings import in platform.py endpoint | LOW | CERTAIN | Fixed (RISK FIX BUG-2) |

## Security Review History

| Date | Reviewer | Findings | Status |
|------|----------|----------|--------|
| 2026-03-22 | Security Agent (Claude) | 2 CRITICAL, 5 HIGH, 5 MEDIUM, 3 LOW | All CRITICAL/HIGH fixed in spec |
| 2026-03-22 | Risk Analyst Agent (Claude) | 2 CRITICAL, 6 HIGH, 5 MEDIUM, 3 LOW additional | Fixes applied to spec; see /docs/PLATFORM_ADMIN_LOGIN_RISK_ANALYSIS.md |
