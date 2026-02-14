# SIMS Plus - Project Guide

## Project Overview

**SIMS Plus** (School Information Management System Plus) is a comprehensive multi-tenant SaaS platform designed for schools. It supports educational institutions from preschools to Senior High Schools (SHS), covering both public and private sectors.

**Author:** Harry McNinson
**Version:** 2.2
**Date:** January 2026

## Quick Reference

| Aspect | Details |
|--------|---------|
| **Project Type** | Multi-tenant SaaS School Management System |
| **Target Market** | Schools (Preschool, Primary, JHS, SHS) |
| **Multi-Tenancy** | Subdomain-based (`{school}.simsplus.io`) |
| **Primary Language** | Python (Backend), TypeScript (Frontend) |
| **Backend Framework** | FastAPI |
| **Frontend Framework** | Next.js 16 with React 19 |
| **Database** | PostgreSQL 16 with Row-Level Security |
| **API Style** | REST (OpenAPI 3.1) |
| **Deployment** | AWS (EKS/Kubernetes) |

## Technology Stack

### Backend
- **Runtime:** Python 3.12
- **Framework:** FastAPI
- **ORM:** SQLAlchemy 2.0 (async)
- **Migrations:** Alembic
- **Validation:** Pydantic v2
- **Authentication:** JWT with refresh token rotation
- **Password Hashing:** Argon2id
- **Task Queue:** Celery + Redis
- **PDF Generation:** WeasyPrint
- **Excel Export:** openpyxl

### Frontend
- **Framework:** Next.js 16 (App Router, Turbopack)
- **React:** React 19 with Server Components
- **Language:** TypeScript 5.x
- **Styling:** Tailwind CSS v4 (OKLCH colors)
- **UI Components:** Shadcn/ui (New York style)
- **Data Fetching:** Server Actions
- **Forms:** React Hook Form + Zod
- **Charts:** Recharts
- **Data Tables:** TanStack Table

### Infrastructure
- **Cloud Provider:** AWS
- **Container Orchestration:** Kubernetes (EKS)
- **Database:** RDS PostgreSQL 16
- **Cache:** ElastiCache Redis 7
- **File Storage:** S3
- **CDN:** CloudFront
- **CI/CD:** GitHub Actions
- **IaC:** Terraform
- **Monitoring:** Prometheus + Grafana
- **Logging:** Loki
- **Error Tracking:** Sentry

### Mobile (Phase 4)
- **Framework:** React Native
- **Offline Storage:** WatermelonDB
- **Push Notifications:** Firebase Cloud Messaging

---

## Multi-Tenant Architecture

### Subdomain Strategy

Each school gets a unique subdomain:
```
https://{school-code}.simsplus.io
```

**Examples:**
- `https://presec.simsplus.io` - Presbyterian Boys' Secondary School
- `https://achimota.simsplus.io` - Achimota School
- `https://wesleyg.simsplus.io` - Wesley Girls' High School

### Shared Infrastructure

**All schools share ONE infrastructure:**

```
┌─────────────────────────────────────────────────────────────────┐
│   presec.simsplus.io    achimota.simsplus.io   etc...          │
│              │                    │                             │
│              └────────────────────┴────────────────┐            │
│                                                    │            │
│                              ┌─────────────────────▼──────────┐ │
│                              │     ONE Application Cluster    │ │
│                              └─────────────────────┬──────────┘ │
│                                                    │            │
│                              ┌─────────────────────▼──────────┐ │
│                              │     ONE PostgreSQL Database    │ │
│                              │   (Data isolated by tenant_id) │ │
│                              └────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Data Isolation

- **PostgreSQL Row-Level Security (RLS)** enforces tenant isolation
- Every tenant-scoped table has a `tenant_id` column
- Database automatically filters queries by current tenant
- Cross-tenant access is **impossible** at the database level

### Request Flow

1. User visits `presec.simsplus.io`
2. DNS wildcard resolves to application server
3. Application extracts subdomain from URL
4. Tenant lookup: `SELECT * FROM tenants WHERE subdomain = 'presec'`
5. Validate tenant status (active, not suspended)
6. Set database context: `SET app.current_tenant_id = 'uuid'`
7. All subsequent queries auto-filtered by tenant

---

## API Reference

### Base URLs

| Environment | URL Pattern |
|-------------|-------------|
| Production (School) | `https://{subdomain}.simsplus.io/api/v1` |
| Production (Central) | `https://api.simsplus.io/v1` (requires `X-Subdomain` header) |
| Staging | `https://api.staging.simsplus.io/v1` |
| Development | `http://localhost:8000/api/v1` |

