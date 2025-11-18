"""
BIM Analysis Endpoints

Spatial analysis and building intelligence queries.

Author: Projektant Copilot Team
License: Commercial
"""

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class EgressPathRequest(BaseModel):
    """Request model for egress path analysis."""
    room_id: str
    max_hops: int = 15


class FireCompartmentRequest(BaseModel):
    """Request model for fire compartment analysis."""
    room_id: str


@router.post("/egress-paths")
async def find_egress_paths(
    request: Request,
    path_request: EgressPathRequest
):
    """
    Find all egress paths from a room to exits.

    Critical for ČSN 73 0802 compliance checking.
    """
    neo4j = request.app.state.neo4j

    if not neo4j:
        raise HTTPException(status_code=503, detail="Graph service not available")

    try:
        paths = await neo4j.find_egress_paths(
            start_room_id=path_request.room_id,
            max_hops=path_request.max_hops
        )

        return {
            "room_id": path_request.room_id,
            "paths": [p.dict() for p in paths],
            "path_count": len(paths),
            "shortest_distance_m": paths[0].distance_m if paths else None,
            "compliant": all(p.compliant for p in paths) if paths else False
        }

    except Exception as e:
        logger.error(f"Egress path analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/fire-compartment")
async def analyze_fire_compartment(
    request: Request,
    comp_request: FireCompartmentRequest
):
    """
    Analyze fire compartment for a room.

    Returns all rooms in the same fire compartment and compliance status.
    """
    neo4j = request.app.state.neo4j

    if not neo4j:
        raise HTTPException(status_code=503, detail="Graph service not available")

    try:
        compartment = await neo4j.get_fire_compartment(
            room_id=comp_request.room_id
        )

        return compartment.dict()

    except Exception as e:
        logger.error(f"Fire compartment analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/corridor/{corridor_id}")
async def analyze_corridor(
    request: Request,
    corridor_id: str
):
    """
    Perform detailed corridor analysis.

    Returns comprehensive corridor metrics and violations.
    """
    neo4j = request.app.state.neo4j

    if not neo4j:
        raise HTTPException(status_code=503, detail="Graph service not available")

    try:
        analysis = await neo4j.analyze_corridor(corridor_id)
        return analysis.dict()

    except Exception as e:
        logger.error(f"Corridor analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/room/{room_id}/context")
async def get_room_context(
    request: Request,
    room_id: str
):
    """
    Get rich context for a room.

    Returns all spatial relationships, properties, and compliance-relevant data.
    """
    neo4j = request.app.state.neo4j

    if not neo4j:
        raise HTTPException(status_code=503, detail="Graph service not available")

    try:
        context = await neo4j.get_room_context(room_id)
        return context

    except Exception as e:
        logger.error(f"Room context retrieval failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
