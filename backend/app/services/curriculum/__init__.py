"""
SIMS Plus - Curriculum Services Package

Re-exports all curriculum service classes for backward compatibility.
"""

from app.services.curriculum._shared import CurriculumServiceError
from app.services.curriculum.profile_service import CurriculumProfileService
from app.services.curriculum.assessment_service import AssessmentStructureService
from app.services.curriculum.equivalency_service import GradeEquivalencyService
from app.services.curriculum.subject_mapping_service import SubjectMappingService
from app.services.curriculum.external_exam_service import ExternalExamService
from app.services.curriculum.credit_service import CreditService
from app.services.curriculum.predicted_grade_service import PredictedGradeService

__all__ = [
    "CurriculumServiceError",
    "CurriculumProfileService",
    "AssessmentStructureService",
    "GradeEquivalencyService",
    "SubjectMappingService",
    "ExternalExamService",
    "CreditService",
    "PredictedGradeService",
]