### Authentication

- **JWT Bearer tokens** (15-minute expiry)
- **Refresh tokens** (7-day expiry, HttpOnly cookie)
- **Token contains:** user_id, tenant_id, tenant_subdomain, roles, permissions
- **Cross-tenant tokens are rejected**

### JWT Structure

```json
{
  "sub": "user-uuid",
  "email": "teacher@presec.edu.gh",
  "tenant_id": "tenant-uuid",
  "tenant_subdomain": "presec",
  "school_id": "school-uuid",
  "roles": ["teacher"],
  "permissions": ["students.read", "attendance.mark"],
  "iat": 1704067200,
  "exp": 1704068100
}
```

### Key Endpoints

| Module | Base Path | Description | Status |
|--------|-----------|-------------|--------|
| Auth | `/auth` | Login, register, refresh, password reset | ✓ |
| Tenant | `/tenant` | Current tenant info, branding | ✓ |
| Onboarding | `/onboarding` | School registration, subdomain check | ✓ |
| Schools | `/schools` | School profiles, settings, branding | ✓ |
| Students | `/students` | Student CRUD, guardians, import/export | ✓ |
| Guardians | `/guardians` | Guardian management, student links | ✓ |
| Academic | `/academic` | Years, terms, classes, sections, subjects, holidays | ✓ |
| Users | `/users` | User management | ✓ |
| Media | `/media` | File uploads (S3) | ✓ |
| Staff | `/staff` | Staff CRUD, employment details, departments | ✓ |
| Attendance | `/attendance` | Student/staff attendance, reports, bulk marking | ✓ |
| Exams | `/exams` | Exam management, CA, score entry, report cards | ✓ |
| Timetable | `/timetable` | Class timetables, periods, schedules | ✓ |
| Preschool | `/preschool` | Observations, daily logs, assessments, reports | ✓ |
| Finance | `/finance` | Fee structures, invoices, payments, scholarships | ✓ |
| Boarding | `/boarding` | Dormitories, exeats, roll calls | Planned |
| Reports | `/reports` | Dashboard, report generation | Planned |

### Rate Limits

| Endpoint Type | Limit | Window |
|--------------|-------|--------|
| Authentication | 5 requests | 1 minute |
| General API | 100 requests | 1 minute |
| Bulk Operations | 10 requests | 1 minute |
| Report Generation | 5 requests | 1 minute |
| File Upload | 20 requests | 1 minute |

---

## Database Schema

### Core Tables

| Table | Purpose |
|-------|---------|
| `tenants` | Multi-tenant root with subdomain, subscription, features |
| `reserved_subdomains` | Protected subdomain list (www, api, admin, etc.) |
| `schools` | School profiles with branding and student ID prefix |
| `users` | User accounts with roles and permissions |
| `students` | Student profiles with enrollment status |
| `guardians` | Parent/guardian information |
| `student_guardians` | Many-to-many relationship with relationship type |
| `academic_years` | Academic year definitions with status |
| `terms` | Term/semester definitions |
| `classes` | Class levels (Nursery, KG, Primary, JHS, SHS) |
| `class_sections` | Sections within classes (A, B, C) |
| `subjects` | Subject catalog (core, elective, vocational) |
| `class_subjects` | Subject assignments to classes |
| `grading_scales` | Grading systems (WAEC, GPA, custom) |
| `grades` | Grade definitions within scales |
| `assessment_weights` | Continuous assessment weight configuration |
| `academic_settings` | School-wide academic preferences |
| `school_holidays` | School calendar events and holidays |
| `departments` | Staff departments |
| `exams` | Exam definitions with term/year association |
| `exam_subjects` | Subjects included in each exam |
| `exam_scores` | Student scores for exams |
| `continuous_assessments` | CA scores for ongoing assessment |
| `term_reports` | Generated term report cards |
| `class_timetables` | Weekly class schedules |
| `timetable_periods` | Individual period definitions |

