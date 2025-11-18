"""
Project and Building Models

Database models for BIM projects and buildings.

Author: Projektant Copilot Team
License: Commercial
"""

from sqlalchemy import Column, Integer, String, Float, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
from .base import Base
import enum


class BuildingType(str, enum.Enum):
    """Building type classification."""
    RESIDENTIAL = "residential"
    OFFICE = "office"
    EDUCATIONAL = "educational"
    HEALTHCARE = "healthcare"
    INDUSTRIAL = "industrial"
    MIXED_USE = "mixed_use"


class Project(Base):
    """
    BIM Project model.

    Represents a Revit project with all associated data.
    """
    __tablename__ = "projects"

    project_id = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(String(1000))

    # Building information
    building_type = Column(SQLEnum(BuildingType), nullable=False)
    construction_type = Column(String(50))
    total_area_m2 = Column(Float, default=0.0)
    total_floors = Column(Integer, default=0)
    total_occupancy = Column(Integer, default=0)

    # File references
    revit_file_path = Column(String(500))
    graph_db_namespace = Column(String(100))

    # Metadata
    location = Column(String(255))
    client_name = Column(String(255))
    architect_name = Column(String(255))
    project_number = Column(String(100))
    metadata_json = Column(JSON)

    # Owner reference (would connect to User model)
    owner_id = Column(Integer, ForeignKey("user.id"))

    # Relationships
    compliance_checks = relationship("ComplianceCheck", back_populates="project")


class Building(Base):
    """
    Building model (separate from Project for multi-building projects).
    """
    __tablename__ = "buildings"

    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    building_id = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)

    building_type = Column(SQLEnum(BuildingType), nullable=False)
    total_area_m2 = Column(Float, default=0.0)
    total_floors = Column(Integer, default=0)
    total_occupancy = Column(Integer, default=0)

    # Neo4j reference
    graph_node_id = Column(String(100))

    # Relationships
    project = relationship("Project")
    floors = relationship("Floor", back_populates="building")


class Floor(Base):
    """Floor/Level model."""
    __tablename__ = "floors"

    building_id = Column(Integer, ForeignKey("buildings.id"), nullable=False)
    floor_id = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    level_number = Column(Integer, nullable=False)
    elevation_mm = Column(Float, default=0.0)
    height_mm = Column(Float, default=3000.0)
    area_m2 = Column(Float, default=0.0)

    # Neo4j reference
    graph_node_id = Column(String(100))

    # Relationships
    building = relationship("Building", back_populates="floors")


class BuildingMetadata(Base):
    """Additional building metadata and parameters."""
    __tablename__ = "building_metadata"

    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    parameter_name = Column(String(255), nullable=False)
    parameter_value = Column(String(1000))
    parameter_type = Column(String(50))  # string, number, boolean, etc.
    category = Column(String(100))  # grouping category
