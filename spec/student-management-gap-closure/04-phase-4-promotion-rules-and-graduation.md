# Phase 4: Configurable Promotion Rules & Graduation Certificate

**Covers:** SM-041 (Configurable Promotion Rules), SM-043 (Graduation Certificate)
**Priority:** Should
**Estimated Effort:** 3–4 days
**New Tables:** 1
**New Endpoints:** 5
**New Tests:** ~16
**PDF Templates:** 1
**Dependencies:** Phase 1 (class history for graduation cert), Phase 2 (status change recording)

---

## 1. Database Schema

### 1.1 New Table: `promotion_rules`

Configurable criteria for auto-populating promotion batch entries. Rules can be set school-wide (class_id = NULL) or per-class. When a promotion batch preview is generated, these rules are evaluated against each student's academic and attendance records to pre-fill the promote/repeat decision.

| Column | Type | Nullable | Default | Constraints | Notes |
|--------|------|----------|---------|-------------|-------|
| `id` | UUID | No | `uuid4()` | PK | |
| `tenant_id` | UUID | No | | FK `tenants.id` CASCADE | TenantMixin |
| `school_id` | UUID | No | | FK `schools.id` CASCADE | |
| `academic_year_id` | UUID | No | | FK `academic_years.id` CASCADE | Rules are year-specific |
| `class_id` | UUID | Yes | | FK `classes.id` CASCADE | NULL = school-wide default rule |
| `min_average` | NUMERIC(5,2) | Yes | | | Minimum term average to auto-promote (e.g., 50.00) |
| `min_attendance_pct` | NUMERIC(5,2) | Yes | | | Minimum attendance percentage (e.g., 75.00) |
| `core_subject_pass_count` | INTEGER | Yes | | | Min number of core subjects student must pass |
| `pass_mark` | NUMERIC(5,2) | Yes | `50.00` | | What score constitutes a "pass" for core subject counting |
| `auto_apply` | BOOLEAN | No | `false` | | If true, auto-populate promotion entries with rule results |
| `is_active` | BOOLEAN | No | `true` | | Soft toggle without deleting the rule |
| `created_at` | TIMESTAMPTZ | No | `now()` | | |
| `updated_at` | TIMESTAMPTZ | No | `now()` | | |
| `deleted_at` | TIMESTAMPTZ | Yes | | | SoftDeleteMixin |

**UniqueConstraint:** `(school_id, academic_year_id, class_id, tenant_id)` — one rule per school/year/class combination.

**Indexes:**

```sql
-- Primary lookup: rules for a school and year
CREATE INDEX ix_pr_school_year ON promotion_rules(school_id, academic_year_id)
    WHERE deleted_at IS NULL AND is_active = true;

-- Unique active rule per school/year/class
CREATE UNIQUE INDEX uq_promo_rule
    ON promotion_rules(school_id, academic_year_id, COALESCE(class_id, '00000000-0000-0000-0000-000000000000'::uuid), tenant_id)
    WHERE deleted_at IS NULL;
```

**RLS Policy:**

```sql
ALTER TABLE promotion_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE promotion_rules FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_promotion_rules ON promotion_rules
    FOR ALL TO sims_app_user
    USING (tenant_id = get_current_tenant_id())
    WITH CHECK (tenant_id = get_current_tenant_id());

GRANT SELECT, INSERT, UPDATE, DELETE ON promotion_rules TO sims_app_user;
```

---

## 2. Alembic Migration

**File:** `backend/alembic/versions/20260326_0600_promotion_rules_graduation.py`

**Revision chain:** Revises `20260326_0500` (Phase 3).

```python
"""Add promotion rules table for configurable auto-promotion.

Revision ID: 20260326_0600
Revises: 20260326_0500
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "20260326_0600"
down_revision = "20260326_0500"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "promotion_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("academic_year_id", UUID(as_uuid=True), sa.ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False),
        sa.Column("class_id", UUID(as_uuid=True), sa.ForeignKey("classes.id", ondelete="CASCADE"), nullable=True),
        sa.Column("min_average", sa.Numeric(5, 2), nullable=True),
        sa.Column("min_attendance_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("core_subject_pass_count", sa.Integer, nullable=True),
        sa.Column("pass_mark", sa.Numeric(5, 2), nullable=True, server_default=sa.text("50.00")),
        sa.Column("auto_apply", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Indexes
    op.execute("""
        CREATE INDEX ix_pr_school_year ON promotion_rules(school_id, academic_year_id)
        WHERE deleted_at IS NULL AND is_active = true
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_promo_rule
        ON promotion_rules(
            school_id,
            academic_year_id,
            COALESCE(class_id, '00000000-0000-0000-0000-000000000000'::uuid),
            tenant_id
        )
        WHERE deleted_at IS NULL
    """)

    # RLS
    op.execute("ALTER TABLE promotion_rules ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE promotion_rules FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation_promotion_rules ON promotion_rules
        FOR ALL TO sims_app_user
        USING (tenant_id = get_current_tenant_id())
        WITH CHECK (tenant_id = get_current_tenant_id())
    """)
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON promotion_rules TO sims_app_user")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON promotion_rules")
    op.drop_table("promotion_rules")
```

