# Phase 3: External Exams, Credits & Transcripts

**Phase:** MC-Sprint 3
**Depends on:** Phase 1 (curriculum profiles), partially Phase 2 (GPA calculation for transcripts)
**Parallel with:** External exam features are independent of score strategies

---

## Task List

| # | Task | Files | Est. |
|---|------|-------|------|
| 6.1 | Create Phase 3 migration | `backend/alembic/versions/20260320_0100_external_exams_and_credits.py` | 1d |
| 6.2 | Create ExternalExamRegistration model | `backend/app/models/curriculum.py` | 0.5d |
| 6.3 | Create StudentCreditAccumulation model | `backend/app/models/curriculum.py` | 0.5d |
| 6.4 | Create PredictedGrade model | `backend/app/models/curriculum.py` | 0.5d |
| 6.5 | Create ExternalExamService | `backend/app/services/curriculum/external_exam_service.py` | 1.5d |
| 6.6 | Create CreditService | `backend/app/services/curriculum/credit_service.py` | 1.5d |
| 6.7 | Create PredictedGradeService | `backend/app/services/curriculum/predicted_grade_service.py` | 0.75d |
| 6.8 | Create Phase 3 Pydantic schemas | `backend/app/schemas/curriculum.py` | 1d |
| 6.9 | Create external exam endpoints | `backend/app/api/v1/endpoints/curriculum/external_exams.py` | 1d |
| 6.10 | Create credit/GPA endpoints | `backend/app/api/v1/endpoints/curriculum/credits.py` | 0.5d |
| 6.11 | Create predicted grade endpoints | `backend/app/api/v1/endpoints/curriculum/predicted_grades.py` | 0.5d |
| 6.12 | Create WAEC export service | `backend/app/services/curriculum/external_exam_service.py` | 0.75d |
| 6.13 | Create Cambridge export service | `backend/app/services/curriculum/external_exam_service.py` | 0.75d |
| 6.14 | Create CSV results import parser | `backend/app/services/curriculum/external_exam_service.py` | 1d |
| 6.15 | Create transcript PDF template | `backend/app/templates/reports/transcript.html` | 1d |
| 6.16 | Create transcript generation service | `backend/app/services/curriculum/credit_service.py` | 1d |
| 6.17 | Update conftest.py for Phase 3 tables | `backend/tests/conftest.py` | 0.25d |

---

## 6.1 Phase 3 Migration

**File:** `backend/alembic/versions/20260320_0100_external_exams_and_credits.py`

**Revision chain:** `20260315_0100` -> `20260320_0100`

### New Enum

```sql
CREATE TYPE externalexamboard AS ENUM (
    'waec', 'cambridge_international', 'edexcel', 'college_board', 'ibo', 'other'
);
```

### New Tables

**`external_exam_registrations`:**

```sql
CREATE TABLE external_exam_registrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    school_id UUID REFERENCES schools(id) ON DELETE SET NULL,
    student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    exam_board externalexamboard NOT NULL,
    exam_session VARCHAR(20) NOT NULL,        -- e.g., "May 2026", "Nov 2026"
    candidate_number VARCHAR(50),             -- Board-assigned candidate number
    center_number VARCHAR(20),                -- Exam center number
    registration_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    CONSTRAINT chk_registration_status CHECK (registration_status IN ('pending', 'registered', 'confirmed')),
    subjects JSONB NOT NULL,                  -- Array of {subject_code, subject_name, level, paper_numbers}
    results JSONB,                            -- Array of {subject_code, grade, score, date_received}
    registration_date DATE,
    results_date DATE,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ                    -- SoftDeleteMixin
);

-- Use a PARTIAL unique index instead of a UNIQUE constraint because
-- this table uses SoftDeleteMixin. Without the WHERE clause, re-registering
-- a student after soft-deleting a prior registration would fail.
CREATE UNIQUE INDEX uq_external_exam_registration
    ON external_exam_registrations (tenant_id, student_id, exam_board, exam_session)
    WHERE deleted_at IS NULL;
```

**`student_credit_accumulations`:**

