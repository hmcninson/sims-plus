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
│   │   │   ├── academic.py    # Classes, subjects, grading, holidays
│   │   │   ├── students.py    # Student & guardian management
│   │   │   ├── staff.py       # Staff & department management
│   │   │   ├── attendance.py  # Student/staff attendance
│   │   │   ├── exams.py       # Exams, CA, score entry, report cards
│   │   │   ├── timetable.py   # Class timetables
│   │   │   ├── preschool.py   # Preschool module
│   │   │   ├── finance.py     # Fee structures, invoices, payments, scholarships
│   │   │   ├── schools.py     # School settings
│   │   │   └── users.py       # User management
│   │   ├── core/              # Security, config
│   │   ├── db/                # Database session
│   │   ├── models/            # SQLAlchemy models
│   │   ├── schemas/           # Pydantic schemas
│   │   ├── services/          # Business logic
│   │   ├── middleware/        # Tenant, rate limiting
│   │   └── templates/         # PDF templates
│   ├── alembic/               # Database migrations
│   └── tests/
├── frontend/                  # Next.js 16 frontend
│   ├── app/
│   │   ├── (auth)/            # Login, register, password reset
│   │   └── (dashboard)/       # Protected pages
│   │       ├── dashboard/     # Main dashboard
│   │       ├── calendar/      # School calendar
│   │       ├── students/      # Student management
│   │       ├── staff/         # Staff & departments
│   │       ├── classes/       # Class/section/timetable management
│   │       ├── attendance/    # Attendance marking & reports
│   │       ├── exams/         # Exams, CA, report cards
│   │       ├── preschool/     # Preschool module
│   │       ├── finance/       # Fee structures, invoices, payments, scholarships
│   │       └── settings/      # School & academic settings
│   ├── components/
│   │   ├── ui/                # Shadcn components
│   │   ├── dashboard/         # Sidebar, header
│   │   ├── academic/          # Academic settings
│   │   └── preschool/         # Preschool components
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
| **Staff Management** | Staff profiles, employment details, departments | ✅ Complete |
| **Attendance** | Student/staff attendance, bulk marking, reports | ✅ Complete |
| **Examinations** | Exam management, CA, score entry, grade calculations | ✅ Complete |
| **Report Cards** | Term report generation with grades and comments | ✅ Complete |
| **School Calendar** | Holidays, events, multi-view, drag-and-drop, export | ✅ Complete |
| **Timetables** | Class schedules, period management | ✅ Complete |
| **Preschool** | Observations, daily logs, assessments, reports | ✅ Complete |
| **Finance** | Fee structures, invoices, payments, scholarships | ✅ Complete |
| **Boarding** | Dormitories, exeats, roll calls | 🔜 Next |

## API Documentation

The API follows REST conventions with OpenAPI 3.1 specification.

- **Development**: http://localhost:8000/docs
- **Base URL**: `/api/v1`

### Key Endpoints

| Module | Endpoint | Description |
|--------|----------|-------------|
| Auth | `/auth/login` | User authentication |
| Students | `/students` | Student CRUD operations |
| Staff | `/staff` | Staff & department management |
| Academic | `/academic/classes` | Class/section management |
| Academic | `/academic/holidays` | School calendar events |
| Attendance | `/attendance` | Attendance marking & reports |
| Exams | `/exams` | Exam CRUD, score entry |
| Exams | `/exams/{id}/report-cards` | Report card generation |
| Timetable | `/timetable` | Class schedule management |
| Preschool | `/preschool` | Preschool observations & logs |
| Finance | `/finance/fee-structures` | Fee structure management |
| Finance | `/finance/invoices` | Invoice CRUD, bulk generate |
| Finance | `/finance/payments` | Payment recording & receipts |
| Finance | `/finance/scholarships` | Scholarship management & awards |
| Finance | `/finance/credit-notes` | Credit note management |
| Finance | `/finance/dashboard` | Finance statistics & overview |

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

