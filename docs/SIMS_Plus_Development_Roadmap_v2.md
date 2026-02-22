# SIMS Plus (School Information Management System Plus) - Development Roadmap

**Version:** 2.3
**Date:** January 2026
**Author:** Harry McNinson
**Status:** Phase 1 Complete - Phase 2 In Progress

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Project Phases](#2-project-phases)
3. [Phase 1: Foundation (Months 1-3)](#3-phase-1-foundation)
4. [Phase 2: MVP Launch (Months 4-6)](#4-phase-2-mvp-launch)
5. [Phase 3: Enhancement (Months 7-9)](#5-phase-3-enhancement)
6. [Phase 4: Scale & Mobile (Months 10-12)](#6-phase-4-scale--mobile)
7. [Budget & Resources](#7-budget--resources)
8. [Risk Management](#8-risk-management)
9. [Success Metrics](#9-success-metrics)

---

## 1. Executive Summary

### 1.1 Project Overview

SIMS Plus is a multi-tenant SaaS school management system with subdomain-based access for each school. This roadmap covers 12 months of development across 4 phases.

### 1.2 Key Milestones

| Month | Milestone | Status |
|-------|-----------|--------|
| Month 3 | Infrastructure + Core Auth Complete | ✅ Complete |
| Month 6 | MVP Launch (10 pilot schools) | 🔄 In Progress |
| Month 9 | Full Feature Set + Parent Portal | Planned |
| Month 12 | Mobile Apps + 100+ Schools | Planned |

### 1.3 Architecture Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                SHARED INFRASTRUCTURE                             │
│                                                                  │
│  presec.simsplus.io  ──┐                                        │
│  achimota.simsplus.io ──┼──► ONE Server Cluster                 │
│  {any}.simsplus.io   ──┘    ONE Database (with RLS)             │
│                               ONE Codebase                       │
│                                                                  │
│  Adding new school = Database insert only (no infrastructure)   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Project Phases

```
┌────────────────────────────────────────────────────────────────────────────┐
│                        12-MONTH DEVELOPMENT TIMELINE                        │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  PHASE 1: Foundation ✅      PHASE 2: MVP ✅         PHASE 3: Enhancement   │
│  ─────────────────────        ──────────────         ───────────────────   │
│  Months 1-3 COMPLETE         Months 4-6             Months 7-9             │
│                                                                             │
│  ✅ Infrastructure setup     ✅ Finance module      • Boarding module      │
│  ✅ Subdomain routing        ✅ Fee structures      • Transport module     │
│  ✅ Auth + Multi-tenancy     ✅ Invoices (bulk)     • Advanced reports     │
│  ✅ School onboarding        ✅ Payments            • Bulk operations      │
│  ✅ Student management       ✅ Scholarships        • SMS integration      │
│  ✅ Staff management         • Parent portal        • 50 schools           │
│  ✅ Attendance module        • Beta launch                                 │
│  ✅ Examinations & CA        • 10 pilot schools     PHASE 4: Scale        │
│  ✅ Report cards                                     ─────────────────     │
│  ✅ Preschool module                                 Months 10-12          │
│  ✅ School calendar                                                         │
│  ✅ Timetables                                       • Mobile apps         │
│                                                       • Offline sync        │
│                                                       • Performance opt     │
│                                                       • 100+ schools        │
│                                                                             │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Phase 1: Foundation (Months 1-3) ✅ COMPLETE

### Sprint 1: Project Setup & Infrastructure (Weeks 1-2) ✅

**Focus:** Establish development environment with subdomain support

| Task ID | Task | Status |
|---------|------|--------|
| INF-001 | Git repository setup (monorepo) | ✅ |
| INF-002 | FastAPI backend scaffolding | ✅ |
| INF-003 | Next.js 16 frontend setup | ✅ |
| INF-004 | PostgreSQL database setup | ✅ |
| INF-005 | Docker configuration | ✅ |
| INF-006 | CI/CD pipeline (GitHub Actions) | ✅ |
| DNS-001 | Configure Cloudflare DNS with wildcard | ✅ |
| SSL-001 | Generate wildcard SSL certificate | ✅ |
| NGX-001 | Configure Nginx for wildcard subdomain routing | ✅ |

**Sprint 1 Deliverables:**
- ✅ Development environment with subdomain support
- ✅ Staging environment at `*.staging.simsplus.io`
- ✅ CI/CD pipeline operational
- ✅ Wildcard DNS and SSL configured

---

### Sprint 2: Multi-Tenancy Foundation (Weeks 3-4) ✅

**Focus:** Database multi-tenancy and tenant detection

| Task ID | Task | Status |
|---------|------|--------|
| DB-001 | Create `tenants` table with subdomain field | ✅ |
| DB-002 | Create `reserved_subdomains` table | ✅ |
| DB-003 | Implement Row-Level Security (RLS) policies | ✅ |
| DB-004 | Create `set_tenant_context()` function | ✅ |
| DB-005 | Create `schools` table | ✅ |
| DB-006 | Create `users` table with tenant_id | ✅ |
| MW-001 | Implement Next.js middleware for subdomain detection | ✅ |
| MW-002 | Create tenant context provider (React) | ✅ |

**Sprint 2 Deliverables:**
- ✅ Multi-tenant database schema with RLS
- ✅ Subdomain detection middleware
- ✅ Tenant context available in frontend

---

### Sprint 3: Authentication System (Weeks 5-6) ✅

**Focus:** Tenant-aware authentication

| Task ID | Task | Status |
|---------|------|--------|
| AUTH-001 | JWT authentication implementation | ✅ |
| AUTH-002 | Add tenant_id claim to JWT tokens | ✅ |
| AUTH-003 | Password hashing (Argon2) | ✅ |
| AUTH-004 | Login endpoint (tenant-scoped) | ✅ |
| AUTH-005 | Token refresh endpoint | ✅ |
| AUTH-006 | Cross-tenant access prevention | ✅ |
| AUTH-007 | Password reset flow | ✅ |
| UI-001 | School-branded login page | ✅ |

**Sprint 3 Deliverables:**
- ✅ JWT authentication with tenant claims
- ✅ School-branded login pages
- ✅ Password reset flow

---

### Sprint 4: School Onboarding (Weeks 7-8) ✅

**Focus:** Self-service school registration

| Task ID | Task | Status |
|---------|------|--------|
| ONB-001 | Subdomain availability check endpoint | ✅ |
| ONB-002 | Subdomain validation rules | ✅ |
| ONB-003 | School registration API | ✅ |
| ONB-004 | Tenant + school + admin user creation | ✅ |
| ONB-006 | Self-service registration form | ✅ |
| ONB-008 | Onboarding setup wizard UI | ✅ |

**Sprint 4 Deliverables:**
- ✅ Self-service school registration
- ✅ Automatic subdomain provisioning
- ✅ First-login setup wizard

---

### Sprint 5: RBAC & Permissions (Weeks 9-10) ✅

**Focus:** Role-based access control

| Task ID | Task | Status |
|---------|------|--------|
| RBAC-001 | Roles table and seeding | ✅ |
| RBAC-002 | Permissions model | ✅ |
| RBAC-003 | User-roles assignment | ✅ |
| RBAC-004 | Permission checking middleware | ✅ |
| UI-005 | Admin dashboard | ✅ |
| UI-006 | Navigation with role-based menu | ✅ |

**Sprint 5 Deliverables:**
- ✅ RBAC system operational
- ✅ Admin dashboard
- ✅ Role-based navigation

---

### Sprint 6: Core Academic Setup (Weeks 11-12) ✅

**Focus:** Academic structure foundation

| Task ID | Task | Status |
|---------|------|--------|
| ACD-001 | Academic years CRUD | ✅ |
| ACD-002 | Terms CRUD | ✅ |
| ACD-003 | Classes CRUD | ✅ |
| ACD-004 | Sections CRUD | ✅ |
| ACD-005 | Subjects CRUD | ✅ |
| ACD-006 | Grading scales | ✅ |
| UI-007 | Academic year management UI | ✅ |
| UI-008 | Class management UI | ✅ |
| UI-009 | Subject management UI | ✅ |
| BRD-001 | Tenant branding settings | ✅ |

**Sprint 6 Deliverables:**
- ✅ Complete academic structure setup
- ✅ Tenant branding customization

---

### Sprint 7-8: Student Management (Weeks 13-16) ✅

| Task ID | Task | Status |
|---------|------|--------|
| STU-001 | Students CRUD API | ✅ |
| STU-002 | Guardians CRUD API | ✅ |
| STU-003 | Student-guardian linking | ✅ |
| STU-004 | Student photo upload | ✅ |
| STU-005 | Student ID generation | ✅ |
| STU-006 | Student list UI | ✅ |
| STU-007 | Student profile UI | ✅ |
| STU-008 | Add/Edit student forms | ✅ |
| STU-009 | Guardian management UI | ✅ |
| STU-010 | Bulk import (CSV/Excel) | ✅ |

**Deliverables:**
- ✅ Complete student management
- ✅ Guardian management
- ✅ Bulk import capability

---

### Sprint 9-10: Staff & Attendance (Weeks 17-20) ✅

| Task ID | Task | Status |
|---------|------|--------|
| STF-001 | Staff CRUD API | ✅ |
| STF-002 | Staff-class assignment | ✅ |
| STF-003 | Department management | ✅ |
| STF-004 | Staff import functionality | ✅ |
| ATT-001 | Attendance marking API | ✅ |
| ATT-002 | Attendance reports API | ✅ |
| ATT-003 | Calendar-based school days | ✅ |
| UI-010 | Staff list and profile UI | ✅ |
| UI-011 | Attendance marking UI | ✅ |
| UI-012 | Attendance reports UI | ✅ |

**Deliverables:**
- ✅ Staff management with departments
- ✅ Attendance tracking with calendar integration

---

### Sprint 11-12: Examinations & Assessment (Weeks 21-24) ✅

| Task ID | Task | Status |
|---------|------|--------|
| EXM-001 | Exam management API | ✅ |
| EXM-002 | Continuous Assessment (CA) API | ✅ |
| EXM-003 | Score entry API with validation | ✅ |
| EXM-004 | Grade calculation engine | ✅ |
| EXM-005 | Report card generation API | ✅ |
| EXM-006 | Score change audit logging | ✅ |
| UI-013 | Exam setup UI | ✅ |
| UI-014 | CA management UI | ✅ |
| UI-015 | Score entry UI | ✅ |
| UI-016 | Report card preview/download | ✅ |
| UI-017 | Exam analytics dashboard | ✅ |

**Deliverables:**
- ✅ Complete exam management
- ✅ Continuous assessment tracking
- ✅ Report card generation (PDF)
- ✅ Exam analytics and insights

---

### Sprint 13-14: Preschool Module (Weeks 25-28) ✅

| Task ID | Task | Status |
|---------|------|--------|
| PRE-001 | Developmental domains and milestones | ✅ |
| PRE-002 | Student observations API | ✅ |
| PRE-003 | Daily activity logs API | ✅ |
| PRE-004 | Preschool assessments API | ✅ |
| PRE-005 | Preschool reports API | ✅ |
| UI-PRE-001 | Observations manager UI | ✅ |
| UI-PRE-002 | Daily logs entry UI | ✅ |
| UI-PRE-003 | Assessment entry UI | ✅ |
| UI-PRE-004 | Progress reports UI | ✅ |
| UI-PRE-005 | Preschool settings UI | ✅ |
| MIG-001 | Database migrations for preschool | ✅ |
| SEED-001 | Seed developmental domains | ✅ |

**Deliverables:**
- ✅ Developmental domains and milestones
- ✅ Student observations with categories
- ✅ Daily activity logs (meals, naps, activities)
- ✅ Milestone-based assessments
- ✅ Preschool progress reports

---

### Sprint 15-16: Calendar & Timetable (Weeks 29-32) ✅

| Task ID | Task | Status |
|---------|------|--------|
| CAL-001 | School holidays API | ✅ |
| CAL-002 | Calendar events management | ✅ |
| CAL-003 | School days calculation | ✅ |
| TT-001 | Class timetable API | ✅ |
| TT-002 | Period management API | ✅ |
| UI-CAL-001 | Month view calendar | ✅ |
| UI-CAL-002 | Week view calendar | ✅ |
| UI-CAL-003 | Year view calendar | ✅ |
| UI-CAL-004 | Event form (add/edit) | ✅ |
| UI-CAL-005 | Drag-and-drop rescheduling | ✅ |
| UI-CAL-006 | School days counter | ✅ |
| UI-CAL-007 | iCal/Google Calendar export | ✅ |
| UI-TT-001 | Timetable management UI | ✅ |

**Deliverables:**
- ✅ School calendar with multi-view (Month, Week, Year)
- ✅ Holiday and event management
- ✅ Drag-and-drop event rescheduling
- ✅ Calendar export (iCal, Google Calendar)
- ✅ School days calculation per term
- ✅ Class timetable management

---

## 4. Phase 2: MVP Launch (Months 4-6)

### Sprint 17-18: Finance Core (Weeks 33-36) ✅

| Task ID | Task | Status |
|---------|------|--------|
| FIN-001 | Fee types API | ✅ |
| FIN-002 | Fee structure API | ✅ |
| FIN-003 | Invoice generation API (single & bulk) | ✅ |
| FIN-004 | Invoice sync with fee structure changes | ✅ |
| FIN-005 | Payment recording API | ✅ |
| FIN-006 | Scholarship management API | ✅ |
| FIN-007 | Scholarship award/revoke API | ✅ |
| FIN-008 | Finance dashboard API | ✅ |
| FIN-009 | Invoice email with CC recipients | ✅ |
| FIN-010 | Credit notes API (create, issue, apply, refund, cancel) | ✅ |
| FIN-011 | Auto-apply credit notes to oldest unpaid invoice | ✅ |
| FIN-012 | Student credit balance tracking | ✅ |
| FIN-013 | Finance audit logging (immutable transaction trail) | ✅ |
| FIN-014 | Write-off invoice status support | ✅ |
| UI-FIN-001 | Fee types management UI | ✅ |
| UI-FIN-002 | Fee structure management UI | ✅ |
| UI-FIN-003 | Invoice list with search/filter | ✅ |
| UI-FIN-004 | Invoice generation UI (single & bulk) | ✅ |
| UI-FIN-005 | Invoice sync UI | ✅ |
| UI-FIN-006 | Payment recording UI | ✅ |
| UI-FIN-007 | Scholarship management UI | ✅ |
| UI-FIN-008 | Scholarship award UI | ✅ |
| UI-FIN-009 | Finance dashboard | ✅ |
| UI-FIN-010 | Credit notes management UI (list, create, detail) | ✅ |
| UI-FIN-011 | Apply credit to invoice UI | ✅ |

**Deliverables:**
- [x] Fee types and fee structure management
- [x] Invoice generation (single and bulk by class)
- [x] Invoice sync with fee structure updates
- [x] Payment recording (cash, Mobile Money, bank transfer)
- [x] Scholarship management with auto-discount application
- [x] Credit notes system (create, issue, apply, refund, cancel)
- [x] Auto-apply credit notes to oldest unpaid invoice
- [x] Student credit balance tracking
- [x] Finance audit logging (immutable transaction trail)
- [x] Finance dashboard with revenue statistics

---

### Sprint 19-20: Parent Portal (Weeks 37-40)

| Task ID | Task | Status |
|---------|------|--------|
| PAR-001 | Parent portal API | Planned |
| PAR-002 | Parent account auto-creation | Planned |
| PAR-003 | Child record viewing | Planned |
| PAR-004 | Online fee payment | Planned |
| UI-PAR-001 | Parent portal dashboard | Planned |
| UI-PAR-002 | Parent fee payment UI | Planned |

**Deliverables:**
- [ ] Parent portal live
- [ ] View children's records
- [ ] Online payments

---

### Sprint 21-22: Beta Launch (Weeks 41-44)

| Task ID | Task | Status |
|---------|------|--------|
| BETA-001 | Performance optimization | Planned |
| BETA-002 | Security audit | Planned |
| BETA-003 | User acceptance testing | Planned |
| PILOT-001 | Onboard 10 pilot schools | Planned |

**Deliverables:**
- [ ] Performance optimized
- [ ] Security audit complete
- [ ] **10 pilot schools onboarded**

---

## 5. Phase 3: Enhancement (Months 7-9)

### Sprint 23-24: Boarding & Transport (Weeks 45-48)

| Task ID | Task | Status |
|---------|------|--------|
| BRD-001 | Dormitory management API | Planned |
| BRD-002 | Room/bed assignment API | Planned |
| BRD-003 | Exeat workflow API | Planned |
| TRN-001 | Route management API | Planned |
| TRN-002 | Vehicle management API | Planned |
| TRN-003 | Student transport assignment | Planned |

---

### Sprint 25-26: Communication & SMS (Weeks 49-52)

| Task ID | Task | Status |
|---------|------|--------|
| SMS-001 | Hubtel SMS integration | Planned |
| SMS-002 | SMS templates | Planned |
| COM-001 | Announcements API | Planned |
| COM-002 | Parent-teacher messaging | Planned |
| SCALE-001 | Onboard to 50 schools | Planned |

**Deliverables:**
- [ ] SMS integration
- [ ] Announcements system
- [ ] **50 schools onboarded**

---

## 6. Phase 4: Scale & Mobile (Months 10-12)

### Sprint 27-28: Mobile Apps (Weeks 53-56)

| Task ID | Task | Status |
|---------|------|--------|
| MOB-001 | React Native setup | Planned |
| MOB-002 | Teacher app - Attendance | Planned |
| MOB-003 | Teacher app - Scores | Planned |
| MOB-004 | Parent app - Dashboard | Planned |
| MOB-005 | Parent app - Payments | Planned |
| MOB-006 | Push notifications | Planned |

---

### Sprint 29-30: Offline & Performance (Weeks 57-60)

| Task ID | Task | Status |
|---------|------|--------|
| OFF-001 | Service worker implementation | Planned |
| OFF-002 | Offline data storage | Planned |
| OFF-003 | Sync queue management | Planned |
| PERF-001 | Database query optimization | Planned |
| PERF-002 | Caching layer (Redis) | Planned |
| SCALE-002 | Onboard to 100+ schools | Planned |

**Deliverables:**
- [ ] Mobile apps on app stores
- [ ] Full offline capability
- [ ] **100+ schools onboarded**

---

## 7. Budget & Resources

### 7.1 Team Structure

| Role | Count | Monthly Cost (GHS) |
|------|-------|-------------------|
| Technical Lead | 1 | 15,000 |
| Backend Developer | 2 | 20,000 |
| Frontend Developer | 2 | 20,000 |
| Mobile Developer | 1 | 10,000 |
| DevOps Engineer | 1 | 12,000 |
| UI/UX Designer | 1 | 8,000 |
| QA Engineer | 1 | 8,000 |
| Project Manager | 1 | 12,000 |
| **Total Monthly** | **10** | **105,000** |

### 7.2 Infrastructure Costs (Monthly)

| Service | Cost (USD) | Cost (GHS) |
|---------|------------|------------|
| AWS (EC2, RDS, S3) | $300 | 4,500 |
| Cloudflare Pro | $20 | 300 |
| SendGrid | $20 | 300 |
| Domain renewal | $2 | 30 |
| Monitoring tools | $50 | 750 |
| **Total Monthly** | **$392** | **5,880** |

### 7.3 Total Budget Summary

| Phase | Duration | Staff Cost | Infra Cost | Total |
|-------|----------|------------|------------|-------|
| Phase 1 | 3 months | 315,000 | 17,640 | 332,640 |
| Phase 2 | 3 months | 315,000 | 17,640 | 332,640 |
| Phase 3 | 3 months | 315,000 | 17,640 | 332,640 |
| Phase 4 | 3 months | 315,000 | 17,640 | 332,640 |
| **Total** | **12 months** | **1,260,000** | **70,560** | **1,330,560** |

**Contingency (15%):** GHS 199,584
**Grand Total:** GHS 1,530,144 (~$98,000 USD)

---

## 8. Risk Management

### 8.1 Technical Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| DNS propagation delays | High | Medium | Use low TTL, test with staging first |
| SSL certificate issues | High | Low | Cloudflare automatic SSL, monitor expiry |
| Cross-tenant data leak | Critical | Low | RLS policies, security audit, penetration testing |
| Mobile Money API changes | High | Medium | Abstract payment provider, maintain fallbacks |
| Performance at scale | High | Medium | Load testing, caching, CDN |

### 8.2 Business Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Low pilot adoption | High | Medium | Careful pilot selection, hands-on support |
| School internet issues | Medium | High | Offline-first architecture, PWA |
| Competition | Medium | Medium | Focus on Ghana-specific features |
| Staff turnover | High | Medium | Documentation, knowledge sharing |

---

## 9. Success Metrics

### 9.1 Phase 1 Success Criteria ✅ COMPLETE

- [x] Wildcard subdomain routing working
- [x] 5+ test tenants created successfully
- [x] Login works on all subdomains
- [x] RLS tenant isolation verified
- [x] CI/CD pipeline operational
- [x] Student management complete
- [x] Staff management complete
- [x] Attendance module complete
- [x] Examination system complete
- [x] Report cards generating
- [x] Preschool module complete
- [x] School calendar complete
- [x] Timetable management complete

### 9.2 Phase 2 Success Criteria (MVP)

- [x] Finance module operational
- [ ] 10 pilot schools onboarded
- [ ] Students enrolled in all pilots
- [ ] Attendance marked for 1 week
- [ ] Fee payments processed via MoMo
- [ ] Parent portal active

### 9.3 Phase 3 Success Criteria

- [ ] 50 schools onboarded
- [ ] Parent portal active with 500+ parents
- [ ] SMS notifications working
- [ ] < 3 critical bugs reported

### 9.4 Phase 4 Success Criteria

- [ ] 100+ schools onboarded
- [ ] Mobile apps published (Android + iOS)
- [ ] Offline sync working reliably
- [ ] < 500ms average API response time
- [ ] 99.5% uptime achieved

### 9.5 Key Performance Indicators (KPIs)

| KPI | Target (Month 6) | Target (Month 12) |
|-----|------------------|-------------------|
| Schools onboarded | 10 | 100+ |
| Active users | 500 | 5,000 |
| Monthly transactions | 200 | 2,000 |
| Mobile app installs | - | 1,000 |
| Customer satisfaction | 80% | 90% |
| System uptime | 99% | 99.5% |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | January 2026 | Harry McNinson | Initial version |
| 2.0 | January 2026 | Harry McNinson | Added subdomain infrastructure tasks |
| 2.1 | January 2026 | Harry McNinson | Marked Phase 1 complete, added Exams, Preschool, Calendar, Timetable sprints |
| 2.2 | January 2026 | Harry McNinson | Marked Finance Core complete with fee types, invoices, payments, scholarships |
| 2.3 | January 2026 | Harry McNinson | Added credit notes, finance audit logging, write-off status, student credit balance tasks |