---

## 3. SQLAlchemy Model

**File:** `backend/app/models/admissions/promotion.py`

Add alongside the existing `ClassPromotion` and `ClassPromotionEntry` models:

```python
class PromotionRule(Base, TenantMixin, SoftDeleteMixin):
    """Configurable criteria for auto-populating promotion batch entries.

    Rules define thresholds (min average, min attendance, core subject passes)
    that determine whether a student should be auto-promoted or auto-repeated.

    When auto_apply=True and a promotion batch preview is generated, the system
    evaluates each student against the applicable rule and pre-fills the
    action (promote/repeat) with a generated reason.

    Rules are scoped to a school + academic year. A class_id=NULL rule acts as
    the school-wide default. A class-specific rule overrides the default for
    students in that class.
    """
    __tablename__ = "promotion_rules"
    __table_args__ = (
        {"extend_existing": True},
    )

    school_id: Mapped[UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    academic_year_id: Mapped[UUID] = mapped_column(
        ForeignKey("academic_years.id", ondelete="CASCADE"),
        nullable=False,
    )
    class_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("classes.id", ondelete="CASCADE"),
        nullable=True,
        comment="NULL = school-wide default rule",
    )
    min_average: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="Minimum term average to auto-promote (e.g., 50.00)",
    )
    min_attendance_pct: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="Minimum attendance percentage (e.g., 75.00)",
    )
    core_subject_pass_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Min number of core subjects student must pass",
    )
    pass_mark: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        default=Decimal("50.00"),
        comment="What score constitutes a pass for core subject counting",
    )
    auto_apply: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="If true, auto-populate promotion entries with rule results on preview",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    school: Mapped["School"] = relationship("School", lazy="raise")
    academic_year: Mapped["AcademicYear"] = relationship("AcademicYear", lazy="raise")
    class_: Mapped[Optional["Class"]] = relationship("Class", lazy="raise")
```

**Imports to add:**

```python
from decimal import Decimal
from sqlalchemy import Boolean, Integer, Numeric
```

---

## 4. Pydantic Schemas

**File:** `backend/app/schemas/student.py` (or a new `backend/app/schemas/promotion.py`)

### 4.1 Promotion Rule Schemas

```python
class PromotionRuleCreate(BaseModel):
    """Request to create a promotion rule."""
    school_id: UUID
    academic_year_id: UUID
    class_id: UUID | None = None  # NULL = school-wide default
    min_average: float | None = Field(None, ge=0, le=100)
    min_attendance_pct: float | None = Field(None, ge=0, le=100)
    core_subject_pass_count: int | None = Field(None, ge=0)
    pass_mark: float | None = Field(50.0, ge=0, le=100)
    auto_apply: bool = False

    @model_validator(mode="after")
    def at_least_one_criterion(self) -> "PromotionRuleCreate":
        """Ensure at least one promotion criterion is set."""
        if (
            self.min_average is None
            and self.min_attendance_pct is None
            and self.core_subject_pass_count is None
        ):
            raise ValueError("At least one criterion (min_average, min_attendance_pct, or core_subject_pass_count) must be set")
        return self


class PromotionRuleUpdate(BaseModel):
    """Request to update a promotion rule."""
    min_average: float | None = Field(None, ge=0, le=100)
    min_attendance_pct: float | None = Field(None, ge=0, le=100)
    core_subject_pass_count: int | None = Field(None, ge=0)
    pass_mark: float | None = Field(None, ge=0, le=100)
    auto_apply: bool | None = None
    is_active: bool | None = None


class PromotionRuleResponse(BaseModel):
    """Response for a promotion rule."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    school_id: UUID
    academic_year_id: UUID
    class_id: UUID | None = None
    min_average: float | None = None
    min_attendance_pct: float | None = None
    core_subject_pass_count: int | None = None
    pass_mark: float | None = None
    auto_apply: bool
    is_active: bool
    created_at: str

    # Populated via eager loading
    class_name: str | None = None
    academic_year_name: str | None = None


class PromotionRuleEvaluationResult(BaseModel):
    """Result of evaluating a promotion rule against a student."""
    student_id: UUID
    student_name: str
    recommended_action: str  # "promote" or "repeat"
    reason: str
    term_average: float | None = None
    attendance_pct: float | None = None
    core_subjects_passed: int | None = None
    criteria_met: dict  # {"min_average": True, "min_attendance_pct": False, ...}
```

---

## 5. Service Layer

### 5.1 Promotion Rule CRUD

**File:** `backend/app/services/admissions/promotion_service.py`

Add these methods to the existing `PromotionService` class:

```python
# ─── Promotion Rules CRUD ────────────────────────────────────────

async def create_promotion_rule(
    self,
    tenant_id: UUID,
    school_id: UUID,
    academic_year_id: UUID,
    class_id: UUID | None = None,
    min_average: Decimal | None = None,
    min_attendance_pct: Decimal | None = None,
    core_subject_pass_count: int | None = None,
    pass_mark: Decimal | None = Decimal("50.00"),
    auto_apply: bool = False,
) -> PromotionRule:
    """Create a promotion rule for a school/year/class combination.

    Validates that no duplicate rule exists for the same combination.

    Args:
        class_id: NULL creates a school-wide default rule.
                  A specific class_id creates a class-specific override.
    """
    # Check for duplicate
    existing_stmt = (
        select(PromotionRule)
        .where(
            PromotionRule.tenant_id == tenant_id,
            PromotionRule.school_id == school_id,
            PromotionRule.academic_year_id == academic_year_id,
            PromotionRule.deleted_at.is_(None),
        )
    )
    if class_id:
        existing_stmt = existing_stmt.where(PromotionRule.class_id == class_id)
    else:
        existing_stmt = existing_stmt.where(PromotionRule.class_id.is_(None))

    result = await self.db.execute(existing_stmt)
    if result.scalar_one_or_none():
        target = f"class {class_id}" if class_id else "school-wide default"
        raise PromotionServiceError(
            f"A promotion rule already exists for this {target} and academic year",
            code="duplicate_rule",
        )

    rule = PromotionRule(
        tenant_id=tenant_id,
        school_id=school_id,
        academic_year_id=academic_year_id,
        class_id=class_id,
        min_average=min_average,
        min_attendance_pct=min_attendance_pct,
        core_subject_pass_count=core_subject_pass_count,
        pass_mark=pass_mark,
        auto_apply=auto_apply,
    )
    self.db.add(rule)
    await self.db.flush()
    await self.db.refresh(rule)
    return rule

async def list_promotion_rules(
    self,
    tenant_id: UUID,
    school_id: UUID,
    academic_year_id: UUID | None = None,
) -> list[PromotionRule]:
    """List promotion rules for a school, optionally filtered by year."""
    filters = [
        PromotionRule.tenant_id == tenant_id,
        PromotionRule.school_id == school_id,
        PromotionRule.deleted_at.is_(None),
    ]
    if academic_year_id:
        filters.append(PromotionRule.academic_year_id == academic_year_id)

    stmt = (
        select(PromotionRule)
        .options(
            joinedload(PromotionRule.class_),
            joinedload(PromotionRule.academic_year),
        )
        .where(*filters)
        .order_by(PromotionRule.class_id.asc().nulls_first())
    )
    result = await self.db.execute(stmt)
    return list(result.unique().scalars().all())

async def update_promotion_rule(
    self,
    tenant_id: UUID,
    rule_id: UUID,
    **fields,
) -> PromotionRule:
    """Update a promotion rule."""
    stmt = select(PromotionRule).where(
        PromotionRule.tenant_id == tenant_id,
        PromotionRule.id == rule_id,
        PromotionRule.deleted_at.is_(None),
    )
    result = await self.db.execute(stmt)
    rule = result.scalar_one_or_none()
    if not rule:
        raise PromotionServiceError("Promotion rule not found", code="rule_not_found")

    allowed = {"min_average", "min_attendance_pct", "core_subject_pass_count", "pass_mark", "auto_apply", "is_active"}
    for key, value in fields.items():
        if key in allowed and value is not None:
            setattr(rule, key, value)

    await self.db.flush()
    await self.db.refresh(rule)
    return rule

async def delete_promotion_rule(
    self,
    tenant_id: UUID,
    rule_id: UUID,
) -> bool:
    """Soft-delete a promotion rule."""
    from datetime import datetime, UTC
    stmt = select(PromotionRule).where(
        PromotionRule.tenant_id == tenant_id,
        PromotionRule.id == rule_id,
        PromotionRule.deleted_at.is_(None),
    )
    result = await self.db.execute(stmt)
    rule = result.scalar_one_or_none()
    if not rule:
        raise PromotionServiceError("Promotion rule not found", code="rule_not_found")

    rule.deleted_at = datetime.now(UTC)
    await self.db.flush()
    return True
```

### 5.2 Rule Evaluation Logic

Add to the existing `PromotionService`:

```python
async def evaluate_promotion_rules(
    self,
    tenant_id: UUID,
    school_id: UUID,
    academic_year_id: UUID,
    student_ids: list[UUID],
) -> list[dict]:
    """Evaluate promotion rules against a list of students.

    For each student:
    1. Find the applicable rule (class-specific first, then school-wide default)
    2. Query the student's term average (from term_reports for the last term of the year)
    3. Query the student's attendance percentage
    4. Query core subject pass count
    5. Determine recommended action (promote/repeat) based on ALL criteria

    A student is recommended for promotion only if they meet ALL
    configured criteria. If any criterion fails, they are recommended
    for repetition.

    Returns:
        List of evaluation results matching PromotionRuleEvaluationResult schema
    """
    # Load all active rules for this school/year
    rules = await self.list_promotion_rules(tenant_id, school_id, academic_year_id)
    if not rules:
        return []  # No rules = no auto-evaluation

    # Build rule lookup: class_id -> rule, None -> default
    rule_map: dict[UUID | None, PromotionRule] = {}
    for rule in rules:
        if rule.is_active:
            rule_map[rule.class_id] = rule

    default_rule = rule_map.get(None)

    results = []
    for student_id in student_ids:
        # Get student with class info
        student_stmt = (
            select(Student)
            .options(joinedload(Student.class_))
            .where(Student.tenant_id == tenant_id, Student.id == student_id)
        )
        student_result = await self.db.execute(student_stmt)
        student = student_result.unique().scalar_one_or_none()
        if not student:
            continue

        # Find applicable rule (class-specific overrides default)
        rule = rule_map.get(student.class_id, default_rule)
        if not rule:
            continue  # No applicable rule

        # Evaluate criteria
        criteria_met = {}
        term_average = None
        attendance_pct = None
        core_passed = None

        # Criterion 1: Term average
        if rule.min_average is not None:
            term_average = await self._get_student_term_average(
                tenant_id, student_id, academic_year_id
            )
            criteria_met["min_average"] = (
                term_average is not None and term_average >= float(rule.min_average)
            )

        # Criterion 2: Attendance percentage
        if rule.min_attendance_pct is not None:
            attendance_pct = await self._get_student_attendance_pct(
                tenant_id, student_id, academic_year_id
            )
            criteria_met["min_attendance_pct"] = (
                attendance_pct is not None and attendance_pct >= float(rule.min_attendance_pct)
            )

        # Criterion 3: Core subject pass count
        if rule.core_subject_pass_count is not None:
            core_passed = await self._get_core_subjects_passed(
                tenant_id, student_id, academic_year_id, float(rule.pass_mark or 50)
            )
            criteria_met["core_subject_pass_count"] = (
                core_passed is not None and core_passed >= rule.core_subject_pass_count
            )

        # Determine action
        all_met = all(criteria_met.values()) if criteria_met else False
        action = "promote" if all_met else "repeat"

        # Generate reason
        if all_met:
            reason = "Auto-promoted: all criteria met"
        else:
            failed = [k for k, v in criteria_met.items() if not v]
            reason = f"Auto-repeated: failed criteria — {', '.join(failed)}"

        results.append({
            "student_id": str(student_id),
            "student_name": student.full_name,
            "recommended_action": action,
            "reason": reason,
            "term_average": term_average,
            "attendance_pct": attendance_pct,
            "core_subjects_passed": core_passed,
            "criteria_met": criteria_met,
        })

    return results

# ─── Private Helpers for Rule Evaluation ────────────────────────

async def _get_student_term_average(
    self,
    tenant_id: UUID,
    student_id: UUID,
    academic_year_id: UUID,
) -> float | None:
    """Get the student's average from the most recent term report for the academic year.

    Queries the term_reports table for the latest report in the given academic year.
    Returns the average field, or None if no report exists.
    """
    from app.models.exam import TermReport
    from app.models.academic import Term

    stmt = (
        select(TermReport.average)
        .join(Term, Term.id == TermReport.term_id)
        .where(
            TermReport.tenant_id == tenant_id,
            TermReport.student_id == student_id,
            Term.academic_year_id == academic_year_id,
        )
        .order_by(Term.start_date.desc())
        .limit(1)
    )
    result = await self.db.execute(stmt)
    avg = result.scalar_one_or_none()
    return float(avg) if avg is not None else None

async def _get_student_attendance_pct(
    self,
    tenant_id: UUID,
    student_id: UUID,
    academic_year_id: UUID,
) -> float | None:
    """Calculate student's attendance percentage for the academic year.

    Queries student_attendance table, counts present/(present+absent+late) * 100.
    Returns None if no attendance records exist.
    """
    from app.models.attendance import StudentAttendance
    from app.models.academic import AcademicYear

    # Get year date range
    ay_stmt = select(AcademicYear).where(
        AcademicYear.tenant_id == tenant_id,
        AcademicYear.id == academic_year_id,
    )
    ay_result = await self.db.execute(ay_stmt)
    ay = ay_result.scalar_one_or_none()
    if not ay:
        return None

    total_stmt = (
        select(func.count(StudentAttendance.id))
        .where(
            StudentAttendance.tenant_id == tenant_id,
            StudentAttendance.student_id == student_id,
            StudentAttendance.date >= ay.start_date,
            StudentAttendance.date <= ay.end_date,
        )
    )
    total_result = await self.db.execute(total_stmt)
    total = total_result.scalar() or 0

    if total == 0:
        return None

    present_stmt = (
        select(func.count(StudentAttendance.id))
        .where(
            StudentAttendance.tenant_id == tenant_id,
            StudentAttendance.student_id == student_id,
            StudentAttendance.date >= ay.start_date,
            StudentAttendance.date <= ay.end_date,
            StudentAttendance.status.in_(["present", "late"]),  # Late counts as present
        )
    )
    present_result = await self.db.execute(present_stmt)
    present = present_result.scalar() or 0

    return round(present / total * 100, 2)

async def _get_core_subjects_passed(
    self,
    tenant_id: UUID,
    student_id: UUID,
    academic_year_id: UUID,
    pass_mark: float,
) -> int | None:
    """Count how many core subjects the student passed in the academic year.

    A "core subject" is identified by Subject.subject_type == 'core'.
    A "pass" means the student's exam score (or term report score) >= pass_mark.

    Queries ExamScore for exams in the academic year where the subject is core.
    Returns count of distinct subjects where the student scored >= pass_mark.
    """
    from app.models.exam import ExamScore, Exam, ExamSubject
    from app.models.academic import Subject, Term

    stmt = (
        select(func.count(func.distinct(ExamSubject.subject_id)))
        .join(Exam, Exam.id == ExamScore.exam_id)
        .join(ExamSubject, and_(
            ExamSubject.exam_id == ExamScore.exam_id,
            ExamSubject.subject_id == ExamScore.subject_id,
        ))
        .join(Subject, Subject.id == ExamSubject.subject_id)
        .join(Term, Term.id == Exam.term_id)
        .where(
            ExamScore.tenant_id == tenant_id,
            ExamScore.student_id == student_id,
            Term.academic_year_id == academic_year_id,
            Subject.subject_type == "core",
            ExamScore.total_score >= pass_mark,
        )
    )
    result = await self.db.execute(stmt)
    count = result.scalar()
    return count if count is not None else None
```