```sql
CREATE TABLE student_credit_accumulations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    school_id UUID REFERENCES schools(id) ON DELETE SET NULL,
    student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    curriculum_profile_id UUID NOT NULL REFERENCES curriculum_profiles(id) ON DELETE CASCADE,
    academic_year_id UUID NOT NULL REFERENCES academic_years(id) ON DELETE CASCADE,
    term_id UUID REFERENCES terms(id) ON DELETE SET NULL,
    subject_id UUID NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    credits_attempted NUMERIC(4,1) NOT NULL,
    credits_earned NUMERIC(4,1) NOT NULL,
    grade_points NUMERIC(5,2),               -- For GPA calculation
    weighted_grade_points NUMERIC(5,2),       -- For weighted GPA
    is_ap BOOLEAN DEFAULT false,              -- AP course flag
    is_honors BOOLEAN DEFAULT false,          -- Honors course flag
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX uq_student_credit
    ON student_credit_accumulations (
        tenant_id, student_id, subject_id, academic_year_id,
        COALESCE(term_id, '00000000-0000-0000-0000-000000000000'::UUID)
    );
```

**`predicted_grades`:**

```sql
CREATE TABLE predicted_grades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    school_id UUID REFERENCES schools(id) ON DELETE SET NULL,
    student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    subject_id UUID NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    academic_year_id UUID NOT NULL REFERENCES academic_years(id) ON DELETE CASCADE,
    term_id UUID REFERENCES terms(id) ON DELETE SET NULL,
    predicted_grade VARCHAR(10),
    target_grade VARCHAR(10),
    predicted_score NUMERIC(5,2),
    predicted_by UUID REFERENCES users(id) ON DELETE SET NULL,
    predicted_at TIMESTAMPTZ,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ                    -- SoftDeleteMixin
);

CREATE UNIQUE INDEX uq_predicted_grade
    ON predicted_grades (
        tenant_id, student_id, subject_id, academic_year_id,
        COALESCE(term_id, '00000000-0000-0000-0000-000000000000'::UUID)
    )
    WHERE deleted_at IS NULL;
```

### RLS + Indexes

Use `rls_helpers.enable_rls_for_table()` for all 3 tables (same as Phase 1 — do NOT write inline RLS DDL):

```python
from app.db.rls_helpers import enable_rls_for_table

for table_name in [
    "external_exam_registrations",
    "student_credit_accumulations",
    "predicted_grades",
]:
    enable_rls_for_table(op.get_bind(), table_name)
```

Add indexes:

```sql
-- Standard indexes
CREATE INDEX ix_external_exam_registrations_tenant_id ON external_exam_registrations(tenant_id);
CREATE INDEX ix_external_exam_registrations_student_id ON external_exam_registrations(student_id);
CREATE INDEX ix_student_credit_accumulations_tenant_id ON student_credit_accumulations(tenant_id);
CREATE INDEX ix_student_credit_accumulations_student_id ON student_credit_accumulations(student_id);
CREATE INDEX ix_predicted_grades_tenant_id ON predicted_grades(tenant_id);
CREATE INDEX ix_predicted_grades_student_id ON predicted_grades(student_id);

-- Composite indexes for common query patterns
CREATE INDEX ix_external_exam_registrations_tenant_student
    ON external_exam_registrations (tenant_id, student_id);
CREATE INDEX ix_student_credit_accumulations_tenant_student_profile
    ON student_credit_accumulations (tenant_id, student_id, curriculum_profile_id);
CREATE INDEX ix_predicted_grades_tenant_student_year
    ON predicted_grades (tenant_id, student_id, academic_year_id)
    WHERE deleted_at IS NULL;
```

### Downgrade

```python
def downgrade():
    from app.db.rls_helpers import disable_rls_for_table
    for table in ["external_exam_registrations", "student_credit_accumulations", "predicted_grades"]:
        disable_rls_for_table(op.get_bind(), table)

    op.execute("DROP INDEX IF EXISTS uq_external_exam_registration")
    op.execute("DROP INDEX IF EXISTS uq_student_credit")
    op.execute("DROP INDEX IF EXISTS uq_predicted_grade")
    op.drop_table("predicted_grades")
    op.drop_table("student_credit_accumulations")
    op.drop_table("external_exam_registrations")
    op.execute("DROP TYPE IF EXISTS externalexamboard")
```

