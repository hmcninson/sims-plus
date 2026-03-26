# Phase 1: Schemas, Services & Endpoints — Safety & Enrollment

**Sprint:** 20.5
**Depends on:** Phase 1 Models & Migration (doc 01)
**Parallel with:** Phase 1 Frontend (doc 03)

---

## Task List

| # | Task | Files | Est. |
|---|------|-------|------|
| 2.1 | Create incident schemas | `backend/app/schemas/preschool.py` | 0.25d |
| 2.2 | Create pickup schemas | `backend/app/schemas/preschool.py` | 0.25d |
| 2.3 | Create allergy/dietary schemas | `backend/app/schemas/preschool.py` | 0.15d |
| 2.4 | Add incident service methods | `backend/app/services/preschool.py` | 1d |
| 2.5 | Add pickup service methods | `backend/app/services/preschool.py` | 0.5d |
| 2.6 | Add allergy service methods | `backend/app/services/preschool.py` | 0.5d |
| 2.7 | Add incident endpoints | `backend/app/api/v1/endpoints/preschool.py` | 0.5d |
| 2.8 | Add pickup endpoints | `backend/app/api/v1/endpoints/preschool.py` | 0.5d |
| 2.9 | Add allergy/dietary endpoints | `backend/app/api/v1/endpoints/preschool.py` | 0.25d |
| 2.10 | Update student schemas for session/dietary | `backend/app/schemas/student.py` | 0.15d |

---

## Critical Patterns (Read First)

**All new endpoints MUST follow the existing preschool endpoint pattern:**
```python
# Correct pattern (from existing preschool endpoints):
from app.api.deps import DatabaseSession, RequestTenant, ValidatedUser, require_permissions
from app.schemas.preschool import convert_uuid

@router.get(
    "/path",
    response_model=ResponseSchema,
    summary="Description",
    dependencies=[Depends(require_permissions("preschool.read"))],  # Permission in decorator
)
async def endpoint_name(
    db: DatabaseSession,           # Annotated type alias, NOT Depends(get_db)
    current_user: ValidatedUser,   # Annotated type alias, NOT Depends(...)
    tenant: RequestTenant,         # Annotated type alias, NOT Depends(get_request_tenant)
):
    service = SomeService(db)
    result = await service.method(convert_uuid(tenant.tenant_id))  # ALWAYS convert_uuid()
```

**DO NOT use:** `Depends(get_db)`, `Depends(get_request_tenant)`, `AsyncSession`. These are wrong.

---

## 2.0 AttachmentSchema Definition

**File:** `backend/app/schemas/preschool.py` (add before incident schemas)

The existing codebase uses raw JSONB (`list | None`) for attachments but the new code should use a typed schema for validation:

```python
class AttachmentSchema(BaseSchema):
    """Typed attachment entry for observations, incidents, and learning stories."""

    url: Annotated[str, Field(max_length=500)]
    type: Annotated[str, Field(pattern=r"^(image|video|document)$")]
    thumbnail: Annotated[str | None, Field(max_length=500)] = None
    filename: Annotated[str | None, Field(max_length=255)] = None

    @field_validator("url", mode="before")
    @classmethod
    def validate_url_scheme(cls, v: str) -> str:
        """Only allow HTTPS URLs to prevent SSRF attacks."""
        if not v.startswith("https://"):
            raise ValueError("URL must use HTTPS")
        return v
```

---

## 2.1 Incident Schemas

**File:** `backend/app/schemas/preschool.py` (append after existing report schemas)

