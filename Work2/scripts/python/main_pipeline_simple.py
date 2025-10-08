#!/usr/bin/env python3
"""
Simple Pipeline Script - API Key Version
Simplified office automation using API keys instead of OAuth
"""

import os
import sys
import logging
import yaml
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import argparse

# Import our simplified modules
try:
    from google_integration_simple import SimpleGoogleIntegration
    from office_integration import ExcelIntegration, WordIntegration
    from pdf_generator import PDFGenerator, generate_sample_report
    from email_automation import EmailSender, EmailConfig, EmailTemplateManager
    from env_config import load_environment
except ImportError as e:
    print(f"[ERROR] Import error: {e}")
    print("Make sure all required modules are in the same directory")
    sys.exit(1)

# Configure logging without Unicode issues
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('automation_pipeline.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class SimpleAutomationPipeline:
    """Simplified automation pipeline using API keys"""
    
    def __init__(self, config_path: str = "settings.yaml"):
        # Load environment configuration first
        self.env_config = load_environment()
        
        # Keep YAML for backward compatibility
        self.config_path = config_path
        self.yaml_config = self.load_yaml_config()
        
        self.google_api = None
        self.email_sender = None
        
        self.setup_directories()
        self.initialize_services()
    
    def load_yaml_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file (backward compatibility)"""
        try:
            if not os.path.exists(self.config_path):
                print(f"[INFO] YAML config not found: {self.config_path} (using environment variables)")
                return {}
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            print(f"[OK] YAML configuration loaded from {self.config_path}")
            return config
            
        except Exception as e:
            print(f"[WARNING] Error loading YAML configuration: {e}")
            return {}
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Get configuration value from environment first, then YAML"""
        # Try environment first
        env_value = self.env_config.get(key)
        if env_value is not None:
            return env_value
        
        # Fall back to YAML
        keys = key.split('.')
        value = self.yaml_config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    def setup_directories(self):
        """Create necessary directories"""
        paths_config = self.env_config.get_paths_config()
        
        directories = [
            paths_config['output_dir'],
            f"{paths_config['output_dir']}/reports",
            f"{paths_config['output_dir']}/documents", 
            f"{paths_config['output_dir']}/pdfs",
            f"{paths_config['output_dir']}/data",
            paths_config['logs_dir'],
            "temp"
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
    
    def initialize_services(self):
        """Initialize external services"""
        try:
            # Initialize Google Integration with API key from environment
            google_config = self.env_config.get_google_config()
            if google_config['enabled']:
                api_key = google_config['api_key']
                self.google_api = SimpleGoogleIntegration(api_key)
                
                # Test the connection
                if self.google_api.test_connection():
                    print("[OK] Google API integration initialized")
                else:
                    print("[WARNING] Google API test failed")
                    self.google_api = None
            else:
                print("[WARNING] Google API key not configured")
            
            # Initialize Email from environment
            email_config = self.env_config.get_email_config()
            if email_config['enabled']:
                email_cfg = EmailConfig(
                    smtp_server=email_config['smtp_server'],
                    smtp_port=email_config['smtp_port'],
                    username=email_config['username'],
                    password=email_config['password'],
                    use_tls=True
                )
                self.email_sender = EmailSender(email_cfg)
                self.template_manager = EmailTemplateManager("templates/email")
                print("[OK] Email automation initialized")
            else:
                print("[WARNING] Email not configured")
            
        except Exception as e:
            print(f"[ERROR] Error initializing services: {e}")
    
    def run_google_sheets_to_pdf_pipeline(self, spreadsheet_id: str, 
                                        sheet_name: str = "Sheet1") -> bool:
        """Simple pipeline: Google Sheets -> PDF Report"""
        try:
            print("[INFO] Starting Google Sheets to PDF pipeline")
            
            if not self.google_api:
                print("[ERROR] Google API not available")
                return False
            
            # Step 1: Read data from Google Sheets
            print("[INFO] Reading data from Google Sheets...")
            data = self.google_api.read_sheet_data(spreadsheet_id, sheet_name)
            
            if data.empty:
                print("[ERROR] No data retrieved from Google Sheets")
                return False
            
            print(f"[OK] Retrieved {len(data)} rows from Google Sheets")
            
            # Step 2: Save data locally
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            data_file = f"outputs/data/sheet_data_{timestamp}.csv"
            data.to_csv(data_file, index=False)
            print(f"[OK] Data saved to: {data_file}")
            
            # Step 3: Generate PDF report
            print("[INFO] Generating PDF report...")
            pdf_path = f"outputs/pdfs/google_sheets_report_{timestamp}.pdf"
            
            success = self.generate_data_report(data, pdf_path)
            if not success:
                print("[ERROR] Failed to generate PDF report")
                return False
            
            print(f"[OK] PDF report generated: {pdf_path}")
            return True
            
        except Exception as e:
            print(f"[ERROR] Pipeline error: {e}")
            return False
    
    def run_csv_to_documents_pipeline(self, csv_file: str, template_file: str = None) -> bool:
        """Pipeline: CSV Data -> Word Documents -> PDF"""
        try:
            print("[INFO] Starting CSV to Documents pipeline")
            
            # Step 1: Read CSV data
            if not os.path.exists(csv_file):
                print(f"[ERROR] CSV file not found: {csv_file}")
                return False
            
            data = pd.read_csv(csv_file)
            print(f"[OK] Read {len(data)} rows from CSV")
            
            # Step 2: Generate documents for each row
            print("[INFO] Generating documents...")
            generated_docs = []
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            for index, row in data.iterrows():
                try:
                    # Create simple document content
                    content = self.create_document_content(row)
                    
                    # Generate output filename
                    name_col = 'Name' if 'Name' in data.columns else data.columns[0]
                    safe_name = str(row[name_col]).replace(' ', '_').replace('/', '_')
                    output_path = f"outputs/documents/document_{safe_name}_{timestamp}.txt"
                    
                    # Save document
                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    
                    generated_docs.append(output_path)
                    print(f"[OK] Generated: {os.path.basename(output_path)}")
                    
                except Exception as e:
                    print(f"[ERROR] Error processing row {index}: {e}")
                    continue
            
            print(f"[OK] Generated {len(generated_docs)} documents")
            return True
            
        except Exception as e:
            print(f"[ERROR] Pipeline error: {e}")
            return False
    
    def create_document_content(self, row_data: pd.Series) -> str:
        """Create document content from row data"""
        content = f"Generated Document\n"
        content += f"Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        content += "=" * 50 + "\n\n"
        
        for column, value in row_data.items():
            content += f"{column}: {value}\n"
        
        content += "\n" + "=" * 50 + "\n"
        content += "This document was generated automatically by the Office Automation System."
        
        return content
    
    def generate_data_report(self, data: pd.DataFrame, output_path: str) -> bool:
        """Generate a PDF report from data"""
        try:
            pdf = PDFGenerator(title="Data Report", author="Simple Automation System")
            
            # Add title and metadata
            pdf.add_title("Automated Data Report")
            pdf.add_subtitle(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Add data summary
            pdf.add_subtitle("Data Summary")
            pdf.add_paragraph(f"Total records: {len(data)}")
            pdf.add_paragraph(f"Columns: {', '.join(data.columns)}")
            
            # Add data table (first 20 rows)
            if len(data) > 0:
                pdf.add_subtitle("Data Sample (First 20 Rows)")
                
                display_data = data.head(20)
                table_data = []
                
                # Add headers
                headers = list(display_data.columns)
                
                # Add data rows
                for _, row in display_data.iterrows():
                    table_data.append([str(row[col]) for col in headers])
                
                pdf.add_table(table_data, headers=headers, table_style='professional')
            
            # Generate PDF
            return pdf.generate_pdf(output_path)
            
        except Exception as e:
            print(f"[ERROR] Error generating report: {e}")
            return False


def main():
    """Main function with CLI interface"""
    parser = argparse.ArgumentParser(description="Simple Office Automation Pipeline")
    parser.add_argument('--config', default='settings.yaml', help='Configuration file path')
    parser.add_argument('--pipeline', choices=['google-sheets', 'csv-docs', 'test'], 
                       required=True, help='Pipeline to run')
    parser.add_argument('--spreadsheet-id', help='Google Sheets spreadsheet ID')
    parser.add_argument('--sheet-name', default='Sheet1', help='Google Sheets sheet name')
    parser.add_argument('--csv-file', help='CSV file path')
    parser.add_argument('--template-file', help='Template file path')
    
    args = parser.parse_args()
    
    # Initialize pipeline
    pipeline = SimpleAutomationPipeline(config_path=args.config)
    
    try:
        if args.pipeline == 'google-sheets':
            if not args.spreadsheet_id:
                print("[ERROR] --spreadsheet-id is required for google-sheets pipeline")
                return False
            
            success = pipeline.run_google_sheets_to_pdf_pipeline(
                spreadsheet_id=args.spreadsheet_id,
                sheet_name=args.sheet_name
            )
            
        elif args.pipeline == 'csv-docs':
            if not args.csv_file:
                print("[ERROR] --csv-file is required for csv-docs pipeline")
                return False
            
            success = pipeline.run_csv_to_documents_pipeline(
                csv_file=args.csv_file,
                template_file=args.template_file
            )
            
        elif args.pipeline == 'test':
            print("[INFO] Running test pipeline...")
            
            # Generate sample report
            sample_path = "outputs/pdfs/test_report_simple.pdf"
            success = generate_sample_report(sample_path)
            
            if success:
                print(f"[OK] Test report generated: {sample_path}")
            else:
                print("[ERROR] Test report generation failed")
        
        else:
            print(f"[ERROR] Unknown pipeline: {args.pipeline}")
            return False
        
        if success:
            print("[SUCCESS] Pipeline completed successfully")
        else:
            print("[ERROR] Pipeline failed")
        
        return success
        
    except KeyboardInterrupt:
        print("\n[WARNING] Pipeline interrupted by user")
        return False
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)