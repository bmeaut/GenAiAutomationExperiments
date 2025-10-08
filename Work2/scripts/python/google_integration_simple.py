#!/usr/bin/env python3
"""
Google APIs Integration Module - API Key Version
Simplified Google Sheets and Docs integration using API keys
"""

import os
import json
import pandas as pd
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime
import time

import logging
logger = logging.getLogger(__name__)


class GoogleSheetsAPI:
    """
    Simplified Google Sheets integration using API key
    Read/Write operations for Google Sheets
    """
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://sheets.googleapis.com/v4/spreadsheets"
    
    def read_sheet_data(self, spreadsheet_id: str, range_name: str = "Sheet1") -> pd.DataFrame:
        """Read data from Google Sheets and return as DataFrame"""
        try:
            url = f"{self.base_url}/{spreadsheet_id}/values/{range_name}"
            params = {
                'key': self.api_key,
                'majorDimension': 'ROWS'
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            if 'values' not in data:
                logger.warning("No data found in the sheet")
                return pd.DataFrame()
            
            values = data['values']
            
            if len(values) == 0:
                return pd.DataFrame()
            
            # First row as headers, rest as data
            headers = values[0]
            rows = values[1:] if len(values) > 1 else []
            
            # Pad rows to match header length
            padded_rows = []
            for row in rows:
                padded_row = row + [''] * (len(headers) - len(row))
                padded_rows.append(padded_row)
            
            df = pd.DataFrame(padded_rows, columns=headers)
            
            logger.info(f"✅ Read {len(df)} rows from Google Sheets")
            return df
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error reading from Google Sheets: {e}")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")
            return pd.DataFrame()
    
    def write_sheet_data(self, spreadsheet_id: str, data: pd.DataFrame, 
                        range_name: str = "Sheet1", include_headers: bool = True) -> bool:
        """
        Write DataFrame to Google Sheets
        Note: This requires a service account or OAuth for write permissions
        API key alone only allows read operations
        """
        logger.warning("⚠️ Writing to Google Sheets requires OAuth or Service Account authentication")
        logger.warning("⚠️ API key only supports read operations")
        return False
    
    def get_sheet_info(self, spreadsheet_id: str) -> Dict[str, Any]:
        """Get basic information about the spreadsheet"""
        try:
            url = f"{self.base_url}/{spreadsheet_id}"
            params = {
                'key': self.api_key,
                'fields': 'properties,sheets.properties'
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            info = {
                'title': data.get('properties', {}).get('title', 'Unknown'),
                'sheets': []
            }
            
            for sheet in data.get('sheets', []):
                sheet_info = {
                    'title': sheet.get('properties', {}).get('title', 'Unknown'),
                    'sheet_id': sheet.get('properties', {}).get('sheetId', 0),
                    'index': sheet.get('properties', {}).get('index', 0)
                }
                info['sheets'].append(sheet_info)
            
            logger.info(f"✅ Retrieved info for spreadsheet: {info['title']}")
            return info
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error getting sheet info: {e}")
            return {}
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")
            return {}


class GoogleDocsAPI:
    """
    Simplified Google Docs integration using API key
    Read operations for Google Docs
    """
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://docs.googleapis.com/v1/documents"
    
    def read_document_content(self, document_id: str) -> str:
        """Read text content from Google Docs"""
        try:
            url = f"{self.base_url}/{document_id}"
            params = {'key': self.api_key}
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            content = self._extract_text_from_document(data)
            
            logger.info(f"✅ Read document content ({len(content)} characters)")
            return content
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error reading Google Doc: {e}")
            return ""
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")
            return ""
    
    def _extract_text_from_document(self, doc_data: Dict) -> str:
        """Extract plain text from Google Docs API response"""
        content = ""
        
        try:
            body = doc_data.get('body', {})
            content_elements = body.get('content', [])
            
            for element in content_elements:
                if 'paragraph' in element:
                    paragraph = element['paragraph']
                    elements = paragraph.get('elements', [])
                    
                    for elem in elements:
                        if 'textRun' in elem:
                            text_run = elem['textRun']
                            text_content = text_run.get('content', '')
                            content += text_content
                        
        except Exception as e:
            logger.error(f"❌ Error extracting text: {e}")
        
        return content
    
    def get_document_info(self, document_id: str) -> Dict[str, Any]:
        """Get basic information about the document"""
        try:
            url = f"{self.base_url}/{document_id}"
            params = {
                'key': self.api_key,
                'fields': 'title,documentId,revisionId'
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            info = {
                'title': data.get('title', 'Unknown'),
                'document_id': data.get('documentId', ''),
                'revision_id': data.get('revisionId', '')
            }
            
            logger.info(f"✅ Retrieved info for document: {info['title']}")
            return info
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error getting document info: {e}")
            return {}


class SimpleGoogleIntegration:
    """
    Simplified Google integration using API key
    Combines Sheets and Docs functionality
    """
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.sheets = GoogleSheetsAPI(api_key)
        self.docs = GoogleDocsAPI(api_key)
    
    def test_connection(self) -> bool:
        """Test if the API key is working"""
        try:
            # Test with a public Google Sheet (Google's example sheet)
            test_spreadsheet_id = "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
            
            info = self.sheets.get_sheet_info(test_spreadsheet_id)
            
            if info and 'title' in info:
                logger.info(f"✅ API key working - accessed: {info['title']}")
                return True
            else:
                logger.error("❌ API key test failed")
                return False
                
        except Exception as e:
            logger.error(f"❌ API key test error: {e}")
            return False
    
    def read_sheet_data(self, spreadsheet_id: str, sheet_name: str = "Sheet1") -> pd.DataFrame:
        """Read data from Google Sheets"""
        return self.sheets.read_sheet_data(spreadsheet_id, sheet_name)
    
    def read_document_content(self, document_id: str) -> str:
        """Read content from Google Docs"""
        return self.docs.read_document_content(document_id)
    
    def get_sheet_info(self, spreadsheet_id: str) -> Dict[str, Any]:
        """Get spreadsheet information"""
        return self.sheets.get_sheet_info(spreadsheet_id)
    
    def get_document_info(self, document_id: str) -> Dict[str, Any]:
        """Get document information"""
        return self.docs.get_document_info(document_id)


def create_sample_data_and_test():
    """Create sample data and test the integration"""
    try:
        # Create sample data
        sample_data = pd.DataFrame({
            'Name': ['John Doe', 'Jane Smith', 'Bob Johnson', 'Alice Brown'],
            'Department': ['IT', 'HR', 'Finance', 'Marketing'],
            'Email': ['john@company.com', 'jane@company.com', 'bob@company.com', 'alice@company.com'],
            'Salary': [75000, 65000, 80000, 70000]
        })
        
        # Save sample data
        sample_data.to_csv('sample_employee_data.csv', index=False)
        print("✅ Created sample_employee_data.csv")
        
        # Test API key (you need to provide a real API key)
        api_key = "YOUR_API_KEY_HERE"  # Replace with real API key
        
        if api_key == "YOUR_API_KEY_HERE":
            print("⚠️ Please set a real Google API key to test the integration")
            print("📋 Steps to get API key:")
            print("1. Go to https://console.cloud.google.com/")
            print("2. Create/select project")
            print("3. Enable Google Sheets API and Google Docs API")
            print("4. Go to Credentials > Create Credentials > API Key")
            print("5. Copy the API key and update this script")
            return False
        
        # Test the integration
        google_api = SimpleGoogleIntegration(api_key)
        
        if google_api.test_connection():
            print("✅ Google API connection successful!")
            return True
        else:
            print("❌ Google API connection failed")
            return False
            
    except Exception as e:
        print(f"❌ Error in test: {e}")
        return False


def main():
    """Main function for testing"""
    print("🔧 Google APIs Integration - API Key Version")
    print("=" * 50)
    
    success = create_sample_data_and_test()
    
    if success:
        print("\n🎉 Setup successful!")
        print("You can now use the SimpleGoogleIntegration class with your API key")
    else:
        print("\n📋 Next steps:")
        print("1. Get a Google API key from Google Cloud Console")
        print("2. Enable Google Sheets API and Google Docs API")
        print("3. Update the API key in your code")
        print("4. Test with your own spreadsheets and documents")


if __name__ == "__main__":
    main()