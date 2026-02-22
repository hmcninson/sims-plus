"""
SIMS Plus - Academic Services Package

Re-exports AcademicService and AcademicServiceError for backward compatibility.
Existing imports like `from app.services.academic import AcademicService` continue to work.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.academic._shared import AcademicServiceError
from app.services.academic.academic_year_service import AcademicYearMixin
from app.services.academic.class_service import ClassMixin
from app.services.academic.subject_service import SubjectMixin


class AcademicService(AcademicYearMixin, ClassMixin, SubjectMixin):
    """Service for managing academic entities.

    Composed from:
    - AcademicYearMixin: Academic year and term CRUD
    - ClassMixin: Class and section CRUD
    - SubjectMixin: Subject, class-subject, grading scale, assessment weight, settings
    """

    def __init__(self, db: AsyncSession):
        self.db = db


__all__ = [
    "AcademicService",
    "AcademicServiceError",
]
