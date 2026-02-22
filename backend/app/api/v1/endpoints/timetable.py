"""
SIMS Plus - Timetable Endpoints

API endpoints for class timetable management.
"""

from typing import Optional
from uuid import UUID
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.schemas.academic import (
    TimetableEntryCreate,
    TimetableEntryUpdate,
    TimetableEntryResponse,
    TimetableBulkCreate,
    TimetableWeekResponse,
    TimetableDayResponse,
    TimetableSubjectResponse,
    TimetableTeacherResponse,
    TimetableTermResponse,
    SchoolPeriodCreate,
    SchoolPeriodUpdate,
    SchoolPeriodResponse,
    SchoolPeriodBulkCreate,
    SchoolHolidayCreate,
    SchoolHolidayUpdate,
    SchoolHolidayResponse,
)
from app.services.timetable import TimetableService, TimetableServiceError

router = APIRouter()


def _format_entry_response(entry) -> TimetableEntryResponse:
    """Format a timetable entry into response schema."""
    subject_data = None
    if entry.subject:
        subject_data = TimetableSubjectResponse(
            id=entry.subject.id,
            name=entry.subject.name,
            code=entry.subject.code,
        )

    teacher_data = None
    if entry.teacher:
        teacher_data = TimetableTeacherResponse(
            id=entry.teacher.id,
            first_name=entry.teacher.first_name,
            last_name=entry.teacher.last_name,
            staff_id=entry.teacher.staff_id,
        )

    term_data = None
    if entry.term:
        term_data = TimetableTermResponse(
            id=entry.term.id,
            name=entry.term.name,
            short_name=entry.term.short_name,
        )

    return TimetableEntryResponse(
        id=entry.id,
        class_id=entry.class_id,
        section_id=entry.section_id,
        academic_year_id=entry.academic_year_id,
        term_id=entry.term_id,
        subject_id=entry.subject_id,
        teacher_id=entry.teacher_id,
        day_of_week=entry.day_of_week,
        period_number=entry.period_number,
        start_time=entry.start_time,
        end_time=entry.end_time,
        room=entry.room,
        is_active=entry.is_active,
        notes=entry.notes,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        subject=subject_data,
        teacher=teacher_data,
        term=term_data,
    )


