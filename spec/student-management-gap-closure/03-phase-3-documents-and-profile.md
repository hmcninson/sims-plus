# Phase 3: Documents, Previous Schools & Profile Fields

**Covers:** STU-002 (Birth Certificate), SM-014 (Structured Medical), SM-015 (Previous School History), SM-019 (Document Repository)
**Priority:** Should
**Estimated Effort:** 3–4 days
**New Tables:** 2
**New Columns:** 2 (on `students` table)
**New Endpoints:** 8
**New Tests:** ~24
**Dependencies:** None — can be developed in parallel with Phase 2

---

## 1. Database Schema

### 1.1 New Enum: `studentdocumenttype`

```python
class StudentDocumentType(str, Enum):
    """Types of documents that can be stored per student."""
    BIRTH_CERTIFICATE = "birth_certificate"
    MEDICAL_RECORD = "medical_record"
    TRANSFER_LETTER = "transfer_letter"
    REPORT_CARD = "report_card"
    ID_CARD = "id_card"
    LEAVING_CERTIFICATE = "leaving_certificate"
    PHOTO = "photo"
    OTHER = "other"
```

### 1.2 New Table: `student_documents`

Per-student document repository backed by S3. Each document has a type, title, S3 reference, and metadata.

| Column | Type | Nullable | Default | Constraints | Notes |
|--------|------|----------|---------|-------------|-------|
| `id` | UUID | No | `uuid4()` | PK | |
| `tenant_id` | UUID | No | | FK `tenants.id` CASCADE | TenantMixin |
| `student_id` | UUID | No | | FK `students.id` CASCADE | |
| `school_id` | UUID | No | | FK `schools.id` CASCADE | |
| `document_type` | VARCHAR(30) | No | | | StudentDocumentType enum value |
| `title` | VARCHAR(255) | No | | | Human-readable document name |
| `file_url` | VARCHAR(500) | No | | | S3 key (NOT a presigned URL) |
| `file_size` | INTEGER | No | | | Size in bytes |
| `mime_type` | VARCHAR(100) | No | | | MIME type (validated on upload) |
| `uploaded_by` | UUID | Yes | | FK `users.id` SET NULL | User who uploaded. Nullable to allow user deletion. |
| `notes` | TEXT | Yes | | | Optional notes about the document |
| `created_at` | TIMESTAMPTZ | No | `now()` | | |
| `updated_at` | TIMESTAMPTZ | No | `now()` | | |
| `deleted_at` | TIMESTAMPTZ | Yes | | | SoftDeleteMixin |

**Uses SoftDeleteMixin** — documents can be soft-deleted.

**Indexes:**

```sql
-- Per-student document listing (most common query)
CREATE INDEX ix_sdoc_student ON student_documents(student_id, document_type) WHERE deleted_at IS NULL;

-- Per-tenant document count (for storage quota enforcement)
CREATE INDEX ix_sdoc_tenant ON student_documents(tenant_id) WHERE deleted_at IS NULL;
```

**RLS Policy:**

```sql
ALTER TABLE student_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_documents FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_student_documents ON student_documents
    FOR ALL TO sims_app_user
    USING (tenant_id = get_current_tenant_id())
    WITH CHECK (tenant_id = get_current_tenant_id());

GRANT SELECT, INSERT, UPDATE, DELETE ON student_documents TO sims_app_user;
```

### 1.3 New Table: `previous_schools`

Structured previous school history for transfer students. Multiple records per student are allowed (a student may have attended several schools before).

| Column | Type | Nullable | Default | Constraints | Notes |
|--------|------|----------|---------|-------------|-------|
| `id` | UUID | No | `uuid4()` | PK | |
| `tenant_id` | UUID | No | | FK `tenants.id` CASCADE | TenantMixin |
| `student_id` | UUID | No | | FK `students.id` CASCADE | |
| `school_id` | UUID | No | | FK `schools.id` CASCADE | Which school the student belongs to (for chain filtering) |
| `school_name` | VARCHAR(255) | No | | | Name of the previous school |
| `school_address` | TEXT | Yes | | | Address of the previous school |
| `last_class` | VARCHAR(100) | Yes | | | Last class/form attended (e.g., "JHS 2", "Grade 5") |
| `years_attended` | VARCHAR(50) | Yes | | | Free text, e.g., "2020-2024" |
| `transfer_reason` | TEXT | Yes | | | Why the student left the previous school |
| `leaving_certificate_ref` | VARCHAR(100) | Yes | | | Reference number of leaving certificate |
| `created_at` | TIMESTAMPTZ | No | `now()` | | |
| `updated_at` | TIMESTAMPTZ | No | `now()` | | |

**NOT using SoftDeleteMixin** — previous school records are informational and rarely deleted. Hard delete via endpoint is fine.

**Indexes:**

```sql
CREATE INDEX ix_prev_school_student ON previous_schools(student_id);
```

**RLS Policy:**

