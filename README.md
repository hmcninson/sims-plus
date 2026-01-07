# SIMS Plus

**School Information Management System Plus**

A comprehensive multi-tenant SaaS platform for managing schools - from preschools to Senior High Schools.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    SUBDOMAIN MULTI-TENANCY                       │
│                                                                  │
│   presec.simsplus.io    achimota.simsplus.io    etc...          │
│              │                    │                              │
│              └────────────────────┴────────────────┐             │
│                                                    ▼             │
│                         ┌──────────────────────────────┐         │
│                         │   Shared Application Cluster │         │
│                         └──────────────┬───────────────┘         │
│                                        ▼                         │
│                         ┌──────────────────────────────┐         │
│                         │   Shared PostgreSQL + RLS    │         │
│                         │   (Data isolated by tenant)  │         │
│                         └──────────────────────────────┘         │
└─────────────────────────────────────────────────────────────────┘
```

Each school gets a unique subdomain: `https://{school-code}.simsplus.io`

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Python 3.12, FastAPI, SQLAlchemy 2.0 (async), PostgreSQL 16 |
| **Frontend** | Next.js 16, React 19, TypeScript, Tailwind CSS v4, Shadcn/ui |
| **Mobile** | React Native (Phase 4) |
| **Infrastructure** | Docker, AWS (EKS, RDS, S3), Terraform |

## Quick Start

### Prerequisites

- Node.js 20+
- Python 3.12+
- Docker & Docker Compose
- PostgreSQL 16 (or use Docker)

### Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-org/sims-plus.git
   cd sims-plus
   ```

2. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Start with Docker Compose**
   ```bash
   docker-compose up -d
   ```

4. **Run database migrations**
   ```bash
   docker-compose exec backend alembic upgrade head
   ```

5. **Access the applications**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs
   - Adminer (DB GUI): `docker-compose --profile tools up adminer` then http://localhost:8080

### Manual Setup (Without Docker)

#### Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements-dev.txt

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload
```

#### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

## Project Structure

```
sims-plus/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── api/v1/endpoints/  # Route handlers
│   │   │   ├── auth.py        # Authentication
│   │   │   ├── academic.py    # Classes, subjects, grading
│   │   │   ├── students.py    # Student & guardian management
│   │   │   ├── schools.py     # School settings
│   │   │   └── users.py       # User management
│   │   ├── core/              # Security, config
│   │   ├── db/                # Database session
│   │   ├── models/            # SQLAlchemy models
│   │   ├── schemas/           # Pydantic schemas
│   │   ├── services/          # Business logic
│   │   └── middleware/        # Tenant, rate limiting
│   ├── alembic/               # Database migrations
│   └── tests/
├── frontend/                  # Next.js 16 frontend
│   ├── app/
│   │   ├── (auth)/            # Login, register, password reset
│   │   └── (dashboard)/       # Protected pages
│   │       ├── students/      # Student management
│   │       ├── classes/       # Class/section management
│   │       └── settings/      # School & academic settings
│   ├── components/
│   │   ├── ui/                # Shadcn components
│   │   ├── dashboard/         # Sidebar, header
│   │   └── academic/          # Academic settings
│   ├── actions/               # Server Actions (*.action.ts)
│   ├── lib/                   # Utilities
│   └── types/                 # TypeScript types
├── infrastructure/            # Terraform IaC
├── docs/                      # Documentation
└── docker-compose.yml
```

## Core Modules

| Module | Description | Status |
|--------|-------------|--------|
| **Multi-Tenancy** | Subdomain routing, tenant context, RLS | ✅ Complete |
| **Authentication** | Login, JWT, password reset, email verification | ✅ Complete |
| **Student Management** | Profiles, guardians, import/export, enrollment | ✅ Complete |
| **Academic** | Classes, sections, subjects, grading scales | ✅ Complete |
| **School Settings** | School profile, branding, student ID prefix | ✅ Complete |
| **Attendance** | Daily attendance, reports | 🔜 Next |
| **Finance** | Fees, invoices, Mobile Money payments | Planned |
| **Boarding** | Dormitories, exeats, roll calls | Planned |
| **Staff/HR** | Staff management, roles, payroll | Planned |

## API Documentation

The API follows REST conventions with OpenAPI 3.1 specification.

- **Development**: http://localhost:8000/docs
- **Base URL**: `/api/v1`

### Authentication

JWT Bearer tokens with refresh token rotation:
- Access token: 15 minutes
- Refresh token: 7 days

Tokens include tenant context to prevent cross-tenant access.

## Environment Variables

See [.env.example](.env.example) for all available options.