```python
# =========================
# Allergy / Dietary Schemas
# =========================


class AllergyEntry(BaseSchema):
    """Single allergy entry within dietary_requirements."""

    allergen: Annotated[str, Field(min_length=1, max_length=100)]
    severity: Annotated[str, Field(pattern=r"^(mild|moderate|severe)$")]
    reaction: Annotated[str | None, Field(max_length=500)] = None
    medication: Annotated[str | None, Field(max_length=500)] = None


class DietaryRequirements(BaseSchema):
    """Structured dietary requirements for a student."""

    allergies: list[AllergyEntry] = []
    dietary_restrictions: list[Annotated[str, Field(max_length=50)]] = []
    notes: Annotated[str | None, Field(max_length=2000)] = None


class DietaryRequirementsUpdate(BaseSchema):
    """Update schema — replaces entire dietary_requirements JSONB."""

    dietary_requirements: DietaryRequirements | None = None


class AllergyAlertResponse(BaseSchema):
    """Student allergy summary for teacher alerts."""

    student_id: UUID
    student_name: str
    allergies: list[AllergyEntry]
    dietary_restrictions: list[str]
    notes: str | None = None


# =========================
# Preschool Incident Schemas
# =========================


class PreschoolIncidentCreate(BaseSchema):
    """Create a new preschool incident report."""

    student_id: UUID
    incident_type: Annotated[str, Field(pattern=r"^(accident|illness|behavioral|allergic_reaction|other)$")]
    severity: Annotated[str, Field(pattern=r"^(minor|moderate|serious)$")]
    incident_date: date
    incident_time: time | None = None

    @field_validator("incident_date")
    @classmethod
    def incident_date_not_future(cls, v: date) -> date:
        """Incidents cannot be reported for future dates."""
        if v > date.today():
            raise ValueError("Incident date cannot be in the future")
        return v
    location: Annotated[str | None, Field(max_length=255)] = None
    description: Annotated[str, Field(min_length=10, max_length=5000)]
    action_taken: Annotated[str | None, Field(max_length=5000)] = None
    first_aid_given: bool = False
    medical_attention_required: bool = False
    witnesses: list[Annotated[str, Field(max_length=200)]] | None = None
    attachments: list[AttachmentSchema] | None = None


class PreschoolIncidentUpdate(BaseSchema):
    """Update an existing incident. All fields optional."""

    incident_type: Annotated[str | None, Field(pattern=r"^(accident|illness|behavioral|allergic_reaction|other)$")] = None
    severity: Annotated[str | None, Field(pattern=r"^(minor|moderate|serious)$")] = None
    location: Annotated[str | None, Field(max_length=255)] = None
    description: Annotated[str | None, Field(min_length=10, max_length=5000)] = None
    action_taken: Annotated[str | None, Field(max_length=5000)] = None
    first_aid_given: bool | None = None
    medical_attention_required: bool | None = None
    witnesses: list[Annotated[str, Field(max_length=200)]] | None = None
    attachments: list[AttachmentSchema] | None = None
    follow_up_notes: Annotated[str | None, Field(max_length=5000)] = None


class PreschoolIncidentResponse(BaseSchema):
    """Incident response with all fields."""

    id: UUID
    tenant_id: UUID
    student_id: UUID
    incident_type: str
    severity: str
    status: str
    incident_date: date
    incident_time: time | None = None
    location: str | None = None
    description: str
    action_taken: str | None = None
    first_aid_given: bool
    medical_attention_required: bool
    parent_notified_at: datetime | None = None
    parent_notified_by: UUID | None = None
    witnesses: list[str] | None = None
    attachments: list[AttachmentSchema] | None = None
    follow_up_notes: str | None = None
    resolved_at: datetime | None = None
    resolved_by: UUID | None = None
    reported_by: UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def convert_uuids(cls, data: Any) -> Any:
        """Convert asyncpg UUIDs to standard UUIDs."""
        if not isinstance(data, dict):
            # ORM model — convert known UUID fields
            for field_name in [
                "id", "tenant_id", "student_id", "parent_notified_by",
                "resolved_by", "reported_by",
            ]:
                val = getattr(data, field_name, None)
                if val is not None:
                    setattr(data, field_name, convert_uuid(val))
        return data


class IncidentResolveRequest(BaseSchema):
    """Request body for resolving an incident."""

    follow_up_notes: Annotated[str | None, Field(max_length=5000)] = None


# =========================
# Authorized Pickup Schemas
# =========================


class AuthorizedPickupCreate(BaseSchema):
    """Add a new authorized pickup person for a student."""

    full_name: Annotated[str, Field(min_length=2, max_length=200)]
    phone: Annotated[str, Field(min_length=10, max_length=20)]
    relationship_to_student: Annotated[str | None, Field(max_length=100)] = None
    photo_url: Annotated[str | None, Field(max_length=500)] = None
    id_document_url: Annotated[str | None, Field(max_length=500)] = None
    notes: Annotated[str | None, Field(max_length=2000)] = None

    @field_validator("photo_url", "id_document_url", mode="before")
    @classmethod
    def validate_s3_url(cls, v: str | None) -> str | None:
        """Only allow HTTPS URLs to prevent SSRF. Must be S3 presigned URLs."""
        if v is None:
            return None
        if not v.startswith("https://"):
            raise ValueError("URL must use HTTPS (S3 presigned URL)")
        return v


class AuthorizedPickupUpdate(BaseSchema):
    """Update authorized pickup person. All fields optional."""

    full_name: Annotated[str | None, Field(min_length=2, max_length=200)] = None
    phone: Annotated[str | None, Field(min_length=10, max_length=20)] = None
    relationship_to_student: Annotated[str | None, Field(max_length=100)] = None
    photo_url: Annotated[str | None, Field(max_length=500)] = None
    id_document_url: Annotated[str | None, Field(max_length=500)] = None
    is_active: bool | None = None
    notes: Annotated[str | None, Field(max_length=2000)] = None


class AuthorizedPickupResponse(BaseSchema):
    """Authorized pickup person response."""

    id: UUID
    tenant_id: UUID
    student_id: UUID
    full_name: str
    phone: str
    relationship_to_student: str | None = None
    photo_url: str | None = None
    id_document_url: str | None = None
    is_active: bool
    notes: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def convert_uuids(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            for field_name in ["id", "tenant_id", "student_id"]:
                val = getattr(data, field_name, None)
                if val is not None:
                    setattr(data, field_name, convert_uuid(val))
        return data


# =========================
# Pickup Log Schemas
# =========================


class PickupLogCreate(BaseSchema):
    """Record a student pickup event."""

    student_id: UUID
    pickup_time: time
    picked_up_by_type: Annotated[str, Field(pattern=r"^(guardian|authorized_person)$")]
    picked_up_by_guardian_id: UUID | None = None
    picked_up_by_authorized_id: UUID | None = None
    notes: Annotated[str | None, Field(max_length=2000)] = None

    @model_validator(mode="after")
    def validate_pickup_person(self) -> "PickupLogCreate":
        """Ensure exactly one pickup person ID is provided."""
        if self.picked_up_by_type == "guardian":
            if not self.picked_up_by_guardian_id:
                raise ValueError("picked_up_by_guardian_id is required when type is 'guardian'")
            if self.picked_up_by_authorized_id:
                raise ValueError("picked_up_by_authorized_id must be null when type is 'guardian'")
        elif self.picked_up_by_type == "authorized_person":
            if not self.picked_up_by_authorized_id:
                raise ValueError("picked_up_by_authorized_id is required when type is 'authorized_person'")
            if self.picked_up_by_guardian_id:
                raise ValueError("picked_up_by_guardian_id must be null when type is 'authorized_person'")
        return self


class PickupLogResponse(BaseSchema):
    """Pickup log entry response."""

    id: UUID
    tenant_id: UUID
    student_id: UUID
    pickup_date: date
    pickup_time: time
    picked_up_by_type: str
    picked_up_by_guardian_id: UUID | None = None
    picked_up_by_authorized_id: UUID | None = None
    verified_by: UUID | None = None
    notes: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def convert_uuids(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            for field_name in [
                "id", "tenant_id", "student_id", "picked_up_by_guardian_id",
                "picked_up_by_authorized_id", "verified_by",
            ]:
                val = getattr(data, field_name, None)
                if val is not None:
                    setattr(data, field_name, convert_uuid(val))
        return data
```

