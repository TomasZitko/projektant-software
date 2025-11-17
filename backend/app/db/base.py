"""
SQLAlchemy declarative base and imports.
"""
from sqlalchemy.ext.declarative import declarative_base

# Create declarative base
Base = declarative_base()

# Import all models here for Alembic auto-generation
# from app.models.user import User
# from app.models.project import Project
# from app.models.compliance import ComplianceRule, ComplianceCheck
