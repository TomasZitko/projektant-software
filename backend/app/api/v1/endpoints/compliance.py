"""
Compliance checking endpoints.
"""
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.db.session import get_db

router = APIRouter()


# Request/Response Models
class ElementProperties(BaseModel):
    """Building element properties."""
    width_mm: float = Field(..., description="Width in millimeters")
    height_mm: float | None = Field(None, description="Height in millimeters")
    length_mm: float | None = Field(None, description="Length in millimeters")
    function: str | None = Field(None, description="Element function")


class ElementContext(BaseModel):
    """Spatial and semantic context."""
    room_type: str | None = Field(None, description="Room type (corridor, office, etc.)")
    building_type: str | None = Field(None, description="Building type (residential, office, etc.)")
    occupancy: int | None = Field(None, description="Number of occupants")
    floor_level: int | None = Field(None, description="Floor level")


class ComplianceCheckRequest(BaseModel):
    """Request to check element compliance."""
    element_type: str = Field(..., description="Type of element (Wall, Door, etc.)")
    properties: ElementProperties
    context: ElementContext | None = None


class ComplianceViolation(BaseModel):
    """A compliance violation."""
    rule_id: str
    severity: str = Field(..., description="critical, warning, info")
    message: str
    required_value: float | None = None
    actual_value: float | None = None
    code_reference: str | None = None
    confidence_score: float = Field(..., ge=0.0, le=1.0)


class ComplianceCheckResponse(BaseModel):
    """Response from compliance check."""
    compliant: bool
    violations: List[ComplianceViolation]
    recommendations: List[str]
    checked_at: str


@router.post("/check", response_model=ComplianceCheckResponse)
async def check_compliance(
    request: ComplianceCheckRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Check building element compliance against Czech building codes.

    This is the main endpoint that the Revit plugin calls for real-time compliance checking.
    """
    logger.info(f"Compliance check requested for {request.element_type}")

    # TODO: Implement RAG-based compliance checking
    # For now, return a mock response based on hardcoded rules

    violations = []

    # Example: Check corridor width (ČSN 73 0802)
    if request.element_type.lower() in ["wall", "corridor"]:
        if request.context and request.context.room_type == "Corridor":
            min_width = 1200  # mm
            if request.context.occupancy and request.context.occupancy > 200:
                min_width = 1500

            actual_width = request.properties.width_mm

            if actual_width < min_width:
                violations.append(
                    ComplianceViolation(
                        rule_id="ČSN_73_0802_Sec_5.2.a",
                        severity="critical",
                        message=f"Corridor width ({actual_width}mm) is less than minimum {min_width}mm required by ČSN 73 0802",
                        required_value=min_width,
                        actual_value=actual_width,
                        code_reference="Section 5.2(a) - Escape Routes",
                        confidence_score=0.98,
                    )
                )

    from datetime import datetime

    return ComplianceCheckResponse(
        compliant=len(violations) == 0,
        violations=violations,
        recommendations=[
            f"Increase {request.element_type.lower()} spacing to meet minimum requirements"
        ]
        if violations
        else [],
        checked_at=datetime.utcnow().isoformat() + "Z",
    )


@router.get("/rules")
async def list_rules():
    """List available compliance rules (placeholder)."""
    return {
        "total_rules": 0,
        "rules": [],
        "message": "RAG pipeline not yet configured. Run document ingestion first.",
    }
