# SIMS Plus (School Information Management System Plus) - Development Roadmap

**Version:** 2.0  
**Date:** January 2026  
**Author:** Harry McNinson  
**Status:** Complete with Subdomain Infrastructure

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

| Month | Milestone |
|-------|-----------|
| Month 3 | Infrastructure + Core Auth Complete |
| Month 6 | MVP Launch (10 pilot schools) |
| Month 9 | Full Feature Set + Parent Portal |
| Month 12 | Mobile Apps + 100+ Schools |

### 1.3 Architecture Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                SHARED INFRASTRUCTURE                             │
│                                                                  │
│  presec.simsplus.io  ──┐                                      │
│  achimota.simsplus.io ──┼──► ONE Server Cluster               │
│  {any}.simsplus.io   ──┘    ONE Database (with RLS)           │
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
│  PHASE 1: Foundation          PHASE 2: MVP           PHASE 3: Enhancement  │
│  ─────────────────────        ──────────────         ───────────────────   │
│  Months 1-3                   Months 4-6             Months 7-9            │
│                                                                             │
│  • Infrastructure setup       • Student mgmt         • Boarding module     │
│  • Subdomain routing          • Staff mgmt           • Transport module    │
│  • Auth + Multi-tenancy       • Attendance           • Advanced reports    │
│  • School onboarding          • Basic finance        • Bulk import         │
│  • Core database              • Report cards         • SMS integration     │
│  • CI/CD pipeline             • Basic reports        • Parent portal       │
│                               • 10 pilot schools     • 50 schools          │
│                                                                             │
│                                                       PHASE 4: Scale       │
│                                                       ─────────────────    │
│                                                       Months 10-12         │
│                                                                             │
│                                                       • Mobile apps        │
│                                                       • Offline sync       │
│                                                       • Performance opt    │
│                                                       • 100+ schools       │
│                                                                             │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Phase 1: Foundation (Months 1-3)

### Sprint 1: Project Setup & Infrastructure (Weeks 1-2)

**Focus:** Establish development environment with subdomain support

| Task ID | Task | Effort | Owner |
|---------|------|--------|-------|
| INF-001 | Git repository setup (monorepo) | 2h | DevOps |
| INF-002 | FastAPI backend scaffolding | 4h | Backend |
| INF-003 | Next.js 16 frontend setup | 4h | Frontend |
| INF-004 | PostgreSQL database setup | 4h | Backend |
| INF-005 | Docker configuration | 4h | DevOps |
| INF-006 | CI/CD pipeline (GitHub Actions) | 8h | DevOps |
| DNS-001 | Configure Cloudflare DNS with wildcard (`*.simsplus.io`) | 2h | DevOps |
| DNS-002 | Set up DNS records for root, www, app, api | 1h | DevOps |
| SSL-001 | Generate wildcard SSL certificate | 2h | DevOps |
| SSL-002 | Configure auto-renewal | 1h | DevOps |
| NGX-001 | Configure Nginx for wildcard subdomain routing | 4h | DevOps |
| NGX-002 | Set up reverse proxy to Next.js and FastAPI | 2h | DevOps |
| STG-001 | AWS staging environment setup | 8h | DevOps |

**Sprint 1 Deliverables:**
- ✅ Development environment with subdomain support
- ✅ Staging environment at `*.staging.simsplus.io`
- ✅ CI/CD pipeline operational
- ✅ Wildcard DNS and SSL configured

---

### Sprint 2: Multi-Tenancy Foundation (Weeks 3-4)

**Focus:** Database multi-tenancy and tenant detection

| Task ID | Task | Effort | Owner |
|---------|------|--------|-------|
| DB-001 | Create `tenants` table with subdomain field | 4h | Backend |
| DB-002 | Create `reserved_subdomains` table | 2h | Backend |
| DB-003 | Implement Row-Level Security (RLS) policies | 8h | Backend |
| DB-004 | Create `set_tenant_context()` function | 2h | Backend |
| DB-005 | Create `schools` table | 4h | Backend |
| DB-006 | Create `users` table with tenant_id | 4h | Backend |
| MW-001 | Implement Next.js middleware for subdomain detection | 8h | Frontend |
| MW-002 | Create tenant context provider (React) | 4h | Frontend |
| MW-003 | Implement server-side tenant fetching | 4h | Frontend |
| API-001 | Create internal tenant validation endpoint | 4h | Backend |
| TEST-001 | Set up local development with test subdomains | 4h | DevOps |

