"""
Projektant Copilot - Main FastAPI Application

The most advanced AI-powered BIM automation system ever created.

This application provides:
- Real-time compliance checking against Czech building codes (ČSN)
- Intelligent building analysis using graph database and ML
- Automated documentation generation
- WebSocket support for real-time updates to Revit plugin

Author: Projektant Copilot Team
License: Commercial
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
import logging
from contextlib import asynccontextmanager
from typing import Dict, Set

from .core.config import settings
from .api.v1.router import api_router
from .services.graph.neo4j_service import Neo4jService
from .services.rag.vector_store import VectorStore
from .services.rag.embedding_service import EmbeddingService
from .services.compliance.engine import ComplianceEngine

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global service instances
neo4j_service: Neo4jService = None
vector_store: VectorStore = None
embedding_service: EmbeddingService = None
compliance_engine: ComplianceEngine = None

# WebSocket connection manager
class ConnectionManager:
    """Manage WebSocket connections for real-time updates."""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, client_id: str, websocket: WebSocket):
        """Accept new WebSocket connection."""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"Client {client_id} connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, client_id: str):
        """Remove WebSocket connection."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(f"Client {client_id} disconnected. Total connections: {len(self.active_connections)}")

    async def send_personal_message(self, message: dict, client_id: str):
        """Send message to specific client."""
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_json(message)
            except Exception as e:
                logger.error(f"Failed to send message to {client_id}: {e}")
                self.disconnect(client_id)

    async def broadcast(self, message: dict, exclude_client: str = None):
        """Broadcast message to all connected clients."""
        for client_id, connection in self.active_connections.items():
            if client_id != exclude_client:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Failed to broadcast to {client_id}: {e}")
                    self.disconnect(client_id)


manager = ConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Handles startup and shutdown of services.
    """
    # Startup
    logger.info("🚀 Starting Projektant Copilot...")

    global neo4j_service, vector_store, embedding_service, compliance_engine

    try:
        # Initialize Neo4j
        logger.info("Connecting to Neo4j...")
        neo4j_service = Neo4jService(
            uri=settings.NEO4J_URI,
            user=settings.NEO4J_USER,
            password=settings.NEO4J_PASSWORD
        )
        await neo4j_service.connect()
        await neo4j_service.initialize_schema()
        logger.info("✓ Neo4j connected and initialized")

        # Initialize Vector Store
        logger.info("Connecting to Pinecone...")
        vector_store = VectorStore(
            api_key=settings.PINECONE_API_KEY,
            environment=settings.PINECONE_ENVIRONMENT,
            index_name=settings.PINECONE_INDEX_NAME,
            dimension=settings.OPENAI_EMBEDDING_DIMENSION
        )
        await vector_store.initialize()
        logger.info("✓ Pinecone connected and initialized")

        # Initialize Embedding Service
        logger.info("Initializing Embedding Service...")
        embedding_service = EmbeddingService(
            api_key=settings.OPENAI_API_KEY,
            model=settings.OPENAI_EMBEDDING_MODEL
        )
        logger.info("✓ Embedding Service ready")

        # Initialize Compliance Engine
        logger.info("Initializing Compliance Engine...")
        compliance_engine = ComplianceEngine(
            neo4j_service=neo4j_service,
            vector_store=vector_store,
            embedding_service=embedding_service,
            anthropic_api_key=settings.ANTHROPIC_API_KEY
        )
        logger.info("✓ Compliance Engine ready")

        logger.info("✅ All services initialized successfully!")

    except Exception as e:
        logger.error(f"❌ Failed to initialize services: {e}")
        raise

    # Store services in app state
    app.state.neo4j = neo4j_service
    app.state.vector_store = vector_store
    app.state.embedding_service = embedding_service
    app.state.compliance_engine = compliance_engine

    yield

    # Shutdown
    logger.info("Shutting down Projektant Copilot...")

    if neo4j_service:
        await neo4j_service.close()
        logger.info("✓ Neo4j closed")

    logger.info("👋 Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered BIM automation system for architectural compliance and documentation",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

# Include API router
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/")
async def root():
    """Root endpoint - API status."""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "operational",
        "environment": settings.ENVIRONMENT,
        "docs": "/api/docs"
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint.

    Returns detailed status of all services.
    """
    health_status = {
        "status": "healthy",
        "services": {}
    }

    # Check Neo4j
    try:
        if neo4j_service and neo4j_service.driver:
            await neo4j_service.driver.verify_connectivity()
            health_status["services"]["neo4j"] = "healthy"
        else:
            health_status["services"]["neo4j"] = "not initialized"
    except Exception as e:
        health_status["services"]["neo4j"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"

    # Check Vector Store
    try:
        if vector_store and vector_store.index:
            stats = await vector_store.get_stats()
            health_status["services"]["pinecone"] = {
                "status": "healthy",
                "vectors": stats.get("total_vector_count", 0)
            }
        else:
            health_status["services"]["pinecone"] = "not initialized"
    except Exception as e:
        health_status["services"]["pinecone"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"

    # Check Embedding Service
    health_status["services"]["embeddings"] = "healthy" if embedding_service else "not initialized"

    # Check Compliance Engine
    health_status["services"]["compliance"] = "healthy" if compliance_engine else "not initialized"

    # WebSocket connections
    health_status["services"]["websocket"] = {
        "status": "healthy",
        "active_connections": len(manager.active_connections)
    }

    return health_status


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """
    WebSocket endpoint for real-time communication with Revit plugin.

    Handles:
    - Compliance check status updates
    - Real-time violation notifications
    - Progress tracking for long-running operations
    """
    await manager.connect(client_id, websocket)

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            message_type = data.get("type")

            logger.info(f"Received message from {client_id}: {message_type}")

            # Handle different message types
            if message_type == "ping":
                await manager.send_personal_message(
                    {"type": "pong", "timestamp": data.get("timestamp")},
                    client_id
                )

            elif message_type == "compliance_check":
                # Trigger compliance check and stream results
                element_id = data.get("element_id")
                element_type = data.get("element_type")
                project_id = data.get("project_id")

                # Send acknowledgment
                await manager.send_personal_message(
                    {
                        "type": "compliance_check_started",
                        "element_id": element_id,
                        "status": "processing"
                    },
                    client_id
                )

                # Perform compliance check
                if compliance_engine:
                    try:
                        result = await compliance_engine.check_element(
                            element_id=element_id,
                            element_type=element_type,
                            project_id=project_id
                        )

                        # Send results
                        await manager.send_personal_message(
                            {
                                "type": "compliance_check_complete",
                                "element_id": element_id,
                                "result": result.dict()
                            },
                            client_id
                        )

                    except Exception as e:
                        logger.error(f"Compliance check failed: {e}")
                        await manager.send_personal_message(
                            {
                                "type": "compliance_check_error",
                                "element_id": element_id,
                                "error": str(e)
                            },
                            client_id
                        )

    except WebSocketDisconnect:
        manager.disconnect(client_id)
        logger.info(f"Client {client_id} disconnected")

    except Exception as e:
        logger.error(f"WebSocket error for client {client_id}: {e}")
        manager.disconnect(client_id)


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled errors."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.DEBUG else "An error occurred"
        }
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )
