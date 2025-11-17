"""
API v1 router aggregation.
"""
from fastapi import APIRouter
from app.api.v1.endpoints import health, compliance

api_router = APIRouter()

# Include endpoint routers
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(compliance.router, prefix="/compliance", tags=["compliance"])