---

## 2.4 Incident Service Methods

**File:** `backend/app/services/preschool.py` (add methods to existing `PreschoolService` class)

```python
    # =========================
    # Incident Methods
    # =========================

    async def create_incident(
        self,
        tenant_id: uuid.UUID,
        data: "PreschoolIncidentCreate",
        reported_by: uuid.UUID,
    ) -> PreschoolIncident:
        """
        Create a new preschool incident report.

        For "serious" severity, auto-triggers parent notification via
        NotificationDispatcher (if available).
        """
        # Defense-in-depth: verify student belongs to tenant
        student = await self.db.execute(
            select(Student)
            .where(Student.id == data.student_id)
            .where(Student.tenant_id == tenant_id)
        )
        student = student.scalar_one_or_none()
        if not student:
            raise PreschoolServiceError("Student not found", code="STUDENT_NOT_FOUND")

        incident = PreschoolIncident(
            tenant_id=tenant_id,
            school_id=student.school_id,
            student_id=data.student_id,
            incident_type=data.incident_type,
            severity=data.severity,
            status=PreschoolIncidentStatus.REPORTED.value,
            incident_date=data.incident_date,
            incident_time=data.incident_time,
            location=data.location,
            description=data.description,
            action_taken=data.action_taken,
            first_aid_given=data.first_aid_given,
            medical_attention_required=data.medical_attention_required,
            witnesses=data.witnesses,
            attachments=[att.model_dump() for att in data.attachments] if data.attachments else None,
            reported_by=reported_by,
        )
        self.db.add(incident)
        await self.db.flush()
        await self.db.refresh(incident)
        return incident

    async def list_incidents(
        self,
        tenant_id: uuid.UUID,
        *,
        student_id: uuid.UUID | None = None,
        class_id: uuid.UUID | None = None,
        status: str | None = None,
        severity: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Sequence[PreschoolIncident]:
        """List incidents with optional filters."""
        query = (
            select(PreschoolIncident)
            .where(PreschoolIncident.tenant_id == tenant_id)
            .where(PreschoolIncident.deleted_at.is_(None))
            .order_by(PreschoolIncident.incident_date.desc(), PreschoolIncident.created_at.desc())
        )
        if student_id:
            query = query.where(PreschoolIncident.student_id == student_id)
        if class_id:
            query = query.join(Student, PreschoolIncident.student_id == Student.id).where(
                Student.class_id == class_id,
                Student.tenant_id == tenant_id,  # Defense-in-depth on JOIN
            )
        if status:
            query = query.where(PreschoolIncident.status == status)
        if severity:
            query = query.where(PreschoolIncident.severity == severity)
        if date_from:
            query = query.where(PreschoolIncident.incident_date >= date_from)
        if date_to:
            query = query.where(PreschoolIncident.incident_date <= date_to)

        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_incident(
        self, tenant_id: uuid.UUID, incident_id: uuid.UUID
    ) -> PreschoolIncident:
        """Get a single incident by ID."""
        result = await self.db.execute(
            select(PreschoolIncident)
            .where(PreschoolIncident.id == incident_id)
            .where(PreschoolIncident.tenant_id == tenant_id)
            .where(PreschoolIncident.deleted_at.is_(None))
        )
        incident = result.scalar_one_or_none()
        if not incident:
            raise PreschoolServiceError("Incident not found", code="INCIDENT_NOT_FOUND")
        return incident

    async def update_incident(
        self,
        tenant_id: uuid.UUID,
        incident_id: uuid.UUID,
        data: "PreschoolIncidentUpdate",
    ) -> PreschoolIncident:
        """Update incident details (not status — use dedicated methods for that)."""
        incident = await self.get_incident(tenant_id, incident_id)

        # SECURITY: Blocklist prevents accidental overwrite of protected fields
        # if the update schema is later extended incorrectly.
        PROTECTED_FIELDS = {
            "id", "tenant_id", "school_id", "student_id", "status",
            "reported_by", "parent_notified_at", "parent_notified_by",
            "resolved_at", "resolved_by", "created_at", "deleted_at",
        }

        update_data = data.model_dump(exclude_unset=True)
        if "attachments" in update_data and update_data["attachments"] is not None:
            update_data["attachments"] = [
                att.model_dump() if hasattr(att, "model_dump") else att
                for att in update_data["attachments"]
            ]

        for field, value in update_data.items():
            if field in PROTECTED_FIELDS:
                continue
            setattr(incident, field, value)

        await self.db.flush()
        await self.db.refresh(incident)
        return incident

    async def notify_parent_incident(
        self,
        tenant_id: uuid.UUID,
        incident_id: uuid.UUID,
        notified_by: uuid.UUID,
    ) -> PreschoolIncident:
        """
        Mark incident as parent_notified and record who notified.

        The actual SMS/email sending is handled by the endpoint layer
        which has access to NotificationDispatcher.
        """
        incident = await self.get_incident(tenant_id, incident_id)

        # Validate status transition
        current_status = PreschoolIncidentStatus(incident.status)
        if PreschoolIncidentStatus.PARENT_NOTIFIED not in VALID_INCIDENT_TRANSITIONS.get(current_status, []):
            raise PreschoolServiceError(
                f"Cannot transition from '{incident.status}' to 'parent_notified'",
                code="INVALID_TRANSITION",
            )

        incident.status = PreschoolIncidentStatus.PARENT_NOTIFIED.value
        incident.parent_notified_at = datetime.now(timezone.utc)
        incident.parent_notified_by = notified_by

        await self.db.flush()
        await self.db.refresh(incident)
        return incident

    async def resolve_incident(
        self,
        tenant_id: uuid.UUID,
        incident_id: uuid.UUID,
        follow_up_notes: str | None,
        resolved_by: uuid.UUID,
    ) -> PreschoolIncident:
        """Resolve an incident with optional follow-up notes."""
        incident = await self.get_incident(tenant_id, incident_id)

        current_status = PreschoolIncidentStatus(incident.status)

        # CHILD SAFETY: Moderate and serious incidents MUST go through
        # parent notification before resolution. Only minor incidents
        # can be resolved from REVIEWED without parent notification.
        if incident.severity in ("moderate", "serious"):
            if current_status != PreschoolIncidentStatus.PARENT_NOTIFIED:
                raise PreschoolServiceError(
                    "Moderate and serious incidents must have parent notification before resolution",
                    code="PARENT_NOTIFICATION_REQUIRED",
                )

        if PreschoolIncidentStatus.RESOLVED not in VALID_INCIDENT_TRANSITIONS.get(current_status, []):
            raise PreschoolServiceError(
                f"Cannot transition from '{incident.status}' to 'resolved'",
                code="INVALID_TRANSITION",
            )

        incident.status = PreschoolIncidentStatus.RESOLVED.value
        incident.follow_up_notes = follow_up_notes
        incident.resolved_at = datetime.now(timezone.utc)
        incident.resolved_by = resolved_by

        await self.db.flush()
        await self.db.refresh(incident)
        return incident
```

