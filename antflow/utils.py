import logging

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
            return error.last_attempt.exception()
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
