"""
SIMS Plus - Staff Service

Business logic for staff management.
"""

from datetime import datetime, UTC, date
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select, and_, or_, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.staff import (
    Department,
    Staff,
    StaffType,
    StaffStatus,
    StaffClassAssignment,
)
from app.models.student import Gender
from app.models.academic import ClassSection, Subject


class StaffServiceError(Exception):
    """Base exception for staff service errors."""

    def __init__(self, message: str, code: str = "staff_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class StaffService:
    """Service for managing staff members."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================
    # Staff Methods
    # =========================

    async def create_staff(
        self,
        tenant_id: UUID,
        staff_id: str,
        first_name: str,
        last_name: str,
        email: str,
        phone: str,
        gender: str,
        job_title: str,
        employment_date: date,
        middle_name: Optional[str] = None,
        date_of_birth: Optional[date] = None,
        previous_staff_id: Optional[str] = None,
        phone_secondary: Optional[str] = None,
        address: Optional[str] = None,
        city: Optional[str] = None,
        region: Optional[str] = None,
        emergency_contact_name: Optional[str] = None,
        emergency_contact_phone: Optional[str] = None,
        emergency_contact_relationship: Optional[str] = None,
        ghana_card_number: Optional[str] = None,
        ssnit_number: Optional[str] = None,
        teacher_license_number: Optional[str] = None,
        staff_type: str = "teaching",
        status: str = "active",
        department: Optional[str] = None,
        termination_date: Optional[date] = None,
        qualifications: Optional[list] = None,
        bank_name: Optional[str] = None,
        bank_branch: Optional[str] = None,
        account_number: Optional[str] = None,
        photo_url: Optional[str] = None,
        notes: Optional[str] = None,
        school_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
    ) -> Staff:
        """Create a new staff member."""
        # Check for duplicate staff_id
        existing = await self.db.execute(
            select(Staff).where(
                and_(
                    Staff.tenant_id == tenant_id,
                    Staff.staff_id == staff_id,
                    Staff.deleted_at.is_(None),
                )
            )
        )
        if existing.scalar_one_or_none():
            raise StaffServiceError(
                f"Staff ID '{staff_id}' already exists",
                code="duplicate_staff_id",
            )

        # Check for duplicate email
        existing_email = await self.db.execute(
            select(Staff).where(
                and_(
                    Staff.tenant_id == tenant_id,
                    Staff.email == email,
                    Staff.deleted_at.is_(None),
                )
            )
        )
        if existing_email.scalar_one_or_none():
            raise StaffServiceError(
                f"A staff member with email '{email}' already exists",
                code="duplicate_staff_email",
            )

        staff = Staff(
            tenant_id=tenant_id,
            staff_id=staff_id,
            previous_staff_id=previous_staff_id,
            first_name=first_name,
            middle_name=middle_name,
            last_name=last_name,
            date_of_birth=date_of_birth,
            gender=Gender(gender),
            email=email,
            phone=phone,
            phone_secondary=phone_secondary,
            address=address,
            city=city,
            region=region,
            emergency_contact_name=emergency_contact_name,
            emergency_contact_phone=emergency_contact_phone,
            emergency_contact_relationship=emergency_contact_relationship,
            ghana_card_number=ghana_card_number,
            ssnit_number=ssnit_number,
            teacher_license_number=teacher_license_number,
            staff_type=StaffType(staff_type),
            status=StaffStatus(status),
            job_title=job_title,
            department=department,
            employment_date=employment_date,
            termination_date=termination_date,
            qualifications=qualifications or [],
            bank_name=bank_name,
            bank_branch=bank_branch,
            account_number=account_number,
            photo_url=photo_url,
            notes=notes,
            school_id=school_id,
            user_id=user_id,
        )
        self.db.add(staff)
        try:
            await self.db.flush()
        except IntegrityError as e:
            await self.db.rollback()
            error_msg = str(e.orig) if e.orig else str(e)
            if "uq_staff_staff_id_tenant" in error_msg or "staff_id" in error_msg.lower():
                raise StaffServiceError(
                    f"Staff ID '{staff_id}' already exists (concurrent creation detected)",
                    code="duplicate_staff_id",
                )
            if "uq_staff_email_tenant" in error_msg or "email" in error_msg.lower():
                raise StaffServiceError(
                    f"Email '{email}' already exists (concurrent creation detected)",
                    code="duplicate_staff_email",
                )
            raise StaffServiceError(
                f"Database error while creating staff: {error_msg}",
                code="database_error",
            )

        await self.db.commit()
        await self.db.refresh(staff)
        return staff

    async def get_staff(
        self, staff_id: UUID, include_assignments: bool = False
    ) -> Optional[Staff]:
        """Get staff by ID."""
        query = select(Staff).where(
            and_(
                Staff.id == staff_id,
                Staff.deleted_at.is_(None),
            )
        )
        if include_assignments:
            query = query.options(
                selectinload(Staff.class_assignments).selectinload(StaffClassAssignment.section)
            )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_staff_by_staff_id(
        self, tenant_id: UUID, staff_id: str
    ) -> Optional[Staff]:
        """Get staff by staff ID (the school-assigned ID)."""
        result = await self.db.execute(
            select(Staff).where(
                and_(
                    Staff.tenant_id == tenant_id,
                    Staff.staff_id == staff_id,
                    Staff.deleted_at.is_(None),
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_staff_by_user_id(
        self, tenant_id: UUID, user_id: UUID
    ) -> Optional[Staff]:
        """Get staff by linked user ID."""
        result = await self.db.execute(
            select(Staff).where(
                and_(
                    Staff.tenant_id == tenant_id,
                    Staff.user_id == user_id,
                    Staff.deleted_at.is_(None),
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_staff(
        self,
        tenant_id: UUID,
        search: Optional[str] = None,
        staff_type: Optional[str] = None,
        status: Optional[str] = None,
        gender: Optional[str] = None,
        department: Optional[str] = None,
        school_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[Sequence[Staff], int]:
        """List staff with filters and pagination."""
        conditions = [
            Staff.tenant_id == tenant_id,
            Staff.deleted_at.is_(None),
        ]

        if search:
            search_term = f"%{search}%"
            conditions.append(
                or_(
                    Staff.first_name.ilike(search_term),
                    Staff.last_name.ilike(search_term),
                    Staff.middle_name.ilike(search_term),
                    Staff.staff_id.ilike(search_term),
                    Staff.email.ilike(search_term),
                    Staff.job_title.ilike(search_term),
                )
            )

        if staff_type:
            conditions.append(Staff.staff_type == StaffType(staff_type))
        if status:
            conditions.append(Staff.status == StaffStatus(status))
        if gender:
            conditions.append(Staff.gender == Gender(gender))
        if department:
            conditions.append(Staff.department.ilike(f"%{department}%"))
        if school_id:
            conditions.append(Staff.school_id == school_id)

        # Get total count
        count_query = select(func.count(Staff.id)).where(and_(*conditions))
        total = (await self.db.execute(count_query)).scalar_one()

        # Get paginated results
        query = (
            select(Staff)
            .where(and_(*conditions))
            .options(selectinload(Staff.school))
            .order_by(Staff.last_name, Staff.first_name)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(query)
        staff_list = result.scalars().all()

        return staff_list, total

    async def update_staff(
        self, staff_id: UUID, **kwargs
    ) -> Optional[Staff]:
        """Update a staff member."""
        staff = await self.get_staff(staff_id)
        if not staff:
            return None

        # Handle enum conversions
        if "status" in kwargs and kwargs["status"]:
            kwargs["status"] = StaffStatus(kwargs["status"])
        if "gender" in kwargs and kwargs["gender"]:
            kwargs["gender"] = Gender(kwargs["gender"])
        if "staff_type" in kwargs and kwargs["staff_type"]:
            kwargs["staff_type"] = StaffType(kwargs["staff_type"])

        for key, value in kwargs.items():
            if value is not None and hasattr(staff, key):
                setattr(staff, key, value)

        staff.updated_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(staff)
        return staff

    async def delete_staff(self, staff_id: UUID) -> bool:
        """Soft delete a staff member."""
        staff = await self.get_staff(staff_id)
        if not staff:
            return False

        staff.deleted_at = datetime.now(UTC)
        await self.db.commit()
        return True

    async def generate_staff_id(
        self, tenant_id: UUID, prefix: str = "STF", max_retries: int = 10
    ) -> str:
        """
        Generate a unique staff ID for the tenant.

        Format: {PREFIX}-{YEAR}-{SEQUENCE}
        Example: STF-2026-001, STF-2026-002
        """
        import re

        current_year = datetime.now().year
        pattern = f"{prefix}-{current_year}-%"

        # Find the highest existing sequence number for this prefix and year
        result = await self.db.execute(
            select(Staff.staff_id).where(
                and_(
                    Staff.tenant_id == tenant_id,
                    Staff.staff_id.like(pattern),
                )
            )
        )
        existing_ids = result.scalars().all()

        # Extract sequence numbers from existing IDs
        max_seq = 0
        seq_pattern = re.compile(rf"^{re.escape(prefix)}-{current_year}-(\d+)$")
        for existing_id in existing_ids:
            match = seq_pattern.match(existing_id)
            if match:
                seq = int(match.group(1))
                if seq > max_seq:
                    max_seq = seq

        # Start from the next sequence number
        next_seq = max_seq + 1

        # Retry loop for race condition protection
        for attempt in range(max_retries):
            # Format: PREFIX-YEAR-SEQUENCE (3 digits minimum)
            if next_seq < 1000:
                new_staff_id = f"{prefix}-{current_year}-{next_seq:03d}"
            else:
                new_staff_id = f"{prefix}-{current_year}-{next_seq}"

            # Check if this ID already exists
            existing = await self.db.execute(
                select(Staff.id).where(
                    and_(
                        Staff.tenant_id == tenant_id,
                        Staff.staff_id == new_staff_id,
                    )
                )
            )
            if not existing.scalar_one_or_none():
                return new_staff_id

            next_seq += 1

        raise StaffServiceError(
            f"Unable to generate unique staff ID after {max_retries} attempts.",
            code="id_generation_failed",
        )

    async def get_staff_stats(self, tenant_id: UUID) -> dict:
        """Get staff statistics for a tenant."""
        base_conditions = [
            Staff.tenant_id == tenant_id,
            Staff.deleted_at.is_(None),
        ]

        # Total count
        total = (
            await self.db.execute(
                select(func.count(Staff.id)).where(and_(*base_conditions))
            )
        ).scalar_one()

        # By status
        status_counts = {}
        for status in StaffStatus:
            count = (
                await self.db.execute(
                    select(func.count(Staff.id)).where(
                        and_(*base_conditions, Staff.status == status)
                    )
                )
            ).scalar_one()
            status_counts[status.value] = count

        # By type
        type_counts = {}
        for staff_type in StaffType:
            count = (
                await self.db.execute(
                    select(func.count(Staff.id)).where(
                        and_(*base_conditions, Staff.staff_type == staff_type)
                    )
                )
            ).scalar_one()
            type_counts[staff_type.value] = count

        # By gender
        male_count = (
            await self.db.execute(
                select(func.count(Staff.id)).where(
                    and_(*base_conditions, Staff.gender == Gender.MALE)
                )
            )
        ).scalar_one()

        female_count = (
            await self.db.execute(
                select(func.count(Staff.id)).where(
                    and_(*base_conditions, Staff.gender == Gender.FEMALE)
                )
            )
        ).scalar_one()

        return {
            "total": total,
            "active": status_counts.get("active", 0),
            "on_leave": status_counts.get("on_leave", 0),
            "suspended": status_counts.get("suspended", 0),
            "terminated": status_counts.get("terminated", 0),
            "retired": status_counts.get("retired", 0),
            "teaching": type_counts.get("teaching", 0),
            "non_teaching": type_counts.get("non_teaching", 0),
            "administrative": type_counts.get("administrative", 0),
            "male": male_count,
            "female": female_count,
        }

    # =========================
    # Import Methods
    # =========================

    def parse_csv_file(self, content: bytes) -> tuple[list[str], list[dict]]:
        """Parse CSV file content into headers and rows."""
        import csv
        import io

        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("latin-1")

        reader = csv.DictReader(io.StringIO(text))
        headers = reader.fieldnames or []
        rows = list(reader)
        return headers, rows

    def _parse_date(self, value) -> Optional[date]:
        """Parse various date formats."""
        if not value or str(value).strip() == "":
            return None

        value_str = str(value).strip()

        # Try common formats
        formats = [
            "%Y-%m-%d",      # 2026-01-15
            "%d/%m/%Y",      # 15/01/2026
            "%m/%d/%Y",      # 01/15/2026
            "%d-%m-%Y",      # 15-01-2026
            "%Y/%m/%d",      # 2026/01/15
        ]

        for fmt in formats:
            try:
                return datetime.strptime(value_str, fmt).date()
            except ValueError:
                continue

        return None

    def _parse_gender(self, value) -> str:
        """Parse gender value to standard format."""
        if not value:
            return "male"  # Default

        value_str = str(value).lower().strip()

        male_values = ["m", "male", "boy", "man"]
        female_values = ["f", "female", "girl", "woman"]

        if value_str in male_values:
            return "male"
        elif value_str in female_values:
            return "female"
        else:
            return "male"  # Default

    def _parse_staff_type(self, value) -> str:
        """Parse staff type value."""
        if not value:
            return "teaching"

        value_str = str(value).lower().strip().replace(" ", "_")

        if value_str in ["teaching", "teacher"]:
            return "teaching"
        elif value_str in ["non_teaching", "non-teaching", "nonteaching", "support"]:
            return "non_teaching"
        elif value_str in ["administrative", "admin", "administration"]:
            return "administrative"

        return "teaching"

    def _parse_status(self, value) -> str:
        """Parse staff status value."""
        if not value:
            return "active"

        value_str = str(value).lower().strip().replace(" ", "_")

        valid_statuses = ["active", "on_leave", "suspended", "terminated", "retired"]
        if value_str in valid_statuses:
            return value_str

        return "active"

    def _auto_map_columns(self, headers: list[str]) -> dict[str, str]:
        """Auto-map CSV headers to staff fields."""
        mapping = {}

        # Define possible column names for each field
        field_mappings = {
            "previous_staff_id": ["previous_staff_id", "old_staff_id", "external_id", "legacy_id", "old_id"],
            "first_name": ["first_name", "firstname", "first", "given_name", "fname"],
            "middle_name": ["middle_name", "middlename", "middle", "mname"],
            "last_name": ["last_name", "lastname", "surname", "family_name", "lname"],
            "email": ["email", "email_address", "e-mail"],
            "phone": ["phone", "mobile", "telephone", "phone_number", "tel"],
            "phone_secondary": ["phone_secondary", "secondary_phone", "alt_phone", "phone2"],
            "gender": ["gender", "sex"],
            "date_of_birth": ["date_of_birth", "dob", "birth_date", "birthdate"],
            "job_title": ["job_title", "jobtitle", "title", "position", "role"],
            "employment_date": ["employment_date", "hire_date", "start_date", "joined_date"],
            "staff_type": ["staff_type", "type", "employee_type", "category"],
            "status": ["status", "employment_status"],
            "department": ["department", "dept"],
            "address": ["address", "street_address", "street"],
            "city": ["city", "town"],
            "region": ["region", "state", "province"],
            "emergency_contact_name": ["emergency_contact_name", "emergency_name", "emergency_contact"],
            "emergency_contact_phone": ["emergency_contact_phone", "emergency_phone"],
            "emergency_contact_relationship": ["emergency_contact_relationship", "emergency_relationship"],
            "ghana_card_number": ["ghana_card_number", "ghana_card", "national_id"],
            "ssnit_number": ["ssnit_number", "ssnit", "social_security"],
            "teacher_license_number": ["teacher_license_number", "license_number", "teaching_license", "ges_license"],
            "bank_name": ["bank_name", "bank"],
            "bank_branch": ["bank_branch", "branch"],
            "account_number": ["account_number", "account_no", "bank_account"],
            "notes": ["notes", "comments", "remarks"],
        }

        # Normalize headers for matching
        normalized_headers = {h.lower().strip().replace(" ", "_"): h for h in headers}

        for field, possible_names in field_mappings.items():
            for name in possible_names:
                if name in normalized_headers:
                    mapping[field] = normalized_headers[name]
                    break

        return mapping

    def _parse_row(
        self,
        row: dict,
        column_mapping: dict[str, str],
        row_number: int,
    ) -> dict:
        """Parse a single row using the column mapping."""
        data = {}
        errors = []

        # Required fields for staff
        required_fields = ["first_name", "last_name", "email", "phone", "gender", "job_title", "employment_date"]

        for field, column in column_mapping.items():
            if column not in row:
                continue

            value = row[column]

            try:
                if field == "date_of_birth":
                    parsed_value = self._parse_date(value)
                    if parsed_value:
                        data[field] = parsed_value
                elif field == "employment_date":
                    parsed_value = self._parse_date(value)
                    if parsed_value:
                        data[field] = parsed_value
                elif field == "gender":
                    data[field] = self._parse_gender(value)
                elif field == "staff_type":
                    data[field] = self._parse_staff_type(value)
                elif field == "status":
                    data[field] = self._parse_status(value)
                elif value is not None and str(value).strip():
                    data[field] = str(value).strip()
            except Exception as e:
                errors.append({
                    "row": row_number,
                    "field": field,
                    "value": str(value),
                    "error": str(e),
                })

        # Check required fields
        for field in required_fields:
            if field not in data:
                mapped_column = column_mapping.get(field, field)
                errors.append({
                    "row": row_number,
                    "field": field,
                    "message": f"Missing required field: {field} (column: {mapped_column})",
                })

        return {"data": data, "errors": errors}

    async def import_staff_from_file(
        self,
        tenant_id: UUID,
        file_content: bytes,
        file_type: str,
        column_mapping: Optional[dict[str, str]] = None,
        preview_only: bool = False,
    ) -> dict:
        """
        Import staff from a CSV file.

        Args:
            tenant_id: Tenant UUID
            file_content: Raw file bytes
            file_type: 'csv'
            column_mapping: Optional manual column mapping
            preview_only: If True, only return preview without creating

        Returns:
            Dict with import results
        """
        # Parse file
        if file_type == "csv":
            headers, rows = self.parse_csv_file(file_content)
        else:
            raise StaffServiceError(f"Unsupported file type: {file_type}")

        if not rows:
            return {
                "total_rows": 0,
                "created": 0,
                "failed": 0,
                "errors": [{"row": 0, "error": "File is empty or has no data rows"}],
                "preview": [],
            }

        # Auto-map columns if not provided
        if not column_mapping:
            column_mapping = self._auto_map_columns(headers)

        # Preview mode - return first 100 rows with parsed values
        if preview_only:
            preview = []
            valid_rows = 0
            invalid_rows = 0
            all_errors = []

            for i, row in enumerate(rows[:100]):
                parsed = self._parse_row(row, column_mapping, i + 2)
                row_errors = parsed.get("errors", [])

                if row_errors:
                    invalid_rows += 1
                    all_errors.extend(row_errors)
                else:
                    valid_rows += 1

                preview.append({
                    "row": i + 2,
                    "raw": row,
                    "parsed": parsed.get("data", {}),
                    "valid": len(row_errors) == 0,
                    "errors": [e.get("message", str(e)) for e in row_errors],
                })

            return {
                "total_rows": len(rows),
                "valid_rows": valid_rows + (len(rows) - len(rows[:100])),  # Assume remaining are valid
                "invalid_rows": invalid_rows,
                "preview": preview,
                "errors": [{"row": e.get("row"), "error": e.get("message", str(e))} for e in all_errors],
                "headers": headers,
                "auto_mapping": column_mapping,
            }

        # Import mode - create staff
        created = 0
        failed = 0
        errors = []
        max_id_retries = 5

        # Get the school's staff_id_prefix for consistent ID generation
        from app.models.school import School
        school_result = await self.db.execute(
            select(School.staff_id_prefix).where(School.tenant_id == tenant_id).limit(1)
        )
        school_prefix = school_result.scalar_one_or_none() or "STF"

        for i, row in enumerate(rows):
            row_number = i + 2  # Account for header row
            parsed = self._parse_row(row, column_mapping, row_number)

            if parsed.get("errors"):
                failed += 1
                for err in parsed["errors"]:
                    errors.append({
                        "row": row_number,
                        "error": err.get("message", str(err)),
                    })
                continue

            staff_data = parsed["data"]

            # Create the staff with retry logic for auto-generated IDs
            staff_created = False
            for attempt in range(max_id_retries):
                try:
                    # Always auto-generate staff ID using school's prefix
                    staff_data["staff_id"] = await self.generate_staff_id(
                        tenant_id, prefix=school_prefix
                    )

                    await self.create_staff(
                        tenant_id=tenant_id,
                        **staff_data,
                    )
                    created += 1
                    staff_created = True
                    break
                except StaffServiceError as e:
                    # Retry on duplicate ID (race condition on auto-generation)
                    if e.code == "duplicate_staff_id" and attempt < max_id_retries - 1:
                        import asyncio
                        await asyncio.sleep(0.01 * (attempt + 1))
                        continue
                    failed += 1
                    errors.append({
                        "row": row_number,
                        "previous_staff_id": staff_data.get("previous_staff_id"),
                        "error": e.message,
                    })
                    break
                except Exception as e:
                    failed += 1
                    errors.append({
                        "row": row_number,
                        "previous_staff_id": staff_data.get("previous_staff_id"),
                        "error": str(e),
                    })
                    break

            if not staff_created and not any(
                err.get("row") == row_number for err in errors
            ):
                failed += 1
                errors.append({
                    "row": row_number,
                    "error": f"Failed to generate unique staff ID after {max_id_retries} attempts",
                })

        return {
            "total": len(rows),
            "success": created,
            "failed": failed,
            "errors": errors,
        }

    # =========================
    # Staff Class Assignment Methods
    # =========================

    async def assign_staff_to_section(
        self,
        tenant_id: UUID,
        staff_id: UUID,
        section_id: UUID,
        is_class_teacher: bool = False,
        subject_id: Optional[UUID] = None,
    ) -> StaffClassAssignment:
        """Assign a staff member to a class section."""
        # Verify staff exists
        staff = await self.get_staff(staff_id)
        if not staff:
            raise StaffServiceError("Staff member not found", code="staff_not_found")

        # Verify section exists
        section_result = await self.db.execute(
            select(ClassSection).where(
                and_(
                    ClassSection.id == section_id,
                    ClassSection.tenant_id == tenant_id,
                    ClassSection.deleted_at.is_(None),
                )
            )
        )
        if not section_result.scalar_one_or_none():
            raise StaffServiceError("Class section not found", code="section_not_found")

        # Check for existing assignment
        existing = await self.db.execute(
            select(StaffClassAssignment).where(
                and_(
                    StaffClassAssignment.tenant_id == tenant_id,
                    StaffClassAssignment.staff_id == staff_id,
                    StaffClassAssignment.section_id == section_id,
                )
            )
        )
        if existing.scalar_one_or_none():
            raise StaffServiceError(
                "Staff is already assigned to this section",
                code="duplicate_assignment",
            )

        # If setting as class teacher, unset other class teachers for this section
        if is_class_teacher:
            await self._unset_class_teacher(tenant_id, section_id)

        assignment = StaffClassAssignment(
            tenant_id=tenant_id,
            staff_id=staff_id,
            section_id=section_id,
            is_class_teacher=is_class_teacher,
            subject_id=subject_id,
        )
        self.db.add(assignment)
        await self.db.commit()
        await self.db.refresh(assignment)
        return assignment

    async def update_staff_assignment(
        self,
        assignment_id: UUID,
        tenant_id: UUID,
        **kwargs,
    ) -> Optional[StaffClassAssignment]:
        """Update a staff class assignment."""
        result = await self.db.execute(
            select(StaffClassAssignment).where(
                and_(
                    StaffClassAssignment.id == assignment_id,
                    StaffClassAssignment.tenant_id == tenant_id,
                )
            )
        )
        assignment = result.scalar_one_or_none()
        if not assignment:
            return None

        # If setting as class teacher, unset other class teachers for this section
        if kwargs.get("is_class_teacher"):
            await self._unset_class_teacher(tenant_id, assignment.section_id)

        for key, value in kwargs.items():
            if value is not None and hasattr(assignment, key):
                setattr(assignment, key, value)

        assignment.updated_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(assignment)
        return assignment

    async def remove_staff_from_section(
        self, tenant_id: UUID, staff_id: UUID, section_id: UUID
    ) -> bool:
        """Remove a staff assignment from a section."""
        result = await self.db.execute(
            select(StaffClassAssignment).where(
                and_(
                    StaffClassAssignment.tenant_id == tenant_id,
                    StaffClassAssignment.staff_id == staff_id,
                    StaffClassAssignment.section_id == section_id,
                )
            )
        )
        assignment = result.scalar_one_or_none()
        if not assignment:
            return False

        await self.db.delete(assignment)
        await self.db.commit()
        return True

    async def get_staff_assignments(
        self, tenant_id: UUID, staff_id: UUID
    ) -> Sequence[StaffClassAssignment]:
        """Get all class assignments for a staff member."""
        result = await self.db.execute(
            select(StaffClassAssignment)
            .where(
                and_(
                    StaffClassAssignment.tenant_id == tenant_id,
                    StaffClassAssignment.staff_id == staff_id,
                )
            )
            .options(
                selectinload(StaffClassAssignment.section),
            )
        )
        return result.scalars().all()

    async def get_section_staff(
        self, tenant_id: UUID, section_id: UUID
    ) -> Sequence[StaffClassAssignment]:
        """Get all staff assigned to a section."""
        result = await self.db.execute(
            select(StaffClassAssignment)
            .where(
                and_(
                    StaffClassAssignment.tenant_id == tenant_id,
                    StaffClassAssignment.section_id == section_id,
                )
            )
            .options(
                selectinload(StaffClassAssignment.staff),
                selectinload(StaffClassAssignment.section).selectinload(ClassSection.class_),
            )
        )
        return result.scalars().all()

    async def get_class_teacher(
        self, tenant_id: UUID, section_id: UUID
    ) -> Optional[Staff]:
        """Get the class teacher for a section."""
        result = await self.db.execute(
            select(StaffClassAssignment)
            .where(
                and_(
                    StaffClassAssignment.tenant_id == tenant_id,
                    StaffClassAssignment.section_id == section_id,
                    StaffClassAssignment.is_class_teacher == True,
                )
            )
            .options(selectinload(StaffClassAssignment.staff))
        )
        assignment = result.scalar_one_or_none()
        return assignment.staff if assignment else None

    async def _unset_class_teacher(
        self, tenant_id: UUID, section_id: UUID
    ) -> None:
        """Unset class teacher flag for all staff in a section."""
        result = await self.db.execute(
            select(StaffClassAssignment).where(
                and_(
                    StaffClassAssignment.tenant_id == tenant_id,
                    StaffClassAssignment.section_id == section_id,
                    StaffClassAssignment.is_class_teacher == True,
                )
            )
        )
        for assignment in result.scalars().all():
            assignment.is_class_teacher = False

    # =========================
    # Teaching Staff Specific Methods
    # =========================

    async def get_teaching_staff(
        self, tenant_id: UUID, school_id: Optional[UUID] = None
    ) -> Sequence[Staff]:
        """Get all active teaching staff."""
        conditions = [
            Staff.tenant_id == tenant_id,
            Staff.staff_type == StaffType.TEACHING,
            Staff.status == StaffStatus.ACTIVE,
            Staff.deleted_at.is_(None),
        ]
        if school_id:
            conditions.append(Staff.school_id == school_id)

        result = await self.db.execute(
            select(Staff)
            .where(and_(*conditions))
            .order_by(Staff.last_name, Staff.first_name)
        )
        return result.scalars().all()


class DepartmentService:
    """Service for managing departments."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_department(
        self,
        tenant_id: UUID,
        name: str,
        code: Optional[str] = None,
        description: Optional[str] = None,
        head_id: Optional[UUID] = None,
    ) -> Department:
        """Create a new department."""
        # Check for duplicate name
        existing = await self.db.execute(
            select(Department).where(
                and_(
                    Department.tenant_id == tenant_id,
                    Department.name == name,
                    Department.deleted_at.is_(None),
                )
            )
        )
        if existing.scalar_one_or_none():
            raise StaffServiceError(
                f"Department '{name}' already exists",
                code="duplicate_department",
            )

        department = Department(
            tenant_id=tenant_id,
            name=name,
            code=code,
            description=description,
            head_id=head_id,
        )
        self.db.add(department)
        await self.db.commit()
        await self.db.refresh(department)
        return department

    async def get_department(
        self, tenant_id: UUID, department_id: UUID
    ) -> Optional[Department]:
        """Get a department by ID."""
        result = await self.db.execute(
            select(Department).where(
                and_(
                    Department.tenant_id == tenant_id,
                    Department.id == department_id,
                    Department.deleted_at.is_(None),
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_departments(
        self,
        tenant_id: UUID,
        search: Optional[str] = None,
    ) -> Sequence[Department]:
        """List all departments."""
        conditions = [
            Department.tenant_id == tenant_id,
            Department.deleted_at.is_(None),
        ]

        if search:
            conditions.append(
                or_(
                    Department.name.ilike(f"%{search}%"),
                    Department.code.ilike(f"%{search}%"),
                )
            )

        result = await self.db.execute(
            select(Department)
            .where(and_(*conditions))
            .order_by(Department.name)
        )
        return result.scalars().all()

    async def update_department(
        self,
        tenant_id: UUID,
        department_id: UUID,
        name: Optional[str] = None,
        code: Optional[str] = None,
        description: Optional[str] = None,
        head_id: Optional[UUID] = None,
    ) -> Optional[Department]:
        """Update a department."""
        department = await self.get_department(tenant_id, department_id)
        if not department:
            return None

        if name is not None:
            # Check for duplicate name
            existing = await self.db.execute(
                select(Department).where(
                    and_(
                        Department.tenant_id == tenant_id,
                        Department.name == name,
                        Department.id != department_id,
                        Department.deleted_at.is_(None),
                    )
                )
            )
            if existing.scalar_one_or_none():
                raise StaffServiceError(
                    f"Department '{name}' already exists",
                    code="duplicate_department",
                )
            department.name = name

        if code is not None:
            department.code = code
        if description is not None:
            department.description = description
        if head_id is not None:
            department.head_id = head_id

        department.updated_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(department)
        return department

    async def delete_department(
        self, tenant_id: UUID, department_id: UUID
    ) -> bool:
        """Soft delete a department."""
        department = await self.get_department(tenant_id, department_id)
        if not department:
            return False

        department.deleted_at = datetime.now(UTC)
        await self.db.commit()
        return True

    async def get_department_staff_count(
        self, tenant_id: UUID, department_id: UUID
    ) -> int:
        """Get the count of staff in a department."""
        result = await self.db.execute(
            select(func.count(Staff.id)).where(
                and_(
                    Staff.tenant_id == tenant_id,
                    Staff.department_id == department_id,
                    Staff.deleted_at.is_(None),
                )
            )
        )
        return result.scalar() or 0
