# SIMS Plus (School Information Management System Plus) - Database Schema

**Version:** 2.3
**Date:** January 2026
**Author:** Harry McNinson
**Status:** Updated with Finance Tables (Fee Types, Fee Structures, Invoices, Payments, Scholarships, Credit Notes, Audit Log)

---

## Table of Contents

1. [Schema Overview](#1-schema-overview)
2. [Multi-Tenancy Design](#2-multi-tenancy-design)
3. [Core Tables](#3-core-tables)
4. [User & Authentication Tables](#4-user--authentication-tables)
5. [Student Tables](#5-student-tables)
6. [Staff Tables](#6-staff-tables)
7. [Academic Tables](#7-academic-tables)
8. [Exam Tables](#8-exam-tables)
9. [Timetable Tables](#9-timetable-tables)
10. [Finance Tables](#10-finance-tables)
11. [Indexes & Performance](#11-indexes--performance)

---

## 1. Schema Overview

### 1.1 Design Principles

- **UUID Primary Keys**: Global uniqueness across tenants
- **Soft Deletes**: `deleted_at` timestamp (data recovery)
- **Audit Columns**: `created_at`, `updated_at`, `created_by`, `updated_by`
- **Multi-Tenant**: `tenant_id` on all tenant-scoped tables
- **Row-Level Security**: PostgreSQL RLS for tenant isolation
- **Subdomain Routing**: Unique subdomain per tenant

### 1.2 Table Categories

| Category | Tables | Description |
|----------|--------|-------------|
| **Core** | tenants, schools, reserved_subdomains | Multi-tenancy foundation |
| **Users** | users, roles, permissions | Authentication & authorization |
| **Students** | students, guardians, enrollments | Student management |
| **Staff** | staff, departments | Staff management |
| **Academic** | classes, subjects, grading_scales, school_holidays | Academic structure |
| **Exams** | exams, exam_subjects, exam_scores, continuous_assessments, term_reports | Examination management |
| **Timetable** | class_timetables, timetable_periods | Class scheduling |
| **Finance** | fee_types, fee_structures, fee_items, invoices, invoice_items, payments, scholarships, student_scholarships, scholarship_applications, credit_notes, finance_audit_log | Financial management |
| **Boarding** | dormitories, rooms, exeats | Boarding management |
| **Transport** | vehicles, routes, assignments | Transport management |
| **Preschool** | developmental_domains, milestones, observations, daily_logs, assessments | Early childhood education |
| **Audit** | audit_logs, score_change_logs | Compliance & tracking |

> **Note:** For detailed preschool database schema, see [PRESCHOOL_ARCHITECTURE.md](./PRESCHOOL_ARCHITECTURE.md)

---

## 2. Multi-Tenancy Design

### 2.1 Tenants Table (Root of Multi-Tenancy)

```sql
CREATE TABLE tenants (
    -- Primary Key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Subdomain (CRITICAL for routing)
    subdomain VARCHAR(63) NOT NULL,
    slug VARCHAR(100) NOT NULL,

    -- Basic Info
    name VARCHAR(255) NOT NULL,
    type VARCHAR(20) DEFAULT 'single_school'
        CHECK (type IN ('single_school', 'school_chain')),

    -- Branding
    logo_url VARCHAR(500),
    favicon_url VARCHAR(500),
    primary_color VARCHAR(7) DEFAULT '#1B4F72',
    secondary_color VARCHAR(7),

    -- Status
    status VARCHAR(20) DEFAULT 'trial'
        CHECK (status IN ('trial', 'active', 'suspended', 'cancelled')),

    -- Subscription
    subscription_plan VARCHAR(50) DEFAULT 'starter'
        CHECK (subscription_plan IN ('starter', 'professional', 'enterprise')),
    subscription_status VARCHAR(20) DEFAULT 'trial',
    trial_ends_at TIMESTAMP,
    subscription_starts_at TIMESTAMP,
    subscription_ends_at TIMESTAMP,

    -- Resource Limits
    max_students INTEGER DEFAULT 100,
    max_staff INTEGER DEFAULT 20,
    max_schools INTEGER DEFAULT 1,
    storage_limit_gb INTEGER DEFAULT 5,
    sms_monthly_limit INTEGER DEFAULT 50,

    -- Current Usage (cached, updated periodically)
    current_student_count INTEGER DEFAULT 0,
    current_staff_count INTEGER DEFAULT 0,
    current_storage_gb DECIMAL(10,2) DEFAULT 0,

    -- Feature Flags
    features JSONB DEFAULT '{
        "boarding": false,
        "transport": false,
        "multi_curriculum": false,
        "api_access": false,
        "custom_domain": false,
        "white_label": false,
        "preschool": false
    }',

    -- Settings
    settings JSONB DEFAULT '{}',
    timezone VARCHAR(50) DEFAULT 'Africa/Accra',
    locale VARCHAR(10) DEFAULT 'en',

    -- Audit
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by UUID,
    updated_by UUID,
    deleted_at TIMESTAMP
);

-- CRITICAL: Unique constraint on subdomain
CREATE UNIQUE INDEX idx_tenants_subdomain_unique
    ON tenants(subdomain)
    WHERE deleted_at IS NULL;

-- Unique constraint on slug
CREATE UNIQUE INDEX idx_tenants_slug_unique
    ON tenants(slug)
    WHERE deleted_at IS NULL;

-- Index for status queries
CREATE INDEX idx_tenants_status ON tenants(status);

-- Index for subscription queries
CREATE INDEX idx_tenants_subscription ON tenants(subscription_status, subscription_ends_at);
```

### 2.2 Reserved Subdomains Table

```sql
CREATE TABLE reserved_subdomains (
    subdomain VARCHAR(63) PRIMARY KEY,
    reason VARCHAR(255) NOT NULL,
    reserved_at TIMESTAMP DEFAULT NOW(),
    reserved_by VARCHAR(100)
);

-- Insert reserved subdomains
INSERT INTO reserved_subdomains (subdomain, reason) VALUES
    ('www', 'System - Main website'),
    ('app', 'System - Generic login portal'),
    ('api', 'System - API endpoint'),
    ('admin', 'System - Admin panel'),
    ('mail', 'System - Email services'),
    ('smtp', 'System - Email services'),
    ('ftp', 'System - File transfer'),
    ('status', 'System - Status page'),
    ('blog', 'Marketing - Blog'),
    ('help', 'Support - Help center'),
    ('support', 'Support - Support portal'),
    ('docs', 'Documentation'),
    ('cdn', 'System - Content delivery'),
    ('assets', 'System - Static assets'),
    ('staging', 'System - Staging environment'),
    ('dev', 'System - Development'),
    ('test', 'System - Testing'),
    ('demo', 'Sales - Demo environment'),
    ('sandbox', 'Development - Sandbox');
```

### 2.3 Row-Level Security (RLS)

```sql
-- Enable RLS on tenant-scoped tables
ALTER TABLE schools ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE students ENABLE ROW LEVEL SECURITY;
ALTER TABLE staff ENABLE ROW LEVEL SECURITY;
ALTER TABLE guardians ENABLE ROW LEVEL SECURITY;
ALTER TABLE classes ENABLE ROW LEVEL SECURITY;
ALTER TABLE sections ENABLE ROW LEVEL SECURITY;
ALTER TABLE subjects ENABLE ROW LEVEL SECURITY;
ALTER TABLE exams ENABLE ROW LEVEL SECURITY;
ALTER TABLE exam_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE attendance ENABLE ROW LEVEL SECURITY;
ALTER TABLE dormitories ENABLE ROW LEVEL SECURITY;
ALTER TABLE school_holidays ENABLE ROW LEVEL SECURITY;
ALTER TABLE class_timetables ENABLE ROW LEVEL SECURITY;
ALTER TABLE credit_notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE finance_audit_log ENABLE ROW LEVEL SECURITY;

-- Create tenant isolation policy (template)
CREATE POLICY tenant_isolation ON schools
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- Function to set tenant context
CREATE OR REPLACE FUNCTION set_tenant_context(p_tenant_id UUID)
RETURNS VOID AS $$
BEGIN
    PERFORM set_config('app.current_tenant_id', p_tenant_id::TEXT, false);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to get current tenant
CREATE OR REPLACE FUNCTION get_current_tenant_id()
RETURNS UUID AS $$
BEGIN
    RETURN current_setting('app.current_tenant_id', true)::UUID;
EXCEPTION
    WHEN OTHERS THEN
        RETURN NULL;
END;
$$ LANGUAGE plpgsql STABLE;
```

---

## 3. Core Tables

### 3.1 Schools Table

```sql
CREATE TABLE schools (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

    -- Basic Info
    name VARCHAR(255) NOT NULL,
    code VARCHAR(50),
    type VARCHAR(50) CHECK (type IN (
        'primary', 'jhs', 'shs', 'basic', 'international',
        'technical', 'vocational', 'tertiary', 'preschool'
    )),

    -- Contact
    email VARCHAR(255),
    phone VARCHAR(20),
    phone_secondary VARCHAR(20),
    website VARCHAR(255),

    -- Address
    address_line1 VARCHAR(255),
    address_line2 VARCHAR(255),
    city VARCHAR(100),
    region VARCHAR(100),
    gps_address VARCHAR(50),
    postal_address VARCHAR(255),

    -- Location (for transport)
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),

    -- Branding
    logo_url VARCHAR(500),
    motto VARCHAR(500),
    vision TEXT,
    mission TEXT,

    -- Student ID Configuration
    student_id_prefix VARCHAR(20),

    -- GES Integration
    emis_code VARCHAR(50),
    district_education_office VARCHAR(255),

    -- Settings
    settings JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT true,
    is_main_campus BOOLEAN DEFAULT false,

    -- Audit
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by UUID,
    updated_by UUID,
    deleted_at TIMESTAMP
);

CREATE INDEX idx_schools_tenant ON schools(tenant_id);
CREATE INDEX idx_schools_code ON schools(tenant_id, code);
```

### 3.2 Academic Years Table

```sql
CREATE TABLE academic_years (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    school_id UUID REFERENCES schools(id) ON DELETE CASCADE,

    name VARCHAR(50) NOT NULL,  -- e.g., "2025/2026"
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    is_current BOOLEAN DEFAULT false,

    settings JSONB DEFAULT '{}',

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_academic_years_tenant ON academic_years(tenant_id);
CREATE UNIQUE INDEX idx_academic_years_current
    ON academic_years(tenant_id, school_id)
    WHERE is_current = true;
```

### 3.3 Terms Table

```sql
CREATE TABLE terms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    academic_year_id UUID NOT NULL REFERENCES academic_years(id) ON DELETE CASCADE,

    name VARCHAR(50) NOT NULL,  -- e.g., "Term 1", "First Semester"
    sequence INTEGER NOT NULL,  -- 1, 2, 3
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    is_current BOOLEAN DEFAULT false,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_terms_academic_year ON terms(academic_year_id);
```

### 3.4 School Holidays Table

```sql
CREATE TABLE school_holidays (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    academic_year_id UUID REFERENCES academic_years(id) ON DELETE SET NULL,

    name VARCHAR(255) NOT NULL,
    date DATE NOT NULL,
    end_date DATE,  -- For multi-day events
    type VARCHAR(50) DEFAULT 'public_holiday' CHECK (type IN (
        'public_holiday', 'school_break', 'school_event',
        'exam_period', 'other'
    )),
    description TEXT,
    is_recurring BOOLEAN DEFAULT false,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by UUID,
    deleted_at TIMESTAMP
);

CREATE INDEX idx_school_holidays_tenant ON school_holidays(tenant_id);
CREATE INDEX idx_school_holidays_date ON school_holidays(tenant_id, date);
CREATE INDEX idx_school_holidays_year ON school_holidays(academic_year_id);
```

---

## 4. User & Authentication Tables

### 4.1 Users Table

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

    -- Authentication
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255),
    is_email_verified BOOLEAN DEFAULT false,
    email_verified_at TIMESTAMP,

    -- Profile
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    other_names VARCHAR(100),
    phone VARCHAR(20),
    photo_url VARCHAR(500),

    -- MFA
    mfa_enabled BOOLEAN DEFAULT false,
    mfa_secret VARCHAR(100),
    mfa_recovery_codes JSONB,

    -- Status
    is_active BOOLEAN DEFAULT true,
    last_login_at TIMESTAMP,
    last_login_ip VARCHAR(45),
    failed_login_attempts INTEGER DEFAULT 0,
    locked_until TIMESTAMP,

    -- Password Reset
    password_reset_token VARCHAR(255),
    password_reset_expires TIMESTAMP,
    must_change_password BOOLEAN DEFAULT false,
    password_changed_at TIMESTAMP,

    -- Linked Records
    staff_id UUID,
    guardian_id UUID,

    -- Settings
    settings JSONB DEFAULT '{}',
    notification_preferences JSONB DEFAULT '{}',

    -- Audit
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    deleted_at TIMESTAMP
);

CREATE UNIQUE INDEX idx_users_tenant_email
    ON users(tenant_id, LOWER(email))
    WHERE deleted_at IS NULL;

CREATE INDEX idx_users_tenant ON users(tenant_id);
CREATE INDEX idx_users_staff ON users(staff_id) WHERE staff_id IS NOT NULL;
```

### 4.2 Roles Table

```sql
CREATE TABLE roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,

    name VARCHAR(100) NOT NULL,
    slug VARCHAR(100) NOT NULL,
    description TEXT,
    is_system BOOLEAN DEFAULT false,

    permissions JSONB NOT NULL DEFAULT '[]',

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

---

## 5. Student Tables

### 5.1 Students Table

```sql
CREATE TABLE students (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,

    -- Identifiers
    student_id VARCHAR(50) NOT NULL,
    admission_number VARCHAR(50),
    previous_student_id VARCHAR(50),  -- For migrations

    -- Personal Info
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    other_names VARCHAR(100),
    gender VARCHAR(10) NOT NULL CHECK (gender IN ('male', 'female')),
    date_of_birth DATE NOT NULL,

    -- Contact
    email VARCHAR(255),
    phone VARCHAR(20),

    -- Photo
    photo_url VARCHAR(500),

    -- Address
    address_line1 VARCHAR(255),
    city VARCHAR(100),
    region VARCHAR(100),

    -- Medical
    blood_group VARCHAR(5),
    medical_conditions TEXT,
    allergies TEXT,

    -- Academic
    current_class_id UUID REFERENCES classes(id),
    current_section_id UUID REFERENCES sections(id),
    admission_date DATE NOT NULL,
    graduation_date DATE,

    -- Status
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN (
        'active', 'inactive', 'withdrawn', 'transferred',
        'graduated', 'suspended', 'expelled'
    )),

    -- Boarding
    is_boarding BOOLEAN DEFAULT false,
    dormitory_id UUID,

    -- Metadata
    metadata JSONB DEFAULT '{}',

    -- Audit
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by UUID,
    updated_by UUID,
    deleted_at TIMESTAMP
);

CREATE UNIQUE INDEX idx_students_tenant_student_id
    ON students(tenant_id, student_id)
    WHERE deleted_at IS NULL;

CREATE INDEX idx_students_tenant_school ON students(tenant_id, school_id);
CREATE INDEX idx_students_status ON students(tenant_id, status);
CREATE INDEX idx_students_class ON students(current_class_id);
```

### 5.2 Guardians Table

```sql
CREATE TABLE guardians (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

    -- Personal Info
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    other_names VARCHAR(100),
    gender VARCHAR(10),

    -- Contact
    phone_primary VARCHAR(20) NOT NULL,
    phone_secondary VARCHAR(20),
    email VARCHAR(255),

    -- Address
    address VARCHAR(500),
    city VARCHAR(100),
    region VARCHAR(100),

    -- Employment
    occupation VARCHAR(255),
    employer VARCHAR(255),

    -- Linked User Account
    user_id UUID REFERENCES users(id),

    -- Audit
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    deleted_at TIMESTAMP
);

CREATE INDEX idx_guardians_tenant ON guardians(tenant_id);
CREATE INDEX idx_guardians_phone ON guardians(tenant_id, phone_primary);
```

### 5.3 Student Guardians (Junction Table)

```sql
CREATE TABLE student_guardians (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    guardian_id UUID NOT NULL REFERENCES guardians(id) ON DELETE CASCADE,

    relationship VARCHAR(50) NOT NULL CHECK (relationship IN (
        'father', 'mother', 'guardian', 'grandfather', 'grandmother',
        'uncle', 'aunt', 'sibling', 'other'
    )),

    is_primary BOOLEAN DEFAULT false,
    is_emergency_contact BOOLEAN DEFAULT false,
    can_pickup BOOLEAN DEFAULT true,
    receives_reports BOOLEAN DEFAULT true,
    receives_invoices BOOLEAN DEFAULT false,

    notes TEXT,

    created_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(student_id, guardian_id)
);

CREATE INDEX idx_student_guardians_student ON student_guardians(student_id);
CREATE INDEX idx_student_guardians_guardian ON student_guardians(guardian_id);
```

---

## 6. Staff Tables

### 6.1 Departments Table

```sql
CREATE TABLE departments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    school_id UUID REFERENCES schools(id) ON DELETE CASCADE,

    name VARCHAR(255) NOT NULL,
    code VARCHAR(50),
    description TEXT,
    head_id UUID,  -- References staff table

    is_active BOOLEAN DEFAULT true,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    deleted_at TIMESTAMP
);

CREATE INDEX idx_departments_tenant ON departments(tenant_id);
CREATE UNIQUE INDEX idx_departments_code
    ON departments(tenant_id, code)
    WHERE deleted_at IS NULL AND code IS NOT NULL;
```

### 6.2 Staff Table

```sql
CREATE TABLE staff (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,

    -- Identifiers
    staff_id VARCHAR(50) NOT NULL,

    -- Personal Info
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    other_names VARCHAR(100),
    gender VARCHAR(10) CHECK (gender IN ('male', 'female')),
    date_of_birth DATE,

    -- Contact
    email VARCHAR(255),
    phone VARCHAR(20),
    phone_secondary VARCHAR(20),

    -- Photo
    photo_url VARCHAR(500),

    -- Address
    address VARCHAR(500),
    city VARCHAR(100),
    region VARCHAR(100),

    -- Employment
    staff_type VARCHAR(50) DEFAULT 'teaching' CHECK (staff_type IN (
        'teaching', 'non_teaching', 'administrative'
    )),
    job_title VARCHAR(255),
    department_id UUID REFERENCES departments(id),
    date_joined DATE,
    employment_status VARCHAR(50) DEFAULT 'active' CHECK (employment_status IN (
        'active', 'on_leave', 'suspended', 'terminated', 'retired'
    )),

    -- Qualifications
    highest_qualification VARCHAR(255),
    specialization VARCHAR(255),

    -- Emergency Contact
    emergency_contact_name VARCHAR(255),
    emergency_contact_phone VARCHAR(20),
    emergency_contact_relationship VARCHAR(100),

    -- Linked User Account
    user_id UUID REFERENCES users(id),

    -- Metadata
    metadata JSONB DEFAULT '{}',

    -- Audit
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by UUID,
    updated_by UUID,
    deleted_at TIMESTAMP
);

CREATE UNIQUE INDEX idx_staff_tenant_staff_id
    ON staff(tenant_id, staff_id)
    WHERE deleted_at IS NULL;

CREATE INDEX idx_staff_tenant_school ON staff(tenant_id, school_id);
CREATE INDEX idx_staff_department ON staff(department_id);
CREATE INDEX idx_staff_user ON staff(user_id) WHERE user_id IS NOT NULL;
```

---

## 7. Academic Tables

### 7.1 Classes Table

```sql
CREATE TABLE classes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,

    name VARCHAR(100) NOT NULL,
    code VARCHAR(20),
    level INTEGER,
    category VARCHAR(50) CHECK (category IN (
        'preschool', 'primary', 'jhs', 'shs'
    )),

    capacity INTEGER,
    is_active BOOLEAN DEFAULT true,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_classes_tenant_school ON classes(tenant_id, school_id);
```

### 7.2 Sections Table

```sql
CREATE TABLE sections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    class_id UUID NOT NULL REFERENCES classes(id) ON DELETE CASCADE,

    name VARCHAR(50) NOT NULL,
    capacity INTEGER,

    class_teacher_id UUID REFERENCES staff(id),

    is_active BOOLEAN DEFAULT true,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_sections_class ON sections(class_id);
```

### 7.3 Subjects Table

```sql
CREATE TABLE subjects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    school_id UUID REFERENCES schools(id) ON DELETE CASCADE,

    name VARCHAR(255) NOT NULL,
    code VARCHAR(50),
    type VARCHAR(50) DEFAULT 'core' CHECK (type IN (
        'core', 'elective', 'vocational', 'extra'
    )),
    category VARCHAR(100),
    description TEXT,

    is_active BOOLEAN DEFAULT true,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_subjects_tenant ON subjects(tenant_id);
```

### 7.4 Grading Scales Table

```sql
CREATE TABLE grading_scales (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

    name VARCHAR(100) NOT NULL,
    type VARCHAR(50) DEFAULT 'custom' CHECK (type IN (
        'waec', 'gpa', 'percentage', 'custom'
    )),
    description TEXT,
    is_default BOOLEAN DEFAULT false,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE grades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    grading_scale_id UUID NOT NULL REFERENCES grading_scales(id) ON DELETE CASCADE,

    grade VARCHAR(10) NOT NULL,
    min_score DECIMAL(5,2) NOT NULL,
    max_score DECIMAL(5,2) NOT NULL,
    grade_point DECIMAL(3,2),
    description VARCHAR(100),

    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_grades_scale ON grades(grading_scale_id);
```

---

## 8. Exam Tables

### 8.1 Exams Table

```sql
CREATE TABLE exams (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    school_id UUID REFERENCES schools(id) ON DELETE CASCADE,
    academic_year_id UUID NOT NULL REFERENCES academic_years(id),
    term_id UUID NOT NULL REFERENCES terms(id),

    name VARCHAR(255) NOT NULL,
    exam_type VARCHAR(50) DEFAULT 'end_of_term' CHECK (exam_type IN (
        'mid_term', 'end_of_term', 'mock', 'promotion', 'entrance', 'other'
    )),
    description TEXT,

    start_date DATE,
    end_date DATE,

    status VARCHAR(50) DEFAULT 'draft' CHECK (status IN (
        'draft', 'scheduled', 'in_progress', 'completed', 'cancelled'
    )),

    -- Settings
    settings JSONB DEFAULT '{}',

    -- Audit
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by UUID,
    updated_by UUID,
    deleted_at TIMESTAMP
);

CREATE INDEX idx_exams_tenant ON exams(tenant_id);
CREATE INDEX idx_exams_term ON exams(term_id);
CREATE INDEX idx_exams_status ON exams(tenant_id, status);
```

### 8.2 Exam Subjects Table

```sql
CREATE TABLE exam_subjects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exam_id UUID NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
    subject_id UUID NOT NULL REFERENCES subjects(id),
    class_id UUID NOT NULL REFERENCES classes(id),
    section_id UUID REFERENCES sections(id),

    max_score DECIMAL(5,2) DEFAULT 100,
    passing_score DECIMAL(5,2) DEFAULT 50,
    grading_scale_id UUID REFERENCES grading_scales(id),

    exam_date DATE,
    start_time TIME,
    end_time TIME,
    venue VARCHAR(255),

    -- Soft delete
    deleted_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(exam_id, subject_id, class_id, section_id)
);

CREATE INDEX idx_exam_subjects_exam ON exam_subjects(exam_id);
CREATE INDEX idx_exam_subjects_class ON exam_subjects(class_id);
CREATE INDEX idx_exam_subjects_subject ON exam_subjects(subject_id);
```

### 8.3 Exam Scores Table

```sql
CREATE TABLE exam_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    exam_subject_id UUID NOT NULL REFERENCES exam_subjects(id) ON DELETE CASCADE,
    student_id UUID NOT NULL REFERENCES students(id),

    score DECIMAL(5,2),
    grade VARCHAR(10),
    grade_point DECIMAL(3,2),
    remarks TEXT,

    is_absent BOOLEAN DEFAULT false,
    is_exempt BOOLEAN DEFAULT false,

    -- Audit
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    entered_by UUID,
    updated_by UUID,
    deleted_at TIMESTAMP,

    UNIQUE(exam_subject_id, student_id)
);

CREATE INDEX idx_exam_scores_tenant ON exam_scores(tenant_id);
CREATE INDEX idx_exam_scores_student ON exam_scores(student_id);
CREATE INDEX idx_exam_scores_exam_subject ON exam_scores(exam_subject_id);
```

### 8.4 Continuous Assessments Table

```sql
CREATE TABLE continuous_assessments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    term_id UUID NOT NULL REFERENCES terms(id),
    class_id UUID NOT NULL REFERENCES classes(id),
    section_id UUID REFERENCES sections(id),
    subject_id UUID NOT NULL REFERENCES subjects(id),
    student_id UUID NOT NULL REFERENCES students(id),

    assessment_type VARCHAR(50) NOT NULL CHECK (assessment_type IN (
        'class_test', 'homework', 'assignment', 'quiz', 'project', 'other'
    )),
    assessment_name VARCHAR(255),

    max_score DECIMAL(5,2) NOT NULL,
    score DECIMAL(5,2),
    date DATE,

    remarks TEXT,

    -- Audit
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    entered_by UUID,
    deleted_at TIMESTAMP
);

CREATE INDEX idx_ca_tenant ON continuous_assessments(tenant_id);
CREATE INDEX idx_ca_term ON continuous_assessments(term_id);
CREATE INDEX idx_ca_student ON continuous_assessments(student_id);
CREATE INDEX idx_ca_subject ON continuous_assessments(subject_id);
CREATE INDEX idx_ca_class ON continuous_assessments(class_id);
```

### 8.5 Term Reports Table

```sql
CREATE TABLE term_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    exam_id UUID NOT NULL REFERENCES exams(id),
    student_id UUID NOT NULL REFERENCES students(id),
    class_id UUID NOT NULL REFERENCES classes(id),
    section_id UUID REFERENCES sections(id),

    -- Aggregated Scores
    total_score DECIMAL(7,2),
    total_possible DECIMAL(7,2),
    average_score DECIMAL(5,2),
    overall_grade VARCHAR(10),
    overall_grade_point DECIMAL(3,2),

    -- Position
    class_position INTEGER,
    section_position INTEGER,

    -- Subjects Count
    subjects_count INTEGER,
    subjects_passed INTEGER,

    -- Class Stats
    class_size INTEGER,
    class_average DECIMAL(5,2),

    -- Attendance
    days_present INTEGER,
    days_absent INTEGER,
    total_school_days INTEGER,

    -- Comments
    class_teacher_comment TEXT,
    head_teacher_comment TEXT,
    conduct_grade VARCHAR(50),

    -- Promotion
    promoted BOOLEAN,
    next_class_id UUID REFERENCES classes(id),

    -- Status
    status VARCHAR(50) DEFAULT 'draft' CHECK (status IN (
        'draft', 'generated', 'approved', 'released'
    )),

    -- PDF
    pdf_url VARCHAR(500),
    generated_at TIMESTAMP,

    -- Audit
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    approved_by UUID,
    approved_at TIMESTAMP,

    UNIQUE(exam_id, student_id)
);

CREATE INDEX idx_term_reports_tenant ON term_reports(tenant_id);
CREATE INDEX idx_term_reports_exam ON term_reports(exam_id);
CREATE INDEX idx_term_reports_student ON term_reports(student_id);
CREATE INDEX idx_term_reports_class ON term_reports(class_id);
```

### 8.6 Score Change Log Table

```sql
CREATE TABLE score_change_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

    table_name VARCHAR(100) NOT NULL,  -- 'exam_scores' or 'continuous_assessments'
    record_id UUID NOT NULL,
    student_id UUID NOT NULL REFERENCES students(id),

    old_score DECIMAL(5,2),
    new_score DECIMAL(5,2),
    reason TEXT,

    changed_by UUID NOT NULL REFERENCES users(id),
    changed_at TIMESTAMP DEFAULT NOW(),
    ip_address VARCHAR(45)
);

CREATE INDEX idx_score_change_logs_tenant ON score_change_logs(tenant_id);
CREATE INDEX idx_score_change_logs_record ON score_change_logs(table_name, record_id);
CREATE INDEX idx_score_change_logs_student ON score_change_logs(student_id);
```

---

## 9. Timetable Tables

### 9.1 Class Timetables Table

```sql
CREATE TABLE class_timetables (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    class_id UUID NOT NULL REFERENCES classes(id),
    section_id UUID REFERENCES sections(id),
    term_id UUID NOT NULL REFERENCES terms(id),

    name VARCHAR(255),
    is_active BOOLEAN DEFAULT true,

    -- Settings
    settings JSONB DEFAULT '{}',

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by UUID,

    UNIQUE(class_id, section_id, term_id)
);

CREATE INDEX idx_class_timetables_tenant ON class_timetables(tenant_id);
CREATE INDEX idx_class_timetables_class ON class_timetables(class_id);
CREATE INDEX idx_class_timetables_term ON class_timetables(term_id);
```

### 9.2 Timetable Periods Table

```sql
CREATE TABLE timetable_periods (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timetable_id UUID NOT NULL REFERENCES class_timetables(id) ON DELETE CASCADE,

    day_of_week INTEGER NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
    -- 0 = Monday, 1 = Tuesday, ..., 6 = Sunday

    start_time TIME NOT NULL,
    end_time TIME NOT NULL,

    subject_id UUID REFERENCES subjects(id),
    teacher_id UUID REFERENCES staff(id),

    room VARCHAR(100),
    period_type VARCHAR(50) DEFAULT 'class' CHECK (period_type IN (
        'class', 'break', 'assembly', 'lunch', 'other'
    )),

    notes TEXT,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_timetable_periods_timetable ON timetable_periods(timetable_id);
CREATE INDEX idx_timetable_periods_teacher ON timetable_periods(teacher_id);
CREATE INDEX idx_timetable_periods_subject ON timetable_periods(subject_id);
CREATE INDEX idx_timetable_periods_day ON timetable_periods(timetable_id, day_of_week);
```

---

## 10. Finance Tables

### 10.1 Fee Types Table

```sql
CREATE TABLE fee_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,

    name VARCHAR(100) NOT NULL,
    description TEXT,
    category VARCHAR(50) CHECK (category IN (
        'tuition', 'examination', 'facilities', 'activities', 'other'
    )),

    is_active BOOLEAN DEFAULT true,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_fee_types_tenant ON fee_types(tenant_id);
CREATE UNIQUE INDEX idx_fee_types_name
    ON fee_types(tenant_id, school_id, LOWER(name))
    WHERE is_active = true;
```

### 10.2 Fee Structures Table

```sql
CREATE TABLE fee_structures (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,

    name VARCHAR(255) NOT NULL,
    description TEXT,

    academic_year_id UUID REFERENCES academic_years(id),
    term_id UUID REFERENCES terms(id),
    class_id UUID REFERENCES classes(id),
    level VARCHAR(50),  -- e.g., 'jhs_1', 'shs_2'
    level_category VARCHAR(50) CHECK (level_category IN (
        'preschool', 'primary', 'jhs', 'shs'
    )),
    student_type VARCHAR(20) DEFAULT 'all' CHECK (student_type IN (
        'all', 'boarding', 'day'
    )),

    is_active BOOLEAN DEFAULT true,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by UUID,
    deleted_at TIMESTAMP
);

CREATE INDEX idx_fee_structures_tenant ON fee_structures(tenant_id);
CREATE INDEX idx_fee_structures_year_term ON fee_structures(academic_year_id, term_id);
CREATE INDEX idx_fee_structures_class ON fee_structures(class_id);
```

### 10.3 Fee Items Table

```sql
CREATE TABLE fee_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    fee_structure_id UUID NOT NULL REFERENCES fee_structures(id) ON DELETE CASCADE,
    fee_type_id UUID REFERENCES fee_types(id),

    name VARCHAR(255) NOT NULL,
    description TEXT,
    amount DECIMAL(12, 2) NOT NULL,
    is_optional BOOLEAN DEFAULT false,
    sequence INTEGER DEFAULT 0,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_fee_items_structure ON fee_items(fee_structure_id);
CREATE INDEX idx_fee_items_type ON fee_items(fee_type_id);
```

### 10.4 Invoices Table

```sql
CREATE TABLE invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,

    invoice_number VARCHAR(50) NOT NULL,
    student_id UUID NOT NULL REFERENCES students(id),
    fee_structure_id UUID REFERENCES fee_structures(id),

    academic_year_id UUID REFERENCES academic_years(id),
    term_id UUID REFERENCES terms(id),

    subtotal DECIMAL(12, 2) NOT NULL,
    discount_amount DECIMAL(12, 2) DEFAULT 0,
    scholarship_discount DECIMAL(12, 2) DEFAULT 0,
    tax_amount DECIMAL(12, 2) DEFAULT 0,
    total_amount DECIMAL(12, 2) NOT NULL,
    amount_paid DECIMAL(12, 2) DEFAULT 0,
    balance DECIMAL(12, 2) GENERATED ALWAYS AS (total_amount - amount_paid) STORED,

    currency VARCHAR(3) DEFAULT 'GHS',
    issue_date DATE,
    due_date DATE,

    status VARCHAR(20) DEFAULT 'draft' CHECK (status IN (
        'draft', 'issued', 'partial', 'paid', 'overdue', 'cancelled', 'write_off'
    )),

    notes TEXT,
    cancel_reason TEXT,
    cancelled_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by UUID,
    issued_by UUID,
    issued_at TIMESTAMP
);

CREATE UNIQUE INDEX idx_invoices_number
    ON invoices(tenant_id, invoice_number);
CREATE INDEX idx_invoices_student ON invoices(student_id);
CREATE INDEX idx_invoices_status ON invoices(tenant_id, status);
CREATE INDEX idx_invoices_fee_structure ON invoices(fee_structure_id);
CREATE INDEX idx_invoices_year_term ON invoices(academic_year_id, term_id);
```

### 10.5 Invoice Items Table

```sql
CREATE TABLE invoice_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    invoice_id UUID NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    fee_item_id UUID REFERENCES fee_items(id),

    description VARCHAR(255) NOT NULL,
    quantity INTEGER DEFAULT 1,
    unit_price DECIMAL(12, 2) NOT NULL,
    amount DECIMAL(12, 2) NOT NULL,

    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_invoice_items_invoice ON invoice_items(invoice_id);
```

### 10.6 Payments Table

```sql
CREATE TABLE payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,

    receipt_number VARCHAR(50) NOT NULL,
    transaction_reference VARCHAR(100),

    invoice_id UUID REFERENCES invoices(id),
    student_id UUID NOT NULL REFERENCES students(id),

    amount DECIMAL(12, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'GHS',

    payment_method VARCHAR(50) NOT NULL CHECK (payment_method IN (
        'cash', 'momo_mtn', 'momo_vodafone', 'momo_airteltigo',
        'bank_transfer', 'cheque', 'card', 'other'
    )),

    momo_phone VARCHAR(20),
    momo_transaction_id VARCHAR(100),
    momo_provider VARCHAR(20),

    bank_name VARCHAR(100),
    bank_reference VARCHAR(100),
    cheque_number VARCHAR(50),

    payer_name VARCHAR(255),
    payer_phone VARCHAR(20),
    payer_email VARCHAR(255),

    status VARCHAR(20) DEFAULT 'completed' CHECK (status IN (
        'pending', 'completed', 'failed', 'refunded', 'cancelled'
    )),

    payment_date DATE NOT NULL,
    is_voided BOOLEAN DEFAULT false,
    voided_at TIMESTAMP,
    voided_by UUID,
    void_reason TEXT,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by UUID,
    notes TEXT
);

CREATE UNIQUE INDEX idx_payments_receipt
    ON payments(tenant_id, receipt_number);
CREATE INDEX idx_payments_student ON payments(student_id);
CREATE INDEX idx_payments_invoice ON payments(invoice_id);
CREATE INDEX idx_payments_date ON payments(tenant_id, payment_date);
CREATE INDEX idx_payments_method ON payments(tenant_id, payment_method);
```

### 10.7 Scholarships Table

```sql
CREATE TABLE scholarships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,

    name VARCHAR(255) NOT NULL,
    code VARCHAR(50) NOT NULL,
    description TEXT,

    scholarship_type VARCHAR(50) NOT NULL CHECK (scholarship_type IN (
        'full', 'partial', 'merit', 'need_based', 'athletic', 'special'
    )),

    coverage_type VARCHAR(20) NOT NULL CHECK (coverage_type IN (
        'percentage', 'fixed_amount'
    )),
    coverage_value DECIMAL(12, 2) NOT NULL,

    applicable_fees JSONB,  -- List of fee type IDs or "all"
    max_recipients INTEGER,
    academic_year_id UUID REFERENCES academic_years(id),
    eligibility_criteria JSONB,  -- {"min_gpa": 3.5, "max_income": 5000}

    is_active BOOLEAN DEFAULT true,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by UUID,
    deleted_at TIMESTAMP
);

CREATE UNIQUE INDEX idx_scholarships_code
    ON scholarships(tenant_id, code)
    WHERE deleted_at IS NULL;
CREATE INDEX idx_scholarships_tenant ON scholarships(tenant_id);
CREATE INDEX idx_scholarships_year ON scholarships(academic_year_id);
```

### 10.8 Student Scholarships Table

```sql
CREATE TABLE student_scholarships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    scholarship_id UUID NOT NULL REFERENCES scholarships(id),
    student_id UUID NOT NULL REFERENCES students(id),
    academic_year_id UUID NOT NULL REFERENCES academic_years(id),

    awarded_by UUID REFERENCES users(id),
    awarded_at TIMESTAMP DEFAULT NOW(),

    status VARCHAR(20) DEFAULT 'active' CHECK (status IN (
        'active', 'suspended', 'revoked', 'expired'
    )),

    effective_from DATE NOT NULL,
    effective_to DATE,
    coverage_override DECIMAL(12, 2),  -- Override default coverage
    notes TEXT,

    revoked_at TIMESTAMP,
    revoked_by UUID REFERENCES users(id),
    revoke_reason TEXT,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_student_scholarships_unique
    ON student_scholarships(tenant_id, scholarship_id, student_id, academic_year_id)
    WHERE status = 'active';
CREATE INDEX idx_student_scholarships_student ON student_scholarships(student_id);
CREATE INDEX idx_student_scholarships_scholarship ON student_scholarships(scholarship_id);
CREATE INDEX idx_student_scholarships_year ON student_scholarships(academic_year_id);
```

### 10.9 Scholarship Applications Table

```sql
CREATE TABLE scholarship_applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    scholarship_id UUID NOT NULL REFERENCES scholarships(id),
    student_id UUID NOT NULL REFERENCES students(id),
    academic_year_id UUID NOT NULL REFERENCES academic_years(id),

    applied_at TIMESTAMP DEFAULT NOW(),

    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN (
        'pending', 'under_review', 'approved', 'rejected'
    )),

    supporting_documents JSONB,  -- [{name, url, type}]
    application_notes TEXT,

    reviewer_id UUID REFERENCES users(id),
    reviewed_at TIMESTAMP,
    reviewer_notes TEXT,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_scholarship_applications_unique
    ON scholarship_applications(scholarship_id, student_id, academic_year_id);
CREATE INDEX idx_scholarship_applications_student ON scholarship_applications(student_id);
CREATE INDEX idx_scholarship_applications_status ON scholarship_applications(tenant_id, status);
```

### 10.10 Credit Notes Table

```sql
CREATE TABLE credit_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,

    credit_note_number VARCHAR(50) NOT NULL,
    student_id UUID NOT NULL REFERENCES students(id),
    invoice_id UUID REFERENCES invoices(id),  -- Original invoice (optional)

    type VARCHAR(50) NOT NULL CHECK (type IN (
        'overpayment', 'fee_reduction', 'error_correction'
    )),

    amount DECIMAL(12, 2) NOT NULL,
    amount_used DECIMAL(12, 2) DEFAULT 0,
    balance DECIMAL(12, 2) GENERATED ALWAYS AS (amount - amount_used) STORED,

    reason TEXT NOT NULL,
    notes TEXT,

    status VARCHAR(20) DEFAULT 'draft' CHECK (status IN (
        'draft', 'issued', 'applied', 'partially_applied',
        'refunded', 'cancelled'
    )),

    -- Issue tracking
    issued_at TIMESTAMP,
    issued_by UUID REFERENCES users(id),

    -- Application tracking
    applied_to_invoice_id UUID REFERENCES invoices(id),
    applied_at TIMESTAMP,
    applied_by UUID REFERENCES users(id),

    -- Refund tracking
    refund_method VARCHAR(50),
    refund_reference VARCHAR(100),
    refunded_to VARCHAR(255),
    refunded_at TIMESTAMP,
    refunded_by UUID REFERENCES users(id),

    -- Cancellation tracking
    cancel_reason TEXT,
    cancelled_at TIMESTAMP,
    cancelled_by UUID REFERENCES users(id),

    -- Audit
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by UUID
);

CREATE UNIQUE INDEX idx_credit_notes_number
    ON credit_notes(tenant_id, credit_note_number);
CREATE INDEX idx_credit_notes_student ON credit_notes(student_id);
CREATE INDEX idx_credit_notes_status ON credit_notes(tenant_id, status);
CREATE INDEX idx_credit_notes_invoice ON credit_notes(invoice_id);
```

### 10.11 Finance Audit Log Table

```sql
CREATE TABLE finance_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

    entity_type VARCHAR(50) NOT NULL,  -- 'invoice', 'payment', 'credit_note', etc.
    entity_id UUID NOT NULL,
    action VARCHAR(100) NOT NULL,  -- 'created', 'status_change', 'payment_recorded', etc.

    old_values JSONB,  -- Previous state
    new_values JSONB,  -- New state
    metadata JSONB,    -- Additional context

    performed_by UUID REFERENCES users(id),
    performed_at TIMESTAMP DEFAULT NOW(),
    ip_address VARCHAR(45)
);

CREATE INDEX idx_finance_audit_entity ON finance_audit_log(entity_type, entity_id);
CREATE INDEX idx_finance_audit_tenant ON finance_audit_log(tenant_id);
CREATE INDEX idx_finance_audit_date ON finance_audit_log(tenant_id, performed_at);
```

---

## 11. Indexes & Performance

### 11.1 Critical Indexes for Subdomain Lookup

```sql
-- Fast tenant lookup by subdomain (CRITICAL for every request)
CREATE UNIQUE INDEX idx_tenants_subdomain_lookup
    ON tenants(LOWER(subdomain))
    WHERE deleted_at IS NULL AND status = 'active';

-- Include commonly needed fields to avoid table lookup
CREATE INDEX idx_tenants_subdomain_covering
    ON tenants(subdomain)
    INCLUDE (id, name, status, subscription_plan, features)
    WHERE deleted_at IS NULL;
```

### 11.2 Composite Indexes for Common Queries

```sql
-- Student list with filters
CREATE INDEX idx_students_list
    ON students(tenant_id, school_id, status, current_class_id, last_name);

-- Attendance lookup
CREATE INDEX idx_attendance_lookup
    ON student_attendance(tenant_id, class_id, date, student_id);

-- Exam scores lookup
CREATE INDEX idx_exam_scores_lookup
    ON exam_scores(tenant_id, exam_subject_id, student_id);

-- Invoice queries
CREATE INDEX idx_invoices_outstanding
    ON invoices(tenant_id, status, due_date)
    WHERE status IN ('issued', 'partial', 'overdue');
```

### 11.3 Partial Indexes for Performance

```sql
-- Only active students (most queries)
CREATE INDEX idx_students_active
    ON students(tenant_id, school_id, current_class_id)
    WHERE status = 'active' AND deleted_at IS NULL;

-- Only current term
CREATE INDEX idx_terms_current
    ON terms(tenant_id)
    WHERE is_current = true;

-- Active exams
CREATE INDEX idx_exams_active
    ON exams(tenant_id, term_id)
    WHERE status IN ('scheduled', 'in_progress') AND deleted_at IS NULL;

-- Only unpaid invoices
CREATE INDEX idx_invoices_unpaid
    ON invoices(tenant_id, student_id, balance)
    WHERE status IN ('issued', 'partial', 'overdue') AND balance > 0;
```

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | January 2026 | Harry McNinson | Initial version |
| 2.0 | January 2026 | Harry McNinson | Enhanced tenants table with subdomain, added RLS functions |
| 2.1 | January 2026 | Harry McNinson | Added exam tables, timetable tables, departments, school_holidays, score_change_logs |
| 2.2 | January 2026 | Harry McNinson | Added complete Finance tables: fee_types, fee_structures, fee_items, invoices, invoice_items, payments, scholarships, student_scholarships, scholarship_applications |
| 2.3 | January 2026 | Harry McNinson | Added credit_notes and finance_audit_log tables, write_off invoice status, RLS for new tables |
