import structlog
from typing import Dict, Any, Optional
from datetime import datetime


def setup_logging(level: str = "INFO") -> None:
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: Optional[str] = None) -> structlog.BoundLogger:
    return structlog.get_logger(name or __name__)


def log_error(logger: structlog.BoundLogger, msg: str, **kwargs) -> None:
    logger.error(msg, **kwargs)


def log_info(logger: structlog.BoundLogger, msg: str, **kwargs) -> None:
    logger.info(msg, **kwargs)


def timed(func):
    """Decorator to log execution time."""
    import asyncio
    import time
    from functools import wraps

    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        start = time.time()
        result = await func(*args, **kwargs)
        elapsed = time.time() - start
        log_info(get_logger(), f"{func.__name__} took {elapsed:.2f}s")
        return result

    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        log_info(get_logger(), f"{func.__name__} took {elapsed:.2f}s")
        return result

    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper
