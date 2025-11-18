"""
Compliance Models

Database models for compliance checking and violation tracking.

Author: Projektant Copilot Team
License: Commercial
"""

from sqlalchemy import Column, Integer, String, Float, ForeignKey, JSON, Enum as SQLEnum, Text, Boolean
from sqlalchemy.orm import relationship
from .base import Base
import enum


class ComplianceStatus(str, enum.Enum):
    """Compliance check status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class ViolationSeverity(str, enum.Enum):
    """Violation severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ComplianceCheck(Base):
    """
    Compliance check record.

    Tracks individual compliance checks performed on BIM elements.
    """
    __tablename__ = "compliance_checks"

    check_id = Column(String(100), unique=True, index=True, nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)

    # Element being checked
    element_id = Column(String(100), nullable=False, index=True)
    element_type = Column(String(50), nullable=False)

    # Check status
    status = Column(SQLEnum(ComplianceStatus), default=ComplianceStatus.PENDING)
    compliant = Column(Boolean, default=None)

    # Results
    violation_count = Column(Integer, default=0)
    critical_count = Column(Integer, default=0)
    high_count = Column(Integer, default=0)
    medium_count = Column(Integer, default=0)
    low_count = Column(Integer, default=0)

    # Confidence and metadata
    confidence = Column(Float, default=0.0)
    context_json = Column(JSON)
    rules_applied = Column(JSON)  # List of code references

    # Timing
    started_at = Column(String(50))
    completed_at = Column(String(50))
    duration_seconds = Column(Float)

    # Relationships
    project = relationship("Project", back_populates="compliance_checks")
    violations = relationship("Violation", back_populates="compliance_check")


class Violation(Base):
    """
    Code violation record.

    Represents a single building code violation detected.
    """
    __tablename__ = "violations"

    violation_id = Column(String(100), unique=True, index=True, nullable=False)
    check_id = Column(Integer, ForeignKey("compliance_checks.id"), nullable=False)

    # Element information
    element_id = Column(String(100), nullable=False, index=True)
    element_type = Column(String(50), nullable=False)

    # Violation details
    severity = Column(SQLEnum(ViolationSeverity), nullable=False)
    code_reference = Column(String(255), nullable=False)  # e.g., "ČSN 73 0802 Section 5.2"
    description = Column(Text, nullable=False)

    # Values
    current_value = Column(String(255))
    required_value = Column(String(255))

    # Recommendation
    recommendation = Column(Text)
    confidence = Column(Float, default=0.0)

    # Status tracking
    resolved = Column(Boolean, default=False)
    resolved_at = Column(String(50))
    resolution_notes = Column(Text)

    # Relationships
    compliance_check = relationship("ComplianceCheck", back_populates="violations")


class ComplianceRule(Base):
    """
    Building code rule.

    Stores extracted and structured building code requirements.
    """
    __tablename__ = "compliance_rules"

    rule_id = Column(String(100), unique=True, index=True, nullable=False)

    # Code identification
    code_type = Column(String(50), nullable=False)  # 'CSN', 'IBC', etc.
    code_number = Column(String(50), nullable=False)  # 'ČSN 73 0802'
    section_id = Column(String(50), nullable=False)  # '5.2.1'
    section_title = Column(String(500))

    # Rule content
    rule_text = Column(Text, nullable=False)
    applies_to = Column(JSON)  # List of element types this applies to
    building_types = Column(JSON)  # List of building types this applies to

    # Extracted requirements
    numerical_requirements = Column(JSON)  # Extracted dimensions, values
    mandatory_items = Column(JSON)  # "must", "shall" requirements
    prohibited_items = Column(JSON)  # "must not" requirements

    # Metadata
    effective_date = Column(String(50))
    version = Column(String(50))
    page_number = Column(Integer)

    # Vector embedding reference
    vector_id = Column(String(100))  # ID in Pinecone


class CheckHistory(Base):
    """
    Historical compliance check results.

    Tracks changes over time for trending and auditing.
    """
    __tablename__ = "check_history"

    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    element_id = Column(String(100), nullable=False, index=True)
    check_date = Column(String(50), nullable=False)

    total_violations = Column(Integer, default=0)
    critical_violations = Column(Integer, default=0)
    compliant = Column(Boolean, default=False)

    # Summary statistics
    snapshot_json = Column(JSON)
