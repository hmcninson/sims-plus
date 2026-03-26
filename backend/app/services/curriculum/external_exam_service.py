"""
SIMS Plus - External Exam Service

Business logic for managing external examination registrations (WAEC, Cambridge,
Edexcel, IB, etc.) and importing results from CSV exports provided by exam boards.
"""

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from uuid import UUID

import structlog
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.orm import selectinload

from app.models.curriculum import ExternalExamBoard, ExternalExamRegistration
from app.models.student import Student
from app.services.curriculum._shared import CurriculumServiceError, check_multi_curriculum_access

logger = structlog.get_logger()

# Maximum number of registrations in a single bulk request
MAX_BULK_REGISTRATIONS = 200

# Maximum number of CSV rows to process (prevent DoS)
_MAX_CSV_ROWS = 5000

# Fields that cannot be changed after creation (identity + system fields)
_IMMUTABLE_FIELDS = {
    "id", "tenant_id", "school_id", "student_id", "exam_board",
    "exam_session", "created_at", "deleted_at",
}

# Characters that could trigger formula injection in spreadsheet applications
_CSV_INJECTION_PATTERN = re.compile(r"^[=+\-@\t\r]")


@dataclass
class ImportResult:
    """Result of a CSV results import operation."""

    total_rows: int = 0
    matched: int = 0
    unmatched: int = 0
    errors: list[str] = field(default_factory=list)
    preview_rows: list[dict] = field(default_factory=list)


def _sanitize_csv_cell(value: str) -> str:
    """
    Strip leading characters that could trigger formula injection in
    spreadsheet applications (=, +, -, @, tab, carriage return).

    Defense-in-depth: even though we control the import pipeline, sanitizing
    CSV data prevents formula injection if the data is later exported.
    """
    if value and _CSV_INJECTION_PATTERN.match(value):
        return "'" + value
    return value


