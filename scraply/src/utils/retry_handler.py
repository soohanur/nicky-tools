"""
Retry and Error Recovery Handler

Provides intelligent retry logic with exponential backoff,
browser recovery, and data validation.
"""
import time
import logging
from typing import Callable, Any, Optional
from functools import wraps

logger = logging.getLogger('retry_handler')


class RetryConfig:
    """Retry configuration constants."""
    MAX_RETRIES = 2
    INITIAL_DELAY = 2  # seconds
    BACKOFF_MULTIPLIER = 2
    MAX_DELAY = 10  # seconds
    

def retry_with_recovery(
    max_attempts: int = RetryConfig.MAX_RETRIES,
    delay: float = RetryConfig.INITIAL_DELAY,
    backoff: float = RetryConfig.BACKOFF_MULTIPLIER,
    exceptions: tuple = (Exception,),
    browser_restart_on_fail: bool = False
):
    """
    Decorator for retry logic with exponential backoff.
    
    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries (seconds)
        backoff: Multiplier for exponential backoff
        exceptions: Tuple of exceptions to catch and retry
        browser_restart_on_fail: Whether to restart browser on final failure
        
    Returns:
        Decorated function with retry logic
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            current_delay = delay
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    result = func(*args, **kwargs)
                    
                    # Validate result has data
                    if _validate_result(result):
                        if attempt > 1:
                            logger.info(f"✓ Success on attempt {attempt}/{max_attempts}")
                        return result
                    else:
                        logger.warning(f"⚠ Attempt {attempt}/{max_attempts}: No data extracted, retrying...")
                        
                except exceptions as e:
                    last_exception = e
                    logger.warning(f"⚠ Attempt {attempt}/{max_attempts} failed: {str(e)[:100]}")
                    
                    # Check if browser-related error
                    if _is_browser_error(e):
                        logger.warning("Browser error detected - may need restart")
                
                # Brief pause before retry (minimal, not blocking)
                if attempt < max_attempts:
                    logger.info(f"Retrying immediately (smart waits will handle timing)...")
                    current_delay = min(current_delay * backoff, RetryConfig.MAX_DELAY)
            
            # All attempts failed
            logger.error(f"✗ All {max_attempts} attempts failed")
            
            if browser_restart_on_fail:
                logger.error("Browser restart recommended")
                
            # Return empty result instead of raising
            return _get_empty_result()
            
        return wrapper
    return decorator


def _validate_result(result: Any) -> bool:
    """
    Validate that result contains actual data.
    
    Args:
        result: Result to validate
        
    Returns:
        True if result has data, False otherwise
    """
    if result is None:
        return False
        
    if isinstance(result, dict):
        # Check if phone or email found
        phone = result.get('phone')
        email = result.get('email')
        
        # Consider valid if we have at least phone OR email (not NULL)
        has_phone = phone and phone != 'NULL' and str(phone).strip()
        has_email = email and email != 'NULL' and str(email).strip()
        
        return has_phone or has_email
    
    return True  # Non-dict results assumed valid


def _is_browser_error(exception: Exception) -> bool:
    """
    Check if exception is browser-related.
    
    Args:
        exception: Exception to check
        
    Returns:
        True if browser error, False otherwise
    """
    error_indicators = [
        'chrome',
        'driver',
        'session',
        'timeout',
        'renderer',
        'connection',
        'webdriver',
        'browser'
    ]
    
    error_msg = str(exception).lower()
    return any(indicator in error_msg for indicator in error_indicators)


def is_permanent_error(error_msg: str, result: dict = None) -> bool:
    """
    Determine if error is permanent (don't retry) or transient (can retry).
    
    Permanent errors (DON'T retry):
    - Not found / No results
    - Invalid data
    - Already searched successfully but no contact info
    
    Transient errors (DO retry):
    - Network timeout
    - Browser crash
    - Session expired
    
    Args:
        error_msg: Error message or status
        result: Result dictionary if available
        
    Returns:
        True if permanent (don't retry), False if transient (can retry)
    """
    error_lower = error_msg.lower()
    
    # Permanent: Data doesn't exist
    permanent_indicators = [
        'not found',
        'no results',
        'search input not found',
        'multiple results',  # Need address search, not retry
        'invalid data',
        'no matching',
    ]
    
    for indicator in permanent_indicators:
        if indicator in error_lower:
            return True
    
    # If we successfully searched but just no contact info = permanent
    if result and result.get('status') == 'SUCCESS':
        if result.get('phone') == 'NULL' and result.get('email') == 'NULL':
            return True  # Data doesn't exist, retrying won't help
    
    # Transient errors (worth retrying)
    transient_indicators = [
        'timeout',
        'connection',
        'network',
        'chrome',
        'session',
        'renderer',
        'webdriver'
    ]
    
    # If it's a transient error, retry is worthwhile
    for indicator in transient_indicators:
        if indicator in error_lower:
            return False
    
    # Unknown error - be conservative, allow 1 retry
    return False


def _get_empty_result() -> dict:
    """
    Get empty result dictionary for failed attempts.
    
    Returns:
        Empty result dictionary
    """
    return {
        'phone': 'NULL',
        'email': 'NULL',
        'business': 'NULL',
        'owner': 'NULL',
        'status': 'FAIL',
        'notes': 'Failed after all retry attempts'
    }


def check_browser_health(driver) -> bool:
    """
    Check if browser is still responsive.
    
    Args:
        driver: Selenium WebDriver instance
        
    Returns:
        True if healthy, False otherwise
    """
    try:
        # Try to get current URL (quick health check)
        _ = driver.current_url
        
        # Try to execute simple JavaScript
        driver.execute_script("return document.readyState")
        
        return True
        
    except Exception as e:
        logger.error(f"Browser health check failed: {e}")
        return False


def recover_browser(browser_instance, logger_instance):
    """
    Attempt to recover browser from error state.
    
    Args:
        browser_instance: BrowserAutomation instance
        logger_instance: Logger instance
        
    Returns:
        True if recovery successful, False otherwise
    """
    try:
        logger_instance.warning("🔄 Attempting browser recovery...")
        
        # Close current browser
        try:
            browser_instance.driver.quit()
        except:
            pass
        
        # Restart browser immediately (smart waits handle timing)
        browser_instance.start_browser()
        
        logger_instance.info("✓ Browser recovered successfully")
        return True
        
    except Exception as e:
        logger_instance.error(f"Browser recovery failed: {e}")
        return False
