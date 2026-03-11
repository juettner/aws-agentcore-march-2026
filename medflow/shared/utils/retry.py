import logging
import time
from typing import Callable, TypeVar, Optional
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')


class RetryableError(Exception):
    """Exception that should trigger a retry."""
    pass


def exponential_backoff_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    exceptions: tuple = (RetryableError, ConnectionError, TimeoutError)
):
    """
    Decorator for retry with exponential backoff.
    Formula: delay = base_delay * (2 ^ attempt_number)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_attempts - 1:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_attempts} failed: {e}. "
                            f"Retrying in {delay}s..."
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"All {max_attempts} attempts failed. Last error: {e}"
                        )
            
            raise last_exception
        
        return wrapper
    return decorator


async def async_exponential_backoff_retry(
    func: Callable,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    exceptions: tuple = (RetryableError, ConnectionError, TimeoutError),
    *args,
    **kwargs
) -> T:
    """Async version of exponential backoff retry."""
    import asyncio
    
    last_exception = None
    
    for attempt in range(max_attempts):
        try:
            return await func(*args, **kwargs)
        except exceptions as e:
            last_exception = e
            
            if attempt < max_attempts - 1:
                delay = base_delay * (2 ** attempt)
                logger.warning(
                    f"Attempt {attempt + 1}/{max_attempts} failed: {e}. "
                    f"Retrying in {delay}s..."
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    f"All {max_attempts} attempts failed. Last error: {e}"
                )
    
    raise last_exception
