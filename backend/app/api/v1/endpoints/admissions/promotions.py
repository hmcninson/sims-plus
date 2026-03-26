"""
SIMS Plus - Class Promotion Endpoints

End-of-year class promotion management. This is the primary tool
for Ghanaian academic year transitions.

Workflow: create batch -> generate preview -> review/edit entries -> execute.
"""

import math
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response

from app.api.deps import (
    DatabaseSession,
    SchoolCtx,
    ValidatedUser,
    require_permissions,
)
from app.schemas.admissions import (
    BulkPromotionEntryUpdate,
    BulkPromotionUpdateResponse,
    ClassPromotionCreate,
    ClassPromotionEntryListResponse,
    ClassPromotionEntryResponse,
    ClassPromotionListResponse,
    ClassPromotionResponse,
    PromotionEntryUpdate,
)
from app.schemas.student import (
    PromotionRuleCreate,
    PromotionRuleUpdate,
    PromotionRuleResponse,
    PromotionRuleEvaluationResult,
)
from app.services.admissions import ClassPromotionError, ClassPromotionService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/promotions")


def _handle_error(e: ClassPromotionError) -> HTTPException:
    """Map service errors to HTTP responses."""
    status_map = {
        "NOT_FOUND": 404,
        "ENTRY_NOT_FOUND": 404,
        "YEAR_NOT_FOUND": 404,
        "RULE_NOT_FOUND": 404,
        "NOT_GRADUATED": 422,
        "BATCH_EXISTS": 409,
        "RULE_EXISTS": 409,
        "SAME_YEAR": 422,
        "INVALID_STATUS": 422,
        "BATCH_NOT_PREVIEW": 422,
        "INVALID_ACTION": 422,
        "NO_CLASSES": 422,
    }
    return HTTPException(
        status_code=status_map.get(e.code, 400),
        detail=e.message,
    )


