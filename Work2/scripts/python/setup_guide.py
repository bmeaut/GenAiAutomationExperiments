#!/usr/bin/env python3
"""
Setup and Configuration Guide for Office Automation
Step-by-step instructions for getting each integration working
"""

import os
import sys
from pathlib import Path

def check_google_setup():
    """Check Google API setup status"""
    print("=" * 60)
    print("GOOGLE APIS INTEGRATION SETUP")
    print("=" * 60)
    
    credentials_file = Path("credentials.json")
    token_file = Path("google_token.json")
    
    print("\n1. GOOGLE CLOUD CONSOLE SETUP:")
    print("   - Go to: https://console.cloud.google.com/")
    print("   - Create project or select existing")
    print("   - Enable APIs: Sheets, Docs, Drive, Gmail")
    print("   - Create OAuth 2.0 credentials (Desktop App)")
    print("   - Download credentials.json")
    
    if credentials_file.exists():
        print("   ✅ credentials.json found")
    else:
        print("   ❌ credentials.json NOT FOUND")
        print("      → Download from Google Cloud Console")
    
    print("\n2. AUTHENTICATION:")
    if token_file.exists():
        print("   ✅ google_token.json found (already authenticated)")
    else:
        print("   ❌ Not authenticated yet")
        print("      → Run: python setup_guide.py --auth-google")
    
    print("\n3. TEST GOOGLE INTEGRATION:")
    print("   → Run: python setup_guide.py --test-google")

def check_email_setup():
    """Check email setup status"""
    print("\n" + "=" * 60)
    print("EMAIL INTEGRATION SETUP")
    print("=" * 60)
    
    print("\n1. GMAIL APP PASSWORD SETUP:")
    print("   - Enable 2-Factor Authentication on Google Account")
    print("   - Go to: Google Account → Security → App passwords")
    print("   - Generate app password for 'Mail'")
    print("   - Copy 16-character password")
    
    print("\n2. UPDATE CONFIGURATION:")
    print("   - Edit settings.yaml")
    print("   - Set email.enabled: true")
    print("   - Set email.username: your-email@gmail.com")
    print("   - Set email.password: your-app-password")
    
    print("\n3. TEST EMAIL:")
    print("   → Run: python setup_guide.py --test-email")

def check_office_setup():
    """Check Office COM setup status"""
    print("\n" + "=" * 60)
    print("OFFICE COM INTEGRATION SETUP")
    print("=" * 60)
    
    print("\n1. REQUIREMENTS CHECK:")
    try:
        import win32com.client
        print("   ✅ pywin32 installed")
    except ImportError:
        print("   ❌ pywin32 not installed")
        print("      → Run: pip install pywin32")
        return
    
    print("   ✅ Windows OS (required for COM)")
    print("   ✅ Microsoft Office (assumed installed)")
    
    print("\n2. VBA MACROS SETUP:")
    print("   EXCEL:")
    print("   - Open Excel → Developer → Visual Basic")
    print("   - Insert → Module")
    print("   - File → Import → scripts\\vba\\excel_google_sync.bas")
    print("   - Run SetupGoogleSheetsIntegration macro")
    
    print("   WORD:")
    print("   - Open Word → Developer → Visual Basic")
    print("   - Insert → Module") 
    print("   - File → Import → scripts\\vba\\word_automation.bas")
    print("   - Run SetupGoogleDocsIntegration macro")
    
    print("\n3. TEST OFFICE INTEGRATION:")
    print("   → Run: python setup_guide.py --test-office")

def authenticate_google():
    """Authenticate with Google APIs"""
    print("Authenticating with Google APIs...")
    
    if not Path("credentials.json").exists():
        print("❌ credentials.json not found!")
        print("Please download from Google Cloud Console first.")
        return False
    
    try:
        from scripts.python.google_integration import GoogleIntegration
        
        gi = GoogleIntegration("credentials.json", "google_token.json")
        success = gi.authenticate()
        
        if success:
            print("✅ Google authentication successful!")
            print("Token saved to google_token.json")
            return True
        else:
            print("❌ Google authentication failed!")
            return False
            
    except Exception as e:
        print(f"❌ Error during authentication: {e}")
        return False

def test_google():
    """Test Google integration"""
    print("Testing Google integration...")
    
    if not Path("google_token.json").exists():
        print("❌ Not authenticated. Run --auth-google first.")
        return False
    
    try:
        from scripts.python.google_integration import GoogleIntegration
        
        gi = GoogleIntegration("credentials.json", "google_token.json")
        
        # Test creating a new spreadsheet
        print("Creating test spreadsheet...")
        spreadsheet_id = gi.create_spreadsheet("Test Automation Sheet")
        
        if spreadsheet_id:
            print(f"✅ Spreadsheet created: {spreadsheet_id}")
            
            # Test writing data
            test_data = [
                ["Name", "Email", "Department"],
                ["John Doe", "john@test.com", "IT"],
                ["Jane Smith", "jane@test.com", "HR"]
            ]
            
            success = gi.write_sheet_data(spreadsheet_id, "Sheet1", test_data)
            if success:
                print("✅ Data written to spreadsheet")
            else:
                print("❌ Failed to write data")
            
            print(f"View spreadsheet: https://docs.google.com/spreadsheets/d/{spreadsheet_id}")
            return True
        else:
            print("❌ Failed to create spreadsheet")
            return False
            
    except Exception as e:
        print(f"❌ Error testing Google integration: {e}")
        return False

