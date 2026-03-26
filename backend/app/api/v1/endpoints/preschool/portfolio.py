"""
SIMS Plus - Preschool Portfolio Endpoints

API routes for learning stories and student timeline.
"""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.services.preschool import PreschoolService, PreschoolServiceError
from app.schemas.preschool import (
    LearningStoryCreate,
    LearningStoryUpdate,
    LearningStoryResponse,
    TimelineEntry,
    convert_uuid,
)

router = APIRouter()


# =========================
# Learning Stories
# =========================


@router.get(
    "/learning-stories",
    response_model=list[LearningStoryResponse],
    summary="List learning stories",
    dependencies=[Depends(require_permissions("preschool.read"))],
)
async def list_learning_stories(
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
    student_id: UUID | None = Query(None),
    term_id: UUID | None = Query(None),
    shared_only: bool = Query(False),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, le=100),
):
    """List learning stories with optional filters."""
    service = PreschoolService(db)
    return await service.list_learning_stories(
        convert_uuid(tenant.tenant_id),
        student_id=student_id,
        term_id=term_id,
        shared_only=shared_only,
        skip=skip,
        limit=limit,
    )


@router.post(
    "/learning-stories",
    response_model=LearningStoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create learning story",
    dependencies=[Depends(require_permissions("preschool.create"))],
)
async def create_learning_story(
    data: LearningStoryCreate,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Create a new learning story (portfolio entry)."""
    service = PreschoolService(db)
    try:
        return await service.create_learning_story(
            convert_uuid(tenant.tenant_id),
            data,
            convert_uuid(current_user["user_id"]),
        )
    except PreschoolServiceError as e:
        if e.code == "not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get(
    "/learning-stories/{story_id}",
    response_model=LearningStoryResponse,
    summary="Get learning story",
    dependencies=[Depends(require_permissions("preschool.read"))],
)
async def get_learning_story(
    story_id: UUID,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Get a learning story by ID."""
    service = PreschoolService(db)
    try:
        return await service.get_learning_story(
            convert_uuid(tenant.tenant_id), story_id
        )
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.put(
    "/learning-stories/{story_id}",
    response_model=LearningStoryResponse,
    summary="Update learning story",
    dependencies=[Depends(require_permissions("preschool.update"))],
)
async def update_learning_story(
    story_id: UUID,
    data: LearningStoryUpdate,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Update a learning story."""
    service = PreschoolService(db)
    try:
        return await service.update_learning_story(
            convert_uuid(tenant.tenant_id), story_id, data
        )
    except PreschoolServiceError as e:
        if e.code == "not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.delete(
    "/learning-stories/{story_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete learning story",
    dependencies=[Depends(require_permissions("preschool.delete"))],
)
async def delete_learning_story(
    story_id: UUID,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Soft-delete a learning story."""
    service = PreschoolService(db)
    try:
        await service.delete_learning_story(
            convert_uuid(tenant.tenant_id), story_id
        )
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


# =========================
# Student Timeline
# =========================


@router.get(
    "/students/{student_id}/timeline",
    response_model=list[TimelineEntry],
    summary="Get student timeline",
    dependencies=[Depends(require_permissions("preschool.read"))],
)
async def get_student_timeline(
    student_id: UUID,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    limit: int = Query(100, le=500),
):
    """Get aggregated timeline of a student's preschool journey.

    Combines assessments, observations, incidents, and learning stories
    into a unified timeline sorted by date DESC.
    """
    service = PreschoolService(db)
    try:
        return await service.get_student_timeline(
            convert_uuid(tenant.tenant_id),
            student_id,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
        )
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