---

## 6.2 ExternalExamRegistration Model

```python
class ExternalExamBoard(str, Enum):
    """External examination boards."""

    WAEC = "waec"
    CAMBRIDGE_INTERNATIONAL = "cambridge_international"
    EDEXCEL = "edexcel"
    COLLEGE_BOARD = "college_board"  # SAT/AP
    IBO = "ibo"                      # IB Organization
    OTHER = "other"


class ExternalExamRegistration(Base, TenantMixin, SoftDeleteMixin):
    """
    External examination registration and results tracking.

    Tracks student registrations for external exams (WAEC, Cambridge, IB, etc.)
    and stores imported results.
    """

    __tablename__ = "external_exam_registrations"
    # NOTE: Unique constraint is a PARTIAL unique index (WHERE deleted_at IS NULL)
    # created in the migration, not a table-level constraint, because this table
    # uses SoftDeleteMixin. See migration DDL for the actual index definition.
    __table_args__ = (
        # Partial unique index created in migration — not declarable via SA UniqueConstraint
    )

    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    exam_board: Mapped[ExternalExamBoard] = mapped_column(
        SQLEnum(ExternalExamBoard, name="externalexamboard",
                values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    exam_session: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="e.g., 'May 2026', 'Nov 2026'",
    )
    candidate_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    center_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    registration_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending",
        comment="pending, registered, confirmed",
    )
    subjects: Mapped[list] = mapped_column(
        JSONB, nullable=False,
        comment="Array of {subject_code, subject_name, level, paper_numbers}",
    )
    results: Mapped[list | None] = mapped_column(
        JSONB, nullable=True,
        comment="Array of {subject_code, grade, score, date_received}",
    )
    registration_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    results_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    student: Mapped["Student"] = relationship("Student", lazy="raise")
```

### JSONB `subjects` Schema

```json
[
  {
    "subject_code": "0580",
    "subject_name": "Mathematics",
    "level": "Extended",
    "paper_numbers": ["Paper 2", "Paper 4"]
  },
  {
    "subject_code": "0620",
    "subject_name": "Chemistry",
    "level": "Extended",
    "paper_numbers": ["Paper 2", "Paper 4", "Paper 6"]
  }
]
```

### JSONB `results` Schema

```json
[
  {
    "subject_code": "0580",
    "grade": "A*",
    "score": 95,
    "date_received": "2026-08-15"
  },
  {
    "subject_code": "0620",
    "grade": "A",
    "score": 88,
    "date_received": "2026-08-15"
  }
]
```

---

## 6.3 StudentCreditAccumulation Model

```python
class StudentCreditAccumulation(Base, TenantMixin):
    """
    Credit/unit tracking for American and IB curricula.

    Records credits attempted and earned per subject per term,
    with grade points for GPA calculation.
    """

    __tablename__ = "student_credit_accumulations"
    __table_args__ = (
        Index(
            "uq_student_credit",
            "tenant_id", "student_id", "subject_id", "academic_year_id",
            text("COALESCE(term_id, '00000000-0000-0000-0000-000000000000')"),
            unique=True,
        ),
    )

    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    curriculum_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("curriculum_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_years.id", ondelete="CASCADE"),
        nullable=False,
    )
    term_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("terms.id", ondelete="SET NULL"),
        nullable=True,
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"),
        nullable=False,
    )
    credits_attempted: Mapped[Decimal] = mapped_column(Numeric(4, 1), nullable=False)
    credits_earned: Mapped[Decimal] = mapped_column(Numeric(4, 1), nullable=False)
    grade_points: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True, comment="For GPA calculation",
    )
    weighted_grade_points: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True, comment="For weighted GPA",
    )
    is_ap: Mapped[bool] = mapped_column(Boolean, default=False)
    is_honors: Mapped[bool] = mapped_column(Boolean, default=False)
```