```sql
ALTER TABLE previous_schools ENABLE ROW LEVEL SECURITY;
ALTER TABLE previous_schools FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_previous_schools ON previous_schools
    FOR ALL TO sims_app_user
    USING (tenant_id = get_current_tenant_id())
    WITH CHECK (tenant_id = get_current_tenant_id());

GRANT SELECT, INSERT, UPDATE, DELETE ON previous_schools TO sims_app_user;
```

### 1.4 Column Additions to `students` Table

| Column | Type | Nullable | Default | Purpose |
|--------|------|----------|---------|---------|
| `birth_certificate_number` | VARCHAR(50) | Yes | NULL | National birth certificate reference number (STU-002) |
| `structured_medical` | JSONB | Yes | NULL | Structured medical data (SM-014) |

**`structured_medical` JSONB Schema:**

```json
{
  "conditions": [
    {
      "name": "Asthma",
      "severity": "moderate",
      "diagnosed_date": "2024-01-15",
      "notes": "Triggered by dust and cold weather"
    }
  ],
  "allergies": [
    {
      "name": "Peanuts",
      "severity": "severe",
      "reaction": "Anaphylaxis"
    },
    {
      "name": "Penicillin",
      "severity": "mild",
      "reaction": "Rash"
    }
  ],
  "medications": [
    {
      "name": "Ventolin Inhaler",
      "dosage": "2 puffs",
      "frequency": "As needed",
      "prescriber": "Dr. Mensah"
    }
  ],
  "emergency_protocol": "In case of asthma attack: 1) Sit upright 2) Administer Ventolin 3) Call parent 4) If no improvement in 5 min, call ambulance",
  "doctor_name": "Dr. Kwame Mensah",
  "doctor_phone": "+233 24 123 4567",
  "hospital": "Korle Bu Teaching Hospital",
  "blood_group": "O+"
}
```

**Design notes:**
- This JSONB field coexists with the existing text fields (`medical_conditions`, `allergies`, `blood_group`)
- Existing text fields remain for backward compatibility — no migration of existing data needed
- Frontend should read from `structured_medical` first, fall back to text fields if null
- New data entry should write to both `structured_medical` AND the text fields (for backward compatibility)

---

## 2. Alembic Migration

**File:** `backend/alembic/versions/20260326_0500_student_documents_profile.py`

**Revision chain:** Revises `20260326_0400` (Phase 2).

```python
"""Add student documents, previous schools tables, and profile columns.

Revision ID: 20260326_0500
Revises: 20260326_0400
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision = "20260326_0500"
down_revision = "20260326_0400"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Enum ---
    studentdocumenttype = sa.Enum(
        "birth_certificate", "medical_record", "transfer_letter",
        "report_card", "id_card", "leaving_certificate", "photo", "other",
        name="studentdocumenttype",
    )
    studentdocumenttype.create(op.get_bind(), checkfirst=True)

    # --- Table 1: student_documents ---
    op.create_table(
        "student_documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_type", studentdocumenttype, nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("file_url", sa.String(500), nullable=False),
        sa.Column("file_size", sa.Integer, nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("uploaded_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.execute("""
        CREATE INDEX ix_sdoc_student ON student_documents(student_id, document_type)
        WHERE deleted_at IS NULL
    """)
    op.execute("""
        CREATE INDEX ix_sdoc_tenant ON student_documents(tenant_id)
        WHERE deleted_at IS NULL
    """)

    # RLS
    op.execute("ALTER TABLE student_documents ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE student_documents FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation_student_documents ON student_documents
        FOR ALL TO sims_app_user
        USING (tenant_id = get_current_tenant_id())
        WITH CHECK (tenant_id = get_current_tenant_id())
    """)
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON student_documents TO sims_app_user")

    # --- Table 2: previous_schools ---
    op.create_table(
        "previous_schools",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("school_name", sa.String(255), nullable=False),
        sa.Column("school_address", sa.Text, nullable=True),
        sa.Column("last_class", sa.String(100), nullable=True),
        sa.Column("years_attended", sa.String(50), nullable=True),
        sa.Column("transfer_reason", sa.Text, nullable=True),
        sa.Column("leaving_certificate_ref", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )

    op.create_index("ix_prev_school_student", "previous_schools", ["student_id"])

    # RLS
    op.execute("ALTER TABLE previous_schools ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE previous_schools FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation_previous_schools ON previous_schools
        FOR ALL TO sims_app_user
        USING (tenant_id = get_current_tenant_id())
        WITH CHECK (tenant_id = get_current_tenant_id())
    """)
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON previous_schools TO sims_app_user")

    # --- Column additions to students ---
    op.add_column("students", sa.Column("birth_certificate_number", sa.String(50), nullable=True))
    op.add_column("students", sa.Column("structured_medical", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("students", "structured_medical")
    op.drop_column("students", "birth_certificate_number")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON previous_schools")
    op.drop_table("previous_schools")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON student_documents")
    op.drop_table("student_documents")
    sa.Enum(name="studentdocumenttype").drop(op.get_bind(), checkfirst=True)
```

---

## 3. SQLAlchemy Models

### 3.1 StudentDocument Model

**File:** `backend/app/models/student.py`

