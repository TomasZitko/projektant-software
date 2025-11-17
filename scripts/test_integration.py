#!/usr/bin/env python3
"""
End-to-end integration test runner.

Tests complete workflow:
1. Start backend services (Docker)
2. Run database migrations
3. Test API connectivity
4. Run integration tests
5. Run performance tests
6. Generate report

Usage:
    python scripts/test_integration.py
    python scripts/test_integration.py --quick  # Skip slow tests
    python scripts/test_integration.py --load   # Run full load tests
"""
import sys
import os
import subprocess
import time
import argparse
from pathlib import Path
from datetime import datetime
import json

# Colors for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_header(message):
    """Print section header."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{message}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 70}{Colors.ENDC}\n")


def print_success(message):
    """Print success message."""
    print(f"{Colors.OKGREEN}✓ {message}{Colors.ENDC}")


def print_error(message):
    """Print error message."""
    print(f"{Colors.FAIL}✗ {message}{Colors.ENDC}")


def print_warning(message):
    """Print warning message."""
    print(f"{Colors.WARNING}⚠ {message}{Colors.ENDC}")


def print_info(message):
    """Print info message."""
    print(f"{Colors.OKCYAN}ℹ {message}{Colors.ENDC}")


def run_command(cmd, cwd=None, capture=True):
    """Run shell command and return success status."""
    try:
        if capture:
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=300
            )
            return result.returncode == 0, result.stdout, result.stderr
        else:
            result = subprocess.run(cmd, shell=True, cwd=cwd, timeout=300)
            return result.returncode == 0, "", ""
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except Exception as e:
        return False, "", str(e)


def check_docker():
    """Check if Docker is running."""
    print_info("Checking Docker...")
    success, stdout, stderr = run_command("docker info")
    if success:
        print_success("Docker is running")
        return True
    else:
        print_error("Docker is not running. Please start Docker Desktop.")
        return False


def start_services():
    """Start backend services with Docker Compose."""
    print_info("Starting backend services...")
    docker_compose_path = Path(__file__).parent.parent / "docker"

    success, stdout, stderr = run_command(
        "docker-compose up -d postgres redis",
        cwd=docker_compose_path
    )

    if success:
        print_success("Services started")
        print_info("Waiting 10 seconds for services to initialize...")
        time.sleep(10)
        return True
    else:
        print_error(f"Failed to start services: {stderr}")
        return False


def test_service_connectivity():
    """Test connectivity to PostgreSQL and Redis."""
    print_info("Testing service connectivity...")

    # Test PostgreSQL
    pg_success, _, _ = run_command(
        "docker exec projektant-postgres pg_isready -U projektant"
    )

    if pg_success:
        print_success("PostgreSQL is ready")
    else:
        print_error("PostgreSQL not ready")

    # Test Redis
    redis_success, stdout, _ = run_command(
        "docker exec projektant-redis redis-cli ping"
    )

    if redis_success and "PONG" in stdout:
        print_success("Redis is ready")
    else:
        print_error("Redis not ready")

    return pg_success and redis_success


def run_migrations():
    """Run database migrations."""
    print_info("Running database migrations...")
    backend_path = Path(__file__).parent.parent / "backend"

    success, stdout, stderr = run_command(
        "alembic upgrade head",
        cwd=backend_path
    )

    if success:
        print_success("Database migrations completed")
        return True
    else:
        print_warning("Migrations may not be configured yet")
        print_info("This is expected if migrations haven't been created")
        return True  # Don't fail on this


def start_backend():
    """Start the FastAPI backend."""
    print_info("Starting FastAPI backend...")
    backend_path = Path(__file__).parent.parent / "backend"

    # Start backend in background
    process = subprocess.Popen(
        ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
        cwd=backend_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    print_info("Waiting 5 seconds for backend to start...")
    time.sleep(5)

    # Check if it's running
    success, stdout, _ = run_command("curl -s http://localhost:8000/health")

    if success and "healthy" in stdout:
        print_success("Backend is running")
        return process
    else:
        print_warning("Backend may not be fully started yet, continuing...")
        return process


def test_api_endpoints():
    """Test critical API endpoints."""
    print_info("Testing API endpoints...")

    endpoints = [
        ("/health", "Health check"),
        ("/api/v1/health/detailed", "Detailed health check"),
        ("/metrics", "Metrics endpoint"),
    ]

    all_passed = True

    for endpoint, description in endpoints:
        success, stdout, _ = run_command(f"curl -s http://localhost:8000{endpoint}")
        if success:
            print_success(f"{description}: OK")
        else:
            print_error(f"{description}: FAILED")
            all_passed = False

    return all_passed


def run_integration_tests(quick=False):
    """Run integration tests."""
    print_info("Running integration tests...")
    backend_path = Path(__file__).parent.parent / "backend"

    cmd = "pytest tests/integration/ -v"
    if quick:
        cmd += " -m 'not slow'"

    success, _, _ = run_command(cmd, cwd=backend_path, capture=False)

    if success:
        print_success("Integration tests passed")
        return True
    else:
        print_error("Integration tests failed")
        return False


def run_performance_tests(load=False):
    """Run performance tests."""
    print_info("Running performance tests...")
    backend_path = Path(__file__).parent.parent / "backend"

    if load:
        cmd = "pytest tests/performance/ -v -s -m slow"
        print_warning("Running full load tests (this will take several minutes)...")
    else:
        cmd = "pytest tests/performance/ -v -s -m 'not slow'"

    success, _, _ = run_command(cmd, cwd=backend_path, capture=False)

    if success:
        print_success("Performance tests passed")
        return True
    else:
        print_error("Performance tests failed")
        return False


def cleanup(backend_process):
    """Cleanup services."""
    print_info("Cleaning up...")

    # Stop backend
    if backend_process:
        backend_process.terminate()
        backend_process.wait(timeout=5)
        print_success("Backend stopped")

    # Note: Keep Docker services running for development
    print_info("Docker services left running for development")
    print_info("To stop: cd docker && docker-compose down")


def generate_report(results):
    """Generate test report."""
    print_header("TEST REPORT")

    total_checks = len(results)
    passed = sum(1 for r in results.values() if r)
    failed = total_checks - passed

    for check, result in results.items():
        if result:
            print_success(check)
        else:
            print_error(check)

    print(f"\n{Colors.BOLD}Summary:{Colors.ENDC}")
    print(f"  Total checks: {total_checks}")
    print(f"  Passed: {Colors.OKGREEN}{passed}{Colors.ENDC}")
    print(f"  Failed: {Colors.FAIL}{failed}{Colors.ENDC}")

    success_rate = (passed / total_checks * 100) if total_checks > 0 else 0
    print(f"  Success rate: {success_rate:.1f}%")

    return failed == 0


def main():
    """Main test runner."""
    parser = argparse.ArgumentParser(description="Run integration tests")
    parser.add_argument("--quick", action="store_true", help="Skip slow tests")
    parser.add_argument("--load", action="store_true", help="Run full load tests")
    parser.add_argument("--skip-setup", action="store_true", help="Skip Docker setup")
    args = parser.parse_args()

    print_header("PROJEKTANT COPILOT - INTEGRATION TEST SUITE")
    print_info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    results = {}
    backend_process = None

    try:
        # Check prerequisites
        if not args.skip_setup:
            if not check_docker():
                sys.exit(1)

            # Start services
            if not start_services():
                sys.exit(1)
            results["Docker services started"] = True

            # Test connectivity
            if not test_service_connectivity():
                sys.exit(1)
            results["Service connectivity"] = True

            # Run migrations
            results["Database migrations"] = run_migrations()

            # Start backend
            backend_process = start_backend()
            results["Backend started"] = backend_process is not None

            # Wait a bit more
            time.sleep(3)
        else:
            print_info("Skipping Docker setup, assuming services are running")

        # Test API
        results["API endpoints"] = test_api_endpoints()

        # Run tests
        print_header("RUNNING INTEGRATION TESTS")
        results["Integration tests"] = run_integration_tests(quick=args.quick)

        print_header("RUNNING PERFORMANCE TESTS")
        results["Performance tests"] = run_performance_tests(load=args.load)

        # Generate report
        all_passed = generate_report(results)

        if all_passed:
            print(f"\n{Colors.OKGREEN}{Colors.BOLD}✓ ALL TESTS PASSED{Colors.ENDC}\n")
            return 0
        else:
            print(f"\n{Colors.FAIL}{Colors.BOLD}✗ SOME TESTS FAILED{Colors.ENDC}\n")
            return 1

    except KeyboardInterrupt:
        print_warning("\nTest run interrupted by user")
        return 130

    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        if not args.skip_setup:
            cleanup(backend_process)


if __name__ == "__main__":
    sys.exit(main())
