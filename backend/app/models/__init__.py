"""SIMS Plus Models package."""

from app.models.base import Base, TenantMixin, SoftDeleteMixin, AuditMixin
from app.models.tenant import Tenant, TenantType, SubscriptionTier
from app.models.user import User, UserRole, UserStatus
from app.models.school import School, SchoolType, SchoolStatus
from app.models.reserved_subdomain import ReservedSubdomain, DEFAULT_RESERVED_SUBDOMAINS
from app.models.audit_log import AuditLog
from app.models.academic import (
    AcademicYear,
    AcademicYearStatus,
    Term,
    TermStatus,
    Class,
    ClassLevel,
    ClassSection,
    Subject,
    SubjectCategory,
    ClassSubject,
    GradingScale,
    GradingScaleType,
    Grade,
    AssessmentWeight,
    AcademicSettings,
)
from app.models.student import (
    Student,
    StudentStatus,
    Gender,
    Guardian,
    StudentGuardian,
    GuardianRelationship,
)
from app.models.staff import (
    Staff,
    StaffType,
    StaffStatus,
    StaffClassAssignment,
)
from app.models.attendance import (
    AttendanceStatus,
    StudentAttendance,
    StaffAttendance,
)

__all__ = [
    "Base",
    "TenantMixin",
    "SoftDeleteMixin",
    "AuditMixin",
    "Tenant",
    "TenantType",
    "SubscriptionTier",
    "User",
    "UserRole",
    "UserStatus",
    "School",
    "SchoolType",
    "SchoolStatus",
    "ReservedSubdomain",
    "DEFAULT_RESERVED_SUBDOMAINS",
    "AuditLog",
    # Academic models
    "AcademicYear",
    "AcademicYearStatus",
    "Term",
    "TermStatus",
    "Class",
    "ClassLevel",
    "ClassSection",
    "Subject",
    "SubjectCategory",
    "ClassSubject",
    "GradingScale",
    "GradingScaleType",
    "Grade",
    "AssessmentWeight",
    "AcademicSettings",
    # Student models
    "Student",
    "StudentStatus",
    "Gender",
    "Guardian",
    "StudentGuardian",
    "GuardianRelationship",
    # Staff models
    "Staff",
    "StaffType",
    "StaffStatus",
    "StaffClassAssignment",
    # Attendance models
    "AttendanceStatus",
    "StudentAttendance",
    "StaffAttendance",
]
