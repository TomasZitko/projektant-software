"""
Performance monitoring and metrics collection.
"""
import time
from typing import Dict, Optional, List
from collections import defaultdict
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class RequestMetric:
    """Single request metric data."""

    endpoint: str
    duration_ms: float
    status: str  # success, error, timeout
    timestamp: datetime
    error: Optional[str] = None


@dataclass
class EndpointStats:
    """Aggregated statistics for an endpoint."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_duration_ms: float = 0.0
    min_duration_ms: float = float("inf")
    max_duration_ms: float = 0.0
    durations: List[float] = field(default_factory=list)

    @property
    def avg_duration_ms(self) -> float:
        """Calculate average duration."""
        return self.total_duration_ms / self.total_requests if self.total_requests > 0 else 0

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        return self.successful_requests / self.total_requests if self.total_requests > 0 else 0

    @property
    def p95_duration_ms(self) -> float:
        """Calculate 95th percentile duration."""
        if not self.durations:
            return 0
        sorted_durations = sorted(self.durations)
        idx = int(len(sorted_durations) * 0.95)
        return sorted_durations[idx] if idx < len(sorted_durations) else 0

    @property
    def p99_duration_ms(self) -> float:
        """Calculate 99th percentile duration."""
        if not self.durations:
            return 0
        sorted_durations = sorted(self.durations)
        idx = int(len(sorted_durations) * 0.99)
        return sorted_durations[idx] if idx < len(sorted_durations) else 0


class MetricsCollector:
    """Collects and aggregates performance metrics."""

    def __init__(self, retention_hours: int = 24):
        """
        Initialize metrics collector.

        Args:
            retention_hours: How long to keep metrics in memory
        """
        self.retention_hours = retention_hours
        self.metrics: List[RequestMetric] = []
        self.endpoint_stats: Dict[str, EndpointStats] = defaultdict(EndpointStats)
        self._start_time = datetime.utcnow()

    def record_request(
        self,
        endpoint: str,
        duration_ms: float,
        status: str = "success",
        error: Optional[str] = None,
    ):
        """
        Record a request metric.

        Args:
            endpoint: API endpoint name
            duration_ms: Request duration in milliseconds
            status: Request status (success, error, timeout)
            error: Error message if failed
        """
        metric = RequestMetric(
            endpoint=endpoint,
            duration_ms=duration_ms,
            status=status,
            timestamp=datetime.utcnow(),
            error=error,
        )
        self.metrics.append(metric)

        # Update endpoint statistics
        stats = self.endpoint_stats[endpoint]
        stats.total_requests += 1
        stats.total_duration_ms += duration_ms
        stats.min_duration_ms = min(stats.min_duration_ms, duration_ms)
        stats.max_duration_ms = max(stats.max_duration_ms, duration_ms)
        stats.durations.append(duration_ms)

        if status == "success":
            stats.successful_requests += 1
        else:
            stats.failed_requests += 1

        # Cleanup old metrics
        self._cleanup_old_metrics()

        # Log slow requests
        if duration_ms > 1000:  # > 1 second
            logger.warning(
                f"Slow request detected: {endpoint} took {duration_ms:.2f}ms"
            )

    def _cleanup_old_metrics(self):
        """Remove metrics older than retention period."""
        cutoff = datetime.utcnow() - timedelta(hours=self.retention_hours)
        self.metrics = [m for m in self.metrics if m.timestamp > cutoff]

    def get_endpoint_stats(self, endpoint: str) -> dict:
        """Get statistics for a specific endpoint."""
        stats = self.endpoint_stats.get(endpoint)
        if not stats:
            return {}

        return {
            "endpoint": endpoint,
            "total_requests": stats.total_requests,
            "successful_requests": stats.successful_requests,
            "failed_requests": stats.failed_requests,
            "success_rate": round(stats.success_rate * 100, 2),
            "avg_duration_ms": round(stats.avg_duration_ms, 2),
            "min_duration_ms": round(stats.min_duration_ms, 2),
            "max_duration_ms": round(stats.max_duration_ms, 2),
            "p95_duration_ms": round(stats.p95_duration_ms, 2),
            "p99_duration_ms": round(stats.p99_duration_ms, 2),
        }

    def get_all_stats(self) -> dict:
        """Get statistics for all endpoints."""
        return {
            "uptime_hours": (datetime.utcnow() - self._start_time).total_seconds() / 3600,
            "total_metrics_stored": len(self.metrics),
            "endpoints": {
                endpoint: self.get_endpoint_stats(endpoint)
                for endpoint in self.endpoint_stats.keys()
            },
        }

    def get_recent_errors(self, limit: int = 10) -> List[dict]:
        """Get recent error metrics."""
        errors = [m for m in self.metrics if m.status != "success"]
        errors.sort(key=lambda x: x.timestamp, reverse=True)
        return [
            {
                "endpoint": e.endpoint,
                "error": e.error,
                "duration_ms": e.duration_ms,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in errors[:limit]
        ]

    def reset_stats(self):
        """Reset all statistics."""
        self.metrics.clear()
        self.endpoint_stats.clear()
        self._start_time = datetime.utcnow()
        logger.info("Metrics reset")


# Global metrics collector
metrics_collector = MetricsCollector(retention_hours=24)


class RequestTimer:
    """Context manager for timing requests."""

    def __init__(self, endpoint: str, collector: MetricsCollector = None):
        self.endpoint = endpoint
        self.collector = collector or metrics_collector
        self.start_time: Optional[float] = None
        self.duration_ms: Optional[float] = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            self.duration_ms = (time.time() - self.start_time) * 1000

            if exc_type is None:
                self.collector.record_request(self.endpoint, self.duration_ms, "success")
            else:
                self.collector.record_request(
                    self.endpoint,
                    self.duration_ms,
                    "error",
                    error=str(exc_val) if exc_val else "Unknown error",
                )
        return False  # Don't suppress exceptions
