#!/usr/bin/env python3
"""
Complete Redmine Timesheet Automation

This script automates the complete workflow:
1. Export CSV from Redmine (using Selenium)
2. Parse CSV and create Excel timesheet
3. Clean up temporary CSV file

Usage:
    python redmine_timesheet_automation.py           # Quiet mode
    python redmine_timesheet_automation.py --verbose # Detailed output
    python redmine_timesheet_automation.py -v        # Detailed output

Requirements:
- selenium
- pandas
- openpyxl
- python-dotenv
- Chrome browser with ChromeDriver
"""

import os
import sys
import time
from datetime import datetime

# Import our existing modules
from redmine_automation import RedmineTimeEntriesExporter
from csv_parser import RedmineCSVParser


class CompleteTimesheetAutomation:
    def __init__(self, verbose=False):
        """Initialize the complete automation workflow."""
        self.verbose = verbose
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.csv_filename = 'timelog.csv'
        self.csv_path = os.path.join(self.current_dir, self.csv_filename)
        
    def log(self, message, force=False):
        """Log message only if verbose mode is enabled or forced."""
        if self.verbose or force:
            print(message)
    
    def run_redmine_export(self):
        """Step 1: Export CSV from Redmine using Selenium."""
        self.log("🔄 Step 1: Exporting time entries from Redmine...")
        
        try:
            # Use headless mode unless verbose (for debugging)
            headless = not self.verbose
            
            with RedmineTimeEntriesExporter(headless=headless) as exporter:
                exporter.run_automation()
            
            # Wait a moment for file to be fully written
            time.sleep(2)
            
            # Verify CSV was created
            if not os.path.exists(self.csv_path):
                raise FileNotFoundError(f"CSV export failed - file not found: {self.csv_path}")
            
            # Check file size to ensure it's not empty
            file_size = os.path.getsize(self.csv_path)
            if file_size == 0:
                raise ValueError("CSV export failed - file is empty")
            
            self.log(f"✅ CSV exported successfully ({file_size} bytes)", force=True)
            return True
            
        except Exception as e:
            self.log(f"❌ CSV export failed: {str(e)}", force=True)
            raise
    
    def run_excel_processing(self):
        """Step 2: Process CSV and create Excel timesheet."""
        self.log("🔄 Step 2: Processing CSV and creating Excel timesheet...")
        
        try:
            parser = RedmineCSVParser(csv_filename=self.csv_filename, verbose=self.verbose)
            parsed_data = parser.run_analysis()
            
            if not parsed_data:
                raise ValueError("No data was parsed from CSV file")
            
            self.log(f"✅ Excel processing completed", force=True)
            return parsed_data
            
        except Exception as e:
            self.log(f"❌ Excel processing failed: {str(e)}", force=True)
            raise
    
    def cleanup_csv(self):
        """Step 3: Delete the temporary CSV file."""
        self.log("🔄 Step 3: Cleaning up temporary CSV file...")
        
        try:
            if os.path.exists(self.csv_path):
                os.remove(self.csv_path)
                self.log("✅ Temporary CSV file deleted", force=True)
            else:
                self.log("ℹ️  No CSV file to clean up", force=True)
                
        except OSError as e:
            self.log(f"⚠️ Warning: Could not delete CSV file: {e}", force=True)
            # Don't raise exception for cleanup failure
    
    def run_complete_automation(self):
        """Run the complete automation workflow."""
        start_time = datetime.now()
        
        try:
            self.log("🚀 Starting complete Redmine timesheet automation...", force=True)
            self.log(f"📅 Started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}", force=True)
            
            # Step 1: Export CSV from Redmine
            self.run_redmine_export()
            
            # Step 2: Process CSV and create Excel
            parsed_data = self.run_excel_processing()
            
            # Step 3: Clean up CSV file
            self.cleanup_csv()
            
            # Success summary
            end_time = datetime.now()
            duration = end_time - start_time
            
            self.log("\n" + "="*60, force=True)
            self.log("🎉 AUTOMATION COMPLETED SUCCESSFULLY!", force=True)
            self.log("="*60, force=True)
            self.log(f"📊 Processed {len(parsed_data)} time entries", force=True)
            self.log(f"⏱️  Total duration: {duration.total_seconds():.1f} seconds", force=True)
            self.log(f"✅ Excel timesheet ready for submission!", force=True)
            
            return True
            
        except Exception as e:
            end_time = datetime.now()
            duration = end_time - start_time
            
            self.log("\n" + "="*60, force=True)
            self.log("❌ AUTOMATION FAILED", force=True)
            self.log("="*60, force=True)
            self.log(f"💥 Error: {str(e)}", force=True)
            self.log(f"⏱️  Duration before failure: {duration.total_seconds():.1f} seconds", force=True)
            
            # Attempt cleanup even on failure
            try:
                self.cleanup_csv()
            except:
                pass
                
            raise


def main():
    """Main function to run the complete automation."""
    # Check for verbose flag
    verbose = '--verbose' in sys.argv or '-v' in sys.argv
    
    try:
        automation = CompleteTimesheetAutomation(verbose=verbose)
        automation.run_complete_automation()
        
        return 0
        
    except KeyboardInterrupt:
        print("\n⚠️  Automation interrupted by user")
        return 1
        
    except Exception as e:
        if not verbose:
            print(f"❌ Automation failed: {str(e)}")
            print("💡 Run with --verbose flag for detailed error information")
        return 1


if __name__ == '__main__':
    exit(main())