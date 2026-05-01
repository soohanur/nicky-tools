"""Configuration settings for scraply automation."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from project root
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
env_path = PROJECT_ROOT / '.env'
load_dotenv(dotenv_path=env_path)


class Config:
    """Main configuration class."""
    
    # Paths
    PROJECT_ROOT = PROJECT_ROOT
    CHROME_PROFILE_PATH = os.getenv('CHROME_PROFILE_PATH', '')
    CHROME_PROFILE_NAME = os.getenv('CHROME_PROFILE_NAME', 'Default')
    
    # Input/Output
    INPUT_CSV = os.getenv('INPUT_EXCEL_PATH', 'scraply/csv_files/input/Test_10_rows.csv')
    OUTPUT_CSV = os.getenv('OUTPUT_CSV_PATH', 'scraply/csv_files/output/results_final.csv')
    
    # CSV Column mappings
    COL_COMPANY = os.getenv('COL_COMPANY_NAME', 'Achternaam lead')
    COL_STREET = os.getenv('COL_ADDRESS_PART1', 'Straatnaam adres lead')
    COL_HOUSE_NUMBER = os.getenv('COL_ADDRESS_PART2', 'Huisnummer adres lead')
    COL_CITY = os.getenv('COL_ADDRESS_PART3', 'Plaats adres lead')
    COL_PHONE = os.getenv('COL_PHONE_OUTPUT', 'telefoonnummer')
    COL_EMAIL = os.getenv('COL_EMAIL_OUTPUT', 'email')
    
    # Browser settings
    HEADLESS = os.getenv('HEADLESS_MODE', 'True').lower() == 'true'
    IMPLICIT_WAIT = int(os.getenv('IMPLICIT_WAIT', '2'))
    PAGE_LOAD_TIMEOUT = int(os.getenv('PAGE_LOAD_TIMEOUT', '15'))
    
    # CompanyInfo settings
    COMPANYINFO_URL = os.getenv('COMPANYINFO_URL', 'https://company.info/search')
    COMPANYINFO_EMAIL = os.getenv('COMPANYINFO_EMAIL', '')
    COMPANYINFO_PASSWORD = os.getenv('COMPANYINFO_PASSWORD', '')
    COMPANYINFO_TIMEOUT = int(os.getenv('COMPANYINFO_SEARCH_TIMEOUT', '10'))
    
    # Processing
    MAX_WORKERS = int(os.getenv('MAX_WORKERS', '1'))
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')


# Export config instance
config = Config()
