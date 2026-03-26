"""
SIMS Plus - Preschool Services Package

Re-exports PreschoolService and PreschoolServiceError for backward compatibility.
Existing imports like `from app.services.preschool import PreschoolService` continue to work.

The PreschoolService facade delegates to specialized sub-services while maintaining
the same public API as the original monolithic class.
"""

from app.services.preschool._shared import (
    PreschoolServiceError,
    DEFAULT_LEARNING_AREAS,
    DEFAULT_SKILLS_BY_AREA,
    DEFAULT_RATING_SCALE,
)
from app.services.preschool.core_service import PreschoolCoreService
from app.services.preschool.observation_service import PreschoolObservationService
from app.services.preschool.report_service import PreschoolReportService
from app.services.preschool.incident_service import PreschoolIncidentService
from app.services.preschool.pickup_service import PreschoolPickupService
from app.services.preschool.portfolio_service import PreschoolPortfolioService
from app.services.preschool.extended_care_service import PreschoolExtendedCareService
from app.services.preschool.supply_service import PreschoolSupplyService

from sqlalchemy.ext.asyncio import AsyncSession


class PreschoolService:
    """Facade service that delegates to specialized sub-services.

    Maintains backward compatibility with the original monolithic PreschoolService.
    All existing callers can continue using PreschoolService(db).method_name() unchanged.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._core = PreschoolCoreService(db)
        self._observation = PreschoolObservationService(db)
        self._report = PreschoolReportService(db)
        self._incident = PreschoolIncidentService(db)
        self._pickup = PreschoolPickupService(db)
        self._portfolio = PreschoolPortfolioService(db)
        self._extended_care = PreschoolExtendedCareService(db)
        self._supply = PreschoolSupplyService(db)

    # =========================
    # Core Service (Learning Areas, Skills, Ratings, Assessments, Seeds)
    # =========================

    # Learning Areas
    create_learning_area = property(lambda self: self._core.create_learning_area)
    get_learning_area = property(lambda self: self._core.get_learning_area)
    list_learning_areas = property(lambda self: self._core.list_learning_areas)
    update_learning_area = property(lambda self: self._core.update_learning_area)
    delete_learning_area = property(lambda self: self._core.delete_learning_area)

    # Skills
    create_skill = property(lambda self: self._core.create_skill)
    bulk_create_skills = property(lambda self: self._core.bulk_create_skills)
    get_skill = property(lambda self: self._core.get_skill)
    list_skills = property(lambda self: self._core.list_skills)
    update_skill = property(lambda self: self._core.update_skill)
    delete_skill = property(lambda self: self._core.delete_skill)

    # Rating Scales
    create_rating_scale = property(lambda self: self._core.create_rating_scale)
    get_rating_scale = property(lambda self: self._core.get_rating_scale)
    get_default_rating_scale = property(lambda self: self._core.get_default_rating_scale)
    list_rating_scales = property(lambda self: self._core.list_rating_scales)
    update_rating_scale = property(lambda self: self._core.update_rating_scale)
    delete_rating_scale = property(lambda self: self._core.delete_rating_scale)

    # Assessments
    create_or_update_assessment = property(lambda self: self._core.create_or_update_assessment)
    bulk_assess = property(lambda self: self._core.bulk_assess)
    list_assessments = property(lambda self: self._core.list_assessments)

    # Seeds
    seed_learning_areas = property(lambda self: self._core.seed_learning_areas)
    seed_rating_scale = property(lambda self: self._core.seed_rating_scale)

    # =========================
    # Observation Service (Observations, Daily Logs)
    # =========================

    # Observations
    create_observation = property(lambda self: self._observation.create_observation)
    get_observation = property(lambda self: self._observation.get_observation)
    list_observations = property(lambda self: self._observation.list_observations)
    update_observation = property(lambda self: self._observation.update_observation)
    delete_observation = property(lambda self: self._observation.delete_observation)

    # Daily Logs
    create_or_update_daily_log = property(lambda self: self._observation.create_or_update_daily_log)
    get_daily_log = property(lambda self: self._observation.get_daily_log)
    list_daily_logs = property(lambda self: self._observation.list_daily_logs)

    # Daily Report Sending
    send_daily_log_to_parents = property(lambda self: self._observation.send_daily_log_to_parents)
    bulk_send_daily_logs = property(lambda self: self._observation.bulk_send_daily_logs)

    # =========================
    # Report Service
    # =========================

    create_report = property(lambda self: self._report.create_report)
    get_report = property(lambda self: self._report.get_report)
    list_reports = property(lambda self: self._report.list_reports)
    update_report = property(lambda self: self._report.update_report)
    publish_reports = property(lambda self: self._report.publish_reports)
    generate_reports = property(lambda self: self._report.generate_reports)

    # =========================
    # Incident Service (Incidents)
    # =========================

    create_incident = property(lambda self: self._incident.create_incident)
    list_incidents = property(lambda self: self._incident.list_incidents)
    get_incident = property(lambda self: self._incident.get_incident)
    update_incident = property(lambda self: self._incident.update_incident)
    notify_parent_incident = property(lambda self: self._incident.notify_parent_incident)
    resolve_incident = property(lambda self: self._incident.resolve_incident)

    # =========================
    # Pickup Service (Pickups, Logs, Dietary)
    # =========================

    # Authorized Pickups
    add_authorized_pickup = property(lambda self: self._pickup.add_authorized_pickup)
    list_authorized_pickups = property(lambda self: self._pickup.list_authorized_pickups)
    update_authorized_pickup = property(lambda self: self._pickup.update_authorized_pickup)
    deactivate_authorized_pickup = property(lambda self: self._pickup.deactivate_authorized_pickup)

    # Pickup Logs
    record_pickup = property(lambda self: self._pickup.record_pickup)
    list_pickup_logs = property(lambda self: self._pickup.list_pickup_logs)

    # Allergy / Dietary
    get_student_dietary_requirements = property(lambda self: self._pickup.get_student_dietary_requirements)
    update_dietary_requirements = property(lambda self: self._pickup.update_dietary_requirements)
    get_class_allergy_alerts = property(lambda self: self._pickup.get_class_allergy_alerts)

    # =========================
    # Portfolio Service (Learning Stories, Timeline)
    # =========================

    create_learning_story = property(lambda self: self._portfolio.create_learning_story)
    list_learning_stories = property(lambda self: self._portfolio.list_learning_stories)
    get_learning_story = property(lambda self: self._portfolio.get_learning_story)
    update_learning_story = property(lambda self: self._portfolio.update_learning_story)
    delete_learning_story = property(lambda self: self._portfolio.delete_learning_story)
    get_student_timeline = property(lambda self: self._portfolio.get_student_timeline)

    # =========================
    # Extended Care Service (Sessions, Billing, Ratios)
    # =========================

    check_in_extended_care = property(lambda self: self._extended_care.check_in_extended_care)
    check_out_extended_care = property(lambda self: self._extended_care.check_out_extended_care)
    list_extended_care_sessions = property(lambda self: self._extended_care.list_extended_care_sessions)
    get_extended_care_billing_summary = property(lambda self: self._extended_care.get_extended_care_billing_summary)
    list_caregiver_ratios = property(lambda self: self._extended_care.list_caregiver_ratios)
    set_caregiver_ratio = property(lambda self: self._extended_care.set_caregiver_ratio)

    # =========================
    # Supply Service (Phase 3)
    # =========================

    add_supply = property(lambda self: self._supply.add_supply)
    list_supplies = property(lambda self: self._supply.list_supplies)
    update_supply = property(lambda self: self._supply.update_supply)
    use_supply = property(lambda self: self._supply.use_supply)
    restock_supply = property(lambda self: self._supply.restock_supply)


__all__ = [
    "PreschoolService",
    "PreschoolServiceError",
    "PreschoolCoreService",
    "PreschoolObservationService",
    "PreschoolReportService",
    "PreschoolIncidentService",
    "PreschoolPickupService",
    "PreschoolPortfolioService",
    "PreschoolExtendedCareService",
    "PreschoolSupplyService",
    "DEFAULT_LEARNING_AREAS",
    "DEFAULT_SKILLS_BY_AREA",
    "DEFAULT_RATING_SCALE",
]