```python
class StudentDocumentType(str, Enum):
    """Types of documents stored per student."""
    BIRTH_CERTIFICATE = "birth_certificate"
    MEDICAL_RECORD = "medical_record"
    TRANSFER_LETTER = "transfer_letter"
    REPORT_CARD = "report_card"
    ID_CARD = "id_card"
    LEAVING_CERTIFICATE = "leaving_certificate"
    PHOTO = "photo"
    OTHER = "other"


class StudentDocument(Base, TenantMixin, SoftDeleteMixin):
    """Per-student document stored in S3.

    Documents include certificates, medical records, letters, photos, etc.
    File content is stored in S3; this table holds metadata and the S3 key.
    """
    __tablename__ = "student_documents"

    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    school_id: Mapped[UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_type: Mapped[StudentDocumentType] = mapped_column(
        SQLEnum(
            StudentDocumentType,
            name="studentdocumenttype",
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    file_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="S3 key — NOT a presigned URL",
    )
    file_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="File size in bytes",
    )
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    uploaded_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    student: Mapped["Student"] = relationship("Student", lazy="raise")
```

### 3.2 PreviousSchool Model

```python
class PreviousSchool(Base, TenantMixin):
    """Structured previous school history for transfer students.

    Records schools the student attended before joining this school.
    Multiple records per student are allowed.
    """
    __tablename__ = "previous_schools"

    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    school_name: Mapped[str] = mapped_column(String(255), nullable=False)
    school_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_class: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Last class/form attended, e.g., 'JHS 2', 'Grade 5'",
    )
    years_attended: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Free text, e.g., '2020-2024'",
    )
    transfer_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    leaving_certificate_ref: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Reference number of leaving/transfer certificate",
    )

    # Relationships
    student: Mapped["Student"] = relationship("Student", lazy="raise")
```

### 3.3 Student Model Column Additions

Add to the existing `Student` class in `backend/app/models/student.py`:

```python
# After the existing ghana_card_number and nhis_number fields:
birth_certificate_number: Mapped[Optional[str]] = mapped_column(
    String(50),
    nullable=True,
    comment="National birth certificate reference number",
)

# After the existing dietary_requirements field:
structured_medical: Mapped[Optional[dict]] = mapped_column(
    JSONB,
    nullable=True,
    comment="Structured medical data: conditions, allergies, medications, emergency protocol",
)
```

### 3.4 Student Relationships Additions

Add to the existing `Student` class relationships:

```python
documents: Mapped[list["StudentDocument"]] = relationship(
    "StudentDocument",
    back_populates="student",
    lazy="raise",
    cascade="all, delete-orphan",
)
previous_schools: Mapped[list["PreviousSchool"]] = relationship(
    "PreviousSchool",
    back_populates="student",
    lazy="raise",
    cascade="all, delete-orphan",
)
```

---

## 4. Pydantic Schemas

**File:** `backend/app/schemas/student.py`

### 4.1 Document Schemas

```python
class StudentDocumentUploadResponse(BaseModel):
    """Response after uploading a document."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    student_id: UUID
    document_type: str
    title: str
    file_size: int
    mime_type: str
    uploaded_by: UUID
    notes: str | None = None
    created_at: str


class StudentDocumentListResponse(BaseModel):
    """List of documents for a student."""
    documents: list[StudentDocumentUploadResponse]
    total: int
    total_size_bytes: int  # Sum of all document sizes


class StudentDocumentDownloadResponse(BaseModel):
    """Presigned URL for document download."""
    download_url: str
    expires_in: int  # Seconds until URL expires
```

### 4.2 Previous School Schemas

```python
class PreviousSchoolCreate(BaseModel):
    """Request to add a previous school record."""
    school_name: str = Field(..., min_length=2, max_length=255)
    school_address: str | None = None
    last_class: str | None = Field(None, max_length=100)
    years_attended: str | None = Field(None, max_length=50)
    transfer_reason: str | None = None
    leaving_certificate_ref: str | None = Field(None, max_length=100)


class PreviousSchoolUpdate(BaseModel):
    """Request to update a previous school record."""
    school_name: str | None = Field(None, min_length=2, max_length=255)
    school_address: str | None = None
    last_class: str | None = Field(None, max_length=100)
    years_attended: str | None = Field(None, max_length=50)
    transfer_reason: str | None = None
    leaving_certificate_ref: str | None = Field(None, max_length=100)


class PreviousSchoolResponse(BaseModel):
    """Response for a previous school record."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    student_id: UUID
    school_name: str
    school_address: str | None = None
    last_class: str | None = None
    years_attended: str | None = None
    transfer_reason: str | None = None
    leaving_certificate_ref: str | None = None
    created_at: str
```

### 4.3 Structured Medical Schema