@router.post(
    "",
    response_model=TimetableEntryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create timetable entry",
    dependencies=[Depends(require_permissions("academics.create"))],
)
async def create_timetable_entry(
    data: TimetableEntryCreate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> TimetableEntryResponse:
    """Create a new timetable entry for a class/section.

    Args:
        data.term_id: Optional term ID. If set, the timetable entry applies only to this term.
                      If not set, the entry applies to the entire academic year.
    """
    service = TimetableService(db)
    try:
        entry = await service.create_timetable_entry(
            tenant_id=tenant.tenant_id,
            class_id=data.class_id,
            academic_year_id=data.academic_year_id,
            day_of_week=data.day_of_week,
            period_number=data.period_number,
            start_time=data.start_time,
            end_time=data.end_time,
            section_id=data.section_id,
            term_id=data.term_id,
            subject_id=data.subject_id,
            teacher_id=data.teacher_id,
            room=data.room,
            notes=data.notes,
        )
        # Refresh to load relations
        entry = await service.get_timetable_entry(tenant.tenant_id, entry.id)
        return _format_entry_response(entry)
    except TimetableServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get(
    "/class/{class_id}",
    response_model=TimetableWeekResponse,
    summary="Get class timetable",
    dependencies=[Depends(require_permissions("academics.read"))],
)
async def get_class_timetable(
    class_id: UUID,
    academic_year_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    section_id: Optional[UUID] = Query(None, description="Filter by section"),
    term_id: Optional[UUID] = Query(None, description="Filter by term. If not set, returns year-wide timetable."),
) -> TimetableWeekResponse:
    """Get the weekly timetable for a class/section.

    Args:
        term_id: Optional term ID. If set, returns timetable for that term only.
                 If not set, returns the year-wide timetable (term_id is NULL).
    """
    service = TimetableService(db)

    # Get class details (defense-in-depth: tenant_id verified)
    class_data = await service.get_class_with_details(tenant.tenant_id, class_id)
    if not class_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class not found",
        )

    # Get academic year (defense-in-depth: tenant_id verified)
    academic_year = await service.get_academic_year(tenant.tenant_id, academic_year_id)
    if not academic_year:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Academic year not found",
        )

    # Get section if provided
    section_data = None
    if section_id:
        section_data = next(
            (s for s in class_data.sections if s.id == section_id), None
        )
        if not section_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Section not found",
            )

    # Get term if provided
    term_data = None
    if term_id:
        term_data = await service.get_term(tenant.tenant_id, term_id)
        if not term_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Term not found",
            )

    # Get timetable entries
    entries = await service.get_class_timetable(
        tenant_id=tenant.tenant_id,
        class_id=class_id,
        academic_year_id=academic_year_id,
        section_id=section_id,
        term_id=term_id,
    )

    # Format into weekly structure
    DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    days_map = {i: [] for i in range(7)}
    for entry in entries:
        days_map[entry.day_of_week].append(_format_entry_response(entry))

    days = []
    for day_num in range(7):
        day_entries = days_map[day_num]
        if day_entries:  # Only include days with entries
            days.append(TimetableDayResponse(
                day_of_week=day_num,
                day_name=DAY_NAMES[day_num],
                entries=day_entries,
            ))

    return TimetableWeekResponse(
        class_id=class_data.id,
        class_name=class_data.name,
        section_id=section_data.id if section_data else None,
        section_name=section_data.name if section_data else None,
        academic_year_id=academic_year.id,
        academic_year_name=academic_year.name,
        term_id=term_data.id if term_data else None,
        term_name=term_data.name if term_data else None,
        days=days,
        total_periods=len(entries),
    )


@router.get(
    "/teacher/{teacher_id}",
    response_model=list[TimetableEntryResponse],
    summary="Get teacher timetable",
    dependencies=[Depends(require_permissions("academics.read"))],
)
async def get_teacher_timetable(
    teacher_id: UUID,
    academic_year_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    term_id: Optional[UUID] = Query(None, description="Filter by term. If not set, returns all entries."),
) -> list[TimetableEntryResponse]:
    """Get the timetable for a teacher.

    Args:
        term_id: Optional term ID. If set, returns timetable for that term only.
                 If not set, returns all timetable entries for the academic year.
    """
    service = TimetableService(db)

    entries = await service.get_teacher_timetable(
        tenant_id=tenant.tenant_id,
        teacher_id=teacher_id,
        academic_year_id=academic_year_id,
        term_id=term_id,
    )

    return [_format_entry_response(entry) for entry in entries]