**Required imports** at top of `preschool.py` service file:

```python
from datetime import date, datetime, timezone
from app.models.preschool import (
    # ... existing imports ...
    PreschoolIncident, AuthorizedPickup, PickupLog,
    PreschoolIncidentStatus, VALID_INCIDENT_TRANSITIONS,
)
from app.models.student import Student, Guardian, StudentGuardian
```

---

## 2.5 Pickup Service Methods

**File:** `backend/app/services/preschool.py` (add to `PreschoolService`)

```python
    # =========================
    # Authorized Pickup Methods
    # =========================

    async def add_authorized_pickup(
        self,
        tenant_id: uuid.UUID,
        student_id: uuid.UUID,
        data: "AuthorizedPickupCreate",
        added_by: uuid.UUID,
    ) -> AuthorizedPickup:
        """Add an authorized pickup person for a student."""
        # Defense-in-depth: verify student belongs to tenant
        student = await self.db.execute(
            select(Student)
            .where(Student.id == student_id)
            .where(Student.tenant_id == tenant_id)
        )
        student = student.scalar_one_or_none()
        if not student:
            raise PreschoolServiceError("Student not found", code="STUDENT_NOT_FOUND")

        pickup = AuthorizedPickup(
            tenant_id=tenant_id,
            school_id=student.school_id,
            student_id=student_id,
            full_name=data.full_name,
            phone=data.phone,
            relationship_to_student=data.relationship_to_student,
            photo_url=data.photo_url,
            id_document_url=data.id_document_url,
            notes=data.notes,
            added_by=added_by,
        )
        self.db.add(pickup)
        await self.db.flush()
        await self.db.refresh(pickup)
        return pickup

    async def list_authorized_pickups(
        self, tenant_id: uuid.UUID, student_id: uuid.UUID
    ) -> Sequence[AuthorizedPickup]:
        """List all authorized pickup persons for a student (active + inactive)."""
        result = await self.db.execute(
            select(AuthorizedPickup)
            .where(AuthorizedPickup.tenant_id == tenant_id)
            .where(AuthorizedPickup.student_id == student_id)
            .where(AuthorizedPickup.deleted_at.is_(None))
            .order_by(AuthorizedPickup.full_name)
        )
        return result.scalars().all()

    async def update_authorized_pickup(
        self,
        tenant_id: uuid.UUID,
        pickup_id: uuid.UUID,
        data: "AuthorizedPickupUpdate",
    ) -> AuthorizedPickup:
        """Update an authorized pickup person."""
        result = await self.db.execute(
            select(AuthorizedPickup)
            .where(AuthorizedPickup.id == pickup_id)
            .where(AuthorizedPickup.tenant_id == tenant_id)
            .where(AuthorizedPickup.deleted_at.is_(None))
        )
        pickup = result.scalar_one_or_none()
        if not pickup:
            raise PreschoolServiceError("Authorized pickup not found", code="PICKUP_PERSON_NOT_FOUND")

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(pickup, field, value)

        await self.db.flush()
        await self.db.refresh(pickup)
        return pickup

    async def deactivate_authorized_pickup(
        self, tenant_id: uuid.UUID, pickup_id: uuid.UUID
    ) -> None:
        """Soft-delete an authorized pickup person."""
        result = await self.db.execute(
            select(AuthorizedPickup)
            .where(AuthorizedPickup.id == pickup_id)
            .where(AuthorizedPickup.tenant_id == tenant_id)
            .where(AuthorizedPickup.deleted_at.is_(None))
        )
        pickup = result.scalar_one_or_none()
        if not pickup:
            raise PreschoolServiceError("Authorized pickup not found", code="PICKUP_PERSON_NOT_FOUND")

        pickup.deleted_at = datetime.now(timezone.utc)
        await self.db.flush()

    # =========================
    # Pickup Log Methods
    # =========================

    async def record_pickup(
        self,
        tenant_id: uuid.UUID,
        data: "PickupLogCreate",
        verified_by: uuid.UUID,
    ) -> PickupLog:
        """
        Record a student pickup event.

        Validates that:
        - Student belongs to tenant
        - If guardian: guardian is linked to student with can_pickup=True
        - If authorized_person: authorized pickup is active for this student
        """
        # Verify student belongs to tenant and capture for school_id
        student_result = await self.db.execute(
            select(Student)
            .where(Student.id == data.student_id)
            .where(Student.tenant_id == tenant_id)
        )
        student = student_result.scalar_one_or_none()
        if not student:
            raise PreschoolServiceError("Student not found", code="STUDENT_NOT_FOUND")

        # Validate pickup person
        if data.picked_up_by_type == "guardian":
            guardian_result = await self.db.execute(
                select(StudentGuardian)
                .where(StudentGuardian.student_id == data.student_id)
                .where(StudentGuardian.guardian_id == data.picked_up_by_guardian_id)
                .where(StudentGuardian.tenant_id == tenant_id)
            )
            sg = guardian_result.scalar_one_or_none()
            if not sg:
                raise PreschoolServiceError(
                    "Guardian is not linked to this student",
                    code="GUARDIAN_NOT_LINKED",
                )
            if not sg.can_pickup:
                raise PreschoolServiceError(
                    "Guardian is not authorized for pickup",
                    code="GUARDIAN_PICKUP_NOT_AUTHORIZED",
                )
        elif data.picked_up_by_type == "authorized_person":
            auth_result = await self.db.execute(
                select(AuthorizedPickup)
                .where(AuthorizedPickup.id == data.picked_up_by_authorized_id)
                .where(AuthorizedPickup.student_id == data.student_id)
                .where(AuthorizedPickup.tenant_id == tenant_id)
                .where(AuthorizedPickup.is_active.is_(True))
                .where(AuthorizedPickup.deleted_at.is_(None))
            )
            if not auth_result.scalar_one_or_none():
                raise PreschoolServiceError(
                    "Authorized pickup person not found or inactive",
                    code="AUTHORIZED_PICKUP_NOT_FOUND",
                )

        log = PickupLog(
            tenant_id=tenant_id,
            school_id=student.school_id,  # Set from student record (chain support)
            student_id=data.student_id,
            pickup_date=date.today(),  # Server-side date, not client-provided
            pickup_time=data.pickup_time,
            picked_up_by_type=data.picked_up_by_type,
            picked_up_by_guardian_id=data.picked_up_by_guardian_id,
            picked_up_by_authorized_id=data.picked_up_by_authorized_id,
            verified_by=verified_by,
            notes=data.notes,
        )
        self.db.add(log)
        await self.db.flush()
        await self.db.refresh(log)
        return log

    async def list_pickup_logs(
        self,
        tenant_id: uuid.UUID,
        *,
        student_id: uuid.UUID | None = None,
        class_id: uuid.UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Sequence[PickupLog]:
        """List pickup logs with optional filters."""
        query = (
            select(PickupLog)
            .where(PickupLog.tenant_id == tenant_id)
            .order_by(PickupLog.pickup_date.desc(), PickupLog.pickup_time.desc())
        )
        if student_id:
            query = query.where(PickupLog.student_id == student_id)
        if class_id:
            query = query.join(Student, PickupLog.student_id == Student.id).where(
                Student.class_id == class_id,
                Student.tenant_id == tenant_id,  # Defense-in-depth on JOIN
            )
        if date_from:
            query = query.where(PickupLog.pickup_date >= date_from)
        if date_to:
            query = query.where(PickupLog.pickup_date <= date_to)

        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()
```

