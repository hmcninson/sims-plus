# SIMS Plus (School Information Management System Plus) - Technical Architecture Document

**Version:** 2.1  
**Date:** January 2026  
**Author:** Harry McNinson  
**Status:** Updated with Clear Shared Infrastructure Explanation

---

## Table of Contents

1. [Executive Summary: How Multi-Tenancy Works](#1-executive-summary-how-multi-tenancy-works)
2. [Infrastructure Overview](#2-infrastructure-overview)
3. [Multi-Tenant Subdomain Architecture](#3-multi-tenant-subdomain-architecture)
4. [Technology Stack](#4-technology-stack)
5. [DNS & SSL Configuration](#5-dns--ssl-configuration)
6. [Application Architecture](#6-application-architecture)
7. [Database Architecture](#7-database-architecture)
8. [Authentication & Authorization](#8-authentication--authorization)
9. [API Architecture](#9-api-architecture)
10. [Frontend Architecture](#10-frontend-architecture)
11. [Security & Data Isolation](#11-security--data-isolation)
12. [Scaling Strategy](#12-scaling-strategy)
13. [DevOps & Deployment](#13-devops--deployment)

---

## 1. Executive Summary: How Multi-Tenancy Works

### 1.1 The Key Concept: Shared Infrastructure, Isolated Data

**SIMS Plus uses a multi-tenant SaaS architecture where ALL schools share the same infrastructure but have completely isolated data.**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│                    🏫 100+ SCHOOLS, 1 INFRASTRUCTURE                    │
│                                                                         │
│    presec.simsplus.io    ──┐                                         │
│    achimota.simsplus.io  ──┼──►  SAME Servers  ──►  SAME Database    │
│    wesleyg.simsplus.io   ──┤     SAME Code         (isolated by RLS) │
│    newschool.simsplus.io ──┤                                         │
│    ... (unlimited)         ──┘                                         │
│                                                                         │
│    ✓ ONE set of servers     (not one per school)                       │
│    ✓ ONE database           (not one per school)                       │
│    ✓ ONE codebase           (not one per school)                       │
│    ✓ ONE SSL certificate    (wildcard covers all)                      │
│    ✓ ONE DNS record         (wildcard covers all)                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Common Misconception

| ❌ Wrong Understanding | ✅ Correct Understanding |
|------------------------|--------------------------|
| Each subdomain needs its own server | All subdomains point to the SAME server |
| Each school needs its own database | All schools share ONE database |
| Adding a school requires new infrastructure | Adding a school = 1 database row |
| 100 schools = 100× the cost | 100 schools ≈ same cost as 1 school |

### 1.3 What Makes Each School Unique?

Even though infrastructure is shared, each school has:

| Unique Element | How It Works |
|----------------|--------------|
| **Subdomain** | `presec.simsplus.io` - just a different URL, same server |
| **Branding** | Logo & colors stored in database, loaded dynamically |
| **Data** | Filtered by `tenant_id` column + Row-Level Security |
| **Users** | User accounts scoped to their tenant |

### 1.4 Cost Efficiency

```
❌ WRONG: Separate Infrastructure Per School
   ─────────────────────────────────────────
   100 schools × $50/server/month = $5,000/month
   100 schools × $20/database/month = $2,000/month
   Total: $7,000/month 😱

✅ CORRECT: Shared Infrastructure (Multi-Tenant)
   ─────────────────────────────────────────
   1 server cluster = $200-400/month
   1 database = $50-100/month
   Total: $250-500/month ✓
   
   Serves 100+ schools from SAME infrastructure!
```

---

## 2. Infrastructure Overview

### 2.1 Physical Architecture (What You Actually Deploy)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        YOUR ENTIRE INFRASTRUCTURE                        │
│                    (This serves ALL schools combined)                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│                         ┌─────────────────┐                              │
│                         │   Cloudflare    │                              │
│                         │  DNS + CDN + SSL│                              │
│                         │                 │                              │
│                         │ *.simsplus.io │ ← One wildcard DNS record    │
│                         └────────┬────────┘                              │
│                                  │                                       │
│                                  │ ALL subdomain traffic                 │
│                                  │ goes to same place                    │
│                                  ▼                                       │
│                         ┌─────────────────┐                              │
│                         │  Load Balancer  │ ← One load balancer          │
│                         │   (AWS ALB)     │                              │
│                         └────────┬────────┘                              │
│                                  │                                       │
│              ┌───────────────────┼───────────────────┐                   │
│              │                   │                   │                   │
│              ▼                   ▼                   ▼                   │
│       ┌───────────┐       ┌───────────┐       ┌───────────┐             │
│       │  Next.js  │       │  Next.js  │       │  FastAPI  │             │
│       │  Pod #1   │       │  Pod #2   │       │  Pod #1   │             │
│       └───────────┘       └───────────┘       └───────────┘             │
│              │                   │                   │                   │
│              └───────────────────┼───────────────────┘                   │
│                                  │                                       │
│                                  ▼                                       │
│                         ┌─────────────────┐                              │
│                         │   PostgreSQL    │ ← One database               │
│                         │   (with RLS)    │   All schools' data here     │
│                         │                 │   Isolated by tenant_id      │
│                         └─────────────────┘                              │
│                                                                          │
│                         ┌─────────────────┐                              │
│                         │     Redis       │ ← One cache                  │
│                         │    (Cache)      │                              │
│                         └─────────────────┘                              │
│                                                                          │
│                         ┌─────────────────┐                              │
│                         │    AWS S3       │ ← One storage bucket         │
│                         │   (Files)       │   Files organized by tenant  │
│                         └─────────────────┘                              │
│                                                                          │
├─────────────────────────────────────────────────────────────────────────┤
│  TOTAL MONTHLY COST: ~$250-500 (serves unlimited schools)               │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 What Happens When a School Visits Their Portal

```
┌─────────────────────────────────────────────────────────────────────────┐
│              REQUEST FLOW: presec.simsplus.io/students                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  STEP 1: DNS Resolution                                                  │
│  ────────────────────────                                                │
│  Browser: "What's the IP for presec.simsplus.io?"                     │
│  Cloudflare: "*.simsplus.io → 123.45.67.89" (your ONE server)         │
│                                                                          │
│  STEP 2: Request Hits Load Balancer                                      │
│  ──────────────────────────────────                                      │
│  Load Balancer receives request with Host: presec.simsplus.io         │
│  Routes to any available Next.js pod (they're all identical)            │
│                                                                          │
│  STEP 3: Subdomain Extraction (Next.js Middleware)                       │
│  ─────────────────────────────────────────────────                       │
│  Code extracts "presec" from the Host header                            │
│  Looks up tenant in database: SELECT * FROM tenants                     │
│                                WHERE subdomain = 'presec'               │
│  Finds: tenant_id = 'abc-123', name = 'Presec Legon'                    │
│                                                                          │
│  STEP 4: Tenant Context Set                                              │
│  ──────────────────────────                                              │
│  Database connection configured with: tenant_id = 'abc-123'             │
│  PostgreSQL RLS now active for this request                             │
│                                                                          │
│  STEP 5: Query Execution (Automatic Filtering)                           │
│  ─────────────────────────────────────────────                           │
│  Code runs: SELECT * FROM students                                       │
│                                                                          │
│  PostgreSQL RLS transforms it to:                                        │
│  SELECT * FROM students WHERE tenant_id = 'abc-123'                     │
│                                                                          │
│  STEP 6: Response                                                        │
│  ───────────────                                                         │
│  Only Presec's students returned                                        │
│  Page rendered with Presec's logo and branding                          │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Adding a New School

**Adding a new school does NOT require any new infrastructure:**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     ADDING A NEW SCHOOL                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  What you DON'T need to do:                                             │
│  ─────────────────────────────                                           │
│  ✗ Spin up new servers                                                  │
│  ✗ Create new database                                                  │
│  ✗ Configure new DNS records                                            │
│  ✗ Generate new SSL certificates                                        │
│  ✗ Deploy new code                                                      │
│                                                                          │
│  What you DO (it's just database inserts):                              │
│  ───────────────────────────────────────────                             │
│  1. INSERT INTO tenants (subdomain, name, ...)                          │
│     VALUES ('newschool', 'New School Academy', ...);                    │
│                                                                          │
│  2. INSERT INTO schools (tenant_id, name, ...)                          │
│     VALUES ('new-tenant-id', 'New School Academy', ...);                │
│                                                                          │
│  3. INSERT INTO users (tenant_id, email, role, ...)                     │
│     VALUES ('new-tenant-id', 'admin@newschool.edu.gh', 'admin', ...);   │
│                                                                          │
│  That's it! newschool.simsplus.io now works automatically.            │
│                                                                          │
│  Time to add new school: ~30 seconds                                    │
│  Additional infrastructure cost: $0                                     │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Multi-Tenant Subdomain Architecture

### 3.1 URL Structure

| URL | Purpose | Infrastructure Used |
|-----|---------|---------------------|
| `simsplus.io` | Marketing website | Same servers |
| `app.simsplus.io` | Generic login portal | Same servers |
| `api.simsplus.io` | API endpoint | Same servers |
| `presec.simsplus.io` | Presec's portal | Same servers |
| `achimota.simsplus.io` | Achimota's portal | Same servers |
| `{any-school}.simsplus.io` | Any school's portal | Same servers |

**All URLs resolve to the same infrastructure. The subdomain is just an identifier.**

### 3.2 How Wildcard DNS Works

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          WILDCARD DNS                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ONE DNS record handles ALL subdomains:                                 │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  Type: A                                                         │    │
│  │  Name: *                    (wildcard - matches anything)        │    │
│  │  Value: 123.45.67.89        (your ONE server IP)                │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  This single record means:                                               │
│                                                                          │
│  presec.simsplus.io      → 123.45.67.89                              │
│  achimota.simsplus.io    → 123.45.67.89                              │
│  wesleyg.simsplus.io     → 123.45.67.89                              │
│  newschool.simsplus.io   → 123.45.67.89                              │
│  anything.simsplus.io    → 123.45.67.89                              │
│                                                                          │
│  You NEVER need to add DNS records for new schools!                     │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.3 How Wildcard SSL Works

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         WILDCARD SSL CERTIFICATE                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ONE certificate secures ALL subdomains:                                │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  Certificate covers:                                             │    │
│  │  - simsplus.io                                                │    │
│  │  - *.simsplus.io    (wildcard - matches ANY subdomain)        │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  This single certificate secures:                                        │
│                                                                          │
│  🔒 https://presec.simsplus.io     ✓ Secure                          │
│  🔒 https://achimota.simsplus.io   ✓ Secure                          │
│  🔒 https://wesleyg.simsplus.io    ✓ Secure                          │
│  🔒 https://newschool.simsplus.io  ✓ Secure                          │
│  🔒 https://anything.simsplus.io   ✓ Secure                          │
│                                                                          │
│  You NEVER need new SSL certificates for new schools!                   │
│                                                                          │
│  Cost: FREE (Let's Encrypt) or included with Cloudflare                │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Technology Stack

### 4.1 Core Technologies

| Layer | Technology | Version | Shared? |
|-------|------------|---------|---------|
| **DNS/CDN** | Cloudflare | - | ✅ One account |
| **Frontend** | Next.js | 16.x | ✅ Same code |
| **Backend** | FastAPI | 0.110+ | ✅ Same code |
| **Database** | PostgreSQL | 16.x | ✅ One database |
| **Cache** | Redis | 7.x | ✅ One instance |
| **Storage** | AWS S3 | - | ✅ One bucket |
| **Container** | Docker + K8s | - | ✅ Shared cluster |

### 4.2 What's Shared vs. Isolated

```
┌─────────────────────────────────────────────────────────────────────────┐
│               SHARED INFRASTRUCTURE vs. ISOLATED DATA                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  SHARED (Same for all schools):          ISOLATED (Unique per school):  │
│  ──────────────────────────────          ───────────────────────────    │
│                                                                          │
│  ✅ Servers & Containers                 🔒 Student Records             │
│  ✅ Database Instance                    🔒 Staff Records               │
│  ✅ Application Code                     🔒 Financial Data              │
│  ✅ DNS Records                          🔒 Grades & Reports            │
│  ✅ SSL Certificates                     🔒 User Accounts               │
│  ✅ Load Balancer                        🔒 Attendance Records          │
│  ✅ Redis Cache                          🔒 Documents & Files           │
│  ✅ Monitoring & Logging                 🔒 School Settings             │
│  ✅ CI/CD Pipeline                       🔒 Branding (Logo, Colors)     │
│                                                                          │
│  💰 Cost: Fixed                          📈 Scales: With data only      │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 5. DNS & SSL Configuration

### 5.1 Complete DNS Setup (One-Time)

Configure these records in Cloudflare (or your DNS provider):

```
┌──────────┬──────────┬─────────────────────┬───────┬──────────────────────┐
│ Type     │ Name     │ Value               │ TTL   │ Purpose              │
├──────────┼──────────┼─────────────────────┼───────┼──────────────────────┤
│ A        │ @        │ <your-server-ip>    │ Auto  │ Root domain          │
│ A        │ www      │ <your-server-ip>    │ Auto  │ WWW subdomain        │
│ A        │ *        │ <your-server-ip>    │ Auto  │ ALL school subdomains│
│ A        │ api      │ <your-server-ip>    │ Auto  │ API endpoint         │
│ CNAME    │ status   │ statuspage.io       │ Auto  │ Status page          │
└──────────┴──────────┴─────────────────────┴───────┴──────────────────────┘

Total DNS records: 5 (covers unlimited schools)
```

### 5.2 SSL Certificate Setup (One-Time)

```bash
# Generate ONE wildcard certificate (covers all subdomains forever)
certbot certonly \
  --dns-cloudflare \
  --dns-cloudflare-credentials ~/.secrets/cloudflare.ini \
  -d simsplus.io \
  -d "*.simsplus.io"

# Auto-renewal runs automatically via cron
# You never need to do this again for new schools
```

---

## 6. Application Architecture

### 6.1 Next.js Middleware (Tenant Detection)

The middleware extracts the subdomain and sets tenant context:

```typescript
// middleware.ts
import { NextRequest, NextResponse } from 'next/server';

export async function middleware(request: NextRequest) {
  // Extract subdomain from URL
  const host = request.headers.get('host') || '';
  const subdomain = extractSubdomain(host);
  
  // No subdomain = marketing site
  if (!subdomain || subdomain === 'www') {
    return NextResponse.next();
  }
  
  // 'app' subdomain = generic login portal
  if (subdomain === 'app') {
    return NextResponse.next();
  }
  
  // School subdomain - validate it exists
  const tenant = await getTenantBySubdomain(subdomain);
  
  if (!tenant) {
    // School doesn't exist - show error page
    return NextResponse.redirect(new URL('/school-not-found', request.url));
  }
  
  // Valid school - add tenant info to headers for the app to use
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set('x-tenant-id', tenant.id);
  requestHeaders.set('x-tenant-subdomain', subdomain);
  
  return NextResponse.next({
    request: { headers: requestHeaders }
  });
}

function extractSubdomain(host: string): string | null {
  const hostname = host.split(':')[0];
  
  if (hostname.endsWith('.simsplus.io')) {
    return hostname.replace('.simsplus.io', '');
  }
  
  return null;
}

async function getTenantBySubdomain(subdomain: string) {
  // This query runs against the SHARED database
  // Returns the tenant record for this subdomain
  const response = await fetch(
    `${process.env.API_URL}/internal/tenants/${subdomain}`
  );
  return response.ok ? response.json() : null;
}
```

### 6.2 Tenant-Aware Page Component

```typescript
// app/(portal)/dashboard/page.tsx
import { getTenant } from '@/lib/tenant';

export default async function DashboardPage() {
  // Get current tenant from request headers (set by middleware)
  const tenant = await getTenant();
  
  // Fetch data - automatically filtered by tenant due to RLS
  const stats = await fetchDashboardStats();
  
  return (
    <div>
      {/* Shows school-specific logo */}
      <img src={tenant.logo} alt={tenant.name} />
      
      {/* Shows school name */}
      <h1>Welcome to {tenant.name}</h1>
      
      {/* Stats are automatically filtered to this school only */}
      <div>Total Students: {stats.studentCount}</div>
    </div>
  );
}
```

---

## 7. Database Architecture

### 7.1 Single Database, Multiple Tenants

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     ONE DATABASE FOR ALL SCHOOLS                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Database: sims_plus_prod                                               │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │ TABLE: tenants (one row per school)                             │    │
│  ├─────────────────────────────────────────────────────────────────┤    │
│  │ id       │ subdomain │ name                    │ status         │    │
│  │──────────│───────────│─────────────────────────│────────────────│    │
│  │ uuid-1   │ presec    │ Presec Legon            │ active         │    │
│  │ uuid-2   │ achimota  │ Achimota School         │ active         │    │
│  │ uuid-3   │ wesleyg   │ Wesley Girls' High      │ active         │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │ TABLE: students (all schools' students, filtered by tenant_id)  │    │
│  ├─────────────────────────────────────────────────────────────────┤    │
│  │ id       │ tenant_id │ name           │ class  │ school         │    │
│  │──────────│───────────│────────────────│────────│────────────────│    │
│  │ stu-1    │ uuid-1    │ Kwame Asante   │ JHS 2  │ Presec         │    │
│  │ stu-2    │ uuid-1    │ Ama Mensah     │ JHS 1  │ Presec         │    │
│  │ stu-3    │ uuid-2    │ Kofi Boateng   │ Form 3 │ Achimota       │    │
│  │ stu-4    │ uuid-3    │ Akua Darko     │ Form 2 │ Wesley Girls   │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  Row-Level Security (RLS) ensures:                                      │
│  - Presec users can ONLY see rows where tenant_id = 'uuid-1'           │
│  - Achimota users can ONLY see rows where tenant_id = 'uuid-2'         │
│  - etc.                                                                  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 7.2 Row-Level Security (RLS) Explained

```sql
-- Enable RLS on the students table
ALTER TABLE students ENABLE ROW LEVEL SECURITY;

-- Create policy: users can only see their own tenant's data
CREATE POLICY tenant_isolation ON students
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- Now, when Presec user runs:
SELECT * FROM students;

-- PostgreSQL AUTOMATICALLY transforms it to:
SELECT * FROM students WHERE tenant_id = 'presec-tenant-id';

-- They physically CANNOT see other schools' data
-- This is enforced at the database level, not application level
```

### 7.3 Tenants Table Schema

```sql
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Subdomain (used for routing)
    subdomain VARCHAR(63) UNIQUE NOT NULL,  -- e.g., 'presec'
    
    -- School info
    name VARCHAR(255) NOT NULL,
    
    -- Branding
    logo_url VARCHAR(500),
    primary_color VARCHAR(7) DEFAULT '#1B4F72',
    
    -- Status
    status VARCHAR(20) DEFAULT 'active',
    
    -- Subscription
    subscription_plan VARCHAR(50) DEFAULT 'starter',
    max_students INTEGER DEFAULT 100,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW()
);

-- Index for fast subdomain lookups (critical for every request)
CREATE INDEX idx_tenants_subdomain ON tenants(subdomain);
```

---

## 8. Authentication & Authorization

### 8.1 Tenant-Scoped Authentication

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    LOGIN FLOW (Tenant-Aware)                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  1. User visits: presec.simsplus.io/login                             │
│                                                                          │
│  2. Middleware extracts subdomain: "presec"                             │
│                                                                          │
│  3. Login page shows Presec branding (logo from database)               │
│                                                                          │
│  4. User submits: email + password                                       │
│                                                                          │
│  5. Backend validates:                                                   │
│     - Find user with this email WHERE tenant_id = presec's tenant       │
│     - Verify password                                                    │
│     - Generate JWT with tenant_id embedded                              │
│                                                                          │
│  6. JWT Token contains:                                                  │
│     {                                                                    │
│       "user_id": "user-uuid",                                           │
│       "tenant_id": "presec-tenant-uuid",   ← Locked to this tenant     │
│       "tenant_subdomain": "presec",                                     │
│       "roles": ["teacher"]                                               │
│     }                                                                    │
│                                                                          │
│  7. All subsequent requests:                                             │
│     - Verify JWT is valid                                                │
│     - Verify JWT's tenant matches the subdomain being accessed          │
│     - Set database context for RLS                                       │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 8.2 Cross-Tenant Access Prevention

```python
# FastAPI dependency that prevents cross-tenant access
async def verify_tenant_access(
    request: Request,
    token: JWT = Depends(get_current_token)
):
    # Get subdomain from request
    request_subdomain = request.headers.get('x-tenant-subdomain')
    
    # Get tenant from JWT
    token_subdomain = token.tenant_subdomain
    
    # CRITICAL: These must match
    if request_subdomain != token_subdomain:
        # Log security event
        logger.warning(f"Cross-tenant access attempt: {token_subdomain} tried to access {request_subdomain}")
        
        # Reject request
        raise HTTPException(
            status_code=403,
            detail="Access denied: Token not valid for this school"
        )
    
    return token
```

---

## 9. API Architecture

### 9.1 All Schools Use Same API

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     API ROUTING (Same Backend)                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  These all hit the SAME API servers:                                    │
│                                                                          │
│  presec.simsplus.io/api/v1/students   → Same FastAPI                  │
│  achimota.simsplus.io/api/v1/students → Same FastAPI                  │
│  wesleyg.simsplus.io/api/v1/students  → Same FastAPI                  │
│                                                                          │
│  The subdomain determines which tenant's data is returned:              │
│                                                                          │
│  presec.../students → Returns only Presec's students                    │
│  achimota.../students → Returns only Achimota's students                │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 9.2 FastAPI with Tenant Context

```python
# app/routers/students.py
from fastapi import APIRouter, Depends
from app.auth import get_current_tenant

router = APIRouter()

@router.get("/students")
async def list_students(
    tenant: Tenant = Depends(get_current_tenant),  # Auto-extracted from subdomain
    db: Session = Depends(get_db)
):
    # RLS is active - this query automatically filters by tenant
    students = db.query(Student).all()
    
    # Returns ONLY students for the current tenant
    return students
```

---

## 10. Frontend Architecture

### 10.1 Same Code, Different Branding

```typescript
// app/layout.tsx - Same code serves all schools
export default async function Layout({ children }) {
  // Get tenant from subdomain
  const tenant = await getTenant();
  
  return (
    <html>
      <head>
        {/* Dynamic title based on school */}
        <title>{tenant?.name || 'SIMS Plus'}</title>
        
        {/* Dynamic favicon */}
        <link rel="icon" href={tenant?.favicon || '/default-favicon.ico'} />
        
        {/* Dynamic brand colors */}
        <style>{`
          :root {
            --primary-color: ${tenant?.primaryColor || '#1B4F72'};
          }
        `}</style>
      </head>
      <body>
        {/* Dynamic logo in header */}
        <header>
          <img src={tenant?.logo || '/sims-logo.svg'} alt={tenant?.name} />
        </header>
        
        {children}
      </body>
    </html>
  );
}
```

---

## 11. Security & Data Isolation

### 11.1 Security Layers

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    MULTI-LAYER SECURITY                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Layer 1: Network Level                                                  │
│  ────────────────────────                                                │
│  - Cloudflare DDoS protection                                           │
│  - WAF rules                                                             │
│  - SSL/TLS encryption                                                    │
│                                                                          │
│  Layer 2: Application Level                                              │
│  ──────────────────────────                                              │
│  - JWT token validation                                                  │
│  - Tenant ID in token must match subdomain                              │
│  - All requests logged with tenant context                              │
│                                                                          │
│  Layer 3: Database Level (Most Critical)                                 │
│  ────────────────────────────────────────                                │
│  - Row-Level Security (RLS) policies                                    │
│  - Every query filtered by tenant_id                                    │
│  - Even if app has bug, database enforces isolation                     │
│                                                                          │
│  Result: Schools CANNOT access each other's data                        │
│          This is guaranteed at the database level                       │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 11.2 Data Isolation Test

```sql
-- Simulation: What happens if someone tries to bypass tenant filter?

-- Set context to Presec
SELECT set_tenant_context('presec-tenant-id');

-- Try to select ALL students (no WHERE clause)
SELECT * FROM students;

-- Result: ONLY Presec students returned
-- RLS automatically adds: WHERE tenant_id = 'presec-tenant-id'

-- Try to select Achimota students directly
SELECT * FROM students WHERE tenant_id = 'achimota-tenant-id';

-- Result: EMPTY (0 rows)
-- RLS overrides the WHERE clause with the current tenant

-- It is IMPOSSIBLE to see other tenants' data
```

---

## 12. Scaling Strategy

### 12.1 How to Scale (When Needed)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        SCALING STRATEGY                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  PHASE 1: Starting Out (1-100 schools)                                  │
│  ──────────────────────────────────────                                  │
│  - 1 server or small K8s cluster                                        │
│  - 1 PostgreSQL database                                                │
│  - Cost: ~$200-500/month                                                │
│                                                                          │
│  PHASE 2: Growing (100-500 schools)                                     │
│  ───────────────────────────────────                                     │
│  - Add more application pods (horizontal scaling)                       │
│  - Add PostgreSQL read replicas                                         │
│  - Cost: ~$500-1,500/month                                              │
│                                                                          │
│  PHASE 3: Large Scale (500-2000 schools)                                │
│  ────────────────────────────────────────                                │
│  - Multiple application pods                                            │
│  - PostgreSQL with read replicas                                        │
│  - Redis cluster for caching                                            │
│  - Cost: ~$1,500-5,000/month                                            │
│                                                                          │
│  PHASE 4: Enterprise Scale (2000+ schools)                              │
│  ──────────────────────────────────────────                              │
│  - Consider database sharding by region                                 │
│  - Multiple availability zones                                          │
│  - Cost: $5,000+/month                                                  │
│                                                                          │
│  Note: You can serve 1000+ schools from Phase 2 infrastructure!        │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 12.2 What You DON'T Do When Scaling

```
❌ WRONG: Create new infrastructure for each school
   "Presec is slow, let's give them their own server"
   
✅ CORRECT: Scale the shared infrastructure
   "System is slow, let's add more pods to the cluster"
   
The multi-tenant architecture means ALL schools benefit from scaling.
```

---

## 13. DevOps & Deployment

### 13.1 Deployment is Simple

```yaml
# deploy.yml - ONE deployment serves ALL schools
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sims-plus-app
spec:
  replicas: 3  # 3 pods serve ALL schools
  template:
    spec:
      containers:
      - name: nextjs
        image: simsplus/app:latest
        env:
        - name: DATABASE_URL
          value: "postgresql://..." # ONE database
        - name: BASE_DOMAIN
          value: "simsplus.io"
```

### 13.2 Adding a New School (No Deployment Needed)

```bash
# To add a new school, you DON'T run any deployment commands
# You just insert data into the database:

curl -X POST https://api.simsplus.io/admin/schools \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{
    "subdomain": "newschool",
    "name": "New School Academy",
    "admin_email": "admin@newschool.edu.gh"
  }'

# Response:
# {
#   "success": true,
#   "portal_url": "https://newschool.simsplus.io",
#   "message": "School created. Admin credentials sent via email."
# }

# That's it! The new school is live immediately.
# No servers to provision, no deployments to run.
```

---

## Summary: Key Points

| Aspect | Reality |
|--------|---------|
| **Servers per school** | 0 (all share same servers) |
| **Databases per school** | 0 (all share same database) |
| **DNS records per school** | 0 (wildcard covers all) |
| **SSL certs per school** | 0 (wildcard covers all) |
| **Deployments per school** | 0 (one codebase for all) |
| **Cost per new school** | ~$0 infrastructure, just DB rows |
| **Time to add school** | ~30 seconds (database insert) |
| **Data isolation** | 100% (enforced by PostgreSQL RLS) |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | January 2026 | Harry McNinson | Initial version |
| 2.0 | January 2026 | Harry McNinson | Added subdomain architecture |
| 2.1 | January 2026 | Harry McNinson | Clarified shared infrastructure concept |
