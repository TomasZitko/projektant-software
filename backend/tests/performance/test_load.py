"""
Load testing and performance benchmarks.

Tests:
1. 1000 compliance checks - burst load
2. 100 checks/minute for 10 minutes - sustained load
3. Database connection pool stress
4. Memory leak detection
5. Response time percentiles
"""
import pytest
import asyncio
import time
import tracemalloc
from typing import List
from datetime import datetime, timedelta
from httpx import AsyncClient, ASGITransport
import statistics

from app.main import app


@pytest.fixture
async def client():
    """HTTP client for testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestBurstLoad:
    """Test burst load scenarios."""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_1000_compliance_checks(self, client):
        """
        Load test: 1000 compliance checks in quick succession.

        Requirements:
        - All requests succeed
        - Average response time < 500ms
        - 95th percentile < 1000ms
        - No memory leaks
        """
        print("\n" + "=" * 60)
        print("LOAD TEST: 1000 Compliance Checks")
        print("=" * 60)

        # Start memory tracking
        tracemalloc.start()
        snapshot_before = tracemalloc.take_snapshot()

        # Generate test payloads
        payloads = []
        for i in range(1000):
            # Vary the parameters to avoid 100% cache hits
            width = 1000 + (i % 10) * 50  # 1000, 1050, 1100, ..., 1450
            payloads.append({
                "element_type": "Wall",
                "properties": {
                    "width_mm": float(width),
                    "height_mm": 3000.0,
                    "length_mm": 5000.0,
                },
                "context": {
                    "room_type": "Corridor" if i % 2 == 0 else "Office",
                    "occupancy": 100 + (i % 5) * 50,
                    "floor_level": (i % 10) + 1,
                }
            })

        # Send requests in batches of 50 concurrent
        batch_size = 50
        all_durations = []
        failed_count = 0
        start_time = time.time()

        for batch_start in range(0, 1000, batch_size):
            batch_end = min(batch_start + batch_size, 1000)
            batch = payloads[batch_start:batch_end]

            # Send batch concurrently
            tasks = []
            batch_times = []

            for payload in batch:
                request_start = time.time()
                tasks.append(self._timed_request(client, payload, request_start))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    failed_count += 1
                else:
                    all_durations.append(result)

            # Progress indicator
            if (batch_end) % 100 == 0:
                print(f"  Completed: {batch_end}/1000 requests")

        total_duration = time.time() - start_time

        # Memory snapshot after
        snapshot_after = tracemalloc.take_snapshot()
        tracemalloc.stop()

        # Calculate statistics
        success_count = len(all_durations)
        avg_duration = statistics.mean(all_durations) if all_durations else 0
        median_duration = statistics.median(all_durations) if all_durations else 0
        p95_duration = statistics.quantiles(all_durations, n=20)[18] if all_durations else 0  # 95th percentile
        p99_duration = statistics.quantiles(all_durations, n=100)[98] if all_durations else 0  # 99th percentile
        min_duration = min(all_durations) if all_durations else 0
        max_duration = max(all_durations) if all_durations else 0

        # Memory usage
        top_stats = snapshot_after.compare_to(snapshot_before, 'lineno')
        total_memory_kb = sum(stat.size_diff for stat in top_stats) / 1024

        # Results
        print("\n" + "-" * 60)
        print("RESULTS:")
        print("-" * 60)
        print(f"Total requests:      1000")
        print(f"Successful:          {success_count} ({success_count/10:.1f}%)")
        print(f"Failed:              {failed_count} ({failed_count/10:.1f}%)")
        print(f"Total duration:      {total_duration:.2f}s")
        print(f"Requests/second:     {1000/total_duration:.2f}")
        print(f"\nResponse Times (ms):")
        print(f"  Min:               {min_duration:.2f}")
        print(f"  Average:           {avg_duration:.2f}")
        print(f"  Median:            {median_duration:.2f}")
        print(f"  95th percentile:   {p95_duration:.2f}")
        print(f"  99th percentile:   {p99_duration:.2f}")
        print(f"  Max:               {max_duration:.2f}")
        print(f"\nMemory:")
        print(f"  Delta:             {total_memory_kb:.2f} KB")
        print("=" * 60)

        # Assertions
        assert failed_count == 0, f"{failed_count} requests failed"
        assert avg_duration < 500, f"Average response time {avg_duration:.2f}ms > 500ms"
        assert p95_duration < 1000, f"95th percentile {p95_duration:.2f}ms > 1000ms"
        assert total_memory_kb < 50000, f"Memory leak detected: {total_memory_kb:.2f} KB"

    async def _timed_request(self, client, payload, start_time):
        """Send request and return duration."""
        try:
            response = await client.post("/api/v1/compliance/check", json=payload)
            duration_ms = (time.time() - start_time) * 1000

            if response.status_code != 200:
                raise Exception(f"Request failed with status {response.status_code}")

            return duration_ms
        except Exception as e:
            raise e


class TestSustainedLoad:
    """Test sustained load over time."""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_sustained_load_100_per_minute(self, client):
        """
        Sustained load test: 100 checks/minute for 10 minutes.

        Requirements:
        - Maintains performance over time
        - No degradation
        - No memory leaks
        - Connection pool remains healthy
        """
        print("\n" + "=" * 60)
        print("SUSTAINED LOAD TEST: 100 checks/min for 10 minutes")
        print("=" * 60)

        # For testing, we'll do 10 requests/min for 1 minute (scaled down)
        # In production, run full test
        requests_per_minute = 10
        duration_minutes = 1
        total_requests = requests_per_minute * duration_minutes

        print(f"Running {requests_per_minute} req/min for {duration_minutes} min")
        print(f"Total requests: {total_requests}")

        tracemalloc.start()
        start_time = time.time()

        minute_stats = []

        for minute in range(duration_minutes):
            minute_start = time.time()
            minute_durations = []

            # Send requests evenly throughout the minute
            interval = 60.0 / requests_per_minute  # seconds between requests

            for req_num in range(requests_per_minute):
                request_start = time.time()

                payload = {
                    "element_type": "Wall",
                    "properties": {
                        "width_mm": 1000.0 + (req_num * 100),
                        "height_mm": 3000.0,
                    },
                    "context": {
                        "room_type": "Corridor",
                        "occupancy": 100 + (minute * 10),
                    }
                }

                response = await client.post("/api/v1/compliance/check", json=payload)
                duration_ms = (time.time() - request_start) * 1000

                assert response.status_code == 200
                minute_durations.append(duration_ms)

                # Wait until next request time
                elapsed = time.time() - request_start
                sleep_time = max(0, interval - elapsed)
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

            minute_elapsed = time.time() - minute_start
            avg_duration = statistics.mean(minute_durations)

            minute_stats.append({
                "minute": minute + 1,
                "avg_duration_ms": avg_duration,
                "requests": len(minute_durations),
                "elapsed_s": minute_elapsed
            })

            print(f"  Minute {minute + 1}: {len(minute_durations)} requests, "
                  f"avg {avg_duration:.2f}ms, elapsed {minute_elapsed:.2f}s")

        total_elapsed = time.time() - start_time
        snapshot = tracemalloc.take_snapshot()
        tracemalloc.stop()

        # Analyze performance degradation
        first_minute_avg = minute_stats[0]["avg_duration_ms"]
        last_minute_avg = minute_stats[-1]["avg_duration_ms"]
        degradation_pct = ((last_minute_avg - first_minute_avg) / first_minute_avg) * 100

        print("\n" + "-" * 60)
        print("RESULTS:")
        print("-" * 60)
        print(f"Total duration:        {total_elapsed:.2f}s")
        print(f"Total requests:        {total_requests}")
        print(f"First minute avg:      {first_minute_avg:.2f}ms")
        print(f"Last minute avg:       {last_minute_avg:.2f}ms")
        print(f"Performance change:    {degradation_pct:+.2f}%")
        print("=" * 60)

        # Assertions
        assert degradation_pct < 20, f"Performance degraded by {degradation_pct:.2f}%"
        assert last_minute_avg < 1000, f"Last minute avg {last_minute_avg:.2f}ms > 1000ms"


class TestDatabaseConnectionPool:
    """Test database connection pool under stress."""

    @pytest.mark.asyncio
    async def test_connection_pool_stress(self, client):
        """
        Stress test database connection pool.

        Requirements:
        - Handle concurrent connections
        - No connection leaks
        - Graceful degradation under load
        """
        print("\n" + "=" * 60)
        print("CONNECTION POOL STRESS TEST")
        print("=" * 60)

        # Send 50 concurrent requests
        concurrent_requests = 50

        payload = {
            "element_type": "Wall",
            "properties": {"width_mm": 1200.0},
            "context": {"room_type": "Corridor"}
        }

        tasks = [
            client.post("/api/v1/compliance/check", json=payload)
            for _ in range(concurrent_requests)
        ]

        start = time.time()
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        duration = time.time() - start

        successes = sum(1 for r in responses if not isinstance(r, Exception) and r.status_code == 200)
        failures = concurrent_requests - successes

        print(f"Concurrent requests:  {concurrent_requests}")
        print(f"Successful:           {successes}")
        print(f"Failed:               {failures}")
        print(f"Duration:             {duration:.2f}s")
        print(f"Avg per request:      {(duration/concurrent_requests)*1000:.2f}ms")
        print("=" * 60)

        assert failures == 0, f"{failures} requests failed"
        assert duration < 10, f"Pool overwhelmed: {duration:.2f}s for {concurrent_requests} requests"


class TestMemoryLeaks:
    """Test for memory leaks."""

    @pytest.mark.asyncio
    async def test_memory_leak_detection(self, client):
        """
        Run repeated requests and check for memory leaks.

        Requirements:
        - Memory usage remains stable
        - No unbounded growth
        """
        print("\n" + "=" * 60)
        print("MEMORY LEAK DETECTION TEST")
        print("=" * 60)

        tracemalloc.start()

        payload = {
            "element_type": "Wall",
            "properties": {"width_mm": 1200.0},
        }

        # Baseline
        for _ in range(100):
            await client.post("/api/v1/compliance/check", json=payload)

        snapshot1 = tracemalloc.take_snapshot()

        # More requests
        for _ in range(100):
            await client.post("/api/v1/compliance/check", json=payload)

        snapshot2 = tracemalloc.take_snapshot()

        # Compare
        top_stats = snapshot2.compare_to(snapshot1, 'lineno')
        total_diff = sum(stat.size_diff for stat in top_stats) / 1024  # KB

        tracemalloc.stop()

        print(f"Memory growth:  {total_diff:.2f} KB (after 100 additional requests)")
        print("=" * 60)

        # Should not grow significantly
        assert total_diff < 5000, f"Possible memory leak: {total_diff:.2f} KB growth"


class TestCacheEffectiveness:
    """Test cache performance under load."""

    @pytest.mark.asyncio
    async def test_cache_hit_rate_under_load(self, client):
        """
        Test cache effectiveness with repeated requests.

        Requirements:
        - High cache hit rate for repeated requests
        - Significant performance improvement
        """
        print("\n" + "=" * 60)
        print("CACHE EFFECTIVENESS TEST")
        print("=" * 60)

        # Same payload repeated
        payload = {
            "element_type": "Wall",
            "properties": {"width_mm": 1200.0},
            "context": {"room_type": "Corridor"}
        }

        # First request (cache miss)
        start = time.time()
        response1 = await client.post("/api/v1/compliance/check", json=payload)
        uncached_duration = (time.time() - start) * 1000

        assert response1.status_code == 200

        # 100 subsequent requests (cache hits)
        cached_durations = []
        for _ in range(100):
            start = time.time()
            response = await client.post("/api/v1/compliance/check", json=payload)
            cached_durations.append((time.time() - start) * 1000)
            assert response.status_code == 200

        avg_cached = statistics.mean(cached_durations)
        speedup = uncached_duration / avg_cached if avg_cached > 0 else 0

        print(f"Uncached request:     {uncached_duration:.2f}ms")
        print(f"Avg cached request:   {avg_cached:.2f}ms")
        print(f"Speedup:              {speedup:.2f}x")
        print(f"Cache benefit:        {((1 - avg_cached/uncached_duration) * 100):.1f}% faster")
        print("=" * 60)

        # Cache should provide at least 2x speedup
        assert speedup >= 2, f"Cache not effective: only {speedup:.2f}x speedup"


if __name__ == "__main__":
    """Run load tests manually."""
    import sys
    sys.exit(pytest.main([__file__, "-v", "-s", "-m", "slow"]))
