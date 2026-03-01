"""Metrics collection for monitoring system performance."""

import asyncio
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from functools import wraps
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class MetricType(str, Enum):
    """Types of metrics."""

    COUNTER = "counter"  # Incrementing value
    GAUGE = "gauge"  # Current value
    HISTOGRAM = "histogram"  # Distribution of values
    SUMMARY = "summary"  # Statistical summary


@dataclass
class MetricValue:
    """A metric value with timestamp."""

    value: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class Histogram:
    """Histogram for tracking value distributions."""

    count: int = 0
    sum: float = 0.0
    buckets: dict[float, int] = field(default_factory=dict)

    # Standard bucket values for response times (seconds)
    DEFAULT_BUCKETS = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]

    def observe(self, value: float, buckets: list[float] | None = None) -> None:
        """Observe a value.

        Args:
            value: Value to observe
            buckets: Optional custom buckets
        """
        self.count += 1
        self.sum += value

        bucket_values = buckets or self.DEFAULT_BUCKETS

        for bucket in sorted(bucket_values):
            if value <= bucket:
                self.buckets[bucket] = self.buckets.get(bucket, 0) + 1

    def get_quantile(self, quantile: float) -> float:
        """Calculate approximate quantile.

        Args:
            quantile: Quantile (0.0 to 1.0)

        Returns:
            Approximate value at quantile
        """
        if self.count == 0:
            return 0.0

        target_count = int(self.count * quantile)

        accumulated = 0
        for bucket in sorted(self.buckets.keys()):
            accumulated += self.buckets[bucket]
            if accumulated >= target_count:
                return bucket

        return float("inf")


@dataclass
class Summary:
    """Statistical summary of values."""

    count: int = 0
    sum: float = 0.0
    min: float = float("inf")
    max: float = float("-inf")
    samples: deque[float] = field(default_factory=lambda: deque(maxlen=1000))

    def observe(self, value: float) -> None:
        """Observe a value.

        Args:
            value: Value to observe
        """
        self.count += 1
        self.sum += value
        self.min = min(self.min, value)
        self.max = max(self.max, value)
        self.samples.append(value)

    def get_average(self) -> float:
        """Get average value.

        Returns:
            Average or 0 if no samples
        """
        return self.sum / self.count if self.count > 0 else 0.0


