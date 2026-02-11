import logging
import time
from functools import wraps

logger = logging.getLogger(__name__)

def timing_decorator(func):
    """Decorator to measure execution time"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        
        logger.info(f"⏱️ {func.__name__} executed in {execution_time:.2f}s")
        
        if execution_time > 10:
            logger.warning(f"🐌 {func.__name__} is slow! Took {execution_time:.2f}s")
        elif execution_time > 5:
            logger.warning(f"⚠️ {func.__name__} took {execution_time:.2f}s")
        
        return result
    return wrapper

def log_performance_metrics(operation: str, duration: float, success: bool = True):
    """Log performance metrics"""
    status = "✅" if success else "❌"
    
    if duration < 1:
        logger.info(f"{status} {operation}: {duration:.2f}s (Fast)")
    elif duration < 3:
        logger.info(f"{status} {operation}: {duration:.2f}s (Normal)")
    elif duration < 10:
        logger.warning(f"⚠️ {operation}: {duration:.2f}s (Slow)")
    else:
        logger.error(f"🐌 {operation}: {duration:.2f}s (Very Slow)")
        
    # Suggest optimizations
    if duration > 15:
        logger.error(f"💡 Consider optimizing {operation} - it's taking too long")