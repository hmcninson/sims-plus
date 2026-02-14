# SIMS Plus (School Information Management System Plus) - API Specification

**Version:** 2.3
**Date:** January 2026
**Author:** Harry McNinson
**Status:** Updated with Finance API (Fee Structures, Invoices, Payments, Scholarships, Credit Notes, Audit Log)

---

## Table of Contents

1. [API Overview](#1-api-overview)
2. [Subdomain & Tenant Context](#2-subdomain--tenant-context)
3. [Authentication](#3-authentication)
4. [School Onboarding API](#4-school-onboarding-api)
5. [Tenant Management API](#5-tenant-management-api)
6. [Students API](#6-students-api)
7. [Staff API](#7-staff-api)
8. [Attendance API](#8-attendance-api)
9. [Exams API](#9-exams-api)
10. [Calendar API](#10-calendar-api)
11. [Timetable API](#11-timetable-api)
12. [Preschool API](#12-preschool-api)
13. [Finance API](#13-finance-api)
14. [Error Handling](#14-error-handling)

---

## 1. API Overview

### 1.1 Base URLs

| Environment | URL | Purpose |
|-------------|-----|---------|
| Production | `https://api.simsplus.io/v1` | Central API endpoint |
| Production | `https://{subdomain}.simsplus.io/api/v1` | School-specific API |
| Staging | `https://api.staging.simsplus.io/v1` | Testing |
| Development | `http://localhost:8000/api/v1` | Local development |

### 1.2 URL Patterns

```
# Central API (requires X-Subdomain header)
https://api.simsplus.io/v1/students
Header: X-Subdomain: presec

# School-specific API (subdomain in URL)
https://presec.simsplus.io/api/v1/students

# Both resolve to the same data for "presec" tenant
```

### 1.3 Common Headers

| Header | Required | Description |
|--------|----------|-------------|
| `Authorization` | Yes* | Bearer token: `Bearer {jwt_token}` |
| `Content-Type` | Yes | `application/json` |
| `X-Subdomain` | Conditional | Required when using `api.simsplus.io` |
| `X-Request-ID` | No | Client-generated UUID for tracing |
| `Accept-Language` | No | `en` (default), `tw` (Twi) |

### 1.4 Response Format

```json
{
  "success": true,
  "data": { ... },
  "meta": {
    "page": 1,
    "per_page": 20,
    "total": 150,
    "total_pages": 8
  }
}
```

---

## 2. Subdomain & Tenant Context

### 2.1 How Tenant Context Works

Every API request must have tenant context. This is determined by:

1. **Subdomain in URL** (Preferred)
   ```
   https://presec.simsplus.io/api/v1/students
   → Tenant: presec
   ```

2. **X-Subdomain Header** (For central API)
   ```
   https://api.simsplus.io/v1/students
   Header: X-Subdomain: presec
   → Tenant: presec
   ```

3. **JWT Token** (Validated against subdomain)
   ```
   Token contains: { "tenant_subdomain": "presec" }
   Request to: achimota.simsplus.io
   → REJECTED (tenant mismatch)
   ```

### 2.2 Tenant Validation Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    API REQUEST VALIDATION                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Extract subdomain from URL or X-Subdomain header            │
│                          │                                       │
│                          ▼                                       │
│  2. Look up tenant in database                                  │
│     SELECT * FROM tenants WHERE subdomain = 'presec'            │
│                          │                                       │
│                          ▼                                       │
│  3. Validate tenant status                                      │
│     - status = 'active'? ✓                                      │
│     - subscription valid? ✓                                     │
│     - not suspended? ✓                                          │
│                          │                                       │
│                          ▼                                       │
│  4. Validate JWT tenant matches request tenant                  │
│     token.tenant_subdomain === request.subdomain? ✓             │
│                          │                                       │
│                          ▼                                       │
│  5. Set database context for RLS                                │
│     SELECT set_tenant_context('tenant-uuid')                    │
│                          │                                       │
│                          ▼                                       │
│  6. Process request (all queries auto-filtered by tenant)       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Authentication

### 3.1 Login

**Login to School-Specific Portal**

```http
POST https://presec.simsplus.io/api/v1/auth/login
Content-Type: application/json

{
  "email": "teacher@presec.edu.gh",
  "password": "securepassword123"
}
```

**Response (200 OK)**

```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer",
    "expires_in": 900,
    "user": {
      "id": "uuid",
      "email": "teacher@presec.edu.gh",
      "first_name": "Kwame",
      "last_name": "Asante",
      "role": "teacher",
      "tenant": {
        "id": "tenant-uuid",
        "subdomain": "presec",
        "name": "Presbyterian Boys' Secondary School"
      }
    }
  }
}
```

### 3.2 JWT Token Structure

```json
{
  "sub": "user-uuid",
  "email": "teacher@presec.edu.gh",
  "tenant_id": "tenant-uuid",
  "tenant_subdomain": "presec",
  "school_id": "school-uuid",
  "roles": ["teacher"],
  "permissions": [
    "students.read",
    "attendance.mark",
    "grades.enter"
  ],
  "iat": 1704067200,
  "exp": 1704068100
}
```

### 3.3 Token Refresh

```http
POST https://presec.simsplus.io/api/v1/auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

### 3.4 Cross-Tenant Access Prevention

If a user tries to access a different tenant:

```http
GET https://achimota.simsplus.io/api/v1/students
Authorization: Bearer {token-for-presec}
```

**Response (403 Forbidden)**

```json
{
  "success": false,
  "error": {
    "code": "TENANT_MISMATCH",
    "message": "Access denied: Token not valid for this school",
    "details": "Your session is for a different school. Please login again."
  }
}
```

---

## 4. School Onboarding API

### 4.1 Check Subdomain Availability

```http
GET https://api.simsplus.io/v1/onboarding/check-subdomain/{subdomain}
```

**Response (200 OK - Available)**

```json
{
  "success": true,
  "data": {
    "subdomain": "newschool",
    "available": true,
    "suggestion": null
  }
}
```

### 4.2 Register New School

```http
POST https://api.simsplus.io/v1/onboarding/schools
Content-Type: application/json

{
  "subdomain": "newschool",
  "school_name": "New International School",
  "school_type": "international",
  "admin_email": "admin@newschool.edu.gh",
  "admin_first_name": "John",
  "admin_last_name": "Doe",
  "admin_phone": "+233241234567",
  "plan": "professional",
  "billing_cycle": "annual"
}
```

---

## 5. Tenant Management API

### 5.1 Get Current Tenant

```http
GET https://presec.simsplus.io/api/v1/tenant
Authorization: Bearer {token}
```

### 5.2 Update Tenant Branding

```http
PATCH https://presec.simsplus.io/api/v1/tenant/branding
Authorization: Bearer {token}
Content-Type: application/json

{
  "logo_url": "https://cdn.simsplus.io/presec/new-logo.png",
  "primary_color": "#003366",
  "secondary_color": "#FFD700"
}
```

---

## 6. Students API

### 6.1 List Students

```http
GET https://presec.simsplus.io/api/v1/students?status=active&class_id=uuid&page=1&per_page=20
Authorization: Bearer {token}
```

**Query Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `status` | string | `active` | Filter by status |
| `class_id` | uuid | - | Filter by class |
| `gender` | string | - | Filter by gender |
| `q` | string | - | Search by name or student ID |
| `page` | integer | 1 | Page number |
| `per_page` | integer | 20 | Items per page (max 100) |

### 6.2 Create Student

```http
POST https://presec.simsplus.io/api/v1/students
Authorization: Bearer {token}
Content-Type: application/json

{
  "first_name": "Ama",
  "last_name": "Mensah",
  "gender": "female",
  "date_of_birth": "2011-05-20",
  "class_id": "class-uuid",
  "section_id": "section-uuid",
  "admission_date": "2025-01-06",
  "guardians": [
    {
      "first_name": "Kofi",
      "last_name": "Mensah",
      "relationship": "father",
      "phone_primary": "+233241234567",
      "is_primary": true
    }
  ]
}
```

---

## 7. Staff API

### 7.1 List Staff

```http
GET https://presec.simsplus.io/api/v1/staff
Authorization: Bearer {token}
```

### 7.2 Get Staff Departments

```http
GET https://presec.simsplus.io/api/v1/staff/departments
Authorization: Bearer {token}
```

### 7.3 Create Department

```http
POST https://presec.simsplus.io/api/v1/staff/departments
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "Science Department",
  "code": "SCI",
  "head_id": "staff-uuid"
}
```

---

## 8. Attendance API

### 8.1 Mark Attendance

```http
POST https://presec.simsplus.io/api/v1/attendance/mark
Authorization: Bearer {token}
Content-Type: application/json

{
  "class_id": "class-uuid",
  "section_id": "section-uuid",
  "date": "2026-01-06",
  "records": [
    {
      "student_id": "student-1-uuid",
      "status": "present"
    },
    {
      "student_id": "student-2-uuid",
      "status": "absent",
      "remarks": "Sick"
    }
  ]
}
```

### 8.2 Get Attendance Report

```http
GET https://presec.simsplus.io/api/v1/attendance/reports?class_id=uuid&start_date=2026-01-01&end_date=2026-01-31
Authorization: Bearer {token}
```

---

## 9. Exams API

### 9.1 List Exams

```http
GET https://presec.simsplus.io/api/v1/exams?academic_year_id=uuid&term_id=uuid
Authorization: Bearer {token}
```

**Response**

```json
{
  "success": true,
  "data": [
    {
      "id": "exam-uuid",
      "name": "End of Term Examination",
      "exam_type": "end_of_term",
      "academic_year_id": "year-uuid",
      "academic_year_name": "2025/2026",
      "term_id": "term-uuid",
      "term_name": "Term 1",
      "start_date": "2026-03-15",
      "end_date": "2026-03-25",
      "status": "in_progress",
      "subjects_count": 12,
      "classes_count": 8
    }
  ]
}
```

### 9.2 Create Exam

```http
POST https://presec.simsplus.io/api/v1/exams
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "Mid-Term Examination",
  "exam_type": "mid_term",
  "academic_year_id": "year-uuid",
  "term_id": "term-uuid",
  "start_date": "2026-02-10",
  "end_date": "2026-02-15",
  "description": "Mid-term assessment for all classes"
}
```

### 9.3 Add Subjects to Exam

```http
POST https://presec.simsplus.io/api/v1/exams/{exam_id}/subjects
Authorization: Bearer {token}
Content-Type: application/json

{
  "subjects": [
    {
      "subject_id": "subject-uuid",
      "class_id": "class-uuid",
      "max_score": 100,
      "passing_score": 50,
      "grading_scale_id": "scale-uuid",
      "exam_date": "2026-02-10"
    }
  ]
}
```

### 9.4 Enter Exam Scores

```http
POST https://presec.simsplus.io/api/v1/exams/{exam_id}/subjects/{subject_id}/scores
Authorization: Bearer {token}
Content-Type: application/json

{
  "class_id": "class-uuid",
  "section_id": "section-uuid",
  "scores": [
    {
      "student_id": "student-1-uuid",
      "score": 85,
      "remarks": "Excellent performance"
    },
    {
      "student_id": "student-2-uuid",
      "score": 72
    }
  ]
}
```

**Response**

```json
{
  "success": true,
  "data": {
    "saved": 25,
    "updated": 0,
    "errors": []
  }
}
```

### 9.5 Get Exam Scores

```http
GET https://presec.simsplus.io/api/v1/exams/{exam_id}/subjects/{subject_id}/scores?class_id=uuid&section_id=uuid
Authorization: Bearer {token}
```

### 9.6 Continuous Assessment (CA)

**List CA Records**

```http
GET https://presec.simsplus.io/api/v1/exams/ca?term_id=uuid&class_id=uuid&subject_id=uuid
Authorization: Bearer {token}
```

**Enter CA Scores**

```http
POST https://presec.simsplus.io/api/v1/exams/ca
Authorization: Bearer {token}
Content-Type: application/json

{
  "term_id": "term-uuid",
  "class_id": "class-uuid",
  "section_id": "section-uuid",
  "subject_id": "subject-uuid",
  "assessment_type": "class_test",
  "assessment_name": "Class Test 1",
  "max_score": 20,
  "date": "2026-01-15",
  "scores": [
    {
      "student_id": "student-uuid",
      "score": 18
    }
  ]
}
```

### 9.7 Report Cards

**Generate Report Cards**

```http
POST https://presec.simsplus.io/api/v1/exams/{exam_id}/report-cards/generate
Authorization: Bearer {token}
Content-Type: application/json

{
  "class_id": "class-uuid",
  "section_id": "section-uuid",
  "include_ca": true,
  "ca_weight": 30,
  "exam_weight": 70
}
```

**Response**

```json
{
  "success": true,
  "data": {
    "generated": 45,
    "updated": 0,
    "class_name": "JHS 2A"
  }
}
```

**Get Student Report Card**

```http
GET https://presec.simsplus.io/api/v1/exams/{exam_id}/report-cards/{student_id}
Authorization: Bearer {token}
```

**Download Report Card PDF**

```http
GET https://presec.simsplus.io/api/v1/exams/{exam_id}/report-cards/{student_id}/pdf
Authorization: Bearer {token}
```

### 9.8 Exam Analytics

```http
GET https://presec.simsplus.io/api/v1/exams/{exam_id}/analytics?class_id=uuid
Authorization: Bearer {token}
```

**Response**

```json
{
  "success": true,
  "data": {
    "class_average": 68.5,
    "highest_score": 95,
    "lowest_score": 32,
    "pass_rate": 78.5,
    "grade_distribution": {
      "A": 12,
      "B": 25,
      "C": 18,
      "D": 8,
      "F": 5
    },
    "subject_performance": [
      {
        "subject": "Mathematics",
        "average": 72.3,
        "pass_rate": 85
      }
    ]
  }
}
```

---

## 10. Calendar API

### 10.1 List School Holidays

```http
GET https://presec.simsplus.io/api/v1/academic/holidays?academic_year_id=uuid
Authorization: Bearer {token}
```

**Response**

```json
{
  "success": true,
  "data": [
    {
      "id": "holiday-uuid",
      "name": "Independence Day",
      "date": "2026-03-06",
      "end_date": null,
      "type": "public_holiday",
      "description": "Ghana Independence Day",
      "is_recurring": true
    },
    {
      "id": "holiday-uuid-2",
      "name": "Mid-Term Break",
      "date": "2026-02-15",
      "end_date": "2026-02-21",
      "type": "school_break",
      "description": "Term 1 mid-term break"
    }
  ]
}
```

### 10.2 Create Holiday/Event

```http
POST https://presec.simsplus.io/api/v1/academic/holidays
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "Sports Day",
  "date": "2026-02-28",
  "end_date": null,
  "type": "school_event",
  "description": "Annual inter-house sports competition",
  "academic_year_id": "year-uuid"
}
```

**Event Types:**
- `public_holiday` - National/public holidays
- `school_break` - Term breaks, vacations
- `school_event` - School activities, events
- `exam_period` - Examination periods
- `other` - Other calendar events

### 10.3 Update Holiday/Event

```http
PUT https://presec.simsplus.io/api/v1/academic/holidays/{holiday_id}
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "Sports Day",
  "date": "2026-03-01",
  "description": "Rescheduled annual sports competition"
}
```

### 10.4 Delete Holiday/Event

```http
DELETE https://presec.simsplus.io/api/v1/academic/holidays/{holiday_id}
Authorization: Bearer {token}
```

### 10.5 Get School Days Count

```http
GET https://presec.simsplus.io/api/v1/academic/terms/{term_id}/school-days
Authorization: Bearer {token}
```

**Response**

```json
{
  "success": true,
  "data": {
    "term_id": "term-uuid",
    "term_name": "Term 1",
    "start_date": "2026-01-06",
    "end_date": "2026-04-05",
    "total_days": 90,
    "weekend_days": 26,
    "holidays": 5,
    "school_days": 59,
    "days_elapsed": 15,
    "days_remaining": 44
  }
}
```

---

## 11. Timetable API

### 11.1 Get Class Timetable

```http
GET https://presec.simsplus.io/api/v1/timetable/classes/{class_id}?section_id=uuid
Authorization: Bearer {token}
```

**Response**

```json
{
  "success": true,
  "data": {
    "class_id": "class-uuid",
    "class_name": "JHS 2",
    "section_id": "section-uuid",
    "section_name": "A",
    "periods": [
      {
        "id": "period-uuid",
        "day": "monday",
        "start_time": "08:00",
        "end_time": "08:45",
        "subject_id": "subject-uuid",
        "subject_name": "Mathematics",
        "teacher_id": "teacher-uuid",
        "teacher_name": "Mr. Asante",
        "room": "Room 101"
      }
    ]
  }
}
```

### 11.2 Create/Update Timetable

```http
POST https://presec.simsplus.io/api/v1/timetable/classes/{class_id}
Authorization: Bearer {token}
Content-Type: application/json

{
  "section_id": "section-uuid",
  "term_id": "term-uuid",
  "periods": [
    {
      "day": "monday",
      "start_time": "08:00",
      "end_time": "08:45",
      "subject_id": "subject-uuid",
      "teacher_id": "teacher-uuid",
      "room": "Room 101"
    },
    {
      "day": "monday",
      "start_time": "08:45",
      "end_time": "09:30",
      "subject_id": "subject-uuid-2",
      "teacher_id": "teacher-uuid-2",
      "room": "Room 101"
    }
  ]
}
```

### 11.3 Get Teacher Timetable

```http
GET https://presec.simsplus.io/api/v1/timetable/teachers/{teacher_id}?term_id=uuid
Authorization: Bearer {token}
```

### 11.4 Delete Period

```http
DELETE https://presec.simsplus.io/api/v1/timetable/periods/{period_id}
Authorization: Bearer {token}
```

### 11.5 Check Conflicts

```http
POST https://presec.simsplus.io/api/v1/timetable/check-conflicts
Authorization: Bearer {token}
Content-Type: application/json

{
  "teacher_id": "teacher-uuid",
  "day": "monday",
  "start_time": "08:00",
  "end_time": "08:45",
  "exclude_period_id": "period-uuid"
}
```

**Response**

```json
{
  "success": true,
  "data": {
    "has_conflict": true,
    "conflicts": [
      {
        "type": "teacher",
        "message": "Teacher already assigned to JHS 1A at this time",
        "period_id": "conflicting-period-uuid"
      }
    ]
  }
}
```

---

## 12. Preschool API

The Preschool module provides APIs for early childhood education management, including developmental assessments, observations, and daily activity tracking.

> **Note:** For complete API documentation, see [PRESCHOOL_ARCHITECTURE.md](./PRESCHOOL_ARCHITECTURE.md)

### 12.1 Developmental Domains

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/preschool/domains` | List developmental domains |
| GET | `/preschool/domains/{id}/milestones` | Get milestones for domain |

### 12.2 Observations

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/preschool/observations` | List observations |
| POST | `/preschool/observations` | Create observation |
| GET | `/preschool/observations/student/{id}` | Get student observations |

### 12.3 Daily Activity Logs

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/preschool/daily-logs` | List daily logs |
| POST | `/preschool/daily-logs` | Create/update daily log |
| GET | `/preschool/daily-logs/student/{id}` | Get student daily logs |

### 12.4 Assessments

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/preschool/assessments` | List assessments |
| POST | `/preschool/assessments` | Create assessment |
| GET | `/preschool/assessments/student/{id}` | Get student assessments |

### 12.5 Progress Reports

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/preschool/reports/student/{id}` | Get student progress report |
| GET | `/preschool/reports/student/{id}/pdf` | Download progress report PDF |

---

## 13. Finance API

The Finance module provides comprehensive fee management, invoicing, payment recording, and scholarship management.

### 13.1 Fee Types

**List Fee Types**

```http
GET https://presec.simsplus.io/api/v1/finance/fee-types
Authorization: Bearer {token}
```

**Create Fee Type**

```http
POST https://presec.simsplus.io/api/v1/finance/fee-types
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "Tuition Fee",
  "description": "Main tuition fee",
  "category": "tuition",
  "is_active": true
}
```

**Fee Type Categories:** `tuition`, `examination`, `facilities`, `activities`, `other`

### 13.2 Fee Structures

**List Fee Structures**

```http
GET https://presec.simsplus.io/api/v1/finance/fee-structures?academic_year_id=uuid&term_id=uuid
Authorization: Bearer {token}
```

**Create Fee Structure**

```http
POST https://presec.simsplus.io/api/v1/finance/fee-structures
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "Term 1 Fees - JHS 1",
  "description": "Fee structure for JHS 1 students",
  "academic_year_id": "year-uuid",
  "term_id": "term-uuid",
  "class_id": "class-uuid",
  "level_category": "jhs",
  "student_type": "all",
  "items": [
    {
      "name": "Tuition",
      "amount": 500.00,
      "fee_type_id": "fee-type-uuid",
      "is_optional": false
    },
    {
      "name": "Exam Fee",
      "amount": 50.00,
      "fee_type_id": "fee-type-uuid",
      "is_optional": false
    }
  ]
}
```

**Level Categories:** `preschool`, `primary`, `jhs`, `shs`
**Student Types:** `all`, `boarding`, `day`

### 13.3 Invoices

**List Invoices**

```http
GET https://presec.simsplus.io/api/v1/finance/invoices?status=issued&academic_year_id=uuid&q=search
Authorization: Bearer {token}
```

**Create Single Invoice**

```http
POST https://presec.simsplus.io/api/v1/finance/invoices
Authorization: Bearer {token}
Content-Type: application/json

{
  "student_id": "student-uuid",
  "fee_structure_id": "fee-structure-uuid",
  "academic_year_id": "year-uuid",
  "term_id": "term-uuid",
  "due_date": "2026-02-15",
  "discount_amount": 0,
  "notes": "Term 1 school fees"
}
```

**Bulk Generate Invoices**

```http
POST https://presec.simsplus.io/api/v1/finance/invoices/bulk-generate
Authorization: Bearer {token}
Content-Type: application/json

{
  "fee_structure_id": "fee-structure-uuid",
  "academic_year_id": "year-uuid",
  "term_id": "term-uuid",
  "class_id": "class-uuid",
  "section_id": "section-uuid",
  "due_date": "2026-02-15",
  "issue_immediately": false
}
```

**Response**

```json
{
  "success": true,
  "data": {
    "created": 45,
    "skipped": 5,
    "failed": 0,
    "errors": [],
    "invoice_ids": ["uuid1", "uuid2", "..."]
  }
}
```

**Issue Invoice**

```http
POST https://presec.simsplus.io/api/v1/finance/invoices/{invoice_id}/issue
Authorization: Bearer {token}
Content-Type: application/json

{
  "issue_date": "2026-01-15"
}
```

**Cancel Invoice**

```http
POST https://presec.simsplus.io/api/v1/finance/invoices/{invoice_id}/cancel
Authorization: Bearer {token}
Content-Type: application/json

{
  "reason": "Duplicate invoice created"
}
```

**Sync Invoices with Fee Structure**

```http
POST https://presec.simsplus.io/api/v1/finance/invoices/sync
Authorization: Bearer {token}
Content-Type: application/json

{
  "fee_structure_id": "fee-structure-uuid",
  "academic_year_id": "year-uuid",
  "term_id": "term-uuid"
}
```

**Response**

```json
{
  "success": true,
  "data": {
    "updated": 30,
    "skipped": 15,
    "failed": 0,
    "errors": [],
    "skipped_reasons": {
      "issued": 5,
      "partial": 8,
      "paid": 2
    }
  }
}
```

**Email Invoice**

```http
POST https://presec.simsplus.io/api/v1/finance/invoices/{invoice_id}/email
Authorization: Bearer {token}
Content-Type: application/json

{
  "email": "parent@email.com",
  "recipient_name": "Mr. Mensah",
  "cc_emails": ["accountant@school.edu", "headmaster@school.edu"]
}
```

**Invoice Statuses:** `draft`, `issued`, `partial`, `paid`, `overdue`, `cancelled`

### 13.4 Payments

**List Payments**

```http
GET https://presec.simsplus.io/api/v1/finance/payments?payment_method=cash&start_date=2026-01-01
Authorization: Bearer {token}
```

**Record Payment**

```http
POST https://presec.simsplus.io/api/v1/finance/payments
Authorization: Bearer {token}
Content-Type: application/json

{
  "invoice_id": "invoice-uuid",
  "student_id": "student-uuid",
  "amount": 500.00,
  "payment_method": "cash",
  "payment_date": "2026-01-15",
  "payer_name": "Mr. Kofi Mensah",
  "payer_phone": "+233241234567",
  "notes": "Partial payment for Term 1 fees"
}
```

**Payment Methods:** `cash`, `momo_mtn`, `momo_vodafone`, `momo_airteltigo`, `bank_transfer`, `cheque`, `card`, `other`

**Void Payment**

```http
POST https://presec.simsplus.io/api/v1/finance/payments/{payment_id}/void
Authorization: Bearer {token}
Content-Type: application/json

{
  "reason": "Payment recorded in error"
}
```

**Get Payment Receipt**

```http
GET https://presec.simsplus.io/api/v1/finance/payments/{payment_id}/receipt
Authorization: Bearer {token}
```

### 13.5 Scholarships

**List Scholarships**

```http
GET https://presec.simsplus.io/api/v1/finance/scholarships?is_active=true
Authorization: Bearer {token}
```

**Create Scholarship**

```http
POST https://presec.simsplus.io/api/v1/finance/scholarships
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "Academic Excellence Award",
  "code": "AEA-2026",
  "description": "For students with outstanding academic performance",
  "scholarship_type": "merit",
  "coverage_type": "percentage",
  "coverage_value": 50.00,
  "max_recipients": 10,
  "academic_year_id": "year-uuid",
  "eligibility_criteria": {
    "min_average": 80
  }
}
```

**Scholarship Types:** `full`, `partial`, `merit`, `need_based`, `athletic`, `special`
**Coverage Types:** `percentage`, `fixed_amount`

**Award Scholarship to Student**

```http
POST https://presec.simsplus.io/api/v1/finance/scholarships/{scholarship_id}/award
Authorization: Bearer {token}
Content-Type: application/json

{
  "student_id": "student-uuid",
  "effective_from": "2026-01-01",
  "effective_to": "2026-12-31",
  "coverage_override": null,
  "notes": "Awarded for outstanding performance"
}
```

**Bulk Award Scholarship**

```http
POST https://presec.simsplus.io/api/v1/finance/scholarships/{scholarship_id}/award-bulk
Authorization: Bearer {token}
Content-Type: application/json

{
  "student_ids": ["student-1-uuid", "student-2-uuid"],
  "effective_from": "2026-01-01",
  "effective_to": "2026-12-31",
  "notes": "Merit scholarship recipients"
}
```

**Response**

```json
{
  "success": true,
  "data": {
    "awarded": 2,
    "skipped": 0,
    "failed": 0,
    "errors": [],
    "student_scholarship_ids": ["uuid1", "uuid2"]
  }
}
```

**Revoke Scholarship**

```http
POST https://presec.simsplus.io/api/v1/finance/scholarships/{scholarship_id}/recipients/{student_scholarship_id}/revoke
Authorization: Bearer {token}
Content-Type: application/json

{
  "reason": "Student no longer meets eligibility criteria"
}
```

**Get Scholarship Recipients**

```http
GET https://presec.simsplus.io/api/v1/finance/scholarships/{scholarship_id}/recipients
Authorization: Bearer {token}
```

**Get Student's Scholarships**

```http
GET https://presec.simsplus.io/api/v1/finance/scholarships/student/{student_id}
Authorization: Bearer {token}
```

### 13.6 Credit Notes

Credit notes handle overpayments, fee reductions, and error corrections. They follow a workflow: draft → issued → applied/refunded/cancelled.

**List Credit Notes**

```http
GET https://presec.simsplus.io/api/v1/finance/credit-notes?status=issued&q=search
Authorization: Bearer {token}
```

**Query Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `status` | string | - | Filter by status (draft, issued, applied, refunded, cancelled) |
| `type` | string | - | Filter by type (overpayment, fee_reduction, error_correction) |
| `q` | string | - | Search by credit note number or student name |
| `page` | integer | 1 | Page number |
| `per_page` | integer | 20 | Items per page |

**Create Credit Note**

```http
POST https://presec.simsplus.io/api/v1/finance/credit-notes
Authorization: Bearer {token}
Content-Type: application/json

{
  "student_id": "student-uuid",
  "invoice_id": "invoice-uuid",
  "type": "overpayment",
  "amount": 150.00,
  "reason": "Overpayment on Term 1 fees"
}
```

**Credit Note Types:** `overpayment`, `fee_reduction`, `error_correction`

**Issue Credit Note**

```http
POST https://presec.simsplus.io/api/v1/finance/credit-notes/{credit_note_id}/issue
Authorization: Bearer {token}
```

**Apply Credit Note to Invoice**

```http
POST https://presec.simsplus.io/api/v1/finance/credit-notes/{credit_note_id}/apply
Authorization: Bearer {token}
Content-Type: application/json

{
  "invoice_id": "invoice-uuid",
  "amount": 150.00
}
```

**Response**

```json
{
  "success": true,
  "data": {
    "credit_note_id": "credit-note-uuid",
    "invoice_id": "invoice-uuid",
    "amount_applied": 150.00,
    "credit_note_remaining": 0.00,
    "invoice_new_balance": 350.00
  }
}
```

**Refund Credit Note**

```http
POST https://presec.simsplus.io/api/v1/finance/credit-notes/{credit_note_id}/refund
Authorization: Bearer {token}
Content-Type: application/json

{
  "refund_method": "cash",
  "refund_reference": "REF-001",
  "refunded_to": "Mr. Kofi Mensah"
}
```

**Cancel Credit Note**

```http
POST https://presec.simsplus.io/api/v1/finance/credit-notes/{credit_note_id}/cancel
Authorization: Bearer {token}
Content-Type: application/json

{
  "reason": "Created in error"
}
```

**Get Student Credit Balance**

```http
GET https://presec.simsplus.io/api/v1/finance/credit-notes/student/{student_id}/balance
Authorization: Bearer {token}
```

**Response**

```json
{
  "success": true,
  "data": {
    "student_id": "student-uuid",
    "available_credit": 200.00,
    "total_issued": 500.00,
    "total_applied": 250.00,
    "total_refunded": 50.00
  }
}
```

**Credit Note Statuses:** `draft`, `issued`, `applied`, `partially_applied`, `refunded`, `cancelled`

> **Note:** When a credit note is issued, the system can auto-apply it to the student's oldest unpaid invoice if configured.

### 13.7 Finance Audit Log

All finance transactions are logged to an immutable audit trail.

**Get Audit Log**

```http
GET https://presec.simsplus.io/api/v1/finance/audit-log?entity_type=invoice&entity_id=uuid
Authorization: Bearer {token}
```

**Response**

```json
{
  "success": true,
  "data": [
    {
      "id": "log-uuid",
      "entity_type": "invoice",
      "entity_id": "invoice-uuid",
      "action": "status_change",
      "old_values": {"status": "draft"},
      "new_values": {"status": "issued"},
      "performed_by": "user-uuid",
      "performed_by_name": "Admin User",
      "performed_at": "2026-01-15T10:30:00Z",
      "ip_address": "192.168.1.1"
    }
  ]
}
```

**Entity Types:** `invoice`, `payment`, `credit_note`, `scholarship`, `fee_structure`

### 13.8 Finance Dashboard

**Get Dashboard Statistics**

```http
GET https://presec.simsplus.io/api/v1/finance/dashboard?academic_year_id=uuid&term_id=uuid
Authorization: Bearer {token}
```

**Response**

```json
{
  "success": true,
  "data": {
    "stats": {
      "expected_revenue": 125000.00,
      "collected_revenue": 45000.00,
      "outstanding_balance": 80000.00,
      "total_invoices": 200,
      "paid_invoices": 50,
      "partial_invoices": 30,
      "overdue_invoices": 25,
      "total_payments": 85,
      "total_scholarships_value": 15000.00,
      "scholarship_recipients": 12
    },
    "recent_payments": [
      {
        "id": "payment-uuid",
        "receipt_number": "RCP-2026-001",
        "student_name": "Kofi Asante",
        "amount": 500.00,
        "payment_method": "cash",
        "payment_date": "2026-01-15"
      }
    ],
    "outstanding_by_class": [
      {
        "class_id": "class-uuid",
        "class_name": "JHS 1",
        "student_count": 45,
        "total_outstanding": 15000.00
      }
    ]
  }
}
```

### 13.9 Mobile Money Payment (Future)

**Initiate Mobile Money Payment**

```http
POST https://presec.simsplus.io/api/v1/finance/payments/momo/initiate
Authorization: Bearer {token}
Content-Type: application/json

{
  "student_id": "student-uuid",
  "invoice_id": "invoice-uuid",
  "amount": 500.00,
  "provider": "mtn",
  "phone_number": "0241234567",
  "payer_name": "Kofi Asante"
}
```

**Response**

```json
{
  "success": true,
  "data": {
    "transaction_id": "txn-uuid",
    "reference": "SIMS-PAY-123456",
    "status": "pending",
    "provider": "mtn",
    "amount": 500.00,
    "currency": "GHS",
    "message": "Payment request sent. Please approve on your phone.",
    "expires_at": "2026-01-06T12:30:00Z"
  }
}
```

**Payment Webhook (MoMo Callback)**

```http
POST https://api.simsplus.io/v1/webhooks/momo/mtn
X-Signature: {hmac-signature}
Content-Type: application/json

{
  "reference": "SIMS-PAY-123456",
  "status": "SUCCESSFUL",
  "amount": 500.00,
  "currency": "GHS",
  "payer": "233241234567",
  "transaction_id": "mtn-txn-id",
  "timestamp": "2026-01-06T12:25:00Z"
}
```

---

## 14. Error Handling

### 14.1 Error Response Format

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable message",
    "details": { ... },
    "request_id": "req-uuid"
  }
}
```

### 14.2 Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `TENANT_NOT_FOUND` | 404 | Subdomain doesn't exist |
| `TENANT_SUSPENDED` | 403 | School account is suspended |
| `TENANT_MISMATCH` | 403 | Token tenant doesn't match request |
| `TENANT_LIMIT_EXCEEDED` | 403 | Resource limit reached |
| `SUBSCRIPTION_EXPIRED` | 403 | Subscription has expired |
| `INVALID_SUBDOMAIN` | 400 | Subdomain format invalid |
| `SUBDOMAIN_TAKEN` | 409 | Subdomain already registered |
| `SUBDOMAIN_RESERVED` | 400 | Subdomain is reserved |
| `UNAUTHORIZED` | 401 | Invalid or missing token |
| `FORBIDDEN` | 403 | Insufficient permissions |
| `NOT_FOUND` | 404 | Resource not found |
| `VALIDATION_ERROR` | 422 | Request validation failed |
| `RATE_LIMITED` | 429 | Too many requests |
| `SCORE_VALIDATION_ERROR` | 422 | Score exceeds maximum |
| `EXAM_NOT_FOUND` | 404 | Exam does not exist |
| `TIMETABLE_CONFLICT` | 409 | Schedule conflict detected |
| `INVOICE_NOT_DRAFT` | 400 | Invoice cannot be modified (not in draft status) |
| `CREDIT_NOTE_INVALID_STATUS` | 400 | Credit note action not allowed in current status |
| `INSUFFICIENT_CREDIT` | 400 | Credit note balance insufficient for operation |

### 14.3 Rate Limiting

| Endpoint Type | Limit | Window |
|--------------|-------|--------|
| Authentication | 5 requests | per minute per IP |
| General API | 100 requests | per minute per user |
| Bulk Operations | 10 requests | per minute per user |
| File Upload | 20 requests | per minute per user |
| Report Generation | 5 requests | per minute per user |

**Rate Limit Headers**

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1704067260
```

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | January 2026 | Harry McNinson | Initial version |
| 2.0 | January 2026 | Harry McNinson | Added subdomain multi-tenancy, tenant context, onboarding API |
| 2.1 | January 2026 | Harry McNinson | Added Exams API, Calendar API, Timetable API, updated Preschool API |
| 2.2 | January 2026 | Harry McNinson | Added complete Finance API: fee types, fee structures, invoices, payments, scholarships, dashboard |
| 2.3 | January 2026 | Harry McNinson | Added Credit Notes API, Finance Audit Log API, additional error codes |
