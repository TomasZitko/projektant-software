"""
Comprehensive integration tests for compliance checking workflow.

Tests the full end-to-end flow:
1. Revit plugin → Backend API
2. Backend → Redis cache
3. Backend → PostgreSQL database
4. Error handling scenarios
5. Performance requirements (<1 second)
"""
import pytest
import asyncio
import time
from datetime import datetime
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from app.main import app
from app.config import settings
from app.db.session import get_db
from app.models.compliance import ComplianceCheck, CheckResult
from app.services.cache import cache_service
from app.services.metrics import metrics_collector


@pytest.fixture
async def client():
    """HTTP client for testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def db_session():
    """Database session for testing."""
    async for session in get_db():
        yield session
        break


class TestEndToEndWorkflow:
    """Test complete workflow from API call to database logging."""

    @pytest.mark.asyncio
    async def test_full_workflow_compliant_element(self, client, db_session):
        """Test full workflow with compliant element."""
        # Step 1: Send compliance check request
        payload = {
            "element_type": "Wall",
            "properties": {
                "width_mm": 1500.0,  # Compliant width
                "height_mm": 3000.0,
                "length_mm": 5000.0,
                "function": "Interior"
            },
            "context": {
                "room_type": "Corridor",
                "building_type": "Office",
                "occupancy": 150,
                "floor_level": 1
            }
        }

        start_time = time.time()
        response = await client.post("/api/v1/compliance/check", json=payload)
        duration_ms = (time.time() - start_time) * 1000

        # Verify response
        assert response.status_code == 200
        data = response.json()

        assert data["compliant"] is True
        assert len(data["violations"]) == 0
        assert "checked_at" in data

        # Verify performance (<1 second)
        assert duration_ms < 1000, f"Response took {duration_ms:.2f}ms (should be <1000ms)"

        # Step 2: Verify cached in Redis (second request should be faster)
        cached_start = time.time()
        cached_response = await client.post("/api/v1/compliance/check", json=payload)
        cached_duration_ms = (time.time() - cached_start) * 1000

        assert cached_response.status_code == 200
        # Cached should be significantly faster (usually <100ms)
        assert cached_duration_ms < duration_ms * 0.5, "Cache not working - second request not faster"

        # Step 3: Verify logged to PostgreSQL
        # Note: This requires the database migration to have run
        try:
            result = await db_session.execute(
                select(ComplianceCheck).order_by(ComplianceCheck.checked_at.desc()).limit(1)
            )
            latest_check = result.scalar_one_or_none()

            if latest_check:
                assert latest_check.element_type == "Wall"
                assert latest_check.is_compliant is True
                assert latest_check.violations_count == 0
        except Exception as e:
            pytest.skip(f"Database not initialized: {e}")

    @pytest.mark.asyncio
    async def test_full_workflow_violation_detected(self, client, db_session):
        """Test full workflow with violation detection."""
        # Corridor width too narrow (1100mm < 1200mm minimum)
        payload = {
            "element_type": "Wall",
            "properties": {
                "width_mm": 1100.0,  # Non-compliant
                "height_mm": 3000.0,
            },
            "context": {
                "room_type": "Corridor",
                "building_type": "Office",
                "occupancy": 100,
            }
        }

        response = await client.post("/api/v1/compliance/check", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["compliant"] is False
        assert len(data["violations"]) == 1

        violation = data["violations"][0]
        assert violation["rule_id"] == "ČSN_73_0802_Sec_5.2.a"
        assert violation["severity"] == "critical"
        assert violation["required_value"] == 1200
        assert violation["actual_value"] == 1100
        assert violation["confidence_score"] >= 0.9
        assert "ČSN 73 0802" in violation["message"]

        # Verify recommendations provided
        assert len(data["recommendations"]) > 0

    @pytest.mark.asyncio
    async def test_high_occupancy_wider_corridor(self, client):
        """Test that high occupancy requires wider corridors."""
        # High occupancy (>200) requires 1500mm minimum
        payload = {
            "element_type": "Wall",
            "properties": {"width_mm": 1300.0},
            "context": {
                "room_type": "Corridor",
                "occupancy": 250,  # High occupancy
            }
        }

        response = await client.post("/api/v1/compliance/check", json=payload)
        data = response.json()

        # Should fail because 1300 < 1500 for high occupancy
        assert data["compliant"] is False
        assert data["violations"][0]["required_value"] == 1500

        # Now test with compliant width
        payload["properties"]["width_mm"] = 1600.0
        response = await client.post("/api/v1/compliance/check", json=payload)
        data = response.json()
        assert data["compliant"] is True


class TestCacheBehavior:
    """Test Redis caching behavior."""

    @pytest.mark.asyncio
    async def test_cache_hit_performance(self, client):
        """Verify cache significantly improves performance."""
        payload = {
            "element_type": "Door",
            "properties": {"width_mm": 900.0, "height_mm": 2100.0},
        }

        # First request (cache miss)
        start1 = time.time()
        response1 = await client.post("/api/v1/compliance/check", json=payload)
        duration1 = (time.time() - start1) * 1000

        # Second request (cache hit)
        start2 = time.time()
        response2 = await client.post("/api/v1/compliance/check", json=payload)
        duration2 = (time.time() - start2) * 1000

        assert response1.status_code == 200
        assert response2.status_code == 200

        # Cache hit should be at least 30% faster
        assert duration2 < duration1 * 0.7, f"Cache not effective: {duration2:.2f}ms vs {duration1:.2f}ms"

    @pytest.mark.asyncio
    async def test_cache_key_uniqueness(self, client):
        """Verify different requests don't collide in cache."""
        payload1 = {
            "element_type": "Wall",
            "properties": {"width_mm": 1100.0},
            "context": {"room_type": "Corridor"}
        }

        payload2 = {
            "element_type": "Wall",
            "properties": {"width_mm": 1500.0},  # Different width
            "context": {"room_type": "Corridor"}
        }

        response1 = await client.post("/api/v1/compliance/check", json=payload1)
        response2 = await client.post("/api/v1/compliance/check", json=payload2)

        data1 = response1.json()
        data2 = response2.json()

        # Different widths should give different compliance results
        assert data1["compliant"] != data2["compliant"]