**Sprint 2 Deliverables:**
- ✅ Multi-tenant database schema with RLS
- ✅ Subdomain detection middleware
- ✅ Tenant context available in frontend

---

### Sprint 3: Authentication System (Weeks 5-6)

**Focus:** Tenant-aware authentication

| Task ID | Task | Effort | Owner |
|---------|------|--------|-------|
| AUTH-001 | JWT authentication implementation | 8h | Backend |
| AUTH-002 | Add tenant_id claim to JWT tokens | 4h | Backend |
| AUTH-003 | Password hashing (Argon2) | 2h | Backend |
| AUTH-004 | Login endpoint (tenant-scoped) | 4h | Backend |
| AUTH-005 | Token refresh endpoint | 4h | Backend |
| AUTH-006 | Cross-tenant access prevention | 8h | Backend |
| AUTH-007 | Password reset flow | 8h | Backend |
| UI-001 | School-branded login page | 8h | Frontend |
| UI-002 | Generic login portal (app.simsplus.io) | 8h | Frontend |
| UI-003 | School search/selection component | 4h | Frontend |
| UI-004 | Password reset UI | 4h | Frontend |

**Sprint 3 Deliverables:**
- ✅ JWT authentication with tenant claims
- ✅ School-branded login pages
- ✅ Generic login portal with school search
- ✅ Password reset flow

---

### Sprint 4: School Onboarding (Weeks 7-8)

**Focus:** Self-service school registration

| Task ID | Task | Effort | Owner |
|---------|------|--------|-------|
| ONB-001 | Subdomain availability check endpoint | 4h | Backend |
| ONB-002 | Subdomain validation rules | 4h | Backend |
| ONB-003 | School registration API | 8h | Backend |
| ONB-004 | Tenant + school + admin user creation | 8h | Backend |
| ONB-005 | Welcome email template | 4h | Backend |
| ONB-006 | Self-service registration form | 8h | Frontend |
| ONB-007 | Subdomain suggestion feature | 4h | Frontend |
| ONB-008 | Onboarding setup wizard UI | 12h | Frontend |
| ONB-009 | Trial status display | 4h | Frontend |
| EMAIL-001 | SendGrid integration | 4h | Backend |

**Sprint 4 Deliverables:**
- ✅ Self-service school registration
- ✅ Automatic subdomain provisioning
- ✅ Welcome email with credentials
- ✅ First-login setup wizard

---

### Sprint 5: RBAC & Permissions (Weeks 9-10)

**Focus:** Role-based access control

| Task ID | Task | Effort | Owner |
|---------|------|--------|-------|
| RBAC-001 | Roles table and seeding | 4h | Backend |
| RBAC-002 | Permissions model | 4h | Backend |
| RBAC-003 | User-roles assignment | 4h | Backend |
| RBAC-004 | Permission checking middleware | 8h | Backend |
| RBAC-005 | Role management UI | 8h | Frontend |
| RBAC-006 | User role assignment UI | 4h | Frontend |
| UI-005 | Admin dashboard | 12h | Frontend |
| UI-006 | Navigation with role-based menu | 8h | Frontend |

**Sprint 5 Deliverables:**
- ✅ RBAC system operational
- ✅ Admin dashboard
- ✅ Role-based navigation

---

### Sprint 6: Core Academic Setup (Weeks 11-12)

**Focus:** Academic structure foundation

| Task ID | Task | Effort | Owner |
|---------|------|--------|-------|
| ACD-001 | Academic years CRUD | 8h | Backend |
| ACD-002 | Terms CRUD | 6h | Backend |
| ACD-003 | Classes CRUD | 8h | Backend |
| ACD-004 | Sections CRUD | 4h | Backend |
| ACD-005 | Subjects CRUD | 8h | Backend |
| ACD-006 | Grading scales | 8h | Backend |
| UI-007 | Academic year management UI | 8h | Frontend |
| UI-008 | Class management UI | 8h | Frontend |
| UI-009 | Subject management UI | 8h | Frontend |
| BRD-001 | Tenant branding settings | 8h | Both |

