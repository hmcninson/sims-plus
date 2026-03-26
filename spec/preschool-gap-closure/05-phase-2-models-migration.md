# Phase 2: Models & Migration — Enhancement & Integration

**Sprint:** 21
**Depends on:** Phase 1 complete (`20260328_0100_preschool_phase1`)
**Parallel with:** Phase 2 Services & Endpoints (doc 06), Phase 2 Frontend (doc 07)

---

## Task List

| # | Task | Files | Est. |
|---|------|-------|------|
| 5.1 | Create LearningStory model | `backend/app/models/preschool.py` | 0.25d |
| 5.2 | Create ExtendedCareSession model | `backend/app/models/preschool.py` | 0.25d |
| 5.3 | Create ClassCaregiverRatio model | `backend/app/models/preschool.py` | 0.15d |
| 5.4 | Add columns to PreschoolReport | `backend/app/models/preschool.py` | 0.15d |
| 5.5 | Create Alembic migration | `backend/alembic/versions/20260330_0100_preschool_phase2.py` | 0.75d |
| 5.6 | Update test infrastructure | `backend/tests/conftest.py` | 0.1d |

---

## 5.1 LearningStory Model

**File:** `backend/app/models/preschool.py` (append after Phase 1 models)

```python
class LearningStory(Base, TenantMixin, SoftDeleteMixin):
    """
    Portfolio entry / learning story (Reggio Emilia approach).

    A curated narrative that links multiple observations, spans multiple
    learning areas, and includes rich media. Think of it as a teacher's
    crafted story about a child's learning journey on a particular topic.

    Different from ProgressObservation: observations are point-in-time notes,
    learning stories are curated narratives that aggregate observations.
    """

    __tablename__ = "learning_stories"

    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    term_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("terms.id", ondelete="SET NULL"),
        nullable=True,
        comment="Term this story relates to (optional)",
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Story title, e.g., 'Building a Castle Together'",
    )
    narrative: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="The teacher's narrative describing the learning experience",
    )
    learning_area_ids: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="UUIDs of related learning areas",
    )
    skill_ids: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="UUIDs of related developmental skills demonstrated",
    )
    observation_ids: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="UUIDs of linked progress observations",
    )
    attachments: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Photos/videos: [{url, type, thumbnail, filename, caption}]",
    )
    is_shared_with_parents: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="Visible to parents in parent portal",
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    student: Mapped["Student"] = relationship(
        "Student",
        foreign_keys=[student_id],
        lazy="raise",
    )
    term: Mapped["Term | None"] = relationship(
        "Term",
        foreign_keys=[term_id],
        lazy="raise",
    )
    created_by_user: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[created_by],
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<LearningStory(title='{self.title}', student_id='{self.student_id}')>"
```

**Key design notes:**
- `learning_area_ids`, `skill_ids`, `observation_ids` are JSONB arrays of UUIDs (not FK relationships) because a story can reference multiple areas/skills/observations without junction tables
- `attachments` adds an optional `caption` field per photo (richer than observation attachments)
- `is_shared_with_parents` controls parent portal visibility

---

## 5.2 ExtendedCareSession Model

```python
class ExtendedCareSession(Base, TenantMixin):
    """
    Tracks before-school or after-school extended care sessions.

    Used for billing calculation: total hours × configured hourly rate.
    Does NOT use SoftDeleteMixin — sessions are immutable billing records.
    """

    __tablename__ = "extended_care_sessions"

    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    session_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    session_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="'before_care' or 'after_care'",
    )
    check_in_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
    )
    check_out_time: Mapped[time | None] = mapped_column(
        Time,
        nullable=True,
        comment="NULL until student is checked out",
    )
    duration_minutes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Calculated on check-out: (check_out - check_in) in minutes",
    )
    checked_in_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    checked_out_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    student: Mapped["Student"] = relationship(
        "Student",
        foreign_keys=[student_id],
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<ExtendedCareSession(student_id='{self.student_id}', date='{self.session_date}')>"
```

---

## 5.3 ClassCaregiverRatio Model

