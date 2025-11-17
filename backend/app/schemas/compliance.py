"""Compliance schemas."""
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field


class ComplianceRuleBase(BaseModel):
    """Base compliance rule schema."""

    rule_id: str = Field(..., description="Unique rule identifier (e.g., ČSN_73_0802_Sec_5.2.a)")
    rule_type: str = Field(..., description="min_width, max_height, fire_rating, etc.")
    geometry_type: str = Field(..., description="corridor, wall, door, window, etc.")
    building_types: Optional[List[str]] = Field(None, description='["residential", "office"]')
    title: str
    description: str
    code_reference: str = Field(..., description="Section reference")
    value_mm: Optional[float] = Field(None, description="Numeric requirement in mm")
    value_text: Optional[str] = Field(None, description="Text requirement")
    severity: str = Field(default="warning", description="critical, warning, info")
    source_document: Optional[str] = None
    page_number: Optional[int] = None
    language: str = Field(default="cs")
    version: Optional[str] = None
    is_active: bool = True


class ComplianceRuleCreate(ComplianceRuleBase):
    """Schema for creating a compliance rule."""

    pass


class ComplianceRuleUpdate(BaseModel):
    """Schema for updating a compliance rule."""

    title: Optional[str] = None
    description: Optional[str] = None
    value_mm: Optional[float] = None
    value_text: Optional[str] = None
    severity: Optional[str] = None
    is_active: Optional[bool] = None


class ComplianceRuleResponse(ComplianceRuleBase):
    """Schema for compliance rule response."""

    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ElementProperties(BaseModel):
    """Building element properties."""

    width_mm: float = Field(..., description="Width in millimeters")
    height_mm: Optional[float] = Field(None, description="Height in millimeters")
    length_mm: Optional[float] = Field(None, description="Length in millimeters")
    area_sqm: Optional[float] = Field(None, description="Area in square meters")
    function: Optional[str] = Field(None, description="Element function")
    material: Optional[str] = Field(None, description="Material type")


class ElementContext(BaseModel):
    """Spatial and semantic context."""

    room_type: Optional[str] = Field(None, description="Room type (corridor, office, etc.)")
    building_type: Optional[str] = Field(None, description="Building type (residential, office, etc.)")
    occupancy: Optional[int] = Field(None, description="Number of occupants")
    floor_level: Optional[int] = Field(None, description="Floor level")
    adjacent_spaces: Optional[List[str]] = Field(None, description="Adjacent room types")


class ComplianceCheckRequest(BaseModel):
    """Request to check element compliance."""

    project_id: Optional[int] = Field(None, description="Project ID if available")
    element_id: str = Field(..., description="Unique element ID from Revit")
    element_type: str = Field(..., description="Type of element (Wall, Door, etc.)")
    properties: ElementProperties
    context: Optional[ElementContext] = None


class ComplianceViolation(BaseModel):
    """A compliance violation."""

    rule_id: str
    severity: str = Field(..., description="critical, warning, info")
    message: str
    required_value: Optional[float] = None
    actual_value: Optional[float] = None
    code_reference: Optional[str] = None
    confidence_score: float = Field(..., ge=0.0, le=1.0)


class ComplianceCheckResponse(BaseModel):
    """Response from compliance check."""

    compliant: bool
    violations: List[ComplianceViolation]
    recommendations: List[str]
    checked_at: str
    rules_checked: Optional[int] = Field(None, description="Number of rules evaluated")


class ComplianceCheckHistoryResponse(BaseModel):
    """Historical compliance check record."""

    id: int
    project_id: int
    element_id: str
    element_type: str
    is_compliant: bool
    violations_count: int
    checked_at: datetime

    model_config = {"from_attributes": True}