### 5.3 Integration with Promotion Batch Preview

Modify the existing `generate_preview()` method in `PromotionService`:

```python
async def generate_preview(self, tenant_id: UUID, batch_id: UUID) -> list[ClassPromotionEntry]:
    """Generate preview entries for a promotion batch.

    MODIFICATION: After generating entries, if auto_apply rules exist,
    evaluate them and pre-fill the action and reason fields.
    """
    # ... existing preview generation logic ...

    # NEW: Auto-apply rules if configured
    entries = await self._get_batch_entries(tenant_id, batch_id)
    student_ids = [entry.student_id for entry in entries]

    if student_ids:
        evaluations = await self.evaluate_promotion_rules(
            tenant_id=tenant_id,
            school_id=batch.school_id,
            academic_year_id=batch.academic_year_id,
            student_ids=student_ids,
        )

        # Build lookup
        eval_map = {UUID(e["student_id"]): e for e in evaluations}

        for entry in entries:
            evaluation = eval_map.get(entry.student_id)
            if evaluation:
                # Only auto-apply if the rule has auto_apply=True
                # (already filtered in evaluate_promotion_rules)
                if evaluation["recommended_action"] == "promote":
                    entry.action = PromotionAction.PROMOTE
                else:
                    entry.action = PromotionAction.REPEAT
                entry.reason = evaluation["reason"]
                # Mark as auto-applied for UI indication
                if not entry.metadata:
                    entry.metadata = {}
                entry.metadata["auto_applied"] = True
                entry.metadata["criteria_met"] = evaluation["criteria_met"]

        await self.db.flush()

    return entries
```

---

## 6. Graduation Certificate

### 6.1 PDF Template

**File:** `backend/app/templates/reports/graduation_certificate.html`

```html
<!-- A4 landscape, formal certificate layout -->
<div class="certificate graduation">
  <!-- Decorative border -->
  <div class="border-frame">

    <!-- School crest and name -->
    <div class="header">
      {% if school.logo_url %}
      <img src="{{ school.logo_url }}" class="crest" />
      {% endif %}
      <h1>{{ school.name }}</h1>
      <p class="subtitle">{{ school.address }}</p>
    </div>

    <!-- Certificate title -->
    <h2 class="title">CERTIFICATE OF GRADUATION</h2>

    <p class="cert-number">Certificate No: GC-{{ student.student_id }}-{{ graduation_date.strftime('%Y') }}</p>

    <!-- Main text -->
    <div class="body">
      <p>This is to certify that</p>
      <h3 class="student-name">{{ student.full_name }}</h3>
      <p>Student ID: {{ student.student_id }}</p>
      <p>Date of Birth: {{ student.date_of_birth.strftime('%d %B %Y') }}</p>

      <p class="completion-text">
        has successfully completed the
        <strong>{{ program_name }}</strong>
        programme at {{ school.name }}
      </p>

      {% if years_attended %}
      <p>Years of Attendance: {{ years_attended }}</p>
      {% endif %}

      <p>Date of Graduation: {{ graduation_date.strftime('%d %B %Y') }}</p>
    </div>

    <!-- Signature blocks -->
    <div class="signatures">
      <div class="signature-block">
        <div class="line"></div>
        <p>Headmaster/Headmistress</p>
      </div>
      <div class="signature-block">
        <div class="line"></div>
        <p>School Stamp</p>
      </div>
      <div class="signature-block">
        <div class="line"></div>
        <p>Date</p>
      </div>
    </div>
  </div>
</div>
```

