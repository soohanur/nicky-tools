"""
Logging Utility Module

Provides colored console logging with file output support
for comprehensive application monitoring and debugging.
"""
import logging
import sys
from pathlib import Path
from typing import Optional
from colorama import init, Fore, Style

init(autoreset=True)


class ColoredFormatter(logging.Formatter):
    """
    Console formatter with color coding by log level.
    
    Applies ANSI color codes to log level names for improved
    readability in terminal output.
    """
    
    LEVEL_COLORS = {
        'DEBUG': Fore.CYAN,
        'INFO': Fore.GREEN,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Fore.RED + Style.BRIGHT,
    }

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record with colored level name.
        
        Args:
            record: Log record to format
            
        Returns:
            Formatted log string with color codes
        """
        color = self.LEVEL_COLORS.get(record.levelname, '')
        record.levelname = f"{color}{record.levelname}{Style.RESET_ALL}"
        return super().format(record)


def setup_logger(
    name: str = 'automation',
    log_file: Optional[Path] = None,
    log_level: str = 'INFO'
) -> logging.Logger:
    """
    Configure logger with console and optional file output.
    
    Creates a logger with colored console output for user visibility
    and detailed file logging for debugging. Automatically handles
    duplicate handler cleanup.
    
    Args:
        name: Logger identifier
        log_file: Optional path for file logging
        log_level: Minimum level to log (DEBUG/INFO/WARNING/ERROR/CRITICAL)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper()))
    logger.handlers.clear()
    
    logger.addHandler(_create_console_handler())
    
    if log_file:
        logger.addHandler(_create_file_handler(log_file))
    
    return logger


def _create_console_handler() -> logging.StreamHandler:
    """
    Create colored console handler for user-facing logs.
    
    Returns:
        Console handler with color formatting
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.WARNING)  # Only show warnings and errors in console
    
    formatter = ColoredFormatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    handler.setFormatter(formatter)
    
    return handler


def _create_file_handler(log_file: Path) -> logging.FileHandler:
    """
    Create detailed file handler for debugging.
    
    Args:
        log_file: Path to log file
        
    Returns:
        File handler with detailed formatting
    """
    handler = logging.FileHandler(log_file, encoding='utf-8')
    handler.setLevel(logging.DEBUG)
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    
    return handler


def log_step(logger: logging.Logger, step_name: str, status: str = 'START') -> None:
    """
    Log workflow step with visual separation.
    
    Provides clear visual markers for workflow phases to improve
    log readability during execution monitoring.
    
    Args:
        logger: Logger instance to use
        step_name: Human-readable step description
        status: Step state (START/COMPLETE/FAIL)
    """
    separator = '=' * 60
    
    if status == 'START':
        logger.debug(f"\n{separator}")
        logger.debug(f"Starting: {step_name}")
        logger.debug(separator)
    elif status == 'COMPLETE':
        logger.debug(f"✓ Completed: {step_name}")
    elif status == 'FAIL':
        logger.error(f"✗ Failed: {step_name}")