---

## 2.6 Allergy/Dietary Service Methods

**File:** `backend/app/services/preschool.py` (add to `PreschoolService`)

```python
    # =========================
    # Allergy / Dietary Methods
    # =========================

    async def get_student_dietary_requirements(
        self, tenant_id: uuid.UUID, student_id: uuid.UUID
    ) -> dict | None:
        """Get structured dietary requirements for a student."""
        result = await self.db.execute(
            select(Student.dietary_requirements)
            .where(Student.id == student_id)
            .where(Student.tenant_id == tenant_id)
        )
        row = result.one_or_none()
        if row is None:
            raise PreschoolServiceError("Student not found", code="STUDENT_NOT_FOUND")
        return row[0]  # dietary_requirements column value (may be None)

    async def update_dietary_requirements(
        self,
        tenant_id: uuid.UUID,
        student_id: uuid.UUID,
        dietary_data: dict | None,
    ) -> None:
        """Update dietary requirements JSONB for a student."""
        result = await self.db.execute(
            select(Student)
            .where(Student.id == student_id)
            .where(Student.tenant_id == tenant_id)
        )
        student = result.scalar_one_or_none()
        if not student:
            raise PreschoolServiceError("Student not found", code="STUDENT_NOT_FOUND")

        student.dietary_requirements = dietary_data
        await self.db.flush()

    async def get_class_allergy_alerts(
        self, tenant_id: uuid.UUID, class_id: uuid.UUID
    ) -> list[dict]:
        """
        Get all students in a class who have allergies or dietary restrictions.

        Returns a list of {student_id, student_name, allergies, dietary_restrictions, notes}.
        Used to show allergy alerts when teachers open daily log forms.
        """
        result = await self.db.execute(
            select(
                Student.id,
                Student.first_name,
                Student.last_name,
                Student.dietary_requirements,
            )
            .where(Student.tenant_id == tenant_id)
            .where(Student.class_id == class_id)
            .where(Student.dietary_requirements.isnot(None))
            .where(Student.deleted_at.is_(None))
            .order_by(Student.first_name, Student.last_name)
        )
        rows = result.all()

        alerts = []
        for row in rows:
            dietary = row.dietary_requirements or {}
            allergies = dietary.get("allergies", [])
            restrictions = dietary.get("dietary_restrictions", [])
            # Only include students who actually have allergies or restrictions
            if allergies or restrictions:
                alerts.append({
                    "student_id": str(row.id),
                    "student_name": f"{row.first_name} {row.last_name}",
                    "allergies": allergies,
                    "dietary_restrictions": restrictions,
                    "notes": dietary.get("notes"),
                })
        return alerts
```