class ExternalExamService:
    """Service for external examination registration and results management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================
    # Student Validation
    # =========================

    async def _validate_student(
        self, student_id: UUID, tenant_id: UUID
    ) -> Student:
        """
        Validate that a student exists and belongs to the tenant.

        PostgreSQL FK constraints bypass RLS, so user-supplied UUIDs
        must be verified against the tenant boundary.
        """
        result = await self.db.execute(
            select(Student).where(
                Student.id == student_id,
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                Student.tenant_id == tenant_id,
                Student.deleted_at.is_(None),
            )
        )
        student = result.scalar_one_or_none()
        if not student:
            raise CurriculumServiceError("Student not found", "not_found")
        return student

    async def _validate_students_batch(
        self, student_ids: list[UUID], tenant_id: UUID
    ) -> dict[UUID, Student]:
        """Validate multiple students in a single query. Returns a mapping of id -> Student."""
        unique_ids = list(set(student_ids))
        result = await self.db.execute(
            select(Student).where(
                Student.id.in_(unique_ids),
                Student.tenant_id == tenant_id,
                Student.deleted_at.is_(None),
            )
        )
        students = {s.id: s for s in result.scalars().all()}
        missing = set(unique_ids) - set(students.keys())
        if missing:
            raise CurriculumServiceError(
                f"Students not found: {', '.join(str(sid) for sid in missing)}",
                "not_found",
            )
        return students

    # =========================
    # CRUD Operations
    # =========================

    async def create_registration(
        self,
        tenant_id: UUID,
        school_id: UUID,
        data: dict,
    ) -> ExternalExamRegistration:
        """
        Create a single external exam registration.

        Validates the student belongs to the tenant before creating.
        """
        await check_multi_curriculum_access(self.db, tenant_id)
        await self._validate_student(data["student_id"], tenant_id)

        registration = ExternalExamRegistration(
            tenant_id=tenant_id,
            school_id=school_id,
            student_id=data["student_id"],
            exam_board=data["exam_board"],
            exam_session=data["exam_session"],
            subjects=[s if isinstance(s, dict) else s.model_dump() for s in data["subjects"]],
            candidate_number=data.get("candidate_number"),
            center_number=data.get("center_number"),
            registration_date=data.get("registration_date"),
            notes=data.get("notes"),
        )
        self.db.add(registration)
        await self.db.flush()
        await self.db.refresh(registration)

        logger.info(
            "external_exam_registration_created",
            registration_id=str(registration.id),
            student_id=str(data["student_id"]),
            exam_board=data["exam_board"],
            exam_session=data["exam_session"],
        )
        return registration

    async def get_registration(
        self,
        tenant_id: UUID,
        registration_id: UUID,
    ) -> ExternalExamRegistration:
        """Get a single external exam registration by ID."""
        result = await self.db.execute(
            select(ExternalExamRegistration).where(
                ExternalExamRegistration.tenant_id == tenant_id,
                ExternalExamRegistration.id == registration_id,
                ExternalExamRegistration.deleted_at.is_(None),
            )
        )
        registration = result.scalar_one_or_none()
        if not registration:
            raise CurriculumServiceError(
                "External exam registration not found", "not_found"
            )
        return registration

    async def list_registrations(
        self,
        tenant_id: UUID,
        *,
        student_id: UUID | None = None,
        exam_board: str | None = None,
        exam_session: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ExternalExamRegistration], int]:
        """List external exam registrations with optional filters."""
        base_filter = and_(
            ExternalExamRegistration.tenant_id == tenant_id,
            ExternalExamRegistration.deleted_at.is_(None),
        )

        query = select(ExternalExamRegistration).where(base_filter)
        count_query = select(func.count(ExternalExamRegistration.id)).where(base_filter)

        if student_id is not None:
            query = query.where(ExternalExamRegistration.student_id == student_id)
            count_query = count_query.where(
                ExternalExamRegistration.student_id == student_id
            )

        if exam_board is not None:
            query = query.where(ExternalExamRegistration.exam_board == exam_board)
            count_query = count_query.where(
                ExternalExamRegistration.exam_board == exam_board
            )

        if exam_session is not None:
            query = query.where(ExternalExamRegistration.exam_session == exam_session)
            count_query = count_query.where(
                ExternalExamRegistration.exam_session == exam_session
            )

        if status is not None:
            query = query.where(ExternalExamRegistration.registration_status == status)
            count_query = count_query.where(
                ExternalExamRegistration.registration_status == status
            )

        # Get total count
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination and ordering
        query = (
            query.order_by(ExternalExamRegistration.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def update_registration(
        self,
        tenant_id: UUID,
        registration_id: UUID,
        data: dict,
    ) -> ExternalExamRegistration:
        """
        Update an external exam registration.

        Identity fields (student_id, exam_board, exam_session) are immutable
        after creation to preserve data integrity.
        """
        registration = await self.get_registration(tenant_id, registration_id)

        # Reject attempts to change immutable fields
        for field_name in _IMMUTABLE_FIELDS:
            if field_name in data:
                raise CurriculumServiceError(
                    f"Field '{field_name}' cannot be changed after creation",
                    "immutable_field",
                )

        # Apply mutable field updates
        update_fields = {
            k: v for k, v in data.items()
            if v is not None
        }

        if "subjects" in update_fields:
            update_fields["subjects"] = [
                s if isinstance(s, dict) else s.model_dump()
                for s in update_fields["subjects"]
            ]

        for key, value in update_fields.items():
            setattr(registration, key, value)

        await self.db.flush()
        await self.db.refresh(registration)

        logger.info(
            "external_exam_registration_updated",
            registration_id=str(registration_id),
            updated_fields=list(update_fields.keys()),
        )
        return registration

    async def soft_delete_registration(
        self,
        tenant_id: UUID,
        registration_id: UUID,
    ) -> None:
        """Soft delete an external exam registration."""
        registration = await self.get_registration(tenant_id, registration_id)
        registration.deleted_at = datetime.now(timezone.utc)
        await self.db.flush()

        logger.info(
            "external_exam_registration_deleted",
            registration_id=str(registration_id),
        )

    # =========================
    # Bulk Operations
    # =========================

    async def bulk_register(
        self,
        tenant_id: UUID,
        school_id: UUID,
        registrations_data: list[dict],
    ) -> list[ExternalExamRegistration]:
        """
        Create multiple external exam registrations in a single operation.

        Validates all students upfront before creating any registrations
        to provide atomic all-or-nothing behaviour.
        """
        await check_multi_curriculum_access(self.db, tenant_id)
        if len(registrations_data) > MAX_BULK_REGISTRATIONS:
            raise CurriculumServiceError(
                f"Maximum {MAX_BULK_REGISTRATIONS} registrations per request",
                "bulk_limit_exceeded",
            )

        # Validate all students in a single batch query
        student_ids = [r["student_id"] for r in registrations_data]
        await self._validate_students_batch(student_ids, tenant_id)

        created = []
        for data in registrations_data:
            registration = ExternalExamRegistration(
                tenant_id=tenant_id,
                school_id=school_id,
                student_id=data["student_id"],
                exam_board=data["exam_board"],
                exam_session=data["exam_session"],
                subjects=[
                    s if isinstance(s, dict) else s.model_dump()
                    for s in data["subjects"]
                ],
                candidate_number=data.get("candidate_number"),
                center_number=data.get("center_number"),
                registration_date=data.get("registration_date"),
                notes=data.get("notes"),
            )
            self.db.add(registration)
            created.append(registration)

        await self.db.flush()
        for reg in created:
            await self.db.refresh(reg)

        logger.info(
            "external_exam_bulk_registration",
            count=len(created),
            tenant_id=str(tenant_id),
        )
        return created

    # =========================
    # Results Import
    # =========================

    async def import_results(
        self,
        tenant_id: UUID,
        registration_id: UUID,
        results: list[dict],
    ) -> ExternalExamRegistration:
        """Import results for a single registration."""
        registration = await self.get_registration(tenant_id, registration_id)
        registration.results = results
        registration.results_date = date.today()

        await self.db.flush()
        await self.db.refresh(registration)

        logger.info(
            "external_exam_results_imported",
            registration_id=str(registration_id),
            results_count=len(results),
        )
        return registration

    async def import_results_csv(
        self,
        tenant_id: UUID,
        exam_board: str,
        exam_session: str,
        csv_content: str,
        dry_run: bool = True,
    ) -> ImportResult:
        """
        Parse and import exam results from a CSV file.

        Supports two formats:
        - WAEC: CandidateNumber,SubjectCode,SubjectName,Grade,Score
        - Cambridge: CandidateNumber,CenterNumber,ComponentCode,ComponentName,Grade,Mark,MaxMark

        All CSV cells are sanitized to prevent formula injection.
        In dry_run mode, results are previewed but not committed.
        """
        import_result = ImportResult()

        try:
            reader = csv.DictReader(io.StringIO(csv_content))
            if not reader.fieldnames:
                import_result.errors.append("CSV file is empty or has no headers")
                return import_result
        except csv.Error as e:
            import_result.errors.append(f"Invalid CSV format: {e}")
            return import_result

        is_waec = self._is_waec_format(reader.fieldnames)
        is_cambridge = self._is_cambridge_format(reader.fieldnames)

        if not is_waec and not is_cambridge:
            import_result.errors.append(
                "Unrecognized CSV format. Expected WAEC columns "
                "(CandidateNumber,SubjectCode,SubjectName,Grade,Score) or "
                "Cambridge columns (CandidateNumber,CenterNumber,ComponentCode,"
                "ComponentName,Grade,Mark,MaxMark)"
            )
            return import_result

        # Build a lookup of registrations by candidate_number for this board+session
        registrations_by_candidate = await self._get_registrations_by_candidate(
            tenant_id, exam_board, exam_session
        )

        # Group results by candidate number
        candidate_results: dict[str, list[dict]] = {}
        for row_num, row in enumerate(reader, start=2):
            import_result.total_rows += 1

            # Cap row count to prevent DoS
            if import_result.total_rows > _MAX_CSV_ROWS:
                import_result.errors.append(
                    f"CSV exceeds maximum of {_MAX_CSV_ROWS} rows"
                )
                return import_result

            candidate_num = _sanitize_csv_cell(
                (row.get("CandidateNumber") or "").strip()
            )
            if not candidate_num:
                import_result.errors.append(f"Row {row_num}: missing CandidateNumber")
                continue

            if is_waec:
                result_entry = self._parse_waec_row(row, row_num, import_result)
            else:
                result_entry = self._parse_cambridge_row(row, row_num, import_result)

            if result_entry is None:
                continue

            candidate_results.setdefault(candidate_num, []).append(result_entry)

        # Match candidates to registrations
        for candidate_num, results in candidate_results.items():
            if candidate_num in registrations_by_candidate:
                import_result.matched += 1
                import_result.preview_rows.append({
                    "candidate_number": candidate_num,
                    "results_count": len(results),
                    "results": results,
                    "status": "matched",
                })

                if not dry_run:
                    registration = registrations_by_candidate[candidate_num]
                    registration.results = results
                    registration.results_date = date.today()
            else:
                import_result.unmatched += 1
                import_result.preview_rows.append({
                    "candidate_number": candidate_num,
                    "results_count": len(results),
                    "results": results,
                    "status": "unmatched",
                })

        if not dry_run:
            await self.db.flush()
            logger.info(
                "external_exam_csv_results_imported",
                exam_board=exam_board,
                exam_session=exam_session,
                matched=import_result.matched,
                unmatched=import_result.unmatched,
            )

        return import_result

    # =========================
    # Export Operations
    # =========================

    async def export_waec(
        self,
        tenant_id: UUID,
        exam_session: str,
    ) -> list[dict]:
        """
        Generate WAEC registration export data.

        Returns a list of dicts suitable for CSV serialization with
        fields: CandidateNumber, StudentName, SubjectCode, SubjectName.
        """
        registrations = await self._get_registrations_for_export(
            tenant_id, ExternalExamBoard.WAEC.value, exam_session
        )

        export_rows = []
        for reg in registrations:
            for subject in reg.subjects or []:
                export_rows.append({
                    "CandidateNumber": reg.candidate_number or "",
                    "StudentID": str(reg.student_id),
                    "ExamSession": reg.exam_session,
                    "SubjectCode": subject.get("subject_code", ""),
                    "SubjectName": subject.get("subject_name", ""),
                    "Level": subject.get("level", ""),
                })
        return export_rows

    async def export_cambridge(
        self,
        tenant_id: UUID,
        exam_session: str,
    ) -> list[dict]:
        """
        Generate Cambridge International registration export data.

        Returns a list of dicts suitable for CSV serialization with
        fields: CandidateNumber, CenterNumber, ComponentCode, ComponentName, Level.
        """
        registrations = await self._get_registrations_for_export(
            tenant_id, ExternalExamBoard.CAMBRIDGE_INTERNATIONAL.value, exam_session
        )

        export_rows = []
        for reg in registrations:
            for subject in reg.subjects or []:
                paper_numbers = subject.get("paper_numbers") or []
                if paper_numbers:
                    for paper in paper_numbers:
                        export_rows.append({
                            "CandidateNumber": reg.candidate_number or "",
                            "CenterNumber": reg.center_number or "",
                            "StudentID": str(reg.student_id),
                            "ExamSession": reg.exam_session,
                            "ComponentCode": subject.get("subject_code", ""),
                            "ComponentName": subject.get("subject_name", ""),
                            "PaperNumber": paper,
                            "Level": subject.get("level", ""),
                        })
                else:
                    export_rows.append({
                        "CandidateNumber": reg.candidate_number or "",
                        "CenterNumber": reg.center_number or "",
                        "StudentID": str(reg.student_id),
                        "ExamSession": reg.exam_session,
                        "ComponentCode": subject.get("subject_code", ""),
                        "ComponentName": subject.get("subject_name", ""),
                        "PaperNumber": "",
                        "Level": subject.get("level", ""),
                    })
        return export_rows

    async def export_edexcel(
        self,
        tenant_id: UUID,
        exam_session: str,
    ) -> list[dict]:
        """
        Generate Edexcel registration export data.

        Returns a list of dicts suitable for CSV serialization with fields:
        CentreNumber, CandidateNumber, Surname, FirstName, DateOfBirth,
        Gender, QualificationCode, SubjectTitle, OptionCode, EntryLevel.

        All string fields are sanitized to prevent CSV formula injection.
        """
        registrations = await self._get_registrations_with_students(
            tenant_id, ExternalExamBoard.EDEXCEL.value, exam_session
        )

        export_rows = []
        for reg in registrations:
            student = reg.student
            for subject in reg.subjects or []:
                export_rows.append({
                    "CentreNumber": _sanitize_csv_cell(reg.center_number or ""),
                    "CandidateNumber": _sanitize_csv_cell(
                        reg.candidate_number or ""
                    ),
                    "Surname": _sanitize_csv_cell(student.last_name),
                    "FirstName": _sanitize_csv_cell(student.first_name),
                    "DateOfBirth": (
                        student.date_of_birth.strftime("%d/%m/%Y")
                        if student.date_of_birth
                        else ""
                    ),
                    "Gender": _sanitize_csv_cell(
                        student.gender.value if student.gender else ""
                    ),
                    "QualificationCode": _sanitize_csv_cell(
                        subject.get("subject_code", "")
                    ),
                    "SubjectTitle": _sanitize_csv_cell(
                        subject.get("subject_name", "")
                    ),
                    "OptionCode": _sanitize_csv_cell(
                        subject.get("option_code", "")
                    ),
                    "EntryLevel": _sanitize_csv_cell(
                        subject.get("level", "")
                    ),
                })
        return export_rows

    async def export_ib(
        self,
        tenant_id: UUID,
        exam_session: str,
    ) -> list[dict]:
        """
        Generate IB candidate registration export data.

        Returns a list of dicts suitable for CSV serialization with fields:
        SchoolCode, CandidateNumber, Surname, FirstName, DateOfBirth,
        Programme, SubjectGroup, SubjectCode, SubjectName, Level, PaperNumbers.

        IB uses YYYY-MM-DD date format per IBO specification.
        All string fields are sanitized to prevent CSV formula injection.
        """
        registrations = await self._get_registrations_with_students(
            tenant_id, ExternalExamBoard.IBO.value, exam_session
        )

        export_rows = []
        for reg in registrations:
            student = reg.student
            for subject in reg.subjects or []:
                paper_numbers = subject.get("paper_numbers", [])
                export_rows.append({
                    "SchoolCode": _sanitize_csv_cell(
                        reg.center_number or ""
                    ),
                    "CandidateNumber": _sanitize_csv_cell(
                        reg.candidate_number or ""
                    ),
                    "Surname": _sanitize_csv_cell(student.last_name),
                    "FirstName": _sanitize_csv_cell(student.first_name),
                    # IB uses ISO date format (YYYY-MM-DD)
                    "DateOfBirth": (
                        student.date_of_birth.strftime("%Y-%m-%d")
                        if student.date_of_birth
                        else ""
                    ),
                    "Programme": _sanitize_csv_cell(
                        subject.get("programme", "DP")
                    ),
                    "SubjectGroup": _sanitize_csv_cell(
                        subject.get("subject_group", "")
                    ),
                    "SubjectCode": _sanitize_csv_cell(
                        subject.get("subject_code", "")
                    ),
                    "SubjectName": _sanitize_csv_cell(
                        subject.get("subject_name", "")
                    ),
                    "Level": _sanitize_csv_cell(
                        subject.get("level", "")
                    ),
                    "PaperNumbers": _sanitize_csv_cell(
                        ",".join(paper_numbers) if paper_numbers else ""
                    ),
                })
        return export_rows

    # =========================
    # Private Helpers
    # =========================

    async def _get_registrations_by_candidate(
        self,
        tenant_id: UUID,
        exam_board: str,
        exam_session: str,
    ) -> dict[str, ExternalExamRegistration]:
        """Build a lookup of registrations keyed by candidate_number."""
        result = await self.db.execute(
            select(ExternalExamRegistration).where(
                ExternalExamRegistration.tenant_id == tenant_id,
                ExternalExamRegistration.exam_board == exam_board,
                ExternalExamRegistration.exam_session == exam_session,
                ExternalExamRegistration.candidate_number.isnot(None),
                ExternalExamRegistration.deleted_at.is_(None),
            )
        )
        registrations = result.scalars().all()
        return {r.candidate_number: r for r in registrations}

    async def _get_registrations_for_export(
        self,
        tenant_id: UUID,
        exam_board: str,
        exam_session: str,
    ) -> list[ExternalExamRegistration]:
        """Get all active registrations for a board+session combination."""
        result = await self.db.execute(
            select(ExternalExamRegistration).where(
                ExternalExamRegistration.tenant_id == tenant_id,
                ExternalExamRegistration.exam_board == exam_board,
                ExternalExamRegistration.exam_session == exam_session,
                ExternalExamRegistration.deleted_at.is_(None),
            ).order_by(ExternalExamRegistration.candidate_number)
        )
        return list(result.scalars().all())

    async def _get_registrations_with_students(
        self,
        tenant_id: UUID,
        exam_board: str,
        exam_session: str,
    ) -> list[ExternalExamRegistration]:
        """Get active registrations with eagerly-loaded student data.

        Required by Edexcel and IB exports which include student biographical
        fields (name, DOB, gender) in the export format.
        """
        result = await self.db.execute(
            select(ExternalExamRegistration)
            .where(
                ExternalExamRegistration.tenant_id == tenant_id,
                ExternalExamRegistration.exam_board == exam_board,
                ExternalExamRegistration.exam_session == exam_session,
                ExternalExamRegistration.deleted_at.is_(None),
            )
            .options(selectinload(ExternalExamRegistration.student))
            .order_by(ExternalExamRegistration.candidate_number)
        )
        return list(result.scalars().all())

    @staticmethod
    def _is_waec_format(fieldnames: list[str]) -> bool:
        """Check if CSV headers match the WAEC results format."""
        required = {"CandidateNumber", "SubjectCode", "SubjectName", "Grade", "Score"}
        return required.issubset(set(fieldnames or []))

    @staticmethod
    def _is_cambridge_format(fieldnames: list[str]) -> bool:
        """Check if CSV headers match the Cambridge results format."""
        required = {
            "CandidateNumber", "CenterNumber", "ComponentCode",
            "ComponentName", "Grade", "Mark", "MaxMark",
        }
        return required.issubset(set(fieldnames or []))

    @staticmethod
    def _parse_waec_row(
        row: dict, row_num: int, import_result: ImportResult
    ) -> dict | None:
        """Parse a single WAEC CSV row into a result dict."""
        subject_code = _sanitize_csv_cell((row.get("SubjectCode") or "").strip())
        grade = _sanitize_csv_cell((row.get("Grade") or "").strip())

        if not subject_code:
            import_result.errors.append(f"Row {row_num}: missing SubjectCode")
            return None

        score_str = _sanitize_csv_cell((row.get("Score") or "").strip())
        score = None
        if score_str:
            try:
                score = float(score_str)
            except ValueError:
                import_result.errors.append(
                    f"Row {row_num}: invalid Score '{score_str}'"
                )
                return None

        return {
            "subject_code": subject_code,
            "subject_name": _sanitize_csv_cell(
                (row.get("SubjectName") or "").strip()
            ),
            "grade": grade,
            "score": score,
        }

    @staticmethod
    def _parse_cambridge_row(
        row: dict, row_num: int, import_result: ImportResult
    ) -> dict | None:
        """Parse a single Cambridge CSV row into a result dict."""
        component_code = _sanitize_csv_cell(
            (row.get("ComponentCode") or "").strip()
        )
        grade = _sanitize_csv_cell((row.get("Grade") or "").strip())

        if not component_code:
            import_result.errors.append(f"Row {row_num}: missing ComponentCode")
            return None

        mark_str = _sanitize_csv_cell((row.get("Mark") or "").strip())
        max_mark_str = _sanitize_csv_cell((row.get("MaxMark") or "").strip())

        mark = None
        max_mark = None
        if mark_str:
            try:
                mark = float(mark_str)
            except ValueError:
                import_result.errors.append(
                    f"Row {row_num}: invalid Mark '{mark_str}'"
                )
                return None
        if max_mark_str:
            try:
                max_mark = float(max_mark_str)
            except ValueError:
                import_result.errors.append(
                    f"Row {row_num}: invalid MaxMark '{max_mark_str}'"
                )
                return None

        return {
            "subject_code": component_code,
            "subject_name": _sanitize_csv_cell(
                (row.get("ComponentName") or "").strip()
            ),
            "center_number": _sanitize_csv_cell(
                (row.get("CenterNumber") or "").strip()
            ),
            "grade": grade,
            "mark": mark,
            "max_mark": max_mark,
        }
