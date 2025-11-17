"""
Core compliance checking engine.
Evaluates building elements against Czech building codes.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.compliance import ComplianceRule, ComplianceCheck, CheckResult
from app.services.rag_service import rag_service


class ComplianceEngine:
    """Main engine for compliance checking logic."""

    def __init__(self):
        """Initialize compliance engine."""
        self.rag_service = rag_service
        self.rule_cache = {}

    async def check_element_compliance(
        self,
        element_type: str,
        properties: Dict[str, Any],
        context: Optional[Dict[str, Any]],
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Check element compliance against building codes.

        Args:
            element_type: Type of element (Wall, Door, Window, etc.)
            properties: Element properties (width, height, material, etc.)
            context: Spatial context (room_type, building_type, etc.)
            db: Database session

        Returns:
            Compliance check result with violations and recommendations
        """
        logger.info(f"Checking compliance for {element_type}")

        violations = []
        recommendations = []

        # Get applicable rules from database
        rules = await self._get_applicable_rules(element_type, context, db)
        logger.info(f"Found {len(rules)} applicable rules")

        # Check each rule
        for rule in rules:
            violation = await self._check_rule(rule, properties, context)
            if violation:
                violations.append(violation)

        # If no database rules, try RAG-based checking
        if not rules:
            logger.info("No database rules found, trying RAG service")
            rag_violations = await self._check_with_rag(
                element_type, properties, context
            )
            violations.extend(rag_violations)

        # Generate recommendations
        if violations:
            recommendations = self._generate_recommendations(
                violations, element_type, properties
            )

        result = {
            "compliant": len(violations) == 0,
            "violations": violations,
            "recommendations": recommendations,
            "checked_at": datetime.utcnow().isoformat() + "Z",
            "rules_checked": len(rules),
        }

        return result

    async def _get_applicable_rules(
        self,
        element_type: str,
        context: Optional[Dict[str, Any]],
        db: AsyncSession,
    ) -> List[ComplianceRule]:
        """Get rules applicable to this element and context."""
        try:
            # Build query
            query = select(ComplianceRule).where(
                ComplianceRule.is_active == True,
                ComplianceRule.geometry_type == element_type.lower(),
            )

            result = await db.execute(query)
            rules = result.scalars().all()

            # Filter by building type if provided
            if context and context.get("building_type"):
                building_type = context["building_type"]
                rules = [
                    r
                    for r in rules
                    if not r.building_types
                    or building_type in r.building_types
                ]

            return list(rules)

        except Exception as e:
            logger.error(f"Error fetching rules: {e}")
            return []

    async def _check_rule(
        self,
        rule: ComplianceRule,
        properties: Dict[str, Any],
        context: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """
        Check if element violates a specific rule.

        Returns violation dict if non-compliant, None if compliant.
        """
        try:
            rule_type = rule.rule_type
            required_value = rule.value_mm

            if not required_value:
                return None

            # Get actual value based on rule type
            actual_value = self._get_property_value(properties, rule_type)

            if actual_value is None:
                logger.warning(f"Property not found for rule type: {rule_type}")
                return None

            # Check compliance based on rule type
            is_violation = False
            message = ""

            if "min_" in rule_type:
                # Minimum requirement
                if actual_value < required_value:
                    is_violation = True
                    message = f"{rule.title}: {actual_value}mm is less than required minimum {required_value}mm"

            elif "max_" in rule_type:
                # Maximum requirement
                if actual_value > required_value:
                    is_violation = True
                    message = f"{rule.title}: {actual_value}mm exceeds maximum allowed {required_value}mm"

            if is_violation:
                return {
                    "rule_id": rule.rule_id,
                    "severity": rule.severity,
                    "message": message,
                    "required_value": required_value,
                    "actual_value": actual_value,
                    "code_reference": rule.code_reference,
                    "confidence_score": 0.95,  # High confidence for database rules
                }

            return None

        except Exception as e:
            logger.error(f"Error checking rule {rule.rule_id}: {e}")
            return None

    def _get_property_value(
        self, properties: Dict[str, Any], rule_type: str
    ) -> Optional[float]:
        """Extract property value based on rule type."""
        # Map rule types to property keys
        mapping = {
            "min_width": "width_mm",
            "max_width": "width_mm",
            "min_height": "height_mm",
            "max_height": "height_mm",
            "min_length": "length_mm",
            "max_length": "length_mm",
        }

        property_key = mapping.get(rule_type)
        if property_key:
            return properties.get(property_key)

        return None

    async def _check_with_rag(
        self,
        element_type: str,
        properties: Dict[str, Any],
        context: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Check compliance using RAG service when no database rules exist."""
        try:
            # Build query for RAG
            query = f"Requirements for {element_type} with {properties}"

            # Retrieve relevant rules
            relevant_rules = await self.rag_service.retrieve_relevant_rules(
                query, element_type, context
            )

            # TODO: Evaluate retrieved rules against properties
            violations = []

            return violations

        except Exception as e:
            logger.error(f"Error in RAG-based checking: {e}")
            return []

    def _generate_recommendations(
        self,
        violations: List[Dict[str, Any]],
        element_type: str,
        properties: Dict[str, Any],
    ) -> List[str]:
        """Generate actionable recommendations based on violations."""
        recommendations = []

        for violation in violations:
            rule_type = violation.get("rule_id", "")
            required = violation.get("required_value")
            actual = violation.get("actual_value")

            if required and actual:
                diff = required - actual
                if "width" in rule_type.lower():
                    recommendations.append(
                        f"Increase {element_type.lower()} width by {abs(diff):.0f}mm to meet requirements"
                    )
                elif "height" in rule_type.lower():
                    recommendations.append(
                        f"Adjust {element_type.lower()} height by {abs(diff):.0f}mm"
                    )

        if not recommendations:
            recommendations.append(
                f"Review {element_type.lower()} design to address compliance violations"
            )

        return recommendations


# Singleton instance
compliance_engine = ComplianceEngine()
