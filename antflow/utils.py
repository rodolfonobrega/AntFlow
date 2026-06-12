import logging
from typing import Any

from tenacity import RetryError


def extract_exception(error: Exception) -> Exception:
    """
    Extract the original exception from a RetryError or return the error as-is.

    Args:
        error: The exception to extract from

    Returns:
        The original exception if available, otherwise the input error
    """
    if isinstance(error, RetryError):
        try:
            original = error.last_attempt.exception()
            return original if isinstance(original, Exception) else error
        except Exception:
            return error
    return error


def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Set up a logger with consistent formatting.

    Args:
        name: Logger name
        level: Logging level

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(level)
    return logger


def get_task_name(task: Any) -> str:
    """
    Get a friendly name for a task callable.
    Handles standard functions, functools.partial, and custom callable objects.
    """
    if hasattr(task, "__name__"):
        return task.__name__
    if hasattr(task, "func") and hasattr(task.func, "__name__"):
        return task.func.__name__
    return type(task).__name__