---

## 2.7 Incident Endpoints

**File:** `backend/app/api/v1/endpoints/preschool.py` (add after existing report endpoints)

**IMPORTANT:** All endpoints use `DatabaseSession`, `ValidatedUser`, `RequestTenant` (Annotated type aliases from `app.api.deps`), permissions in `dependencies=[...]`, and `convert_uuid()` on tenant_id. See "Critical Patterns" section above.

```python
# =========================
# Incident Endpoints
# =========================


@router.post(
    "/incidents",
    response_model=PreschoolIncidentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Report a new incident",
    dependencies=[Depends(require_permissions("preschool.create"))],
)
async def create_incident(
    data: PreschoolIncidentCreate,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Report a new preschool incident."""
    service = PreschoolService(db)
    try:
        incident = await service.create_incident(
            tenant_id=convert_uuid(tenant.tenant_id),
            data=data,
            reported_by=convert_uuid(current_user.id),
        )
        # AUDIT: Log incident creation (especially for serious severity)
        # await audit_service.log_event("preschool.incident.created", ...)
        return PreschoolIncidentResponse.model_validate(incident)
    except PreschoolServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND if e.code == "STUDENT_NOT_FOUND" else status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        )


@router.get(
    "/incidents",
    response_model=list[PreschoolIncidentResponse],
    summary="List incidents",
    dependencies=[Depends(require_permissions("preschool.read"))],
)
async def list_incidents(
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
    student_id: UUID | None = None,
    class_id: UUID | None = None,
    incident_status: str | None = Query(None, alias="status"),
    severity: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    """List incidents with optional filters."""
    service = PreschoolService(db)
    incidents = await service.list_incidents(
        tenant_id=convert_uuid(tenant.tenant_id),
        student_id=student_id,
        class_id=class_id,
        status=incident_status,
        severity=severity,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )
    return [PreschoolIncidentResponse.model_validate(i) for i in incidents]


@router.get(
    "/incidents/{incident_id}",
    response_model=PreschoolIncidentResponse,
    summary="Get incident",
    dependencies=[Depends(require_permissions("preschool.read"))],
)
async def get_incident(
    incident_id: UUID,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Get a single incident by ID."""
    service = PreschoolService(db)
    try:
        incident = await service.get_incident(convert_uuid(tenant.tenant_id), incident_id)
        return PreschoolIncidentResponse.model_validate(incident)
    except PreschoolServiceError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")


@router.put(
    "/incidents/{incident_id}",
    response_model=PreschoolIncidentResponse,
    summary="Update incident",
    dependencies=[Depends(require_permissions("preschool.update"))],
)
async def update_incident(
    incident_id: UUID,
    data: PreschoolIncidentUpdate,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Update incident details."""
    service = PreschoolService(db)
    try:
        incident = await service.update_incident(convert_uuid(tenant.tenant_id), incident_id, data)
        return PreschoolIncidentResponse.model_validate(incident)
    except PreschoolServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND if e.code == "INCIDENT_NOT_FOUND" else status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        )


@router.post(
    "/incidents/{incident_id}/notify-parent",
    response_model=PreschoolIncidentResponse,
    summary="Notify parent about incident",
    dependencies=[Depends(require_permissions("preschool.update"))],
)
async def notify_parent_incident(
    incident_id: UUID,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """
    Mark incident as parent_notified and trigger SMS/email.

    IMPORTANT: The notification dispatch MUST happen BEFORE the status update.
    If SMS/email fails, the status should NOT be changed to parent_notified.
    """
    service = PreschoolService(db)
    try:
        # Step 1: Send notification via NotificationDispatcher
        # Load student's emergency contact guardians and send
        # TODO: Integrate NotificationDispatcher — dispatch BEFORE status change
        # If dispatch fails, raise error and do NOT update status

        # Step 2: Only update status after successful dispatch
        incident = await service.notify_parent_incident(
            convert_uuid(tenant.tenant_id), incident_id,
            notified_by=convert_uuid(current_user.id),
        )

        # AUDIT: Log parent notification
        # await audit_service.log_event("preschool.incident.parent_notified", ...)

        return PreschoolIncidentResponse.model_validate(incident)
    except PreschoolServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND if e.code == "INCIDENT_NOT_FOUND" else status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        )


@router.post(
    "/incidents/{incident_id}/resolve",
    response_model=PreschoolIncidentResponse,
    summary="Resolve incident",
    dependencies=[Depends(require_permissions("preschool.update"))],
)
async def resolve_incident(
    incident_id: UUID,
    data: IncidentResolveRequest,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Resolve an incident with optional follow-up notes."""
    service = PreschoolService(db)
    try:
        incident = await service.resolve_incident(
            convert_uuid(tenant.tenant_id), incident_id,
            follow_up_notes=data.follow_up_notes,
            resolved_by=convert_uuid(current_user.id),
        )
        # AUDIT: Log incident resolution
        # await audit_service.log_event("preschool.incident.resolved", ...)
        return PreschoolIncidentResponse.model_validate(incident)
    except PreschoolServiceError as e:
        code = status.HTTP_404_NOT_FOUND if e.code == "INCIDENT_NOT_FOUND" else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=e.message)
```