```python
class ClassCaregiverRatio(Base, TenantMixin):
    """
    Configurable caregiver-to-child ratio per class per academic year.

    Used for compliance tracking — Ghana ECCD standards require specific ratios
    (e.g., 1:10 for Nursery, 1:15 for KG).
    """

    __tablename__ = "class_caregiver_ratios"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "class_id", "academic_year_id",
            name="uq_class_caregiver_ratio",
        ),
    )

    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classes.id", ondelete="CASCADE"),
        nullable=False,
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_years.id", ondelete="CASCADE"),
        nullable=False,
    )
    max_children_per_caregiver: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Maximum children per caregiver (e.g., 10)",
    )
    current_caregiver_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of caregivers/teachers assigned",
    )

    # Relationships
    class_: Mapped["Class"] = relationship(
        "Class",
        foreign_keys=[class_id],
        lazy="raise",
    )
    academic_year: Mapped["AcademicYear"] = relationship(
        "AcademicYear",
        foreign_keys=[academic_year_id],
        lazy="raise",
    )

    @property
    def max_capacity(self) -> int:
        """Maximum student capacity based on ratio."""
        return self.max_children_per_caregiver * self.current_caregiver_count

    @property
    def is_compliant(self) -> bool:
        """Check if current enrollment is within ratio limits."""
        # This is computed at query time, not stored
        return True  # Actual check done in service layer

    def __repr__(self) -> str:
        return f"<ClassCaregiverRatio(class_id='{self.class_id}', ratio=1:{self.max_children_per_caregiver})>"
```

---

## 5.4 PreschoolReport Column Additions

**File:** `backend/app/models/preschool.py` — add to existing `PreschoolReport` class

Add after the `is_published` field:

```python
    # Phase 2 additions
    report_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="term",
        server_default="term",
        comment="Report type: term, interim, progress_update",
    )
    photo_urls: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Student photos for report: [{url, caption}]",
    )
    chart_data: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Pre-computed chart data for PDF: {labels: [...], values: [...]}",
    )
```

**Also update the unique constraint** — the existing `uq_preschool_report` constraint is `(tenant_id, student_id, term_id)`. With multiple report types per term, we need to include `report_type`:

```python
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "student_id", "term_id", "report_type",
            name="uq_preschool_report_v2",
        ),
    )
```

---

## 5.5 Alembic Migration

**File:** `backend/alembic/versions/20260330_0100_preschool_phase2.py`

