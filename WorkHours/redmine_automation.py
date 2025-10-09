#!/usr/bin/env python3
"""
Redmine Time Entries Automation Script

This script automates the process of:
1. Logging into Redmine
2. Navigating to time entries page
3. Setting filters for last month and user
4. Applying filters
5. Exporting to CSV

Requirements:
- selenium
- python-dotenv
- Chrome browser with ChromeDriver
"""

import os
import sys
import time
from contextlib import contextmanager
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from dotenv import load_dotenv


@contextmanager
def suppress_output():
    """Context manager to suppress stdout and stderr output"""
    with open(os.devnull, "w") as devnull:
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = devnull
        sys.stderr = devnull
        try:
            yield
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr


class RedmineTimeEntriesExporter:
    def __init__(self, headless=False, verbose=False):
        """Initialize the Redmine exporter."""
        # Load environment variables
        load_dotenv()
        self.verbose = verbose
        
        self.redmine_url = os.getenv('REDMINE_URL')
        self.username = os.getenv('REDMINE_USERNAME')
        self.password = os.getenv('REDMINE_PASSWORD')
        
        if not self.username or not self.password:
            raise ValueError("REDMINE_USERNAME and REDMINE_PASSWORD must be set in .env file")
        
        # Setup Chrome options
        chrome_options = Options()
        if headless:
            chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        
        # Reduce output if not verbose
        if not self.verbose:
            chrome_options.add_argument('--disable-logging')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--log-level=3')
            chrome_options.add_argument('--silent')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_argument('--disable-web-security')
            chrome_options.add_argument('--disable-features=VizDisplayCompositor')
            chrome_options.add_experimental_option('excludeSwitches', ['enable-logging', 'enable-automation'])
            chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Set download directory to current project directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        download_prefs = {
            "download.default_directory": current_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        chrome_options.add_experimental_option("prefs", download_prefs)
        
        # Initialize WebDriver (suppress output if not verbose)
        if self.verbose:
            self.driver = webdriver.Chrome(options=chrome_options)
        else:
            # Create service with suppressed output
            service = Service()
            service.log_path = os.devnull
            with suppress_output():
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.wait = WebDriverWait(self.driver, 10)
        
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.driver.quit()
    
    def login(self):
        """Log into Redmine if redirected to login page."""
        if self.verbose:
            print("Navigating to Redmine...")
        self.driver.get(self.redmine_url)
        
        # Check if we're redirected to login page
        current_url = self.driver.current_url
        if '/login' in current_url:
            if self.verbose:
                print("Login required. Logging in...")
            
            try:
                # Find username and password fields
                username_field = self.wait.until(
                    EC.presence_of_element_located((By.ID, 'username'))
                )
                password_field = self.driver.find_element(By.ID, 'password')
                
                # Enter credentials
                username_field.clear()
                username_field.send_keys(self.username)
                password_field.clear()
                password_field.send_keys(self.password)
                
                # Submit login form
                login_button = self.driver.find_element(By.NAME, 'login')
                login_button.click()
                
                # Wait for login to complete
                self.wait.until(
                    lambda driver: '/login' not in driver.current_url
                )
                if self.verbose:
                    print("Successfully logged in!")
                
            except TimeoutException:
                raise Exception("Login failed - could not find login form elements")
        else:
            if self.verbose:
                print("Already logged in or no login required.")
    
    def navigate_to_time_entries(self):
        """Navigate to the time entries page."""
        if self.verbose:
            print("Navigating to time entries page...")
        time_entries_url = f"{self.redmine_url.rstrip('/')}/time_entries"
        self.driver.get(time_entries_url)
        
        # Wait for page to load
        self.wait.until(
            EC.presence_of_element_located((By.ID, 'operators_spent_on'))
        )
        if self.verbose:
            print("Time entries page loaded.")
    
    def set_date_filter_to_last_month(self):
        """Set the date filter to 'múlt hónap' (last month)."""
        if self.verbose:
            print("Setting date filter to last month...")
        
        try:
            # Find the date operators dropdown
            date_operators_select = Select(
                self.driver.find_element(By.ID, 'operators_spent_on')
            )
            
            # Select "múlt hónap" (last month)
            date_operators_select.select_by_value('lm')
            if self.verbose:
                print("Date filter set to 'múlt hónap' (last month).")
            
        except NoSuchElementException:
            raise Exception("Could not find date operators dropdown")
    
    def add_user_filter(self):
        """Add user filter by selecting 'Felhasználó' from the filter dropdown."""
        if self.verbose:
            print("Adding user filter...")
        
        try:
            # Find the add filter dropdown
            add_filter_select = Select(
                self.driver.find_element(By.ID, 'add_filter_select')
            )
            
            # Select "Felhasználó" (User)
            add_filter_select.select_by_value('user_id')
            if self.verbose:
                print("User filter added.")
            
            # Wait a moment for the filter to be added to the form
            time.sleep(1)
            
        except NoSuchElementException:
            raise Exception("Could not find add filter dropdown")
    
    def apply_filters(self):
        """Click the Apply button to apply the filters."""
        if self.verbose:
            print("Applying filters...")
        
        try:
            # Find and click the Apply button
            apply_button = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'a.icon.icon-checked'))
            )
            apply_button.click()
            
            # Wait for the page to reload with applied filters
            time.sleep(3)
            if self.verbose:
                print("Filters applied successfully.")
            
        except TimeoutException:
            raise Exception("Could not find or click Apply button")
    
    def export_to_csv(self):
        """Click the CSV export button and handle the export dialog."""
        if self.verbose:
            print("Initiating CSV export...")
        
        try:
            # Find and click the CSV export button
            csv_button = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'a.csv'))
            )
            csv_button.click()
            
            # Wait for the export dialog to appear
            if self.verbose:
                print("Waiting for export dialog...")
            time.sleep(2)
            
            # Find and click the Export button in the dialog
            export_button = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'input[type="submit"][value="Export"]'))
            )
            export_button.click()
            
            if self.verbose:
                print("CSV export completed. Check your downloads folder.")
            
            # Wait a moment for the download to start
            time.sleep(3)
            
        except TimeoutException:
            raise Exception("Could not find CSV export button or Export dialog button")
    
    def delete_existing_csv(self):
        """Delete existing timelog.csv file if it exists."""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        csv_file_path = os.path.join(current_dir, 'timelog.csv')
        
        if os.path.exists(csv_file_path):
            try:
                os.remove(csv_file_path)
                if self.verbose:
                    print("Deleted existing timelog.csv file.")
            except OSError as e:
                if self.verbose:
                    print(f"Warning: Could not delete existing timelog.csv: {e}")
        else:
            if self.verbose:
                print("No existing timelog.csv file found.")
    
    def run_automation(self):
        """Run the complete automation process."""
        try:
            if self.verbose:
                print("Starting Redmine time entries export automation...")
            
            # Step 0: Delete existing CSV file
            self.delete_existing_csv()
            
            # Step 1: Login if needed
            self.login()
            
            # Step 2: Navigate to time entries page
            self.navigate_to_time_entries()
            
            # Step 3: Set date filter to last month
            self.set_date_filter_to_last_month()
            
            # Step 4: Add user filter
            self.add_user_filter()
            
            # Step 5: Apply filters
            self.apply_filters()
            
            # Step 6: Export to CSV
            self.export_to_csv()
            
            if self.verbose:
                print("Automation completed successfully!")
            
            # Keep browser open for a few seconds to see the result
            time.sleep(5)
            
        except Exception as e:
            print(f"Error during automation: {str(e)}")
            # Take a screenshot for debugging
            self.driver.save_screenshot('error_screenshot.png')
            print("Screenshot saved as 'error_screenshot.png' for debugging.")
            raise


def main():
    """Main function to run the automation."""
    import sys
    
    # Check for verbose flag
    verbose = '--verbose' in sys.argv or '-v' in sys.argv
    
    try:
        # Run with browser output suppressed if not verbose
        if verbose:
            # Run with visible browser and full output
            with RedmineTimeEntriesExporter(headless=False, verbose=verbose) as exporter:
                exporter.run_automation()
        else:
            # Run with suppressed output
            with suppress_output():
                with RedmineTimeEntriesExporter(headless=True, verbose=verbose) as exporter:
                    exporter.run_automation()
            print("✅ Redmine CSV export completed!")

    except Exception as e:
        print(f"❌ Automation failed: {str(e)}")
        if not verbose:
            print("💡 Run with --verbose flag for detailed error information")
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())