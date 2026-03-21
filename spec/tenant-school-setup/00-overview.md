# Tenant & School Setup — Implementation Plan

**Date:** 2026-03-21
**Author:** Harry McNinson (via Claude Code)
**Status:** Approved
**Scope:** Gap closure for requirements TS-001 through TS-024

---

## Executive Summary

This plan addresses 7 identified gaps in the Tenant and School Setup module across 4 phases. Most requirements (13 of 20) are already fully implemented. This plan closes the remaining gaps with concrete, actionable tasks.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Trial duration | 90 days | Requirement TS-006, per `docs/SIMS_Plus_Subscription_Tiers.md` |
| Grace period after trial expiry | 7-day read-only (GET only) | Balance UX with enforcement |
| Payment provider for upgrades | Paystack (existing integration) | Reuse parent portal code |
| Pricing model | Per-student, per-term (not flat rate) | Per `docs/SIMS_Plus_Subscription_Tiers.md` |
| Existing tenant data | Clean slate — delete all | Fresh testing start |
| Setup wizard backward compat | Not needed | Clean slate |
| GES subject data | Proceed with standard curriculum | Stakeholder can adjust later |

## Subscription Tier Summary

Source: `docs/SIMS_Plus_Subscription_Tiers.md`

| | Trial | Starter | Professional | Enterprise |
|---|---|---|---|---|
| **Price** | Free (90 days) | GHS 5/student/term | GHS 10/student/term | GHS 15/student/term |
| **Annual (10% off)** | — | GHS 13.50/student/yr | GHS 27/student/yr | GHS 40.50/student/yr |
| **Max Students** | 100 | 300 | Unlimited | Unlimited |
| **User Accounts** | 10 | 10 | 50 | Unlimited |
| **Storage** | 5 GB | 5 GB | 20 GB | 100 GB |
| **SMS/month** | 50 | 50 | 200 | Unlimited |
| **Parent Portal** | — | — | Included | Included |
| **Boarding** | — | — | Add-on (GHS 300/term) | Included |
| **Transport** | — | — | Add-on (GHS 200/term) | Included |
| **Multi-School** | — | — | — | Included |
| **API Access** | — | — | — | Included |

## Requirements Status

### Already Implemented (No Work Needed)

| Req | Description |
|-----|-------------|
| TS-001 | Self-service registration + email verification |
| TS-002 | Tenant type selection (single_school / school_chain) |
| TS-005 | Bulk CSV/Excel import (students, staff) |
| TS-010 | School basic info (name, address, GES code) |
| TS-011 | School type configuration |
| TS-013 | Academic calendar (terms, holidays) |
| TS-014 | Class/Form structure with naming conventions |
| TS-016 | Grading scale configuration |
| TS-017 | School logo and branding upload |
| TS-018 | Multi-campus/branch management |
| TS-020 | Academic year creation with dates |
| TS-021 | Term/semester definitions |
| TS-022 | Student carry-forward / promotion workflow |

### Gaps to Close

| Req | Gap | Phase | Complexity |
|-----|-----|-------|------------|
| TS-006 | Trial is 30 days not 90; no expiration enforcement | Phase 1A | M |
| TS-003 | Plan limits stored but never enforced; no upgrade flow | Phase 1B | M |
| TS-015 | No GES subject templates; schools create manually | Phase 2A | M |
| TS-004 | Setup wizard missing terms, subjects, next-steps | Phase 2B | M |
| TS-012 | No public/private field; boarding is just a boolean | Phase 3A | S |
| TS-023 | No archived status; completed years still editable | Phase 3B | S |
| TS-024 | No date overlap validation for academic years | Phase 4 | S |

## Phase Dependencies

```
Phase 1A (Trial + Expiration)
    └──→ Phase 1B (Subscription Limits) — shares migration

Phase 2A (GES Subject Templates)
    └──→ Phase 2B (Setup Wizard) — wizard uses template endpoint

Phase 3A (School Categories) — independent
Phase 3B (Academic Archiving) — independent
    └──→ Phase 4 (Date Overlap) — uses 'archived' status
```

## File Index

| Document | Contents |
|----------|----------|
| [01-phase-1a-trial-enforcement.md](01-phase-1a-trial-enforcement.md) | Trial 90 days + expiration middleware + banner |
| [02-phase-1b-subscription-enforcement.md](02-phase-1b-subscription-enforcement.md) | Plan limits + Paystack upgrade + feature gating |
| [03-phase-2a-ges-subject-templates.md](03-phase-2a-ges-subject-templates.md) | GES subject seed data + template endpoint |
| [04-phase-2b-setup-wizard.md](04-phase-2b-setup-wizard.md) | Wizard improvements (terms, subjects, next-steps) |
| [05-phase-3a-school-categories.md](05-phase-3a-school-categories.md) | Public/private + boarding type enums |
| [06-phase-3b-academic-archiving.md](06-phase-3b-academic-archiving.md) | Archive status + read-only enforcement |
| [07-phase-4-date-overlap.md](07-phase-4-date-overlap.md) | Academic year date overlap validation |
| [08-migration-plan.md](08-migration-plan.md) | All Alembic migrations in sequence |
| [09-review-findings.md](09-review-findings.md) | Consolidated review findings from 5 agents (must-fix before implementation) |