### Finance Tables

| Table | Purpose |
|-------|---------|
| `fee_types` | Fee categories (tuition, examination, facilities, etc.) |
| `fee_structures` | Fee templates per class/level/term |
| `fee_items` | Individual fee line items within structures |
| `invoices` | Student invoices with status tracking |
| `invoice_items` | Invoice line items |
| `payments` | Payment records (cash, Mobile Money, bank) |
| `scholarships` | Scholarship definitions (full, partial, merit, etc.) |
| `student_scholarships` | Scholarship awards to students |
| `scholarship_applications` | Student scholarship applications |
| `credit_notes` | Credit notes for overpayments, fee reductions, corrections |
| `finance_audit_log` | Immutable audit trail for all finance operations |

### Preschool Tables

| Table | Purpose |
|-------|---------|
| `developmental_domains` | Areas of development (cognitive, physical, etc.) |
| `developmental_milestones` | Age-appropriate milestones |
| `student_observations` | Teacher observations of students |
| `daily_activity_logs` | Daily activities (meals, naps, etc.) |
| `preschool_assessments` | Milestone-based assessments |
| `preschool_reports` | Developmental progress reports |

### Tenants Table (Key Fields)

```sql
CREATE TABLE tenants (
    id UUID PRIMARY KEY,
    subdomain VARCHAR(63) NOT NULL,           -- CRITICAL: unique subdomain
    slug VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(20),                         -- single_school, school_chain
    status VARCHAR(20),                       -- trial, active, suspended
    subscription_plan VARCHAR(50),            -- starter, professional, enterprise
    max_students INTEGER,
    max_staff INTEGER,
    features JSONB,                           -- boarding, transport, api_access, etc.
    primary_color VARCHAR(7),                 -- Branding
    logo_url VARCHAR(500)
);
```

### Row-Level Security

```sql
-- Enable RLS
ALTER TABLE students ENABLE ROW LEVEL SECURITY;

-- Create isolation policy
CREATE POLICY tenant_isolation ON students
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- Set tenant context (called on every request)
SELECT set_config('app.current_tenant_id', 'tenant-uuid', false);
```

---

## Core Modules

### 1. Student Management
- Student registration and profiles
- Guardian management (multiple per student)
- Class enrollment
- Attendance tracking
- Transfers and withdrawals
- Promotion and graduation

### 2. Academic Management
- Curriculum and subjects (GES, Cambridge, IB)
- Timetable management
- School calendar with holidays
- Examination management
- Grade entry and calculation
- Report card generation (PDF)

### 3. Examination & Assessment
- Exam creation and scheduling
- Continuous Assessment (CA) management
- Score entry with validation
- Grade calculations (configurable weights)
- Report card generation
- Class and student analytics

### 4. Preschool Module
- Developmental domains and milestones
- Student observations tracking
- Daily activity logs (meals, naps, activities)
- Milestone-based assessments
- Developmental progress reports

### 5. School Calendar
- Academic year and term visualization
- School holidays and events
- Multi-view calendar (Month, Week, Year)
- Drag-and-drop event rescheduling
- School days counter per term
- iCal and Google Calendar export

### 6. Timetable Management
- Class schedule creation
- Period configuration
- Teacher assignments
- Room/venue management

