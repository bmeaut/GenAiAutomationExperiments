#!/usr/bin/env python3
"""
Test Google Sheets API with Public Sheet
No API key needed for public sheets!
"""

import pandas as pd
import requests
from datetime import datetime

def test_public_google_sheet():
    """Test reading from a public Google Sheet without API key"""
    try:
        print("🧪 Testing Google Sheets integration with public sheet...")
        
        # Google's public example sheet
        spreadsheet_id = "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
        range_name = "Class Data!A:F"  # This sheet has student data
        
        # Build URL for CSV export (no API key needed for public sheets)
        csv_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid=0"
        
        print(f"📊 Reading from public sheet: {spreadsheet_id}")
        
        # Read the CSV data
        response = requests.get(csv_url)
        response.raise_for_status()
        
        # Save to temporary file and read with pandas
        with open('temp_sheet_data.csv', 'w', encoding='utf-8') as f:
            f.write(response.text)
        
        # Read with pandas
        df = pd.read_csv('temp_sheet_data.csv')
        
        print(f"✅ Successfully read {len(df)} rows from Google Sheets")
        print("\n📋 Data preview:")
        print(df.head())
        
        # Clean up
        import os
        os.remove('temp_sheet_data.csv')
        
        return df
        
    except Exception as e:
        print(f"❌ Error reading Google Sheet: {e}")
        return pd.DataFrame()

def generate_report_from_sheet_data(data: pd.DataFrame):
    """Generate a simple report from the sheet data"""
    try:
        from pdf_generator import PDFGenerator
        
        print("\n📄 Generating PDF report from Google Sheets data...")
        
        pdf = PDFGenerator(title="Google Sheets Report", author="Simple Automation")
        
        # Add title
        pdf.add_title("Google Sheets Data Report")
        pdf.add_subtitle(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Add summary
        pdf.add_subtitle("Data Summary")
        pdf.add_paragraph(f"Total records: {len(data)}")
        pdf.add_paragraph(f"Columns: {', '.join(data.columns)}")
        
        # Add data table (first 10 rows)
        if len(data) > 0:
            pdf.add_subtitle("Data Sample")
            
            display_data = data.head(10)
            table_data = []
            headers = list(display_data.columns)
            
            for _, row in display_data.iterrows():
                table_data.append([str(row[col]) for col in headers])
            
            pdf.add_table(table_data, headers=headers, table_style='professional')
        
        # Generate PDF
        output_path = "outputs/pdfs/google_sheets_report.pdf"
        success = pdf.generate_pdf(output_path)
        
        if success:
            print(f"✅ PDF report generated: {output_path}")
            return True
        else:
            print("❌ Failed to generate PDF")
            return False
            
    except Exception as e:
        print(f"❌ Error generating report: {e}")
        return False

def test_with_your_own_sheet():
    """Instructions for testing with your own sheet"""
    print("\n🔗 To test with your own Google Sheet:")
    print("1. Create a Google Sheet: https://sheets.google.com/")
    print("2. Add some data (Name, Email, Department, etc.)")
    print("3. Click 'Share' → 'Anyone with the link' → 'Viewer'")
    print("4. Copy the sheet ID from the URL")
    print("5. Update the spreadsheet_id in this script")
    print("\n📝 Or use this function:")
    print("   read_your_sheet('YOUR_SHEET_ID_HERE')")

def read_your_sheet(spreadsheet_id: str, sheet_name: str = "Sheet1"):
    """Read data from your own public Google Sheet"""
    try:
        # For public sheets, we can use CSV export
        csv_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv"
        
        response = requests.get(csv_url)
        response.raise_for_status()
        
        # Save and read with pandas
        with open('your_sheet_data.csv', 'w', encoding='utf-8') as f:
            f.write(response.text)
        
        df = pd.read_csv('your_sheet_data.csv')
        
        print(f"✅ Read {len(df)} rows from your Google Sheet")
        print(df.head())
        
        # Clean up
        import os
        os.remove('your_sheet_data.csv')
        
        return df
        
    except Exception as e:
        print(f"❌ Error reading your sheet: {e}")
        print("💡 Make sure your sheet is public (shared with 'anyone with the link')")
        return pd.DataFrame()

def main():
    """Main test function"""
    print("🚀 Google Sheets Integration - Public Sheet Test")
    print("=" * 60)
    
    # Test with public sheet
    data = test_public_google_sheet()
    
    if not data.empty:
        # Generate report
        generate_report_from_sheet_data(data)
        
        print("\n🎉 Success! Google Sheets integration is working!")
        print("\n📊 Your data has been converted to a PDF report")
    else:
        print("\n❌ Test failed")
    
    # Show instructions for own sheet
    test_with_your_own_sheet()
    
    print("\n" + "=" * 60)
    print("🏁 Test completed!")

if __name__ == "__main__":
    main()