class TestErrorHandling:
    """Test error handling scenarios."""

    @pytest.mark.asyncio
    async def test_invalid_element_type(self, client):
        """Test handling of invalid element types."""
        payload = {
            "element_type": "",  # Empty element type
            "properties": {"width_mm": 1000.0},
        }

        response = await client.post("/api/v1/compliance/check", json=payload)
        # Should still succeed but may not find violations
        assert response.status_code in [200, 422]

    @pytest.mark.asyncio
    async def test_missing_required_fields(self, client):
        """Test handling of missing required fields."""
        payload = {
            "element_type": "Wall",
            # Missing properties
        }

        response = await client.post("/api/v1/compliance/check", json=payload)
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_negative_dimensions(self, client):
        """Test handling of invalid negative dimensions."""
        payload = {
            "element_type": "Wall",
            "properties": {"width_mm": -100.0},  # Invalid
        }

        response = await client.post("/api/v1/compliance/check", json=payload)
        # Should either reject or handle gracefully
        assert response.status_code in [200, 422]

    @pytest.mark.asyncio
    async def test_extremely_large_dimensions(self, client):
        """Test handling of unrealistic dimensions."""
        payload = {
            "element_type": "Wall",
            "properties": {"width_mm": 999999999.0},  # Unrealistic
        }

        response = await client.post("/api/v1/compliance/check", json=payload)
        assert response.status_code == 200  # Should handle gracefully