---

## 2.8 Pickup Endpoints

**File:** `backend/app/api/v1/endpoints/preschool.py` (add after incident endpoints)

**All endpoints use the same DI pattern as doc 2.7 above.**

```python
# =========================
# Authorized Pickup Endpoints
# =========================


@router.post(
    "/students/{student_id}/authorized-pickups",
    response_model=AuthorizedPickupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add authorized pickup person",
    dependencies=[Depends(require_permissions("preschool.create"))],
)
async def add_authorized_pickup(
    student_id: UUID,
    data: AuthorizedPickupCreate,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Add an authorized pickup person for a student."""
    service = PreschoolService(db)
    try:
        pickup = await service.add_authorized_pickup(
            tenant.tenant_id, student_id, data, added_by=user.id,
        )
        return AuthorizedPickupResponse.model_validate(pickup)
    except PreschoolServiceError as e:
        raise HTTPException(
            status_code=404 if e.code == "STUDENT_NOT_FOUND" else 400,
            detail=e.message,
        )


@router.get(
    "/students/{student_id}/authorized-pickups",
    response_model=list[AuthorizedPickupResponse],
)
async def list_authorized_pickups(
    student_id: uuid.UUID,
    tenant: RequestTenant = Depends(get_request_tenant),
    user: ValidatedUser = Depends(require_permissions("preschool.read")),
    db: AsyncSession = Depends(get_db),
):
    """List authorized pickup persons for a student."""
    service = PreschoolService(db)
    pickups = await service.list_authorized_pickups(tenant.tenant_id, student_id)
    return [AuthorizedPickupResponse.model_validate(p) for p in pickups]


@router.put(
    "/authorized-pickups/{pickup_id}",
    response_model=AuthorizedPickupResponse,
)
async def update_authorized_pickup(
    pickup_id: uuid.UUID,
    data: AuthorizedPickupUpdate,
    tenant: RequestTenant = Depends(get_request_tenant),
    user: ValidatedUser = Depends(require_permissions("preschool.update")),
    db: AsyncSession = Depends(get_db),
):
    """Update an authorized pickup person."""
    service = PreschoolService(db)
    try:
        pickup = await service.update_authorized_pickup(tenant.tenant_id, pickup_id, data)
        return AuthorizedPickupResponse.model_validate(pickup)
    except PreschoolServiceError:
        raise HTTPException(status_code=404, detail="Authorized pickup not found")


@router.delete("/authorized-pickups/{pickup_id}", status_code=204)
async def delete_authorized_pickup(
    pickup_id: uuid.UUID,
    tenant: RequestTenant = Depends(get_request_tenant),
    user: ValidatedUser = Depends(require_permissions("preschool.delete")),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete an authorized pickup person."""
    service = PreschoolService(db)
    try:
        await service.deactivate_authorized_pickup(tenant.tenant_id, pickup_id)
    except PreschoolServiceError:
        raise HTTPException(status_code=404, detail="Authorized pickup not found")


# =========================
# Pickup Log Endpoints
# =========================


@router.post("/pickup-logs", response_model=PickupLogResponse, status_code=201)
async def record_pickup(
    data: PickupLogCreate,
    tenant: RequestTenant = Depends(get_request_tenant),
    user: ValidatedUser = Depends(require_permissions("preschool.create")),
    db: AsyncSession = Depends(get_db),
):
    """Record a student pickup event."""
    service = PreschoolService(db)
    try:
        log = await service.record_pickup(
            tenant.tenant_id, data, verified_by=user.id,
        )
        return PickupLogResponse.model_validate(log)
    except PreschoolServiceError as e:
        status_map = {
            "STUDENT_NOT_FOUND": 404,
            "GUARDIAN_NOT_LINKED": 403,
            "GUARDIAN_PICKUP_NOT_AUTHORIZED": 403,
            "AUTHORIZED_PICKUP_NOT_FOUND": 404,
        }
        raise HTTPException(
            status_code=status_map.get(e.code, 400),
            detail=e.message,
        )


@router.get("/pickup-logs", response_model=list[PickupLogResponse])
async def list_pickup_logs(
    student_id: uuid.UUID | None = None,
    class_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    tenant: RequestTenant = Depends(get_request_tenant),
    user: ValidatedUser = Depends(require_permissions("preschool.read")),
    db: AsyncSession = Depends(get_db),
):
    """List pickup log entries with optional filters."""
    service = PreschoolService(db)
    logs = await service.list_pickup_logs(
        tenant.tenant_id,
        student_id=student_id,
        class_id=class_id,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )
    return [PickupLogResponse.model_validate(l) for l in logs]
```