### 7. Financial Management ✓
- Fee type management (tuition, examination, facilities, etc.)
- Fee structure configuration per class/level/term
- Invoice generation (single student, bulk by class)
- Invoice sync with fee structure updates
- Payment recording (Cash, Mobile Money, Bank Transfer)
- Mobile Money support: MTN MoMo, Vodafone Cash, AirtelTigo
- Scholarship management (full, partial, merit, need-based)
- Auto-application of scholarship discounts to invoices at generation time
- Credit notes (overpayment, fee reduction, error correction, other)
- Credit note workflow: draft → issued → applied/refunded/cancelled
- Auto-apply credit notes to oldest unpaid invoice
- Student credit balance tracking
- Finance dashboard with revenue statistics
- Invoice email with CC recipients
- Finance audit logging for all transactions

### 8. Enrollment Management
- Inquiry and lead management
- Online application processing
- Entrance exam scheduling
- Admission decisions
- Re-enrollment campaigns

### 9. Boarding/Hostel Management
- Dormitory and room setup
- Bed assignments
- Exeat management
- Roll calls
- Visitor management

### 10. Transport Management
- Vehicle fleet management
- Route and stop configuration
- Student transport assignments
- Transport fee integration

### 11. HR Management
- Staff records with departments
- Employment tracking
- Leave management
- Payroll (optional module)

### 12. Communication
- SMS notifications (Hubtel/Arkesel)
- Email notifications (SMTP)
- Announcements
- Parent-teacher messaging

---

## Pricing Tiers

| Tier | Monthly Price | Max Students | Key Features |
|------|---------------|--------------|--------------|
| **Trial** | Free (14 days) | 50 | Basic features |
| **Starter** | $50 | 300 | Core modules, 50 SMS/month |
| **Professional** | $150 | 1,000 | All modules, API access, priority support |
| **Enterprise** | Custom | Unlimited | Multi-school, custom domain, SLA |

### Feature Flags by Plan

| Feature | Starter | Professional | Enterprise |
|---------|---------|--------------|------------|
| Student Management | ✓ | ✓ | ✓ |
| Academic Module | ✓ | ✓ | ✓ |
| Finance & Payments | ✓ | ✓ | ✓ |
| Preschool Module | ✓ | ✓ | ✓ |
| Boarding | - | ✓ | ✓ |
| Transport | - | ✓ | ✓ |
| API Access | - | ✓ | ✓ |
| Multi-School | - | - | ✓ |
| Custom Domain | - | - | ✓ |
| White Label | - | - | ✓ |

---

## Development Roadmap

### Phase 1: Foundation (Sprints 1-12, Jan - Mar 2026)

**Sprint 1-2: Core Infrastructure** ✓
- Project setup and Docker environment ✓
- Multi-tenant subdomain architecture ✓
- Authentication with tenant context ✓
- School setup wizard (onboarding) ✓
- Row-Level Security policies ✓

**Sprint 2.5: Security Hardening** ✓
- Rate limiting (Redis sliding window) ✓
- Audit logging service ✓
- Cross-tenant token validation ✓
- Password validation with special chars ✓
- Account lockout protection ✓
- Token blacklisting for logout ✓
- Password reset flow ✓
- Email verification endpoints ✓

**Sprint 3-4: Academic Foundation** ✓
- Academic year/term setup ✓
- Class/section management with student counts ✓
- Subject configuration ✓
- Grading scales (WAEC, GPA, custom) ✓
- Assessment weight configuration ✓

**Sprint 4-5: Student Management** ✓
- Student CRUD with profiles ✓
- Guardian management (multiple per student) ✓
- Student import from CSV/Excel ✓
- Previous student ID support for migrations ✓
- Class enrollment with section assignments ✓
- Student ID auto-generation with school prefix ✓

**Sprint 5-6: Staff Management** ✓
- Staff CRUD with comprehensive profiles ✓
- Employment details (date joined, job title, department) ✓
- Staff types (teaching, non-teaching, administrative) ✓
- Employment status tracking (active, on leave, terminated) ✓
- Staff qualification and emergency contact info ✓
- Department management ✓

