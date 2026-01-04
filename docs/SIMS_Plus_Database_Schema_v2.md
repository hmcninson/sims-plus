# SIMS Plus (School Information Management System Plus) - Database Schema

**Version:** 2.0  
**Date:** January 2026  
**Author:** Harry McNinson  
**Status:** Updated with Subdomain Multi-Tenancy

---

## Table of Contents

1. [Schema Overview](#1-schema-overview)
2. [Multi-Tenancy Design](#2-multi-tenancy-design)
3. [Core Tables](#3-core-tables)
4. [User & Authentication Tables](#4-user--authentication-tables)
5. [Student Tables](#5-student-tables)
6. [Academic Tables](#6-academic-tables)
7. [Finance Tables](#7-finance-tables)
8. [Indexes & Performance](#8-indexes--performance)

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
| **Academic** | classes, subjects, exams, scores | Academic records |
| **Finance** | invoices, payments, fee_structures | Financial management |
| **Boarding** | dormitories, rooms, exeats | Boarding management |
| **Transport** | vehicles, routes, assignments | Transport management |
| **Audit** | audit_logs | Compliance & tracking |

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
        "white_label": false
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
    ('sandbox', 'Development - Sandbox'),
    ('beta', 'System - Beta testing'),
    ('alpha', 'System - Alpha testing'),
    ('internal', 'System - Internal use'),
    ('vpn', 'System - VPN'),
    ('git', 'System - Git repositories'),
    ('jenkins', 'System - CI/CD'),
    ('grafana', 'System - Monitoring'),
    ('kibana', 'System - Logging'),
    ('prometheus', 'System - Metrics');
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
ALTER TABLE scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE attendance ENABLE ROW LEVEL SECURITY;
ALTER TABLE dormitories ENABLE ROW LEVEL SECURITY;

-- Create tenant isolation policy (template)
CREATE POLICY tenant_isolation ON schools
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- Apply same policy to all tenant-scoped tables
-- (Repeat for each table)

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

-- Trigger to auto-set tenant_id on insert
CREATE OR REPLACE FUNCTION set_tenant_id()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.tenant_id IS NULL THEN
        NEW.tenant_id := get_current_tenant_id();
    END IF;
    
    IF NEW.tenant_id IS NULL THEN
        RAISE EXCEPTION 'tenant_id is required';
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to tables (example)
CREATE TRIGGER set_student_tenant_id
    BEFORE INSERT ON students
    FOR EACH ROW
    EXECUTE FUNCTION set_tenant_id();
```

### 2.4 Tenant Lookup Function

```sql
-- Function to get tenant by subdomain (used by application)
CREATE OR REPLACE FUNCTION get_tenant_by_subdomain(p_subdomain VARCHAR)
RETURNS TABLE (
    id UUID,
    subdomain VARCHAR,
    name VARCHAR,
    status VARCHAR,
    subscription_plan VARCHAR,
    features JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        t.id,
        t.subdomain,
        t.name,
        t.status,
        t.subscription_plan,
        t.features
    FROM tenants t
    WHERE t.subdomain = LOWER(p_subdomain)
      AND t.deleted_at IS NULL;
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
        'technical', 'vocational', 'tertiary'
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
    region VARCHAR(100) CHECK (region IN (
        'Greater Accra', 'Ashanti', 'Western', 'Central', 'Eastern',
        'Volta', 'Northern', 'Upper East', 'Upper West', 'Bono',
        'Bono East', 'Ahafo', 'Western North', 'Oti', 'North East', 'Savannah'
    )),
    gps_address VARCHAR(50),
    postal_address VARCHAR(255),
    
    -- Location (for transport)
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    
    -- Branding (can override tenant)
    logo_url VARCHAR(500),
    motto VARCHAR(500),
    vision TEXT,
    mission TEXT,
    
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
CREATE INDEX idx_schools_emis ON schools(emis_code) WHERE emis_code IS NOT NULL;
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
    staff_id UUID,  -- If user is staff
    guardian_id UUID,  -- If user is guardian/parent
    
    -- Settings
    settings JSONB DEFAULT '{}',
    notification_preferences JSONB DEFAULT '{}',
    
    -- Audit
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    deleted_at TIMESTAMP
);

-- Email must be unique per tenant
CREATE UNIQUE INDEX idx_users_tenant_email 
    ON users(tenant_id, LOWER(email)) 
    WHERE deleted_at IS NULL;

CREATE INDEX idx_users_tenant ON users(tenant_id);
CREATE INDEX idx_users_staff ON users(staff_id) WHERE staff_id IS NOT NULL;
CREATE INDEX idx_users_guardian ON users(guardian_id) WHERE guardian_id IS NOT NULL;
```

### 4.2 Roles Table

```sql
CREATE TABLE roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,  -- NULL = system role
    
    name VARCHAR(100) NOT NULL,
    slug VARCHAR(100) NOT NULL,
    description TEXT,
    is_system BOOLEAN DEFAULT false,  -- System roles can't be deleted
    
    permissions JSONB NOT NULL DEFAULT '[]',
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- System roles (tenant_id = NULL)
INSERT INTO roles (name, slug, description, is_system, permissions) VALUES
('Super Admin', 'super_admin', 'Full system access', true, '["*"]'),
('School Admin', 'school_admin', 'Full school access', true, '["school.*"]'),
('Academic Head', 'academic_head', 'Academic management', true, '["students.*", "academics.*", "exams.*", "reports.*"]'),
('Finance Officer', 'finance_officer', 'Financial management', true, '["finance.*", "reports.financial"]'),
('Teacher', 'teacher', 'Teaching staff', true, '["students.read", "attendance.*", "grades.*", "classes.own"]'),
('House Parent', 'house_parent', 'Boarding management', true, '["boarding.*", "students.read"]'),
('Parent', 'parent', 'Parent/Guardian access', true, '["children.read", "fees.own", "reports.own"]');
```

### 4.3 User Roles Table

```sql
CREATE TABLE user_roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    school_id UUID REFERENCES schools(id) ON DELETE CASCADE,  -- For school-specific roles
    
    assigned_at TIMESTAMP DEFAULT NOW(),
    assigned_by UUID REFERENCES users(id),
    expires_at TIMESTAMP,
    
    UNIQUE(user_id, role_id, school_id)
);

CREATE INDEX idx_user_roles_user ON user_roles(user_id);
CREATE INDEX idx_user_roles_role ON user_roles(role_id);
```

### 4.4 Refresh Tokens Table

```sql
CREATE TABLE refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    token_hash VARCHAR(255) NOT NULL,
    device_info JSONB,
    ip_address VARCHAR(45),
    
    issued_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,
    revoked_at TIMESTAMP,
    
    UNIQUE(token_hash)
);

CREATE INDEX idx_refresh_tokens_user ON refresh_tokens(user_id);
CREATE INDEX idx_refresh_tokens_expires ON refresh_tokens(expires_at);
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
    student_id VARCHAR(50) NOT NULL,  -- School-assigned ID
    admission_number VARCHAR(50),
    
    -- Personal Info
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    other_names VARCHAR(100),
    gender VARCHAR(10) NOT NULL CHECK (gender IN ('male', 'female')),
    date_of_birth DATE NOT NULL,
    
    -- Contact
    email VARCHAR(255),
    phone VARCHAR(20),
    
    -- National IDs
    ghana_card_number VARCHAR(20),
    birth_certificate_number VARCHAR(50),
    nhis_number VARCHAR(50),
    
    -- Photo
    photo_url VARCHAR(500),
    
    -- Address
    address_line1 VARCHAR(255),
    address_line2 VARCHAR(255),
    city VARCHAR(100),
    region VARCHAR(100),
    gps_address VARCHAR(50),
    
    -- Medical
    blood_group VARCHAR(5),
    medical_conditions TEXT,
    allergies TEXT,
    emergency_notes TEXT,
    
    -- Academic
    current_class_id UUID,
    current_section_id UUID,
    admission_date DATE NOT NULL,
    graduation_date DATE,
    previous_school VARCHAR(255),
    
    -- Status
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN (
        'active', 'inactive', 'withdrawn', 'transferred', 
        'graduated', 'suspended', 'expelled'
    )),
    status_reason TEXT,
    status_changed_at TIMESTAMP,
    
    -- Boarding
    is_boarding BOOLEAN DEFAULT false,
    dormitory_id UUID,
    
    -- Transport
    uses_transport BOOLEAN DEFAULT false,
    transport_route_id UUID,
    pickup_point_id UUID,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Audit
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by UUID,
    updated_by UUID,
    deleted_at TIMESTAMP
);

-- Student ID unique per tenant
CREATE UNIQUE INDEX idx_students_tenant_student_id 
    ON students(tenant_id, student_id) 
    WHERE deleted_at IS NULL;

CREATE INDEX idx_students_tenant_school ON students(tenant_id, school_id);
CREATE INDEX idx_students_status ON students(tenant_id, status);
CREATE INDEX idx_students_class ON students(current_class_id);
CREATE INDEX idx_students_name ON students(tenant_id, last_name, first_name);
CREATE INDEX idx_students_ghana_card ON students(ghana_card_number) 
    WHERE ghana_card_number IS NOT NULL;
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
    gps_address VARCHAR(50),
    
    -- Employment
    occupation VARCHAR(255),
    employer VARCHAR(255),
    work_phone VARCHAR(20),
    
    -- National ID
    ghana_card_number VARCHAR(20),
    
    -- Linked User Account
    user_id UUID REFERENCES users(id),
    
    -- Audit
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    deleted_at TIMESTAMP
);

CREATE INDEX idx_guardians_tenant ON guardians(tenant_id);
CREATE INDEX idx_guardians_phone ON guardians(tenant_id, phone_primary);
CREATE INDEX idx_guardians_user ON guardians(user_id) WHERE user_id IS NOT NULL;
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

## 6. Academic Tables

### 6.1 Classes Table

```sql
CREATE TABLE classes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    
    name VARCHAR(100) NOT NULL,  -- e.g., "JHS 2", "Class 6"
    code VARCHAR(20),
    level INTEGER,  -- Numeric level for ordering
    category VARCHAR(50),  -- primary, jhs, shs
    
    capacity INTEGER,
    
    is_active BOOLEAN DEFAULT true,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_classes_tenant_school ON classes(tenant_id, school_id);
```

### 6.2 Sections Table

```sql
CREATE TABLE sections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    class_id UUID NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    
    name VARCHAR(50) NOT NULL,  -- e.g., "A", "B", "Science"
    capacity INTEGER,
    
    class_teacher_id UUID REFERENCES staff(id),
    
    is_active BOOLEAN DEFAULT true,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_sections_class ON sections(class_id);
```

---

## 7. Finance Tables

### 7.1 Invoices Table

```sql
CREATE TABLE invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    
    -- Reference
    invoice_number VARCHAR(50) NOT NULL,
    
    -- Student
    student_id UUID NOT NULL REFERENCES students(id),
    
    -- Period
    academic_year_id UUID REFERENCES academic_years(id),
    term_id UUID REFERENCES terms(id),
    
    -- Amounts
    subtotal DECIMAL(12, 2) NOT NULL,
    discount_amount DECIMAL(12, 2) DEFAULT 0,
    tax_amount DECIMAL(12, 2) DEFAULT 0,
    total_amount DECIMAL(12, 2) NOT NULL,
    amount_paid DECIMAL(12, 2) DEFAULT 0,
    balance DECIMAL(12, 2) GENERATED ALWAYS AS (total_amount - amount_paid) STORED,
    
    -- Dates
    issue_date DATE NOT NULL,
    due_date DATE NOT NULL,
    
    -- Status
    status VARCHAR(20) DEFAULT 'draft' CHECK (status IN (
        'draft', 'issued', 'partial', 'paid', 'overdue', 'cancelled'
    )),
    
    -- Notes
    notes TEXT,
    
    -- Audit
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
CREATE INDEX idx_invoices_due_date ON invoices(due_date);
```

### 7.2 Payments Table

```sql
CREATE TABLE payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    
    -- Reference
    receipt_number VARCHAR(50) NOT NULL,
    transaction_reference VARCHAR(100),
    
    -- Links
    invoice_id UUID REFERENCES invoices(id),
    student_id UUID NOT NULL REFERENCES students(id),
    
    -- Amount
    amount DECIMAL(12, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'GHS',
    
    -- Payment Method
    payment_method VARCHAR(50) NOT NULL CHECK (payment_method IN (
        'cash', 'momo_mtn', 'momo_vodafone', 'momo_airteltigo',
        'bank_transfer', 'cheque', 'card', 'other'
    )),
    
    -- MoMo Details
    momo_phone VARCHAR(20),
    momo_transaction_id VARCHAR(100),
    momo_provider VARCHAR(20),
    
    -- Bank Details
    bank_name VARCHAR(100),
    bank_reference VARCHAR(100),
    
    -- Payer Info
    payer_name VARCHAR(255),
    payer_phone VARCHAR(20),
    
    -- Status
    status VARCHAR(20) DEFAULT 'completed' CHECK (status IN (
        'pending', 'completed', 'failed', 'refunded', 'cancelled'
    )),
    
    -- Dates
    payment_date DATE NOT NULL,
    
    -- Audit
    created_at TIMESTAMP DEFAULT NOW(),
    created_by UUID,
    notes TEXT
);

CREATE UNIQUE INDEX idx_payments_receipt 
    ON payments(tenant_id, receipt_number);
CREATE INDEX idx_payments_student ON payments(student_id);
CREATE INDEX idx_payments_invoice ON payments(invoice_id);
CREATE INDEX idx_payments_date ON payments(tenant_id, payment_date);
CREATE INDEX idx_payments_momo ON payments(momo_transaction_id) 
    WHERE momo_transaction_id IS NOT NULL;
```

---

## 8. Indexes & Performance

### 8.1 Critical Indexes for Subdomain Lookup

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

### 8.2 Composite Indexes for Common Queries

```sql
-- Student list with filters
CREATE INDEX idx_students_list 
    ON students(tenant_id, school_id, status, current_class_id, last_name);

-- Attendance lookup
CREATE INDEX idx_attendance_lookup 
    ON student_attendance(tenant_id, class_id, date, student_id);

-- Invoice queries
CREATE INDEX idx_invoices_outstanding 
    ON invoices(tenant_id, status, due_date) 
    WHERE status IN ('issued', 'partial', 'overdue');

-- Payment reconciliation
CREATE INDEX idx_payments_reconcile 
    ON payments(tenant_id, payment_date, payment_method, status);
```

### 8.3 Partial Indexes for Performance

```sql
-- Only active students (most queries)
CREATE INDEX idx_students_active 
    ON students(tenant_id, school_id, current_class_id) 
    WHERE status = 'active' AND deleted_at IS NULL;

-- Only current term
CREATE INDEX idx_terms_current 
    ON terms(tenant_id) 
    WHERE is_current = true;

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
| 2.0 | January 2026 | Harry McNinson | Enhanced tenants table with subdomain, added reserved_subdomains, RLS functions |
