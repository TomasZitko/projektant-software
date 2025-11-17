"""
FastAPI main application.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from app.config import settings
from app.core.logging import setup_logging
from app.api.v1.api import api_router
from app.services.cache import cache_service
from app.services.metrics import metrics_collector
from app.middleware.rate_limit import RateLimitMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    setup_logging()
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Debug mode: {settings.DEBUG}")
    logger.info(f"Database: {settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}")

    # Initialize Redis cache
    await cache_service.connect()

    # Reset metrics on startup
    metrics_collector.reset_stats()

    yield

    # Shutdown
    logger.info("Shutting down application")
    await cache_service.disconnect()


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-Powered Building Code Compliance Engine for Revit",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting middleware
app.add_middleware(RateLimitMiddleware, enabled=not settings.DEBUG)

# Include API router
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint."""
    return {
        "message": "Projektant Copilot API",
        "version": settings.APP_VERSION,
        "status": "operational",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "app_name": settings.APP_NAME,
            "version": settings.APP_VERSION,
        },
    )


@app.get("/metrics", tags=["Monitoring"])
async def get_metrics():
    """Get performance metrics for all endpoints."""
    return metrics_collector.get_all_stats()


@app.get("/metrics/errors", tags=["Monitoring"])
async def get_recent_errors():
    """Get recent error metrics."""
    return {"errors": metrics_collector.get_recent_errors(limit=20)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
