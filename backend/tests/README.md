# Test Suite Documentation

## 📋 Overview

Comprehensive test suite for Projektant Copilot backend, including integration tests, performance tests, and load tests.

## 🗂️ Test Structure

```
tests/
├── integration/
│   └── test_compliance_integration.py    # End-to-end workflow tests
├── performance/
│   └── test_load.py                      # Load and performance tests
└── README.md                             # This file
```

## 🚀 Quick Start

### Prerequisites

```bash
# Start Docker services
cd docker
docker-compose up -d postgres redis

# Install dependencies
cd ../backend
pip install -r requirements.txt
```

### Run All Tests

```bash
# From project root
python scripts/test_integration.py

# Or from backend directory
pytest tests/ -v
```

## 🧪 Test Categories

### 1. Integration Tests

**Location:** `tests/integration/test_compliance_integration.py`

**What they test:**
- Full end-to-end workflow (Revit → API → Cache → Database)
- Redis caching behavior
- PostgreSQL logging
- Error handling scenarios
- API endpoint responses
- Health checks

**Run:**
```bash
pytest tests/integration/ -v
```

**Example output:**
```
tests/integration/test_compliance_integration.py::TestEndToEndWorkflow::test_full_workflow_compliant_element PASSED
tests/integration/test_compliance_integration.py::TestEndToEndWorkflow::test_full_workflow_violation_detected PASSED
tests/integration/test_compliance_integration.py::TestCacheBehavior::test_cache_hit_performance PASSED
tests/integration/test_compliance_integration.py::TestErrorHandling::test_invalid_element_type PASSED
```

### 2. Performance Tests

**Location:** `tests/performance/test_load.py`

**What they test:**
- Response time requirements (<1 second)
- Concurrent request handling
- Cache effectiveness
- Memory leak detection
- Database connection pool stress

**Run:**
```bash
pytest tests/performance/ -v -s -m "not slow"
```

**Run with slow tests:**
```bash
pytest tests/performance/ -v -s -m slow
```

### 3. Load Tests

**Included tests:**
- **Burst load:** 1000 requests in rapid succession
- **Sustained load:** 100 requests/minute for 10 minutes
- **Connection pool stress:** 50 concurrent connections
- **Memory leak detection:** Repeated requests with memory monitoring

**Run:**
```bash
# Full load test suite (takes ~15 minutes)
pytest tests/performance/test_load.py -v -s -m slow

# Quick version (scaled down)
pytest tests/performance/test_load.py -v -s
```

## 📊 Test Scenarios

### Scenario 1: Compliant Element

```python
# Input
{
  "element_type": "Wall",
  "properties": {"width_mm": 1500.0},
  "context": {"room_type": "Corridor", "occupancy": 150}
}

# Expected
{
  "compliant": true,
  "violations": [],
  "recommendations": []
}
```

### Scenario 2: Non-Compliant Corridor Width

```python
# Input
{
  "element_type": "Wall",
  "properties": {"width_mm": 1100.0},
  "context": {"room_type": "Corridor", "occupancy": 150}
}

# Expected
{
  "compliant": false,
  "violations": [
    {
      "rule_id": "ČSN_73_0802_Sec_5.2.a",
      "severity": "critical",
      "message": "Corridor width (1100mm) < minimum 1200mm",
      "required_value": 1200,
      "actual_value": 1100
    }
  ]
}
```

### Scenario 3: High Occupancy (>200 people)

```python
# Input
{
  "element_type": "Wall",
  "properties": {"width_mm": 1300.0},
  "context": {"room_type": "Corridor", "occupancy": 250}
}

# Expected
{
  "compliant": false,  # Needs 1500mm for high occupancy
  "violations": [{"required_value": 1500, "actual_value": 1300}]
}
```

## 🎯 Performance Targets

| Metric | Target | Test Coverage |
|--------|--------|---------------|
| Response time (avg) | <500ms | ✅ test_response_time_under_1_second |
| Response time (P95) | <1000ms | ✅ test_1000_compliance_checks |
| Concurrent requests | 50 | ✅ test_concurrent_requests |
| Cache speedup | >2x | ✅ test_cache_hit_performance |
| Success rate | >99.5% | ✅ test_1000_compliance_checks |
| Memory stability | No leaks | ✅ test_memory_leak_detection |

## 🔍 Test Markers

Tests are marked for selective execution:

```python
@pytest.mark.slow       # Long-running tests (load tests)
@pytest.mark.asyncio    # Async tests (all API tests)
```

**Usage:**
```bash
# Skip slow tests
pytest -m "not slow"

# Only slow tests
pytest -m slow

# Only async tests
pytest -m asyncio
```

## 📈 Load Test Results

### Example Output

```
═══════════════════════════════════════════════════════════════
LOAD TEST: 1000 Compliance Checks
═══════════════════════════════════════════════════════════════

  Completed: 100/1000 requests
  Completed: 200/1000 requests
  ...
  Completed: 1000/1000 requests

───────────────────────────────────────────────────────────────
RESULTS:
───────────────────────────────────────────────────────────────
Total requests:      1000
Successful:          1000 (100.0%)
Failed:              0 (0.0%)
Total duration:      11.82s
Requests/second:     84.60

Response Times (ms):
  Min:               42.34
  Average:           245.67
  Median:            198.45
  95th percentile:   456.23
  99th percentile:   723.12
  Max:               945.67

Memory:
  Delta:             2847.32 KB
═══════════════════════════════════════════════════════════════
```

## 🛠️ Troubleshooting

### Tests fail with "Connection refused"

**Problem:** Backend services not running

**Fix:**
```bash
# Start services
cd docker
docker-compose up -d postgres redis

# Start backend
cd ../backend
python -m uvicorn app.main:app --reload
```

### Tests fail with "Database not initialized"

**Problem:** Database migrations not run

**Fix:**
```bash
cd backend
alembic upgrade head
```

### Cache tests fail

**Problem:** Redis not running

**Fix:**
```bash
docker-compose up -d redis

# Verify
docker exec projektant-redis redis-cli ping
# Should return: PONG
```

### Slow tests timeout

**Problem:** Default timeout too short

**Fix:**
```bash
# Increase timeout
pytest tests/performance/ -v -s --timeout=600
```

## 📝 Writing New Tests

### Integration Test Template

```python
@pytest.mark.asyncio
async def test_my_feature(client, db_session):
    """Test description."""
    # Arrange
    payload = {
        "element_type": "Wall",
        "properties": {"width_mm": 1200.0}
    }

    # Act
    response = await client.post("/api/v1/compliance/check", json=payload)

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["compliant"] is True
```

### Performance Test Template

```python
@pytest.mark.asyncio
async def test_performance_requirement(client):
    """Test that response is fast enough."""
    import time

    start = time.time()
    response = await client.post("/api/v1/compliance/check", json={...})
    duration_ms = (time.time() - start) * 1000

    assert response.status_code == 200
    assert duration_ms < 1000, f"Too slow: {duration_ms:.2f}ms"
```

## 🎯 CI/CD Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s

      redis:
        image: redis:7
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s

    steps:
      - uses: actions/checkout@v2

      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt

      - name: Run tests
        run: |
          cd backend
          pytest tests/ -v --cov=app --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

## 📚 Additional Resources

- [Integration Guide](../../docs/INTEGRATION_GUIDE.md)
- [API Documentation](http://localhost:8000/docs)
- [pytest Documentation](https://docs.pytest.org/)
- [httpx Documentation](https://www.python-httpx.org/)

## ✅ Success Criteria

Before deploying to production, ensure:

- [ ] All integration tests pass (100%)
- [ ] All performance tests meet targets
- [ ] Load test handles 1000 requests successfully
- [ ] No memory leaks detected
- [ ] Cache provides >2x speedup
- [ ] Error handling works for all scenarios
- [ ] Database logging works correctly
- [ ] Metrics collection is accurate

---

**Test Coverage Goal:** >90%
**Current Coverage:** (Run `pytest --cov=app --cov-report=html` to generate)
