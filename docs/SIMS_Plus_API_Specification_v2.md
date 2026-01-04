# SIMS Plus (School Information Management System Plus) - API Specification

**Version:** 2.0  
**Date:** January 2026  
**Author:** Harry McNinson  
**Status:** Updated with Subdomain Multi-Tenancy

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
9. [Finance API](#9-finance-api)
10. [Error Handling](#10-error-handling)

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

### 2.3 Internal API (No Auth Required)

For server-to-server communication:

```
POST https://api.simsplus.io/internal/tenants/validate/{subdomain}
Header: X-Internal-Key: {internal_api_key}

Response:
{
  "valid": true,
  "tenant_id": "uuid",
  "status": "active"
}
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

**Response (200 OK - Not Available)**

```json
{
  "success": true,
  "data": {
    "subdomain": "presec",
    "available": false,
    "suggestion": "presec-legon"
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

**Response (201 Created)**

```json
{
  "success": true,
  "data": {
    "tenant_id": "new-tenant-uuid",
    "subdomain": "newschool",
    "portal_url": "https://newschool.simsplus.io",
    "status": "trial",
    "trial_ends_at": "2026-02-15T00:00:00Z",
    "admin_user": {
      "id": "admin-user-uuid",
      "email": "admin@newschool.edu.gh",
      "temporary_password_sent": true
    },
    "next_steps": [
      "Check email for login credentials",
      "Login at https://newschool.simsplus.io",
      "Complete school profile setup",
      "Add academic year and terms",
      "Import or add students"
    ]
  }
}
```

### 4.3 Subdomain Validation Rules

| Rule | Valid | Invalid |
|------|-------|---------|
| Length | 4-63 characters | `abc`, `a` |
| Characters | `a-z`, `0-9`, `-` | `NewSchool`, `new_school` |
| Start/End | Letter or number | `-school`, `school-` |
| Reserved | Not in reserved list | `www`, `app`, `api`, `admin` |

**Reserved Subdomains:**

```json
[
  "www", "app", "api", "admin", "mail", "ftp", "status",
  "blog", "help", "support", "docs", "cdn", "assets",
  "staging", "dev", "test", "demo", "sandbox"
]
```

---

## 5. Tenant Management API

### 5.1 Get Current Tenant

```http
GET https://presec.simsplus.io/api/v1/tenant
Authorization: Bearer {token}
```

**Response**

```json
{
  "success": true,
  "data": {
    "id": "tenant-uuid",
    "subdomain": "presec",
    "name": "Presbyterian Boys' Secondary School",
    "type": "single_school",
    "status": "active",
    "logo_url": "https://cdn.simsplus.io/presec/logo.png",
    "primary_color": "#1B4F72",
    "subscription": {
      "plan": "professional",
      "status": "active",
      "current_period_end": "2026-12-31T23:59:59Z",
      "limits": {
        "max_students": 2000,
        "max_staff": 200,
        "storage_gb": 50,
        "sms_monthly": 500
      },
      "usage": {
        "students": 1234,
        "staff": 48,
        "storage_gb": 12.5,
        "sms_this_month": 150
      }
    },
    "features": {
      "boarding": true,
      "transport": true,
      "multi_curriculum": false,
      "api_access": true,
      "custom_domain": false
    }
  }
}
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

### 5.3 Get Tenant Schools (For School Chains)

```http
GET https://chainname.simsplus.io/api/v1/tenant/schools
Authorization: Bearer {token}
```

**Response**

```json
{
  "success": true,
  "data": [
    {
      "id": "school-1-uuid",
      "name": "Chain School - Accra Campus",
      "code": "CSA",
      "student_count": 500,
      "staff_count": 30
    },
    {
      "id": "school-2-uuid", 
      "name": "Chain School - Kumasi Campus",
      "code": "CSK",
      "student_count": 450,
      "staff_count": 28
    }
  ]
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
| `status` | string | `active` | Filter by status: active, inactive, withdrawn, graduated |
| `class_id` | uuid | - | Filter by class |
| `gender` | string | - | Filter by gender: male, female |
| `boarding` | boolean | - | Filter by boarding status |
| `q` | string | - | Search by name or student ID |
| `page` | integer | 1 | Page number |
| `per_page` | integer | 20 | Items per page (max 100) |
| `sort` | string | `last_name` | Sort field |
| `order` | string | `asc` | Sort order: asc, desc |

**Response**

```json
{
  "success": true,
  "data": [
    {
      "id": "student-uuid",
      "student_id": "STU-2025-001",
      "first_name": "Kwame",
      "last_name": "Asante",
      "other_names": "Kofi",
      "gender": "male",
      "date_of_birth": "2010-03-15",
      "photo_url": "https://cdn.simsplus.io/presec/students/kwame.jpg",
      "current_class": {
        "id": "class-uuid",
        "name": "JHS 2",
        "section": "A"
      },
      "status": "active",
      "is_boarding": true,
      "admission_date": "2020-09-01"
    }
  ],
  "meta": {
    "page": 1,
    "per_page": 20,
    "total": 1234,
    "total_pages": 62
  }
}
```

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
  "is_boarding": false,
  "guardians": [
    {
      "first_name": "Kofi",
      "last_name": "Mensah",
      "relationship": "father",
      "phone_primary": "+233241234567",
      "email": "kofi.mensah@email.com",
      "is_primary": true,
      "is_emergency_contact": true
    }
  ]
}
```

**Response (201 Created)**

```json
{
  "success": true,
  "data": {
    "id": "new-student-uuid",
    "student_id": "STU-2025-002",
    "first_name": "Ama",
    "last_name": "Mensah",
    "portal_url": "https://presec.simsplus.io/students/new-student-uuid"
  }
}
```

### 6.3 Tenant Limit Exceeded Error

```http
POST https://presec.simsplus.io/api/v1/students
```

**Response (403 Forbidden)**

```json
{
  "success": false,
  "error": {
    "code": "TENANT_LIMIT_EXCEEDED",
    "message": "Student limit reached",
    "details": {
      "current": 2000,
      "limit": 2000,
      "plan": "professional"
    },
    "upgrade_url": "https://presec.simsplus.io/settings/billing/upgrade"
  }
}
```

---

## 7. Staff API

### 7.1 List Staff

```http
GET https://presec.simsplus.io/api/v1/staff
Authorization: Bearer {token}
```

### 7.2 Invite Staff Member

```http
POST https://presec.simsplus.io/api/v1/staff/invite
Authorization: Bearer {token}
Content-Type: application/json

{
  "email": "new.teacher@email.com",
  "first_name": "Akua",
  "last_name": "Darko",
  "role": "teacher",
  "department": "Science",
  "send_invitation": true
}
```

**Response**

```json
{
  "success": true,
  "data": {
    "staff_id": "staff-uuid",
    "invitation_sent": true,
    "invitation_expires": "2026-01-13T00:00:00Z",
    "login_url": "https://presec.simsplus.io/login"
  }
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
    },
    {
      "student_id": "student-3-uuid",
      "status": "late",
      "arrival_time": "08:15"
    }
  ]
}
```

### 8.2 Offline Sync

For offline attendance that needs to sync:

```http
POST https://presec.simsplus.io/api/v1/attendance/sync
Authorization: Bearer {token}
Content-Type: application/json

{
  "records": [
    {
      "local_id": "local-uuid-1",
      "class_id": "class-uuid",
      "date": "2026-01-05",
      "student_id": "student-uuid",
      "status": "present",
      "marked_at": "2026-01-05T08:30:00Z",
      "marked_offline": true
    }
  ]
}
```

**Response**

```json
{
  "success": true,
  "data": {
    "synced": 45,
    "failed": 2,
    "conflicts": [
      {
        "local_id": "local-uuid-x",
        "error": "Record already exists for this date",
        "resolution": "skipped"
      }
    ]
  }
}
```

---

## 9. Finance API

### 9.1 Initiate Mobile Money Payment

```http
POST https://presec.simsplus.io/api/v1/payments/momo/initiate
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

### 9.2 Payment Webhook (MoMo Callback)

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

## 10. Error Handling

### 10.1 Error Response Format

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

### 10.2 Error Codes

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

### 10.3 Rate Limiting

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
