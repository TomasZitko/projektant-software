"""
User and Authentication Models

Database models for users, organizations, and licensing.

Author: Projektant Copilot Team
License: Commercial
"""

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from .base import Base
import enum


class UserRole(str, enum.Enum):
    """User role classification."""
    ADMIN = "admin"
    ARCHITECT = "architect"
    ENGINEER = "engineer"
    VIEWER = "viewer"


class User(Base):
    """User model with authentication and profile information."""
    __tablename__ = "user"

    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)

    # Profile
    full_name = Column(String(255))
    role = Column(SQLEnum(UserRole), default=UserRole.ARCHITECT)
    organization_id = Column(Integer, ForeignKey("organizations.id"))

    # Status
    is_verified = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    # Relationships
    organization = relationship("Organization", back_populates="users")


class Organization(Base):
    """Organization/Company model for multi-tenancy."""
    __tablename__ = "organizations"

    name = Column(String(255), nullable=False)
    license_key = Column(String(100), unique=True)
    license_type = Column(String(50))  # trial, professional, enterprise
    max_users = Column(Integer, default=5)
    max_projects = Column(Integer, default=10)

    # Relationships
    users = relationship("User", back_populates="organization")
