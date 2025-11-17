"""
Compliance checking endpoints.
"""
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.db.session import get_db
from app.services.cache import cache_service
from app.services.compliance_logger import ComplianceLogger
from app.services.metrics import RequestTimer

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

    Features:
    - Redis caching for fast repeated checks
    - PostgreSQL logging of all checks
    - Performance metrics tracking
    - <1 second response time target
    """
    with RequestTimer("compliance_check"):
        logger.info(f"Compliance check requested for {request.element_type}")

        # Step 1: Try to get cached result
        cache_key_data = {
            "element_type": request.element_type,
            "properties": request.properties.model_dump(),
            "context": request.context.model_dump() if request.context else None,
        }

        cached_result = await cache_service.get("compliance", cache_key_data)
        if cached_result:
            logger.info(f"Returning cached result for {request.element_type}")
            return ComplianceCheckResponse(**cached_result)

        # Step 2: Perform compliance check
        # TODO: Implement RAG-based compliance checking with Pinecone
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

        # Step 3: Build response
        from datetime import datetime

        is_compliant = len(violations) == 0

        response = ComplianceCheckResponse(
            compliant=is_compliant,
            violations=violations,
            recommendations=[
                f"Increase {request.element_type.lower()} spacing to meet minimum requirements"
            ]
            if violations
            else [],
            checked_at=datetime.utcnow().isoformat() + "Z",
        )

        # Step 4: Cache the result
        await cache_service.set("compliance", cache_key_data, response.model_dump())

        # Step 5: Log to database (async, non-blocking)
        try:
            await ComplianceLogger.log_check(
                db=db,
                request=request,
                violations=violations,
                is_compliant=is_compliant,
                element_id=None,  # Will come from plugin in future
                project_id=1,  # Default project for demo
            )
        except Exception as e:
            # Don't fail the request if logging fails
            logger.error(f"Failed to log compliance check: {e}")

        logger.info(
            f"Compliance check completed: {request.element_type} - "
            f"Compliant: {is_compliant}, Violations: {len(violations)}"
        )

        return response


@router.get("/rules")
async def list_rules():
    """List available compliance rules (placeholder)."""
    return {
        "total_rules": 0,
        "rules": [],
        "message": "RAG pipeline not yet configured. Run document ingestion first.",
    }