**Sprint 7-8: Attendance Module** ✓
- Daily student attendance marking with bulk operations ✓
- Staff attendance tracking ✓
- Attendance status types (present, absent, late, excused, sick) ✓
- Section-based attendance with summary statistics ✓
- Attendance reports with weekly overview ✓
- School-wide and class-by-class report views ✓
- CSV export for attendance data ✓
- Calendar-based school days calculation ✓

**Sprint 9-10: Examinations & Assessment** ✓
- Exam creation and scheduling ✓
- Continuous Assessment (CA) management ✓
- Score entry interface with validation ✓
- Grade calculations with configurable weights ✓
- Report card generation ✓
- Exam analytics and insights ✓
- Score change audit logging ✓

**Sprint 11-12: Preschool & Calendar** ✓
- Preschool developmental domains and milestones ✓
- Student observations tracking ✓
- Daily activity logs ✓
- Preschool assessments and reports ✓
- School calendar with holidays ✓
- Multi-view calendar (Month, Week, Year) ✓
- Drag-and-drop event management ✓
- iCal and Google Calendar export ✓
- Class timetable management ✓

### Phase 2: MVP Launch (Sprints 13-18, Apr - Jun 2026)

**Sprint 13-14: Finance Core** ✓
- Fee types and fee structure management ✓
- Invoice generation (single and bulk) ✓
- Payment recording (cash, Mobile Money, bank transfer) ✓
- Scholarship management with auto-discount application ✓
- Invoice sync with fee structure updates ✓
- Credit notes system (create, issue, apply, refund, cancel) ✓
- Credit note types: overpayment, fee reduction, error correction, other ✓
- Auto-apply credit notes to oldest unpaid invoice ✓
- Student credit balance tracking ✓
- Finance dashboard with statistics ✓
- Invoice email with CC recipients ✓
- Finance audit logging ✓

**Sprint 15-16: Parent Portal**
- Parent account access
- View children's records
- Online fee payment
- Communication with teachers

**Sprint 17-18: Beta Launch**
- Performance optimization
- Beta launch to pilot schools
- Feedback collection and iteration

### Phase 3: Enhancement (Sprints 19-24, Jul - Sep 2026)

- Boarding management
- Transport management
- Enrollment/admissions module
- Additional payment providers

### Phase 4: Scale & Mobile (Sprints 25-30, Oct - Dec 2026)

- Mobile apps (iOS/Android)
- Multi-curriculum support
- Advanced analytics
- White-label options

---

## Security

### Compliance
- Data Protection regulations
- Cybersecurity best practices
- PCI-DSS awareness (for Mobile Money)
- OWASP Top 10 standards

### Encryption
- **At Rest:** AES-256 (database, S3)
- **In Transit:** TLS 1.3
- **Passwords:** Argon2id hashing

### Access Control
- Role-Based Access Control (RBAC)
- Row-Level Security (RLS) for tenant isolation
- Multi-Factor Authentication (MFA)

### Implemented Security Features

| Feature | Implementation |
|---------|---------------|
| **Rate Limiting** | Redis sliding window (5 req/min auth, 100 req/min default) |
| **Cross-Tenant Validation** | `ValidatedTokenTenant` dependency validates JWT tenant matches request |
| **Audit Logging** | `AuditService` logs auth events with separate DB connection |
| **Account Lockout** | 5 failed attempts triggers 30-minute lockout |
| **Password Policy** | Min 8 chars, uppercase, lowercase, number, special character |
| **Token Blacklisting** | Redis-based blacklist for logout/password change |
| **CORS** | Restricted methods (GET, POST, PUT, DELETE, PATCH, OPTIONS) |
| **SQL Injection** | Parameterized queries in all database operations |
| **Security Headers** | CSP, HSTS, X-Frame-Options, X-Content-Type-Options |
| **Score Change Logging** | Audit trail for exam score modifications |

### Middleware Stack (Order Matters)

```python
# Applied in reverse order (last added = first executed)
app.add_middleware(TenantMiddleware)      # 1. Extract tenant from subdomain
app.add_middleware(RateLimitMiddleware)   # 2. Check rate limits
app.add_middleware(CORSMiddleware, ...)   # 3. Handle CORS
```

