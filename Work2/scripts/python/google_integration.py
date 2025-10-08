#!/usr/bin/env python3
"""
Google APIs Integration Module
Handles Google Sheets, Docs, Drive, and Gmail operations for office automation
"""

import os
import json
import pandas as pd
import pickle
import base64
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
import time

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

import logging
logger = logging.getLogger(__name__)


class GoogleIntegration:
    """
    Google APIs integration class for office automation
    Handles Sheets, Docs, Drive, and Gmail operations
    """
    
    def __init__(self, credentials_file: str, scopes: List[str]):
        self.credentials_file = credentials_file
        self.scopes = scopes
        self.creds = None
        
        # Service objects
        self.sheets_service = None
        self.docs_service = None
        self.drive_service = None
        self.gmail_service = None
        
        self.authenticate()
    
    def authenticate(self):
        """Authenticate with Google APIs using OAuth2"""
        token_file = 'config/token.pickle'
        
        # Load existing token
        if os.path.exists(token_file):
            try:
                with open(token_file, 'rb') as token:
                    self.creds = pickle.load(token)
                logger.info("Loaded existing Google API credentials")
            except Exception as e:
                logger.warning(f"Error loading credentials: {e}")
                self.creds = None
        
        # If no valid credentials, authenticate
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                try:
                    self.creds.refresh(Request())
                    logger.info("Refreshed Google API credentials")
                except Exception as e:
                    logger.error(f"Error refreshing credentials: {e}")
                    self.creds = None
            
            if not self.creds:
                if not os.path.exists(self.credentials_file):
                    raise FileNotFoundError(f"Credentials file not found: {self.credentials_file}")
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, self.scopes)
                self.creds = flow.run_local_server(port=0)
                logger.info("Completed Google API authentication flow")
            
            # Save credentials for next run
            try:
                os.makedirs(os.path.dirname(token_file), exist_ok=True)
                with open(token_file, 'wb') as token:
                    pickle.dump(self.creds, token)
                logger.info("Saved Google API credentials")
            except Exception as e:
                logger.warning(f"Could not save credentials: {e}")
        
        # Build services
        try:
            self.sheets_service = build('sheets', 'v4', credentials=self.creds)
            self.docs_service = build('docs', 'v1', credentials=self.creds)
            self.drive_service = build('drive', 'v3', credentials=self.creds)
            self.gmail_service = build('gmail', 'v1', credentials=self.creds)
            logger.info("✅ Google API services initialized successfully")
        except Exception as e:
            logger.error(f"❌ Error building Google API services: {e}")
            raise
    
    def read_sheet_data(self, spreadsheet_id: str, range_name: str = 'A:Z') -> pd.DataFrame:
        """Read data from Google Sheets and return as pandas DataFrame"""
        try:
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_name
            ).execute()
            
            values = result.get('values', [])
            
            if not values:
                logger.warning("No data found in Google Sheet")
                return pd.DataFrame()
            
            # Convert to DataFrame
            if len(values) > 1:
                df = pd.DataFrame(values[1:], columns=values[0])
            else:
                df = pd.DataFrame(columns=values[0] if values else [])
            
            logger.info(f"✅ Loaded {len(df)} rows from Google Sheets")
            return df
            
        except HttpError as error:
            logger.error(f"❌ Google Sheets API error: {error}")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"❌ Error reading sheet data: {e}")
            return pd.DataFrame()
    
    def append_sheet_data(self, spreadsheet_id: str, range_name: str, values: List[List]) -> bool:
        """Append data to Google Sheets"""
        try:
            body = {'values': values}
            result = self.sheets_service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption='USER_ENTERED',
                body=body
            ).execute()
            
            logger.info(f"✅ Appended {len(values)} rows to Google Sheets")
            return True
            
        except HttpError as error:
            logger.error(f"❌ Error appending to sheet: {error}")
            return False
        except Exception as e:
            logger.error(f"❌ Error appending sheet data: {e}")
            return False
    
    def update_sheet_data(self, spreadsheet_id: str, range_name: str, values: List[List]) -> bool:
        """Update specific range in Google Sheets"""
        try:
            body = {'values': values}
            result = self.sheets_service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption='USER_ENTERED',
                body=body
            ).execute()
            
            logger.info(f"✅ Updated {len(values)} rows in Google Sheets")
            return True
            
        except HttpError as error:
            logger.error(f"❌ Error updating sheet: {error}")
            return False
        except Exception as e:
            logger.error(f"❌ Error updating sheet data: {e}")
            return False
    
    def create_document_from_template(self, template_id: str, title: str) -> Optional[str]:
        """Create a new Google Doc from template"""
        try:
            # Copy the template
            copy_body = {'name': title}
            copied_file = self.drive_service.files().copy(
                fileId=template_id,
                body=copy_body
            ).execute()
            
            new_doc_id = copied_file.get('id')
            logger.info(f"✅ Created Google Doc: {title} (ID: {new_doc_id})")
            return new_doc_id
            
        except HttpError as error:
            logger.error(f"❌ Error creating document: {error}")
            return None
        except Exception as e:
            logger.error(f"❌ Error creating document from template: {e}")
            return None
    
    def replace_text_in_document(self, document_id: str, replacements: Dict[str, str]) -> bool:
        """Replace placeholders in Google Docs"""
        try:
            requests = []
            
            for placeholder, replacement in replacements.items():
                # Support both {{placeholder}} and {placeholder} formats
                for pattern in [f'{{{{{placeholder}}}}}', f'{{{placeholder}}}']:
                    requests.append({
                        'replaceAllText': {
                            'containsText': {
                                'text': pattern,
                                'matchCase': True
                            },
                            'replaceText': str(replacement)
                        }
                    })
            
            if requests:
                result = self.docs_service.documents().batchUpdate(
                    documentId=document_id,
                    body={'requests': requests}
                ).execute()
                
                logger.info(f"✅ Replaced {len(replacements)} placeholders in document")
                return True
            
            return False
            
        except HttpError as error:
            logger.error(f"❌ Error replacing text: {error}")
            return False
        except Exception as e:
            logger.error(f"❌ Error replacing text in document: {e}")
            return False
    
    def export_document_as_pdf(self, document_id: str, filename: str, output_dir: str = "output/generated_pdfs") -> Optional[str]:
        """Export Google Doc as PDF"""
        try:
            # Export as PDF
            pdf_content = self.drive_service.files().export(
                fileId=document_id,
                mimeType='application/pdf'
            ).execute()
            
            # Save to file
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, f"{filename}.pdf")
            
            with open(output_path, 'wb') as f:
                f.write(pdf_content)
            
            logger.info(f"✅ Exported PDF: {filename}.pdf")
            return output_path
            
        except HttpError as error:
            logger.error(f"❌ Error exporting PDF: {error}")
            return None
        except Exception as e:
            logger.error(f"❌ Error exporting document as PDF: {e}")
            return None
    
    def send_email_with_attachment(self, to_email: str, subject: str, 
                                 body: str, attachment_path: Optional[str] = None, 
                                 body_type: str = 'html') -> bool:
        """Send email via Gmail API"""
        try:
            message = MIMEMultipart()
            message['to'] = to_email
            message['subject'] = subject
            
            # Add body
            message.attach(MIMEText(body, body_type))
            
            # Add attachment if provided
            if attachment_path and os.path.exists(attachment_path):
                with open(attachment_path, 'rb') as f:
                    attachment_data = f.read()
                
                attachment = MIMEApplication(attachment_data)
                attachment.add_header(
                    'Content-Disposition', 
                    'attachment', 
                    filename=os.path.basename(attachment_path)
                )
                message.attach(attachment)
            
            # Encode message
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            
            # Send email
            result = self.gmail_service.users().messages().send(
                userId='me',
                body={'raw': raw_message}
            ).execute()
            
            logger.info(f"✅ Email sent to {to_email}")
            return True
            
        except HttpError as error:
            logger.error(f"❌ Gmail API error: {error}")
            return False
        except Exception as e:
            logger.error(f"❌ Error sending email: {e}")
            return False
    
    def monitor_sheet_changes(self, spreadsheet_id: str, callback_func: Callable[[Dict[str, Any]], None], 
                            check_interval: int = 30, max_cycles: int = 1000):
        """
        Monitor Google Sheets for new rows (simplified polling approach)
        In production, consider using Google Apps Script triggers or Pub/Sub notifications
        """
        logger.info(f"🔍 Starting to monitor sheet {spreadsheet_id} for changes...")
        logger.info(f"Check interval: {check_interval}s, Max cycles: {max_cycles}")
        
        last_row_count = 0
        cycle_count = 0
        
        try:
            # Get initial row count
            initial_data = self.read_sheet_data(spreadsheet_id)
            last_row_count = len(initial_data)
            logger.info(f"Initial row count: {last_row_count}")
            
            while cycle_count < max_cycles:
                try:
                    current_data = self.read_sheet_data(spreadsheet_id)
                    current_row_count = len(current_data)
                    
                    if current_row_count > last_row_count:
                        new_rows = current_data.iloc[last_row_count:]
                        logger.info(f"📝 Detected {len(new_rows)} new rows")
                        
                        for index, row in new_rows.iterrows():
                            try:
                                callback_func(row.to_dict())
                            except Exception as e:
                                logger.error(f"❌ Error processing row {index}: {e}")
                        
                        last_row_count = current_row_count
                    
                    cycle_count += 1
                    
                    # Wait before next check
                    time.sleep(check_interval)
                    
                    if cycle_count % 10 == 0:
                        logger.info(f"Monitoring cycle {cycle_count}/{max_cycles} completed")
                    
                except KeyboardInterrupt:
                    logger.info("👋 Monitoring stopped by user")
                    break
                except Exception as e:
                    logger.error(f"❌ Monitoring error: {e}")
                    time.sleep(check_interval * 2)  # Wait longer on error
                    
        except Exception as e:
            logger.error(f"❌ Fatal monitoring error: {e}")
        
        logger.info("🏁 Sheet monitoring ended")
    
    def get_sheet_info(self, spreadsheet_id: str) -> Dict[str, Any]:
        """Get information about a Google Sheet"""
        try:
            sheet_metadata = self.sheets_service.spreadsheets().get(
                spreadsheetId=spreadsheet_id
            ).execute()
            
            info = {
                'title': sheet_metadata.get('properties', {}).get('title', 'Unknown'),
                'sheets': [],
                'url': f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
            }
            
            for sheet in sheet_metadata.get('sheets', []):
                sheet_properties = sheet.get('properties', {})
                info['sheets'].append({
                    'title': sheet_properties.get('title', 'Unknown'),
                    'sheet_id': sheet_properties.get('sheetId'),
                    'row_count': sheet_properties.get('gridProperties', {}).get('rowCount', 0),
                    'column_count': sheet_properties.get('gridProperties', {}).get('columnCount', 0)
                })
            
            logger.info(f"✅ Retrieved info for sheet: {info['title']}")
            return info
            
        except HttpError as error:
            logger.error(f"❌ Error getting sheet info: {error}")
            return {}
        except Exception as e:
            logger.error(f"❌ Error getting sheet information: {e}")
            return {}


