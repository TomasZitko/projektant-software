"""Project model."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.db.base import Base


class Project(Base):
    """Revit project metadata."""

    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    revit_version = Column(String, nullable=True)
    building_type = Column(String, nullable=True)  # residential, office, hospital, etc.
    location = Column(String, nullable=True)
    total_area_sqm = Column(Integer, nullable=True)
    floor_count = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    # user = relationship("User", back_populates="projects")