def test_email():
    """Test email integration"""
    print("Testing email integration...")
    
    try:
        import yaml
        
        # Load configuration
        with open("settings.yaml", "r") as f:
            config = yaml.safe_load(f)
        
        email_config = config.get("email", {})
        
        if not email_config.get("enabled", False):
            print("❌ Email not enabled in settings.yaml")
            return False
        
        if not email_config.get("username") or not email_config.get("password"):
            print("❌ Email credentials not configured in settings.yaml")
            return False
        
        from scripts.python.email_automation import EmailSender, EmailConfig
        
        # Create email configuration
        email_cfg = EmailConfig(
            smtp_server=email_config["smtp_server"],
            smtp_port=email_config["smtp_port"],
            username=email_config["username"],
            password=email_config["password"],
            use_tls=email_config.get("use_tls", True)
        )
        
        # Test sending email
        with EmailSender(email_cfg) as sender:
            success = sender.send_simple_email(
                to_email=email_config["username"],  # Send to self
                subject="Office Automation Test",
                body="This is a test email from the Office Automation system."
            )
        
        if success:
            print("✅ Test email sent successfully!")
            return True
        else:
            print("❌ Failed to send test email")
            return False
            
    except Exception as e:
        print(f"❌ Error testing email: {e}")
        return False

def test_office():
    """Test Office COM integration"""
    print("Testing Office COM integration...")
    
    try:
        from scripts.python.office_integration import ExcelIntegration, WordIntegration
        
        # Test Excel
        print("Testing Excel COM...")
        with ExcelIntegration(visible=False) as excel:
            excel.create_new_workbook()
            print("✅ Excel COM working")
        
        # Test Word  
        print("Testing Word COM...")
        with WordIntegration(visible=False) as word:
            word.create_new_document()
            print("✅ Word COM working")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing Office COM: {e}")
        return False

def create_sample_workflow():
    """Create a complete sample workflow"""
    print("\n" + "=" * 60)
    print("CREATING SAMPLE WORKFLOW")
    print("=" * 60)
    
    # Create sample data file
    import csv
    
    sample_data = [
        ["Name", "Email", "Department", "Salary"],
        ["Alice Johnson", "alice@company.com", "Engineering", "75000"],
        ["Bob Wilson", "bob@company.com", "Marketing", "65000"],
        ["Carol Davis", "carol@company.com", "Finance", "70000"]
    ]
    
    os.makedirs("sample_data", exist_ok=True)
    
    with open("sample_data/employees.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(sample_data)
    
    print("✅ Created sample_data/employees.csv")
    
    # Create Word template
    template_content = """
Employee Information Report

Name: {{Name}}
Email: {{Email}}
Department: {{Department}}
Annual Salary: ${{Salary}}

This report was generated automatically by the Office Automation system.

Generated on: {{Date}}
"""
    
    os.makedirs("sample_templates", exist_ok=True)
    
    with open("sample_templates/employee_template.txt", "w", encoding="utf-8") as f:
        f.write(template_content)
    
    print("✅ Created sample_templates/employee_template.txt")
    
    print("\nSample workflow created! You can now:")
    print("1. Run: python scripts\\python\\main_pipeline.py --pipeline excel-word")
    print("   --excel-file sample_data\\employees.csv")
    print("   --word-template sample_templates\\employee_template.txt")

def main():
    """Main setup guide"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Office Automation Setup Guide")
    parser.add_argument("--auth-google", action="store_true", help="Authenticate with Google APIs")
    parser.add_argument("--test-google", action="store_true", help="Test Google integration")
    parser.add_argument("--test-email", action="store_true", help="Test email integration")
    parser.add_argument("--test-office", action="store_true", help="Test Office COM integration")
    parser.add_argument("--create-sample", action="store_true", help="Create sample workflow")
    
    args = parser.parse_args()
    
    # Change to script directory
    os.chdir(Path(__file__).parent)
    
    if args.auth_google:
        authenticate_google()
    elif args.test_google:
        test_google()
    elif args.test_email:
        test_email()
    elif args.test_office:
        test_office()
    elif args.create_sample:
        create_sample_workflow()
    else:
        # Show full setup guide
        print("OFFICE AUTOMATION - SETUP GUIDE")
        print("Current directory:", os.getcwd())
        print()
        
        check_google_setup()
        check_email_setup()
        check_office_setup()
        
        print("\n" + "=" * 60)
        print("QUICK START COMMANDS:")
        print("=" * 60)
        print("python setup_guide.py --auth-google     # Authenticate Google APIs")
        print("python setup_guide.py --test-google     # Test Google integration")
        print("python setup_guide.py --test-email      # Test email sending")
        print("python setup_guide.py --test-office     # Test Excel/Word COM")
        print("python setup_guide.py --create-sample   # Create sample workflow")

if __name__ == "__main__":
    main()