# AWS S3 (for file uploads)
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_S3_BUCKET=your-bucket-name
```

---

## Development Progress

### Phase 1: Foundation (Completed)

#### Sprint 1-2: Core Infrastructure ✅
- [x] Project structure setup
- [x] Docker Compose configuration (PostgreSQL, Redis, apps)
- [x] FastAPI backend foundation
- [x] Next.js 16 frontend with Shadcn/ui + Tailwind v4
- [x] Database models (Tenant, User)
- [x] Alembic migrations configured
- [x] Multi-tenant subdomain architecture
- [x] Row-Level Security policies

#### Sprint 2.5: Security Hardening ✅
- [x] Rate limiting (Redis sliding window)
- [x] Audit logging service
- [x] Cross-tenant token validation
- [x] Account lockout protection
- [x] Password reset flow
- [x] Email verification

#### Sprint 3-4: Academic Foundation ✅
- [x] Academic year/term setup
- [x] Class/section management with student counts
- [x] Subject configuration
- [x] Grading scales (WAEC, GPA, custom)
- [x] Assessment weight configuration

#### Sprint 4-5: Student Management ✅
- [x] Student CRUD with profiles
- [x] Guardian management (multiple per student)
- [x] Student import from CSV/Excel
- [x] Class enrollment with section assignments
- [x] Student ID auto-generation

#### Sprint 5-6: Staff Management ✅
- [x] Staff CRUD with comprehensive profiles
- [x] Employment details and status tracking
- [x] Department management
- [x] Staff import functionality

#### Sprint 7-8: Attendance Module ✅
- [x] Daily student attendance with bulk operations
- [x] Staff attendance tracking
- [x] Attendance reports with weekly overview
- [x] CSV export for attendance data
- [x] Calendar-based school days calculation

#### Sprint 9-10: Examinations & Assessment ✅
- [x] Exam creation and scheduling
- [x] Continuous Assessment (CA) management
- [x] Score entry interface with validation
- [x] Grade calculations with configurable weights
- [x] Report card generation (PDF)
- [x] Exam analytics and insights
- [x] Score change audit logging

#### Sprint 11-12: Preschool & Calendar ✅
- [x] Preschool developmental domains and milestones
- [x] Student observations tracking
- [x] Daily activity logs (meals, naps, activities)
- [x] Preschool assessments and reports
- [x] School calendar with multi-view (Month, Week, Year)
- [x] Drag-and-drop event rescheduling
- [x] iCal and Google Calendar export
- [x] Class timetable management

### Phase 2: MVP Launch (In Progress)

#### Sprint 13-14: Finance Core ✅
- [x] Fee types and fee structure management
- [x] Invoice generation (single and bulk)
- [x] Payment recording (cash, Mobile Money, bank transfer)
- [x] Scholarship management with auto-discount application
- [x] Invoice sync with fee structure updates
- [x] Credit notes system (create, issue, apply, refund, cancel)
- [x] Auto-apply credit notes to oldest unpaid invoice
- [x] Student credit balance tracking
- [x] Finance dashboard with statistics
- [x] Invoice email with CC recipients
- [x] Finance audit logging

#### Sprint 15-16: Parent Portal (Next)
- [ ] Parent account access
- [ ] View children's records
- [ ] Online fee payment

### Phase 3: Enhancement (Planned)

- Boarding management
- Transport management
- Enrollment/admissions module
- Additional payment providers

### Phase 4: Scale & Mobile (Planned)

- Mobile apps (iOS/Android)
- Multi-curriculum support
- Advanced analytics
- White-label options

---

## Features Highlights

### School Calendar
- **Multi-View Display**: Month, Week, and Year views
- **Term Visualization**: Color-coded term backgrounds
- **School Days Counter**: Automatic calculation excluding weekends and holidays
- **Event Management**: Add, edit, and delete school events
- **Drag-and-Drop**: Easily reschedule events
- **Export**: Download as iCal or add to Google Calendar

### Examination System
- **Exam Setup**: Create exams with subjects, dates, and grading scales
- **Continuous Assessment**: Track CA scores throughout the term
- **Score Entry**: Bulk entry with validation and auto-save
- **Report Cards**: Generate PDF report cards with grades and comments
- **Analytics**: Class performance insights and grade distribution

### Preschool Module
- **Developmental Tracking**: Monitor progress across domains
- **Daily Logs**: Record meals, naps, and activities
- **Observations**: Document student behavior and milestones
- **Parent Reports**: Generate developmental progress reports

### Finance Module
- **Fee Structures**: Configure fees by class, level, or term
- **Invoices**: Generate single or bulk invoices for students
- **Invoice Sync**: Update draft invoices when fee structures change
- **Payments**: Record cash, Mobile Money, and bank transfers
- **Scholarships**: Manage full, partial, merit, and need-based scholarships
- **Auto-Discounts**: Scholarship discounts auto-applied at invoice generation
- **Credit Notes**: Overpayment, fee reduction, error correction management
- **Credit Workflow**: Draft → Issued → Applied/Refunded/Cancelled
- **Auto-Apply**: Credit notes auto-apply to oldest unpaid invoice
- **Student Credit Balance**: Track available credit per student
- **Dashboard**: Revenue tracking with collection statistics
- **Audit Trail**: Immutable logging for all finance transactions

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
| `PRESCHOOL_ARCHITECTURE.md` | Preschool module design |

---

## Contributing

1. Create a feature branch from `dev`
2. Make your changes
3. Run tests: `pytest` (backend) / `npm test` (frontend)
4. Run type checks: `npx tsc --noEmit` (frontend)
5. Submit a pull request

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
