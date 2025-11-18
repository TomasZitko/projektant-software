"""
Compliance Check Endpoints

API endpoints for building code compliance checking.

Author: Projektant Copilot Team
License: Commercial
"""

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class ComplianceCheckRequest(BaseModel):
    """Request model for compliance check."""
    element_id: str
    element_type: str
    project_id: str
    namespace: str = "csn_codes"


class ViolationResponse(BaseModel):
    """Response model for a single violation."""
    violation_id: str
    element_id: str
    severity: str
    code_reference: str
    description: str
    current_value: Optional[str]
    required_value: Optional[str]
    recommendation: str
    confidence: float


class ComplianceCheckResponse(BaseModel):
    """Response model for compliance check results."""
    check_id: str
    element_id: str
    element_type: str
    compliant: bool
    violations: List[ViolationResponse]
    confidence: float
    rules_applied: List[str]


@router.post("/check", response_model=ComplianceCheckResponse)
async def check_compliance(
    request: Request,
    check_request: ComplianceCheckRequest
):
    """
    Perform compliance check on a BIM element.

    This is the MAIN endpoint for compliance checking.
    Called by the Revit plugin to check elements in real-time.
    """
    logger.info(f"Compliance check requested for {check_request.element_type} {check_request.element_id}")

    compliance_engine = request.app.state.compliance_engine

    if not compliance_engine:
        raise HTTPException(status_code=503, detail="Compliance engine not available")

    try:
        # Perform compliance check
        result = await compliance_engine.check_element(
            element_id=check_request.element_id,
            element_type=check_request.element_type,
            project_id=check_request.project_id,
            namespace=check_request.namespace
        )

        # Convert to response format
        violations = [
            ViolationResponse(
                violation_id=v.violation_id,
                element_id=v.element_id,
                severity=v.severity.value,
                code_reference=v.code_reference,
                description=v.description,
                current_value=v.current_value,
                required_value=v.required_value,
                recommendation=v.recommendation,
                confidence=v.confidence
            )
            for v in result.violations
        ]

        return ComplianceCheckResponse(
            check_id=result.check_id,
            element_id=result.element_id,
            element_type=result.element_type,
            compliant=result.compliant,
            violations=violations,
            confidence=result.confidence,
            rules_applied=result.rules_applied
        )

    except Exception as e:
        logger.error(f"Compliance check failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Compliance check failed: {str(e)}")


@router.get("/violations/{element_id}")
async def get_element_violations(
    request: Request,
    element_id: str
):
    """Get all violations for a specific element."""
    # In production, would query database for stored violations
    return {
        "element_id": element_id,
        "violations": []
    }


@router.get("/summary/{project_id}")
async def get_project_compliance_summary(
    request: Request,
    project_id: str
):
    """
    Get compliance summary for entire project.

    Returns aggregate statistics:
    - Total elements checked
    - Total violations
    - Breakdown by severity
    - Most common violations
    """
    # In production, would query database for project compliance history
    return {
        "project_id": project_id,
        "total_checks": 0,
        "total_violations": 0,
        "critical_violations": 0,
        "high_violations": 0,
        "medium_violations": 0,
        "low_violations": 0,
        "compliance_percentage": 100.0
    }