```python
class MedicalCondition(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    severity: str | None = Field(None, pattern="^(mild|moderate|severe)$")
    diagnosed_date: str | None = None
    notes: str | None = Field(None, max_length=1000)


class MedicalAllergy(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    severity: str | None = Field(None, pattern="^(mild|moderate|severe)$")
    reaction: str | None = Field(None, max_length=500)


class MedicalMedication(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    dosage: str | None = Field(None, max_length=200)
    frequency: str | None = Field(None, max_length=200)
    prescriber: str | None = Field(None, max_length=200)


class StructuredMedical(BaseModel):
    """Structured medical data for a student.

    All text fields have max_length bounds. List fields limited to 50 items.
    emergency_protocol is sanitized with nh3.clean() before storage.
    """
    conditions: list[MedicalCondition] = Field(default=[], max_length=50)
    allergies: list[MedicalAllergy] = Field(default=[], max_length=50)
    medications: list[MedicalMedication] = Field(default=[], max_length=50)
    emergency_protocol: str | None = Field(None, max_length=2000)
    doctor_name: str | None = Field(None, max_length=200)
    doctor_phone: str | None = Field(None, max_length=20)
    hospital: str | None = Field(None, max_length=200)
    blood_group: str | None = Field(None, pattern="^(A|B|AB|O)[+-]$")

    @field_validator("emergency_protocol")
    @classmethod
    def sanitize_emergency_protocol(cls, v: str | None) -> str | None:
        if v:
            import nh3
            return nh3.clean(v)
        return v
```

### 4.4 Student Schema Updates

Add to `StudentCreate` and `StudentUpdate`:

```python
birth_certificate_number: str | None = Field(None, max_length=50)
structured_medical: StructuredMedical | None = None
```

Add to `StudentResponse` and `StudentWithGuardiansResponse`:

```python
birth_certificate_number: str | None = None
structured_medical: dict | None = None
```

---

## 5. Service Layer

**File:** `backend/app/services/student/document_service.py` (new file)

### 5.1 StudentDocumentMixin