---

## 6.4 PredictedGrade Model

```python
class PredictedGrade(Base, TenantMixin, SoftDeleteMixin):
    """
    Predicted and target grades for university applications.

    Used by Cambridge and IB schools to track teacher-predicted
    grades and student target grades.
    """

    __tablename__ = "predicted_grades"
    # NOTE: Unique constraint is a PARTIAL unique index (WHERE deleted_at IS NULL)
    # created in the migration, not a table-level constraint, because this model
    # uses SoftDeleteMixin. See migration DDL for the actual index definition.
    __table_args__ = (
        # Partial unique index created in migration — not declarable via SA UniqueConstraint
    )

    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"),
        nullable=False,
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_years.id", ondelete="CASCADE"),
        nullable=False,
    )
    term_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("terms.id", ondelete="SET NULL"),
        nullable=True,
    )
    predicted_grade: Mapped[str | None] = mapped_column(String(10), nullable=True)
    target_grade: Mapped[str | None] = mapped_column(String(10), nullable=True)
    predicted_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    predicted_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    predicted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
```

---

## 6.5 ExternalExamService

**File:** `backend/app/services/curriculum/external_exam_service.py`

### Methods

| Method | Purpose |
|--------|---------|
| `create_registration(tenant_id, data)` | Register a student for external exam |
| `get_registration(tenant_id, registration_id)` | Get single registration |
| `list_registrations(tenant_id, filters)` | List with filters: student_id, exam_board, exam_session, status |
| `update_registration(tenant_id, registration_id, data)` | Update registration details |
| `bulk_register(tenant_id, data)` | Register up to 200 students at once |
| `import_results(tenant_id, registration_id, results)` | Add results to a registration |
| `import_results_csv(tenant_id, exam_board, exam_session, csv_data)` | Parse CSV and import results |
| `export_waec(tenant_id, exam_session)` | Generate WAEC registration export data |
| `export_cambridge(tenant_id, exam_session)` | Generate Cambridge registration export data |

### CSV Import Parser

The `import_results_csv` method accepts raw CSV text and parses it based on the exam board:

**WAEC Format (expected columns):**
```
CandidateNumber,SubjectCode,SubjectName,Grade,Score
WAE-123456,001,English Language,A1,85
WAE-123456,002,Mathematics,B2,72
```

**Cambridge Format (expected columns):**
```
CandidateNumber,CenterNumber,ComponentCode,ComponentName,Grade,Mark,MaxMark
0001,GH001,0580/22,Mathematics Paper 2,A*,95,100
0001,GH001,0580/42,Mathematics Paper 4,A*,92,100
```

**Parser returns:**
```python
@dataclass
class ImportResult:
    total_rows: int
    matched: int        # Matched to existing registrations
    unmatched: int      # Could not find student/registration
    errors: list[str]   # Row-level errors with line numbers
```

**Important:** Results import runs in preview mode first (dry run), showing matched/unmatched/errors. School admin must confirm before committing.

### CSV Import Security Constraints

The CSV import endpoint MUST enforce the following security measures:

1. **File size limit:** Max 5MB per CSV file. Reject larger files at the endpoint level with HTTP 413.
2. **Row count limit:** Max 2,000 rows per import (hard synchronous ceiling). Count rows during parsing; abort if exceeded. Imports >500 rows should use async processing (Celery) for better UX.
3. **CSV formula injection sanitization:** Strip leading `=`, `+`, `-`, `@`, `\t`, `\r` characters from all cell values. These characters can trigger formula execution in spreadsheet applications when the CSV is re-exported.
4. **Encoding validation:** Accept only UTF-8 encoded files. Reject files with invalid byte sequences.
5. **Column validation:** Reject files missing required columns for the specified exam board format.
6. **Accept `UploadFile`:** The endpoint should accept `UploadFile` (multipart form data), NOT raw string body. This follows the existing bulk operation pattern (e.g., student CSV import).

