"""
Compliance checking engine - orchestrates RAG pipeline for Czech building codes.

Workflow:
1. Parse element properties and context
2. Generate search query
3. Retrieve relevant rules from vector DB
4. Check compliance
5. Return violations with confidence scores
"""

import re
from typing import List, Dict, Any, Optional
import time

from loguru import logger

from app.config import settings
from app.services.vector_service import vector_service
from app.services.embedding_service import embedding_service
from app.services.cache_service import cache_service


class ComplianceEngine:
    """Main compliance checking engine using RAG pipeline."""

    # Element type mappings to Czech terms
    ELEMENT_MAPPINGS = {
        "Wall": ["stěna", "zeď", "příčka"],
        "Door": ["dveře", "vchod", "průchod"],
        "Window": ["okno", "zasklení"],
        "Corridor": ["chodba", "úniková cesta"],
        "Stair": ["schodiště", "schody"],
        "Room": ["místnost", "prostor"],
        "Floor": ["podlaha", "strop"],
    }

    ROOM_TYPE_MAPPINGS = {
        "Corridor": ["chodba", "úniková cesta", "komunikace"],
        "Bedroom": ["ložnice", "pokoj"],
        "Bathroom": ["koupelna", "hygienické zařízení"],
        "Kitchen": ["kuchyň"],
        "Office": ["kancelář", "pracovna"],
        "Stairs": ["schodiště"],
    }

    SEVERITY_LEVELS = {
        "critical": {"threshold": 0.85, "priority": 1},
        "high": {"threshold": 0.70, "priority": 2},
        "medium": {"threshold": 0.50, "priority": 3},
        "low": {"threshold": 0.30, "priority": 4},
    }

    def __init__(self):
        """Initialize compliance engine."""
        self._checks_performed = 0
        self._violations_found = 0

    async def initialize(self):
        """Initialize all dependent services."""
        logger.info("Initializing ComplianceEngine...")

        # Initialize services
        await cache_service.connect()
        await embedding_service.initialize()
        await vector_service.initialize()

        logger.info("✓ ComplianceEngine initialized")

    async def shutdown(self):
        """Shutdown all services."""
        logger.info("Shutting down ComplianceEngine...")

        await embedding_service.close()
        await cache_service.disconnect()

        logger.info("✓ ComplianceEngine shutdown complete")

    def _build_search_query(
        self,
        element_type: str,
        properties: Dict[str, Any],
        context: Dict[str, Any]
    ) -> str:
        """
        Build semantic search query from element data.

        Example: "Wall corridor width 1100mm residential building minimum requirements"
        """
        query_parts = []

        # Element type (Czech + English)
        czech_terms = self.ELEMENT_MAPPINGS.get(element_type, [])
        if czech_terms:
            query_parts.append(czech_terms[0])
        query_parts.append(element_type.lower())

        # Room/context type
        room_type = context.get("room_type")
        if room_type:
            czech_room = self.ROOM_TYPE_MAPPINGS.get(room_type, [])
            if czech_room:
                query_parts.append(czech_room[0])

        # Properties with values
        for prop, value in properties.items():
            if value is not None:
                # Extract dimension type (width, height, etc.)
                dim_type = prop.replace("_mm", "").replace("_", " ")
                query_parts.append(f"{dim_type} {value}mm")

        # Building type
        building_type = context.get("building_type")
        if building_type:
            query_parts.append(building_type.lower())

        # Add keywords for better recall
        query_parts.extend(["požadavek", "minimální", "maximální", "ČSN"])

        query = " ".join(query_parts)
        logger.debug(f"Search query: {query}")

        return query

    async def check_compliance(
        self,
        element_type: str,
        properties: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Check element compliance against Czech building codes.

        Args:
            element_type: Type of element (Wall, Door, etc.)
            properties: Element properties (width_mm, height_mm, etc.)
            context: Context (room_type, building_type, etc.)

        Returns:
            Compliance check result with violations
        """
        start_time = time.time()
        self._checks_performed += 1

        logger.info(
            f"Checking compliance: {element_type} in {context.get('room_type', 'unknown')} "
            f"({properties})"
        )

        # Build search query
        search_query = self._build_search_query(element_type, properties, context)

        # Retrieve relevant rules from vector DB
        try:
            relevant_rules = await vector_service.query(
                query_text=search_query,
                top_k=settings.TOP_K_RESULTS,
                use_cache=True,
                include_metadata=True
            )
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            relevant_rules = []

        # Filter by similarity threshold
        filtered_rules = [
            rule for rule in relevant_rules
            if rule["score"] >= settings.SIMILARITY_THRESHOLD
        ]

        logger.info(
            f"Retrieved {len(relevant_rules)} rules, "
            f"{len(filtered_rules)} above threshold ({settings.SIMILARITY_THRESHOLD})"
        )

        # Check each rule
        violations = []

        for rule in filtered_rules:
            violation = self._check_rule(
                element_type=element_type,
                properties=properties,
                context=context,
                rule=rule
            )

            if violation:
                violations.append(violation)
                self._violations_found += 1

        # Sort by severity and confidence
        violations.sort(
            key=lambda v: (
                self.SEVERITY_LEVELS[v["severity"]]["priority"],
                -v["confidence_score"]
            )
        )

        # Calculate overall compliance
        compliant = len(violations) == 0

        # Generate recommendations
        recommendations = self._generate_recommendations(violations, element_type)

        execution_time = (time.time() - start_time) * 1000  # ms

        result = {
            "compliant": compliant,
            "violations": violations,
            "recommendations": recommendations,
            "rules_checked": len(filtered_rules),
            "execution_time_ms": round(execution_time, 2),
        }

        logger.info(
            f"✓ Compliance check complete: {len(violations)} violations, "
            f"{execution_time:.1f}ms"
        )

        return result

    def _check_rule(
        self,
        element_type: str,
        properties: Dict[str, Any],
        context: Dict[str, Any],
        rule: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Check single rule against element.

        Returns violation dict if non-compliant, None if compliant.
        """
        metadata = rule.get("metadata", {})
        rule_text = metadata.get("text", "")
        similarity_score = rule["score"]

        # Parse rule for numeric requirements
        violations = self._extract_numeric_violations(
            rule_text=rule_text,
            properties=properties,
            similarity_score=similarity_score
        )

        if violations:
            # Determine severity based on similarity score
            severity = self._determine_severity(similarity_score)

            return {
                "rule_id": rule["id"],
                "rule_text": rule_text,
                "severity": severity,
                "message": violations["message"],
                "confidence_score": round(similarity_score, 3),
                "required_value": violations.get("required_value"),
                "actual_value": violations.get("actual_value"),
                "csn_reference": metadata.get("csn_reference", ""),
                "page_number": metadata.get("page_number"),
            }

        return None

    def _extract_numeric_violations(
        self,
        rule_text: str,
        properties: Dict[str, Any],
        similarity_score: float
    ) -> Optional[Dict[str, Any]]:
        """
        Extract numeric requirements and check against properties.

        Patterns:
        - "nesmí být menší než X mm" -> minimum requirement
        - "nesmí být větší než X mm" -> maximum requirement
        - "musí být v rozmezí X až Y mm" -> range requirement
        """
        # Minimum width pattern
        min_pattern = re.search(
            r'(šířka|výška|délka|rozměr)[^\d]*?(\d+(?:\s?\d{3})*)\s*mm',
            rule_text,
            re.IGNORECASE | re.UNICODE
        )

        if min_pattern:
            dimension_type = min_pattern.group(1).lower()
            required_value = int(min_pattern.group(2).replace(' ', ''))

            # Map Czech term to property
            property_map = {
                "šířka": "width_mm",
                "výška": "height_mm",
                "délka": "length_mm",
            }

            prop_key = property_map.get(dimension_type)

            if prop_key and prop_key in properties:
                actual_value = properties[prop_key]

                # Check for minimum requirement keywords
                is_minimum = bool(re.search(
                    r'(nejmenší|minimální|nesmí být menší|alespoň)',
                    rule_text,
                    re.IGNORECASE
                ))

                if is_minimum and actual_value < required_value:
                    return {
                        "message": (
                            f"{dimension_type.capitalize()} ({actual_value}mm) je menší než "
                            f"požadovaných {required_value}mm"
                        ),
                        "required_value": required_value,
                        "actual_value": actual_value,
                    }

                # Check for maximum requirement
                is_maximum = bool(re.search(
                    r'(největší|maximální|nesmí být větší|nejvýše)',
                    rule_text,
                    re.IGNORECASE
                ))

                if is_maximum and actual_value > required_value:
                    return {
                        "message": (
                            f"{dimension_type.capitalize()} ({actual_value}mm) je větší než "
                            f"povolených {required_value}mm"
                        ),
                        "required_value": required_value,
                        "actual_value": actual_value,
                    }

        return None

    def _determine_severity(self, confidence_score: float) -> str:
        """Determine severity based on confidence score."""
        if confidence_score >= 0.85:
            return "critical"
        elif confidence_score >= 0.70:
            return "high"
        elif confidence_score >= 0.50:
            return "medium"
        else:
            return "low"

    def _generate_recommendations(
        self,
        violations: List[Dict[str, Any]],
        element_type: str
    ) -> List[str]:
        """Generate actionable recommendations."""
        if not violations:
            return ["Element is compliant with checked regulations."]

        recommendations = []

        # Group by severity
        critical = [v for v in violations if v["severity"] == "critical"]
        high = [v for v in violations if v["severity"] == "high"]

        if critical:
            recommendations.append(
                f"⚠️ CRITICAL: {len(critical)} critical violations must be resolved immediately."
            )

        if high:
            recommendations.append(
                f"⚠️ {len(high)} high-severity violations require attention."
            )

        # Specific recommendations based on violation types
        for violation in violations[:3]:  # Top 3 violations
            required = violation.get("required_value")
            actual = violation.get("actual_value")

            if required and actual:
                diff = abs(required - actual)
                recommendations.append(
                    f"Adjust dimension by {diff}mm to meet {violation.get('csn_reference', 'requirement')}"
                )

        recommendations.append(
            "Review complete ČSN documentation for detailed requirements."
        )

        return recommendations

    def get_stats(self) -> Dict[str, Any]:
        """Get engine statistics."""
        return {
            "checks_performed": self._checks_performed,
            "violations_found": self._violations_found,
            "avg_violations_per_check": (
                self._violations_found / self._checks_performed
                if self._checks_performed > 0 else 0
            ),
        }


# Global instance
compliance_engine = ComplianceEngine()
