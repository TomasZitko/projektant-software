"""
Service for logging compliance checks to PostgreSQL.
"""
from typing import List, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger

from app.models.compliance import ComplianceCheck, CheckResult, ComplianceRule
from app.api.v1.endpoints.compliance import (
    ComplianceCheckRequest,
    ComplianceViolation,
)


class ComplianceLogger:
    """Logs compliance checks and results to database."""

    @staticmethod
    async def log_check(
        db: AsyncSession,
        request: ComplianceCheckRequest,
        violations: List[ComplianceViolation],
        is_compliant: bool,
        element_id: Optional[str] = None,
        project_id: Optional[int] = None,
    ) -> Optional[int]:
        """
        Log compliance check to database.

        Args:
            db: Database session
            request: Original compliance check request
            violations: List of violations found
            is_compliant: Whether element is compliant
            element_id: Revit element ID (optional)
            project_id: Project ID (optional, defaults to 1 for demo)

        Returns:
            Check ID or None if logging failed
        """
        try:
            # Use project_id 1 as default for demo (will be from auth in production)
            project_id = project_id or 1

            # Create compliance check record
            check = ComplianceCheck(
                project_id=project_id,
                element_id=element_id or "unknown",
                element_type=request.element_type,
                properties={
                    "width_mm": request.properties.width_mm,
                    "height_mm": request.properties.height_mm,
                    "length_mm": request.properties.length_mm,
                    "function": request.properties.function,
                },
                context={
                    "room_type": request.context.room_type if request.context else None,
                    "building_type": request.context.building_type if request.context else None,
                    "occupancy": request.context.occupancy if request.context else None,
                    "floor_level": request.context.floor_level if request.context else None,
                }
                if request.context
                else {},
                is_compliant=is_compliant,
                violations_count=len(violations),
                checked_at=datetime.utcnow(),
            )

            db.add(check)
            await db.flush()  # Get check.id without committing

            # Log each violation as a check result
            for violation in violations:
                # Try to find the rule in the database by rule_id
                rule_id_db = None
                try:
                    result = await db.execute(
                        select(ComplianceRule).where(
                            ComplianceRule.rule_id == violation.rule_id
                        )
                    )
                    rule = result.scalar_one_or_none()
                    if rule:
                        rule_id_db = rule.id
                except Exception as e:
                    logger.warning(f"Could not find rule {violation.rule_id}: {e}")

                # Create check result (violation record)
                # Note: rule_id in CheckResult is FK to ComplianceRule.id
                # For now, we'll use a placeholder (1) if rule not found
                # In production, ensure rules exist before checking
                check_result = CheckResult(
                    check_id=check.id,
                    rule_id=rule_id_db or 1,  # TODO: Handle missing rules better
                    severity=violation.severity,
                    message=violation.message,
                    required_value=violation.required_value,
                    actual_value=violation.actual_value,
                    confidence_score=violation.confidence_score,
                    created_at=datetime.utcnow(),
                )
                db.add(check_result)

            await db.commit()
            logger.info(
                f"Logged compliance check #{check.id}: "
                f"{request.element_type} - {violations_count} violations"
            )
            return check.id

        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to log compliance check: {e}")
            return None

    @staticmethod
    async def get_recent_checks(
        db: AsyncSession, project_id: int, limit: int = 10
    ) -> List[ComplianceCheck]:
        """Get recent compliance checks for a project."""
        try:
            result = await db.execute(
                select(ComplianceCheck)
                .where(ComplianceCheck.project_id == project_id)
                .order_by(ComplianceCheck.checked_at.desc())
                .limit(limit)
            )
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Failed to fetch recent checks: {e}")
            return []

    @staticmethod
    async def get_check_statistics(db: AsyncSession, project_id: int) -> dict:
        """Get compliance check statistics for a project."""
        try:
            # Get all checks for project
            result = await db.execute(
                select(ComplianceCheck).where(
                    ComplianceCheck.project_id == project_id
                )
            )
            checks = list(result.scalars().all())

            total_checks = len(checks)
            compliant = sum(1 for c in checks if c.is_compliant)
            non_compliant = total_checks - compliant
            total_violations = sum(c.violations_count for c in checks)

            return {
                "total_checks": total_checks,
                "compliant": compliant,
                "non_compliant": non_compliant,
                "compliance_rate": compliant / total_checks if total_checks > 0 else 0,
                "total_violations": total_violations,
                "avg_violations_per_check": (
                    total_violations / total_checks if total_checks > 0 else 0
                ),
            }
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {
                "total_checks": 0,
                "compliant": 0,
                "non_compliant": 0,
                "compliance_rate": 0,
                "total_violations": 0,
                "avg_violations_per_check": 0,
            }
