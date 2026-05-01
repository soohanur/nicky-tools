"""
CompanyInfo Search and Data Extraction Module

This module handles automated searching and contact information extraction
from the CompanyInfo website, including:
- Company name and address search
- Contact details extraction (phone, email)
- Related company hierarchy traversal
"""
import re
import time
from typing import Dict, List, Tuple, Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from .browser_automation import BrowserAutomation
from ..utils.logger import setup_logger

logger = setup_logger('companyinfo')


# Constants
KVK_CODE_LENGTH = 8
MOBILE_PREFIX = '06'


# Custom Exceptions
class CompanyNotFoundException(Exception):
    """Raised when company not found in database"""
    pass


class BrowserConnectionError(Exception):
    """Raised when browser/driver connection issues"""
    pass


class CompanyInfoSearcher:
    """
    Automated search and data extraction from CompanyInfo website.
    
    Handles company searches, contact information extraction, and
    related company hierarchy traversal for comprehensive data gathering.
    """
    
    @staticmethod
    def normalize_phone_number(phone: str) -> str:
        """
        Normalize phone number to 0XXXXXXXXX format.
        
        Converts various formats:
        - +31 6 12345678 -> 0612345678
        - 31 6 12345678 -> 0612345678
        - 6 12345678 -> 0612345678
        - 612345678 -> 0612345678
        - 0612345678 -> 0612345678
        
        Args:
            phone: Phone number in any format
            
        Returns:
            Normalized phone number starting with 0
        """
        if not phone:
            return phone
        
        cleaned = phone.replace('-', '').replace(' ', '').replace('(', '').replace(')', '')
        
        # International format: +31 or 31
        if cleaned.startswith('+31'):
            cleaned = '0' + cleaned[3:]
        elif cleaned.startswith('31') and len(cleaned) >= 10:
            cleaned = '0' + cleaned[2:]
        # Domestic format without leading 0
        elif not cleaned.startswith('0') and len(cleaned) >= 9:
            # Numbers like 612345678 or 6XXXXXXXX need leading 0
            cleaned = '0' + cleaned
        
        return cleaned
    
    def __init__(self, browser: BrowserAutomation, base_url: str, timeout: int = 10, email: str = '', password: str = ''):
        """
        Initialize the CompanyInfo searcher.
        
        Args:
            browser: BrowserAutomation instance for web interactions
            base_url: Base URL for CompanyInfo search
            timeout: Maximum wait time for search operations in seconds
            email: Login email for auto-login if logged out
            password: Login password for auto-login if logged out
        """
        self.browser = browser
        self.base_url = base_url
        self.timeout = timeout
        self.driver = browser.driver
        self.email = email
        self.password = password
        self.login_verified = False  # Track if login already verified
        
        logger.info("CompanyInfo searcher initialized")
    
    def _smart_wait(self, max_wait: float = 3.0, check_interval: float = 0.1) -> float:
        """
        Smart adaptive wait that responds to actual page load speed.
        Returns immediately when page is ready, or after max_wait seconds.
        
        Args:
            max_wait: Maximum time to wait in seconds
            check_interval: How often to check page state (seconds)
            
        Returns:
            Actual time waited (for logging/optimization)
        """
        start_time = time.time()
        elapsed = 0
        
        while elapsed < max_wait:
            try:
                # Check if page is ready (interactive or complete)
                ready_state = self.driver.execute_script("return document.readyState")
                if ready_state in ['interactive', 'complete']:
                    logger.debug(f"Smart wait: Page ready in {elapsed:.2f}s (state: {ready_state})")
                    return elapsed
            except:
                pass
            
            time.sleep(check_interval)
            elapsed = time.time() - start_time
        
        logger.debug(f"Smart wait: Completed after max timeout {max_wait}s")
        return elapsed
    
    def _check_and_handle_login(self, force_check: bool = False) -> bool:
        """
        Check if user is logged in and auto-login if needed.
        Skips check if login already verified (unless force_check=True).
        
        Args:
            force_check: Force login verification even if previously verified
        
        Returns:
            True if logged in (or successfully logged in), False otherwise
        """
        try:
            # Skip check if already verified (saves ~0.5s per search)
            if self.login_verified and not force_check:
                return True
            
            # Wait for page to be ready
            try:
                WebDriverWait(self.driver, 3).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
            except:
                pass
            
            # Check if we're on the login page by looking for username field
            try:
                username_field = self.driver.find_element(By.ID, "username")
                if username_field.is_displayed():
                    logger.warning("[WARN] Detected login page - need to login")
                    
                    if not self.email or not self.password:
                        logger.error("Logged out but no credentials provided")
                        return False
                    
                    logger.info("Attempting auto-login...")
                    return self._perform_login()
            except:
                pass
            
            # Check for other login indicators
            login_indicators = [
                "//a[contains(text(), 'Login')]",
                "//a[contains(text(), 'Inloggen')]",
                "//button[contains(text(), 'Login')]",
                "//button[contains(text(), 'Inloggen')]",
                "//h1[contains(text(), 'Login to your account')]",
                "//input[@type='email' and @name='username']",
                "//*[contains(text(), 'session') and contains(text(), 'expired')]",
                "//*[contains(text(), 'uitgelogd')]",
                "//*[contains(text(), 'logged out')]"
            ]
            
            for indicator in login_indicators:
                try:
                    element = self.driver.find_element(By.XPATH, indicator)
                    if element.is_displayed():
                        logger.warning(f"[WARN] Detected logged out state: {indicator}")
                        
                        if not self.email or not self.password:
                            logger.error("Logged out but no credentials provided")
                            return False
                        
                        logger.info("Attempting auto-login...")
                        return self._perform_login()
                except:
                    continue
            
            # If no login indicators found, assume logged in
            logger.debug("[OK] Already logged in")
            self.login_verified = True
            return True
            
        except Exception as e:
            logger.error(f"Error checking login status: {e}")
            return True  # Assume logged in on error to continue
    
    def _perform_login(self) -> bool:
        """
        Perform automatic login using stored credentials.
        Two-step process: 1) Enter email and click Next, 2) Enter password and login
        
        Returns:
            True if login successful, False otherwise
        """
        try:
            # Try to find login link first
            try:
                login_link = self.driver.find_element(By.XPATH, "//a[contains(text(), 'Login') or contains(text(), 'Inloggen')]")
                login_link.click()
                # Wait for login page to load
                WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.ID, "username"))
                )
                logger.info("Clicked login link")
            except:
                # Navigate to company.info login page
                try:
                    self.browser.navigate_to("https://company.info/login")
                    # Wait for login page
                    WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.ID, "username"))
                    )
                except:
                    pass
            
            # STEP 1: Enter email and click Next
            logger.info("Step 1: Entering email...")
            
            # Find email field (id="username")
            email_field = None
            try:
                email_field = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.ID, "username"))
                )
                logger.info("[OK] Found email field by ID")
            except:
                try:
                    email_field = self.driver.find_element(By.XPATH, "//input[@type='email']")
                    logger.info("[OK] Found email field by type")
                except:
                    try:
                        email_field = self.driver.find_element(By.NAME, "username")
                        logger.info("[OK] Found email field by name")
                    except:
                        logger.error("Could not find email input field")
                        return False
            
            if not email_field:
                logger.error("Email field is None")
                return False
            
            # Wait for field to be visible and clickable
            try:
                WebDriverWait(self.driver, 5).until(EC.visibility_of(email_field))
                WebDriverWait(self.driver, 5).until(EC.element_to_be_clickable((By.ID, "username")))
            except:
                logger.warning("Email field may not be fully ready")
            
            # Click field first to focus
            try:
                email_field.click()
            except:
                pass
            
            # Clear and enter email
            email_field.clear()
            email_field.send_keys(self.email)
            logger.info(f"[OK] Entered email: {self.email}")
            
            # Click "Next" button
            try:
                next_btn = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.ID, "ci-login"))
                )
                logger.info("[OK] Found Next button")
                next_btn.click()
                logger.info("[OK] Clicked Next button")
            except:
                try:
                    next_btn = self.driver.find_element(By.XPATH, "//input[@name='login'][@type='submit']")
                    next_btn.click()
                    logger.info("[OK] Clicked Next button (fallback)")
                except Exception as e:
                    logger.error(f"Could not find or click Next button: {e}")
                    return False
            
            # Wait for password page to load (smart wait)
            # No fixed delay needed - WebDriverWait below handles it
            
            # STEP 2: Enter password and login
            logger.info("Step 2: Entering password...")
            
            # Find password field
            password_field = None
            try:
                password_field = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//input[@type='password']"))
                )
                logger.info("[OK] Found password field")
            except:
                logger.error("Password field did not appear - check if email was accepted")
                # Print current URL for debugging
                logger.error(f"Current URL: {self.driver.current_url}")
                return False
            
            # Wait for field to be clickable
            try:
                WebDriverWait(self.driver, 5).until(EC.element_to_be_clickable((By.XPATH, "//input[@type='password']")))
            except:
                logger.warning("Password field may not be fully ready")
            
            # Click field to focus
            try:
                password_field.click()
            except:
                pass
            
            # Enter password
            password_field.clear()
            password_field.send_keys(self.password)
            logger.info("[OK] Entered password")
            
            # Smart wait for login button to be ready (adapts to connection speed)
            self._smart_wait(max_wait=1.5, check_interval=0.1)
            
            # Click login/submit button - Try multiple selectors with better waiting
            login_button_found = False
            login_selectors = [
                (By.ID, "ci-login"),
                (By.XPATH, "//button[@type='submit']"),
                (By.XPATH, "//input[@type='submit']"),
                (By.XPATH, "//button[contains(text(), 'Login')]"),
                (By.XPATH, "//button[contains(text(), 'Inloggen')]"),
                (By.XPATH, "//input[@name='login'][@type='submit']"),
                (By.CSS_SELECTOR, "button[type='submit']"),
                (By.CSS_SELECTOR, "input[type='submit']"),
                (By.XPATH, "//form//button"),
                (By.XPATH, "//form//input[@type='submit']")
            ]
            
            for by_method, selector in login_selectors:
                try:
                    # Wait for element to be clickable
                    login_btn = WebDriverWait(self.driver, 3).until(
                        EC.element_to_be_clickable((by_method, selector))
                    )
                    login_btn.click()
                    logger.info(f"[OK] Clicked Login button using selector: {by_method}={selector}")
                    login_button_found = True
                    break
                except:
                    continue
            
            if not login_button_found:
                logger.error("Could not find Login button with any selector")
                # Take a screenshot for debugging
                try:
                    screenshot_path = "/app/logs/login_button_not_found.png"
                    self.driver.save_screenshot(screenshot_path)
                    logger.info(f"Saved screenshot to {screenshot_path}")
                except:
                    pass
                return False
            
            # Wait for login to complete (smart wait for redirect)
            try:
                WebDriverWait(self.driver, 8).until(
                    EC.invisibility_of_element_located((By.XPATH, "//input[@type='password']"))
                )
            except:
                pass
            
            # Verify login success (check if we're no longer on login page)
            try:
                # If password field still exists, login failed
                self.driver.find_element(By.XPATH, "//input[@type='password']")
                logger.error("Login failed - still on login page")
                return False
            except:
                # Password field gone = successful login
                logger.info("[OK] Auto-login successful")
                self.login_verified = True
                
                # After login, check current URL
                try:
                    current_url = self.driver.current_url
                    logger.info(f"Current URL after login: {current_url}")
                    
                    # If we're on a different page (like profile/dashboard), try refresh
                    # to get to search page, but DON'T navigate which might crash Chrome
                    if '/login' not in current_url.lower() and current_url.rstrip('/') != self.base_url.rstrip('/'):
                        logger.info("Not on base URL after login, trying to find search field directly")
                except Exception as e:
                    logger.warning(f"Could not check URL after login: {e}")
                
                return True
            
        except Exception as e:
            logger.error(f"Error during auto-login: {e}")
            return False
    
    def search_by_company_name(self, company_name: str) -> Dict[str, any]:
        """
        Search CompanyInfo database by company name.
        
        Args:
            company_name: Name of the company to search for
        
        Returns:
            Dictionary containing:
                - success (bool): Whether search succeeded
                - result_count (int): Number of matching results found
                - message (str): Status message
        """
        logger.info(f"Step 1: Searching by company name: '{company_name}'")
        
        try:
            # First ensure we are logged in by checking base URL
            try:
                current_url = self.driver.current_url
                if current_url.rstrip('/') != self.base_url.rstrip('/'):
                    self.browser.navigate_to(self.base_url)
            except Exception:
                pass
            
            # Wait for page to load
            try:
                WebDriverWait(self.driver, 8).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
            except Exception:
                pass
            
            # Check and handle login if needed
            if not self._check_and_handle_login():
                logger.error("Login check failed")
                return self._create_search_result(False, 0, 'Login required but failed')
            
            # DIRECT URL NAVIGATION - bypass unreliable SPA search box
            # The homepage search input is NOT in a <form>, it uses Svelte JS handler
            # which has a race condition: sometimes goes to /organisations/search?query=
            # (correct) and sometimes stays at /?q= (broken, shows 404).
            # Direct navigation to the correct URL is 100% reliable.
            from urllib.parse import quote
            search_url = f"https://company.info/organisations/search?query={quote(company_name)}"
            logger.info(f"Navigating directly to search URL: {search_url}")
            self.driver.get(search_url)
            
            # Wait for search results to load on the new page
            self._wait_for_search_results()
            
            # Wait a moment for DOM to settle
            time.sleep(0.5)
            
            result_count = self._count_search_results()
            
            if result_count == 1:
                logger.info("✓ Found exactly 1 result - opening company page")
                
                if self._click_first_result():
                    logger.info("✓ Opened company page successfully")
                    return self._create_search_result(True, result_count, 'Company page opened successfully')
                else:
                    logger.warning("Failed to click result")
                    return self._create_search_result(False, result_count, 'Could not click result')
                    
            elif result_count > 1:
                logger.info(f"Found {result_count} results - trying to match exact company name: '{company_name}'")
                
                # Try to find an exact name match among the results
                match_result = self._find_exact_name_match(company_name)
                if match_result:
                    logger.info(f"✓ Found exact name match - opened company page")
                    return self._create_search_result(True, result_count, 'Exact name match found and opened')
                else:
                    # No exact match - click the first result as best guess
                    logger.info(f"No exact name match found among {result_count} results - opening first result")
                    if self._click_first_result():
                        logger.info("✓ Opened first result as best match")
                        return self._create_search_result(True, result_count, 'Opened first result (no exact match)')
                    else:
                        logger.warning("Failed to click any result")
                        return self._create_search_result(False, result_count, 'Multiple results found but could not click')
            else:
                logger.warning("No results found for company name")
                return self._create_search_result(False, 0, 'No results found - need to search by address')
        
        except Exception as e:
            logger.error(f"Error in company name search: {e}")
            return self._create_search_result(False, 0, f'Error: {str(e)}')
    
    @staticmethod
    def _create_search_result(success: bool, result_count: int, message: str) -> Dict[str, any]:
        """
        Create standardized search result dictionary.
        
        Args:
            success: Whether the operation succeeded
            result_count: Number of results found
            message: Status or error message
            
        Returns:
            Standardized result dictionary
        """
        return {
            'success': success,
            'result_count': result_count,
            'message': message
        }
    
    def _wait_for_search_results(self) -> None:
        """Wait for search results to load on the /organisations/search page."""
        try:
            # Wait for URL to be the correct search results page
            try:
                WebDriverWait(self.driver, 8).until(
                    lambda d: '/organisations/search' in d.current_url
                )
            except Exception:
                pass
            
            # Wait for actual result content to appear (h5 with "resultaten" or search-result items)
            try:
                WebDriverWait(self.driver, 12).until(
                    lambda d: (
                        len(d.find_elements(By.CSS_SELECTOR, 'li[data-cy="search-result"]')) > 0
                        or len(d.find_elements(By.XPATH, "//*[contains(text(), 'resultaten') or contains(text(), 'resultaat')]")) > 0
                        or 'geen resultaten' in d.page_source.lower()
                        or '0 resultaten' in d.page_source.lower()
                    )
                )
            except Exception:
                pass
            
            # Extra wait for DOM to fully settle
            time.sleep(0.5)
        except Exception:
            # Fallback: wait for page to be interactive
            try:
                WebDriverWait(self.driver, 3).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
                time.sleep(1.0)
            except Exception:
                pass
    
    def _find_search_input(self) -> Optional[any]:
        """
        Locate the search input field using multiple selector strategies.
        Waits longer to handle slow page loads on unstable internet.
        
        Returns:
            WebElement if found, None otherwise
        """
        # Longer timeout for unstable internet (but still smart - returns immediately when found)
        search_timeout = 15
        
        selectors = [
            (By.CSS_SELECTOR, 'input[type="search"]'),
            (By.CSS_SELECTOR, 'input[type="text"]'),
            (By.ID, 'search'),
            (By.NAME, 'q'),
            (By.NAME, 'search'),
            (By.XPATH, '//input[@placeholder]'),
        ]
        
        for by, selector in selectors:
            try:
                element = WebDriverWait(self.driver, search_timeout).until(
                    EC.presence_of_element_located((by, selector))
                )
                if element:
                    logger.debug(f"Found search input using: {selector}")
                    return element
            except:
                continue
        
        # Final attempt: wait for page to fully load then try once more
        try:
            WebDriverWait(self.driver, 5).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            # Try first selector again after page ready
            try:
                element = self.driver.find_element(By.CSS_SELECTOR, 'input[type="search"]')
                if element and element.is_displayed():
                    return element
            except:
                pass
        except:
            pass
        
        return None
    
    def _count_search_results(self) -> int:
        """
        Count search results on the page by reading the result count text.
        Uses retry logic to handle stale element references after page re-render.
        
        Returns:
            Number of results found
        """
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                # Strategy 1: Look for result count in heading text (e.g., "322 resultaten")
                heading_selectors = [
                    (By.XPATH, "//*[contains(text(), 'resultaten')]"),
                    (By.XPATH, "//*[contains(text(), 'resultaat')]"),
                    (By.CSS_SELECTOR, "h5"),
                    (By.TAG_NAME, "h2"),
                ]
                
                for by, selector in heading_selectors:
                    try:
                        elements = self.driver.find_elements(by, selector)
                        for element in elements:
                            try:
                                text = element.text.strip()
                                match = re.search(r'(\d+)\s*resultate?n?', text, re.IGNORECASE)
                                if match:
                                    count = int(match.group(1))
                                    logger.debug(f"Found result count from text: {count} (from '{text}')")
                                    return count
                            except StaleElementReferenceException:
                                logger.debug(f"Stale element on attempt {attempt+1}, re-finding...")
                                break  # Break inner loop to retry this selector with fresh elements
                    except StaleElementReferenceException:
                        continue
                
                # Strategy 2: Count actual result rows on the page
                row_selectors = [
                    (By.CSS_SELECTOR, 'li[data-cy="search-result"]'),
                    (By.CSS_SELECTOR, '.row.svelte-j41fqr'),
                    (By.CSS_SELECTOR, '.search-result'),
                    (By.CSS_SELECTOR, '.result-item'),
                ]
                
                for by, selector in row_selectors:
                    try:
                        results = self.driver.find_elements(by, selector)
                        if results:
                            count = len(results)
                            logger.debug(f"Found {count} result rows on current page")
                            return count
                    except StaleElementReferenceException:
                        continue
                
                # Strategy 3: Check page source for no-result indicators
                try:
                    page_text = self.driver.page_source.lower()
                    no_results_texts = [
                        'no results', 'geen resultaten', 'no records found',
                        'niet gevonden', '0 results', '0 resultaten'
                    ]
                    
                    for text in no_results_texts:
                        if text in page_text:
                            logger.debug(f"Found 'no results' indicator: {text}")
                            return 0
                except StaleElementReferenceException:
                    pass
                
                # If we got here without finding anything, wait and retry
                if attempt < max_retries - 1:
                    logger.debug(f"No results found on attempt {attempt+1}, waiting before retry...")
                    time.sleep(1.0)
                    # Re-wait for search results to ensure DOM is settled
                    self._wait_for_search_results()
                    continue
                
                # Final attempt: could not determine count
                logger.warning("Could not determine result count from page after all retries")
                return 0
                
            except StaleElementReferenceException:
                logger.warning(f"Stale element on attempt {attempt+1}/{max_retries}, retrying...")
                if attempt < max_retries - 1:
                    time.sleep(1.0)
                    self._wait_for_search_results()
                continue
            except Exception as e:
                logger.error(f"Error counting results (attempt {attempt+1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(0.5)
                    continue
                return 0
        
        return 0
    
    def _click_first_result(self) -> bool:
        """
        Click the first search result
        
        Returns:
            True if clicked successfully, False otherwise
        """
        # Try multiple selectors for first result link - company.info specific
        selectors = [
            (By.CSS_SELECTOR, 'li[data-cy="search-result"]:first-child a'),
            (By.CSS_SELECTOR, '.row.svelte-j41fqr:first-child a'),
            (By.CSS_SELECTOR, '[data-cy="search-result"] a'),
            (By.XPATH, '(//li[@data-cy="search-result"]//a)[1]'),
            (By.XPATH, '(//div[contains(@class, "svelte")]//a)[1]'),
            (By.CSS_SELECTOR, 'a[href*="company.info"]'),
        ]
        
        for by, selector in selectors:
            try:
                # Wait up to 2 seconds for this specific selector
                first_result = WebDriverWait(self.driver, 2).until(
                    EC.presence_of_element_located((by, selector))
                )
                
                if first_result:
                    current_url = self.driver.current_url
                    
                    # Try to click
                    try:
                        first_result.click()
                    except:
                        # If regular click fails, try JavaScript click
                        self.driver.execute_script("arguments[0].click();", first_result)
                    
                    # Wait for URL to change (page navigation)
                    try:
                        WebDriverWait(self.driver, 5).until(EC.url_changes(current_url))
                    except:
                        # Fallback: wait for page to load
                        try:
                            WebDriverWait(self.driver, 2).until(
                                lambda d: d.execute_script("return document.readyState") == "complete"
                            )
                        except:
                            pass
                    
                    logger.debug(f"Clicked first result using selector: {selector}")
                    return True
            except Exception as e:
                logger.debug(f"Selector failed {selector}: {e}")
                continue
        
        return False
    
    def _find_exact_name_match(self, company_name: str) -> bool:
        """
        When multiple search results are found, iterate through them and find
        the one whose name exactly matches the company name from our sheet.
        
        Args:
            company_name: The company name to match against
            
        Returns:
            True if exact match found and clicked, False otherwise
        """
        # Normalize the target name for comparison
        target_name = company_name.strip().lower()
        # Also create a version without common suffixes for flexible matching
        target_clean = re.sub(r'\s*(b\.?v\.?|n\.?v\.?|v\.?o\.?f\.?|c\.?v\.?)\s*$', '', target_name, flags=re.IGNORECASE).strip()
        
        # Selectors to find all result links
        result_selectors = [
            (By.CSS_SELECTOR, 'li[data-cy="search-result"] a'),
            (By.CSS_SELECTOR, '.row.svelte-j41fqr a'),
            (By.CSS_SELECTOR, '[data-cy="search-result"] a'),
        ]
        
        for by, selector in result_selectors:
            try:
                result_links = self.driver.find_elements(by, selector)
                if not result_links:
                    continue
                
                logger.debug(f"Found {len(result_links)} result links to check for exact match")
                
                for i, link in enumerate(result_links):
                    try:
                        link_text = link.text.strip().lower()
                        link_clean = re.sub(r'\s*(b\.?v\.?|n\.?v\.?|v\.?o\.?f\.?|c\.?v\.?)\s*$', '', link_text, flags=re.IGNORECASE).strip()
                        
                        logger.debug(f"  Result {i+1}: '{link_text}' vs target '{target_name}'")
                        
                        # Check for exact match (with or without legal suffix)
                        if link_text == target_name or link_clean == target_clean or link_text == target_clean or link_clean == target_name:
                            logger.info(f"✓ EXACT MATCH found at result {i+1}: '{link.text.strip()}'")
                            
                            current_url = self.driver.current_url
                            
                            try:
                                link.click()
                            except Exception:
                                self.driver.execute_script("arguments[0].click();", link)
                            
                            # Wait for navigation
                            try:
                                WebDriverWait(self.driver, 5).until(EC.url_changes(current_url))
                            except Exception:
                                try:
                                    WebDriverWait(self.driver, 2).until(
                                        lambda d: d.execute_script("return document.readyState") == "complete"
                                    )
                                except Exception:
                                    pass
                            
                            return True
                            
                    except StaleElementReferenceException:
                        logger.debug(f"Stale element at result {i+1}, re-fetching results...")
                        # Re-fetch all result links and try again from the beginning
                        try:
                            time.sleep(0.5)
                            result_links = self.driver.find_elements(by, selector)
                            continue
                        except Exception:
                            break
                    except Exception as e:
                        logger.debug(f"Error checking result {i+1}: {e}")
                        continue
                
                # If we found links but no exact match, return False
                if result_links:
                    logger.info(f"No exact name match found among {len(result_links)} results")
                    return False
                    
            except StaleElementReferenceException:
                time.sleep(0.5)
                continue
            except Exception as e:
                logger.debug(f"Error with selector {selector}: {e}")
                continue
        
        return False
    
    def search_by_address(self, address: str) -> dict:
        """
        Step 2: Search CompanyInfo by address
        
        Implements fallback strategy:
        1. Try full address (e.g., "Bagijnesingel 1 ZWOLLE")
        2. If no results, remove city and retry (e.g., "Bagijnesingel 1")
        
        Args:
            address: Address to search
        
        Returns:
            dict with 'success', 'result_count', 'message' keys
        """
        logger.info(f"Step 2: Searching by address: '{address}'")
        
        # Try full address first
        result = self._search_address_attempt(address)
        
        if result['success'] or result['result_count'] > 0:
            return result
        
        # If no results and address has multiple words, try without last word (city name)
        address_parts = address.strip().split()
        if len(address_parts) > 1:
            # Remove last word (assumed to be city name)
            address_without_city = ' '.join(address_parts[:-1])
            logger.info(f"No results found. Retrying without city: '{address_without_city}'")
            
            result = self._search_address_attempt(address_without_city)
            if result['success']:
                result['message'] = 'Found via address search (without city name)'
            return result
        
        return result
    
    def _search_address_attempt(self, address: str) -> dict:
        """
        Single address search attempt using direct URL navigation.
        
        Args:
            address: Address string to search
        
        Returns:
            dict with 'success', 'result_count', 'message' keys
        """
        try:
            # Ensure we are logged in first
            try:
                current_url = self.driver.current_url
                if 'company.info' not in current_url:
                    self.browser.navigate_to(self.base_url)
                    self._smart_wait(max_wait=4.0, check_interval=0.2)
            except Exception:
                pass
            
            # Check and handle login if needed
            self._check_and_handle_login()
            
            # DIRECT URL NAVIGATION - bypass unreliable SPA search box
            from urllib.parse import quote
            search_url = f"https://company.info/organisations/search?query={quote(address)}"
            logger.info(f"Navigating directly to address search URL: {search_url}")
            self.driver.get(search_url)
            
            # Wait for results to load
            self._wait_for_search_results()
            time.sleep(0.5)
            
            # Wait for results to load
            self._wait_for_search_results()
            time.sleep(0.5)
            
            # Check results
            result_count = self._count_search_results()
            
            if result_count > 0:
                logger.info(f"Found {result_count} result(s)")
                
                # Click first result
                first_result_clicked = self._click_first_result()
                
                if first_result_clicked:
                    logger.info("✓ Clicked first result")
                    return {
                        'success': True,
                        'result_count': result_count,
                        'message': 'First result clicked successfully'
                    }
                else:
                    logger.warning("Failed to click first result")
                    return {
                        'success': False,
                        'result_count': result_count,
                        'message': 'Could not click first result'
                    }
            else:
                logger.warning("No results found for address")
                return {
                    'success': False,
                    'result_count': 0,
                    'message': 'No results found'
                }
        
        except Exception as e:
            logger.error(f"Error in address search: {e}")
            return {
                'success': False,
                'result_count': 0,
                'message': f'Error: {str(e)}'
            }
    
    def extract_contact_info(self) -> dict:
        """
        Extract phone, email, business name, and owner name from current company page
        Implements Step 3 and Step 3.1 logic
        
        IMPORTANT: First checks "Enig aandeelhouders" section. If the owner has 
        more than 15 businesses (very rich person), skips this company entirely.
        
        Returns:
            dict with 'phone', 'email', 'business', 'owner', and 'source' keys
            If too many businesses: returns {'skip': True, 'reason': '...'}
        """
        logger.info("Extracting contact information from company page...")
        
        result = {
            'phone': None,
            'email': None,
            'business': None,
            'owner': None,
            'source': 'main_page'
        }
        
        # Track best phone found (in case we don't find 06)
        fallback_phone = None
        
        try:
            # Wait for page to load completely
            try:
                WebDriverWait(self.driver, 5).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
            except:
                pass
            
            # ==========================================
            # STEP 0: CHECK PHONE ON MAIN PAGE FIRST
            # Then check business count - only skip if
            # NO phone found AND owner has >15 businesses
            # ==========================================
            
            # STEP 3: Extract from main company page FIRST (before business count check)
            logger.info("Step 3: Checking main company page 'Contactgegevens'...")
            
            # Extract phone numbers from "Contactgegevens" section
            phones = self._extract_phone_numbers()
            
            # Extract email addresses
            emails = self._extract_emails()
            
            # Collect ALL phone numbers
            all_phones = []
            mobile_phones = []
            other_phones = []
            
            if phones:
                mobile_phones = [p for p in phones if p.replace('-', '').replace(' ', '').startswith('06')]
                other_phones = [p for p in phones if not p.replace('-', '').replace(' ', '').startswith('06')]
                all_phones = mobile_phones + other_phones
                
                if all_phones:
                    result['phones'] = all_phones
                    result['business'] = self._extract_business_name()
                    result['owner'] = self._extract_owner_name()
                    logger.info(f"✓ Found {len(all_phones)} number(s): {', '.join(all_phones)}")
            
            if emails:
                result['email'] = emails[0]
                logger.info(f"✓ Found email: {result['email']}")
            
            # NOW check business count - only skip if NO phone found on main page
            logger.info("Step 0: Checking owner's business count...")
            
            shareholders_header = self._find_shareholders_section()
            if shareholders_header:
                try:
                    self._expand_company_list()
                    self._scroll_page()
                    
                    company_links = self._extract_company_links()
                    business_count = len(company_links)
                    
                    logger.info(f"Owner has {business_count} related businesses")
                    
                    if business_count > 15 and not all_phones:
                        # No phone on main page AND too many businesses → skip
                        logger.warning(f"🚫 SKIPPING: No phone found AND owner has {business_count} businesses (>15)")
                        return {
                            'skip': True,
                            'reason': f'Owner has {business_count} businesses (threshold: 15)',
                            'note': f'SKIPPED: Owner has {business_count} businesses (targeting small/mid business owners only)',
                            'phone': None,
                            'email': None,
                            'business': None,
                            'owner': None
                        }
                    elif business_count > 15 and all_phones:
                        # Phone found on main page, don't skip even with many businesses
                        logger.info(f"✓ Owner has {business_count} businesses BUT phone found on main page - NOT skipping")
                    else:
                        logger.info(f"✓ Business count OK ({business_count} ≤ 15) - Proceeding with extraction")
                except Exception as e:
                    logger.warning(f"Could not count businesses, proceeding anyway: {e}")
            else:
                logger.info("No 'Enig aandeelhouders' section found - proceeding with extraction")
            
            # If we have phone numbers AND email → DONE
            if all_phones and result['email']:
                logger.info("✓ Found phone number(s) and email - COMPLETE")
                result['note'] = 'SUCCESS: Contact info extracted successfully'
                return result
            
            # STEP 3.1: Missing phone or email, check related companies
            need_mobile = not all_phones
            need_email = result['email'] is None
            
            logger.info(f"⚠ Missing {'phone number' if need_mobile else ''}{' and ' if need_mobile and need_email else ''}{'email' if need_email else ''}")
            logger.info("→ Checking related companies in 'Enig aandeelhouders' section...")
            
            related_data = self._check_related_companies(need_mobile=need_mobile, need_email=need_email)
            
            # Update result with data from related companies
            if need_mobile and related_data.get('phones'):
                result['phones'] = related_data['phones']
                result['business'] = related_data.get('business')
                result['owner'] = related_data.get('owner')
                result['source'] = 'related_company'
                logger.info(f"✓ Found phone number(s) from related company: {', '.join(result['phones'])}")
                logger.info(f"✓ Business: {result['business']}")
                logger.info(f"✓ Owner: {result['owner']}")
            
            if need_email and related_data.get('email'):
                result['email'] = related_data['email']
                # Only update business/owner if not already set
                if not result.get('business'):
                    result['business'] = related_data.get('business')
                    result['owner'] = related_data.get('owner')
                result['source'] = 'related_company'
                logger.info(f"✓ Found email from related company: {result['email']}")
            
            # Add detailed note explaining what was found/missing
            has_phone = bool(result.get('phones'))
            has_email = bool(result.get('email'))
            
            if has_phone and has_email:
                result['note'] = 'SUCCESS: Contact info extracted from related company'
            elif has_phone and not has_email:
                result['note'] = 'PARTIAL: Phone found but email not available on company page or related companies'
            elif not has_phone and has_email:
                result['note'] = 'PARTIAL: Email found but phone number not available on company page or related companies'
            else:
                result['note'] = 'NO CONTACT: Company page found but no phone or email available (checked main page and related companies)'
            
            return result
            
        except Exception as e:
            logger.error(f"Error extracting contact info: {e}")
            result['note'] = f'ERROR: Failed to extract contact info - {str(e)[:100]}'
            return result
    
    def _extract_phone_numbers(self) -> list:
        """Extract phone numbers from Contactgegevens section"""
        phones = []
        
        # Known false positive numbers (company.info's own numbers / UI artifacts)
        blacklisted_phones = {'0202400400', '00202400400', '+31202400400', '0031202400400'}
        
        try:
            # Try to find the Contactgegevens section and get nearby phone links
            try:
                # Find the div containing "Contactgegevens" text
                contact_header = self.driver.find_element(By.XPATH, 
                    "//*[contains(text(), 'Contactgegevens')]")
                
                # Get the parent container
                contact_section = contact_header.find_element(By.XPATH, "..")
                
                # Look for phone links within the parent section
                phone_elements = contact_section.find_elements(By.XPATH, ".//a[starts-with(@href, 'tel:')]")
                
                for elem in phone_elements:
                    phone = elem.get_attribute('href').replace('tel:', '').strip()
                    phone = self.normalize_phone_number(phone)
                    if phone and phone not in phones:
                        phones.append(phone)
                        logger.debug(f"Found phone in Contactgegevens: {phone}")
                
            except:
                # Fallback: search entire page
                phone_elements = self.driver.find_elements(By.XPATH, "//a[starts-with(@href, 'tel:')]")
                
                for elem in phone_elements:
                    phone = elem.get_attribute('href').replace('tel:', '').strip()
                    phone = self.normalize_phone_number(phone)
                    if phone and phone not in phones:
                        phones.append(phone)
            
        except Exception as e:
            logger.debug(f"Error extracting phones: {e}")
        
        # Filter out blacklisted numbers (company.info's own switchboard etc.)
        phones = [p for p in phones if p.replace('+', '').replace('-', '').replace(' ', '') not in blacklisted_phones 
                  and self.normalize_phone_number(p).replace('+', '').replace('-', '').replace(' ', '') not in blacklisted_phones]
        
        return phones
    
    def _extract_emails(self) -> list:
        """Extract email addresses from Contactgegevens section"""
        emails = []
        
        try:
            # Try to find the Contactgegevens section and get nearby email links
            try:
                # Find the div containing "Contactgegevens" text
                contact_header = self.driver.find_element(By.XPATH, 
                    "//*[contains(text(), 'Contactgegevens')]")
                
                # Get the parent container
                contact_section = contact_header.find_element(By.XPATH, "..")
                
                # Look for mailto: links within the parent section
                email_elements = contact_section.find_elements(By.XPATH, ".//a[starts-with(@href, 'mailto:')]")
                
                logger.debug(f"Found {len(email_elements)} mailto links in Contactgegevens section")
                
                for elem in email_elements:
                    href = elem.get_attribute('href')
                    email = href.replace('mailto:', '').strip() if href else ''
                    logger.debug(f"Checking email: {email}")
                    
                    # Filter out generic company.info emails
                    if email and '@' in email and 'company.info' not in email.lower() and email not in emails:
                        emails.append(email)
                        logger.debug(f"Found email in Contactgegevens: {email}")
                
                # If still no emails, try all mailto links on page
                if not emails:
                    logger.debug("No emails in Contactgegevens, searching entire page")
                    all_email_elements = self.driver.find_elements(By.XPATH, "//a[starts-with(@href, 'mailto:')]")
                    logger.debug(f"Found {len(all_email_elements)} total mailto links on page")
                    
                    for elem in all_email_elements:
                        href = elem.get_attribute('href')
                        email = href.replace('mailto:', '').strip() if href else ''
                        
                        if email and '@' in email and 'company.info' not in email.lower() and email not in emails:
                            emails.append(email)
                            logger.debug(f"Found email on page: {email}")
                    
            except Exception as e:
                logger.debug(f"Error finding Contactgegevens section: {e}")
                # Fallback: search entire page but exclude company.info emails
                email_elements = self.driver.find_elements(By.XPATH, "//a[starts-with(@href, 'mailto:')]")
                
                for elem in email_elements:
                    href = elem.get_attribute('href')
                    email = href.replace('mailto:', '').strip() if href else ''
                    if email and '@' in email and 'company.info' not in email.lower() and email not in emails:
                        emails.append(email)
            
        except Exception as e:
            logger.error(f"Error extracting emails: {e}")
        
        return emails
    
    def _extract_business_name(self) -> Optional[str]:
        """
        Extract the business/company name from current page.
        Looks for the main H1 heading which contains the company name.
        
        Returns:
            Company name if found, None otherwise
        """
        try:
            # Find the main company name from h1 heading
            # Known UI element text that should be excluded
            ui_noise = ['organisaties', 'snel zoeken', 'functionarissen', 'nieuws',
                        'compliance', 'vastgoed', 'meer', 'account', 'zoeken',
                        'home', 'help', 'inloggen', 'login']
            try:
                h1_element = self.driver.find_element(By.TAG_NAME, "h1")
                business_name = h1_element.text.strip()
                if business_name and business_name.lower() not in ui_noise:
                    logger.debug(f"Found business name from h1: {business_name}")
                    return business_name
            except:
                pass
            
            # Fallback: try to find from page title
            try:
                title = self.driver.title
                # Remove " - Company.info" suffix if present
                business_name = title.replace(' - Company.info', '').replace(' | Company.info', '').strip()
                if business_name and business_name.lower() not in ui_noise + ['company.info']:
                    logger.debug(f"Found business name from title: {business_name}")
                    return business_name
            except:
                pass
            
        except Exception as e:
            logger.debug(f"Error extracting business name: {e}")
        
        return None
    
    def _extract_owner_name(self) -> Optional[str]:
        
        """
        Extract the owner/eigenaar name from current page.
        Looks in "Enig Aandeelhouders & Management" section under "Eigenaar" field.
        
        Returns:
            Owner name if found, None otherwise
        """
        try:
            # Primary method: Find "Eigenaar" text and get the link after it
            try:
                # Look for "Eigenaar" text in the Enig Aandeelhouders section
                eigenaar_label = self.driver.find_element(By.XPATH, 
                    "//*[contains(text(), 'Eigenaar')]")
                
                # Get the parent container and find the link within it
                parent = eigenaar_label.find_element(By.XPATH, "..")
                owner_link = parent.find_element(By.XPATH, ".//a")
                owner_name = owner_link.text.strip()
                
                if owner_name:
                    logger.debug(f"Found owner from Eigenaar section: {owner_name}")
                    return owner_name
            except:
                pass
            
            # Fallback 1: Look under "Enig Aandeelhouders & Management" heading
            try:
                management_heading = self.driver.find_element(By.XPATH, 
                    "//*[contains(text(), 'Enig Aandeelhouders & Management') or contains(text(), 'Enig aandeelhouders')]")
                
                # Find the first link after this heading
                owner_link = management_heading.find_element(By.XPATH, 
                    "./following::a[1]")
                owner_name = owner_link.text.strip()
                
                if owner_name:
                    logger.debug(f"Found owner from Management section: {owner_name}")
                    return owner_name
            except:
                pass
            
            # Fallback 2: Find from "Bestuurders" section (Management/Directors)
            try:
                director_element = self.driver.find_element(By.XPATH, 
                    "//*[contains(text(), 'Bestuurders')]/following::a[1]")
                owner_name = director_element.text.strip()
                if owner_name:
                    logger.debug(f"Found owner from Bestuurders: {owner_name}")
                    return owner_name
            except:
                pass
            
        except Exception as e:
            logger.debug(f"Error extracting owner name: {e}")
        
        return None
    
    def _check_related_companies(self, need_mobile: bool = True, need_email: bool = True) -> Dict[str, Optional[str]]:
        """
        Extract contact information from related companies in shareholder hierarchy.
        
        Searches the 'Enig aandeelhouders' section for related companies,
        expands collapsed lists, and systematically checks each company's
        contact details until required information is found.
        
        Args:
            need_mobile: Whether to search for mobile (06) phone number
            need_email: Whether to search for email address
            
        Returns:
            Dictionary with 'phones', 'email', 'business', 'owner' keys (None if not found)
        """
        result = {'phones': None, 'email': None, 'business': None, 'owner': None}
        
        try:
            shareholders_header = self._find_shareholders_section()
            if not shareholders_header:
                return result
            
            # Wait for shareholders section to be fully loaded
            try:
                WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, "//a[contains(@href, '/id/')]" ))
                )
            except:
                pass
            
            self._expand_company_list()
            self._scroll_page()
            
            company_links = self._extract_company_links()
            
            if not company_links:
                logger.info("No company links found in 'Eigenaar' column")
                return result
            
            return self._check_companies_for_contact_info(
                company_links, 
                need_mobile, 
                need_email
            )
                
        except Exception as e:
            logger.debug(f"Error checking related companies: {e}")
        
        return result
    
    def _find_shareholders_section(self) -> Optional[any]:
        """
        Locate the shareholders section on the company page.
        
        Returns:
            WebElement of shareholders header if found, None otherwise
        """
        try:
            shareholders_header = self.driver.find_element(By.XPATH, 
                "//*[contains(text(), 'Enig aandeelhouders') or contains(text(), 'Aandeelhouders')]")
            logger.info("Found 'Enig aandeelhouders' section")
            return shareholders_header
        except:
            logger.info("No 'Enig aandeelhouders' section found")
            return None
    
    def _expand_company_list(self) -> None:
        """
        Click 'Toon meer' (Show more) buttons to expand full company list.
        
        Uses JavaScript click to bypass any overlay elements that might
        intercept regular click events.
        """
        expand_selectors = [
            "//button[@data-cy='show-more']",
            "//button[contains(text(), 'Toon meer')]",
            "//*[contains(text(), 'Toon meer')]",
        ]
        
        total_clicked = 0
        for selector in expand_selectors:
            try:
                expand_buttons = self.driver.find_elements(By.XPATH, selector)
                if expand_buttons:
                    logger.info(f"Found {len(expand_buttons)} 'Toon meer' elements")
                    for btn in expand_buttons:
                        try:
                            self.driver.execute_script("arguments[0].click();", btn)
                            total_clicked += 1
                            logger.info(f"  ✓ Clicked 'Toon meer' button #{total_clicked}")
                            # Wait for new content to appear
                            try:
                                WebDriverWait(self.driver, 3).until(
                                    lambda d: d.execute_script("return document.readyState") == "complete"
                                )
                            except:
                                pass
                        except:
                            pass
                    break
            except:
                pass
        
        logger.info(f"Total 'Toon meer' buttons clicked: {total_clicked}")
        
        if total_clicked > 0:
            # Wait for all new content to load
            try:
                WebDriverWait(self.driver, 3).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
            except:
                pass
    
    def _scroll_page(self) -> None:
        """Scroll page to trigger loading of any lazy-loaded content."""
        try:
            # Quick scroll - modern pages auto-load instantly
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            self.driver.execute_script("window.scrollTo(0, 0);")
        except:
            pass
    
    def _extract_company_links(self) -> List[Tuple[str, str]]:
        """
        Extract all unique company KVK codes and build their URLs.
        
        Scans the page for all company links containing KVK identification codes,
        filters for valid 8-digit codes, and constructs standardized URLs.
        
        Returns:
            List of tuples containing (company_name, company_url)
        """
        company_links = []
        
        try:
            all_id_links = self.driver.find_elements(By.XPATH, "//a[contains(@href, '/id/')]")
            logger.info(f"Found {len(all_id_links)} total /id/ links on page")
            
            seen_kvk = set()
            
            for link in all_id_links:
                try:
                    href = link.get_attribute('href')
                    if not href or '/id/' not in href:
                        continue
                    
                    kvk_code = self._extract_kvk_from_url(href)
                    
                    if kvk_code and kvk_code not in seen_kvk:
                        seen_kvk.add(kvk_code)
                        company_url = f"https://company.info/id/{kvk_code}?fw=true"
                        company_name = link.text.strip() or kvk_code
                        company_links.append((company_name, company_url))
                        logger.info(f"  ✓ {company_name} (KVK: {kvk_code})")
                except:
                    continue
            
            logger.info(f"Total unique company links found: {len(company_links)}")
            logger.info(f"KVK codes: {sorted(list(seen_kvk))}")
            
        except Exception as e:
            logger.warning(f"Error finding company links: {e}")
        
        return company_links
    
    @staticmethod
    def _extract_kvk_from_url(url: str) -> Optional[str]:
        """
        Extract KVK code from company.info URL.
        
        Args:
            url: Full URL containing KVK code
            
        Returns:
            8-digit KVK code if valid, None otherwise
        """
        try:
            kvk_code = url.split('/id/')[1].split('?')[0].split('/')[0]
            if len(kvk_code) == KVK_CODE_LENGTH and kvk_code.isdigit():
                return kvk_code
        except:
            pass
        return None
    
    def _check_companies_for_contact_info(
        self, 
        company_links: List[Tuple[str, str]], 
        need_mobile: bool, 
        need_email: bool
    ) -> Dict[str, Optional[str]]:
        """
        Systematically check each company for required contact information.
        Limited to maximum 15 companies to save time.
        
        Args:
            company_links: List of (company_name, url) tuples to check
            need_mobile: Whether mobile number is needed
            need_email: Whether email is needed
            
        Returns:
            Dictionary with found 'phone' and 'email' values
        """
        result = {'phone': None, 'email': None, 'business': None, 'owner': None}
        
        # Limit to maximum 15 companies
        MAX_COMPANIES_TO_CHECK = 15
        total_companies = len(company_links)
        companies_to_check = min(total_companies, MAX_COMPANIES_TO_CHECK)
        
        logger.info(f"Found {total_companies} links in 'Eigenaar' column")
        if total_companies > MAX_COMPANIES_TO_CHECK:
            logger.info(f"⚡ Speed optimization: Checking first {MAX_COMPANIES_TO_CHECK} companies only")
        
        for idx, (company_name, href) in enumerate(company_links[:companies_to_check], 1):
            try:
                logger.info(f"Checking related company {idx}/{companies_to_check}: {company_name}")
                
                full_url = href if href.startswith('http') else f"https://company.info{href}"
                self.driver.get(full_url)
                
                # Smart wait for page to load
                try:
                    WebDriverWait(self.driver, 5).until(
                        lambda d: d.execute_script("return document.readyState") == "complete"
                    )
                except:
                    pass
                
                if need_mobile:
                    phone_list = self._find_mobile_number()
                    if phone_list:
                        result['phones'] = phone_list
                        result['business'] = self._extract_business_name()
                        result['owner'] = self._extract_owner_name()
                        logger.info(f"✓ Found phone number(s) in related company: {', '.join(phone_list)}")
                        logger.info(f"✓ Business: {result['business']}")
                        logger.info(f"✓ Owner: {result['owner']}")
                        need_mobile = False
                
                if need_email:
                    email = self._find_email_address()
                    if email:
                        result['email'] = email
                        # Only update business/owner if not already found with phone
                        if not result.get('business'):
                            result['business'] = self._extract_business_name()
                            result['owner'] = self._extract_owner_name()
                        logger.info(f"✓ Found email in related company: {email}")
                        need_email = False
                
                if not need_mobile and not need_email:
                    logger.info("✓ Found both 06 number and email - stopping search")
                    return result
                
            except Exception as e:
                logger.debug(f"Error checking related company: {e}")
        
        return result
    
    def _find_mobile_number(self) -> Optional[List[str]]:
        """
        Extract ALL phone numbers from current page (06, 05, etc).
        Returns list with 06 numbers first.
        
        Returns:
            List of phone numbers (06 first) if found, None otherwise
        """
        phones = self._extract_phone_numbers()
        if phones:
            mobile_phones = [p for p in phones 
                           if p.replace('-', '').replace(' ', '').startswith(MOBILE_PREFIX)]
            other_phones = [p for p in phones 
                          if not p.replace('-', '').replace(' ', '').startswith(MOBILE_PREFIX)]
            
            # Combine: 06 numbers first, then others
            all_phones = mobile_phones + other_phones
            if all_phones:
                return all_phones
        return None
    
    def _find_email_address(self) -> Optional[str]:
        """
        Extract email address from current page.
        
        Returns:
            Email address if found, None otherwise
        """
        emails = self._extract_emails()
        return emails[0] if emails else None
    
    def search_company(self, company_name: str, street: str = '', house_number: str = '', city: str = '') -> Dict[str, str]:
        """
        Wrapper method for searching company and extracting contact info.
        This is the main entry point for the automation workflow.
        
        Args:
            company_name: Company name to search
            street: Street name (optional)
            house_number: House number (optional)
            city: City name (optional)
        
        Returns:
            Dictionary with 'phone' and 'email' keys
            If company should be skipped: returns {'skip': True, 'reason': '...'}
        """
        # Build address string
        address_parts = [part for part in [street, house_number, city] if part]
        address = ' '.join(address_parts) if address_parts else ''
        
        logger.info(f"Searching for: {company_name}" + (f" at {address}" if address else ""))
        
        # Try searching by company name first
        search_result = self.search_by_company_name(company_name)
        
        # If company name search failed and we have address, try address search
        if not search_result['success'] and address:
            logger.info("Company name search failed, trying address search...")
            search_result = self.search_by_address(address)
        
        # If we found a company page, extract contact info
        if search_result['success']:
            contact_info = self.extract_contact_info()
            
            # Check if company should be skipped (too many businesses)
            if contact_info.get('skip'):
                logger.warning(f"⏭ SKIP: {contact_info.get('reason')}")
                return {
                    'skip': True,
                    'reason': contact_info.get('reason'),
                    'note': contact_info.get('note', 'SKIPPED: Too many businesses'),
                    'phones': [],
                    'email': '',
                    'business': '',
                    'owner': ''
                }
            
            return {
                'phones': contact_info.get('phones', []),
                'email': contact_info.get('email', ''),
                'business': contact_info.get('business', ''),
                'owner': contact_info.get('owner', ''),
                'note': contact_info.get('note', '')
            }
        else:
            logger.warning("Could not find company page")
            # Determine specific failure reason
            if address:
                note = 'NOT FOUND: Company not found in database (searched by name and address)'
            else:
                note = 'NOT FOUND: Company not found in database (searched by name only)'
            
            return {
                'phones': [], 
                'email': '', 
                'business': '', 
                'owner': '',
                'note': note
            }