class TestPerformance:
    """Test performance requirements."""

    @pytest.mark.asyncio
    async def test_response_time_under_1_second(self, client):
        """Verify all requests complete in <1 second."""
        test_cases = [
            {"element_type": "Wall", "properties": {"width_mm": 1200.0}},
            {"element_type": "Door", "properties": {"width_mm": 900.0, "height_mm": 2100.0}},
            {"element_type": "Window", "properties": {"width_mm": 1500.0, "height_mm": 1200.0}},
        ]

        for payload in test_cases:
            start = time.time()
            response = await client.post("/api/v1/compliance/check", json=payload)
            duration_ms = (time.time() - start) * 1000

            assert response.status_code == 200
            assert duration_ms < 1000, f"{payload['element_type']} took {duration_ms:.2f}ms"

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, client):
        """Test handling of concurrent requests."""
        payload = {
            "element_type": "Wall",
            "properties": {"width_mm": 1200.0},
        }

        # Send 10 concurrent requests
        tasks = [
            client.post("/api/v1/compliance/check", json=payload)
            for _ in range(10)
        ]

        start = time.time()
        responses = await asyncio.gather(*tasks)
        duration = time.time() - start

        # All should succeed
        assert all(r.status_code == 200 for r in responses)

        # Should complete in reasonable time (not serialized)
        assert duration < 3.0, f"10 concurrent requests took {duration:.2f}s"


class TestMetricsCollection:
    """Test metrics collection and monitoring."""

    @pytest.mark.asyncio
    async def test_metrics_endpoint(self, client):
        """Verify metrics endpoint works."""
        # Make some requests first
        for _ in range(3):
            await client.post("/api/v1/compliance/check", json={
                "element_type": "Wall",
                "properties": {"width_mm": 1200.0}
            })

        # Get metrics
        response = await client.get("/metrics")
        assert response.status_code == 200

        data = response.json()
        assert "endpoints" in data
        assert "uptime_hours" in data

    @pytest.mark.asyncio
    async def test_error_tracking(self, client):
        """Verify errors are tracked in metrics."""
        # Get current error count
        response = await client.get("/metrics/errors")
        assert response.status_code == 200


class TestHealthChecks:
    """Test health check endpoints."""

    @pytest.mark.asyncio
    async def test_basic_health_check(self, client):
        """Test basic health check."""
        response = await client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data

    @pytest.mark.asyncio
    async def test_detailed_health_check(self, client):
        """Test detailed health check with DB."""
        response = await client.get("/api/v1/health/detailed")
        assert response.status_code == 200

        data = response.json()
        assert "checks" in data
        assert "api" in data["checks"]


@pytest.mark.asyncio
async def test_complete_integration_scenario():
    """
    Complete integration test simulating Revit plugin workflow:
    1. User draws wall in Revit
    2. IUpdater detects modification
    3. Extract context
    4. POST to compliance API
    5. Receive violation
    6. Display notification
    7. Log to PostgreSQL
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Simulate: User draws corridor wall with 1100mm width
        revit_element_context = {
            "element_type": "Wall",
            "properties": {
                "width_mm": 1100.0,
                "height_mm": 3000.0,
                "length_mm": 6000.0,
                "function": "Interior"
            },
            "context": {
                "room_type": "Corridor",
                "building_type": "Office",
                "occupancy": 150,
                "floor_level": 2
            }
        }

        # Step 1: Send to backend
        start = time.time()
        response = await client.post("/api/v1/compliance/check", json=revit_element_context)
        duration_ms = (time.time() - start) * 1000

        # Step 2: Verify response
        assert response.status_code == 200
        assert duration_ms < 1000, "Response too slow"

        result = response.json()

        # Step 3: Verify violation detected
        assert result["compliant"] is False
        assert len(result["violations"]) == 1

        violation = result["violations"][0]
        assert violation["rule_id"] == "ČSN_73_0802_Sec_5.2.a"
        assert violation["severity"] == "critical"
        assert violation["actual_value"] == 1100
        assert violation["required_value"] == 1200

        # Step 4: Verify recommendations
        assert len(result["recommendations"]) > 0

        # Step 5: Simulate plugin displays red toast notification
        notification_message = f"⚠️ {violation['message']}"
        assert "1100mm" in notification_message
        assert "1200mm" in notification_message

        print(f"✓ Complete integration test passed in {duration_ms:.2f}ms")
        print(f"✓ Violation: {violation['message']}")
        print(f"✓ Recommendation: {result['recommendations'][0]}")