@router.post(
    "/bulk",
    response_model=list[TimetableEntryResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Bulk update class timetable",
    dependencies=[Depends(require_permissions("academics.create"))],
)
async def bulk_update_timetable(
    data: TimetableBulkCreate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> list[TimetableEntryResponse]:
    """Bulk create/update timetable for a class/section.

    This replaces the entire timetable for the specified class/section/term.

    Args:
        data.term_id: Optional term ID. If set, only replaces timetable for that term.
                      If not set, replaces year-wide timetable entries (term_id is NULL).
    """
    service = TimetableService(db)

    try:
        entries = await service.bulk_update_timetable(
            tenant_id=tenant.tenant_id,
            class_id=data.class_id,
            academic_year_id=data.academic_year_id,
            section_id=data.section_id,
            term_id=data.term_id,
            entries=[e.model_dump() for e in data.entries],
        )

        # Get entries with relations loaded
        result = []
        for entry in entries:
            loaded_entry = await service.get_timetable_entry(tenant.tenant_id, entry.id)
            result.append(_format_entry_response(loaded_entry))

        return result
    except TimetableServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


# =========================
# School Period Endpoints
# =========================


@router.get(
    "/periods",
    response_model=list[SchoolPeriodResponse],
    summary="Get school periods",
    dependencies=[Depends(require_permissions("academics.read"))],
)
async def get_school_periods(
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    class_id: Optional[UUID] = Query(None, description="Filter by class (uses hierarchy: section > class > school)"),
    section_id: Optional[UUID] = Query(None, description="Filter by section"),
    active_only: bool = Query(True, description="Only return active periods"),
) -> list[SchoolPeriodResponse]:
    """Get school periods with hierarchy support.

    Returns periods in order of specificity:
    1. Section-specific periods (if section_id provided and found)
    2. Class-specific periods (if class_id provided and found)
    3. School-wide periods (default)
    """
    service = TimetableService(db)
    periods = await service.get_school_periods(
        tenant.tenant_id,
        class_id=class_id,
        section_id=section_id,
        active_only=active_only,
    )
    return [SchoolPeriodResponse.model_validate(p) for p in periods]


@router.post(
    "/periods",
    response_model=SchoolPeriodResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create school period",
    dependencies=[Depends(require_permissions("academics.create"))],
)
async def create_school_period(
    data: SchoolPeriodCreate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> SchoolPeriodResponse:
    """Create a new school period.

    - class_id=None, section_id=None: School-wide period
    - class_id set, section_id=None: Class-specific period
    - class_id set, section_id set: Section-specific period
    """
    service = TimetableService(db)
    try:
        period = await service.create_school_period(
            tenant_id=tenant.tenant_id,
            period_number=data.period_number,
            start_time=data.start_time,
            end_time=data.end_time,
            class_id=data.class_id,
            section_id=data.section_id,
            name=data.name,
            is_break=data.is_break,
        )
        return SchoolPeriodResponse.model_validate(period)
    except TimetableServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.put(
    "/periods/{period_id}",
    response_model=SchoolPeriodResponse,
    summary="Update school period",
    dependencies=[Depends(require_permissions("academics.update"))],
)
async def update_school_period(
    period_id: UUID,
    data: SchoolPeriodUpdate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> SchoolPeriodResponse:
    """Update a school period."""
    service = TimetableService(db)
    period = await service.update_school_period(
        period_id=period_id,
        tenant_id=tenant.tenant_id,
        **data.model_dump(exclude_unset=True),
    )
    if not period:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School period not found",
        )
    return SchoolPeriodResponse.model_validate(period)


@router.delete(
    "/periods/{period_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete school period",
    dependencies=[Depends(require_permissions("academics.delete"))],
)
async def delete_school_period(
    period_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> None:
    """Delete a school period."""
    service = TimetableService(db)
    deleted = await service.delete_school_period(period_id, tenant.tenant_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School period not found",
        )


@router.post(
    "/periods/bulk",
    response_model=list[SchoolPeriodResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Bulk create school periods",
    dependencies=[Depends(require_permissions("academics.create"))],
)
async def bulk_create_school_periods(
    data: SchoolPeriodBulkCreate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> list[SchoolPeriodResponse]:
    """Bulk create school periods at a specific level, replacing existing periods at that level.

    - class_id=None, section_id=None: Replaces school-wide periods
    - class_id set, section_id=None: Replaces class-specific periods
    - class_id set, section_id set: Replaces section-specific periods
    """
    service = TimetableService(db)
    periods = await service.bulk_create_school_periods(
        tenant_id=tenant.tenant_id,
        periods=[p.model_dump() for p in data.periods],
        class_id=data.class_id,
        section_id=data.section_id,
    )
    return [SchoolPeriodResponse.model_validate(p) for p in periods]


# =========================
# School Holiday Endpoints
# =========================


@router.get(
    "/holidays",
    response_model=list[SchoolHolidayResponse],
    summary="Get school holidays",
    dependencies=[Depends(require_permissions("academics.read"))],
)
async def get_school_holidays(
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    academic_year_id: Optional[UUID] = Query(None, description="Filter by academic year"),
) -> list[SchoolHolidayResponse]:
    """Get all school holidays for the current tenant."""
    service = TimetableService(db)
    holidays = await service.get_school_holidays(tenant.tenant_id, academic_year_id)
    return [SchoolHolidayResponse.model_validate(h) for h in holidays]


@router.post(
    "/holidays",
    response_model=SchoolHolidayResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create school holiday",
    dependencies=[Depends(require_permissions("academics.create"))],
)
async def create_school_holiday(
    data: SchoolHolidayCreate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> SchoolHolidayResponse:
    """Create a new school holiday."""
    service = TimetableService(db)
    try:
        holiday = await service.create_school_holiday(
            tenant_id=tenant.tenant_id,
            date=data.date,
            name=data.name,
            description=data.description,
            holiday_type=data.holiday_type,
            academic_year_id=data.academic_year_id,
            is_recurring=data.is_recurring,
        )
        return SchoolHolidayResponse.model_validate(holiday)
    except TimetableServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.put(
    "/holidays/{holiday_id}",
    response_model=SchoolHolidayResponse,
    summary="Update school holiday",
    dependencies=[Depends(require_permissions("academics.update"))],
)
async def update_school_holiday(
    holiday_id: UUID,
    data: SchoolHolidayUpdate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> SchoolHolidayResponse:
    """Update a school holiday."""
    service = TimetableService(db)
    holiday = await service.update_school_holiday(
        holiday_id=holiday_id,
        tenant_id=tenant.tenant_id,
        **data.model_dump(exclude_unset=True),
    )
    if not holiday:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School holiday not found",
        )
    return SchoolHolidayResponse.model_validate(holiday)


@router.delete(
    "/holidays/{holiday_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete school holiday",
    dependencies=[Depends(require_permissions("academics.delete"))],
)
async def delete_school_holiday(
    holiday_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> None:
    """Delete a school holiday."""
    service = TimetableService(db)
    deleted = await service.delete_school_holiday(holiday_id, tenant.tenant_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School holiday not found",
        )


# =========================
# Single Timetable Entry Endpoints
# NOTE: These must be at the end to avoid catching /periods and /holidays routes
# =========================


@router.get(
    "/{entry_id}",
    response_model=TimetableEntryResponse,
    summary="Get timetable entry",
    dependencies=[Depends(require_permissions("academics.read"))],
)
async def get_timetable_entry(
    entry_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> TimetableEntryResponse:
    """Get a single timetable entry by ID."""
    service = TimetableService(db)
    entry = await service.get_timetable_entry(tenant.tenant_id, entry_id)

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Timetable entry not found",
        )

    return _format_entry_response(entry)


@router.put(
    "/{entry_id}",
    response_model=TimetableEntryResponse,
    summary="Update timetable entry",
    dependencies=[Depends(require_permissions("academics.update"))],
)
async def update_timetable_entry(
    entry_id: UUID,
    data: TimetableEntryUpdate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> TimetableEntryResponse:
    """Update a timetable entry."""
    service = TimetableService(db)

    try:
        entry = await service.update_timetable_entry(
            entry_id=entry_id,
            tenant_id=tenant.tenant_id,
            **data.model_dump(exclude_unset=True),
        )

        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Timetable entry not found",
            )

        # Refresh to load relations
        entry = await service.get_timetable_entry(tenant.tenant_id, entry.id)
        return _format_entry_response(entry)
    except TimetableServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.delete(
    "/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete timetable entry",
    dependencies=[Depends(require_permissions("academics.delete"))],
)
async def delete_timetable_entry(
    entry_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> None:
    """Delete a timetable entry."""
    service = TimetableService(db)

    deleted = await service.delete_timetable_entry(tenant.tenant_id, entry_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Timetable entry not found",
        )
