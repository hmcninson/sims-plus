"""
SIMS Plus - Academic Models Package

Re-exports all academic model classes and enums for backward compatibility.
All external code can continue to use:
    from app.models.academic import AcademicYear, Class, Subject, ...
"""

# Year models
from .year_models import AcademicYear, AcademicYearStatus, Term, TermStatus

# Class models
from .class_models import Class, ClassLevel, ClassSection, ClassSubject

# Subject and grading models
from .subject_models import (
    Subject,
    SubjectCategory,
    GradingScale,
    GradingScaleType,
    Grade,
    AssessmentWeight,
    AcademicSettings,
)

# Timetable and calendar models
from .timetable_models import (
    DayOfWeek,
    SchoolPeriod,
    SchoolHoliday,
    ClassTimetable,
)

__all__ = [
    # Year models
    "AcademicYear",
    "AcademicYearStatus",
    "Term",
    "TermStatus",
    # Class models
    "Class",
    "ClassLevel",
    "ClassSection",
    "ClassSubject",
    # Subject and grading models
    "Subject",
    "SubjectCategory",
    "GradingScale",
    "GradingScaleType",
    "Grade",
    "AssessmentWeight",
    "AcademicSettings",
    # Timetable and calendar models
    "DayOfWeek",
    "SchoolPeriod",
    "SchoolHoliday",
    "ClassTimetable",
]
