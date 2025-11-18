"""
Spatial Queries Service

Advanced spatial analysis queries for BIM graph database.
Enables geometric reasoning and spatial relationship analysis.

Author: Projektant Copilot Team
License: Commercial
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)


class RoomProximity(BaseModel):
    """Room proximity analysis result."""
    room1_id: str
    room2_id: str
    distance_m: float
    path_length: int
    direct_connection: bool


class FloorAnalysis(BaseModel):
    """Complete floor analysis."""
    floor_id: str
    total_area_m2: float
    room_count: int
    corridor_count: int
    exit_count: int
    avg_room_area_m2: float
    total_occupancy: int
    occupancy_density: float  # people per m²


class BuildingAnalytics(BaseModel):
    """Building-wide analytics."""
    total_floors: int
    total_area_m2: float
    total_rooms: int
    total_occupancy: int
    avg_floor_area_m2: float
    circulation_percentage: float
    exit_coverage_score: float


class SpatialQueries:
    """
    Advanced spatial query service for Neo4j graph.

    Provides complex analytical queries that power the intelligence
    behind compliance checking and building analysis.
    """

    def __init__(self, neo4j_service):
        """Initialize with Neo4j service."""
        self.neo4j = neo4j_service

    async def find_rooms_by_function(
        self,
        project_id: str,
        function: str
    ) -> List[Dict[str, Any]]:
        """Find all rooms with a specific function."""
        async with self.neo4j.driver.session() as session:
            result = await session.run(
                """
                MATCH (b:Building {project_id: $project_id})-[:HAS_FLOOR]->(f:Floor)-[:CONTAINS]->(r:Room)
                WHERE toLower(r.function) CONTAINS toLower($function)
                RETURN r.room_id as room_id,
                       r.name as name,
                       r.function as function,
                       r.area_m2 as area,
                       f.name as floor
                ORDER BY f.level_number, r.number
                """,
                project_id=project_id,
                function=function
            )

            rooms = []
            async for record in result:
                rooms.append({
                    'room_id': record['room_id'],
                    'name': record['name'],
                    'function': record['function'],
                    'area': record['area'],
                    'floor': record['floor'],
                })

            return rooms

    async def find_rooms_by_area_range(
        self,
        project_id: str,
        min_area: float,
        max_area: float
    ) -> List[Dict[str, Any]]:
        """Find rooms within an area range."""
        async with self.neo4j.driver.session() as session:
            result = await session.run(
                """
                MATCH (b:Building {project_id: $project_id})-[:HAS_FLOOR]->(f:Floor)-[:CONTAINS]->(r:Room)
                WHERE r.area_m2 >= $min_area AND r.area_m2 <= $max_area
                RETURN r.room_id as room_id,
                       r.name as name,
                       r.area_m2 as area,
                       r.function as function,
                       f.name as floor
                ORDER BY r.area_m2 DESC
                """,
                project_id=project_id,
                min_area=min_area,
                max_area=max_area
            )

            rooms = []
            async for record in result:
                rooms.append({
                    'room_id': record['room_id'],
                    'name': record['name'],
                    'area': record['area'],
                    'function': record['function'],
                    'floor': record['floor'],
                })

            return rooms

    async def calculate_room_proximity(
        self,
        room1_id: str,
        room2_id: str
    ) -> RoomProximity:
        """
        Calculate proximity between two rooms.

        Returns both graph distance (path length) and geometric distance.
        """
        async with self.neo4j.driver.session() as session:
            result = await session.run(
                """
                MATCH (r1:Room {room_id: $room1_id})
                MATCH (r2:Room {room_id: $room2_id})

                // Check for direct connection
                OPTIONAL MATCH direct = (r1)-[:CONNECTS_TO]-(r2)

                // Find shortest path
                MATCH path = shortestPath((r1)-[:CONNECTS_TO*]-(r2))

                RETURN
                    length(path) as path_length,
                    reduce(dist = 0.0, rel in relationships(path) |
                        dist + coalesce(rel.distance_m, 5.0)) as total_distance,
                    direct IS NOT NULL as direct_connection
                """,
                room1_id=room1_id,
                room2_id=room2_id
            )

            record = await result.single()

            return RoomProximity(
                room1_id=room1_id,
                room2_id=room2_id,
                distance_m=record['total_distance'],
                path_length=record['path_length'],
                direct_connection=record['direct_connection']
            )

    async def analyze_floor(
        self,
        floor_id: str
    ) -> FloorAnalysis:
        """
        Perform comprehensive floor analysis.

        Returns metrics critical for compliance checking:
        - Total area and occupancy
        - Circulation ratio
        - Exit count and coverage
        """
        async with self.neo4j.driver.session() as session:
            result = await session.run(
                """
                MATCH (f:Floor {floor_id: $floor_id})-[:CONTAINS]->(r:Room)

                WITH f,
                     collect(r) as all_rooms,
                     [r IN collect(r) WHERE r:Corridor] as corridors,
                     [r IN collect(r) WHERE r.is_exit = true] as exits

                RETURN
                    sum([r in all_rooms | r.area_m2]) as total_area,
                    size(all_rooms) as room_count,
                    size(corridors) as corridor_count,
                    size(exits) as exit_count,
                    avg([r in all_rooms | r.area_m2]) as avg_room_area,
                    sum([r in all_rooms | r.occupancy]) as total_occupancy
                """,
                floor_id=floor_id
            )

            record = await result.single()

            total_area = record['total_area'] or 0.0
            total_occupancy = record['total_occupancy'] or 0

            return FloorAnalysis(
                floor_id=floor_id,
                total_area_m2=total_area,
                room_count=record['room_count'],
                corridor_count=record['corridor_count'],
                exit_count=record['exit_count'],
                avg_room_area_m2=record['avg_room_area'] or 0.0,
                total_occupancy=total_occupancy,
                occupancy_density=total_occupancy / total_area if total_area > 0 else 0.0
            )

    async def get_building_analytics(
        self,
        project_id: str
    ) -> BuildingAnalytics:
        """
        Get comprehensive building analytics.

        Critical for understanding building compliance at a high level.
        """
        async with self.neo4j.driver.session() as session:
            result = await session.run(
                """
                MATCH (b:Building {project_id: $project_id})
                MATCH (b)-[:HAS_FLOOR]->(f:Floor)
                MATCH (f)-[:CONTAINS]->(r:Room)

                WITH b, f, r,
                     [room IN collect(r) WHERE room:Corridor] as corridors

                RETURN
                    count(DISTINCT f) as total_floors,
                    sum(r.area_m2) as total_area,
                    count(r) as total_rooms,
                    sum(r.occupancy) as total_occupancy,
                    avg(r.area_m2) as avg_floor_area,
                    sum([c in corridors | c.area_m2]) as corridor_area,
                    count([room in collect(r) WHERE room.is_exit = true]) as exit_count
                """,
                project_id=project_id
            )

            record = await result.single()

            total_area = record['total_area'] or 0.0
            corridor_area = record['corridor_area'] or 0.0
            circulation_pct = (corridor_area / total_area * 100) if total_area > 0 else 0.0

            # Exit coverage score (simplified - would be more complex in production)
            total_rooms = record['total_rooms'] or 1
            exit_count = record['exit_count'] or 0
            exit_coverage = min(100.0, (exit_count / total_rooms) * 100)

            return BuildingAnalytics(
                total_floors=record['total_floors'],
                total_area_m2=total_area,
                total_rooms=total_rooms,
                total_occupancy=record['total_occupancy'] or 0,
                avg_floor_area_m2=record['avg_floor_area'] or 0.0,
                circulation_percentage=circulation_pct,
                exit_coverage_score=exit_coverage
            )

    async def find_dead_end_corridors(
        self,
        project_id: str,
        max_length_m: float = 15.0
    ) -> List[Dict[str, Any]]:
        """
        Find dead-end corridors exceeding maximum allowed length.

        Critical for ČSN 73 0802 compliance - dead-end corridors
        must not exceed 15m in most building types.
        """
        async with self.neo4j.driver.session() as session:
            result = await session.run(
                """
                MATCH (b:Building {project_id: $project_id})-[:HAS_FLOOR]->(f:Floor)-[:CONTAINS]->(c:Corridor)

                // Find corridors with only one connection to exits
                MATCH path = shortestPath((c)-[:CONNECTS_TO*]-(exit:Room {is_exit: true}))

                WITH c, f, count(path) as exit_paths, length(path) as path_length
                WHERE exit_paths = 1 AND path_length > 3

                RETURN
                    c.room_id as corridor_id,
                    c.name as name,
                    c.area_m2 as area,
                    f.name as floor,
                    path_length * 5.0 as estimated_length_m
                """,
                project_id=project_id
            )

            dead_ends = []
            async for record in result:
                if record['estimated_length_m'] > max_length_m:
                    dead_ends.append({
                        'corridor_id': record['corridor_id'],
                        'name': record['name'],
                        'floor': record['floor'],
                        'estimated_length_m': record['estimated_length_m'],
                        'violation': True,
                        'max_allowed_m': max_length_m,
                    })

            return dead_ends

    async def find_undersized_exits(
        self,
        project_id: str
    ) -> List[Dict[str, Any]]:
        """
        Find exit doors that are undersized for occupancy.

        ČSN 73 0802 requirements:
        - Min exit width: 900mm (general)
        - Min exit width: 1100mm (high occupancy)
        - Total exit capacity must handle building occupancy
        """
        async with self.neo4j.driver.session() as session:
            result = await session.run(
                """
                MATCH (b:Building {project_id: $project_id})-[:HAS_FLOOR]->(f:Floor)
                MATCH (f)-[:CONTAINS]->(exit:Room {is_exit: true})
                MATCH (exit)-[:CONNECTS_TO]-(served:Room)

                WITH exit, f, sum(served.occupancy) as total_served_occupancy

                // Find exit doors
                MATCH (exit)-[:BOUNDED_BY]->(w:Wall)-[:HAS_OPENING]->(d:Door {is_exit_door: true})

                WITH exit, f, d, total_served_occupancy,
                     CASE
                        WHEN total_served_occupancy > 200 THEN 1100.0
                        ELSE 900.0
                     END as required_width

                WHERE d.width_mm < required_width

                RETURN
                    d.door_id as door_id,
                    d.width_mm as actual_width,
                    required_width,
                    total_served_occupancy,
                    exit.name as exit_name,
                    f.name as floor
                """,
                project_id=project_id
            )

            violations = []
            async for record in result:
                violations.append({
                    'door_id': record['door_id'],
                    'exit_name': record['exit_name'],
                    'floor': record['floor'],
                    'actual_width_mm': record['actual_width'],
                    'required_width_mm': record['required_width'],
                    'served_occupancy': record['total_served_occupancy'],
                    'violation_severity': 'critical',
                })

            return violations
