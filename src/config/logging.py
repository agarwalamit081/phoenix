"""Logging configuration using Loguru."""

import logging
import sys
from pathlib import Path
from typing import Any

from loguru import logger as _logger

from src.config.settings import settings


class InterceptHandler(logging.Handler):
    """Intercept standard logging messages and redirect to Loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record to Loguru."""
        # Get corresponding Loguru level if it exists
        try:
            level = _logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        _logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logging() -> None:
    """Configure Loguru logging for the application."""
    # Remove default handler
    _logger.remove()

    # Determine log format based on configuration
    # Use {time} which is a built-in loguru field (not {extra[timestamp]})
    if settings.log_format == "json":
        log_format = (
            '{{"timestamp": "{time:YYYY-MM-DD HH:mm:ss.SSS}", '
            '"level": "{level}", '
            '"logger": "{name}", '
            '"function": "{function}", '
            '"line": {line}, '
            '"message": "{message}"}}'
        )
    else:
        log_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        )

    # Console sink
    _logger.add(
        sys.stdout,
        format=log_format,
        level=settings.log_level,
        colorize=True,
        backtrace=True,
        diagnose=settings.debug,
    )

    # File sink (rotating)
    log_path = Path(settings.log_file_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        _logger.add(
            settings.log_file_path,
            format=log_format,
            level=settings.log_level,
            rotation=settings.log_rotation,
            retention=settings.log_retention,
            compression="zip",
            backtrace=True,
            diagnose=settings.debug,
            enqueue=True,
        )
    except PermissionError:
        # Some environments restrict multiprocessing semaphores required by enqueue=True.
        _logger.add(
            settings.log_file_path,
            format=log_format,
            level=settings.log_level,
            rotation=settings.log_rotation,
            retention=settings.log_retention,
            compression="zip",
            backtrace=True,
            diagnose=settings.debug,
            enqueue=False,
        )

    # Intercept standard logging
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # Set log levels for third-party libraries
    logging.getLogger("uvicorn").handlers = [InterceptHandler()]
    logging.getLogger("uvicorn.access").handlers = [InterceptHandler()]
    logging.getLogger("fastapi").handlers = [InterceptHandler()]
    logging.getLogger("sqlalchemy").handlers = [InterceptHandler()]
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    _logger.info(f"Logging configured: level={settings.log_level}, format={settings.log_format}")


def get_logger(name: str | None = None) -> Any:
    """Get a logger instance with optional name binding."""
    if name:
        return _logger.bind(name=name)
    return _logger


# Export logger for use in other modules
logger = _logger
