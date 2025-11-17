"""
Compliance checking endpoints.
"""
from typing import Dict, Any, List
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.db.session import get_db
from app.services.compliance_engine import compliance_engine
from app.services.vector_service import vector_service

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
    Uses RAG pipeline with Pinecone + OpenAI for intelligent compliance checking.
    """
    logger.info(f"Compliance check requested for {request.element_type}")

    try:
        # Convert Pydantic models to dicts
        properties = request.properties.model_dump()
        context = request.context.model_dump() if request.context else {}

        # Run compliance check through RAG pipeline
        result = await compliance_engine.check_compliance(
            element_type=request.element_type,
            properties=properties,
            context=context
        )

        # Convert violations to Pydantic models
        violations = [
            ComplianceViolation(
                rule_id=v["rule_id"],
                severity=v["severity"],
                message=v["message"],
                required_value=v.get("required_value"),
                actual_value=v.get("actual_value"),
                code_reference=v.get("csn_reference"),
                confidence_score=v["confidence_score"],
            )
            for v in result["violations"]
        ]

        logger.info(
            f"✓ Compliance check complete: {len(violations)} violations, "
            f"{result['execution_time_ms']:.1f}ms"
        )

        return ComplianceCheckResponse(
            compliant=result["compliant"],
            violations=violations,
            recommendations=result["recommendations"],
            checked_at=datetime.utcnow().isoformat() + "Z",
        )

    except Exception as e:
        logger.error(f"Compliance check failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Compliance check failed: {str(e)}"
        )


@router.get("/rules")
async def list_rules():
    """Get information about loaded compliance rules."""
    try:
        stats = await vector_service.get_stats()

        return {
            "total_rules": stats.get("total_vectors", 0),
            "index_name": vector_service.index_name,
            "dimension": stats.get("dimension", 1536),
            "namespaces": stats.get("namespaces", {}),
            "queries_executed": stats.get("queries_executed", 0),
            "message": "RAG pipeline active" if stats.get("total_vectors", 0) > 0 else "No rules loaded. Run document ingestion first.",
        }
    except Exception as e:
        logger.error(f"Failed to get rules stats: {e}")
        return {
            "total_rules": 0,
            "message": f"Error accessing vector database: {str(e)}",
        }


@router.get("/stats")
async def get_stats():
    """Get compliance engine statistics."""
    try:
        engine_stats = compliance_engine.get_stats()
        vector_stats = await vector_service.get_stats()

        return {
            "compliance_engine": engine_stats,
            "vector_database": vector_stats,
        }
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
