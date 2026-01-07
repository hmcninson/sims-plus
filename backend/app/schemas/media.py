"""
SIMS Plus - Media Schemas

Pydantic schemas for file upload responses.
"""

from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
    )


class FileUploadResponse(BaseSchema):
    """Response schema for file uploads."""

    url: str
    key: str
    filename: str
    content_type: str
    size: int