```python
"""
SIMS Plus - Student Document Service

Handles per-student document upload, listing, deletion, and presigned URL generation.
Also handles previous school history CRUD.
"""

import uuid as uuid_module
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.models.student import (
    Student, StudentDocument, StudentDocumentType, PreviousSchool,
)
from app.services.student._shared import StudentServiceError
from app.services.s3 import S3Service


# Allowed MIME types for student documents
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

# Max file size: 10 MB
MAX_FILE_SIZE = 10 * 1024 * 1024

# Storage limits by subscription plan (bytes per student)
STORAGE_LIMITS = {
    "starter": 50 * 1024 * 1024,        # 50 MB
    "professional": 200 * 1024 * 1024,   # 200 MB
    "enterprise": 1024 * 1024 * 1024,    # 1 GB
    "trial": 50 * 1024 * 1024,           # 50 MB (same as starter)
}


class StudentDocumentMixin:
    """Mixin for student document management and previous school history."""

    # ─── Document Management ────────────────────────────────────────

    async def upload_document(
        self,
        tenant_id: UUID,
        student_id: UUID,
        school_id: UUID,
        document_type: str,
        title: str,
        file_content: bytes,
        file_name: str,
        mime_type: str,
        uploaded_by: UUID,
        notes: str | None = None,
        subscription_plan: str = "starter",
    ) -> StudentDocument:
        """Upload a document for a student.

        Steps:
        1. Validate MIME type and file size
        2. Check storage quota for the student
        3. Upload to S3
        4. Create database record

        S3 path: {tenant_id}/students/{student_id}/documents/{uuid}_{filename}

        Args:
            tenant_id: Tenant UUID
            student_id: Student UUID
            school_id: School UUID
            document_type: One of StudentDocumentType values
            title: Human-readable document title
            file_content: Raw file bytes
            file_name: Original file name
            mime_type: MIME type (validated against whitelist)
            uploaded_by: User UUID
            notes: Optional notes
            subscription_plan: Tenant's subscription plan (for quota check)

        Returns:
            Created StudentDocument record

        Raises:
            StudentServiceError: On validation failure or quota exceeded
        """
        # 1. Validate MIME type AND magic bytes (not just client-provided MIME)
        from app.utils.sanitize import validate_file_magic
        detected_type = validate_file_magic(file_content)
        if detected_type and detected_type not in ALLOWED_MIME_TYPES:
            raise StudentServiceError(
                f"File content does not match an allowed type (detected: {detected_type})",
                code="invalid_file_content",
            )
        if mime_type not in ALLOWED_MIME_TYPES:
            raise StudentServiceError(
                f"File type '{mime_type}' is not allowed. Allowed types: PDF, JPEG, PNG, DOC, DOCX",
                code="invalid_file_type",
            )

        # 2. Validate file size
        file_size = len(file_content)
        if file_size > MAX_FILE_SIZE:
            raise StudentServiceError(
                f"File size ({file_size} bytes) exceeds maximum of {MAX_FILE_SIZE} bytes (10 MB)",
                code="file_too_large",
            )

        # 3. Check storage quota
        current_usage = await self._get_student_storage_usage(tenant_id, student_id)
        limit = STORAGE_LIMITS.get(subscription_plan, STORAGE_LIMITS["starter"])
        if current_usage + file_size > limit:
            limit_mb = limit // (1024 * 1024)
            raise StudentServiceError(
                f"Storage quota exceeded. Limit: {limit_mb} MB for {subscription_plan} plan",
                code="storage_quota_exceeded",
            )

        # 4. Upload to S3
        # Sanitize filename: strip path separators, limit to alphanumeric + .-_
        import re
        safe_name = re.sub(r'[^a-zA-Z0-9._-]', '_', file_name.split('/')[-1].split('\\')[-1])[:100]
        file_uuid = str(uuid_module.uuid4())
        s3_key = f"{tenant_id}/students/{student_id}/documents/{file_uuid}_{safe_name}"

        s3_service = S3Service()
        await s3_service.upload_bytes(
            key=s3_key,
            data=file_content,
            content_type=mime_type,
        )

        # 5. Create DB record
        doc_type_enum = StudentDocumentType(document_type)
        document = StudentDocument(
            tenant_id=tenant_id,
            student_id=student_id,
            school_id=school_id,
            document_type=doc_type_enum,
            title=title,
            file_url=s3_key,
            file_size=file_size,
            mime_type=mime_type,
            uploaded_by=uploaded_by,
            notes=notes,
        )
        self.db.add(document)
        await self.db.flush()
        await self.db.refresh(document)
        return document

    async def list_documents(
        self,
        tenant_id: UUID,
        student_id: UUID,
        document_type: str | None = None,
    ) -> tuple[list[StudentDocument], int]:
        """List all documents for a student.

        Args:
            tenant_id: Tenant UUID
            student_id: Student UUID
            document_type: Optional filter by document type

        Returns:
            Tuple of (documents list, total storage in bytes)
        """
        filters = [
            StudentDocument.tenant_id == tenant_id,
            StudentDocument.student_id == student_id,
            StudentDocument.deleted_at.is_(None),
        ]
        if document_type:
            filters.append(StudentDocument.document_type == document_type)

        stmt = (
            select(StudentDocument)
            .where(*filters)
            .order_by(StudentDocument.created_at.desc())
        )
        result = await self.db.execute(stmt)
        documents = list(result.scalars().all())

        total_size = sum(doc.file_size for doc in documents)
        return documents, total_size

    async def delete_document(
        self,
        tenant_id: UUID,
        document_id: UUID,
        student_id: UUID,
    ) -> bool:
        """Soft-delete a student document.

        IDOR check: verifies the document belongs to the specified student.
        Does NOT delete the file from S3 (soft delete only).

        Args:
            tenant_id: Tenant UUID
            document_id: Document UUID
            student_id: Student UUID (for IDOR verification)

        Returns:
            True if deleted, raises error if not found
        """
        from datetime import datetime, UTC

        stmt = (
            select(StudentDocument)
            .where(
                StudentDocument.tenant_id == tenant_id,
                StudentDocument.id == document_id,
                StudentDocument.student_id == student_id,
                StudentDocument.deleted_at.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        document = result.scalar_one_or_none()
        if not document:
            raise StudentServiceError("Document not found", code="document_not_found")

        document.deleted_at = datetime.now(UTC)
        await self.db.flush()
        return True

    async def get_document_download_url(
        self,
        tenant_id: UUID,
        document_id: UUID,
        student_id: UUID,
    ) -> dict:
        """Generate a presigned S3 URL for document download.

        IDOR check: verifies the document belongs to the specified student.
        URL expires in 15 minutes.

        Returns:
            {"download_url": "https://...", "expires_in": 900}
        """
        stmt = (
            select(StudentDocument)
            .where(
                StudentDocument.tenant_id == tenant_id,
                StudentDocument.id == document_id,
                StudentDocument.student_id == student_id,
                StudentDocument.deleted_at.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        document = result.scalar_one_or_none()
        if not document:
            raise StudentServiceError("Document not found", code="document_not_found")

        s3_service = S3Service()
        presigned_url = await s3_service.generate_presigned_url(
            key=document.file_url,
            expires_in=900,  # 15 minutes
        )

        return {
            "download_url": presigned_url,
            "expires_in": 900,
        }

    async def _get_student_storage_usage(self, tenant_id: UUID, student_id: UUID) -> int:
        """Get total storage usage in bytes for a student's documents."""
        stmt = (
            select(func.coalesce(func.sum(StudentDocument.file_size), 0))
            .where(
                StudentDocument.tenant_id == tenant_id,
                StudentDocument.student_id == student_id,
                StudentDocument.deleted_at.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    # ─── Previous School History ────────────────────────────────────

    async def add_previous_school(
        self,
        tenant_id: UUID,
        student_id: UUID,
        school_name: str,
        school_address: str | None = None,
        last_class: str | None = None,
        years_attended: str | None = None,
        transfer_reason: str | None = None,
        leaving_certificate_ref: str | None = None,
    ) -> PreviousSchool:
        """Add a previous school record for a student."""
        record = PreviousSchool(
            tenant_id=tenant_id,
            student_id=student_id,
            school_name=school_name,
            school_address=school_address,
            last_class=last_class,
            years_attended=years_attended,
            transfer_reason=transfer_reason,
            leaving_certificate_ref=leaving_certificate_ref,
        )
        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)
        return record

    async def list_previous_schools(
        self,
        tenant_id: UUID,
        student_id: UUID,
    ) -> list[PreviousSchool]:
        """List all previous school records for a student."""
        stmt = (
            select(PreviousSchool)
            .where(
                PreviousSchool.tenant_id == tenant_id,
                PreviousSchool.student_id == student_id,
            )
            .order_by(PreviousSchool.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_previous_school(
        self,
        tenant_id: UUID,
        record_id: UUID,
        student_id: UUID,
        **fields,
    ) -> PreviousSchool:
        """Update a previous school record.

        IDOR check: verifies the record belongs to the specified student.
        """
        stmt = (
            select(PreviousSchool)
            .where(
                PreviousSchool.tenant_id == tenant_id,
                PreviousSchool.id == record_id,
                PreviousSchool.student_id == student_id,
            )
        )
        result = await self.db.execute(stmt)
        record = result.scalar_one_or_none()
        if not record:
            raise StudentServiceError("Previous school record not found", code="record_not_found")

        allowed = {"school_name", "school_address", "last_class", "years_attended", "transfer_reason", "leaving_certificate_ref"}
        for key, value in fields.items():
            if key in allowed and value is not None:
                setattr(record, key, value)

        await self.db.flush()
        await self.db.refresh(record)
        return record

    async def delete_previous_school(
        self,
        tenant_id: UUID,
        record_id: UUID,
        student_id: UUID,
    ) -> bool:
        """Delete a previous school record (hard delete).

        IDOR check: verifies the record belongs to the specified student.
        """
        stmt = (
            select(PreviousSchool)
            .where(
                PreviousSchool.tenant_id == tenant_id,
                PreviousSchool.id == record_id,
                PreviousSchool.student_id == student_id,
            )
        )
        result = await self.db.execute(stmt)
        record = result.scalar_one_or_none()
        if not record:
            raise StudentServiceError("Previous school record not found", code="record_not_found")

        await self.db.delete(record)
        await self.db.flush()
        return True
```

