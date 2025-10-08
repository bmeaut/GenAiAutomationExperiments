#!/usr/bin/env python3
"""
Simple Office Automation Test (Windows-friendly)
No emoji characters for better console compatibility
"""

import sys
import os
from pathlib import Path

def test_basic_functionality():
    """Test basic office automation functionality"""
    print("Testing Office Automation - Basic Test Suite")
    print("=" * 50)
    
    # Test basic imports
    try:
        import json
        import csv
        import datetime
        import smtplib
        import imaplib
        print("[OK] Built-in libraries: Available")
    except ImportError as e:
        print(f"[ERROR] Built-in libraries: {e}")
        return False
    
    # Test optional packages
    packages = {
        'pandas': 'Data processing',
        'yaml': 'Configuration files',
        'openpyxl': 'Excel files',
        'reportlab': 'PDF generation',
        'PyPDF2': 'PDF manipulation',
        'win32com.client': 'Office COM automation',
        'google.oauth2.credentials': 'Google APIs'
    }
    
    available_packages = []
    missing_packages = []
    
    for package, description in packages.items():
        try:
            __import__(package)
            available_packages.append(f"[OK] {package}: {description}")
        except ImportError:
            missing_packages.append(f"[MISSING] {package}: {description}")
    
    print("\nAvailable packages:")
    for pkg in available_packages:
        print(f"  {pkg}")
    
    if missing_packages:
        print("\nMissing packages:")
        for pkg in missing_packages:
            print(f"  {pkg}")
    
    # Test CSV processing
    print("\nTesting CSV processing...")
    test_data = [
        ['Name', 'Email', 'Department'],
        ['John Doe', 'john@example.com', 'IT'],
        ['Jane Smith', 'jane@example.com', 'HR']
    ]
    
    try:
        import csv
        with open('test_output.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows(test_data)
        
        with open('test_output.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            data = list(reader)
        
        print(f"[OK] CSV processing: {len(data)} records processed")
        
        # Clean up
        os.remove('test_output.csv')
        
    except Exception as e:
        print(f"[ERROR] CSV processing: {e}")
    
    # Test template processing
    print("\nTesting template processing...")
    try:
        template = "Hello {{Name}}, welcome to {{Department}}!"
        for record in data:
            result = template
            for key, value in record.items():
                result = result.replace(f"{{{{{key}}}}}", value)
            print(f"  Template result: {result}")
        print("[OK] Template processing: Working")
    except Exception as e:
        print(f"[ERROR] Template processing: {e}")
    
    return True

def test_main_pipeline():
    """Test the main pipeline script"""
    print("\nTesting main pipeline...")
    
    # Change to Work2 directory
    work2_dir = Path(__file__).parent
    os.chdir(work2_dir)
    
    # Test if settings.yaml exists
    if Path('settings.yaml').exists():
        print("[OK] Configuration file: settings.yaml found")
    else:
        print("[WARNING] Configuration file: settings.yaml not found")
    
    # Test PDF generation
    try:
        from scripts.python.pdf_generator import generate_sample_report
        
        # Create outputs directory
        output_dir = Path("outputs/pdfs")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        pdf_path = "outputs/pdfs/test_report_simple.pdf"
        success = generate_sample_report(pdf_path)
        
        if success and Path(pdf_path).exists():
            print(f"[OK] PDF generation: {pdf_path}")
            print(f"  File size: {Path(pdf_path).stat().st_size} bytes")
        else:
            print("[ERROR] PDF generation: Failed")
    
    except Exception as e:
        print(f"[ERROR] PDF generation: {e}")

def main():
    """Run all tests"""
    import datetime
    
    print("Office Automation - Windows Compatible Test")
    print("Date:", datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print()
    
    # Run tests
    success = test_basic_functionality()
    test_main_pipeline()
    
    print("\n" + "=" * 50)
    print("Test completed!")
    
    if success:
        print("\nNext steps:")
        print("1. Configure Google API credentials (optional)")
        print("2. Configure email settings in settings.yaml (optional)")
        print("3. Import VBA macros into Excel and Word")
        print("4. Test with real data files")
    
    return success

if __name__ == "__main__":
    main()