**Sprint 6 Deliverables:**
- ✅ Complete academic structure setup
- ✅ Tenant branding customization
- ✅ Phase 1 complete

---

## 4. Phase 2: MVP Launch (Months 4-6)

### Sprint 7-8: Student Management (Weeks 13-16)

| Task ID | Task | Effort | Owner |
|---------|------|--------|-------|
| STU-001 | Students CRUD API | 12h | Backend |
| STU-002 | Guardians CRUD API | 8h | Backend |
| STU-003 | Student-guardian linking | 4h | Backend |
| STU-004 | Student photo upload | 8h | Backend |
| STU-005 | Student ID generation | 4h | Backend |
| STU-006 | Student list UI | 12h | Frontend |
| STU-007 | Student profile UI | 12h | Frontend |
| STU-008 | Add/Edit student forms | 12h | Frontend |
| STU-009 | Guardian management UI | 8h | Frontend |
| STU-010 | Bulk import (CSV/Excel) | 16h | Both |

**Deliverables:**
- ✅ Complete student management
- ✅ Guardian management
- ✅ Bulk import capability

---

### Sprint 9-10: Staff & Attendance (Weeks 17-20)

| Task ID | Task | Effort | Owner |
|---------|------|--------|-------|
| STF-001 | Staff CRUD API | 12h | Backend |
| STF-002 | Staff-class assignment | 8h | Backend |
| ATT-001 | Attendance marking API | 12h | Backend |
| ATT-002 | Attendance reports API | 8h | Backend |
| ATT-003 | Offline attendance support | 12h | Both |
| UI-010 | Staff list and profile UI | 12h | Frontend |
| UI-011 | Attendance marking UI | 12h | Frontend |
| UI-012 | Attendance reports UI | 8h | Frontend |

**Deliverables:**
- ✅ Staff management
- ✅ Attendance tracking with offline support

---

### Sprint 11-12: Finance & Report Cards (Weeks 21-24)

| Task ID | Task | Effort | Owner |
|---------|------|--------|-------|
| FIN-001 | Fee structure API | 8h | Backend |
| FIN-002 | Invoice generation API | 12h | Backend |
| FIN-003 | Payment recording API | 8h | Backend |
| FIN-004 | MoMo integration (MTN) | 16h | Backend |
| FIN-005 | MoMo integration (Vodafone) | 12h | Backend |
| RPT-001 | Report card generation | 16h | Backend |
| RPT-002 | PDF generation (WeasyPrint) | 8h | Backend |
| UI-013 | Fee structure UI | 8h | Frontend |
| UI-014 | Invoice management UI | 12h | Frontend |
| UI-015 | Payment UI with MoMo | 12h | Frontend |
| UI-016 | Report card preview/download | 8h | Frontend |
| PILOT-001 | Onboard 10 pilot schools | 20h | Team |

**Deliverables:**
- ✅ Fee management with Mobile Money
- ✅ Report card generation
- ✅ **MVP LAUNCH with 10 pilot schools**

---

## 5. Phase 3: Enhancement (Months 7-9)

### Sprint 13-14: Exams & Advanced Grading (Weeks 25-28)

| Task ID | Task | Effort | Owner |
|---------|------|--------|-------|
| EXM-001 | Exam management API | 12h | Backend |
| EXM-002 | Score entry API | 12h | Backend |
| EXM-003 | Grade calculation engine | 8h | Backend |
| EXM-004 | Class rankings | 8h | Backend |
| UI-017 | Exam setup UI | 12h | Frontend |
| UI-018 | Score entry UI | 12h | Frontend |
| UI-019 | Grade reports UI | 8h | Frontend |

---

### Sprint 15-16: Boarding & Transport (Weeks 29-32)

| Task ID | Task | Effort | Owner |
|---------|------|--------|-------|
| BRD-001 | Dormitory management API | 12h | Backend |
| BRD-002 | Room/bed assignment API | 8h | Backend |
| BRD-003 | Exeat workflow API | 12h | Backend |
| TRN-001 | Route management API | 12h | Backend |
| TRN-002 | Vehicle management API | 8h | Backend |
| TRN-003 | Student transport assignment | 8h | Backend |
| UI-020 | Boarding management UI | 16h | Frontend |
| UI-021 | Exeat request/approval UI | 12h | Frontend |
| UI-022 | Transport management UI | 12h | Frontend |