def test_google_integration():
    """Test function for Google Integration"""
    import yaml
    
    # Load config
    config_path = "config/settings.yaml"
    if not os.path.exists(config_path):
        print("❌ Configuration file not found. Please create config/settings.yaml")
        return
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    google_config = config.get('google', {})
    credentials_file = google_config.get('credentials_file')
    
    if not credentials_file or not os.path.exists(credentials_file):
        print("❌ Google credentials file not found. Please set up Google API credentials.")
        return
    
    try:
        # Initialize Google Integration
        google_integration = GoogleIntegration(
            credentials_file=credentials_file,
            scopes=google_config.get('scopes', [])
        )
        
        # Test with sample sheet if provided
        sample_sheet_id = google_config.get('sample_sheet_id')
        if sample_sheet_id:
            print(f"📊 Testing with sample sheet: {sample_sheet_id}")
            
            # Get sheet info
            sheet_info = google_integration.get_sheet_info(sample_sheet_id)
            print(f"Sheet title: {sheet_info.get('title', 'Unknown')}")
            print(f"Sheets count: {len(sheet_info.get('sheets', []))}")
            
            # Read sample data
            data = google_integration.read_sheet_data(sample_sheet_id)
            print(f"Data shape: {data.shape}")
            if not data.empty:
                print("Sample data columns:", list(data.columns))
                print(data.head())
        else:
            print("⚠️ No sample sheet ID configured. Skipping data test.")
        
        print("✅ Google Integration test completed successfully!")
        
    except Exception as e:
        print(f"❌ Google Integration test failed: {e}")


if __name__ == "__main__":
    test_google_integration()