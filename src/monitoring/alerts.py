"""Alerting system for monitoring thresholds and sending notifications."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Callable

from src.monitoring.logging import get_logger

logger = get_logger(__name__)


class AlertSeverity(str, Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    """Alert status."""

    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SILENCED = "silenced"


@dataclass
class Alert:
    """An alert event."""

    id: str
    name: str
    severity: AlertSeverity
    status: AlertStatus = AlertStatus.ACTIVE
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    labels: dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: datetime | None = None
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "id": self.id,
            "name": self.name,
            "severity": self.severity.value,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
            "labels": self.labels,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "acknowledged_by": self.acknowledged_by,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
        }


@dataclass
class AlertRule:
    """Rule for triggering alerts."""

    id: str
    name: str
    metric_name: str
    severity: AlertSeverity
    condition: str  # e.g., ">", "<", "==", "!="
    threshold: float
    duration_seconds: int = 60  # How long condition must be true
    labels: dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    last_triggered: datetime | None = None
    trigger_count: int = 0


class AlertChannel:
    """Channel for sending alerts."""

    def __init__(
        self,
        name: str,
        channel_type: str,
        config: dict[str, Any],
    ) -> None:
        """Initialize alert channel.

        Args:
            name: Channel name
            channel_type: Type of channel (email, slack, webhook, etc.)
            config: Channel configuration
        """
        self.name = name
        self.channel_type = channel_type
        self.config = config

    async def send_alert(self, alert: Alert) -> bool:
        """Send alert to this channel.

        Args:
            alert: Alert to send

        Returns:
            True if sent successfully
        """
        try:
            if self.channel_type == "webhook":
                return await self._send_webhook(alert)
            elif self.channel_type == "log":
                return await self._send_log(alert)
            # Add more channel types as needed
            return False
        except Exception as e:
            logger.error(f"Failed to send alert to {self.name}: {e}")
            return False

    async def _send_webhook(self, alert: Alert) -> bool:
        """Send alert via webhook.

        Args:
            alert: Alert to send

        Returns:
            True if sent successfully
        """
        import httpx

        url = self.config.get("url")
        if not url:
            return False

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=alert.to_dict(),
                timeout=10.0,
            )
            return response.status_code == 200

    async def _send_log(self, alert: Alert) -> bool:
        """Log alert.

        Args:
            alert: Alert to log

        Returns:
            True
        """
        log_method = {
            AlertSeverity.INFO: logger.info,
            AlertSeverity.WARNING: logger.warning,
            AlertSeverity.ERROR: logger.error,
            AlertSeverity.CRITICAL: logger.critical,
        }.get(alert.severity, logger.warning)

        log_method(
            f"Alert: {alert.name}",
            alert_id=alert.id,
            severity=alert.severity.value,
            message=alert.message,
            details=alert.details,
        )

        return True


class AlertManager:
    """Manages alert rules and sends notifications."""

    def __init__(
        self,
        evaluation_interval_seconds: int = 60,
    ) -> None:
        """Initialize alert manager.

        Args:
            evaluation_interval_seconds: Interval between rule evaluations
        """
        self.evaluation_interval = evaluation_interval_seconds
        self._rules: dict[str, AlertRule] = {}
        self._alerts: dict[str, Alert] = {}
        self._channels: dict[str, AlertChannel] = {}
        self._running = False

    def add_rule(self, rule: AlertRule) -> None:
        """Add an alert rule.

        Args:
            rule: Alert rule to add
        """
        self._rules[rule.id] = rule

    def remove_rule(self, rule_id: str) -> None:
        """Remove an alert rule.

        Args:
            rule_id: Rule ID to remove
        """
        if rule_id in self._rules:
            del self._rules[rule_id]

    def add_channel(self, channel: AlertChannel) -> None:
        """Add an alert channel.

        Args:
            channel: Channel to add
        """
        self._channels[channel.name] = channel

    def remove_channel(self, channel_name: str) -> None:
        """Remove an alert channel.

        Args:
            channel_name: Channel name to remove
        """
        if channel_name in self._channels:
            del self._channels[channel_name]

    async def evaluate_rules(
        self,
        get_metric_value: Callable[[str], float | None],
    ) -> list[Alert]:
        """Evaluate all alert rules.

        Args:
            get_metric_value: Function to get current metric value

        Returns:
            List of new alerts triggered
        """
        new_alerts = []

        for rule in self._rules.values():
            if not rule.enabled:
                continue

            value = get_metric_value(rule.metric_name)

            if value is None:
                continue

            triggered = self._evaluate_condition(
                value,
                rule.condition,
                rule.threshold,
            )

            if triggered:
                # Check if already alerted recently
                if rule.last_triggered:
                    elapsed = (datetime.now(timezone.utc) - rule.last_triggered).total_seconds()
                    if elapsed < rule.duration_seconds:
                        continue

                # Create alert
                alert = Alert(
                    id=f"{rule.id}_{int(datetime.now(timezone.utc).timestamp())}",
                    name=rule.name,
                    severity=rule.severity,
                    message=f"Metric {rule.metric_name} is {value} (threshold: {rule.threshold})",
                    details={
                        "metric": rule.metric_name,
                        "current_value": value,
                        "threshold": rule.threshold,
                        "condition": rule.condition,
                    },
                    labels=rule.labels.copy(),
                )

                self._alerts[alert.id] = alert
                rule.last_triggered = datetime.now(timezone.utc)
                rule.trigger_count += 1

                new_alerts.append(alert)

        # Send alerts
        for alert in new_alerts:
            await self._send_alert(alert)

        return new_alerts

    async def acknowledge_alert(
        self,
        alert_id: str,
        acknowledged_by: str,
    ) -> Alert | None:
        """Acknowledge an alert.

        Args:
            alert_id: Alert ID
            acknowledged_by: User acknowledging

        Returns:
            Acknowledged alert or None
        """
        alert = self._alerts.get(alert_id)
        if not alert:
            return None

        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_by = acknowledged_by
        alert.acknowledged_at = datetime.now(timezone.utc)
        alert.updated_at = datetime.now(timezone.utc)

        return alert

    async def resolve_alert(self, alert_id: str) -> Alert | None:
        """Resolve an alert.

        Args:
            alert_id: Alert ID

        Returns:
            Resolved alert or None
        """
        alert = self._alerts.get(alert_id)
        if not alert:
            return None

        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = datetime.now(timezone.utc)
        alert.updated_at = datetime.now(timezone.utc)

        return alert

    def get_active_alerts(self) -> list[Alert]:
        """Get all active alerts.

        Returns:
            List of active alerts
        """
        return [
            alert for alert in self._alerts.values()
            if alert.status in (AlertStatus.ACTIVE, AlertStatus.ACKNOWLEDGED)
        ]

    def get_alerts_by_severity(
        self,
        severity: AlertSeverity,
    ) -> list[Alert]:
        """Get alerts by severity.

        Args:
            severity: Alert severity

        Returns:
            List of alerts
        """
        return [
            alert for alert in self._alerts.values()
            if alert.severity == severity
            and alert.status != AlertStatus.RESOLVED
        ]

    async def start(self) -> None:
        """Start alert evaluation loop."""
        self._running = True

        while self._running:
            try:
                # Get metric values from registry
                from src.monitoring.metrics import get_registry

                registry = get_registry()

                def get_metric_value(name: str) -> float | None:
                    metric = registry.get_metric(name)
                    if not metric:
                        return None

                    data = metric.get()

                    # Extract value based on metric type
                    if data["type"] == "counter" and data.get("values"):
                        return data["values"][0]["value"]
                    elif data["type"] == "gauge" and data.get("values"):
                        return data["values"][0]["value"]
                    elif data["type"] == "histogram" and data.get("histograms"):
                        return data["histograms"][0]["count"]
                    elif data["type"] == "summary" and data.get("summaries"):
                        return data["summaries"][0]["average"]

                    return None

                await self.evaluate_rules(get_metric_value)

            except Exception as e:
                logger.error(f"Error evaluating alert rules: {e}")

            await asyncio.sleep(self.evaluation_interval)

    def stop(self) -> None:
        """Stop alert evaluation loop."""
        self._running = False

    def _evaluate_condition(
        self,
        value: float,
        condition: str,
        threshold: float,
    ) -> bool:
        """Evaluate a condition.

        Args:
            value: Current value
            condition: Condition operator
            threshold: Threshold value

        Returns:
            True if condition is met
        """
        if condition == ">":
            return value > threshold
        elif condition == ">=":
            return value >= threshold
        elif condition == "<":
            return value < threshold
        elif condition == "<=":
            return value <= threshold
        elif condition == "==":
            return value == threshold
        elif condition == "!=":
            return value != threshold
        else:
            return False

    async def _send_alert(self, alert: Alert) -> None:
        """Send alert to all channels.

        Args:
            alert: Alert to send
        """
        for channel in self._channels.values():
            try:
                await channel.send_alert(alert)
            except Exception as e:
                logger.error(f"Error sending alert to {channel.name}: {e}")


# Global alert manager
alert_manager = AlertManager()


def get_alert_manager() -> AlertManager:
    """Get global alert manager instance.

    Returns:
        Alert manager instance
    """
    return alert_manager


def create_default_rules() -> None:
    """Create default alert rules."""
    import uuid
    from src.monitoring.metrics import registry

    # High error rate alert
    error_metric = registry.create_counter(
        "http_errors_total",
        "Total HTTP errors",
        labels=["endpoint", "status"],
    )

    alert_manager.add_rule(AlertRule(
        id=str(uuid.uuid4()),
        name="High Error Rate",
        metric_name="http_errors_total",
        severity=AlertSeverity.WARNING,
        condition=">",
        threshold=100.0,
        duration_seconds=300,  # 5 minutes
    ))

    # Long response time alert
    alert_manager.add_rule(AlertRule(
        id=str(uuid.uuid4()),
        name="High Response Time",
        metric_name="http_request_duration_seconds",
        severity=AlertSeverity.WARNING,
        condition=">",
        threshold=5.0,  # 5 seconds
        duration_seconds=60,
    ))

    # Add log channel
    alert_manager.add_channel(AlertChannel(
        name="log",
        channel_type="log",
        config={},
    ))


# Initialize default rules
create_default_rules()
