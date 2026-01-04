"""
SIMS Plus - Database Base

Import all models here for Alembic to detect.
"""

# Import base model class
from app.models.base import Base

# Import all models for Alembic autogenerate
from app.models.tenant import Tenant
from app.models.user import User

# Future models (uncomment as implemented):
# from app.models.school import School
# from app.models.student import Student
# from app.models.staff import Staff
# from app.models.academic import AcademicYear, Term, Class, Section, Subject
# from app.models.attendance import Attendance
# from app.models.exam import Exam, Score
# from app.models.finance import FeeCategory, Invoice, Payment

__all__ = ["Base", "Tenant", "User"]