```python
"""Preschool Phase 2: Learning Stories, Extended Care, Caregiver Ratios, Report Enhancements

Creates:
- learning_stories table with RLS
- extended_care_sessions table with RLS
- class_caregiver_ratios table with RLS
- report_type, photo_urls, chart_data columns on preschool_reports
- Updated unique constraint on preschool_reports

Revision ID: 20260330_0100
Revises: 20260328_0100
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "20260330_0100"
down_revision = "20260328_0100"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------------------------------------------------------------
    # 1. Create learning_stories table
    # ---------------------------------------------------------------
    op.create_table(
        "learning_stories",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="SET NULL"), nullable=True),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("term_id", UUID(as_uuid=True), sa.ForeignKey("terms.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("narrative", sa.Text(), nullable=False),
        sa.Column("learning_area_ids", JSONB(), nullable=True),
        sa.Column("skill_ids", JSONB(), nullable=True),
        sa.Column("observation_ids", JSONB(), nullable=True),
        sa.Column("attachments", JSONB(), nullable=True),
        sa.Column("is_shared_with_parents", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ---------------------------------------------------------------
    # 2. Create extended_care_sessions table
    # ---------------------------------------------------------------
    op.create_table(
        "extended_care_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="SET NULL"), nullable=True),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_date", sa.Date(), nullable=False),
        sa.Column("session_type", sa.String(20), nullable=False),
        sa.Column("check_in_time", sa.Time(), nullable=False),
        sa.Column("check_out_time", sa.Time(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("checked_in_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("checked_out_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # ---------------------------------------------------------------
    # 3. Create class_caregiver_ratios table
    # ---------------------------------------------------------------
    op.create_table(
        "class_caregiver_ratios",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="SET NULL"), nullable=True),
        sa.Column("class_id", UUID(as_uuid=True), sa.ForeignKey("classes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("academic_year_id", UUID(as_uuid=True), sa.ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False),
        sa.Column("max_children_per_caregiver", sa.Integer(), nullable=False),
        sa.Column("current_caregiver_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_unique_constraint(
        "uq_class_caregiver_ratio", "class_caregiver_ratios",
        ["tenant_id", "class_id", "academic_year_id"],
    )

    # ---------------------------------------------------------------
    # 4. Add columns to preschool_reports
    # ---------------------------------------------------------------
    op.add_column("preschool_reports", sa.Column(
        "report_type", sa.String(20), nullable=False, server_default="term",
    ))
    op.add_column("preschool_reports", sa.Column(
        "photo_urls", JSONB(), nullable=True,
    ))
    op.add_column("preschool_reports", sa.Column(
        "chart_data", JSONB(), nullable=True,
    ))

    # Update unique constraint to include report_type
    op.drop_constraint("uq_preschool_report", "preschool_reports", type_="unique")
    op.create_unique_constraint(
        "uq_preschool_report_v2", "preschool_reports",
        ["tenant_id", "student_id", "term_id", "report_type"],
    )

    # ---------------------------------------------------------------
    # 5. Create indexes
    # ---------------------------------------------------------------
    for table in ["learning_stories", "extended_care_sessions", "class_caregiver_ratios"]:
        op.create_index(f"ix_{table}_tenant", table, ["tenant_id"])
        op.create_index(f"ix_{table}_school", table, ["school_id"])

    op.create_index("ix_learning_stories_student", "learning_stories", ["tenant_id", "student_id"])
    op.create_index("ix_extended_care_sessions_student_date", "extended_care_sessions", ["tenant_id", "student_id", "session_date"])
    op.create_index("ix_class_caregiver_ratios_class", "class_caregiver_ratios", ["tenant_id", "class_id"])

    # ---------------------------------------------------------------
    # 6. CHECK constraints
    # ---------------------------------------------------------------
    op.execute("""
        ALTER TABLE extended_care_sessions
        ADD CONSTRAINT ck_session_type CHECK (session_type IN ('before_care', 'after_care')),
        ADD CONSTRAINT ck_duration_positive CHECK (duration_minutes >= 0),
        ADD CONSTRAINT ck_checkout_after_checkin CHECK (check_out_time > check_in_time)
    """)

    # ---------------------------------------------------------------
    # 7. RLS policies (using project-standard rls_helpers)
    # ---------------------------------------------------------------
    from app.db.rls_helpers import enable_rls_for_table
    conn = op.get_bind()
    for table in ["learning_stories", "extended_care_sessions", "class_caregiver_ratios"]:
        enable_rls_for_table(conn, table)


def downgrade() -> None:
    from app.db.rls_helpers import disable_rls_for_table
    conn = op.get_bind()

    # Disable RLS before dropping tables
    for table in ["class_caregiver_ratios", "extended_care_sessions", "learning_stories"]:
        disable_rls_for_table(conn, table)

    # Restore original unique constraint
    op.drop_constraint("uq_preschool_report_v2", "preschool_reports", type_="unique")
    op.create_unique_constraint(
        "uq_preschool_report", "preschool_reports",
        ["tenant_id", "student_id", "term_id"],
    )

    # Drop added columns
    op.drop_column("preschool_reports", "chart_data")
    op.drop_column("preschool_reports", "photo_urls")
    op.drop_column("preschool_reports", "report_type")

    # Drop tables
    op.drop_table("class_caregiver_ratios")
    op.drop_table("extended_care_sessions")
    op.drop_table("learning_stories")
```

---

## 5.6 Test Infrastructure Update

**File:** `backend/tests/conftest.py`

Add to `TENANT_SCOPED_TABLES` (currently 105 after Phase 1):

```python
    # Preschool Phase 2 (Gap Closure)
    "learning_stories", "extended_care_sessions", "class_caregiver_ratios",
```

After Phase 2, the total will be **108 entries**.

**File:** `backend/scripts/verify_rls.py`

Add same 3 table names.

---

## Validation Checklist

- [ ] `LearningStory` has `SoftDeleteMixin`; `ExtendedCareSession` and `ClassCaregiverRatio` do NOT
- [ ] All relationships use `lazy="raise"`
- [ ] `school_id` nullable on all 3 new models
- [ ] `uq_preschool_report` constraint updated to include `report_type`
- [ ] Migration `down_revision` correctly points to Phase 1 migration
- [ ] JSONB arrays for `learning_area_ids`, `skill_ids`, `observation_ids` (not FK relationships)
- [ ] `duration_minutes` computed on check-out (service layer), not at DB level
- [ ] `TENANT_SCOPED_TABLES` updated with 3 new entries
