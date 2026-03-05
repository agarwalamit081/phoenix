"""Health check endpoints for monitoring system status."""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health check status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a health check."""

    name: str
    status: HealthStatus
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
            "checked_at": self.checked_at.isoformat(),
            "duration_ms": self.duration_ms,
        }


class HealthCheck:
    """A health check that can be executed."""

    def __init__(
        self,
        name: str,
        check_fn: Callable[[], Awaitable[HealthCheckResult] | HealthCheckResult],
        timeout_seconds: float = 5.0,
    ) -> None:
        """Initialize health check.

        Args:
            name: Check name
            check_fn: Function to execute the check
            timeout_seconds: Timeout for the check
        """
        self.name = name
        self.check_fn = check_fn
        self.timeout_seconds = timeout_seconds

    async def execute(self) -> HealthCheckResult:
        """Execute the health check.

        Returns:
            Health check result
        """
        start_time = datetime.now(timezone.utc)

        try:
            # Run with timeout
            result = await asyncio.wait_for(
                self._run_check(),
                timeout=self.timeout_seconds,
            )
            return result

        except asyncio.TimeoutError:
            duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Check timed out after {self.timeout_seconds}s",
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            logger.error(f"Health check {self.name} failed: {e}")
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=str(e),
                duration_ms=duration_ms,
            )

    async def _run_check(self) -> HealthCheckResult:
        """Run the check function.

        Returns:
            Health check result
        """
        start_time = datetime.now(timezone.utc)

        result = self.check_fn()
        if asyncio.iscoroutine(result):
            result = await result  # type: ignore

        # Calculate duration
        duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        result.duration_ms = duration_ms
        result.checked_at = start_time

        return result  # type: ignore


class HealthChecker:
    """Health checker for system components."""

    def __init__(
        self,
        system_name: str = "Phoenix AI Travel Companion",
    ) -> None:
        """Initialize health checker.

        Args:
            system_name: Name of the system
        """
        self.system_name = system_name
        self._checks: dict[str, HealthCheck] = {}
        self._last_results: dict[str, HealthCheckResult] = {}

    def register_check(self, check: HealthCheck) -> None:
        """Register a health check.

        Args:
            check: Health check to register
        """
        self._checks[check.name] = check

    def unregister_check(self, name: str) -> None:
        """Unregister a health check.

        Args:
            name: Check name
        """
        if name in self._checks:
            del self._checks[name]

    async def check_health(
        self,
        check_name: str | None = None,
    ) -> HealthCheckResult:
        """Execute a specific health check.

        Args:
            check_name: Name of check to run, or None for overall

        Returns:
            Health check result
        """
        if check_name:
            check = self._checks.get(check_name)
            if not check:
                return HealthCheckResult(
                    name=check_name,
                    status=HealthStatus.UNKNOWN,
                    message=f"Check not found: {check_name}",
                )
            result = await check.execute()
            self._last_results[check_name] = result
            return result

        # Run all checks
        overall_status = HealthStatus.HEALTHY
        all_results = []

        for check in self._checks.values():
            result = await check.execute()
            all_results.append(result)
            self._last_results[check.name] = result

            # Determine overall status
            if result.status == HealthStatus.UNHEALTHY:
                overall_status = HealthStatus.UNHEALTHY
            elif result.status == HealthStatus.DEGRADED and overall_status == HealthStatus.HEALTHY:
                overall_status = HealthStatus.DEGRADED

        return HealthCheckResult(
            name=self.system_name,
            status=overall_status,
            message=f"{len(all_results)} checks completed",
            details={
                "checks": [r.to_dict() for r in all_results],
                "healthy_count": sum(1 for r in all_results if r.status == HealthStatus.HEALTHY),
                "degraded_count": sum(1 for r in all_results if r.status == HealthStatus.DEGRADED),
                "unhealthy_count": sum(1 for r in all_results if r.status == HealthStatus.UNHEALTHY),
            },
        )

    def get_last_results(self) -> dict[str, HealthCheckResult]:
        """Get last health check results.

        Returns:
            Dictionary of last results
        """
        return self._last_results.copy()


async def check_database(db: Any) -> HealthCheckResult:
    """Check database connectivity.

    Args:
        db: Database connection

    Returns:
        Health check result
    """
    try:
        # Simple query to check connectivity
        await db.execute("SELECT 1")
        return HealthCheckResult(
            name="database",
            status=HealthStatus.HEALTHY,
            message="Database connection OK",
        )
    except Exception as e:
        return HealthCheckResult(
            name="database",
            status=HealthStatus.UNHEALTHY,
            message=f"Database connection failed: {e}",
        )


async def check_redis(redis_client: Any) -> HealthCheckResult:
    """Check Redis connectivity.

    Args:
        redis_client: Redis client

    Returns:
        Health check result
    """
    try:
        await redis_client.ping()
        return HealthCheckResult(
            name="redis",
            status=HealthStatus.HEALTHY,
            message="Redis connection OK",
        )
    except Exception as e:
        return HealthCheckResult(
            name="redis",
            status=HealthStatus.UNHEALTHY,
            message=f"Redis connection failed: {e}",
        )


async def check_neo4j(neo4j_client: Any) -> HealthCheckResult:
    """Check Neo4j connectivity.

    Args:
        neo4j_client: Neo4j client

    Returns:
        Health check result
    """
    try:
        await neo4j_client.verify_connectivity()
        return HealthCheckResult(
            name="neo4j",
            status=HealthStatus.HEALTHY,
            message="Neo4j connection OK",
        )
    except Exception as e:
        return HealthCheckResult(
            name="neo4j",
            status=HealthStatus.UNHEALTHY,
            message=f"Neo4j connection failed: {e}",
        )


async def check_llm_service(llm_service: Any) -> HealthCheckResult:
    """Check LLM service availability.

    Args:
        llm_service: LLM service

    Returns:
        Health check result
    """
    try:
        # Simple test call
        response = await llm_service.chat_completion(
            messages=[
                {"role": "user", "content": "ping"}
            ],
            max_tokens=5,
        )
        return HealthCheckResult(
            name="llm_service",
            status=HealthStatus.HEALTHY,
            message="LLM service OK",
            details={"provider": response.get("provider", "unknown")},
        )
    except Exception as e:
        return HealthCheckResult(
            name="llm_service",
            status=HealthStatus.DEGRADED,
            message=f"LLM service degraded: {e}",
        )


async def check_memory_usage() -> HealthCheckResult:
    """Check memory usage.

    Returns:
        Health check result
    """
    import psutil

    memory = psutil.virtual_memory()
    usage_percent = memory.percent

    status = HealthStatus.HEALTHY
    if usage_percent > 90:
        status = HealthStatus.UNHEALTHY
    elif usage_percent > 75:
        status = HealthStatus.DEGRADED

    return HealthCheckResult(
        name="memory",
        status=status,
        message=f"Memory usage: {usage_percent:.1f}%",
        details={
            "usage_percent": usage_percent,
            "available_mb": memory.available / 1024 / 1024,
            "total_mb": memory.total / 1024 / 1024,
        },
    )


async def check_disk_usage(path: str = "/") -> HealthCheckResult:
    """Check disk usage.

    Args:
        path: Path to check

    Returns:
        Health check result
    """
    import psutil

    disk = psutil.disk_usage(path)
    usage_percent = disk.percent

    status = HealthStatus.HEALTHY
    if usage_percent > 90:
        status = HealthStatus.UNHEALTHY
    elif usage_percent > 80:
        status = HealthStatus.DEGRADED

    return HealthCheckResult(
        name="disk",
        status=status,
        message=f"Disk usage: {usage_percent:.1f}%",
        details={
            "path": path,
            "usage_percent": usage_percent,
            "free_gb": disk.free / 1024 / 1024 / 1024,
            "total_gb": disk.total / 1024 / 1024 / 1024,
        },
    )


# Global health checker
health_checker = HealthChecker()


def get_health_checker() -> HealthChecker:
    """Get global health checker instance.

    Returns:
        Health checker instance
    """
    return health_checker


async def readiness_probe(db: Any) -> dict[str, Any]:
    """Readiness probe for Kubernetes.

    Args:
        db: Database connection

    Returns:
        Readiness status
    """
    result = await check_database(db)

    return {
        "ready": result.status == HealthStatus.HEALTHY,
        "status": result.status.value,
        "checks": [result.to_dict()],
    }


async def liveness_probe() -> dict[str, Any]:
    """Liveness probe for Kubernetes.

    Returns:
        Liveness status
    """
    return {
        "alive": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
