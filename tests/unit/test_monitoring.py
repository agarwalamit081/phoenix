"""Unit tests for monitoring modules."""

import pytest
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from src.monitoring.metrics import (
    Metric,
    MetricType,
    MetricsRegistry,
    Histogram,
    Summary,
    get_registry,
    track_time,
    track_count,
)
from src.monitoring.logging import (
    LogLevel,
    LogContext,
    StructuredLogger,
    AuditLogger,
    get_logger,
    get_audit_logger,
)
from src.monitoring.alerts import (
    Alert,
    AlertRule,
    AlertSeverity,
    AlertStatus,
    AlertChannel,
    AlertManager,
    get_alert_manager,
)
from src.monitoring.health import (
    HealthStatus,
    HealthCheckResult,
    HealthCheck,
    HealthChecker,
    get_health_checker,
)


class TestMetrics:
    """Test metrics."""

    def test_create_counter(self):
        """Test creating counter metric."""
        registry = MetricsRegistry()

        metric = registry.create_counter(
            name="test_counter",
            description="Test counter",
            labels=["method", "endpoint"],
        )

        assert metric.name == "test_counter"
        assert metric.metric_type == MetricType.COUNTER

    def test_counter_inc(self):
        """Test incrementing counter."""
        registry = MetricsRegistry()

        metric = registry.create_counter(
            name="test_counter",
            description="Test counter",
        )

        metric.inc(5.0, labels={"method": "GET"})

        data = metric.get()
        assert data["values"][0]["value"] == 5.0

    def test_gauge_set(self):
        """Test setting gauge value."""
        registry = MetricsRegistry()

        metric = registry.create_gauge(
            name="test_gauge",
            description="Test gauge",
        )

        metric.set(42.0)

        data = metric.get()
        assert data["values"][0]["value"] == 42.0

    def test_histogram_observe(self):
        """Test observing histogram values."""
        registry = MetricsRegistry()

        metric = registry.create_histogram(
            name="test_histogram",
            description="Test histogram",
        )

        # Observe some values
        metric.observe(0.1)
        metric.observe(0.5)
        metric.observe(1.5)

        data = metric.get()
        assert data["histograms"][0]["count"] == 3
        assert data["histograms"][0]["sum"] == 2.1

    def test_summary_observe(self):
        """Test observing summary values."""
        registry = MetricsRegistry()

        metric = registry.create_summary(
            name="test_summary",
            description="Test summary",
        )

        metric.observe(10.0)
        metric.observe(20.0)
        metric.observe(30.0)

        data = metric.get()
        assert data["summaries"][0]["count"] == 3
        assert data["summaries"][0]["average"] == 20.0

    def test_get_metric(self):
        """Test getting metric by name."""
        registry = MetricsRegistry()

        registry.create_counter(
            name="test_counter",
            description="Test counter",
        )

        metric = registry.get_metric("test_counter")

        assert metric is not None
        assert metric.name == "test_counter"

    def test_get_all_metrics(self):
        """Test getting all metrics."""
        registry = MetricsRegistry()

        registry.create_counter("counter1", "Counter 1")
        registry.create_gauge("gauge1", "Gauge 1")

        all_metrics = registry.get_all()

        assert "counter1" in all_metrics
        assert "gauge1" in all_metrics

    def test_track_time_decorator(self):
        """Test track_time decorator."""
        # Create histogram in global registry
        registry = get_registry()
        registry.create_histogram(
            name="test_duration_decorator",
            description="Test duration",
        )

        @track_time("test_duration_decorator")
        def test_function():
            time.sleep(0.01)
            return "done"

        result = test_function()

        assert result == "done"
        # Metric should have observed a value
        metric = registry.get_metric("test_duration_decorator")
        assert metric is not None
        data = metric.get()
        assert len(data["histograms"]) > 0
        assert data["histograms"][0]["count"] >= 1

    def test_track_count_decorator(self):
        """Test track_count decorator."""
        # Create counter in global registry
        registry = get_registry()
        registry.create_counter(
            name="test_calls_decorator",
            description="Test calls",
        )

        @track_count("test_calls_decorator")
        def test_function():
            return "done"

        test_function()
        test_function()

        metric = registry.get_metric("test_calls_decorator")
        assert metric is not None
        data = metric.get()
        assert len(data["values"]) > 0
        assert data["values"][0]["value"] == 2.0


