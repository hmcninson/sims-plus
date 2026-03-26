"""
SIMS Plus - Preschool Schemas Package

Re-exports all schemas for backward compatibility.
Existing imports like `from app.schemas.preschool import LearningAreaCreate` continue to work.
"""

from app.schemas.preschool.core import (
    convert_uuid,
    BaseSchema,
    LearningAreaBase,
    LearningAreaCreate,
    LearningAreaUpdate,
    LearningAreaResponse,
    LearningAreaWithSkills,
    DevelopmentalSkillBase,
    DevelopmentalSkillCreate,
    DevelopmentalSkillUpdate,
    DevelopmentalSkillResponse,
    DevelopmentalSkillBulkCreate,
    PreschoolRatingBase,
    PreschoolRatingCreate,
    PreschoolRatingResponse,
    PreschoolRatingScaleBase,
    PreschoolRatingScaleCreate,
    PreschoolRatingScaleUpdate,
    PreschoolRatingScaleResponse,
    PreschoolRatingScaleWithRatings,
    StudentSkillAssessmentBase,
    StudentSkillAssessmentCreate,
    StudentSkillAssessmentBulk,
    SkillAssessmentEntry,
    BulkAssessmentResult,
    StudentSkillAssessmentResponse,
    StudentSkillAssessmentWithDetails,
    SeedLearningAreasRequest,
    SeedRatingScaleRequest,
)

from app.schemas.preschool.observation import (
    AttachmentSchema,
    ProgressObservationBase,
    ProgressObservationCreate,
    ProgressObservationUpdate,
    ProgressObservationResponse,
    MealEntry,
    DailyActivityLogBase,
    DailyActivityLogCreate,
    DailyActivityLogUpdate,
    DailyActivityLogResponse,
)

from app.schemas.preschool.report import (
    LearningAreaSummary,
    PreschoolReportBase,
    PreschoolReportCreate,
    PreschoolReportUpdate,
    PreschoolReportResponse,
    PreschoolReportGenerateRequest,
    PreschoolReportPublishRequest,
)

from app.schemas.preschool.incident import (
    AttachmentSchema as IncidentAttachmentSchema,
    AllergyEntry,
    DietaryRequirements,
    DietaryRequirementsUpdate,
    AllergyAlertResponse,
    PreschoolIncidentCreate,
    PreschoolIncidentUpdate,
    PreschoolIncidentResponse,
    IncidentResolveRequest,
)

from app.schemas.preschool.pickup import (
    AuthorizedPickupCreate,
    AuthorizedPickupUpdate,
    AuthorizedPickupResponse,
    PickupLogCreate,
    PickupLogResponse,
)

from app.schemas.preschool.portfolio import (
    LearningStoryCreate,
    LearningStoryUpdate,
    LearningStoryResponse,
    TimelineEntry,
)

from app.schemas.preschool.extended_care import (
    ExtendedCareCheckInRequest,
    ExtendedCareCheckOutRequest,
    ExtendedCareSessionResponse,
    ExtendedCareBillingSummary,
    CaregiverRatioSet,
    CaregiverRatioResponse,
)

from app.schemas.preschool.supply import (
    PreschoolSupplyCreate,
    PreschoolSupplyUpdate,
    SupplyUseRequest,
    SupplyRestockRequest,
    PreschoolSupplyResponse,
)

__all__ = [
    # Utility
    "convert_uuid",
    "BaseSchema",
    # Learning Areas
    "LearningAreaBase",
    "LearningAreaCreate",
    "LearningAreaUpdate",
    "LearningAreaResponse",
    "LearningAreaWithSkills",
    # Developmental Skills
    "DevelopmentalSkillBase",
    "DevelopmentalSkillCreate",
    "DevelopmentalSkillUpdate",
    "DevelopmentalSkillResponse",
    "DevelopmentalSkillBulkCreate",
    # Ratings
    "PreschoolRatingBase",
    "PreschoolRatingCreate",
    "PreschoolRatingResponse",
    "PreschoolRatingScaleBase",
    "PreschoolRatingScaleCreate",
    "PreschoolRatingScaleUpdate",
    "PreschoolRatingScaleResponse",
    "PreschoolRatingScaleWithRatings",
    # Assessments
    "StudentSkillAssessmentBase",
    "StudentSkillAssessmentCreate",
    "StudentSkillAssessmentBulk",
    "SkillAssessmentEntry",
    "BulkAssessmentResult",
    "StudentSkillAssessmentResponse",
    "StudentSkillAssessmentWithDetails",
    # Observations
    "AttachmentSchema",
    "ProgressObservationBase",
    "ProgressObservationCreate",
    "ProgressObservationUpdate",
    "ProgressObservationResponse",
    # Daily Logs
    "MealEntry",
    "DailyActivityLogBase",
    "DailyActivityLogCreate",
    "DailyActivityLogUpdate",
    "DailyActivityLogResponse",
    # Reports
    "LearningAreaSummary",
    "PreschoolReportBase",
    "PreschoolReportCreate",
    "PreschoolReportUpdate",
    "PreschoolReportResponse",
    "PreschoolReportGenerateRequest",
    "PreschoolReportPublishRequest",
    # Seed
    "SeedLearningAreasRequest",
    "SeedRatingScaleRequest",
    # Incidents
    "IncidentAttachmentSchema",
    "AllergyEntry",
    "DietaryRequirements",
    "DietaryRequirementsUpdate",
    "AllergyAlertResponse",
    "PreschoolIncidentCreate",
    "PreschoolIncidentUpdate",
    "PreschoolIncidentResponse",
    "IncidentResolveRequest",
    # Pickup
    "AuthorizedPickupCreate",
    "AuthorizedPickupUpdate",
    "AuthorizedPickupResponse",
    "PickupLogCreate",
    "PickupLogResponse",
    # Learning Stories / Portfolio (Phase 2)
    "LearningStoryCreate",
    "LearningStoryUpdate",
    "LearningStoryResponse",
    "TimelineEntry",
    # Extended Care (Phase 2)
    "ExtendedCareCheckInRequest",
    "ExtendedCareCheckOutRequest",
    "ExtendedCareSessionResponse",
    "ExtendedCareBillingSummary",
    # Caregiver Ratios (Phase 2)
    "CaregiverRatioSet",
    "CaregiverRatioResponse",
    # Supplies (Phase 3)
    "PreschoolSupplyCreate",
    "PreschoolSupplyUpdate",
    "SupplyUseRequest",
    "SupplyRestockRequest",
    "PreschoolSupplyResponse",
]