### 5.2 Update `__init__.py`

```python
from app.services.student.document_service import StudentDocumentMixin

class StudentService(
    StudentCoreMixin,
    StudentImportMixin,
    StudentGuardianMixin,
    StudentHistoryMixin,      # Phase 1
    StudentLifecycleMixin,    # Phase 2
    StudentDocumentMixin,     # Phase 3
):
    def __init__(self, db: AsyncSession):
        self.db = db
```

---

## 6. API Endpoints

**File:** `backend/app/api/v1/endpoints/students.py`

### 6.1 POST `/students/{student_id}/documents`

```python
@router.post("/students/{student_id}/documents")
async def upload_document(
    student_id: UUID,
    document_type: str = Form(...),
    title: str = Form(...),
    notes: str | None = Form(None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(ValidatedUser),
    _: None = Depends(require_permissions("students.update")),
):
    """Upload a document for a student.

    Multipart form with file upload.
    Max file size: 10 MB. Allowed types: PDF, JPEG, PNG, DOC, DOCX.
    """
    tenant_id = user["tenant_id"]
    service = StudentService(db)

    # Verify student exists
    student = await service.get_student(tenant_id, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    file_content = await file.read()

    try:
        document = await service.upload_document(
            tenant_id=tenant_id,
            student_id=student_id,
            school_id=student.school_id,
            document_type=document_type,
            title=title,
            file_content=file_content,
            file_name=file.filename or "document",
            mime_type=file.content_type or "application/octet-stream",
            uploaded_by=user["user_id"],
            notes=notes,
            subscription_plan=user.get("subscription_plan", "starter"),
        )
        return { ... }  # Map to StudentDocumentUploadResponse
    except StudentServiceError as e:
        status = 413 if e.code == "storage_quota_exceeded" or e.code == "file_too_large" else 400
        raise HTTPException(status_code=status, detail=e.message)
```

### 6.2 GET `/students/{student_id}/documents`

```python
@router.get("/students/{student_id}/documents")
async def list_documents(
    student_id: UUID,
    document_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(ValidatedUser),
    _: None = Depends(require_permissions("students.read")),
):
    """List all documents for a student, optionally filtered by type."""
```

### 6.3 GET `/students/{student_id}/documents/{document_id}/download`

```python
@router.get("/students/{student_id}/documents/{document_id}/download")
async def download_document(
    student_id: UUID,
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(ValidatedUser),
    _: None = Depends(require_permissions("students.read")),
):
    """Get a presigned download URL for a document. URL expires in 15 minutes."""
```

### 6.4 DELETE `/students/{student_id}/documents/{document_id}`

```python
@router.delete("/students/{student_id}/documents/{document_id}", status_code=204)
async def delete_document(
    student_id: UUID,
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(ValidatedUser),
    _: None = Depends(require_permissions("students.update")),
):
    """Soft-delete a student document."""
```

### 6.5 POST `/students/{student_id}/previous-schools`

```python
@router.post("/students/{student_id}/previous-schools", status_code=201)
async def add_previous_school(
    student_id: UUID,
    request: PreviousSchoolCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(ValidatedUser),
    _: None = Depends(require_permissions("students.update")),
):
    """Add a previous school record for a student."""
```