class TestHistogram:
    """Test histogram."""

    def test_observe(self):
        """Test observing values."""
        hist = Histogram()

        hist.observe(0.01)
        hist.observe(0.1)
        hist.observe(1.0)

        assert hist.count == 3
        assert hist.sum == 1.11

    def test_get_quantile(self):
        """Test getting quantiles."""
        hist = Histogram()

        hist.observe(0.1)
        hist.observe(0.5)
        hist.observe(1.0)

        p50 = hist.get_quantile(0.5)
        assert p50 > 0

    def test_default_buckets(self):
        """Test default bucket values."""
        hist = Histogram()

        assert len(hist.DEFAULT_BUCKETS) > 0
        assert 0.1 in hist.DEFAULT_BUCKETS


class TestSummary:
    """Test summary."""

    def test_observe(self):
        """Test observing values."""
        summary = Summary()

        summary.observe(10.0)
        summary.observe(20.0)
        summary.observe(30.0)

        assert summary.count == 3
        assert summary.sum == 60.0

    def test_get_average(self):
        """Test getting average."""
        summary = Summary()

        summary.observe(10.0)
        summary.observe(20.0)
        summary.observe(30.0)

        assert summary.get_average() == 20.0

    def test_min_max(self):
        """Test min and max."""
        summary = Summary()

        summary.observe(10.0)
        summary.observe(5.0)
        summary.observe(15.0)

        assert summary.min == 5.0
        assert summary.max == 15.0


class TestStructuredLogger:
    """Test structured logger."""

    def test_with_context(self):
        """Test creating logger with context."""
        logger = StructuredLogger("test")

        context_logger = logger.with_context(
            request_id="req_123",
            user_id="user_456",
        )

        assert context_logger._context.request_id == "req_123"

    def test_log_levels(self):
        """Test different log levels."""
        logger = StructuredLogger("test")

        # These should not raise exceptions
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")

    def test_log_with_fields(self):
        """Test logging with additional fields."""
        logger = StructuredLogger("test")

        logger.info("Test message", field1="value1", field2=42)


class TestAuditLogger:
    """Test audit logger."""

    def test_log_event(self):
        """Test logging audit event."""
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "audit.log")
            audit_logger = AuditLogger(log_file=log_file)

            audit_logger.log_event(
                event_type="user_login",
                user_id="user_123",
                ip_address="192.168.1.1",
            )

    def test_log_access(self):
        """Test logging API access."""
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "audit.log")
            audit_logger = AuditLogger(log_file=log_file)

            audit_logger.log_access(
                user_id="user_123",
                endpoint="/api/v1/chat",
                method="POST",
                status_code=200,
                ip_address="192.168.1.1",
            )


class TestLogContext:
    """Test log context."""

    def test_to_dict(self):
        """Test converting context to dictionary."""
        context = LogContext(
            request_id="req_123",
            user_id="user_456",
            tour_id="tour_789",
            custom_field="custom_value",
        )

        data = context.to_dict()

        assert data["request_id"] == "req_123"
        assert data["user_id"] == "user_456"
        assert data["custom_field"] == "custom_value"


class TestAlert:
    """Test alert."""

    def test_to_dict(self):
        """Test converting alert to dictionary."""
        alert = Alert(
            id="alert_1",
            name="Test Alert",
            severity=AlertSeverity.WARNING,
            message="Test alert message",
        )

        data = alert.to_dict()

        assert data["id"] == "alert_1"
        assert data["name"] == "Test Alert"
        assert data["severity"] == "warning"

    def test_acknowledge(self):
        """Test acknowledging alert."""
        alert = Alert(
            id="alert_1",
            name="Test Alert",
            severity=AlertSeverity.WARNING,
        )

        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_by = "user_123"
        alert.acknowledged_at = datetime.now(timezone.utc)

        assert alert.status == AlertStatus.ACKNOWLEDGED
        assert alert.acknowledged_by == "user_123"

    def test_resolve(self):
        """Test resolving alert."""
        alert = Alert(
            id="alert_1",
            name="Test Alert",
            severity=AlertSeverity.WARNING,
        )

        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = datetime.now(timezone.utc)

        assert alert.status == AlertStatus.RESOLVED


