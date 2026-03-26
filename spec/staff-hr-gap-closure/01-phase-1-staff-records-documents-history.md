# Phase 1: Staff Records, Documents & Employment History

**Duration:** 3-4 days
**Prerequisites:** None
**Migration Chain:** `20260425_0400` → `20260426_0100` → `20260426_0200` → `20260426_0300`
**New Tables:** 2 (`staff_documents`, `staff_employment_history`)
**New Columns:** 5 on `staff` table
**New Endpoints:** 6
**Tests:** ~25

---

## 1. Overview

Phase 1 closes the remaining staff records gaps: missing fields (TIN, employment type, GES staff ID), document management (certificates, contracts), and employment history tracking (promotions, transfers, department changes).

---

## 2. Task Breakdown

### Task 1.1: Migration — Add Columns to Staff Table

**File:** `backend/alembic/versions/20260426_0100_staff_hr_fields.py`
**Revises:** `20260425_0400`

**Operations:**

```python
# 1. Create employment type enum
op.execute("""
    CREATE TYPE employmenttype AS ENUM (
        'full_time', 'part_time', 'contract', 'temporary', 'intern'
    )
""")

# 2. Add new columns to staff table
op.add_column('staff', sa.Column('tin_number', sa.String(50), nullable=True))
op.add_column('staff', sa.Column('employment_type',
    sa.Enum('full_time', 'part_time', 'contract', 'temporary', 'intern',
            name='employmenttype', create_type=False),
    nullable=True))
op.add_column('staff', sa.Column('ges_staff_id', sa.String(50), nullable=True))
op.add_column('staff', sa.Column('nationality', sa.String(100), nullable=True))
op.add_column('staff', sa.Column('marital_status', sa.String(20), nullable=True))

# 3. Create index for employment_type filtering
op.create_index(
    'ix_staff_employment_type',
    'staff',
    ['tenant_id', 'employment_type'],
    postgresql_where=text("employment_type IS NOT NULL")
)
```

**Downgrade:**
```python
op.drop_index('ix_staff_employment_type')
op.drop_column('staff', 'marital_status')
op.drop_column('staff', 'nationality')
op.drop_column('staff', 'ges_staff_id')
op.drop_column('staff', 'employment_type')
op.drop_column('staff', 'tin_number')
op.execute("DROP TYPE employmenttype")
```

### Task 1.2: Update Staff Model

**File:** `backend/app/models/staff.py`

Add new enum and columns to existing `Staff` model:

```python
class EmploymentType(str, Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    TEMPORARY = "temporary"
    INTERN = "intern"
```

Add to `Staff` class:
```python
tin_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
employment_type: Mapped[str | None] = mapped_column(
    SAEnum(EmploymentType, name="employmenttype",
           values_callable=lambda x: [e.value for e in x]),
    nullable=True
)
ges_staff_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
nationality: Mapped[str | None] = mapped_column(String(100), nullable=True)
marital_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
```

### Task 1.3: Update Staff Schemas

**File:** `backend/app/schemas/staff.py`

Add to `StaffCreate`:
```python
tin_number: str | None = None
employment_type: str | None = None  # full_time, part_time, contract, temporary, intern
ges_staff_id: str | None = None
nationality: str | None = None
marital_status: str | None = None
```

Add same fields to `StaffUpdate` (all Optional).

Add to `StaffResponse`:
```python
tin_number: str | None = None
employment_type: str | None = None
ges_staff_id: str | None = None
nationality: str | None = None
marital_status: str | None = None
```

**Do NOT add these to `StaffListResponse`** — list view doesn't need TIN/nationality. Keep it lean.

**SECURITY: Sensitive Field Masking** — `tin_number`, `ssnit_number`, `ghana_card_number`, `bank_name`, `bank_branch`, and `account_number` are sensitive PII. In `StaffResponse`, these fields MUST be masked (show last 4 digits only, e.g. `****5678`). Create a separate `StaffSensitiveFieldsResponse` returned only by a dedicated `GET /staff/{id}/sensitive-fields` endpoint requiring `payroll.read` or `staff.update` permission. This prevents users with only `staff.read` (academic_head, teacher) from seeing full financial identifiers.