### 6.6 GET `/students/{student_id}/previous-schools`

```python
@router.get("/students/{student_id}/previous-schools")
async def list_previous_schools(
    student_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(ValidatedUser),
    _: None = Depends(require_permissions("students.read")),
):
    """List all previous school records for a student."""
```

### 6.7 PUT `/students/{student_id}/previous-schools/{record_id}`

```python
@router.put("/students/{student_id}/previous-schools/{record_id}")
async def update_previous_school(
    student_id: UUID,
    record_id: UUID,
    request: PreviousSchoolUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(ValidatedUser),
    _: None = Depends(require_permissions("students.update")),
):
    """Update a previous school record."""
```

### 6.8 DELETE `/students/{student_id}/previous-schools/{record_id}`

```python
@router.delete("/students/{student_id}/previous-schools/{record_id}", status_code=204)
async def delete_previous_school(
    student_id: UUID,
    record_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(ValidatedUser),
    _: None = Depends(require_permissions("students.update")),
):
    """Delete a previous school record (hard delete)."""
```

---

## 7. Frontend Changes

### 7.1 TypeScript Types

**File:** `frontend/types/index.ts`

```typescript
// Student Documents
export interface StudentDocument {
  id: string;
  student_id: string;
  document_type: string;
  title: string;
  file_size: number;
  mime_type: string;
  uploaded_by: string;
  notes: string | null;
  created_at: string;
}

export interface StudentDocumentListResponse {
  documents: StudentDocument[];
  total: number;
  total_size_bytes: number;
}

// Previous Schools
export interface PreviousSchool {
  id: string;
  student_id: string;
  school_name: string;
  school_address: string | null;
  last_class: string | null;
  years_attended: string | null;
  transfer_reason: string | null;
  leaving_certificate_ref: string | null;
  created_at: string;
}

// Structured Medical
export interface MedicalCondition {
  name: string;
  severity?: "mild" | "moderate" | "severe";
  diagnosed_date?: string;
  notes?: string;
}

export interface MedicalAllergy {
  name: string;
  severity?: "mild" | "moderate" | "severe";
  reaction?: string;
}

export interface MedicalMedication {
  name: string;
  dosage?: string;
  frequency?: string;
  prescriber?: string;
}

export interface StructuredMedical {
  conditions: MedicalCondition[];
  allergies: MedicalAllergy[];
  medications: MedicalMedication[];
  emergency_protocol?: string;
  doctor_name?: string;
  doctor_phone?: string;
  hospital?: string;
  blood_group?: string;
}
```

### 7.2 Server Actions

**File:** `frontend/actions/students.action.ts`

```typescript
export async function uploadDocument(studentId: string, formData: FormData): Promise<ActionResult<StudentDocument>> { ... }
export async function listDocuments(studentId: string, documentType?: string): Promise<ActionResult<StudentDocumentListResponse>> { ... }
export async function getDocumentDownloadUrl(studentId: string, documentId: string): Promise<ActionResult<{download_url: string; expires_in: number}>> { ... }
export async function deleteDocument(studentId: string, documentId: string): Promise<ActionResult<void>> { ... }
export async function addPreviousSchool(studentId: string, data: Omit<PreviousSchool, "id" | "student_id" | "created_at">): Promise<ActionResult<PreviousSchool>> { ... }
export async function listPreviousSchools(studentId: string): Promise<ActionResult<PreviousSchool[]>> { ... }
export async function updatePreviousSchool(studentId: string, recordId: string, data: Partial<PreviousSchool>): Promise<ActionResult<PreviousSchool>> { ... }
export async function deletePreviousSchool(studentId: string, recordId: string): Promise<ActionResult<void>> { ... }
```

### 7.3 Frontend Components

#### Documents Tab (`students/[id]/student-documents.tsx`)

- **Upload area:** Drag-and-drop zone + file input button
- **Document type selector:** Dropdown for document type
- **Title input:** Text field for document title
- **Notes input:** Optional textarea
- **File size indicator:** Shows current/max upload size
- **Storage quota bar:** Progress bar showing usage vs. plan limit
- **Document list:** Cards or table with columns: Title, Type, Size, Uploaded Date, Actions (Download, Delete)
- **Type filter:** Filter dropdown to filter by document type
- **Empty state:** "No documents uploaded yet"

#### Previous Schools Section (`students/[id]/previous-schools-section.tsx`)

- **Inline list:** Cards showing each previous school with all fields
- **Add button:** Opens a form dialog with all PreviousSchoolCreate fields
- **Edit button:** Opens the same dialog pre-populated
- **Delete button:** Confirmation dialog, then hard delete
- **Empty state:** "No previous school records"

#### Medical Form Enhancement (`students/[id]/medical-info-form.tsx`)

Replace the existing plain text medical inputs with a structured form:

