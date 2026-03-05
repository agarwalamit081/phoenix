"""Structured logging for application monitoring."""

import asyncio
import logging
import sys
import uuid
from datetime import datetime, timezone
from enum import Enum
from functools import wraps
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
from typing import Any, Callable, TypeVar

from loguru import logger as loguru_logger

T = TypeVar("T")


class LogLevel(str, Enum):
    """Log levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogContext:
    """Context for structured logging."""

    def __init__(
        self,
        request_id: str | None = None,
        user_id: str | None = None,
        tour_id: str | None = None,
        **extra_context: Any,
    ) -> None:
        """Initialize log context.

        Args:
            request_id: Optional request ID
            user_id: Optional user ID
            tour_id: Optional tour ID
            **extra_context: Additional context
        """
        self.request_id = request_id or str(uuid.uuid4())
        self.user_id = user_id
        self.tour_id = tour_id
        self.extra_context = extra_context

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "request_id": self.request_id,
            "user_id": self.user_id,
            "tour_id": self.tour_id,
            **self.extra_context,
        }


class StructuredLogger:
    """Structured logger with context support."""

    def __init__(
        self,
        name: str,
        log_file: str | None = None,
        log_level: str = "INFO",
        rotation: str = "100 MB",
        retention: str = "30 days",
    ) -> None:
        """Initialize structured logger.

        Args:
            name: Logger name
            log_file: Optional log file path
            log_level: Log level
            rotation: Log rotation setting
            retention: Log retention setting
        """
        self.name = name
        self.log_level = log_level
        self._context: LogContext | None = None

        # Configure loguru
        loguru_logger.remove()  # Remove default handler

        # Console handler with colors
        loguru_logger.add(
            sys.stderr,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                "<level>{message}</level>"
            ),
            level=log_level,
            colorize=True,
        )

        # File handler if specified
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            loguru_logger.add(
                log_file,
                format=(
                    "{time:YYYY-MM-DD HH:mm:ss} | "
                    "{level: <8} | "
                    "{name}:{function}:{line} | "
                    "{message}"
                ),
                level=log_level,
                rotation=rotation,
                retention=retention,
                compression="zip",
                enqueue=True,  # Async logging
            )

        self._logger = loguru_logger

    def with_context(
        self,
        request_id: str | None = None,
        user_id: str | None = None,
        tour_id: str | None = None,
        **extra_context: Any,
    ) -> "StructuredLogger":
        """Create logger with context.

        Args:
            request_id: Optional request ID
            user_id: Optional user ID
            tour_id: Optional tour ID
            **extra_context: Additional context

        Returns:
            Logger with context
        """
        new_logger = StructuredLogger(
            name=self.name,
            log_level=self.log_level,
        )
        new_logger._context = LogContext(
            request_id=request_id,
            user_id=user_id,
            tour_id=tour_id,
            **extra_context,
        )
        return new_logger

    def _bind_context(self) -> None:
        """Bind context to logger."""
        if self._context:
            context_dict = self._context.to_dict()
            # Remove None values
            context_dict = {k: v for k, v in context_dict.items() if v is not None}
            self._logger = self._logger.bind(**context_dict)

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message.

        Args:
            message: Log message
            **kwargs: Additional fields
        """
        self._logger.debug(message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message.

        Args:
            message: Log message
            **kwargs: Additional fields
        """
        self._logger.info(message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message.

        Args:
            message: Log message
            **kwargs: Additional fields
        """
        self._logger.warning(message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        """Log error message.

        Args:
            message: Log message
            **kwargs: Additional fields
        """
        self._logger.error(message, **kwargs)

    def critical(self, message: str, **kwargs: Any) -> None:
        """Log critical message.

        Args:
            message: Log message
            **kwargs: Additional fields
        """
        self._logger.critical(message, **kwargs)

    def exception(
        self,
        message: str,
        exc_info: bool = True,
        **kwargs: Any,
    ) -> None:
        """Log exception.

        Args:
            message: Log message
            exc_info: Whether to include exception info
            **kwargs: Additional fields
        """
        self._logger.error(message, exc_info=exc_info, **kwargs)


class AuditLogger:
    """Logger for audit events."""

    def __init__(
        self,
        log_file: str = "logs/audit.log",
    ) -> None:
        """Initialize audit logger.

        Args:
            log_file: Audit log file path
        """
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        self._logger = loguru_logger.bind(audit=True)
        self._logger.add(
            log_file,
            format="{time:YYYY-MM-DD HH:mm:ss} | {message}",
            level="INFO",
            rotation="1 day",
            retention="365 days",
            compression="zip",
            filter=lambda record: record["extra"].get("audit") is True,
        )

    def log_event(
        self,
        event_type: str,
        user_id: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        details: dict[str, Any] | None = None,
        ip_address: str | None = None,
    ) -> None:
        """Log an audit event.

        Args:
            event_type: Type of event (e.g., "user_login", "tour_created")
            user_id: Optional user ID
            resource_type: Optional resource type
            resource_id: Optional resource ID
            details: Optional event details
            ip_address: Optional IP address
        """
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": details or {},
            "ip_address": ip_address,
        }

        # Remove None values
        event = {k: v for k, v in event.items() if v is not None}

        import json
        self._logger.info(json.dumps(event))

    def log_access(
        self,
        user_id: str,
        endpoint: str,
        method: str,
        status_code: int,
        ip_address: str | None = None,
    ) -> None:
        """Log API access.

        Args:
            user_id: User ID
            endpoint: API endpoint
            method: HTTP method
            status_code: Response status code
            ip_address: Optional IP address
        """
        self.log_event(
            event_type="api_access",
            user_id=user_id,
            resource_type="endpoint",
            resource_id=endpoint,
            details={
                "method": method,
                "status_code": status_code,
            },
            ip_address=ip_address,
        )


# Global loggers
def get_logger(
    name: str,
    log_file: str | None = None,
    log_level: str = "INFO",
) -> StructuredLogger:
    """Get or create a structured logger.

    Args:
        name: Logger name
        log_file: Optional log file path
        log_level: Log level

    Returns:
        Structured logger instance
    """
    return StructuredLogger(
        name=name,
        log_file=log_file,
        log_level=log_level,
    )


def get_audit_logger(
    log_file: str = "logs/audit.log",
) -> AuditLogger:
    """Get or create audit logger.

    Args:
        log_file: Audit log file path

    Returns:
        Audit logger instance
    """
    return AuditLogger(log_file=log_file)


# Decorators
def log_execution(
    logger: StructuredLogger | None = None,
    log_level: str = "INFO",
    log_args: bool = False,
    log_result: bool = False,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to log function execution.

    Args:
        logger: Optional logger
        log_level: Log level
        log_args: Whether to log arguments
        log_result: Whether to log result

    Returns:
        Decorator function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            nonlocal logger
            if logger is None:
                logger = get_logger(func.__module__)

            func_name = f"{func.__module__}.{func.__name__}"
            log_method = getattr(logger, log_level.lower())

            log_data = {"function": func_name, "status": "started"}

            if log_args:
                log_data["args"] = str(args)[:200]  # Limit length
                log_data["kwargs"] = str(kwargs)[:200]

            log_method(f"Executing {func_name}", **log_data)

            try:
                result = await func(*args, **kwargs)

                log_data["status"] = "completed"
                if log_result:
                    log_data["result"] = str(result)[:200]

                log_method(f"Completed {func_name}", **log_data)

                return result

            except Exception as e:
                log_data["status"] = "failed"
                log_data["error"] = str(e)
                logger.error(f"Failed {func_name}", **log_data)
                raise

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            nonlocal logger
            if logger is None:
                logger = get_logger(func.__module__)

            func_name = f"{func.__module__}.{func.__name__}"
            log_method = getattr(logger, log_level.lower())

            log_data = {"function": func_name, "status": "started"}

            if log_args:
                log_data["args"] = str(args)[:200]
                log_data["kwargs"] = str(kwargs)[:200]

            log_method(f"Executing {func_name}", **log_data)

            try:
                result = func(*args, **kwargs)

                log_data["status"] = "completed"
                if log_result:
                    log_data["result"] = str(result)[:200]

                log_method(f"Completed {func_name}", **log_data)

                return result

            except Exception as e:
                log_data["status"] = "failed"
                log_data["error"] = str(e)
                logger.error(f"Failed {func_name}", **log_data)
                raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        else:
            return sync_wrapper  # type: ignore

    return decorator


def log_errors(
    logger: StructuredLogger | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to log function errors.

    Args:
        logger: Optional logger

    Returns:
        Decorator function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            nonlocal logger
            if logger is None:
                logger = get_logger(func.__module__)

            try:
                return await func(*args, **kwargs)
            except Exception as e:
                func_name = f"{func.__module__}.{func.__name__}"
                logger.exception(
                    f"Error in {func_name}",
                    function=func_name,
                    error_type=type(e).__name__,
                )
                raise

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            nonlocal logger
            if logger is None:
                logger = get_logger(func.__module__)

            try:
                return func(*args, **kwargs)
            except Exception as e:
                func_name = f"{func.__module__}.{func.__name__}"
                logger.exception(
                    f"Error in {func_name}",
                    function=func_name,
                    error_type=type(e).__name__,
                )
                raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        else:
            return sync_wrapper  # type: ignore

    return decorator
