"""
BIM Graph Builder Service

Transforms Revit BIM data into Neo4j graph structure.
Handles geometric analysis, relationship detection, and spatial computations.

This service bridges the gap between Revit's parametric model and
our graph-based intelligence system.

Author: Projektant Copilot Team
License: Commercial
"""

from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel
import logging
import math

logger = logging.getLogger(__name__)


class BoundingBox(BaseModel):
    """3D bounding box for spatial analysis."""
    min_x: float
    min_y: float
    min_z: float
    max_x: float
    max_y: float
    max_z: float

    def intersects(self, other: 'BoundingBox') -> bool:
        """Check if this bounding box intersects another."""
        return not (
            self.max_x < other.min_x or self.min_x > other.max_x or
            self.max_y < other.min_y or self.min_y > other.max_y or
            self.max_z < other.min_z or self.min_z > other.max_z
        )

    def get_center(self) -> Tuple[float, float, float]:
        """Get the center point of the bounding box."""
        return (
            (self.min_x + self.max_x) / 2,
            (self.min_y + self.max_y) / 2,
            (self.min_z + self.max_z) / 2
        )


class BIMGraphBuilder:
    """
    Build graph representation from Revit BIM data.

    This service performs critical geometric analysis and relationship
    detection that enables intelligent compliance checking.
    """

    def __init__(self):
        """Initialize the graph builder."""
        self.elements: Dict[str, Any] = {}
        self.spatial_index: Dict[str, List[str]] = {}

    def transform_revit_data(
        self,
        project_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Transform raw Revit data into graph-ready format.

        Input: Raw Revit API data (from plugin)
        Output: Structured data ready for Neo4j ingestion

        Performs:
        1. Data normalization and validation
        2. Geometric analysis (areas, volumes, dimensions)
        3. Relationship detection (which walls bound which rooms)
        4. Door-room connection mapping
        5. Corridor identification
        6. Exit detection
        """
        logger.info(f"Transforming Revit data for project: {project_data.get('project_name')}")

        # Build spatial index for fast lookups
        self._build_spatial_index(project_data)

        # Process and enrich each element type
        transformed = {
            'project_name': project_data.get('project_name', 'Unnamed'),
            'project_id': project_data.get('project_id'),
            'building_type': self._determine_building_type(project_data),
            'construction_type': project_data.get('construction_type', 'Unknown'),
            'total_area_m2': 0.0,
            'occupancy': 0,
            'floors': self._process_floors(project_data.get('levels', [])),
            'rooms': [],
            'walls': [],
            'doors': [],
            'windows': [],
        }

        # Process rooms with enrichment
        rooms = project_data.get('rooms', [])
        transformed['rooms'] = self._process_rooms(rooms, project_data)
        transformed['total_area_m2'] = sum(r['area_m2'] for r in transformed['rooms'])
        transformed['occupancy'] = sum(r.get('occupancy', 0) for r in transformed['rooms'])

        # Process walls with room boundary detection
        walls = project_data.get('walls', [])
        transformed['walls'] = self._process_walls(walls, transformed['rooms'])

        # Process doors with room connection detection
        doors = project_data.get('doors', [])
        transformed['doors'] = self._process_doors(doors, transformed['rooms'])

        # Process windows
        windows = project_data.get('windows', [])
        transformed['windows'] = self._process_windows(windows)

        logger.info(f"Transformation complete: {len(transformed['rooms'])} rooms, "
                   f"{len(transformed['walls'])} walls, {len(transformed['doors'])} doors")

        return transformed

    def _build_spatial_index(self, project_data: Dict[str, Any]):
        """Build spatial index for fast geometric queries."""
        # In production, this would use R-tree or similar
        # For now, simple dictionary-based index
        for room in project_data.get('rooms', []):
            room_id = room['id']
            self.elements[room_id] = room

    def _determine_building_type(self, project_data: Dict[str, Any]) -> str:
        """
        Determine building type from project data.

        Uses heuristics:
        - Project parameters
        - Room function distribution
        - Building size and layout
        """
        # Check explicit parameter
        if 'building_type' in project_data:
            return project_data['building_type']

        # Analyze room functions
        rooms = project_data.get('rooms', [])
        functions = [r.get('function', '').lower() for r in rooms]

        # Heuristic detection
        if any('apartment' in f or 'byt' in f for f in functions):
            return 'Residential'
        elif any('office' in f or 'kancelář' in f for f in functions):
            return 'Office'
        elif any('classroom' in f or 'třída' in f for f in functions):
            return 'Educational'
        elif any('patient' in f or 'pacient' in f for f in functions):
            return 'Healthcare'
        else:
            return 'Mixed Use'

    def _process_floors(self, levels: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process and enrich floor/level data."""
        floors = []
        for i, level in enumerate(sorted(levels, key=lambda x: x.get('elevation', 0))):
            floors.append({
                'id': level['id'],
                'name': level.get('name', f'Level {i}'),
                'elevation_mm': level.get('elevation', 0.0),
                'level': i,
                'height_mm': level.get('height', 3000.0),
                'area_m2': 0.0,  # Will be calculated from rooms
            })
        return floors

    def _process_rooms(
        self,
        rooms: List[Dict[str, Any]],
        project_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Process and enrich room data.

        Adds:
        - Occupancy calculations
        - Exit detection
        - Corridor identification
        - Fire rating requirements
        """
        processed_rooms = []

        for room in rooms:
            # Calculate occupancy based on function and area
            function = room.get('function', 'Unknown').lower()
            area_m2 = room.get('area', 0.0)
            occupancy = self._calculate_occupancy(function, area_m2)

            # Detect if this is an exit
            name = room.get('name', '').lower()
            is_exit = any(keyword in name for keyword in ['exit', 'východ', 'stairway', 'schodiště'])

            # Detect corridor
            is_corridor = any(keyword in function for keyword in [
                'corridor', 'hallway', 'circulation', 'chodba', 'průchod'
            ])

            # Determine if habitable
            is_habitable = function not in [
                'corridor', 'bathroom', 'toilet', 'storage', 'mechanical',
                'chodba', 'koupelna', 'wc', 'sklad', 'technická místnost'
            ]

            processed_rooms.append({
                'id': room['id'],
                'floor_id': room['floor_id'],
                'name': room.get('name', 'Unnamed Room'),
                'number': room.get('number', ''),
                'function': function.title(),
                'area_m2': area_m2,
                'volume_m3': room.get('volume', area_m2 * 3.0),
                'perimeter_m': room.get('perimeter', math.sqrt(area_m2) * 4),
                'ceiling_height_mm': room.get('ceiling_height', 3000.0),
                'occupancy': occupancy,
                'occupancy_type': self._get_occupancy_type(function),
                'fire_rating_required': None,  # Determined by compliance engine
                'is_exit': is_exit,
                'is_habitable': is_habitable,
                'is_corridor': is_corridor,
                'bounding_box': room.get('bounding_box'),
            })

        return processed_rooms

    def _calculate_occupancy(self, function: str, area_m2: float) -> int:
        """
        Calculate occupancy based on room function and area.

        Uses ČSN standards for occupancy calculations.
        """
        # Occupancy factors (m² per person)
        occupancy_factors = {
            'office': 10.0,
            'kancelář': 10.0,
            'classroom': 2.0,
            'třída': 2.0,
            'assembly': 1.5,
            'shromažďovací': 1.5,
            'retail': 5.0,
            'obchod': 5.0,
            'apartment': 20.0,
            'byt': 20.0,
            'bedroom': 15.0,
            'ložnice': 15.0,
        }

        # Find matching factor
        factor = 20.0  # Default conservative factor
        for key, value in occupancy_factors.items():
            if key in function.lower():
                factor = value
                break

        return max(1, int(area_m2 / factor))

    def _get_occupancy_type(self, function: str) -> str:
        """Get occupancy classification for building code compliance."""
        function = function.lower()

        if any(x in function for x in ['office', 'kancelář']):
            return 'Business'
        elif any(x in function for x in ['apartment', 'byt', 'residential']):
            return 'Residential'
        elif any(x in function for x in ['classroom', 'třída', 'school']):
            return 'Educational'
        elif any(x in function for x in ['assembly', 'shromažďovací']):
            return 'Assembly'
        elif any(x in function for x in ['storage', 'sklad']):
            return 'Storage'
        else:
            return 'Mixed'

    def _process_walls(
        self,
        walls: List[Dict[str, Any]],
        rooms: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Process walls and detect which rooms they bound.

        Uses spatial analysis to determine wall-room relationships.
        """
        processed_walls = []

        for wall in walls:
            bounding_rooms = []

            # Find rooms that this wall bounds (spatial intersection)
            wall_bbox = wall.get('bounding_box')
            if wall_bbox:
                wall_bb = BoundingBox(**wall_bbox)
                for room in rooms:
                    room_bbox = room.get('bounding_box')
                    if room_bbox:
                        room_bb = BoundingBox(**room_bbox)
                        if wall_bb.intersects(room_bb):
                            bounding_rooms.append(room['id'])

            processed_walls.append({
                'id': wall['id'],
                'width_mm': wall.get('width', 0.0),
                'height_mm': wall.get('height', 0.0),
                'length_mm': wall.get('length', 0.0),
                'area_m2': wall.get('area', 0.0),
                'type': wall.get('type', 'Unknown'),
                'fire_rating_minutes': wall.get('fire_rating', 0),
                'structural': wall.get('structural', False),
                'load_bearing': wall.get('load_bearing', False),
                'bounding_rooms': bounding_rooms[:2],  # Max 2 rooms per wall
            })

        return processed_walls

    def _process_doors(
        self,
        doors: List[Dict[str, Any]],
        rooms: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Process doors and detect which rooms they connect.

        This is CRITICAL for egress path finding!
        """
        processed_doors = []

        for door in doors:
            connecting_rooms = []

            # Find rooms that this door connects (spatial proximity)
            door_bbox = door.get('bounding_box')
            if door_bbox:
                door_bb = BoundingBox(**door_bbox)
                door_center = door_bb.get_center()

                # Find closest rooms
                room_distances = []
                for room in rooms:
                    room_bbox = room.get('bounding_box')
                    if room_bbox:
                        room_bb = BoundingBox(**room_bbox)
                        room_center = room_bb.get_center()
                        distance = math.sqrt(
                            (door_center[0] - room_center[0])**2 +
                            (door_center[1] - room_center[1])**2
                        )
                        room_distances.append((room['id'], distance))

                # Take 2 closest rooms
                room_distances.sort(key=lambda x: x[1])
                connecting_rooms = [r[0] for r in room_distances[:2]]

            processed_doors.append({
                'id': door['id'],
                'width_mm': door.get('width', 0.0),
                'height_mm': door.get('height', 0.0),
                'type': door.get('type', 'Unknown'),
                'fire_rated': door.get('fire_rated', False),
                'fire_rating_minutes': door.get('fire_rating', 0),
                'is_exit': door.get('is_exit', False),
                'swing_direction': door.get('swing_direction', 'Unknown'),
                'host_wall_id': door.get('host_wall_id'),
                'connecting_rooms': connecting_rooms,
            })

        return processed_doors

    def _process_windows(
        self,
        windows: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Process window data."""
        processed_windows = []

        for window in windows:
            processed_windows.append({
                'id': window['id'],
                'width_mm': window.get('width', 0.0),
                'height_mm': window.get('height', 0.0),
                'area_m2': window.get('area', 0.0),
                'type': window.get('type', 'Unknown'),
                'host_wall_id': window.get('host_wall_id'),
            })

        return processed_windows
