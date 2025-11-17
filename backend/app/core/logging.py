"""
Logging configuration using Loguru.
"""
import sys
from pathlib import Path
from loguru import logger
from app.config import settings


def setup_logging() -> None:
    """Configure application logging."""

    # Remove default handler
    logger.remove()

    # Console handler with color
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=settings.LOG_LEVEL,
        colorize=True,
    )

    # File handler
    if settings.LOG_FILE:
        log_path = Path(settings.LOG_FILE)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        logger.add(
            settings.LOG_FILE,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            level=settings.LOG_LEVEL,
            rotation="10 MB",
            retention="1 week",
            compression="zip",
        )

    logger.info(f"Logging configured - Level: {settings.LOG_LEVEL}")


def get_logger(name: str):
    """Get a logger instance for a module."""
    return logger.bind(name=name)