```python
@router.post(
    "/external-exams/results/import",
    dependencies=[Depends(require_permissions("exams.create"))],
)
async def import_results(
    file: UploadFile,
    exam_board: str = Query(...),
    exam_session: str = Query(...),
    dry_run: bool = Query(True),
    db: DatabaseSession,
    user: ValidatedUser,
    school: SchoolCtx,
):
    # Validate file size
    if file.size and file.size > 5 * 1024 * 1024:
        raise HTTPException(413, "File too large (max 5MB)")
    ...
```

---

## 6.6 CreditService

**File:** `backend/app/services/curriculum/credit_service.py`

### Methods

| Method | Purpose |
|--------|---------|
| `get_student_credits(tenant_id, student_id, profile_id)` | Get credit summary for a student |
| `get_student_gpa(tenant_id, student_id, profile_id)` | Calculate term + cumulative GPA |
| `recalculate_credits(tenant_id, student_id)` | Recalculate from term reports |
| `generate_transcript_data(tenant_id, student_id, profile_id)` | Full transcript data |
| `record_credit(tenant_id, data)` | Create/update a credit record |

### GPA Calculation

```python
async def get_student_gpa(
    self, tenant_id: uuid.UUID, student_id: uuid.UUID,
    profile_id: uuid.UUID,
    academic_year_id: uuid.UUID | None = None,
    term_id: uuid.UUID | None = None,
) -> dict:
    """
    Calculate GPA for a student.

    Unweighted GPA = sum(grade_points) / count(subjects)
    Weighted GPA = sum(weighted_grade_points) / count(subjects)

    Grade point mapping (American standard):
      A+ = 4.0, A = 4.0, A- = 3.7
      B+ = 3.3, B = 3.0, B- = 2.7
      C+ = 2.3, C = 2.0, C- = 1.7
      D+ = 1.3, D = 1.0, D- = 0.7
      F  = 0.0

    Weighted adjustments:
      AP courses: grade_point + 1.0 (max 5.0)
      Honors courses: grade_point + 0.5 (max 4.5)

    Returns:
        {
            "term_gpa": Decimal,
            "term_weighted_gpa": Decimal,
            "cumulative_gpa": Decimal,
            "cumulative_weighted_gpa": Decimal,
            "total_credits_attempted": Decimal,
            "total_credits_earned": Decimal,
            "honor_roll": bool,
        }
    """
```

### Transcript Data

```python
async def generate_transcript_data(
    self, tenant_id: uuid.UUID, student_id: uuid.UUID,
    profile_id: uuid.UUID,
) -> dict:
    """
    Generate complete transcript data for a student.

    Returns:
        {
            "student": { name, id, enrollment_date, ... },
            "school": { name, address, ... },
            "curriculum": { name, type },
            "terms": [
                {
                    "academic_year": "2025/2026",
                    "term": "Semester 1",
                    "subjects": [
                        {
                            "name": "Mathematics",
                            "code": "MATH101",
                            "credits_attempted": 1.0,
                            "credits_earned": 1.0,
                            "grade": "A",
                            "grade_points": 4.0,
                            "is_ap": false,
                        },
                        ...
                    ],
                    "term_gpa": 3.85,
                    "term_credits_earned": 6.0,
                },
                ...
            ],
            "cumulative_gpa": 3.82,
            "cumulative_weighted_gpa": 4.15,
            "total_credits_earned": 18.0,
            "graduation_credits_required": 24,
            "credits_remaining": 6.0,
        }
    """
```

---

## 6.8 Phase 3 Pydantic Schemas

**File:** `backend/app/schemas/curriculum.py` (append to existing)

