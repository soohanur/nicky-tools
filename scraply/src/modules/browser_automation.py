"""
Browser Automation Module

Manages Selenium WebDriver instance with Chrome profile support,
providing controlled web interaction and element discovery capabilities.
"""
import os
import time
import shutil
from typing import Optional, List
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from ..utils.logger import setup_logger

logger = setup_logger('browser')


# Constants
DEFAULT_IMPLICIT_WAIT = 5
# company.info pages are heavy; a 5s driver-level budget made navigation fail
# ("timeout: Timed out receiving message from renderer") and killed the login,
# which left whole runs empty. The searchers already wait for real content, so a
# generous ceiling here costs nothing on a fast page.
DEFAULT_PAGE_LOAD_TIMEOUT = 45
DEFAULT_SCRIPT_TIMEOUT = 30
DEFAULT_WAIT_TIMEOUT = 10
REMOTE_DEBUGGING_PORT = 9222


class BrowserAutomation:
    """
    Selenium-based browser automation with Chrome profile support.
    
    Provides managed browser lifecycle, navigation, and safe element
    discovery with automatic timeout handling.
    """
    
    def __init__(
        self, 
        profile_path: Optional[str] = None, 
        profile_name: str = 'Default', 
        headless: bool = False, 
        implicit_wait: int = DEFAULT_IMPLICIT_WAIT
    ):
        """
        Initialize browser automation manager.
        
        Args:
            profile_path: Path to Chrome user data directory
            profile_name: Chrome profile directory name
            headless: Run browser in headless mode
            implicit_wait: Default implicit wait time in seconds
        """
        self.profile_path = profile_path
        self.profile_name = profile_name
        self.headless = headless
        self.implicit_wait = implicit_wait
        self.driver = None
        
        logger.info(f"Browser automation initialized (Headless: {headless})")
    
    def start_browser(self) -> None:
        """
        Initialize and start Chrome browser with configured options.
        
        Raises:
            Exception: If browser fails to start
        """
        try:
            chrome_options = self._configure_chrome_options()
            
            logger.info("Starting Chrome browser...")
            
            # Check if we're in Docker/Linux environment with system ChromeDriver
            chromedriver_path = shutil.which('chromedriver')
            if chromedriver_path and os.path.exists('/usr/local/bin/chromedriver'):
                logger.info(f"Using system ChromeDriver: {chromedriver_path}")
                service = Service(chromedriver_path)
            else:
                logger.info("Using webdriver-manager to download ChromeDriver")
                service = Service(ChromeDriverManager().install())
            
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            self._configure_timeouts()
            
            logger.info("[OK] Chrome browser started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start browser: {e}")
            raise
    
    def _configure_chrome_options(self) -> Options:
        """
        Configure Chrome options including profile and performance settings.
        
        Returns:
            Configured Chrome Options instance
        """
        chrome_options = Options()
        
        if self.profile_path:
            chrome_options.add_argument(f"user-data-dir={self.profile_path}")
            chrome_options.add_argument(f"profile-directory={self.profile_name}")
            chrome_options.add_argument('--disable-features=ProfilePicker')
            chrome_options.add_argument(f'--remote-debugging-port={REMOTE_DEBUGGING_PORT}')
            logger.info(f"Using Chrome profile: {self.profile_path}/{self.profile_name}")
        
        if self.headless:
            chrome_options.add_argument('--headless=new')
        
        # Essential flags for Docker/Linux containers
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--start-maximized')
        
        # Docker-specific flags (prevent Chrome crashes in containers)
        chrome_options.add_argument('--disable-gpu')  # No GPU on server
        # REMOVED --single-process: causes crashes on navigation after login
        # chrome_options.add_argument('--single-process')  # Too unstable, causes session crashes
        chrome_options.add_argument('--disable-software-rasterizer')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-plugins')
        chrome_options.add_argument('--disable-background-networking')
        chrome_options.add_argument('--disable-sync')
        chrome_options.add_argument('--disable-translate')
        chrome_options.add_argument('--disable-features=TranslateUI')
        chrome_options.add_argument('--disk-cache-size=1')  # Minimal disk cache
        chrome_options.add_argument('--media-cache-size=1')  # Minimal media cache
        
        # Stability improvements for long-running sessions
        chrome_options.add_argument('--disable-breakpad')  # Disable crash reporting
        chrome_options.add_argument('--disable-crash-reporter')
        chrome_options.add_argument('--no-first-run')
        chrome_options.add_argument('--no-default-browser-check')
        
        # Explicitly enable JavaScript and all content
        prefs = {
            "profile.managed_default_content_settings.javascript": 1,
            "profile.default_content_setting_values.javascript": 1,
            "profile.managed_default_content_settings.images": 2,  # 2 = Block images for faster loading
            "profile.default_content_setting_values.images": 2,     # Text-only mode
            "profile.managed_default_content_settings.stylesheets": 1,
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.page_load_strategy = 'normal'  # Load everything including images, CSS, JS
        
        return chrome_options
    
    def _configure_timeouts(self) -> None:
        """Configure browser timeout settings."""
        self.driver.implicitly_wait(self.implicit_wait)
        self.driver.set_page_load_timeout(DEFAULT_PAGE_LOAD_TIMEOUT)
        self.driver.set_script_timeout(DEFAULT_SCRIPT_TIMEOUT)
        
        # Ensure window is visible and on top
        try:
            self.driver.maximize_window()
            self.driver.set_window_position(0, 0)
            logger.info("Browser window positioned and maximized")
        except Exception as e:
            logger.warning(f"Could not position window: {e}")
    
    def close_browser(self) -> None:
        """Terminate browser instance and cleanup resources."""
        if self.driver:
            # Clear browser data before closing (server optimization)
            try:
                self.driver.execute_script("window.localStorage.clear();")
                self.driver.execute_script("window.sessionStorage.clear();")
                self.driver.delete_all_cookies()
            except:
                pass
            
            self.driver.quit()
            logger.info("Browser closed (cache cleared)")
    
    def navigate_to(self, url: str) -> None:
        """
        Navigate browser to specified URL.
        
        Args:
            url: Target URL
            
        Raises:
            Exception: If navigation fails
        """
        try:
            self.driver.get(url)
            logger.info(f"Navigated to: {url}")
        except Exception as e:
            logger.error(f"Failed to navigate to {url}: {e}")
            raise
    
    def wait_for_element(
        self, 
        by: By, 
        value: str, 
        timeout: int = DEFAULT_WAIT_TIMEOUT
    ) -> Optional[any]:
        """
        Wait for element to become present in DOM.
        
        Args:
            by: Selenium locator strategy
            value: Locator value
            timeout: Maximum wait time in seconds
        
        Returns:
            WebElement if found within timeout, None otherwise
        """
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return element
        except TimeoutException:
            logger.warning(f"Timeout waiting for element: {by}='{value}'")
            return None
    
    def find_element_safe(self, by: By, value: str) -> Optional[any]:
        """
        Locate single element without raising exceptions.
        
        Args:
            by: Selenium locator strategy
            value: Locator value
        
        Returns:
            WebElement if found, None otherwise
        """
        try:
            return self.driver.find_element(by, value)
        except NoSuchElementException:
            return None
    
    def find_elements_safe(self, by: By, value: str) -> List[any]:
        """
        Locate multiple elements without raising exceptions.
        
        Args:
            by: Selenium locator strategy
            value: Locator value
        
        Returns:
            List of WebElements (empty if none found)
        """
        try:
            return self.driver.find_elements(by, value)
        except NoSuchElementException:
            return []
    
    def __enter__(self):
        """Context manager entry point."""
        self.start_browser()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit point."""
        self.close_browser()
