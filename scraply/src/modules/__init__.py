"""Modules package"""
from .excel_reader import ExcelReader
from .csv_reader import CSVReader as CSVReaderClass
from .csv_writer_simple import CSVWriter as CSVWriterClass
from .browser_automation import BrowserAutomation
from .companyinfo_searcher import CompanyInfoSearcher

# Aliases for backward compatibility
Browser = BrowserAutomation
CSVReader = CSVReaderClass  # Use actual CSVReader, not ExcelReader
CSVWriter = CSVWriterClass  # Use the simple CSV writer
CompanyInfoScraper = CompanyInfoSearcher

def create_browser(profile_path=None, headless=False, profile_name='Default', implicit_wait=5):
    """Create and start a browser instance."""
    browser = BrowserAutomation(
        profile_path=str(profile_path) if profile_path else None,
        profile_name=profile_name,
        headless=headless,
        implicit_wait=implicit_wait
    )
    browser.start_browser()
    return browser

__all__ = [
    'BrowserAutomation', 'Browser', 'create_browser',
    'ExcelReader', 'CSVReader',
    'CSVWriter',
    'CompanyInfoSearcher', 'CompanyInfoScraper'
]