### User Roles

| Role | Access Level | Permissions |
|------|-------------|-------------|
| Platform Admin | System-wide administration | `*` (all) |
| Chain Admin | All schools in chain | `schools.*`, `users.*`, `students.*`, etc. |
| School Admin | Full access to single school | `school.read`, `school.update`, `users.*`, etc. |
| Academic Head | Students, academics, exams | `students.read`, `classes.*`, `exams.*` |
| Finance Officer | Fees, invoices, payments | `students.read`, `finance.*` |
| Teacher | Assigned classes only | `students.read`, `attendance.mark`, `exams.scores` |
| House Parent | Boarding operations | `students.read`, `boarding.*` |
| Parent | Own children (read-only) | `children.read`, `finance.invoices.read` |
| Student | Own records (limited) | `self.read` |

---

## Project Structure

```
sims-plus/
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── api/v1/endpoints/  # Route handlers
│   │   │   ├── auth.py        # Authentication
│   │   │   ├── academic.py    # Classes, subjects, grading, holidays
│   │   │   ├── students.py    # Student management
│   │   │   ├── staff.py       # Staff & departments
│   │   │   ├── attendance.py  # Attendance tracking
│   │   │   ├── exams.py       # Exams, CA, report cards
│   │   │   ├── timetable.py   # Class timetables
│   │   │   ├── preschool.py   # Preschool module
│   │   │   ├── finance.py     # Fee structures, invoices, payments, scholarships
│   │   │   ├── schools.py     # School settings
│   │   │   ├── users.py       # User management
│   │   │   └── media.py       # File uploads
│   │   ├── core/              # Config, security
│   │   ├── db/                # Database session
│   │   ├── models/            # SQLAlchemy models
│   │   │   ├── tenant.py      # Tenant, User
│   │   │   ├── school.py      # School profiles
│   │   │   ├── student.py     # Student, Guardian
│   │   │   ├── staff.py       # Staff, Departments
│   │   │   ├── academic.py    # Classes, Subjects, Grading
│   │   │   ├── exam.py        # Exams, Scores, Reports
│   │   │   ├── preschool.py   # Preschool models
│   │   │   └── finance.py     # Fee structures, invoices, payments, scholarships
│   │   ├── schemas/           # Pydantic schemas
│   │   ├── services/          # Business logic
│   │   │   ├── auth.py        # Authentication service
│   │   │   ├── student.py     # Student service with import
│   │   │   ├── staff.py       # Staff service
│   │   │   ├── academic.py    # Academic service
│   │   │   ├── exam.py        # Exam service
│   │   │   ├── timetable.py   # Timetable service
│   │   │   ├── preschool.py   # Preschool service
│   │   │   ├── finance.py     # Finance service (fees, invoices, payments, scholarships)
│   │   │   ├── pdf.py         # PDF generation
│   │   │   └── s3.py          # S3 upload service
│   │   ├── middleware/        # Tenant, rate limiting
│   │   └── templates/         # PDF templates
│   ├── alembic/               # Database migrations
│   └── requirements.txt
├── frontend/                   # Next.js 16 frontend
│   ├── app/
│   │   ├── (auth)/            # Login, register, password reset
│   │   └── (dashboard)/       # Protected dashboard pages
│   │       ├── dashboard/     # Main dashboard
│   │       ├── calendar/      # School calendar
│   │       ├── students/      # Student management
│   │       ├── staff/         # Staff & departments
│   │       ├── classes/       # Classes, timetables
│   │       ├── attendance/    # Attendance marking & reports
│   │       ├── exams/         # Exams, CA, report cards
│   │       ├── preschool/     # Preschool module
│   │       ├── finance/       # Fee structures, invoices, payments, scholarships, credit notes
│   │       ├── boarding/      # Boarding (placeholder)
│   │       ├── transport/     # Transport (placeholder)
│   │       ├── messages/      # Communication (placeholder)
│   │       ├── reports/       # Reports (placeholder)
│   │       └── settings/      # School & academic settings
│   ├── components/
│   │   ├── ui/                # Shadcn components
│   │   ├── dashboard/         # Sidebar, header
│   │   ├── academic/          # Academic settings components
│   │   ├── preschool/         # Preschool components
│   │   └── setup-wizard/      # School setup wizard
│   ├── actions/               # Server Actions (*.action.ts)
│   │   ├── auth.action.ts
│   │   ├── students.action.ts
│   │   ├── staff.action.ts
│   │   ├── academic.action.ts
│   │   ├── school.action.ts
│   │   ├── exams.action.ts
│   │   ├── timetable.action.ts
│   │   ├── preschool.action.ts
│   │   └── finance.action.ts
│   ├── hooks/                 # Custom hooks
│   ├── lib/                   # Utilities
│   └── types/                 # TypeScript types
├── infrastructure/             # Terraform IaC
├── docs/                       # Documentation
├── docker-compose.yml
├── CLAUDE.md                   # This file
└── README.md
```