### 6.2 Graduation Certificate Service Method

Add to `StudentLifecycleMixin` (in `lifecycle_service.py` from Phase 2):

```python
async def generate_graduation_certificate(
    self,
    tenant_id: UUID,
    student_id: UUID,
) -> BytesIO:
    """Generate a graduation certificate PDF for a graduated student.

    The certificate includes:
    - School crest and name
    - Student name, ID, date of birth
    - Programme completed (determined from last class level)
    - Years of attendance (from class history)
    - Date of graduation
    - Certificate number

    Raises:
        StudentServiceError: If student is not found or not graduated
    """
    # Load student
    student = await self._get_student_with_details(tenant_id, student_id)
    if not student:
        raise StudentServiceError("Student not found", code="student_not_found")

    if student.status != StudentStatus.GRADUATED:
        raise StudentServiceError(
            "Student is not graduated. Cannot generate graduation certificate.",
            code="student_not_graduated",
        )

    # Load school
    school_stmt = select(School).where(School.tenant_id == tenant_id, School.id == student.school_id)
    school = (await self.db.execute(school_stmt)).scalar_one_or_none()

    # Load class history for years attended
    class_history = await self.get_class_history(tenant_id, student_id)

    # Determine programme name from the last class
    program_name = "General Education"
    if class_history:
        last_class_name = class_history[0].class_.name if class_history[0].class_ else ""
        if "JHS" in last_class_name or "Junior" in last_class_name:
            program_name = "Junior High School"
        elif "SHS" in last_class_name or "Senior" in last_class_name:
            program_name = "Senior High School"
        elif "Primary" in last_class_name or "Grade" in last_class_name:
            program_name = "Primary School"
        elif "KG" in last_class_name or "Kindergarten" in last_class_name:
            program_name = "Kindergarten"
        elif "Nursery" in last_class_name:
            program_name = "Nursery"

    # Calculate years attended
    years_attended = None
    if class_history:
        first_year = class_history[-1].enrolled_date.year  # Oldest record
        last_year = class_history[0].left_date.year if class_history[0].left_date else date.today().year
        years_attended = f"{first_year} - {last_year}"

    # Get graduation date from status change
    graduation_change = await self._get_last_status_change(tenant_id, student_id, "graduated")
    graduation_date = graduation_change.effective_date if graduation_change else date.today()

    context = {
        "student": student,
        "school": school,
        "program_name": program_name,
        "years_attended": years_attended,
        "graduation_date": graduation_date,
    }

    pdf_service = PDFService()
    return pdf_service.render_template("reports/graduation_certificate.html", context)
```

---

## 7. API Endpoints

**File:** `backend/app/api/v1/endpoints/admissions/promotions.py` (existing file, add to existing router)

### 7.1 POST `/promotions/rules`

```python
@router.post("/promotions/rules", status_code=201)
async def create_promotion_rule(
    request: PromotionRuleCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(ValidatedUser),
    _: None = Depends(require_permissions("students.update")),
):
    """Create a promotion rule for a school/year/class.

    Professional and Enterprise plans only.
    """
    service = PromotionService(db)
    try:
        rule = await service.create_promotion_rule(
            tenant_id=user["tenant_id"],
            school_id=request.school_id,
            academic_year_id=request.academic_year_id,
            class_id=request.class_id,
            min_average=Decimal(str(request.min_average)) if request.min_average else None,
            min_attendance_pct=Decimal(str(request.min_attendance_pct)) if request.min_attendance_pct else None,
            core_subject_pass_count=request.core_subject_pass_count,
            pass_mark=Decimal(str(request.pass_mark)) if request.pass_mark else None,
            auto_apply=request.auto_apply,
        )
        return { ... }  # Map to PromotionRuleResponse
    except PromotionServiceError as e:
        raise HTTPException(status_code=400, detail=e.message)
```

### 7.2 GET `/promotions/rules`

```python
@router.get("/promotions/rules")
async def list_promotion_rules(
    school_id: UUID,
    academic_year_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(ValidatedUser),
    _: None = Depends(require_permissions("students.read")),
):
    """List promotion rules for a school, optionally filtered by academic year."""
```

### 7.3 PUT `/promotions/rules/{rule_id}`

```python
@router.put("/promotions/rules/{rule_id}")
async def update_promotion_rule(
    rule_id: UUID,
    request: PromotionRuleUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(ValidatedUser),
    _: None = Depends(require_permissions("students.update")),
):
    """Update a promotion rule."""
```

### 7.4 DELETE `/promotions/rules/{rule_id}`

```python
@router.delete("/promotions/rules/{rule_id}", status_code=204)
async def delete_promotion_rule(
    rule_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(ValidatedUser),
    _: None = Depends(require_permissions("students.update")),
):
    """Soft-delete a promotion rule."""
```

### 7.5 GET `/students/{student_id}/graduation-certificate`

**File:** `backend/app/api/v1/endpoints/students.py`