@router.post(
    "",
    response_model=ClassPromotionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create promotion batch",
    dependencies=[Depends(require_permissions("admissions.manage"))],
)
async def create_batch(
    data: ClassPromotionCreate,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ClassPromotionResponse:
    """
    Create a new class promotion batch in draft status.
    Validates both academic years exist and no duplicate batch exists.
    """
    service = ClassPromotionService(db)
    try:
        # Unpack Pydantic model fields into individual kwargs
        return await service.create_batch(
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
            source_academic_year_id=data.source_academic_year_id,
            target_academic_year_id=data.target_academic_year_id,
            name=data.name,
        )
    except ClassPromotionError as e:
        raise _handle_error(e)


@router.get(
    "",
    response_model=ClassPromotionListResponse,
    summary="List promotion batches",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def list_batches(
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ClassPromotionListResponse:
    """List promotion batches for the school."""
    service = ClassPromotionService(db)
    # list_batches returns (items, total) tuple
    items, total = await service.list_batches(
        tenant_id=UUID(user["tenant_id"]),
        school_id=school.school_id,
        page=page,
        page_size=page_size,
    )
    return ClassPromotionListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get(
    "/{promotion_id}",
    response_model=ClassPromotionResponse,
    summary="Get promotion batch details",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def get_batch(
    promotion_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ClassPromotionResponse:
    """Get batch details with counts."""
    service = ClassPromotionService(db)
    try:
        return await service.get_batch(
            tenant_id=UUID(user["tenant_id"]),
            promotion_id=promotion_id,
        )
    except ClassPromotionError as e:
        raise _handle_error(e)


@router.post(
    "/{promotion_id}/preview",
    response_model=ClassPromotionResponse,
    summary="Generate promotion preview",
    dependencies=[Depends(require_permissions("admissions.manage"))],
)
async def generate_preview(
    promotion_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ClassPromotionResponse:
    """
    Generate ClassPromotionEntry records for all active students.
    Default: promote to next class; terminal class students: graduate.
    Sets batch status to 'preview'.
    """
    service = ClassPromotionService(db)
    try:
        return await service.generate_preview(
            tenant_id=UUID(user["tenant_id"]),
            promotion_id=promotion_id,
        )
    except ClassPromotionError as e:
        raise _handle_error(e)


@router.get(
    "/{promotion_id}/entries",
    response_model=ClassPromotionEntryListResponse,
    summary="List promotion entries",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def list_entries(
    promotion_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
    source_class_id: UUID | None = Query(None),
    action: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> ClassPromotionEntryListResponse:
    """List entries for a batch with optional filters."""
    service = ClassPromotionService(db)
    # get_entries returns (items, total) tuple
    items, total = await service.get_entries(
        tenant_id=UUID(user["tenant_id"]),
        promotion_id=promotion_id,
        source_class_id=source_class_id,
        action=action,
        page=page,
        page_size=page_size,
    )
    return ClassPromotionEntryListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.put(
    "/entries/{entry_id}",
    response_model=ClassPromotionEntryResponse,
    summary="Update promotion entry",
    dependencies=[Depends(require_permissions("admissions.manage"))],
)
async def update_entry(
    entry_id: UUID,
    data: PromotionEntryUpdate,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ClassPromotionEntryResponse:
    """Update a single student's promotion action."""
    service = ClassPromotionService(db)
    try:
        # Unpack Pydantic model fields into individual kwargs
        return await service.update_entry(
            tenant_id=UUID(user["tenant_id"]),
            entry_id=entry_id,
            action=data.action,
            target_class_id=data.target_class_id,
            target_section_id=data.target_section_id,
            reason=data.reason,
        )
    except ClassPromotionError as e:
        raise _handle_error(e)


@router.put(
    "/{promotion_id}/entries/bulk",
    response_model=BulkPromotionUpdateResponse,
    summary="Bulk update promotion entries",
    dependencies=[Depends(require_permissions("admissions.manage"))],
)
async def bulk_update_entries(
    promotion_id: UUID,
    data: BulkPromotionEntryUpdate,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> BulkPromotionUpdateResponse:
    """Bulk update multiple entries' actions."""
    service = ClassPromotionService(db)
    try:
        # Convert Pydantic models to dicts for the service
        updates = [u.model_dump() for u in data.updates]
        result = await service.bulk_update_entries(
            tenant_id=UUID(user["tenant_id"]),
            promotion_id=promotion_id,
            updates=updates,
        )
        return BulkPromotionUpdateResponse(
            succeeded=result["succeeded"],
            failed=result["failed"],
        )
    except ClassPromotionError as e:
        raise _handle_error(e)


@router.post(
    "/{promotion_id}/execute",
    response_model=ClassPromotionResponse,
    summary="Execute promotion batch",
    dependencies=[Depends(require_permissions("admissions.manage"))],
)
async def execute_batch(
    promotion_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ClassPromotionResponse:
    """
    Execute the promotion batch. Updates student class assignments.
    Each entry processed in its own savepoint (partial success).
    Status transitions: preview -> in_progress -> completed/failed.
    """
    service = ClassPromotionService(db)
    try:
        return await service.execute_batch(
            tenant_id=UUID(user["tenant_id"]),
            promotion_id=promotion_id,
            executed_by=UUID(user["user_id"]),
        )
    except ClassPromotionError as e:
        raise _handle_error(e)


# ═══════════════════════════════════════════════════════════════
# Promotion Rules CRUD
# ═══════════════════════════════════════════════════════════════


@router.post(
    "/rules",
    response_model=PromotionRuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create promotion rule",
    dependencies=[Depends(require_permissions("admissions.manage"))],
)
async def create_promotion_rule(
    data: PromotionRuleCreate,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> PromotionRuleResponse:
    """Create a configurable promotion rule for a school/academic year.

    Rules define minimum thresholds (average score, attendance, core
    subject passes) that a student must meet to be auto-promoted.
    When class_id is NULL, the rule is the school-wide default.
    """
    service = ClassPromotionService(db)
    try:
        from decimal import Decimal

        rule = await service.create_promotion_rule(
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
            academic_year_id=data.academic_year_id,
            class_id=data.class_id,
            min_average=(
                Decimal(str(data.min_average))
                if data.min_average is not None
                else None
            ),
            min_attendance_pct=(
                Decimal(str(data.min_attendance_pct))
                if data.min_attendance_pct is not None
                else None
            ),
            core_subject_pass_count=data.core_subject_pass_count,
            pass_mark=(
                Decimal(str(data.pass_mark))
                if data.pass_mark is not None
                else Decimal("50.00")
            ),
            auto_apply=data.auto_apply,
        )
        return PromotionRuleResponse(
            id=rule.id,
            school_id=rule.school_id,
            academic_year_id=rule.academic_year_id,
            class_id=rule.class_id,
            min_average=float(rule.min_average) if rule.min_average else None,
            min_attendance_pct=(
                float(rule.min_attendance_pct)
                if rule.min_attendance_pct
                else None
            ),
            core_subject_pass_count=rule.core_subject_pass_count,
            pass_mark=float(rule.pass_mark) if rule.pass_mark else None,
            auto_apply=rule.auto_apply,
            is_active=rule.is_active,
            created_at=str(rule.created_at),
        )
    except ClassPromotionError as e:
        raise _handle_error(e)


@router.get(
    "/rules",
    response_model=list[PromotionRuleResponse],
    summary="List promotion rules",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def list_promotion_rules(
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
    academic_year_id: UUID | None = Query(None),
) -> list[PromotionRuleResponse]:
    """List promotion rules for the school, optionally filtered by academic year."""
    service = ClassPromotionService(db)
    rules = await service.list_promotion_rules(
        tenant_id=UUID(user["tenant_id"]),
        school_id=school.school_id,
        academic_year_id=academic_year_id,
    )
    return [
        PromotionRuleResponse(
            id=r.id,
            school_id=r.school_id,
            academic_year_id=r.academic_year_id,
            class_id=r.class_id,
            min_average=float(r.min_average) if r.min_average else None,
            min_attendance_pct=(
                float(r.min_attendance_pct) if r.min_attendance_pct else None
            ),
            core_subject_pass_count=r.core_subject_pass_count,
            pass_mark=float(r.pass_mark) if r.pass_mark else None,
            auto_apply=r.auto_apply,
            is_active=r.is_active,
            created_at=str(r.created_at),
            class_name=r.class_.name if r.class_ else None,
            academic_year_name=(
                r.academic_year.name if r.academic_year else None
            ),
        )
        for r in rules
    ]


@router.put(
    "/rules/{rule_id}",
    response_model=PromotionRuleResponse,
    summary="Update promotion rule",
    dependencies=[Depends(require_permissions("admissions.manage"))],
)
async def update_promotion_rule(
    rule_id: UUID,
    data: PromotionRuleUpdate,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> PromotionRuleResponse:
    """Update fields on an existing promotion rule."""
    service = ClassPromotionService(db)
    try:
        # Only pass fields that were explicitly set (not None from schema defaults)
        update_fields = data.model_dump(exclude_unset=True)
        rule = await service.update_promotion_rule(
            tenant_id=UUID(user["tenant_id"]),
            rule_id=rule_id,
            **update_fields,
        )
        return PromotionRuleResponse(
            id=rule.id,
            school_id=rule.school_id,
            academic_year_id=rule.academic_year_id,
            class_id=rule.class_id,
            min_average=float(rule.min_average) if rule.min_average else None,
            min_attendance_pct=(
                float(rule.min_attendance_pct)
                if rule.min_attendance_pct
                else None
            ),
            core_subject_pass_count=rule.core_subject_pass_count,
            pass_mark=float(rule.pass_mark) if rule.pass_mark else None,
            auto_apply=rule.auto_apply,
            is_active=rule.is_active,
            created_at=str(rule.created_at),
        )
    except ClassPromotionError as e:
        raise _handle_error(e)


@router.delete(
    "/rules/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete promotion rule",
    dependencies=[Depends(require_permissions("admissions.manage"))],
)
async def delete_promotion_rule(
    rule_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> None:
    """Soft-delete a promotion rule."""
    service = ClassPromotionService(db)
    try:
        await service.delete_promotion_rule(
            tenant_id=UUID(user["tenant_id"]),
            rule_id=rule_id,
        )
    except ClassPromotionError as e:
        raise _handle_error(e)


# ═══════════════════════════════════════════════════════════════
# Graduation Certificate
# ═══════════════════════════════════════════════════════════════


@router.get(
    "/graduation-certificate/{student_id}",
    summary="Generate graduation certificate PDF",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def get_graduation_certificate(
    student_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> Response:
    """Generate and download a graduation certificate as PDF.

    The student must have status='graduated'.
    """
    service = ClassPromotionService(db)
    try:
        pdf_bytes = await service.generate_graduation_certificate(
            tenant_id=UUID(user["tenant_id"]),
            student_id=student_id,
        )
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="graduation_certificate_{student_id}.pdf"'
                )
            },
        )
    except ClassPromotionError as e:
        raise _handle_error(e)