---

### Sprint 17-18: Parent Portal & Communication (Weeks 33-36)

| Task ID | Task | Effort | Owner |
|---------|------|--------|-------|
| PAR-001 | Parent portal API | 12h | Backend |
| PAR-002 | Parent account auto-creation | 8h | Backend |
| SMS-001 | Hubtel SMS integration | 12h | Backend |
| SMS-002 | SMS templates | 8h | Backend |
| COM-001 | Announcements API | 8h | Backend |
| UI-023 | Parent portal dashboard | 16h | Frontend |
| UI-024 | Parent fee payment UI | 12h | Frontend |
| UI-025 | SMS sending UI | 8h | Frontend |
| UI-026 | Announcements UI | 8h | Frontend |
| SCALE-001 | Onboard to 50 schools | 30h | Team |

**Deliverables:**
- ✅ Parent portal live
- ✅ SMS integration
- ✅ **50 schools onboarded**

---

## 6. Phase 4: Scale & Mobile (Months 10-12)

### Sprint 19-20: Mobile Apps (Weeks 37-40)

| Task ID | Task | Effort | Owner |
|---------|------|--------|-------|
| MOB-001 | React Native setup | 16h | Mobile |
| MOB-002 | School code entry flow | 8h | Mobile |
| MOB-003 | Authentication flow | 12h | Mobile |
| MOB-004 | Teacher app - Attendance | 16h | Mobile |
| MOB-005 | Teacher app - Scores | 16h | Mobile |
| MOB-006 | Parent app - Dashboard | 16h | Mobile |
| MOB-007 | Parent app - Payments | 16h | Mobile |
| MOB-008 | Push notifications | 12h | Mobile |

---

### Sprint 21-22: Offline & Performance (Weeks 41-44)

| Task ID | Task | Effort | Owner |
|---------|------|--------|-------|
| OFF-001 | Service worker implementation | 16h | Frontend |
| OFF-002 | Offline data storage | 16h | Frontend |
| OFF-003 | Sync queue management | 12h | Frontend |
| OFF-004 | Conflict resolution | 12h | Both |
| PERF-001 | Database query optimization | 16h | Backend |
| PERF-002 | Caching layer (Redis) | 12h | Backend |
| PERF-003 | CDN configuration | 8h | DevOps |

---

### Sprint 23-24: Polish & Scale (Weeks 45-48)

| Task ID | Task | Effort | Owner |
|---------|------|--------|-------|
| QA-001 | Comprehensive testing | 40h | QA |
| SEC-001 | Security audit | 20h | Security |
| SEC-002 | Penetration testing | 20h | Security |
| DOC-001 | API documentation | 16h | Backend |
| DOC-002 | User documentation | 16h | Team |
| SCALE-002 | Performance load testing | 20h | DevOps |
| SCALE-003 | Onboard to 100+ schools | 40h | Team |

**Deliverables:**
- ✅ Mobile apps on app stores
- ✅ Full offline capability
- ✅ Security audit complete
- ✅ **100+ schools onboarded**

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

### 7.3 Third-Party Services (Monthly at Scale)

| Service | Cost |
|---------|------|
| Hubtel SMS (5,000 SMS) | GHS 750 |
| MoMo API fees | Variable |
| SSL Certificate | Free (Let's Encrypt) |

### 7.4 Total Budget Summary

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

### 8.3 Mitigation Strategies

1. **Subdomain Infrastructure:** Tested thoroughly in Sprint 1
2. **Security:** Regular audits, RLS validation
3. **Performance:** Load testing before each major release
4. **User Adoption:** Training materials, dedicated support

---

## 9. Success Metrics

### 9.1 Phase 1 Success Criteria

- [ ] Wildcard subdomain routing working
- [ ] 5+ test tenants created successfully
- [ ] Login works on all subdomains
- [ ] RLS tenant isolation verified
- [ ] CI/CD pipeline operational

### 9.2 Phase 2 Success Criteria (MVP)

- [ ] 10 pilot schools onboarded
- [ ] Students enrolled in all pilots
- [ ] Attendance marked for 1 week
- [ ] Fee payments processed via MoMo
- [ ] Report cards generated

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
| 2.0 | January 2026 | Harry McNinson | Added subdomain infrastructure tasks, updated Sprint 1-4 |