- **Conditions section:** Repeatable field group (name, severity dropdown, diagnosed date, notes). Add/remove buttons.
- **Allergies section:** Repeatable field group (name, severity, reaction). Add/remove buttons.
- **Medications section:** Repeatable field group (name, dosage, frequency, prescriber). Add/remove buttons.
- **Emergency protocol:** Textarea
- **Doctor info:** Name, phone, hospital text fields
- **Blood group:** Dropdown (A+, A-, B+, B-, AB+, AB-, O+, O-)

On save, writes to both `structured_medical` JSONB AND the legacy text fields for backward compatibility.

#### Student Create/Edit Form Updates

Add `birth_certificate_number` field in the "ID Documents" section of the student create/edit form, alongside `ghana_card_number` and `nhis_number`.

---

## 8. Test Plan

### 8.1 `tests/test_student_documents.py`

| # | Test | Type | Description |
|---|------|------|-------------|
| 1 | `test_upload_document_success` | Unit | Upload a PDF, verify DB record and S3 key format |
| 2 | `test_upload_invalid_mime_type` | Unit | Reject .exe or unsupported type |
| 3 | `test_upload_file_too_large` | Unit | Reject file > 10 MB |
| 4 | `test_upload_storage_quota_exceeded` | Unit | Reject when student's total storage exceeds plan limit |
| 5 | `test_list_documents` | Unit | List all documents for a student, verify total_size_bytes |
| 6 | `test_list_documents_filter_by_type` | Unit | Filter by document_type returns only matching |
| 7 | `test_delete_document` | Unit | Soft-delete sets deleted_at, doesn't appear in list |
| 8 | `test_delete_document_idor` | Security | Cannot delete document belonging to different student |
| 9 | `test_download_url` | Unit | Returns presigned URL with expires_in |
| 10 | `test_download_url_idor` | Security | Cannot get URL for document of different student |
| 11 | `test_documents_rls` | RLS | Tenant A cannot see tenant B's documents |

### 8.2 `tests/test_previous_schools.py`

| # | Test | Type | Description |
|---|------|------|-------------|
| 1 | `test_add_previous_school` | Unit | Create record, verify all fields |
| 2 | `test_list_previous_schools` | Unit | Returns ordered by created_at DESC |
| 3 | `test_update_previous_school` | Unit | Partial update works |
| 4 | `test_update_previous_school_idor` | Security | Cannot update record of different student |
| 5 | `test_delete_previous_school` | Unit | Hard delete removes record |
| 6 | `test_delete_previous_school_idor` | Security | Cannot delete record of different student |
| 7 | `test_multiple_previous_schools` | Unit | Student can have multiple records |
| 8 | `test_previous_schools_rls` | RLS | Tenant isolation enforced |

### 8.3 `tests/test_student_profile_fields.py`

| # | Test | Type | Description |
|---|------|------|-------------|
| 1 | `test_create_student_with_birth_cert` | Unit | birth_certificate_number stored correctly |
| 2 | `test_update_student_structured_medical` | Unit | JSONB stored and retrieved correctly |
| 3 | `test_structured_medical_validation` | Unit | Invalid severity value rejected by Pydantic |
| 4 | `test_backward_compat_text_fields` | Unit | Existing text fields still work alongside JSONB |
| 5 | `test_birth_cert_in_response` | Unit | Field appears in StudentResponse |

---

## 9. Checklist

- [ ] Create migration `20260326_0500_student_documents_profile.py`
- [ ] Run migration
- [ ] Add `StudentDocumentType` enum to `models/student.py`
- [ ] Add `StudentDocument` model to `models/student.py`
- [ ] Add `PreviousSchool` model to `models/student.py`
- [ ] Add `birth_certificate_number` and `structured_medical` columns to `Student` model
- [ ] Add relationships to `Student` model
- [ ] Register new models in `db/base.py`
- [ ] Add schemas to `schemas/student.py`
- [ ] Create `services/student/document_service.py` with `StudentDocumentMixin`
- [ ] Update `services/student/__init__.py`
- [ ] Update `StudentCreate`, `StudentUpdate`, `StudentResponse` schemas
- [ ] Add 8 endpoints to `api/v1/endpoints/students.py`
- [ ] Add `student_documents` and `previous_schools` to `TENANT_SCOPED_TABLES` in `tests/conftest.py`
- [ ] Add both tables to `backend/scripts/verify_rls.py`
- [ ] Add both tables to `backend/app/tasks/tenant_cleanup.py`
- [ ] Write `tests/test_student_documents.py` (~11 tests)
- [ ] Write `tests/test_previous_schools.py` (~8 tests)
- [ ] Write `tests/test_student_profile_fields.py` (~5 tests)
- [ ] Add RLS tests for new tables
- [ ] Add TypeScript types to `frontend/types/index.ts`
- [ ] Add server actions to `frontend/actions/students.action.ts`
- [ ] Create `student-documents.tsx` component
- [ ] Create `previous-schools-section.tsx` component
- [ ] Create `medical-info-form.tsx` component
- [ ] Add "Documents" tab to student detail page
- [ ] Add "Previous Schools" section to student detail page
- [ ] Add `birth_certificate_number` to create/edit forms
- [ ] Test document upload/download via Swagger UI
- [ ] Test storage quota enforcement