```python
from decimal import Decimal
from datetime import datetime, date
from uuid import UUID
from pydantic import Field

# --- External Exam Registration ---

class ExternalExamSubject(BaseSchema):
    subject_code: str
    subject_name: str | None = None
    level: str | None = None
    paper_numbers: list[str] | None = None

class ExternalExamRegistrationCreate(BaseSchema):
    student_id: UUID
    exam_board: str  # waec, cambridge_international, edexcel, college_board, ibo, other
    exam_session: str  # e.g., "May 2026"
    subjects: list[ExternalExamSubject]
    class_section_id: UUID | None = None
    candidate_number: str | None = None
    center_number: str | None = None
    registration_date: date | None = None
    notes: str | None = None

class ExternalExamRegistrationUpdate(BaseSchema):
    subjects: list[ExternalExamSubject] | None = None
    candidate_number: str | None = None
    center_number: str | None = None
    registration_status: str | None = None  # pending, registered, confirmed
    registration_date: date | None = None
    notes: str | None = None

class ExternalExamRegistrationResponse(BaseSchema):
    id: UUID
    student_id: UUID
    exam_board: str
    exam_session: str
    subjects: list[ExternalExamSubject]
    candidate_number: str | None
    center_number: str | None
    registration_status: str
    registration_date: date | None
    results_date: date | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

class ExternalExamRegistrationListResponse(BaseSchema):
    items: list[ExternalExamRegistrationResponse]
    total: int
    page: int
    page_size: int
    pages: int

class BulkExternalExamRegistrationCreate(BaseSchema):
    registrations: list[ExternalExamRegistrationCreate] = Field(max_length=200)

# --- Results Import ---

class ResultsImportPreview(BaseSchema):
    """Returned from dry-run CSV import."""
    total_rows: int
    matched: int
    unmatched: int
    errors: list[str]
    preview_rows: list[dict]  # first 10 matched rows

class ResultsImportCommit(BaseSchema):
    """Returned after committing import."""
    imported: int
    skipped: int
    errors: list[str]

# --- Predicted Grades ---

class PredictedGradeCreate(BaseSchema):
    student_id: UUID
    subject_id: UUID
    academic_year_id: UUID
    term_id: UUID | None = None
    predicted_grade: str | None = None
    target_grade: str | None = None
    predicted_score: Decimal | None = None
    notes: str | None = None

class PredictedGradeUpdate(BaseSchema):
    predicted_grade: str | None = None
    target_grade: str | None = None
    predicted_score: Decimal | None = None
    notes: str | None = None

class PredictedGradeResponse(BaseSchema):
    id: UUID
    student_id: UUID
    subject_id: UUID
    academic_year_id: UUID
    term_id: UUID | None
    predicted_grade: str | None
    target_grade: str | None
    predicted_score: Decimal | None
    predicted_by: UUID | None
    predicted_at: datetime | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

class PredictedGradeListResponse(BaseSchema):
    items: list[PredictedGradeResponse]
    total: int
    page: int
    page_size: int
    pages: int

class BulkPredictedGradeCreate(BaseSchema):
    predictions: list[PredictedGradeCreate] = Field(max_length=200)

# --- Credits & GPA ---

class StudentCreditResponse(BaseSchema):
    id: UUID
    student_id: UUID
    subject_id: UUID
    curriculum_profile_id: UUID
    academic_year_id: UUID
    term_id: UUID | None
    credits_attempted: Decimal
    credits_earned: Decimal
    grade_points: Decimal | None
    weighted_grade_points: Decimal | None
    is_ap: bool
    is_honors: bool
    created_at: datetime

class StudentCreditListResponse(BaseSchema):
    items: list[StudentCreditResponse]
    total: int
    page: int
    page_size: int
    pages: int

class StudentGPAResponse(BaseSchema):
    student_id: UUID
    curriculum_profile_id: UUID
    cumulative_gpa: Decimal
    weighted_gpa: Decimal | None
    total_credits_earned: Decimal
    total_credits_attempted: Decimal
    total_quality_points: Decimal

class TranscriptSubjectRecord(BaseSchema):
    subject_name: str
    subject_code: str | None
    grade: str
    credits_attempted: Decimal
    credits_earned: Decimal
    grade_points: Decimal | None

class TranscriptTermRecord(BaseSchema):
    academic_year: str
    term: str | None
    subjects: list[TranscriptSubjectRecord]
    term_gpa: Decimal | None
    term_credits_earned: Decimal

class TranscriptResponse(BaseSchema):
    student_id: UUID
    student_name: str
    curriculum_profile: str
    academic_records: list[TranscriptTermRecord]
    cumulative_gpa: Decimal | None
    weighted_gpa: Decimal | None
    total_credits_earned: Decimal
    graduation_credits_required: Decimal | None
    credits_remaining: Decimal | None
    honors: list[str]
    generated_at: datetime
```

