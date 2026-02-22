"""
SIMS Plus - Student Services Package

Re-exports StudentService and StudentServiceError for backward compatibility.
Existing imports like `from app.services.student import StudentService` continue to work.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.student._shared import StudentServiceError
from app.services.student.student_service import StudentCoreMixin
from app.services.student.import_service import StudentImportMixin
from app.services.student.guardian_service import StudentGuardianMixin


class StudentService(StudentCoreMixin, StudentImportMixin, StudentGuardianMixin):
    """Service for managing students and guardians.

    Composed from:
    - StudentCoreMixin: Student CRUD, ID generation, stats, bulk creation
    - StudentImportMixin: CSV/Excel file import
    - StudentGuardianMixin: Guardian CRUD, student-guardian links
    """

    def __init__(self, db: AsyncSession):
        self.db = db


__all__ = [
    "StudentService",
    "StudentServiceError",
]
