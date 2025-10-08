#!/usr/bin/env python3
"""
Simple Test Script for Office Automation
Tests core functionality without requiring all dependencies
"""

import sys
import os
from pathlib import Path

def test_basic_imports():
    """Test basic Python imports"""
    print("🧪 Testing basic imports...")
    
    try:
        import json
        import csv
        import datetime
        import smtplib  # Built-in email library
        import imaplib  # Built-in email library
        print("✅ Built-in libraries: OK")
    except ImportError as e:
        print(f"❌ Built-in libraries failed: {e}")
        return False
    
    return True

def test_optional_imports():
    """Test optional imports"""
    print("🧪 Testing optional imports...")
    
    # Test pandas
    try:
        import pandas as pd
        print("✅ Pandas: OK")
    except ImportError:
        print("⚠️ Pandas: Not available (install with: pip install pandas)")
    
    # Test python-docx
    try:
        from docx import Document
        print("✅ python-docx: OK")
    except ImportError:
        print("⚠️ python-docx: Not available (install with: pip install python-docx)")
    
    # Test openpyxl
    try:
        import openpyxl
        print("✅ openpyxl: OK")
    except ImportError:
        print("⚠️ openpyxl: Not available (install with: pip install openpyxl)")
    
    # Test PyYAML
    try:
        import yaml
        print("✅ PyYAML: OK")
    except ImportError:
        print("⚠️ PyYAML: Not available (install with: pip install pyyaml)")
    
    # Test ReportLab
    try:
        from reportlab.pdfgen import canvas
        print("✅ ReportLab: OK")
    except ImportError:
        print("⚠️ ReportLab: Not available (install with: pip install reportlab)")
    
    # Test PyPDF2
    try:
        import PyPDF2
        print("✅ PyPDF2: OK")
    except ImportError:
        print("⚠️ PyPDF2: Not available (install with: pip install PyPDF2)")

def test_windows_com():
    """Test Windows COM objects (Excel/Word automation)"""
    print("🧪 Testing Windows COM objects...")
    
    try:
        import win32com.client
        print("✅ pywin32: OK")
        
        # Test if we can create COM objects (without actually opening applications)
        try:
            # Just test if the COM classes are available
            import pythoncom
            pythoncom.CoInitialize()
            print("✅ COM initialization: OK")
            pythoncom.CoUninitialize()
        except Exception as e:
            print(f"⚠️ COM objects: {e}")
            
    except ImportError:
        print("⚠️ pywin32: Not available (install with: pip install pywin32)")

def test_google_apis():
    """Test Google API imports"""
    print("🧪 Testing Google API imports...")
    
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        print("✅ Google API Client: OK")
    except ImportError:
        print("⚠️ Google API Client: Not available (install with: pip install google-api-python-client google-auth-oauthlib)")

def create_test_files():
    """Create test configuration files"""
    print("🧪 Creating test configuration files...")
    
    # Create test settings
    test_settings = {
        'google': {
            'enabled': False,
            'credentials_path': 'credentials.json',
            'token_path': 'google_token.json'
        },
        'email': {
            'enabled': False,
            'smtp_server': 'smtp.gmail.com',
            'smtp_port': 587,
            'username': 'your-email@gmail.com',
            'password': 'your-app-password',
            'use_tls': True
        },
        'pipeline': {
            'convert_to_pdf': True,
            'auto_email': False
        }
    }
    
    try:
        import yaml
        with open('test_settings.yaml', 'w') as f:
            yaml.dump(test_settings, f, default_flow_style=False)
        print("✅ Created test_settings.yaml")
    except ImportError:
        # Fallback to JSON
        import json
        with open('test_settings.json', 'w') as f:
            json.dump(test_settings, f, indent=2)
        print("✅ Created test_settings.json (YAML not available)")
    
    # Create test data
    test_data = [
        ['Name', 'Email', 'Department'],
        ['John Doe', 'john@example.com', 'IT'],
        ['Jane Smith', 'jane@example.com', 'HR'],
        ['Bob Johnson', 'bob@example.com', 'Finance']
    ]
    
    import csv
    with open('test_data.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(test_data)
    print("✅ Created test_data.csv")

def test_basic_functionality():
    """Test basic office automation functionality"""
    print("🧪 Testing basic functionality...")
    
    try:
        # Test CSV reading
        import csv
        with open('test_data.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            data = list(reader)
        print(f"✅ CSV reading: {len(data)} records")
        
        # Test simple template replacement
        template = "Hello {{Name}}, welcome to {{Department}}!"
        for record in data:
            result = template
            for key, value in record.items():
                result = result.replace(f"{{{{{key}}}}}", value)
            print(f"  📝 {result}")
        
        print("✅ Basic template processing: OK")
        
    except Exception as e:
        print(f"❌ Basic functionality test failed: {e}")

def main():
    """Run all tests"""
    print("🚀 Office Automation - Basic Test Suite")
    print("=" * 50)
    
    # Change to script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    # Run tests
    test_basic_imports()
    print()
    test_optional_imports()
    print()
    test_windows_com()
    print()
    test_google_apis()
    print()
    create_test_files()
    print()
    test_basic_functionality()
    
    print("\n" + "=" * 50)
    print("🏁 Test suite completed!")
    print("\n📋 Next steps:")
    print("1. Install missing packages using: pip install -r requirements_minimal.txt")
    print("2. Configure Google API credentials if needed")
    print("3. Test individual modules: python scripts/python/main_pipeline.py --pipeline test")
    print("4. Set up VBA macros in Excel and Word")

if __name__ == "__main__":
    main()