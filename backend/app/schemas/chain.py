"""
SIMS Plus - School Chain Schemas

Pydantic schemas for chain management: schools CRUD, user-school mappings,
accessible schools for switcher, chain dashboard, and chain user listing.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Valid roles that can be assigned at the school level
VALID_SCHOOL_ROLES = Literal[
    "school_admin",
    "academic_head",
    "finance_officer",
    "hr_officer",
    "teacher",
    "house_parent",
    "transport_officer",
]


# =========================
# School in Chain
# =========================


class ChainSchoolCreate(BaseModel):
    """Request to add a new school to a chain tenant."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., min_length=1, max_length=255)
    code: str = Field(
        ...,
        min_length=1,
        max_length=20,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="Short unique code (letters, numbers, hyphens, underscores)",
    )
    address: Optional[str] = Field(None, max_length=500)
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=255)
    student_id_prefix: Optional[str] = Field(
        None,
        max_length=10,
        description="Prefix for student IDs, e.g., 'PS' for Presec",
    )


class ChainSchoolUpdate(BaseModel):
    """Request to update a school in a chain."""

    model_config = ConfigDict(from_attributes=True)

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    address: Optional[str] = Field(None, max_length=500)
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=255)
    student_id_prefix: Optional[str] = Field(None, max_length=10)


class ChainSchoolResponse(BaseModel):
    """Response for a school in a chain."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    name: str
    code: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    logo_url: Optional[str] = None
    student_id_prefix: Optional[str] = None
    student_count: int = 0
    staff_count: int = 0
    created_at: datetime
    updated_at: datetime


class ChainSchoolListResponse(BaseModel):
    """Paginated list of schools in a chain."""

    items: list[ChainSchoolResponse]
    total: int


# =========================
# User-School Mapping
# =========================


class UserSchoolAssign(BaseModel):
    """Request to grant a user access to a school."""

    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    school_id: UUID
    role_at_school: VALID_SCHOOL_ROLES = Field(
        ...,
        description="Role the user has at this school",
    )
    is_primary: bool = False


class UserSchoolResponse(BaseModel):
    """Response for a user-school mapping."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    user_id: UUID
    school_id: UUID
    role_at_school: str
    is_primary: bool
    is_active: bool
    school_name: Optional[str] = None
    user_email: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class UserSchoolListResponse(BaseModel):
    """List of user-school mappings."""

    items: list[UserSchoolResponse]
    total: int


# =========================
# Chain Overview
# =========================


class ChainOverview(BaseModel):
    """High-level overview of a school chain."""

    tenant_id: UUID
    tenant_name: str
    total_schools: int
    total_students: int
    total_staff: int
    schools: list[ChainSchoolResponse]


# =========================
# Accessible Schools (Switcher)
# =========================


class AccessibleSchoolResponse(BaseModel):
    """Lightweight school info for the school switcher dropdown."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    code: Optional[str] = None
    logo_url: Optional[str] = None


# =========================
# Chain Dashboard
# =========================


class ChainSchoolMetrics(BaseModel):
    """Per-school metrics for the chain dashboard."""

    model_config = ConfigDict(from_attributes=True)

    school_id: UUID
    school_name: str
    school_code: Optional[str] = None
    logo_url: Optional[str] = None
    total_students: int = 0
    total_staff: int = 0
    attendance_rate: float = 0.0
    total_billed: float = 0.0
    total_collected: float = 0.0
    collection_rate: float = 0.0
    outstanding: float = 0.0


class ChainDashboardResponse(BaseModel):
    """Chain-level dashboard with aggregated metrics."""

    total_schools: int
    total_students: int
    total_staff: int
    overall_attendance_rate: float = 0.0
    total_revenue: float = 0.0
    total_outstanding: float = 0.0
    schools: list[ChainSchoolMetrics]


# =========================
# Chain Users
# =========================


class ChainUserSchoolAccess(BaseModel):
    """User's access to a specific school."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    school_id: UUID
    school_name: str
    school_code: Optional[str] = None
    role_at_school: str
    is_primary: bool


class ChainUserResponse(BaseModel):
    """User with their school assignments."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    first_name: str
    last_name: str
    role: str
    status: str
    school_accesses: list[ChainUserSchoolAccess]
    created_at: datetime
    updated_at: datetime


class ChainUserListResponse(BaseModel):
    """Paginated list of chain users."""

    items: list[ChainUserResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
