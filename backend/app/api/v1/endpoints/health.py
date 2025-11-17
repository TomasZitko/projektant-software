"""
Health check endpoints.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.db.session import get_db
from loguru import logger

router = APIRouter()


@router.get("/")
async def health_check():
    """Basic health check."""
    return {
        "status": "healthy",
        "message": "Service is operational",
    }


@router.get("/detailed")
async def detailed_health_check(db: AsyncSession = Depends(get_db)):
    """Detailed health check with database connectivity."""
    checks = {
        "api": "healthy",
        "database": "unknown",
    }

    # Check database connection
    try:
        result = await db.execute(text("SELECT 1"))
        if result:
            checks["database"] = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        checks["database"] = "unhealthy"

    overall_status = "healthy" if all(v == "healthy" for v in checks.values()) else "degraded"

    return {
        "status": overall_status,
        "checks": checks,
    }