---

## Key Integrations

### Payment Providers
- MTN MoMo (Collections API) - **Must Have**
- Vodafone Cash - **Should Have**
- AirtelTigo Money - **Should Have**
- Stripe (International) - **Should Have**

### SMS Gateways
- Hubtel (Primary)
- Arkesel (Backup)
- Twilio (International)

### Calendar Integrations
- iCal (.ics) export
- Google Calendar URL generation

### Education System Integrations
- GES EMIS (Annual census export)
- WAEC (BECE/WASSCE registration)
- CSSPS (SHS placement data)

---

## Design System

### Colors (GitHub Primer Theme)
- Uses GitHub's Primer design system
- Light and Dark mode support
- System preference detection

### Typography
- **Font Family:** Inter (system fallback)
- **H1:** 36px Bold
- **H2:** 30px Semibold
- **H3:** 24px Semibold
- **Body:** 14px Regular

---

## Performance Targets

| Metric | Target |
|--------|--------|
| Page Load (3G) | < 3 seconds |
| API Response (p95) | < 500ms |
| Concurrent Users/Tenant | 500 |
| Uptime SLA | 99.5% |
| RTO (Recovery Time) | 4 hours |
| RPO (Data Loss) | 1 hour |

---

## Getting Help

- **Documentation:** See `/docs` folder
- **API Docs:** `http://localhost:8000/docs` (Swagger UI)
- **Support Email:** support@simsplus.io

---

## Contributing

When working on this project:

1. Follow the subdomain multi-tenant architecture
2. Always include `tenant_id` in tenant-scoped queries
3. Use Row-Level Security for data isolation
4. Use Server Actions for data fetching (frontend)
5. Follow formatting requirements:
   - Date format: DD/MM/YYYY
   - Phone format: +233 XX XXX XXXX (Ghana) or international format
   - Currency: Configurable per tenant
6. Test offline functionality for critical features
7. Add appropriate audit logging

---

## Frontend Conventions

### File Naming

| Type | Convention | Example |
|------|------------|---------|
| Server Actions | `{module}.action.ts` | `auth.action.ts`, `students.action.ts` |
| API Routes | `route.ts` | `app/api/health/route.ts` |
| Components | PascalCase | `StudentCard.tsx`, `LoginForm.tsx` |
| Hooks | camelCase with `use` prefix | `useTenant.ts`, `useAuth.ts` |
| Types | `index.ts` in types folder | `types/index.ts` |

### Server Actions Structure

```typescript
// actions/students.action.ts
"use server";

import { apiGet, apiPost } from "@/lib/api";
import type { ActionResult, Student } from "@/types";

export async function getStudents(): Promise<ActionResult<Student[]>> {
  try {
    const response = await apiGet<Student[]>("/students");
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch students",
    };
  }
}
```

### Import Order

1. React/Next.js imports
2. Third-party libraries
3. UI components (`@/components/ui/*`)
4. Custom components
5. Actions (`@/actions/*`)
6. Hooks (`@/hooks/*`)
7. Types (`@/types`)
8. Utilities (`@/lib/*`)