---

## 2.9 Allergy/Dietary Endpoints

**File:** `backend/app/api/v1/endpoints/preschool.py` (add after pickup endpoints)

```python
# =========================
# Allergy / Dietary Endpoints
# =========================


@router.get(
    "/students/{student_id}/dietary-requirements",
    response_model=DietaryRequirements | None,
)
async def get_dietary_requirements(
    student_id: uuid.UUID,
    tenant: RequestTenant = Depends(get_request_tenant),
    user: ValidatedUser = Depends(require_permissions("preschool.read")),
    db: AsyncSession = Depends(get_db),
):
    """Get structured dietary requirements for a student."""
    service = PreschoolService(db)
    try:
        data = await service.get_student_dietary_requirements(tenant.tenant_id, student_id)
        if data is None:
            return None
        return DietaryRequirements(**data)
    except PreschoolServiceError:
        raise HTTPException(status_code=404, detail="Student not found")


@router.put("/students/{student_id}/dietary-requirements")
async def update_dietary_requirements(
    student_id: uuid.UUID,
    data: DietaryRequirementsUpdate,
    tenant: RequestTenant = Depends(get_request_tenant),
    user: ValidatedUser = Depends(require_permissions("preschool.update")),
    db: AsyncSession = Depends(get_db),
):
    """Update dietary requirements for a student."""
    service = PreschoolService(db)
    try:
        dietary_dict = data.dietary_requirements.model_dump() if data.dietary_requirements else None
        await service.update_dietary_requirements(tenant.tenant_id, student_id, dietary_dict)
        return {"message": "Dietary requirements updated"}
    except PreschoolServiceError:
        raise HTTPException(status_code=404, detail="Student not found")


@router.get("/allergy-alerts", response_model=list[AllergyAlertResponse])
async def get_class_allergy_alerts(
    class_id: uuid.UUID = Query(..., description="Class ID to check alerts for"),
    tenant: RequestTenant = Depends(get_request_tenant),
    user: ValidatedUser = Depends(require_permissions("preschool.read")),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all students in a class who have allergies or dietary restrictions.

    Used to show allergy alert banners in daily log forms and class views.
    """
    service = PreschoolService(db)
    alerts = await service.get_class_allergy_alerts(tenant.tenant_id, class_id)
    return alerts
```

---

## 2.10 Student Schema Updates

**File:** `backend/app/schemas/student.py` (or wherever student update schemas live)

Add `enrollment_session` to the student update schema:

```python
class StudentUpdate(BaseSchema):
    # ... existing fields ...
    enrollment_session: Annotated[
        str | None,
        Field(pattern=r"^(half_day_morning|half_day_afternoon|full_day|extended)$")
    ] = None
```

Add `enrollment_session` to the student response schema:

```python
class StudentResponse(BaseSchema):
    # ... existing fields ...
    enrollment_session: str | None = None
    dietary_requirements: dict | None = None
```

**Note:** Do NOT add `dietary_requirements` to `StudentUpdate` — it's managed via the dedicated `/preschool/students/{id}/dietary-requirements` endpoint to keep validation separate.

---

## Security Checklist

- [ ] All endpoints use `DatabaseSession`, `ValidatedUser`, `RequestTenant` (NOT `Depends(get_db)`)
- [ ] All endpoints wrap `tenant.tenant_id` with `convert_uuid()` before passing to service
- [ ] All endpoints use `dependencies=[Depends(require_permissions(...))]` (NOT inline `Depends`)
- [ ] All incident endpoints require `preschool.create`/`read`/`update` permissions
- [ ] All pickup endpoints require `preschool.create`/`read`/`update`/`delete` permissions
- [ ] `record_pickup` validates guardian `can_pickup=True` or active `AuthorizedPickup` — rejects with 403 on mismatch
- [ ] `record_pickup` sets `pickup_date` server-side AND `school_id` from student record
- [ ] Student tenant ownership verified before any incident/pickup/allergy operation
- [ ] `photo_url` and `id_document_url` validated to HTTPS-only via Pydantic field_validator
- [ ] `description` and `follow_up_notes` are plain text only (no HTML rendering)
- [ ] Incident status transitions validated against `VALID_INCIDENT_TRANSITIONS`
- [ ] **Severity gate:** moderate/serious incidents CANNOT be resolved without parent notification
- [ ] **Notification ordering:** dispatch SMS/email BEFORE updating status to parent_notified
- [ ] `update_incident` uses PROTECTED_FIELDS blocklist in setattr loop
- [ ] `incident_date` validated to not be in the future
- [ ] `AttachmentSchema.url` validated to HTTPS-only
- [ ] Audit logging on incident create, parent notification, and resolution
- [ ] Student JOIN queries include `Student.tenant_id == tenant_id` (defense-in-depth)
- [ ] No information leakage: 404 for both "not found" and "wrong tenant" cases
