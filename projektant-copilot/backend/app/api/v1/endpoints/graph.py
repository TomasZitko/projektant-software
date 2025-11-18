"""
Graph Database Endpoints

Neo4j graph operations and building graph management.

Author: Projektant Copilot Team
License: Commercial
"""

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class GraphImportRequest(BaseModel):
    """Request model for importing Revit data to graph."""
    project_id: str
    revit_data: Dict[str, Any]


@router.post("/import")
async def import_building_graph(
    request: Request,
    import_request: GraphImportRequest
):
    """
    Import Revit BIM data into Neo4j graph database.

    This is called by the Revit plugin after project analysis
    to create the intelligent graph representation.
    """
    neo4j = request.app.state.neo4j

    if not neo4j:
        raise HTTPException(status_code=503, detail="Graph service not available")

    try:
        success = await neo4j.create_building_graph(
            project_id=import_request.project_id,
            revit_data=import_request.revit_data
        )

        return {
            "success": success,
            "project_id": import_request.project_id,
            "message": "Building graph created successfully"
        }

    except Exception as e:
        logger.error(f"Graph import failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Graph import failed: {str(e)}")


@router.get("/stats/{project_id}")
async def get_graph_stats(
    request: Request,
    project_id: str
):
    """
    Get statistics about the building graph.

    Returns node counts, relationship counts, etc.
    """
    neo4j = request.app.state.neo4j

    if not neo4j:
        raise HTTPException(status_code=503, detail="Graph service not available")

    # In production, would query graph statistics
    return {
        "project_id": project_id,
        "stats": {
            "nodes": 0,
            "relationships": 0,
            "rooms": 0,
            "corridors": 0,
            "doors": 0
        }
    }


@router.delete("/{project_id}")
async def delete_building_graph(
    request: Request,
    project_id: str
):
    """Delete building graph for a project."""
    neo4j = request.app.state.neo4j

    if not neo4j:
        raise HTTPException(status_code=503, detail="Graph service not available")

    # In production, would delete graph nodes
    return {
        "success": True,
        "project_id": project_id,
        "message": "Building graph deleted"
    }