Similarly, `salary_changed` events in employment history must redact `previous_value`/`new_value` unless the requesting user has `payroll.read` permission.

### Task 1.4: Update Staff Service for New Fields

**File:** `backend/app/services/staff/staff_service.py`

1. Add new fields to `create_staff()` method — pass through from schema to model.
2. Add new fields to `update_staff()` method — include in enum conversion handling for `employment_type`.
3. Update `import_staff_from_file()` — add column auto-mapping for:
   - `tin_number` → aliases: `tin`, `tax_id`, `tax_identification_number`
   - `employment_type` → aliases: `employment_type`, `emp_type`, `contract_type`
   - `ges_staff_id` → aliases: `ges_id`, `ges_staff_id`, `ges_number`
   - `nationality` → aliases: `nationality`, `country`
   - `marital_status` → aliases: `marital_status`, `marital`
4. Add `_parse_employment_type()` helper (similar to `_parse_staff_type()`):
   ```python
   def _parse_employment_type(self, value: str) -> str | None:
       mapping = {
           "full time": "full_time", "full-time": "full_time", "ft": "full_time",
           "part time": "part_time", "part-time": "part_time", "pt": "part_time",
           "contract": "contract", "contractor": "contract",
           "temporary": "temporary", "temp": "temporary",
           "intern": "intern", "internship": "intern",
       }
       return mapping.get(value.lower().strip())
   ```
5. Update CSV export to include new fields.

### Task 1.5: Migration — Staff Documents Table

**File:** `backend/alembic/versions/20260426_0200_staff_documents.py`
**Revises:** `20260426_0100`

**Operations:**

```python
# 1. Create document type enum
op.execute("""
    CREATE TYPE staffdocumenttype AS ENUM (
        'contract', 'certificate', 'cv_resume', 'id_document',
        'reference_letter', 'disciplinary', 'training', 'medical', 'other'
    )
""")

# 2. Create staff_documents table
op.create_table(
    'staff_documents',
    sa.Column('id', sa.dialects.postgresql.UUID(), server_default=sa.text('gen_random_uuid()'), primary_key=True),
    sa.Column('tenant_id', sa.dialects.postgresql.UUID(), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
    sa.Column('school_id', sa.dialects.postgresql.UUID(), sa.ForeignKey('schools.id', ondelete='SET NULL'), nullable=True),
    sa.Column('staff_id', sa.dialects.postgresql.UUID(), sa.ForeignKey('staff.id', ondelete='CASCADE'), nullable=False),
    sa.Column('document_type', sa.Enum('contract', 'certificate', 'cv_resume', 'id_document',
              'reference_letter', 'disciplinary', 'training', 'medical', 'other',
              name='staffdocumenttype', create_type=False), nullable=False),
    sa.Column('file_name', sa.String(255), nullable=False),
    sa.Column('file_key', sa.String(500), nullable=False),  # S3 key
    sa.Column('file_size', sa.Integer, nullable=False),       # bytes
    sa.Column('mime_type', sa.String(100), nullable=False),
    sa.Column('description', sa.Text, nullable=True),
    sa.Column('uploaded_by', sa.dialects.postgresql.UUID(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
)

# 3. Indexes
op.create_index('ix_staff_documents_tenant_staff', 'staff_documents', ['tenant_id', 'staff_id'])
op.create_index('ix_staff_documents_type', 'staff_documents', ['tenant_id', 'document_type'])

# 4. RLS
op.execute("ALTER TABLE staff_documents ENABLE ROW LEVEL SECURITY")
op.execute("ALTER TABLE staff_documents FORCE ROW LEVEL SECURITY")
op.execute("""
    CREATE POLICY tenant_isolation ON staff_documents
        FOR ALL
        USING (tenant_id = get_current_tenant_id())
        WITH CHECK (tenant_id = get_current_tenant_id())
""")
op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON staff_documents TO sims_app_user")
```

### Task 1.6: Staff Document Model

**File:** `backend/app/models/staff.py` (add to existing file)

```python
class StaffDocumentType(str, Enum):
    CONTRACT = "contract"
    CERTIFICATE = "certificate"
    CV_RESUME = "cv_resume"
    ID_DOCUMENT = "id_document"
    REFERENCE_LETTER = "reference_letter"
    DISCIPLINARY = "disciplinary"
    TRAINING = "training"
    MEDICAL = "medical"
    OTHER = "other"


class StaffDocument(TenantMixin, SoftDeleteMixin, Base):
    __tablename__ = "staff_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("schools.id", ondelete="SET NULL"), nullable=True
    )
    staff_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id", ondelete="CASCADE"), nullable=False
    )
    document_type: Mapped[str] = mapped_column(
        SAEnum(StaffDocumentType, name="staffdocumenttype",
               values_callable=lambda x: [e.value for e in x]),
        nullable=False
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_key: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    staff: Mapped["Staff"] = relationship(back_populates="documents", lazy="raise")
```

Add to `Staff` model:
```python
documents: Mapped[list["StaffDocument"]] = relationship(
    back_populates="staff", lazy="raise", cascade="all, delete-orphan"
)
```

### Task 1.7: Staff Document Schemas

**File:** `backend/app/schemas/staff.py` (add to existing file)

```python
class StaffDocumentResponse(BaseModel):
    id: UUID
    staff_id: UUID
    document_type: str
    file_name: str
    file_size: int
    mime_type: str
    description: str | None = None
    download_url: str  # presigned S3 URL
    uploaded_by: UUID | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

### Task 1.8: Staff Document Service

**File:** `backend/app/services/staff/document_service.py` (NEW)

Clone pattern from `backend/app/services/student/document_service.py`.

```python
class StaffDocumentService:
    """Manages staff document uploads, downloads, and deletions via S3."""

    ALLOWED_MIME_TYPES = {
        "application/pdf",
        "image/jpeg",
        "image/png",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

    def __init__(self, db: AsyncSession):
        self.db = db

    async def upload_document(
        self,
        tenant_id: UUID,
        staff_id: UUID,
        document_type: str,
        file: UploadFile,
        uploaded_by: UUID,
        description: str | None = None,
        school_id: UUID | None = None,
    ) -> StaffDocument:
        """Upload a staff document to S3 and create DB record."""
        # 1. Validate staff exists and belongs to tenant
        # 2. Validate file size (read content, check len <= MAX_FILE_SIZE)
        # 3. Magic byte validation (validate_file_content from existing utils)
        # 4. Validate MIME type against ALLOWED_MIME_TYPES
        # 5. Sanitize filename (remove path traversal, special chars)
        # 6. Generate S3 key: tenants/{tenant_id}/staff/{staff_id}/documents/{uuid}-{safe_name}
        # 7. Upload to S3 via get_s3_service()
        # 8. Create StaffDocument record
        # 9. flush() + refresh()
        # 10. Return document

    async def list_documents(
        self,
        tenant_id: UUID,
        staff_id: UUID,
        document_type: str | None = None,
    ) -> list[StaffDocument]:
        """List all documents for a staff member, optionally filtered by type."""
        # Query with tenant_id + staff_id + deleted_at IS NULL
        # Optional filter by document_type
        # Order by created_at DESC

    async def get_download_url(
        self,
        tenant_id: UUID,
        staff_id: UUID,
        document_id: UUID,
    ) -> str:
        """Generate presigned S3 download URL (15-min expiry)."""
        # 1. Fetch document, verify tenant_id + staff_id match
        # 2. Generate presigned URL via get_s3_service().generate_presigned_url(file_key, 900)
        # 3. Return URL

    async def delete_document(
        self,
        tenant_id: UUID,
        staff_id: UUID,
        document_id: UUID,
    ) -> None:
        """Soft-delete a staff document."""
        # 1. Fetch document, verify tenant_id + staff_id match
        # 2. Set deleted_at = now
        # 3. flush()
        # Note: S3 file NOT deleted immediately (retention policy handles cleanup)
```

### Task 1.9: Staff Document Endpoints

**File:** `backend/app/api/v1/endpoints/staff/documents.py` (NEW)

```python
router = APIRouter()

@router.post("/{staff_id}/documents", response_model=StaffDocumentResponse, status_code=201)
async def upload_staff_document(
    staff_id: UUID,
    document_type: str = Form(...),
    description: str | None = Form(None),
    file: UploadFile = File(...),
    user: ValidatedUser = Depends(require_permissions("staff.update")),
    db: AsyncSession = Depends(get_db),
):
    """Upload a document for a staff member."""
    service = StaffDocumentService(db)
    doc = await service.upload_document(
        tenant_id=user.tenant_id,
        staff_id=staff_id,
        document_type=document_type,
        file=file,
        uploaded_by=user.id,
        description=description,
        school_id=user.school_id,
    )
    # Generate download URL for response
    download_url = await service.get_download_url(user.tenant_id, staff_id, doc.id)
    return StaffDocumentResponse(
        id=doc.id,
        staff_id=doc.staff_id,
        document_type=doc.document_type,
        file_name=doc.file_name,
        file_size=doc.file_size,
        mime_type=doc.mime_type,
        description=doc.description,
        download_url=download_url,
        uploaded_by=doc.uploaded_by,
        created_at=doc.created_at,
    )


@router.get("/{staff_id}/documents", response_model=list[StaffDocumentResponse])
async def list_staff_documents(
    staff_id: UUID,
    document_type: str | None = None,
    user: ValidatedUser = Depends(require_permissions("staff.read")),
    db: AsyncSession = Depends(get_db),
):
    """List all documents for a staff member."""


@router.get("/{staff_id}/documents/{document_id}")
async def get_document_download_url(
    staff_id: UUID,
    document_id: UUID,
    user: ValidatedUser = Depends(require_permissions("staff.read")),
    db: AsyncSession = Depends(get_db),
):
    """Get presigned download URL for a staff document."""
    # Returns {"download_url": "https://..."}


@router.delete("/{staff_id}/documents/{document_id}", status_code=204)
async def delete_staff_document(
    staff_id: UUID,
    document_id: UUID,
    user: ValidatedUser = Depends(require_permissions("staff.delete")),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a staff document."""
```

### Task 1.10: Migration — Employment History Table

**File:** `backend/alembic/versions/20260426_0300_employment_history.py`
**Revises:** `20260426_0200`

**Operations:**

```python
# 1. Create event type enum
op.execute("""
    CREATE TYPE employmenteventtype AS ENUM (
        'hired', 'promoted', 'demoted', 'transferred', 'title_changed',
        'department_changed', 'status_changed', 'salary_changed', 'contract_renewed'
    )
""")

# 2. Create staff_employment_history table
op.create_table(
    'staff_employment_history',
    sa.Column('id', sa.dialects.postgresql.UUID(), server_default=sa.text('gen_random_uuid()'), primary_key=True),
    sa.Column('tenant_id', sa.dialects.postgresql.UUID(), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
    sa.Column('school_id', sa.dialects.postgresql.UUID(), sa.ForeignKey('schools.id', ondelete='SET NULL'), nullable=True),
    sa.Column('staff_id', sa.dialects.postgresql.UUID(), sa.ForeignKey('staff.id', ondelete='CASCADE'), nullable=False),
    sa.Column('event_type', sa.Enum('hired', 'promoted', 'demoted', 'transferred', 'title_changed',
              'department_changed', 'status_changed', 'salary_changed', 'contract_renewed',
              name='employmenteventtype', create_type=False), nullable=False),
    sa.Column('effective_date', sa.Date, nullable=False),
    sa.Column('previous_value', sa.String(255), nullable=True),
    sa.Column('new_value', sa.String(255), nullable=True),
    sa.Column('previous_department_id', sa.dialects.postgresql.UUID(), sa.ForeignKey('departments.id', ondelete='SET NULL'), nullable=True),
    sa.Column('new_department_id', sa.dialects.postgresql.UUID(), sa.ForeignKey('departments.id', ondelete='SET NULL'), nullable=True),
    sa.Column('previous_job_title', sa.String(100), nullable=True),
    sa.Column('new_job_title', sa.String(100), nullable=True),
    sa.Column('notes', sa.Text, nullable=True),
    sa.Column('recorded_by', sa.dialects.postgresql.UUID(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
)

# 3. Indexes
op.create_index('ix_staff_emp_history_tenant_staff', 'staff_employment_history', ['tenant_id', 'staff_id'])
op.create_index('ix_staff_emp_history_date', 'staff_employment_history', ['tenant_id', sa.text('effective_date DESC')])

# 4. RLS
op.execute("ALTER TABLE staff_employment_history ENABLE ROW LEVEL SECURITY")
op.execute("ALTER TABLE staff_employment_history FORCE ROW LEVEL SECURITY")
op.execute("""
    CREATE POLICY tenant_isolation ON staff_employment_history
        FOR ALL
        USING (tenant_id = get_current_tenant_id())
        WITH CHECK (tenant_id = get_current_tenant_id())
""")
op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON staff_employment_history TO sims_app_user")
```

### Task 1.11: Employment History Model

**File:** `backend/app/models/staff.py` (add to existing file)

```python
class EmploymentEventType(str, Enum):
    HIRED = "hired"
    PROMOTED = "promoted"
    DEMOTED = "demoted"
    TRANSFERRED = "transferred"
    TITLE_CHANGED = "title_changed"
    DEPARTMENT_CHANGED = "department_changed"
    STATUS_CHANGED = "status_changed"
    SALARY_CHANGED = "salary_changed"
    CONTRACT_RENEWED = "contract_renewed"


class StaffEmploymentHistory(TenantMixin, Base):
    __tablename__ = "staff_employment_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("schools.id", ondelete="SET NULL"), nullable=True
    )
    staff_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(
        SAEnum(EmploymentEventType, name="employmenteventtype",
               values_callable=lambda x: [e.value for e in x]),
        nullable=False
    )
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    previous_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    new_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    previous_department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True
    )
    new_department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True
    )
    previous_job_title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    new_job_title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )

    # Relationships
    staff: Mapped["Staff"] = relationship(back_populates="employment_history", lazy="raise")
```

Add to `Staff` model:
```python
employment_history: Mapped[list["StaffEmploymentHistory"]] = relationship(
    back_populates="staff", lazy="raise", cascade="all, delete-orphan",
    order_by="desc(StaffEmploymentHistory.effective_date)"
)
```

### Task 1.12: Employment History Schemas

**File:** `backend/app/schemas/staff.py`

```python
class StaffEmploymentHistoryCreate(BaseModel):
    event_type: str  # hired, promoted, transferred, etc.
    effective_date: date
    previous_value: str | None = None
    new_value: str | None = None
    previous_department_id: UUID | None = None
    new_department_id: UUID | None = None
    previous_job_title: str | None = None
    new_job_title: str | None = None
    notes: str | None = None


class StaffEmploymentHistoryResponse(BaseModel):
    id: UUID
    staff_id: UUID
    event_type: str
    effective_date: date
    previous_value: str | None = None
    new_value: str | None = None
    previous_department_id: UUID | None = None
    new_department_id: UUID | None = None
    previous_job_title: str | None = None
    new_job_title: str | None = None
    notes: str | None = None
    recorded_by: UUID | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

### Task 1.13: Employment History Service

**File:** `backend/app/services/staff/history_service.py` (NEW)

```python
class StaffHistoryService:
    """Manages employment history records for staff members."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_event(
        self,
        tenant_id: UUID,
        staff_id: UUID,
        event_type: str,
        effective_date: date,
        recorded_by: UUID | None = None,
        school_id: UUID | None = None,
        **kwargs,  # previous_value, new_value, department IDs, job titles, notes
    ) -> StaffEmploymentHistory:
        """Create a new employment history record."""
        # 1. Validate staff exists and belongs to tenant
        # 2. Validate event_type is valid EmploymentEventType
        # 3. Create StaffEmploymentHistory record
        # 4. flush() + refresh()
        # 5. Return record

    async def list_history(
        self,
        tenant_id: UUID,
        staff_id: UUID,
    ) -> list[StaffEmploymentHistory]:
        """List all employment history for a staff member, newest first."""
        # Query with tenant_id + staff_id
        # Order by effective_date DESC, created_at DESC

    async def auto_record_changes(
        self,
        tenant_id: UUID,
        staff_id: UUID,
        old_staff: Staff,
        new_data: dict,
        recorded_by: UUID | None = None,
        school_id: UUID | None = None,
    ) -> list[StaffEmploymentHistory]:
        """
        Automatically record history events when staff fields change.
        Called from StaffService.update_staff().

        Tracks changes to: job_title, department_id, status, employment_type
        """
        events = []
        today = date.today()

        # Check job_title change
        if "job_title" in new_data and new_data["job_title"] != old_staff.job_title:
            events.append(await self.record_event(
                tenant_id=tenant_id,
                staff_id=staff_id,
                event_type="title_changed",
                effective_date=today,
                previous_job_title=old_staff.job_title,
                new_job_title=new_data["job_title"],
                recorded_by=recorded_by,
                school_id=school_id,
            ))

        # Check department_id change
        if "department_id" in new_data and new_data["department_id"] != old_staff.department_id:
            events.append(await self.record_event(
                tenant_id=tenant_id,
                staff_id=staff_id,
                event_type="department_changed",
                effective_date=today,
                previous_department_id=old_staff.department_id,
                new_department_id=new_data["department_id"],
                recorded_by=recorded_by,
                school_id=school_id,
            ))

        # Check status change
        if "status" in new_data and new_data["status"] != old_staff.status:
            events.append(await self.record_event(
                tenant_id=tenant_id,
                staff_id=staff_id,
                event_type="status_changed",
                effective_date=today,
                previous_value=old_staff.status,
                new_value=new_data["status"],
                recorded_by=recorded_by,
                school_id=school_id,
            ))

        return events
```

### Task 1.14: Update StaffService to Auto-Record History

**File:** `backend/app/services/staff/staff_service.py`

In the existing `update_staff()` method, add after fetching the staff record but before applying changes:

```python
async def update_staff(self, tenant_id, staff_id, data, current_user_id=None, school_id=None):
    staff = await self.get_staff(tenant_id, staff_id)
    if not staff:
        raise self.Error("Staff member not found", "NOT_FOUND")

    # Auto-record employment history for tracked fields
    history_service = StaffHistoryService(self.db)
    update_dict = data.model_dump(exclude_unset=True) if hasattr(data, 'model_dump') else data
    await history_service.auto_record_changes(
        tenant_id=tenant_id,
        staff_id=staff.id,
        old_staff=staff,
        new_data=update_dict,
        recorded_by=current_user_id,
        school_id=school_id,
    )

    # ... existing update logic ...
```

**Important:** Pass `current_user_id` to `update_staff()` from the endpoint. The endpoint already has `user: ValidatedUser` — pass `user.id`.

### Task 1.15: Employment History Endpoints

**File:** `backend/app/api/v1/endpoints/staff/history.py` (NEW)

```python
router = APIRouter()

@router.get("/{staff_id}/employment-history", response_model=list[StaffEmploymentHistoryResponse])
async def list_employment_history(
    staff_id: UUID,
    user: ValidatedUser = Depends(require_permissions("staff.read")),
    db: AsyncSession = Depends(get_db),
):
    """List employment history for a staff member."""
    service = StaffHistoryService(db)
    return await service.list_history(user.tenant_id, staff_id)


@router.post("/{staff_id}/employment-history", response_model=StaffEmploymentHistoryResponse, status_code=201)
async def create_employment_event(
    staff_id: UUID,
    data: StaffEmploymentHistoryCreate,
    user: ValidatedUser = Depends(require_permissions("staff.update")),
    db: AsyncSession = Depends(get_db),
):
    """Manually record an employment history event."""
    service = StaffHistoryService(db)
    return await service.record_event(
        tenant_id=user.tenant_id,
        staff_id=staff_id,
        recorded_by=user.id,
        school_id=user.school_id,
        **data.model_dump(),
    )
```

### Task 1.16: Register New Routes

**File:** `backend/app/api/v1/endpoints/staff/__init__.py`

Import and include the new routers:
```python
from .documents import router as documents_router
from .history import router as history_router

# Add to combined router:
router.include_router(documents_router, tags=["Staff Documents"])
router.include_router(history_router, tags=["Staff History"])
```

### Task 1.17: Update `db/base.py`

Add new models to the import list:
```python
from app.models.staff import StaffDocument, StaffEmploymentHistory  # noqa: F401
```

### Task 1.18: Frontend — Update Staff Forms

**Files to modify:**
- `frontend/app/(dashboard)/staff/new/new-staff-form.tsx`
- `frontend/app/(dashboard)/staff/[id]/edit/page.tsx`

Add new fields to the Employment step of the staff form:

```tsx
// In the Employment step (Step 3), add:
<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
  <FormField name="employment_type" label="Employment Type">
    <Select>
      <SelectTrigger><SelectValue placeholder="Select type" /></SelectTrigger>
      <SelectContent>
        <SelectItem value="full_time">Full Time</SelectItem>
        <SelectItem value="part_time">Part Time</SelectItem>
        <SelectItem value="contract">Contract</SelectItem>
        <SelectItem value="temporary">Temporary</SelectItem>
        <SelectItem value="intern">Intern</SelectItem>
      </SelectContent>
    </Select>
  </FormField>

  <FormField name="ges_staff_id" label="GES Staff ID">
    <Input placeholder="GES staff ID (public schools)" />
  </FormField>

  <FormField name="tin_number" label="TIN Number">
    <Input placeholder="Tax Identification Number" />
  </FormField>

  <FormField name="nationality" label="Nationality">
    <Input placeholder="e.g., Ghanaian" />
  </FormField>

  <FormField name="marital_status" label="Marital Status">
    <Select>
      <SelectTrigger><SelectValue placeholder="Select status" /></SelectTrigger>
      <SelectContent>
        <SelectItem value="single">Single</SelectItem>
        <SelectItem value="married">Married</SelectItem>
        <SelectItem value="divorced">Divorced</SelectItem>
        <SelectItem value="widowed">Widowed</SelectItem>
      </SelectContent>
    </Select>
  </FormField>
</div>
```

Update the Zod schema to include new optional fields.

### Task 1.19: Frontend — Staff Detail Page Tabs

**File:** `frontend/app/(dashboard)/staff/[id]/page.tsx`

Add two new tabs to the staff detail page: "Documents" and "History".

Use the existing tab pattern (if tabs exist) or add a Tabs component:

```tsx
<Tabs defaultValue="overview">
  <TabsList>
    <TabsTrigger value="overview">Overview</TabsTrigger>
    <TabsTrigger value="assignments">Assignments</TabsTrigger>
    <TabsTrigger value="documents">Documents</TabsTrigger>
    <TabsTrigger value="history">History</TabsTrigger>
  </TabsList>
  <TabsContent value="overview">
    {/* Existing staff detail content */}
  </TabsContent>
  <TabsContent value="assignments">
    {/* Existing assignments card */}
  </TabsContent>
  <TabsContent value="documents">
    <StaffDocuments staffId={staff.id} />
  </TabsContent>
  <TabsContent value="history">
    <EmploymentHistory staffId={staff.id} />
  </TabsContent>
</Tabs>
```

### Task 1.20: Frontend — Staff Documents Component

**File:** `frontend/app/(dashboard)/staff/[id]/staff-documents.tsx` (NEW)

Client component that:
1. Fetches documents via `getStaffDocuments(staffId)` server action
2. Displays a table: Type, File Name, Size, Uploaded, Actions (Download, Delete)
3. Upload button opens `DocumentUploadDialog` (file picker + type selector + description)
4. Download triggers presigned URL fetch and browser download
5. Delete with confirmation dialog

### Task 1.21: Frontend — Employment History Component

**File:** `frontend/app/(dashboard)/staff/[id]/employment-history.tsx` (NEW)

Client component that:
1. Fetches history via `getStaffEmploymentHistory(staffId)` server action
2. Displays a vertical timeline (newest first)
3. Each event shows: icon (based on event_type), date, description, notes
4. "Add Event" button for manual history entry (dialog with event type + date + notes)

### Task 1.22: Frontend — Server Actions

**File:** `frontend/actions/staff.action.ts` (add to existing)

```typescript
export async function uploadStaffDocument(staffId: string, formData: FormData): Promise<ActionResult<StaffDocument>> {
  // POST /staff/{staffId}/documents (multipart)
}

export async function getStaffDocuments(staffId: string, documentType?: string): Promise<ActionResult<StaffDocument[]>> {
  // GET /staff/{staffId}/documents?document_type=...
}

export async function getDocumentDownloadUrl(staffId: string, documentId: string): Promise<ActionResult<{download_url: string}>> {
  // GET /staff/{staffId}/documents/{documentId}
}

export async function deleteStaffDocument(staffId: string, documentId: string): Promise<ActionResult<void>> {
  // DELETE /staff/{staffId}/documents/{documentId}
}

export async function getStaffEmploymentHistory(staffId: string): Promise<ActionResult<StaffEmploymentHistory[]>> {
  // GET /staff/{staffId}/employment-history
}

export async function createStaffEmploymentEvent(staffId: string, data: CreateEmploymentEvent): Promise<ActionResult<StaffEmploymentHistory>> {
  // POST /staff/{staffId}/employment-history
}
```

### Task 1.23: Frontend — TypeScript Types

**File:** `frontend/types/index.ts` (add to existing Staff types section)

```typescript
export type EmploymentType = "full_time" | "part_time" | "contract" | "temporary" | "intern"
export type StaffDocumentType = "contract" | "certificate" | "cv_resume" | "id_document" | "reference_letter" | "disciplinary" | "training" | "medical" | "other"
export type EmploymentEventType = "hired" | "promoted" | "demoted" | "transferred" | "title_changed" | "department_changed" | "status_changed" | "salary_changed" | "contract_renewed"

// Add to existing Staff interface:
// tin_number?: string
// employment_type?: EmploymentType
// ges_staff_id?: string
// nationality?: string
// marital_status?: string

export interface StaffDocument {
  id: string
  staff_id: string
  document_type: StaffDocumentType
  file_name: string
  file_size: number
  mime_type: string
  description?: string
  download_url: string
  uploaded_by?: string
  created_at: string
}

export interface StaffEmploymentHistory {
  id: string
  staff_id: string
  event_type: EmploymentEventType
  effective_date: string
  previous_value?: string
  new_value?: string
  previous_department_id?: string
  new_department_id?: string
  previous_job_title?: string
  new_job_title?: string
  notes?: string
  recorded_by?: string
  created_at: string
}
```

### Task 1.24: Update TENANT_SCOPED_TABLES

**File:** `backend/tests/conftest.py`

Add to the `TENANT_SCOPED_TABLES` list:
```python
# Staff HR (Phase 1)
"staff_documents",
"staff_employment_history",
```

**File:** `backend/scripts/verify_rls.py`

Add same tables to the verification list.

### Task 1.25: Tests

**File:** `backend/tests/test_staff_hr_fields.py` (~8 tests)

```python
# test_create_staff_with_tin_number
# test_create_staff_with_employment_type
# test_create_staff_with_ges_staff_id
# test_create_staff_with_nationality_marital_status
# test_update_staff_tin_number
# test_update_staff_employment_type
# test_csv_import_with_new_fields
# test_csv_export_includes_new_fields
```

**File:** `backend/tests/test_staff_documents.py` (~10 tests)

```python
# test_upload_staff_document_pdf
# test_upload_staff_document_image
# test_upload_rejects_invalid_mime_type
# test_upload_rejects_oversized_file (>10MB)
# test_upload_validates_magic_bytes
# test_list_staff_documents
# test_list_staff_documents_filter_by_type
# test_get_document_download_url
# test_delete_staff_document
# test_staff_documents_tenant_isolation (cross-tenant invisible)
```

**File:** `backend/tests/test_staff_employment_history.py` (~7 tests)

```python
# test_create_manual_employment_event
# test_list_employment_history_ordered_by_date
# test_auto_record_on_job_title_change
# test_auto_record_on_department_change
# test_auto_record_on_status_change
# test_no_auto_record_when_field_unchanged
# test_employment_history_tenant_isolation
```

---

## 3. Acceptance Criteria

- [ ] Staff can be created/updated with TIN, employment type, GES staff ID, nationality, marital status
- [ ] CSV import/export supports all new fields
- [ ] Documents (PDF, JPEG, PNG, DOC, DOCX) can be uploaded per staff member (max 10MB)
- [ ] Documents are stored in S3 with tenant-scoped paths
- [ ] Documents can be listed, downloaded (presigned URL), and soft-deleted
- [ ] Employment history is auto-recorded when job_title, department, or status changes
- [ ] Employment history can be manually created for events like hiring, promotion, contract renewal
- [ ] History displays as a timeline on the staff detail page
- [ ] All new tables have RLS policies and are in TENANT_SCOPED_TABLES
- [ ] All 25 tests pass
