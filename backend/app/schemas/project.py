"""Project schemas."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ProjectBase(BaseModel):
    """Base project schema."""

    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    revit_version: Optional[str] = None
    building_type: Optional[str] = Field(
        None, description="residential, office, hospital, school, etc."
    )
    location: Optional[str] = None
    total_area_sqm: Optional[int] = Field(None, gt=0)
    floor_count: Optional[int] = Field(None, gt=0)


class ProjectCreate(ProjectBase):
    """Schema for creating a project."""

    pass


class ProjectUpdate(BaseModel):
    """Schema for updating a project."""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    revit_version: Optional[str] = None
    building_type: Optional[str] = None
    location: Optional[str] = None
    total_area_sqm: Optional[int] = Field(None, gt=0)
    floor_count: Optional[int] = Field(None, gt=0)


class ProjectResponse(ProjectBase):
    """Schema for project response."""

    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    """Schema for project list response."""

    total: int
    projects: list[ProjectResponse]
