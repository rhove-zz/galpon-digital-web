"""
Logging utilities for ACU.
Provides structured logging with loguru.
"""

import sys
from loguru import logger
from src.config.settings import system_config


def setup_logger():
    """Configure loguru for the application."""
    # Remove default handler
    logger.remove()

    # Add console handler with formatting
    logger.add(
        sys.stderr,
        format="<level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=system_config.log_level,
        colorize=True,
    )

    # Add file handler for persistent logging
    logger.add(
        "logs/acu_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",
        rotation="00:00",
    )

    return logger


# Initialize logger
log = setup_logger()