Key variables:
```env
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/sims_plus

# Security
SECRET_KEY=your-secret-key
ALGORITHM=HS256

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

---

## Development Progress

### Sprint 1: Project Setup & Core Models (Completed)

- [x] Project structure setup
- [x] Docker Compose configuration (PostgreSQL, Redis, apps)
- [x] FastAPI backend foundation
- [x] Next.js 16 frontend with Shadcn/ui + Tailwind v4
- [x] Database models (Tenant, User)
- [x] Alembic migrations configured and initial schema applied
- [x] GitHub Actions CI pipelines
- [x] Landing page with pricing section
- [x] Health check endpoint

### Sprint 2: Multi-Tenant Authentication (Completed)

- [x] **Subdomain Middleware**
  - Extract subdomain from request URL
  - Validate against reserved subdomains table
  - Lookup tenant and set context

- [x] **Tenant-Aware Authentication**
  - Login endpoint with tenant context
  - JWT tokens with tenant claims (tenant_id, subdomain, permissions, school_id)
  - Cross-tenant token rejection with `ValidatedTokenTenant` dependency

- [x] **School Branding**
  - Dynamic login page with school logo/colors
  - TenantProvider for frontend branding context

- [x] **School Onboarding**
  - Subdomain availability check API (`/tenant/check-subdomain`)
  - School registration endpoint (`/onboarding/register`)
  - Admin account creation with password validation

- [x] **Database Enhancements**
  - Reserved subdomains table with seed data
  - Row-Level Security policies for all tenant-scoped tables
  - Tenant context functions (`set_tenant_context`, `get_current_tenant_id`)

### Sprint 2.5: Security Hardening (Completed)

- [x] **Rate Limiting**
  - Redis-based sliding window algorithm
  - 5 req/min for auth, 20 req/min for subdomain check, 100 req/min default
  - Returns 429 with Retry-After header

- [x] **Audit Logging**
  - AuditService with separate DB connection (persists on transaction rollback)
  - Logs: login success/failure, account lockout, password changes

- [x] **Security Fixes**
  - SQL injection fix in migrations (parameterized queries)
  - CORS restricted to specific methods/headers
  - Password validation with special character requirement
  - Account lockout after 5 failed attempts (30 min)
  - Token blacklisting for logout
  - Password reset flow with email
  - Email verification endpoints
  - Security headers (CSP, HSTS, X-Frame-Options)

### Sprint 3-4: Academic Foundation (Completed)

- [x] Academic year and term setup with status management
- [x] Class/section management with student enrollment counts
- [x] Subject configuration (core, elective, vocational, extra)
- [x] Grading scales (WAEC, GPA, percentage, custom)
- [x] Assessment weight configuration
- [x] Academic settings (auto-promote, show positions, etc.)
- [x] Class-level categorization (Preschool, Primary, JHS, SHS)

### Sprint 4-5: Student Management (Completed)

- [x] Student CRUD with comprehensive profiles
- [x] Guardian management with relationship types
- [x] Student-guardian many-to-many linking
- [x] Student import from CSV/Excel with validation
- [x] Previous student ID support for data migration
- [x] Student ID auto-generation with school-specific prefix
- [x] Class and section enrollment
- [x] Student status tracking (active, graduated, transferred, etc.)
- [x] Gender-based enrollment statistics per class/section
- [x] Click-through from classes to filtered students

### Sprint 5-6: Attendance & Dashboards (Next)

- [ ] Daily attendance marking interface
- [ ] Attendance reports and analytics
- [ ] Student/class dashboards
- [ ] Dashboard widgets and statistics

---

## Pricing Tiers

| Tier | Monthly Price | Max Students | Features |
|------|---------------|--------------|----------|
| **Trial** | Free | 50 | 14 days, basic features |
| **Starter** | $50 | 300 | Core modules, 50 SMS/month |
| **Professional** | $150 | 1,000 | All modules, API access |
| **Enterprise** | Custom | Unlimited | Multi-school, custom domain |

---

## Documentation

Detailed documentation is available in the `/docs` folder:

| Document | Description |
|----------|-------------|
| `SIMS_Plus_Technical_Architecture_v2.1.md` | System architecture and tech stack |
| `SIMS_Plus_Requirements_Specification_v2.md` | Functional requirements |
| `SIMS_Plus_Database_Schema_v2.md` | Database design and RLS |
| `SIMS_Plus_API_Specification_v2.md` | API endpoints and patterns |
| `SIMS_Plus_Development_Roadmap_v2.md` | Sprint breakdown |
| `SIMS_Plus_Infrastructure_Overview.md` | Multi-tenant infrastructure |
| `SIMS_Plus_UI_UX_Wireframes_v2.md` | UI wireframes |
| `SIMS_Plus_User_Manual_v2.md` | User guide |

---

## Contributing

1. Create a feature branch from `develop`
2. Make your changes
3. Run tests: `pytest` (backend) / `npm test` (frontend)
4. Submit a pull request

### Development Guidelines

- Always include `tenant_id` in tenant-scoped queries
- Use Row-Level Security for data isolation
- Use Server Actions for data fetching (frontend)
- Follow formatting conventions:
  - Date: DD/MM/YYYY
  - Phone: International format
  - Currency: Configurable per tenant

---

## License

Proprietary - SIMS Plus © 2026

## Contact

- **Author**: Harry McNinson
- **Email**: support@simsplus.io
