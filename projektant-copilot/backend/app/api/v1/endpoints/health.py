"""
Health Check Endpoints

System health and status monitoring.

Author: Projektant Copilot Team
License: Commercial
"""

from fastapi import APIRouter, Request
from typing import Dict, Any

router = APIRouter()


@router.get("/status")
async def get_status(request: Request) -> Dict[str, Any]:
    """Get detailed system status."""
    return {
        "status": "operational",
        "services": {
            "neo4j": bool(request.app.state.neo4j),
            "vector_store": bool(request.app.state.vector_store),
            "embedding_service": bool(request.app.state.embedding_service),
            "compliance_engine": bool(request.app.state.compliance_engine),
        }
    }


@router.get("/ready")
async def readiness_check(request: Request) -> Dict[str, bool]:
    """Kubernetes readiness probe endpoint."""
    return {
        "ready": all([
            request.app.state.neo4j,
            request.app.state.vector_store,
            request.app.state.compliance_engine,
        ])
    }


@router.get("/live")
async def liveness_check() -> Dict[str, bool]:
    """Kubernetes liveness probe endpoint."""
    return {"alive": True}
