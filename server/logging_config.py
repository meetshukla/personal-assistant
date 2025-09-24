"""Logging configuration for Personal Assistant."""

import logging
import sys
from typing import Any

# Configure root logger
logger = logging.getLogger("personal_assistant")


def configure_logging() -> None:
    """Set up logging configuration."""

    # Configure root logger first
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Clear all existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create new console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)

    # Create formatter matching your log format
    formatter = logging.Formatter(
        '[%(asctime)s][%(levelname)s] %(message)s'
    )
    console_handler.setFormatter(formatter)

    # Add handler to root logger
    root_logger.addHandler(console_handler)

    # Configure our specific logger
    logger.handlers.clear()
    logger.addHandler(console_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    # Also configure specific loggers that might exist
    for logger_name in ['server.services.triggers.scheduler', 'server.tools.scheduler_tool']:
        specific_logger = logging.getLogger(logger_name)
        specific_logger.setLevel(logging.INFO)
        specific_logger.propagate = True  # Let it propagate to root


def get_logger(name: str = "personal_assistant") -> logging.Logger:
    """Get logger instance."""
    return logging.getLogger(name)