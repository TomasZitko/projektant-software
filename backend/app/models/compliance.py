"""Compliance models."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Float, Boolean, JSON
from app.db.base import Base


class ComplianceRule(Base):
    """Building code compliance rules (Czech ČSN standards)."""

    __tablename__ = "compliance_rules"

    id = Column(Integer, primary_key=True, index=True)
    rule_id = Column(String, unique=True, index=True, nullable=False)  # e.g., "ČSN_73_0802_Sec_5.2.a"
    rule_type = Column(String, nullable=False)  # min_width, max_height, fire_rating, etc.
    geometry_type = Column(String, nullable=False)  # corridor, wall, door, window, etc.
    building_types = Column(JSON, nullable=True)  # ["residential", "office"]
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    code_reference = Column(String, nullable=False)  # Section reference
    value_mm = Column(Float, nullable=True)  # Numeric requirement value in mm
    value_text = Column(String, nullable=True)  # Text requirement
    severity = Column(String, default="warning")  # critical, warning, info
    source_document = Column(String, nullable=True)
    page_number = Column(Integer, nullable=True)
    language = Column(String, default="cs")
    version = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ComplianceCheck(Base):
    """Record of compliance checks performed."""

    __tablename__ = "compliance_checks"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    element_id = Column(String, nullable=False)  # Revit element ID
    element_type = Column(String, nullable=False)
    properties = Column(JSON, nullable=False)
    context = Column(JSON, nullable=True)
    is_compliant = Column(Boolean, nullable=False)
    violations_count = Column(Integer, default=0)
    checked_at = Column(DateTime, default=datetime.utcnow)


class CheckResult(Base):
    """Detailed compliance check violations."""

    __tablename__ = "check_results"

    id = Column(Integer, primary_key=True, index=True)
    check_id = Column(Integer, ForeignKey("compliance_checks.id"), nullable=False)
    rule_id = Column(Integer, ForeignKey("compliance_rules.id"), nullable=False)
    severity = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    required_value = Column(Float, nullable=True)
    actual_value = Column(Float, nullable=True)
    confidence_score = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
