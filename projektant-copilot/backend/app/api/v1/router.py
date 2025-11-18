"""
API Router

Main router that includes all API endpoint routers.

Author: Projektant Copilot Team
License: Commercial
"""

from fastapi import APIRouter
from .endpoints import health, compliance, bim_analysis, graph

api_router = APIRouter()

# Include endpoint routers
api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(compliance.router, prefix="/compliance", tags=["Compliance"])
api_router.include_router(bim_analysis.router, prefix="/bim", tags=["BIM Analysis"])
api_router.include_router(graph.router, prefix="/graph", tags=["Graph"])