class Metric:
    """A metric with values."""

    def __init__(
        self,
        name: str,
        description: str,
        metric_type: MetricType,
        labels: list[str] | None = None,
    ) -> None:
        """Initialize metric.

        Args:
            name: Metric name
            description: Metric description
            metric_type: Type of metric
            labels: Optional label names
        """
        self.name = name
        self.description = description
        self.metric_type = metric_type
        self.label_names = labels or []
        self._values: dict[tuple[str, ...], MetricValue] = {}
        self._histograms: dict[tuple[str, ...], Histogram] = {}
        self._summaries: dict[tuple[str, ...], Summary] = {}
        self._created_at = datetime.now(timezone.utc)

    def inc(
        self,
        value: float = 1.0,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Increment counter.

        Args:
            value: Amount to increment
            labels: Optional label values
        """
        if self.metric_type != MetricType.COUNTER:
            raise ValueError(f"Cannot increment {self.metric_type} metric")

        key = self._make_label_key(labels)
        current = self._values.get(key, MetricValue(value=0.0))
        current.value += value
        current.timestamp = datetime.now(timezone.utc)
        self._values[key] = current

    def set(
        self,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Set gauge value.

        Args:
            value: Value to set
            labels: Optional label values
        """
        if self.metric_type != MetricType.GAUGE:
            raise ValueError(f"Cannot set {self.metric_type} metric")

        key = self._make_label_key(labels)
        self._values[key] = MetricValue(
            value=value,
            labels=labels or {},
        )

    def observe(
        self,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Observe a value for histogram/summary.

        Args:
            value: Value to observe
            labels: Optional label values
        """
        key = self._make_label_key(labels)

        if self.metric_type == MetricType.HISTOGRAM:
            if key not in self._histograms:
                self._histograms[key] = Histogram()
            self._histograms[key].observe(value)

        elif self.metric_type == MetricType.SUMMARY:
            if key not in self._summaries:
                self._summaries[key] = Summary()
            self._summaries[key].observe(value)

    def get(self) -> dict[str, Any]:
        """Get metric values.

        Returns:
            Metric data
        """
        data = {
            "name": self.name,
            "description": self.description,
            "type": self.metric_type.value,
            "created_at": self._created_at.isoformat(),
        }

        if self.metric_type == MetricType.COUNTER:
            data["values"] = [
                {
                    "value": v.value,
                    "labels": v.labels,
                    "timestamp": v.timestamp.isoformat(),
                }
                for v in self._values.values()
            ]

        elif self.metric_type == MetricType.GAUGE:
            data["values"] = [
                {
                    "value": v.value,
                    "labels": v.labels,
                    "timestamp": v.timestamp.isoformat(),
                }
                for v in self._values.values()
            ]

        elif self.metric_type == MetricType.HISTOGRAM:
            data["histograms"] = []
            for key, hist in self._histograms.items():
                data["histograms"].append({
                    "count": hist.count,
                    "sum": hist.sum,
                    "buckets": hist.buckets,
                    "p50": hist.get_quantile(0.5),
                    "p95": hist.get_quantile(0.95),
                    "p99": hist.get_quantile(0.99),
                })

        elif self.metric_type == MetricType.SUMMARY:
            data["summaries"] = []
            for key, summary in self._summaries.items():
                data["summaries"].append({
                    "count": summary.count,
                    "sum": summary.sum,
                    "min": summary.min,
                    "max": summary.max,
                    "average": summary.get_average(),
                })

        return data

    def _make_label_key(self, labels: dict[str, str] | None) -> tuple[str, ...]:
        """Create key from labels.

        Args:
            labels: Label values

        Returns:
            Tuple key
        """
        if not labels:
            return ()

        # Ensure consistent order
        return tuple(labels.get(name, "") for name in self.label_names)


class MetricsRegistry:
    """Registry for metrics."""

    def __init__(self) -> None:
        """Initialize registry."""
        self._metrics: dict[str, Metric] = {}
        self._created_at = datetime.now(timezone.utc)

    def create_counter(
        self,
        name: str,
        description: str,
        labels: list[str] | None = None,
    ) -> Metric:
        """Create a counter metric.

        Args:
            name: Metric name
            description: Metric description
            labels: Optional label names

        Returns:
            Created metric
        """
        return self._create_metric(
            name=name,
            description=description,
            metric_type=MetricType.COUNTER,
            labels=labels,
        )

    def create_gauge(
        self,
        name: str,
        description: str,
        labels: list[str] | None = None,
    ) -> Metric:
        """Create a gauge metric.

        Args:
            name: Metric name
            description: Metric description
            labels: Optional label names

        Returns:
            Created metric
        """
        return self._create_metric(
            name=name,
            description=description,
            metric_type=MetricType.GAUGE,
            labels=labels,
        )

    def create_histogram(
        self,
        name: str,
        description: str,
        labels: list[str] | None = None,
    ) -> Metric:
        """Create a histogram metric.

        Args:
            name: Metric name
            description: Metric description
            labels: Optional label names

        Returns:
            Created metric
        """
        return self._create_metric(
            name=name,
            description=description,
            metric_type=MetricType.HISTOGRAM,
            labels=labels,
        )

    def create_summary(
        self,
        name: str,
        description: str,
        labels: list[str] | None = None,
    ) -> Metric:
        """Create a summary metric.

        Args:
            name: Metric name
            description: Metric description
            labels: Optional label names

        Returns:
            Created metric
        """
        return self._create_metric(
            name=name,
            description=description,
            metric_type=MetricType.SUMMARY,
            labels=labels,
        )

    def _create_metric(
        self,
        name: str,
        description: str,
        metric_type: MetricType,
        labels: list[str] | None = None,
    ) -> Metric:
        """Create a metric.

        Args:
            name: Metric name
            description: Metric description
            metric_type: Type of metric
            labels: Optional label names

        Returns:
            Created metric
        """
        if name in self._metrics:
            return self._metrics[name]

        metric = Metric(
            name=name,
            description=description,
            metric_type=metric_type,
            labels=labels,
        )

        self._metrics[name] = metric
        return metric

    def get_metric(self, name: str) -> Metric | None:
        """Get a metric by name.

        Args:
            name: Metric name

        Returns:
            Metric or None
        """
        return self._metrics.get(name)

    def get_all(self) -> dict[str, dict[str, Any]]:
        """Get all metrics.

        Returns:
            Dictionary of metric data
        """
        return {
            name: metric.get()
            for name, metric in self._metrics.items()
        }

    def reset(self) -> None:
        """Reset all metrics."""
        self._metrics.clear()


# Global registry
registry = MetricsRegistry()


def get_registry() -> MetricsRegistry:
    """Get global metrics registry.

    Returns:
        Metrics registry
    """
    return registry


# Default metrics
def init_default_metrics() -> None:
    """Initialize default application metrics."""
    # HTTP metrics
    registry.create_counter(
        "http_requests_total",
        "Total HTTP requests",
        labels=["method", "endpoint", "status"],
    )
    registry.create_histogram(
        "http_request_duration_seconds",
        "HTTP request duration",
        labels=["method", "endpoint"],
    )
    registry.create_gauge(
        "http_requests_in_progress",
        "HTTP requests currently in progress",
        labels=["method", "endpoint"],
    )

    # Database metrics
    registry.create_counter(
        "db_queries_total",
        "Total database queries",
        labels=["operation", "table"],
    )
    registry.create_histogram(
        "db_query_duration_seconds",
        "Database query duration",
        labels=["operation", "table"],
    )

    # LLM metrics
    registry.create_counter(
        "llm_requests_total",
        "Total LLM requests",
        labels=["provider", "model"],
    )
    registry.create_histogram(
        "llm_request_duration_seconds",
        "LLM request duration",
        labels=["provider", "model"],
    )
    registry.create_counter(
        "llm_tokens_total",
        "Total LLM tokens processed",
        labels=["provider", "model", "type"],
    )

    # Tour metrics
    registry.create_counter(
        "tours_created_total",
        "Total tours created",
    )
    registry.create_gauge(
        "tours_active",
        "Currently active tours",
    )
    registry.create_histogram(
        "tour_duration_seconds",
        "Tour duration",
    )

    # Translation metrics
    registry.create_counter(
        "translations_total",
        "Total translations",
        labels=["source_lang", "target_lang"],
    )
    registry.create_histogram(
        "translation_duration_seconds",
        "Translation duration",
        labels=["source_lang", "target_lang"],
    )


# Decorators
def track_time(
    metric_name: str,
    labels: dict[str, str] | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to track function execution time.

    Args:
        metric_name: Name of histogram metric
        labels: Optional static labels

    Returns:
        Decorator function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            metric = registry.get_metric(metric_name)
            start = time.time()

            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start
                if metric:
                    dynamic_labels = labels.copy() if labels else {}
                    metric.observe(duration, dynamic_labels)

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            metric = registry.get_metric(metric_name)
            start = time.time()

            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start
                if metric:
                    dynamic_labels = labels.copy() if labels else {}
                    metric.observe(duration, dynamic_labels)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        else:
            return sync_wrapper  # type: ignore

    return decorator


def track_count(
    metric_name: str,
    labels: dict[str, str] | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to track function call count.

    Args:
        metric_name: Name of counter metric
        labels: Optional static labels

    Returns:
        Decorator function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            metric = registry.get_metric(metric_name)
            dynamic_labels = labels.copy() if labels else {}
            if metric:
                metric.inc(1.0, dynamic_labels)
            return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            metric = registry.get_metric(metric_name)
            dynamic_labels = labels.copy() if labels else {}
            if metric:
                metric.inc(1.0, dynamic_labels)
            return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        else:
            return sync_wrapper  # type: ignore

    return decorator


# Initialize default metrics
init_default_metrics()