```python
@router.get("/students/{student_id}/graduation-certificate")
async def download_graduation_certificate(
    student_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(ValidatedUser),
    _: None = Depends(require_permissions("students.read")),
):
    """Generate and download a graduation certificate PDF.

    Only available for students with status='graduated'.
    Rate limited to 5 requests per minute.
    """
    service = StudentService(db)
    try:
        pdf_buffer = await service.generate_graduation_certificate(user["tenant_id"], student_id)
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=graduation_certificate_{student_id}.pdf"},
        )
    except StudentServiceError as e:
        raise HTTPException(status_code=400, detail=e.message)
```

---

## 8. Frontend Changes

### 8.1 TypeScript Types

**File:** `frontend/types/index.ts`

```typescript
// Promotion Rules
export interface PromotionRule {
  id: string;
  school_id: string;
  academic_year_id: string;
  class_id: string | null;
  min_average: number | null;
  min_attendance_pct: number | null;
  core_subject_pass_count: number | null;
  pass_mark: number | null;
  auto_apply: boolean;
  is_active: boolean;
  created_at: string;
  class_name: string | null;
  academic_year_name: string | null;
}

export interface PromotionRuleCreate {
  school_id: string;
  academic_year_id: string;
  class_id?: string | null;
  min_average?: number | null;
  min_attendance_pct?: number | null;
  core_subject_pass_count?: number | null;
  pass_mark?: number;
  auto_apply?: boolean;
}

export interface PromotionRuleEvaluation {
  student_id: string;
  student_name: string;
  recommended_action: "promote" | "repeat";
  reason: string;
  term_average: number | null;
  attendance_pct: number | null;
  core_subjects_passed: number | null;
  criteria_met: Record<string, boolean>;
}
```

### 8.2 Server Actions

**File:** `frontend/actions/admissions.action.ts`

```typescript
export async function getPromotionRules(schoolId: string, academicYearId?: string): Promise<ActionResult<PromotionRule[]>> { ... }
export async function createPromotionRule(data: PromotionRuleCreate): Promise<ActionResult<PromotionRule>> { ... }
export async function updatePromotionRule(ruleId: string, data: Partial<PromotionRule>): Promise<ActionResult<PromotionRule>> { ... }
export async function deletePromotionRule(ruleId: string): Promise<ActionResult<void>> { ... }
export async function downloadGraduationCertificate(studentId: string): Promise<ActionResult<Blob>> { ... }
```

### 8.3 Promotion Rules Settings Page

**File:** `frontend/app/(dashboard)/settings/promotion-rules/page.tsx`

**Layout:**
- Academic year selector dropdown at the top
- Table showing rules with columns: Scope (class name or "School Default"), Min Average, Min Attendance, Core Passes, Pass Mark, Auto-Apply toggle, Actions
- "Add Rule" button opens a dialog

**Add/Edit Rule Dialog:**
- Class selector (dropdown with "School-Wide Default" option)
- Min Average input (number, 0-100, optional)
- Min Attendance % input (number, 0-100, optional)
- Core Subject Pass Count input (integer, optional)
- Pass Mark input (number, 0-100, default 50)
- Auto-Apply toggle with explanation text: "When enabled, promotion entries will be auto-populated based on these rules during batch preview"
- Validation: at least one criterion must be set

### 8.4 Promotion Batch Preview Enhancement

**File:** `frontend/app/(dashboard)/admissions/promotions/promotions-management.tsx`

Modify the existing promotion entries table:
- Add a column or badge indicator for "Auto-Applied" entries (entries where `metadata.auto_applied === true`)
- Show criteria results in a tooltip or expandable row: term average, attendance %, core subjects passed, which criteria passed/failed
- Visual distinction: auto-applied entries have a subtle background color or icon
- Admin can still override any auto-applied entry

### 8.5 Graduation Certificate Button

**File:** `frontend/app/(dashboard)/students/[id]/page.tsx`

Add to the student detail page (or the download menu from Phase 2):
- "Generate Graduation Certificate" button
- Only visible when `student.status === "graduated"`
- Triggers PDF download via `downloadGraduationCertificate(studentId)`
- Loading state while generating

---

## 9. How Auto-Promotion Works (End-to-End Flow)

1. **Admin creates rules** at Settings > Promotion Rules
   - e.g., School-wide: min_average=50, min_attendance=75%, auto_apply=true
   - e.g., JHS 3 override: min_average=55, core_subjects_pass=4, pass_mark=50, auto_apply=true

2. **Admin creates a promotion batch** (existing flow)
   - Selects source academic year, source class

3. **Admin clicks "Generate Preview"** (existing flow, now enhanced)
   - System generates one entry per student (existing behavior)
   - **NEW:** System runs `evaluate_promotion_rules()` for all students
   - For JHS 3 students, the JHS 3-specific rule is used
   - For all other students, the school-wide default rule is used
   - Each entry's `action` is pre-filled (promote/repeat) based on rule evaluation
   - Each entry's `reason` explains why (e.g., "Auto-promoted: all criteria met" or "Auto-repeated: failed criteria — min_average, min_attendance_pct")
   - Entries are marked with `metadata.auto_applied = true`

