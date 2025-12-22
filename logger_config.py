"""
Logging configuration for AWS Lambda functions.

This module provides a standardized logging setup that works well with
AWS Lambda and CloudWatch Logs.
"""
import logging
import os
import sys


def get_logger(name: str = None) -> logging.Logger:
    """
    Get a configured logger instance for AWS Lambda.

    Args:
        name: Logger name (defaults to root logger if not provided)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name or __name__)

    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger

    # Set log level from environment variable, default to INFO
    log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
    logger.setLevel(getattr(logging, log_level, logging.INFO))

    # Create console handler (Lambda sends stdout/stderr to CloudWatch)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logger.level)

    # Create formatter
    # Use a format that works well with CloudWatch Logs
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)

    # Add handler to logger
    logger.addHandler(handler)

    # Prevent propagation to root logger to avoid duplicate logs
    logger.propagate = False

    return logger
