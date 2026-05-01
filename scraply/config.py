"""
Scraply - CompanyInfo Automation Tool Configuration
Dedicated configuration for Scraply tool with isolated resources
"""

import os
from pathlib import Path
from typing import Optional

# Base directory - Scraply tool folder
BASE_DIR = Path(__file__).resolve().parent  # scraply/ folder
PROJECT_ROOT = BASE_DIR.parent  # project root

# Scraply-specific directories (isolated from other tools)
CSV_DIR = BASE_DIR / "csv_files"
INPUT_DIR = CSV_DIR / "input"
OUTPUT_DIR = CSV_DIR / "output"

# Chrome profiles - SHARED at project root (optimized for memory)
PROFILES_DIR = PROJECT_ROOT / "chrome_profiles"  # Shared across all tools

# Logs directory (scraply-specific)
LOGS_DIR = BASE_DIR / "logs"

# Create directories if they don't exist
for directory in [CSV_DIR, INPUT_DIR, OUTPUT_DIR, LOGS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Chrome profiles are shared at project root - ensure they exist
PROFILES_DIR.mkdir(parents=True, exist_ok=True)


class Config:
    """Scraply Configuration - CompanyInfo Automation Tool
    
    All resources are isolated within scraply/ folder:
    - CSV files: scraply/csv_files/
    - Chrome profiles: scraply/chrome_profiles/
    - Logs: scraply/logs/
    
    This isolation prevents conflicts with future automation tools.
    """
    
    # Tool Information
    TOOL_NAME = "Scraply"
    TOOL_VERSION = "2.0.0"
    TOOL_DESCRIPTION = "CompanyInfo.com Data Scraper"
    
    # ============ File Paths (Scraply-Specific) ============
    BASE_DIR = BASE_DIR
    PROJECT_ROOT = PROJECT_ROOT
    CSV_DIR = CSV_DIR
    INPUT_DIR = INPUT_DIR
    OUTPUT_DIR = OUTPUT_DIR
    PROFILES_DIR = PROFILES_DIR  # Shared across all tools (memory optimized)
    LOGS_DIR = LOGS_DIR
    
    # ============ Browser Settings ============
    # Chrome profile paths (SHARED - all tools use same profiles)
    CHROME_PROFILE_PATH = PROFILES_DIR / "default"
    CHROME_DATA_PROFILE_PATH = PROFILES_DIR / "data_profile"
    
    # Browser options
    HEADLESS_MODE = True
    WINDOW_SIZE = "1920,1080"
    
    # ============ Processing Settings ============
    # Processing mode: "sequential" or "parallel"
    PROCESSING_MODE = "sequential"
    
    # Maximum parallel workers (used when PROCESSING_MODE = "parallel")
    MAX_WORKERS = 5
    
    # Retry settings
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # seconds
    
    # Timeout settings
    PAGE_LOAD_TIMEOUT = 30  # seconds
    ELEMENT_WAIT_TIMEOUT = 10  # seconds
    
    # ============ Output Settings ============
    # Output file prefix
    OUTPUT_PREFIX = "DONE_"
    
    # CSV delimiter
    CSV_DELIMITER = ","
    
    # Excel sheet name
    EXCEL_SHEET_NAME = "Sheet1"
    
    # ============ Logging Settings ============
    LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    LOG_FORMAT = "%(asctime)s - [Scraply] %(name)s - %(levelname)s - %(message)s"
    LOG_FILE_NAME = "scraply.log"  # Scraply-specific log file
    
    @classmethod
    def get_log_file_path(cls) -> Path:
        """Get the full path to the log file"""
        return cls.LOGS_DIR / cls.LOG_FILE_NAME
    
    @classmethod
    def get_input_file_path(cls, filename: str) -> Path:
        """Get the full path to an input file"""
        return cls.INPUT_DIR / filename
    
    @classmethod
    def get_output_file_path(cls, filename: str) -> Path:
        """Get the full path to an output file"""
        # Add prefix if not already present
        if not filename.startswith(cls.OUTPUT_PREFIX):
            name_parts = filename.rsplit(".", 1)
            if len(name_parts) == 2:
                filename = f"{cls.OUTPUT_PREFIX}{name_parts[0]}.{name_parts[1]}"
            else:
                filename = f"{cls.OUTPUT_PREFIX}{filename}"
        
        return cls.OUTPUT_DIR / filename
    
    @classmethod
    def ensure_directories_exist(cls):
        """Ensure all required directories exist"""
        for directory in [cls.INPUT_DIR, cls.OUTPUT_DIR, cls.PROFILES_DIR, cls.LOGS_DIR]:
            directory.mkdir(parents=True, exist_ok=True)


# Environment-specific settings (can be overridden)
class DevelopmentConfig(Config):
    """Development environment configuration"""
    HEADLESS_MODE = False  # Show browser in development
    LOG_LEVEL = "DEBUG"


class ProductionConfig(Config):
    """Production environment configuration"""
    HEADLESS_MODE = True  # Hide browser in production
    LOG_LEVEL = "INFO"
    PROCESSING_MODE = "parallel"
    MAX_WORKERS = 10


# Default configuration
config = Config()


def get_config(env: Optional[str] = None) -> Config:
    """
    Get configuration based on environment
    
    Args:
        env: Environment name ('development', 'production', or None for default)
    
    Returns:
        Config instance
    """
    if env == "development":
        return DevelopmentConfig()
    elif env == "production":
        return ProductionConfig()
    else:
        return Config()


# Utility functions for backward compatibility
def get_chrome_profile_path() -> str:
    """Get Chrome profile path as string"""
    return str(config.CHROME_PROFILE_PATH)


def get_chrome_data_profile_path() -> str:
    """Get Chrome data profile path as string"""
    return str(config.CHROME_DATA_PROFILE_PATH)


if __name__ == "__main__":
    # Test configuration
    print("=" * 60)
    print("Configuration Test")
    print("=" * 60)
    print(f"Base Directory: {Config.BASE_DIR}")
    print(f"Input Directory: {Config.INPUT_DIR}")
    print(f"Output Directory: {Config.OUTPUT_DIR}")
    print(f"Profiles Directory: {Config.PROFILES_DIR}")
    print(f"Logs Directory: {Config.LOGS_DIR}")
    print(f"Chrome Profile: {Config.CHROME_PROFILE_PATH}")
    print(f"Chrome Data Profile: {Config.CHROME_DATA_PROFILE_PATH}")
    print(f"Log File: {Config.get_log_file_path()}")
    print()
    print(f"Example Input File: {Config.get_input_file_path('Number.csv')}")
    print(f"Example Output File: {Config.get_output_file_path('Number.csv')}")
    print("=" * 60)