class TestAlertManager:
    """Test alert manager."""

    def test_add_rule(self):
        """Test adding alert rule."""
        manager = AlertManager()

        rule = AlertRule(
            id="rule_1",
            name="Test Rule",
            metric_name="test_metric",
            severity=AlertSeverity.WARNING,
            condition=">",
            threshold=100.0,
        )

        manager.add_rule(rule)

        assert "rule_1" in manager._rules

    def test_remove_rule(self):
        """Test removing alert rule."""
        manager = AlertManager()

        rule = AlertRule(
            id="rule_1",
            name="Test Rule",
            metric_name="test_metric",
            severity=AlertSeverity.WARNING,
            condition=">",
            threshold=100.0,
        )

        manager.add_rule(rule)
        manager.remove_rule("rule_1")

        assert "rule_1" not in manager._rules

    def test_evaluate_condition(self):
        """Test evaluating alert conditions."""
        manager = AlertManager()

        # Greater than
        assert manager._evaluate_condition(150, ">", 100) is True
        assert manager._evaluate_condition(50, ">", 100) is False

        # Less than
        assert manager._evaluate_condition(50, "<", 100) is True
        assert manager._evaluate_condition(150, "<", 100) is False

        # Equal
        assert manager._evaluate_condition(100, "==", 100) is True
        assert manager._evaluate_condition(99, "==", 100) is False

    def test_add_channel(self):
        """Test adding alert channel."""
        manager = AlertManager()

        channel = AlertChannel(
            name="log",
            channel_type="log",
            config={},
        )

        manager.add_channel(channel)

        assert "log" in manager._channels

    def test_get_active_alerts(self):
        """Test getting active alerts."""
        manager = AlertManager()

        alert = Alert(
            id="alert_1",
            name="Test Alert",
            severity=AlertSeverity.WARNING,
            status=AlertStatus.ACTIVE,
        )

        manager._alerts["alert_1"] = alert

        active = manager.get_active_alerts()

        assert len(active) == 1
        assert active[0].status == AlertStatus.ACTIVE


class TestHealthChecker:
    """Test health checker."""

    @pytest.mark.asyncio
    async def test_register_check(self):
        """Test registering health check."""
        checker = HealthChecker()

        async def check_fn() -> HealthCheckResult:
            return HealthCheckResult(
                name="test",
                status=HealthStatus.HEALTHY,
                message="OK",
            )

        check = HealthCheck("test", check_fn)
        checker.register_check(check)

        assert "test" in checker._checks

    @pytest.mark.asyncio
    async def test_check_health(self):
        """Test checking health."""
        checker = HealthChecker()

        async def check_fn() -> HealthCheckResult:
            return HealthCheckResult(
                name="test",
                status=HealthStatus.HEALTHY,
                message="OK",
            )

        check = HealthCheck("test", check_fn)
        checker.register_check(check)

        result = await checker.check_health()

        assert result.status == HealthStatus.HEALTHY
        assert "checks" in result.details

    @pytest.mark.asyncio
    async def test_health_check_timeout(self):
        """Test health check timeout."""
        checker = HealthChecker()

        async def slow_check_fn() -> HealthCheckResult:
            import asyncio
            await asyncio.sleep(10)
            return HealthCheckResult(
                name="slow",
                status=HealthStatus.HEALTHY,
                message="OK",
            )

        check = HealthCheck("slow", slow_check_fn, timeout_seconds=0.1)
        checker.register_check(check)

        result = await checker.check_health("slow")

        assert result.status == HealthStatus.UNHEALTHY
        assert "timed out" in result.message.lower()


class TestHealthCheckResult:
    """Test health check result."""

    def test_to_dict(self):
        """Test converting to dictionary."""
        result = HealthCheckResult(
            name="test",
            status=HealthStatus.HEALTHY,
            message="OK",
            details={"key": "value"},
        )

        data = result.to_dict()

        assert data["name"] == "test"
        assert data["status"] == "healthy"
        assert data["message"] == "OK"