---

## 6.9 External Exam Endpoints

**File:** `backend/app/api/v1/endpoints/curriculum/external_exams.py`

| Method | Path | Permissions | Rate Limit |
|--------|------|-------------|------------|
| POST | `/curriculum/external-exams/registrations` | `curriculum.create` | 100/min |
| GET | `/curriculum/external-exams/registrations` | `curriculum.read` | 100/min |
| GET | `/curriculum/external-exams/registrations/{id}` | `curriculum.read` | 100/min |
| PUT | `/curriculum/external-exams/registrations/{id}` | `curriculum.update` | 100/min |
| POST | `/curriculum/external-exams/registrations/bulk` | `curriculum.create` | 10/min |
| POST | `/curriculum/external-exams/results/import` | `curriculum.create` | 10/min |
| DELETE | `/curriculum/external-exams/registrations/{id}` | `curriculum.delete` | 100/min |
| GET | `/curriculum/external-exams/export?board={board}` | `curriculum.read` | 5/min |

---

## 6.10 Credit/GPA Endpoints

| Method | Path | Permissions | Rate Limit |
|--------|------|-------------|------------|
| GET | `/curriculum/students/{student_id}/credits` | `curriculum.read` | 100/min |
| GET | `/curriculum/students/{student_id}/transcript` | `curriculum.read` | 100/min |
| GET | `/curriculum/students/{student_id}/gpa` | `curriculum.read` | 100/min |
| POST | `/curriculum/students/{student_id}/credits/recalculate` | `curriculum.create` | 10/min |

---

## 6.11 Predicted Grade Endpoints

| Method | Path | Permissions | Rate Limit |
|--------|------|-------------|------------|
| POST | `/curriculum/predicted-grades` | `curriculum.create` | 100/min |
| GET | `/curriculum/predicted-grades` | `curriculum.read` | 100/min |
| PUT | `/curriculum/predicted-grades/{id}` | `curriculum.update` | 100/min |
| DELETE | `/curriculum/predicted-grades/{id}` | `curriculum.delete` | 100/min |
| POST | `/curriculum/predicted-grades/bulk` | `curriculum.create` | 10/min |

---

## 6.15 Transcript PDF Template

**File:** `backend/app/templates/reports/transcript.html`

A formal transcript document with:

- School letterhead (logo, name, address)
- Student information (name, ID, enrollment date, expected graduation)
- Curriculum information (type, programme)
- Term-by-term breakdown:
  - Academic year and term name
  - Table: Subject | Code | Credits Attempted | Credits Earned | Grade | Points
  - Term GPA and Credits Earned
- Cumulative Summary:
  - Total Credits Earned / Required
  - Cumulative GPA (unweighted and weighted)
  - Credits Remaining for Graduation
- Official stamp/signature area
- "This is an official transcript" watermark

---

## 6.17 Test Infrastructure

Add to `TENANT_SCOPED_TABLES` in `conftest.py` (current count is **91**, will be **100** after all 3 phases):

```python
"external_exam_registrations",
"student_credit_accumulations",
"predicted_grades",
```

### Key Test Cases

**External Exam Tests:**
- Registration CRUD + RLS isolation
- Bulk registration with validation (max 200)
- CSV results import: valid file, invalid file, partial matches
- WAEC export format validation
- Cambridge export format validation
- Duplicate registration prevention (unique constraint)

**Credit/GPA Tests:**
- GPA calculation accuracy (known inputs -> expected GPA)
- Weighted GPA with AP/Honors bonuses
- Cumulative GPA across multiple terms
- Credit accumulation tracking
- Transcript data generation completeness
- Recalculation matches fresh calculation

**Predicted Grade Tests:**
- CRUD + RLS isolation
- Bulk set for a class
- Teacher permission validation (can only predict for assigned subjects)
- Unique constraint per student+subject+year+term
