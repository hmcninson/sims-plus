"""
Pydantic schemas for custom role endpoints.

Custom roles allow tenant admins to create fine-grained permission
sets that are subsets of a predefined base role.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CustomRoleCreate(BaseModel):
    """Create a new custom role."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=2, max_length=100)
    base_role: str = Field(
        ..., description="Parent role that defines the permission ceiling"
    )
    permissions: list[str] = Field(
        ..., min_length=1, description="Permission strings to grant"
    )
    description: str | None = Field(
        None, max_length=500, description="Optional description"
    )


class CustomRoleUpdate(BaseModel):
    """Update an existing custom role. All fields optional."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(None, min_length=2, max_length=100)
    permissions: list[str] | None = Field(
        None, min_length=1, description="New permission set"
    )
    description: str | None = Field(None, max_length=500)


class CustomRoleResponse(BaseModel):
    """Single custom role response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    description: str | None
    base_role: str
    permissions: list[str]
    is_system: bool
    user_count: int = 0
    created_at: datetime
    updated_at: datetime


class CustomRoleListResponse(BaseModel):
    """List of custom roles."""

    roles: list[CustomRoleResponse]


class CustomRoleAssign(BaseModel):
    """Assign or clear a custom role on a user."""

    custom_role_id: UUID | None = Field(
        None,
        description="Custom role ID to assign, or null to clear",
    )


# ------------------------------------------------------------------
# Permissions catalog schemas
# ------------------------------------------------------------------


class PermissionItem(BaseModel):
    """Single permission entry in the catalog."""

    key: str
    label: str
    description: str


class PermissionModule(BaseModel):
    """A group of permissions organized by module."""

    module: str
    permissions: list[PermissionItem]


class PermissionsCatalogResponse(BaseModel):
    """Full permissions catalog grouped by module."""

    modules: list[PermissionModule]