4. **Admin reviews preview** (existing flow)
   - Auto-applied entries are visually marked in the UI
   - Admin can override any entry (change action, edit reason)
   - Admin can add notes

5. **Admin clicks "Execute"** (existing flow, unchanged)
   - Batch is executed as before
   - Status changes and class history records are created (Phase 1 integration)

---

## 10. Identifying Core Subjects

The auto-promotion rule evaluation needs to know which subjects are "core." There are two approaches:

### Option A: Use Existing `Subject.subject_type` Field

Check if the `subjects` table already has a `subject_type` column with a `core` value:

```python
# Query core subjects
Subject.subject_type == "core"
```

### Option B: Add `is_core` Boolean to `Subject`

If `subject_type` doesn't have a `core` value, add a simple boolean:

```sql
ALTER TABLE subjects ADD COLUMN is_core BOOLEAN DEFAULT false;
```

**Decision:** Check the current `Subject` model before implementation. If `subject_type` includes `core`, use Option A. Otherwise, add `is_core` via a small migration addendum.

**Developer action:** Read `backend/app/models/academic.py` and check the `Subject` model's `subject_type` field. The existing values in the `SubjectType` enum are: `core`, `elective`, `vocational`. **Option A is confirmed viable.**

---

## 11. Test Plan

### 11.1 `tests/test_promotion_rules.py`

| # | Test | Type | Description |
|---|------|------|-------------|
| 1 | `test_create_promotion_rule` | Unit | Create a rule, verify all fields |
| 2 | `test_create_duplicate_rule` | Unit | Reject duplicate rule for same school/year/class |
| 3 | `test_create_school_wide_default` | Unit | Create rule with class_id=None |
| 4 | `test_create_class_specific_override` | Unit | Create rule with specific class_id |
| 5 | `test_list_rules` | Unit | List rules for school, verify ordering |
| 6 | `test_list_rules_filter_by_year` | Unit | Academic year filter works |
| 7 | `test_update_rule` | Unit | Update min_average, auto_apply, verify |
| 8 | `test_delete_rule` | Unit | Soft-delete sets deleted_at |
| 9 | `test_at_least_one_criterion` | Validation | Reject rule with no criteria set |
| 10 | `test_evaluate_promote` | Integration | Student meeting all criteria → action=promote |
| 11 | `test_evaluate_repeat` | Integration | Student failing a criterion → action=repeat |
| 12 | `test_evaluate_class_override` | Integration | Class-specific rule overrides default |
| 13 | `test_auto_apply_in_preview` | Integration | Preview populates entries from rules when auto_apply=true |
| 14 | `test_rules_rls` | RLS | Tenant isolation enforced |
| 15 | `test_generate_graduation_cert` | Unit | PDF generated for graduated student |
| 16 | `test_graduation_cert_not_graduated` | Unit | Fails for non-graduated student |

---

## 12. Checklist

- [ ] Create migration `20260326_0600_promotion_rules_graduation.py`
- [ ] Run migration
- [ ] Add `PromotionRule` model to `models/admissions/promotion.py`
- [ ] Register model in `db/base.py`
- [ ] Add schemas (PromotionRuleCreate, Update, Response, EvaluationResult)
- [ ] Add rule CRUD methods to `PromotionService`
- [ ] Add `evaluate_promotion_rules()` to `PromotionService`
- [ ] Add helper methods: `_get_student_term_average`, `_get_student_attendance_pct`, `_get_core_subjects_passed`
- [ ] Modify `PromotionService.generate_preview()` to auto-apply rules
- [ ] Verify `Subject.subject_type` has `core` value (for core subject identification)
- [ ] Add `generate_graduation_certificate()` to `StudentLifecycleMixin`
- [ ] Create PDF template `templates/reports/graduation_certificate.html`
- [ ] Add 4 rule endpoints to `api/v1/endpoints/admissions/promotions.py`
- [ ] Add graduation cert endpoint to `api/v1/endpoints/students.py`
- [ ] Add `promotion_rules` to `TENANT_SCOPED_TABLES` in `tests/conftest.py`
- [ ] Add `promotion_rules` to `backend/scripts/verify_rls.py`
- [ ] Add `promotion_rules` to `backend/app/tasks/tenant_cleanup.py`
- [ ] Write `tests/test_promotion_rules.py` (~16 tests)
- [ ] Add TypeScript types to `frontend/types/index.ts`
- [ ] Add server actions to `frontend/actions/admissions.action.ts`
- [ ] Create promotion rules settings page at `/settings/promotion-rules`
- [ ] Enhance promotion batch preview UI with auto-applied indicators
- [ ] Add graduation certificate download button to student detail page
- [ ] Test rule evaluation with sample data
- [ ] Test auto-apply integration with promotion batch preview
- [ ] Test graduation certificate PDF generation
