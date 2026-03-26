# User Management & Access Control — Implementation Plan

**Date:** 2026-03-21
**Author:** Harry McNinson (via Claude Code)
**Status:** Approved
**Scope:** Gap closure for requirements UM-001 through UM-011 and Role definitions (Section 4.1)

---

## Executive Summary

This plan addresses 7 identified gaps in User Management and Access Control across 4 phases. Of the 11 requirements plus role definitions, 5 are already fully implemented. This plan closes the remaining gaps with concrete, actionable tasks suitable for handoff to a development team.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Session timeout scope | Global 30 min (not per-tenant) | Simplicity; no real demand for per-tenant config yet |
| MFA enforcement | Optional toggle for school admins | Security-conscious schools get the option without onboarding friction |
| Custom role permission ceiling | Capped at base_role permissions | Prevents privilege escalation through misconfiguration |
| Bulk import email notification | Yes — "set your password" link (not plaintext password) | Admin ≠ end-user; accounts created as PENDING |
| Phone verification | Optional for all, prompted for parents | Practical for Ghanaian school context (shared devices, number changes) |
| SSO (UM-005) | Deferred to Sprint 22+ | Enterprise-only; no current demand |
| HR Officer permissions | `staff.*`, `students.read`, `attendance.read`, `reports.hr`, `users.read`, `boarding.read` | Full staff management + read-only cross-referencing |
| SMS provider | Arkesel (clean break from Hubtel) | Arkesel V2 API; same `send_sms()` interface; Hubtel code/config/enum fully removed (pre-MVP) |
| Auth return type | Separate MFARequiredResponse (not modifying LoginResponse) | Avoids breaking existing API consumers |

## Requirements Status

### Already Implemented (No Work Needed)

| Req | Description |
|-----|-------------|
| 4.1 (partial) | 9 of 10 roles defined (Platform Admin, Chain Admin, School Admin, Academic Head, Finance Officer, Teacher, House Parent, Parent, Student) |
| UM-002 | Password requirements: min 8 chars, uppercase, lowercase, digit, special char, Argon2id hashing |
| UM-007 | User deactivation with soft delete (SoftDeleteMixin), data retention, token blacklisting |
| UM-009 | Audit logging: 11+ event types, separate DB connection, all auth/admin actions logged |
| UM-011 | Multi-role across schools: UserSchool junction table, chain-aware JWT with school_ids |

### Gaps to Close

| Req | Gap | Phase | Complexity |
|-----|-----|-------|------------|
| 4.1 | HR Officer role missing from enum + permissions | Phase 1 | S |
| UM-001 | Phone verification (SMS OTP) not implemented | Phase 1 | M |
| UM-003 | SMS OTP password reset not implemented (email-only) | Phase 1 | M |
| UM-006 | Bulk user CSV import missing (staff import exists) | Phase 1 | M |
| UM-008 | 30-minute inactivity session timeout not implemented | Phase 2 | M |
| UM-004 | MFA fields exist but no TOTP logic/UI implemented | Phase 3 | L |
| UM-010 | Custom roles with granular permissions (all hardcoded) | Phase 4 | L |

### Explicitly Deferred

| Req | Description | When |
|-----|-------------|------|
| UM-005 | SSO integration (OAuth2/OIDC) | Sprint 22+ (Enterprise feature) |

## Phase Dependencies

```
Phase 0: Arkesel SMS Migration (pre-requisite for Phase 1B)
  └── Replace HubtelClient with ArkeselClient (same interface)

Phase 1: Foundation (independent items, parallelizable)
  ├── 1A: HR Officer Role (standalone)
  ├── 1B: OTP Service + Phone Verification + SMS Password Reset
  │       (depends on Phase 0 — Arkesel SMS client)
  └── 1C: Bulk User CSV Import (standalone)

Phase 2: Session Timeout (standalone)
  └── Frontend-driven with server-side verification

Phase 3: MFA (standalone, but modifies auth.py login flow)
  └── TOTP with pyotp + backup codes

Phase 4: Custom Roles (standalone, but modifies auth.py permission resolution)
  └── New custom_roles table + permission catalog + UI

Single combined migration covers Phases 1-4 (Phase 0 has no migration).
Phases 3 and 4 both modify auth.py — serialize or carefully merge.
```

**Parallel tracks:** Track A (critical path): Phase 0 → Phase 1B → Phase 3 → Phase 4. Track B (parallel): Phase 1A → Phase 1C → Phase 2 → Testing.

## Estimated Timeline

| Phase | Items | Effort | Parallelizable |
|-------|-------|--------|----------------|
| Phase 0 | Arkesel SMS migration (Hubtel → Arkesel) | 1 day | Must complete before Phase 1B |
| Phase 1 | HR Officer + OTP + Bulk Import | 4-5 days | Yes (3 devs) |
| Phase 2 | Session Timeout | 2 days | Yes (after Phase 1 starts) |
| Phase 3 | MFA | 3-4 days | After Phase 1 (modifies auth.py) |
| Phase 4 | Custom Roles | 3-4 days | After Phase 3 (modifies auth.py) |
| **Total** | | **~4 weeks calendar time with 2 developers (23 dev-days raw, ~29 with buffer)** | |

## New Dependencies (pip)

| Package | Version | Purpose | Phase |
|---------|---------|---------|-------|
| `pyotp` | 2.9.0 | TOTP generation/verification for MFA | Phase 3 |
| `qrcode[pil]` | 7.4.2 | QR code generation for MFA setup | Phase 3 |
| `cryptography` | 42.0+ | Fernet symmetric encryption for MFA secret encryption at rest | Phase 3 |

## File Index

| Document | Contents |
|----------|----------|
| [09-arkesel-sms-migration.md](09-arkesel-sms-migration.md) | **Phase 0:** Arkesel SMS client + migration from Hubtel |
| [01-phase-1a-hr-officer-role.md](01-phase-1a-hr-officer-role.md) | Phase 1A: HR Officer enum + permissions + frontend config |
| [02-phase-1b-otp-phone-verification.md](02-phase-1b-otp-phone-verification.md) | Phase 1B: OTP service + phone verification + SMS password reset |
| [03-phase-1c-bulk-user-import.md](03-phase-1c-bulk-user-import.md) | Phase 1C: Bulk user CSV import backend + frontend |
| [04-phase-2-session-timeout.md](04-phase-2-session-timeout.md) | Phase 2: 30-minute inactivity timeout |
| [05-phase-3-mfa.md](05-phase-3-mfa.md) | Phase 3: TOTP MFA with backup codes |
| [06-phase-4-custom-roles.md](06-phase-4-custom-roles.md) | Phase 4: Custom roles with granular permissions |
| [07-migration-plan.md](07-migration-plan.md) | Single combined Alembic migration |
| [08-testing-plan.md](08-testing-plan.md) | Test cases for all phases |
