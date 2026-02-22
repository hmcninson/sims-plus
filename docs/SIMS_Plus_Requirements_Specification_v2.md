# SIMS Plus (School Information Management System Plus) - Software Requirements Specification

**Version:** 2.2
**Date:** January 2026
**Author:** Harry McNinson
**Status:** Updated with Finance, Credit Notes, Calendar, Timetable, and Preschool Requirements

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [System Overview](#2-system-overview)
3. [Subdomain & Multi-Tenancy Requirements](#3-subdomain--multi-tenancy-requirements)
4. [User Roles & Permissions](#4-user-roles--permissions)
5. [Authentication Requirements](#5-authentication-requirements)
6. [School Onboarding Requirements](#6-school-onboarding-requirements)
7. [Student Management Requirements](#7-student-management-requirements)
8. [Staff Management Requirements](#8-staff-management-requirements)
9. [Academic Management Requirements](#9-academic-management-requirements)
10. [Attendance Requirements](#10-attendance-requirements)
11. [Examination & Grading Requirements](#11-examination--grading-requirements)
12. [Finance Requirements](#12-finance-requirements)
13. [Boarding House Requirements](#13-boarding-house-requirements)
14. [Transport Requirements](#14-transport-requirements)
15. [Communication Requirements](#15-communication-requirements)
16. [Reporting Requirements](#16-reporting-requirements)
17. [Parent Portal Requirements](#17-parent-portal-requirements)
18. [Mobile Application Requirements](#18-mobile-application-requirements)
19. [API Requirements](#19-api-requirements)
20. [Non-Functional Requirements](#20-non-functional-requirements)

---

## 1. Introduction

### 1.1 Purpose

This document specifies the functional and non-functional requirements for SIMS Plus, a comprehensive School Information Management System designed for Ghanaian educational institutions.

### 1.2 Scope

SIMS Plus is a multi-tenant SaaS platform that provides:
- Student enrollment and records management
- Staff and HR management
- Academic management (curriculum, timetables, exams)
- Financial management (fees, payments, Mobile Money)
- Attendance tracking
- Boarding house management
- Transport management
- Parent/Guardian portal
- Multi-curriculum support (GES, Cambridge, IB, American)
- Ghana-specific integrations (Mobile Money, GES reporting)

### 1.3 Target Users

- School administrators
- Teachers and academic staff
- Finance officers
- Parents/Guardians
- Students (limited access)
- House parents (boarding schools)
- Transport coordinators

### 1.4 Definitions

| Term | Definition |
|------|------------|
| **Tenant** | A single school or school chain using the platform |
| **Subdomain** | The unique URL identifier for a school (e.g., `presec` in `presec.simsplus.io`) |
| **RLS** | Row-Level Security - database feature for tenant isolation |
| **GES** | Ghana Education Service |
| **MoMo** | Mobile Money (MTN, Vodafone Cash, AirtelTigo Money) |

---

## 2. System Overview

### 2.1 Architecture Summary

SIMS Plus uses a **shared infrastructure, multi-tenant architecture**:

```
┌─────────────────────────────────────────────────────────────────┐
│                   SHARED INFRASTRUCTURE                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  presec.simsplus.io    ──┐                                    │
│  achimota.simsplus.io  ──┼──► SAME Servers ──► SAME Database  │
│  wesleyg.simsplus.io   ──┤                    (isolated by    │
│  {any}.simsplus.io     ──┘                     tenant_id)     │
│                                                                  │
│  • ONE set of servers (not one per school)                      │
│  • ONE database (not one per school)                            │
│  • ONE codebase (not one per school)                            │
│  • Data isolated by tenant_id + Row-Level Security              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 URL Structure

| URL | Purpose |
|-----|---------|
| `simsplus.io` | Marketing website |
| `www.simsplus.io` | Marketing website |
| `app.simsplus.io` | Generic login portal |
| `api.simsplus.io` | API endpoint |
| `{school}.simsplus.io` | School-specific portal |

---

## 3. Subdomain & Multi-Tenancy Requirements

### 3.1 URL Structure Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| SUB-001 | System SHALL support wildcard subdomain routing (`*.simsplus.io`) | MUST |
| SUB-002 | Each school SHALL have a unique subdomain (e.g., `presec.simsplus.io`) | MUST |
| SUB-003 | Marketing site SHALL be accessible at `simsplus.io` and `www.simsplus.io` | MUST |
| SUB-004 | Generic login portal SHALL be accessible at `app.simsplus.io` | MUST |
| SUB-005 | API SHALL be accessible at `api.simsplus.io` and `{subdomain}.simsplus.io/api` | MUST |
| SUB-006 | System SHALL redirect HTTP to HTTPS for all subdomains | MUST |
| SUB-007 | System SHALL support custom domain mapping for Enterprise tier | SHOULD |

### 3.2 Subdomain Validation Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| SUB-010 | Subdomains SHALL be 4-63 characters in length | MUST |
| SUB-011 | Subdomains SHALL contain only lowercase letters, numbers, and hyphens | MUST |
| SUB-012 | Subdomains SHALL NOT start or end with a hyphen | MUST |
| SUB-013 | Subdomains SHALL NOT contain consecutive hyphens | SHOULD |
| SUB-014 | System SHALL maintain a list of reserved subdomains | MUST |
| SUB-015 | Reserved subdomains SHALL include: www, app, api, admin, mail, ftp, status, blog, help, support, docs | MUST |
| SUB-016 | System SHALL check subdomain availability before registration | MUST |
| SUB-017 | System SHALL provide subdomain suggestions when requested name is taken | SHOULD |

### 3.3 SSL/TLS Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| SUB-020 | System SHALL use wildcard SSL certificate for `*.simsplus.io` | MUST |
| SUB-021 | All subdomains SHALL support TLS 1.2 minimum, TLS 1.3 preferred | MUST |
| SUB-022 | System SHALL implement HSTS with minimum 1-year max-age | MUST |
| SUB-023 | SSL certificates SHALL auto-renew before expiration | MUST |

### 3.4 Tenant Isolation Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| TEN-001 | Each tenant's data SHALL be completely isolated from other tenants | MUST |
| TEN-002 | Database SHALL implement Row-Level Security (RLS) for tenant isolation | MUST |
| TEN-003 | All queries SHALL automatically filter by current tenant context | MUST |
| TEN-004 | Cross-tenant data access SHALL be technically impossible for regular users | MUST |
| TEN-005 | System SHALL log all cross-tenant access attempts | MUST |
| TEN-006 | JWT tokens SHALL include tenant_id claim | MUST |
| TEN-007 | System SHALL reject tokens used on wrong tenant subdomain | MUST |

### 3.5 Tenant Branding Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| TEN-010 | Each tenant SHALL be able to customize their logo | MUST |
| TEN-011 | Each tenant SHALL be able to customize primary brand color | MUST |
| TEN-012 | Login page SHALL display tenant's logo and branding | MUST |
| TEN-013 | Report cards SHALL use tenant's logo and branding | MUST |
| TEN-014 | Tenant branding SHALL be applied to all portal pages | MUST |
| TEN-015 | System SHALL provide default branding for tenants without custom branding | MUST |

### 3.6 Tenant Status Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| TEN-020 | Tenant status SHALL be one of: trial, active, suspended, cancelled | MUST |
| TEN-021 | Suspended tenants SHALL see suspension notice on login | MUST |
| TEN-022 | Suspended tenants SHALL NOT be able to access the system | MUST |
| TEN-023 | Cancelled tenant subdomains SHALL show "School not found" page | MUST |
| TEN-024 | System SHALL preserve cancelled tenant data for 90 days | MUST |
| TEN-025 | Trial tenants SHALL see days remaining in trial | SHOULD |

---

## 4. User Roles & Permissions

### 4.1 System Roles

| Role | Description | Key Permissions |
|------|-------------|-----------------|
| **Super Admin** | SIMS Plus platform administrator | All permissions across all tenants |
| **School Admin** | School administrator | Full access within their school |
| **Academic Head** | Head of academics | Academic, exams, reports |
| **Finance Officer** | Finance department | Fees, payments, financial reports |
| **Teacher** | Teaching staff | Attendance, grades, own classes |
| **House Parent** | Boarding house staff | Boarding management |
| **Transport Officer** | Transport coordinator | Routes, vehicles, assignments |
| **Parent** | Parent/Guardian | View child's info, pay fees |
| **Student** | Student (limited) | View own info, timetable |

### 4.2 Permission Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| ROL-001 | System SHALL support role-based access control (RBAC) | MUST |
| ROL-002 | Permissions SHALL be granular (module.action format) | MUST |
| ROL-003 | Custom roles SHALL be creatable per tenant | SHOULD |
| ROL-004 | Users MAY have multiple roles | MUST |
| ROL-005 | Role changes SHALL take effect immediately | MUST |

---

## 5. Authentication Requirements

### 5.1 School-Specific Login

| ID | Requirement | Priority |
|----|-------------|----------|
| AUTH-001 | Users SHALL login at their school's subdomain | MUST |
| AUTH-002 | Login page SHALL display school's logo and name | MUST |
| AUTH-003 | System SHALL validate credentials only within the tenant | MUST |
| AUTH-004 | Successful login SHALL redirect to school's dashboard | MUST |
| AUTH-005 | System SHALL support "Remember me" functionality | SHOULD |
| AUTH-006 | Failed login attempts SHALL be rate-limited (5 per minute) | MUST |
| AUTH-007 | Account SHALL lock after 5 consecutive failed attempts | MUST |

### 5.2 Generic Login Portal

| ID | Requirement | Priority |
|----|-------------|----------|
| AUTH-010 | `app.simsplus.io` SHALL provide school search/selection | MUST |
| AUTH-011 | Users SHALL be able to find their school by name or code | MUST |
| AUTH-012 | After school selection, user SHALL be redirected to school's subdomain | MUST |
| AUTH-013 | System SHALL remember last used school for returning users | SHOULD |

### 5.3 Password Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| AUTH-020 | Passwords SHALL be minimum 8 characters | MUST |
| AUTH-021 | Passwords SHALL require mixed case, numbers, or symbols | SHOULD |
| AUTH-022 | Password reset SHALL be available via email | MUST |
| AUTH-023 | Password reset links SHALL expire after 24 hours | MUST |
| AUTH-024 | System SHALL support MFA via authenticator app | SHOULD |

### 5.4 Session Management

| ID | Requirement | Priority |
|----|-------------|----------|
| AUTH-030 | Sessions SHALL expire after 30 minutes of inactivity | MUST |
| AUTH-031 | Users SHALL be able to view active sessions | SHOULD |
| AUTH-032 | Users SHALL be able to terminate other sessions | SHOULD |
| AUTH-033 | JWT access tokens SHALL expire after 15 minutes | MUST |
| AUTH-034 | Refresh tokens SHALL expire after 7 days | MUST |

---

## 6. School Onboarding Requirements

### 6.1 Self-Service Registration

| ID | Requirement | Priority |
|----|-------------|----------|
| ONB-001 | Schools SHALL be able to self-register via simsplus.io | MUST |
| ONB-002 | Registration SHALL require: school name, subdomain, admin email, admin name | MUST |
| ONB-003 | System SHALL validate email with verification link | MUST |
| ONB-004 | System SHALL create tenant, school, and admin user on registration | MUST |
| ONB-005 | System SHALL send welcome email with login instructions | MUST |
| ONB-006 | System SHALL provide 30-day free trial for new registrations | MUST |
| ONB-007 | Trial SHALL include full feature access up to 100 students | MUST |

### 6.2 Setup Wizard

| ID | Requirement | Priority |
|----|-------------|----------|
| ONB-010 | First login SHALL present school setup wizard | MUST |
| ONB-011 | Setup wizard SHALL guide through: school profile, academic year, terms, classes, subjects | MUST |
| ONB-012 | Setup wizard progress SHALL be saved and resumable | MUST |
| ONB-013 | Setup wizard SHALL be skippable for experienced users | SHOULD |
| ONB-014 | System SHALL provide sample data import option | SHOULD |

---

## 7. Student Management Requirements

### 7.1 Student Registration

| ID | Requirement | Priority |
|----|-------------|----------|
| STU-001 | System SHALL capture: name, DOB, gender, photo, contact info | MUST |
| STU-002 | System SHALL capture: Ghana Card number (optional) | SHOULD |
| STU-003 | System SHALL capture: NHIS number | SHOULD |
| STU-004 | System SHALL auto-generate unique student ID | MUST |
| STU-005 | System SHALL support bulk student import via CSV/Excel | MUST |
| STU-006 | Student records SHALL be linked to guardians | MUST |

### 7.2 Guardian Management

| ID | Requirement | Priority |
|----|-------------|----------|
| STU-010 | Each student SHALL have at least one guardian | MUST |
| STU-011 | System SHALL capture guardian: name, relationship, phone, email | MUST |
| STU-012 | System SHALL support multiple guardians per student | MUST |
| STU-013 | One guardian SHALL be designated as primary contact | MUST |
| STU-014 | Guardians SHALL be able to have multiple children linked | MUST |

### 7.3 Enrollment

| ID | Requirement | Priority |
|----|-------------|----------|
| STU-020 | System SHALL track enrollment history | MUST |
| STU-021 | System SHALL support: promotion, repetition, transfer, withdrawal | MUST |
| STU-022 | System SHALL generate enrollment statistics | MUST |
| STU-023 | System SHALL support mid-year enrollment | MUST |

---

## 8. Staff Management Requirements

### 8.1 Staff Records

| ID | Requirement | Priority |
|----|-------------|----------|
| STF-001 | System SHALL capture: name, contact, qualifications, employment date | MUST |
| STF-002 | System SHALL capture: Ghana Card, SSNIT, TIN numbers | SHOULD |
| STF-003 | System SHALL support staff categories: teaching, non-teaching, admin | MUST |
| STF-004 | System SHALL track staff documents (certificates, contracts) | SHOULD |

### 8.2 Staff Assignment

| ID | Requirement | Priority |
|----|-------------|----------|
| STF-010 | Teachers SHALL be assignable to classes and subjects | MUST |
| STF-011 | System SHALL support class teacher designation | MUST |
| STF-012 | System SHALL support department/unit assignment | SHOULD |
| STF-013 | System SHALL track teaching workload | SHOULD |

---

## 9. Academic Management Requirements

### 9.1 Curriculum Support

| ID | Requirement | Priority |
|----|-------------|----------|
| ACD-001 | System SHALL support GES curriculum (default) | MUST |
| ACD-002 | System SHALL support Cambridge curriculum | MUST |
| ACD-003 | System SHALL support IB curriculum | SHOULD |
| ACD-004 | System SHALL support American curriculum | SHOULD |
| ACD-005 | Schools SHALL be able to customize grading scales | MUST |

### 9.2 Class Management

| ID | Requirement | Priority |
|----|-------------|----------|
| ACD-010 | System SHALL support class levels: Creche, KG, Primary, JHS, SHS | MUST |
| ACD-011 | System SHALL support class sections/streams | MUST |
| ACD-012 | System SHALL support subject assignment to classes | MUST |
| ACD-013 | System SHALL support elective subjects | MUST |

### 9.3 Timetable

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| ACD-020 | System SHALL support timetable creation | MUST | ✅ Implemented |
| ACD-021 | System SHALL detect scheduling conflicts | MUST | ✅ Implemented |
| ACD-022 | System SHALL support recurring and one-time schedules | MUST | ✅ Implemented |
| ACD-023 | Timetables SHALL be viewable by class, teacher, room | MUST | ✅ Implemented |
| ACD-024 | System SHALL support period types: class, break, assembly, lunch | SHOULD | ✅ Implemented |
| ACD-025 | System SHALL support teacher assignment to periods | MUST | ✅ Implemented |

### 9.4 School Calendar

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| CAL-001 | System SHALL support school calendar with events and holidays | MUST | ✅ Implemented |
| CAL-002 | Calendar SHALL display month, week, and year views | MUST | ✅ Implemented |
| CAL-003 | Calendar SHALL show term periods with visual distinction | MUST | ✅ Implemented |
| CAL-004 | System SHALL support multiple event types: public_holiday, school_break, school_event, exam_period | MUST | ✅ Implemented |
| CAL-005 | System SHALL calculate school days per term (excluding weekends and holidays) | MUST | ✅ Implemented |
| CAL-006 | Events SHALL support multi-day spans | MUST | ✅ Implemented |
| CAL-007 | System SHALL support drag-and-drop event rescheduling | SHOULD | ✅ Implemented |
| CAL-008 | System SHALL support iCal export for integration with external calendars | SHOULD | ✅ Implemented |
| CAL-009 | System SHALL support Google Calendar integration links | SHOULD | ✅ Implemented |
| CAL-010 | Calendar SHALL display upcoming events list | SHOULD | ✅ Implemented |

---

## 10. Attendance Requirements

### 10.1 Student Attendance

| ID | Requirement | Priority |
|----|-------------|----------|
| ATT-001 | System SHALL support daily attendance marking | MUST |
| ATT-002 | System SHALL support status: Present, Absent, Late, Excused | MUST |
| ATT-003 | System SHALL support bulk attendance marking | MUST |
| ATT-004 | System SHALL work offline and sync when connected | MUST |
| ATT-005 | Late arrivals SHALL capture arrival time | SHOULD |
| ATT-006 | Absent students SHALL trigger SMS to parents (configurable) | SHOULD |

### 10.2 Attendance Reports

| ID | Requirement | Priority |
|----|-------------|----------|
| ATT-010 | System SHALL calculate attendance percentage per student | MUST |
| ATT-011 | System SHALL generate class attendance summaries | MUST |
| ATT-012 | System SHALL flag students below attendance threshold | SHOULD |

---

## 11. Examination & Grading Requirements

### 11.1 Exam Management

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| EXM-001 | System SHALL support exam types: class test, mid-term, end-of-term, mock | MUST | ✅ Implemented |
| EXM-002 | System SHALL support exam scheduling | MUST | ✅ Implemented |
| EXM-003 | System SHALL support exam weight configuration | MUST | ✅ Implemented |
| EXM-004 | System SHALL support continuous assessment (CA) | MUST | ✅ Implemented |
| EXM-005 | System SHALL support multiple CA types: class_test, homework, assignment, quiz, project | MUST | ✅ Implemented |
| EXM-006 | System SHALL support configurable CA and exam weights | MUST | ✅ Implemented |
| EXM-007 | System SHALL log all score changes for audit purposes | MUST | ✅ Implemented |

### 11.2 Score Entry

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| EXM-010 | Teachers SHALL enter scores by class/subject | MUST | ✅ Implemented |
| EXM-011 | System SHALL validate scores against maximum marks | MUST | ✅ Implemented |
| EXM-012 | System SHALL auto-calculate grades based on grading scale | MUST | ✅ Implemented |
| EXM-013 | System SHALL support bulk score import | SHOULD | ✅ Implemented |
| EXM-014 | System SHALL support score entry deadline | SHOULD | Planned |
| EXM-015 | System SHALL provide exam analytics: averages, pass rates, grade distribution | MUST | ✅ Implemented |

### 11.3 Report Cards

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| EXM-020 | System SHALL generate report cards with school branding | MUST | ✅ Implemented |
| EXM-021 | Report cards SHALL show: subjects, scores, grades, position, remarks | MUST | ✅ Implemented |
| EXM-022 | Report cards SHALL be downloadable as PDF | MUST | ✅ Implemented |
| EXM-023 | Report cards SHALL support QR code verification | SHOULD | Planned |
| EXM-024 | System SHALL support multiple report card templates | SHOULD | Planned |
| EXM-025 | Report cards SHALL include teacher and head teacher comments | MUST | ✅ Implemented |
| EXM-026 | Report cards SHALL include attendance summary | SHOULD | ✅ Implemented |

### 11.4 Preschool Assessment

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| PRE-001 | System SHALL support developmental domains: cognitive, physical, social-emotional, language, creative | MUST | ✅ Implemented |
| PRE-002 | System SHALL support age-appropriate milestones per domain | MUST | ✅ Implemented |
| PRE-003 | System SHALL support student observations with categories and photos | MUST | ✅ Implemented |
| PRE-004 | System SHALL support daily activity logs: meals, naps, toileting, activities | MUST | ✅ Implemented |
| PRE-005 | System SHALL support milestone-based assessments | MUST | ✅ Implemented |
| PRE-006 | System SHALL generate developmental progress reports | MUST | ✅ Implemented |
| PRE-007 | Preschool reports SHALL use narrative format instead of numeric grades | SHOULD | ✅ Implemented |

---

## 12. Finance Requirements

### 12.1 Fee Management

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FIN-001 | System SHALL support fee structure creation | MUST | ✅ Implemented |
| FIN-002 | System SHALL support fee categories: tuition, boarding, transport, PTA | MUST | ✅ Implemented |
| FIN-003 | System SHALL support fee variations by class level | MUST | ✅ Implemented |
| FIN-004 | System SHALL auto-generate invoices per term | MUST | ✅ Implemented |
| FIN-005 | System SHALL support discounts (sibling, scholarship, staff) | MUST | ✅ Implemented |

### 12.2 Payment Processing

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FIN-010 | System SHALL support cash payments | MUST | ✅ Implemented |
| FIN-011 | System SHALL support MTN Mobile Money | MUST | ✅ Implemented |
| FIN-012 | System SHALL support Vodafone Cash | MUST | ✅ Implemented |
| FIN-013 | System SHALL support AirtelTigo Money | SHOULD | ✅ Implemented |
| FIN-014 | System SHALL support bank transfer recording | MUST | ✅ Implemented |
| FIN-015 | System SHALL auto-reconcile MoMo payments via webhook | MUST | Planned |
| FIN-016 | System SHALL generate payment receipts | MUST | ✅ Implemented |
| FIN-017 | Receipts SHALL be sendable via SMS | SHOULD | Planned |

### 12.3 Financial Reports

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FIN-020 | System SHALL generate fee collection reports | MUST | ✅ Implemented |
| FIN-021 | System SHALL generate outstanding fees report | MUST | ✅ Implemented |
| FIN-022 | System SHALL generate daily/weekly/monthly collection summaries | MUST | ✅ Implemented |
| FIN-023 | System SHALL support export to Excel | MUST | Planned |

### 12.4 Scholarship Management

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FIN-030 | System SHALL support scholarship creation with types: full, partial, merit, need-based, athletic, special | MUST | ✅ Implemented |
| FIN-031 | System SHALL support scholarship coverage by percentage or fixed amount | MUST | ✅ Implemented |
| FIN-032 | System SHALL support awarding scholarships to individual and multiple students | MUST | ✅ Implemented |
| FIN-033 | System SHALL auto-apply scholarship discounts at invoice generation time | MUST | ✅ Implemented |
| FIN-034 | System SHALL support scholarship revocation with reason | MUST | ✅ Implemented |
| FIN-035 | System SHALL enforce max recipients limit per scholarship | SHOULD | ✅ Implemented |
| FIN-036 | Scholarships awarded after invoice generation SHALL require cancel and regenerate of invoice to take effect | MUST | ✅ Implemented |

### 12.5 Credit Notes

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FIN-040 | System SHALL support credit notes for overpayments, fee reductions, and error corrections | MUST | ✅ Implemented |
| FIN-041 | Credit notes SHALL follow a workflow: draft → issued → applied/refunded/cancelled | MUST | ✅ Implemented |
| FIN-042 | System SHALL support applying credit notes to unpaid invoices | MUST | ✅ Implemented |
| FIN-043 | System SHALL auto-apply issued credit notes to the student's oldest unpaid invoice | SHOULD | ✅ Implemented |
| FIN-044 | System SHALL track student credit balance (total issued minus applied and refunded) | MUST | ✅ Implemented |
| FIN-045 | System SHALL support credit note refunds with method and reference tracking | MUST | ✅ Implemented |
| FIN-046 | System SHALL support credit note cancellation with reason | MUST | ✅ Implemented |
| FIN-047 | Only draft credit notes SHALL be editable; issued and beyond SHALL be immutable | MUST | ✅ Implemented |

### 12.6 Finance Audit Trail

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FIN-050 | System SHALL maintain an immutable audit log for all finance transactions | MUST | ✅ Implemented |
| FIN-051 | Audit log SHALL record entity type, action, old/new values, user, and timestamp | MUST | ✅ Implemented |
| FIN-052 | Audit log SHALL cover invoices, payments, credit notes, and scholarships | MUST | ✅ Implemented |
| FIN-053 | Audit entries SHALL NOT be deletable or modifiable | MUST | ✅ Implemented |

---

## 13. Boarding House Requirements

### 13.1 Dormitory Management

| ID | Requirement | Priority |
|----|-------------|----------|
| BRD-001 | System SHALL support dormitory/house creation | MUST |
| BRD-002 | System SHALL support room and bed management | MUST |
| BRD-003 | System SHALL track bed assignments | MUST |
| BRD-004 | System SHALL show occupancy statistics | MUST |

### 13.2 Exeat Management

| ID | Requirement | Priority |
|----|-------------|----------|
| BRD-010 | System SHALL support exeat request workflow | MUST |
| BRD-011 | Exeat requests SHALL capture: reason, departure/return time, pickup person | MUST |
| BRD-012 | Exeat requests SHALL require approval | MUST |
| BRD-013 | System SHALL track exeat history | MUST |
| BRD-014 | System SHALL notify parents of exeat status | SHOULD |

### 13.3 Roll Call

| ID | Requirement | Priority |
|----|-------------|----------|
| BRD-020 | System SHALL support dormitory roll call | MUST |
| BRD-021 | Roll call SHALL flag students on exeat | MUST |
| BRD-022 | System SHALL track lights-out compliance | SHOULD |

---

## 14. Transport Requirements

### 14.1 Route Management

| ID | Requirement | Priority |
|----|-------------|----------|
| TRN-001 | System SHALL support transport route creation | MUST |
| TRN-002 | System SHALL support pickup points per route | MUST |
| TRN-003 | System SHALL support GPS coordinates for points | SHOULD |
| TRN-004 | System SHALL calculate estimated arrival times | SHOULD |

### 14.2 Vehicle Management

| ID | Requirement | Priority |
|----|-------------|----------|
| TRN-010 | System SHALL track vehicles: registration, capacity, driver | MUST |
| TRN-011 | System SHALL track vehicle maintenance schedule | SHOULD |
| TRN-012 | System SHALL assign vehicles to routes | MUST |

### 14.3 Student Transport

| ID | Requirement | Priority |
|----|-------------|----------|
| TRN-020 | System SHALL assign students to routes/pickup points | MUST |
| TRN-021 | System SHALL support transport fee calculation | MUST |
| TRN-022 | System SHALL notify parents of arrival (optional) | SHOULD |

---

## 15. Communication Requirements

### 15.1 SMS Notifications

| ID | Requirement | Priority |
|----|-------------|----------|
| COM-001 | System SHALL support SMS via Hubtel API | MUST |
| COM-002 | System SHALL support bulk SMS to parents | MUST |
| COM-003 | System SHALL support SMS templates | MUST |
| COM-004 | System SHALL track SMS delivery status | SHOULD |
| COM-005 | System SHALL support SMS credits management | MUST |

### 15.2 In-App Notifications

| ID | Requirement | Priority |
|----|-------------|----------|
| COM-010 | System SHALL support push notifications | SHOULD |
| COM-011 | System SHALL support in-app announcements | MUST |
| COM-012 | Announcements SHALL be targetable by class/group | MUST |

### 15.3 Email Notifications

| ID | Requirement | Priority |
|----|-------------|----------|
| COM-020 | System SHALL support email notifications | MUST |
| COM-021 | System SHALL support email templates | MUST |
| COM-022 | System SHALL support bulk email | SHOULD |

---

## 16. Reporting Requirements

### 16.1 Standard Reports

| ID | Requirement | Priority |
|----|-------------|----------|
| RPT-001 | System SHALL provide enrollment reports | MUST |
| RPT-002 | System SHALL provide attendance reports | MUST |
| RPT-003 | System SHALL provide academic performance reports | MUST |
| RPT-004 | System SHALL provide financial reports | MUST |
| RPT-005 | All reports SHALL be exportable to PDF and Excel | MUST |

### 16.2 GES Reports

| ID | Requirement | Priority |
|----|-------------|----------|
| RPT-010 | System SHALL generate EMIS-compatible reports | SHOULD |
| RPT-011 | System SHALL generate enrollment statistics for GES | SHOULD |
| RPT-012 | System SHALL support BECE/WASSCE result tracking | SHOULD |

### 16.3 Dashboard Analytics

| ID | Requirement | Priority |
|----|-------------|----------|
| RPT-020 | Dashboard SHALL show key metrics: enrollment, attendance, fees | MUST |
| RPT-021 | Dashboard SHALL show trends and comparisons | SHOULD |
| RPT-022 | Dashboard SHALL be role-appropriate | MUST |

---

## 17. Parent Portal Requirements

### 17.1 Parent Access

| ID | Requirement | Priority |
|----|-------------|----------|
| PAR-001 | Parents SHALL access portal at school's subdomain | MUST |
| PAR-002 | Parents SHALL view their children's information | MUST |
| PAR-003 | Parents with multiple children SHALL see all in one account | MUST |
| PAR-004 | Parent accounts SHALL be auto-created when guardian is added | SHOULD |

### 17.2 Parent Features

| ID | Requirement | Priority |
|----|-------------|----------|
| PAR-010 | Parents SHALL view attendance records | MUST |
| PAR-011 | Parents SHALL view grades and report cards | MUST |
| PAR-012 | Parents SHALL view fee statements | MUST |
| PAR-013 | Parents SHALL pay fees via Mobile Money | MUST |
| PAR-014 | Parents SHALL receive SMS/email notifications | MUST |
| PAR-015 | Parents SHALL view announcements | MUST |

---

## 18. Mobile Application Requirements

### 18.1 Mobile App General

| ID | Requirement | Priority |
|----|-------------|----------|
| MOB-001 | Mobile app SHALL be available for Android | MUST |
| MOB-002 | Mobile app SHALL be available for iOS | SHOULD |
| MOB-003 | Mobile app SHALL require school code on first launch | MUST |
| MOB-004 | Mobile app SHALL work offline for key functions | MUST |
| MOB-005 | Mobile app SHALL sync data when online | MUST |

### 18.2 Teacher Mobile App

| ID | Requirement | Priority |
|----|-------------|----------|
| MOB-010 | Teachers SHALL mark attendance via mobile app | MUST |
| MOB-011 | Teachers SHALL enter scores via mobile app | SHOULD |
| MOB-012 | Teachers SHALL view their timetable | MUST |
| MOB-013 | Teachers SHALL receive notifications | MUST |

### 18.3 Parent Mobile App

| ID | Requirement | Priority |
|----|-------------|----------|
| MOB-020 | Parents SHALL view child info via mobile app | MUST |
| MOB-021 | Parents SHALL pay fees via mobile app | MUST |
| MOB-022 | Parents SHALL receive push notifications | MUST |
| MOB-023 | Parents SHALL download report cards | SHOULD |

---

## 19. API Requirements

### 19.1 API General

| ID | Requirement | Priority |
|----|-------------|----------|
| API-001 | System SHALL provide RESTful API | MUST |
| API-002 | API SHALL use JSON format | MUST |
| API-003 | API SHALL be versioned (v1, v2, etc.) | MUST |
| API-004 | API SHALL require authentication | MUST |
| API-005 | API documentation SHALL be available (OpenAPI/Swagger) | MUST |

### 19.2 API Access Control

| ID | Requirement | Priority |
|----|-------------|----------|
| API-010 | API SHALL be accessible at `{subdomain}.simsplus.io/api/v1` | MUST |
| API-011 | API SHALL also be accessible at `api.simsplus.io/v1` with X-Subdomain header | MUST |
| API-012 | API SHALL validate JWT tenant matches request tenant | MUST |
| API-013 | API SHALL return 403 if token tenant doesn't match request subdomain | MUST |

### 19.3 API Rate Limiting

| ID | Requirement | Priority |
|----|-------------|----------|
| API-020 | API rate limits SHALL be applied per tenant | MUST |
| API-021 | Starter: 1000 requests/hour | MUST |
| API-022 | Professional: 5000 requests/hour | MUST |
| API-023 | Enterprise: 20000 requests/hour | MUST |
| API-024 | Rate limit headers SHALL be included in responses | MUST |

---

## 20. Non-Functional Requirements

### 20.1 Performance

| ID | Requirement | Priority |
|----|-------------|----------|
| NFR-001 | Page load time SHALL be under 3 seconds | MUST |
| NFR-002 | API response time SHALL be under 500ms | MUST |
| NFR-003 | Subdomain/tenant lookup SHALL complete in <50ms | MUST |
| NFR-004 | System SHALL support 100 concurrent users per school | MUST |
| NFR-005 | System SHALL handle 1000+ schools | MUST |

### 20.2 Availability

| ID | Requirement | Priority |
|----|-------------|----------|
| NFR-010 | System uptime SHALL be 99.5% minimum | MUST |
| NFR-011 | Wildcard DNS SHALL have 99.99% uptime | MUST |
| NFR-012 | Individual tenant issues SHALL NOT affect other tenants | MUST |
| NFR-013 | Planned maintenance SHALL be scheduled outside school hours | SHOULD |

### 20.3 Security

| ID | Requirement | Priority |
|----|-------------|----------|
| NFR-020 | All data SHALL be encrypted in transit (TLS 1.2+) | MUST |
| NFR-021 | Sensitive data SHALL be encrypted at rest | MUST |
| NFR-022 | Passwords SHALL be hashed using bcrypt or Argon2 | MUST |
| NFR-023 | System SHALL comply with Ghana Data Protection Act 2012 | MUST |
| NFR-024 | Tenant isolation SHALL be verified in security audits | MUST |
| NFR-025 | Penetration testing SHALL include cross-tenant access attempts | MUST |

### 20.4 Usability

| ID | Requirement | Priority |
|----|-------------|----------|
| NFR-030 | UI SHALL be responsive (mobile, tablet, desktop) | MUST |
| NFR-031 | UI SHALL support low-bandwidth environments | MUST |
| NFR-032 | System SHALL support offline functionality | MUST |
| NFR-033 | UI SHALL use Ghana date format (DD/MM/YYYY) | MUST |
| NFR-034 | UI SHALL use GHS currency format | MUST |

### 20.5 Data Management

| ID | Requirement | Priority |
|----|-------------|----------|
| NFR-040 | System SHALL backup data daily | MUST |
| NFR-041 | Backups SHALL be retained for 30 days | MUST |
| NFR-042 | System SHALL support data export per tenant | MUST |
| NFR-043 | Deleted data SHALL be recoverable for 30 days | SHOULD |

### 20.6 Localization

| ID | Requirement | Priority |
|----|-------------|----------|
| NFR-050 | System SHALL support English (default) | MUST |
| NFR-051 | System SHALL support Ghana phone formats | MUST |
| NFR-052 | System SHALL support Ghana regions | MUST |
| NFR-053 | System SHALL support local names with special characters | MUST |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | January 2026 | Harry McNinson | Initial version |
| 2.0 | January 2026 | Harry McNinson | Added subdomain multi-tenancy requirements, onboarding, API access |
| 2.1 | January 2026 | Harry McNinson | Added calendar, timetable, and preschool requirements |
| 2.2 | January 2026 | Harry McNinson | Added finance requirements: scholarships, credit notes, audit trail; marked implemented statuses |
