#!/usr/bin/env python3
"""
Main Pipeline Script
Orchestrates the complete office automation workflow
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
import json

# Import our modules
try:
    from google_integration import GoogleIntegration
    from office_integration import ExcelIntegration, WordIntegration
    from pdf_generator import PDFGenerator, generate_sample_report
    from email_automation import EmailSender, EmailConfig, EmailTemplateManager
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure all required modules are in the same directory")
    sys.exit(1)

# Configure logging with Windows console encoding support
import io
import sys

# Set console to handle UTF-8 output
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('automation_pipeline.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class AutomationPipeline:
    """Main automation pipeline orchestrator"""
    
    def __init__(self, config_path: str = "settings.yaml"):
        self.config_path = config_path
        self.config = self.load_config()
        self.google_integration = None
        self.email_sender = None
        self.template_manager = None
        
        self.setup_directories()
        self.initialize_services()
    
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        try:
            if not os.path.exists(self.config_path):
                logger.error(f"❌ Configuration file not found: {self.config_path}")
                return {}
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            logger.info(f"✅ Configuration loaded from {self.config_path}")
            return config
            
        except Exception as e:
            logger.error(f"❌ Error loading configuration: {e}")
            return {}
    
    def setup_directories(self):
        """Create necessary directories"""
        directories = [
            "outputs/reports",
            "outputs/documents", 
            "outputs/pdfs",
            "outputs/data",
            "temp",
            "logs"
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
    
    def initialize_services(self):
        """Initialize external services"""
        try:
            # Initialize Google Integration
            google_config = self.config.get('google', {})
            if google_config.get('enabled', False):
                self.google_integration = GoogleIntegration(
                    credentials_path=google_config.get('credentials_path'),
                    token_path=google_config.get('token_path', 'google_token.json')
                )
                logger.info("✅ Google Integration initialized")
            
            # Initialize Email
            email_config = self.config.get('email', {})
            if email_config.get('enabled', False):
                email_cfg = EmailConfig(
                    smtp_server=email_config.get('smtp_server'),
                    smtp_port=email_config.get('smtp_port', 587),
                    username=email_config.get('username'),
                    password=email_config.get('password'),
                    use_tls=email_config.get('use_tls', True)
                )
                self.email_sender = EmailSender(email_cfg)
                
                # Initialize template manager
                self.template_manager = EmailTemplateManager("templates/email")
                logger.info("✅ Email automation initialized")
            
        except Exception as e:
            logger.error(f"❌ Error initializing services: {e}")
    
    def run_google_sheets_to_reports_pipeline(self, spreadsheet_id: str, 
                                            sheet_name: str = None) -> bool:
        """Complete pipeline: Google Sheets → PDF Reports → Email"""
        try:
            logger.info("🚀 Starting Google Sheets to Reports pipeline")
            
            if not self.google_integration:
                logger.error("❌ Google Integration not available")
                return False
            
            # Step 1: Read data from Google Sheets
            logger.info("📊 Reading data from Google Sheets...")
            data = self.google_integration.read_sheet_data(spreadsheet_id, sheet_name)
            
            if data.empty:
                logger.error("❌ No data retrieved from Google Sheets")
                return False
            
            logger.info(f"✅ Retrieved {len(data)} rows from Google Sheets")
            
            # Step 2: Save data locally
            data_file = f"outputs/data/sheet_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            data.to_csv(data_file, index=False)
            logger.info(f"💾 Data saved to: {data_file}")
            
            # Step 3: Generate PDF report
            logger.info("📄 Generating PDF report...")
            pdf_path = f"outputs/pdfs/report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            
            success = self.generate_data_report(data, pdf_path)
            if not success:
                logger.error("❌ Failed to generate PDF report")
                return False
            
            # Step 4: Send email with report
            if self.email_sender and self.config.get('email', {}).get('enabled', False):
                logger.info("📧 Sending email with report...")
                success = self.send_report_email(pdf_path, data_summary=self.get_data_summary(data))
                if success:
                    logger.info("✅ Email sent successfully")
                else:
                    logger.warning("⚠️ Email sending failed")
            
            logger.info("🏁 Pipeline completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Pipeline error: {e}")
            return False
    
    def run_excel_to_word_pipeline(self, excel_path: str, word_template_path: str,
                                 output_dir: str = "outputs/documents") -> bool:
        """Pipeline: Excel Data → Word Documents → PDF → Email"""
        try:
            logger.info("🚀 Starting Excel to Word pipeline")
            
            # Step 1: Read Excel data
            logger.info("📊 Reading Excel data...")
            with ExcelIntegration() as excel:
                if not excel.open_workbook(excel_path):
                    return False
                
                data = excel.read_data_to_dataframe()
                
                if data.empty:
                    logger.error("❌ No data found in Excel file")
                    return False
            
            logger.info(f"✅ Read {len(data)} rows from Excel")
            
            # Step 2: Generate Word documents for each row
            logger.info("📝 Generating Word documents...")
            generated_docs = []
            
            with WordIntegration() as word:
                for index, row in data.iterrows():
                    try:
                        # Create replacements dictionary from row data
                        replacements = {col: str(row[col]) for col in data.columns}
                        
                        # Generate output filename
                        name_col = 'Name' if 'Name' in data.columns else data.columns[0]
                        safe_name = str(row[name_col]).replace(' ', '_').replace('/', '_')
                        output_path = os.path.join(output_dir, f"document_{safe_name}_{index+1}.docx")
                        
                        # Process template
                        success = word.process_template(word_template_path, replacements, output_path)
                        
                        if success:
                            generated_docs.append(output_path)
                            logger.info(f"✅ Generated: {os.path.basename(output_path)}")
                        
                    except Exception as e:
                        logger.error(f"❌ Error processing row {index}: {e}")
                        continue
            
            logger.info(f"✅ Generated {len(generated_docs)} Word documents")
            
            # Step 3: Convert to PDF (optional)
            pdf_docs = []
            if self.config.get('pipeline', {}).get('convert_to_pdf', False):
                logger.info("🔄 Converting to PDF...")
                
                with WordIntegration() as word:
                    for doc_path in generated_docs:
                        try:
                            if word.open_document(doc_path):
                                pdf_path = doc_path.replace('.docx', '.pdf')
                                pdf_path = pdf_path.replace('documents', 'pdfs')
                                os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
                                
                                if word.convert_to_pdf(pdf_path):
                                    pdf_docs.append(pdf_path)
                                
                                word.close_document()
                                
                        except Exception as e:
                            logger.error(f"❌ Error converting {doc_path} to PDF: {e}")
                            continue
                
                logger.info(f"✅ Generated {len(pdf_docs)} PDF documents")
            
            # Step 4: Send summary email
            if self.email_sender:
                logger.info("📧 Sending summary email...")
                self.send_pipeline_summary_email(
                    excel_file=excel_path,
                    documents_generated=len(generated_docs),
                    pdfs_generated=len(pdf_docs)
                )
            
            logger.info("🏁 Excel to Word pipeline completed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Excel to Word pipeline error: {e}")
            return False
    
    def generate_data_report(self, data: pd.DataFrame, output_path: str) -> bool:
        """Generate a comprehensive PDF report from data"""
        try:
            pdf = PDFGenerator(title="Data Analysis Report", author="Office Automation System")
            
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
                table_data.append(headers)
                
                # Add data rows
                for _, row in display_data.iterrows():
                    table_data.append([str(row[col]) for col in headers])
                
                pdf.add_table(table_data[1:], headers=headers, table_style='professional')
            
            # Add statistics if numeric columns exist
            numeric_columns = data.select_dtypes(include=['number']).columns
            if len(numeric_columns) > 0:
                pdf.add_subtitle("Statistical Summary")
                stats = data[numeric_columns].describe()
                
                stats_data = []
                stats_data.append(['Statistic'] + list(numeric_columns))
                
                for stat in ['count', 'mean', 'std', 'min', '25%', '50%', '75%', 'max']:
                    if stat in stats.index:
                        row = [stat] + [f"{stats.loc[stat, col]:.2f}" if pd.notna(stats.loc[stat, col]) else 'N/A' 
                                       for col in numeric_columns]
                        stats_data.append(row)
                
                pdf.add_table(stats_data[1:], headers=stats_data[0], table_style='professional')
            
            # Generate PDF
            return pdf.generate_pdf(output_path)
            
        except Exception as e:
            logger.error(f"❌ Error generating data report: {e}")
            return False
    
    def get_data_summary(self, data: pd.DataFrame) -> str:
        """Get a text summary of the data"""
        try:
            summary = f"""
Data Summary:
- Total rows: {len(data)}
- Total columns: {len(data.columns)}
- Columns: {', '.join(data.columns)}
- Memory usage: {data.memory_usage(deep=True).sum() / 1024:.2f} KB
"""
            
            # Add info about missing values
            missing_values = data.isnull().sum()
            if missing_values.sum() > 0:
                summary += f"\nMissing values found in: {', '.join(missing_values[missing_values > 0].index)}"
            else:
                summary += "\nNo missing values found."
            
            return summary
            
        except Exception as e:
            logger.error(f"❌ Error generating data summary: {e}")
            return "Error generating summary"
    
    def send_report_email(self, pdf_path: str, data_summary: str = None) -> bool:
        """Send email with PDF report attachment"""
        try:
            if not self.email_sender:
                logger.warning("⚠️ Email sender not configured")
                return False
            
            email_config = self.config.get('email', {})
            recipients = email_config.get('report_recipients', [])
            
            if not recipients:
                logger.warning("⚠️ No email recipients configured")
                return False
            
            subject = f"Automated Report - {datetime.now().strftime('%Y-%m-%d')}"
            
            body = f"""
Hello,

Please find attached the automated report generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.

{data_summary or 'Report generated successfully.'}

Best regards,
Office Automation System
"""
            
            with self.email_sender:
                for recipient in recipients:
                    success = self.email_sender.send_email_with_attachments(
                        to_email=recipient,
                        subject=subject,
                        body=body,
                        attachments=[pdf_path],
                        from_name="Office Automation"
                    )
                    
                    if not success:
                        logger.error(f"❌ Failed to send email to {recipient}")
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error sending report email: {e}")
            return False
    
    def send_pipeline_summary_email(self, **kwargs) -> bool:
        """Send pipeline completion summary email"""
        try:
            if not self.email_sender:
                return False
            
            email_config = self.config.get('email', {})
            recipients = email_config.get('notification_recipients', [])
            
            if not recipients:
                return False
            
            subject = f"Pipeline Completed - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            body = f"""
Pipeline Execution Summary
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Details:
"""
            
            for key, value in kwargs.items():
                body += f"- {key.replace('_', ' ').title()}: {value}\n"
            
            body += """
Best regards,
Office Automation System
"""
            
            with self.email_sender:
                for recipient in recipients:
                    self.email_sender.send_simple_email(
                        to_email=recipient,
                        subject=subject,
                        body=body,
                        from_name="Office Automation"
                    )
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error sending summary email: {e}")
            return False


def main():
    """Main function with CLI interface"""
    parser = argparse.ArgumentParser(description="Office Automation Pipeline")
    parser.add_argument('--config', default='settings.yaml', help='Configuration file path')
    parser.add_argument('--pipeline', choices=['google-sheets', 'excel-word', 'test'], 
                       required=True, help='Pipeline to run')
    parser.add_argument('--spreadsheet-id', help='Google Sheets spreadsheet ID')
    parser.add_argument('--sheet-name', help='Google Sheets sheet name')
    parser.add_argument('--excel-file', help='Excel file path')
    parser.add_argument('--word-template', help='Word template file path')
    parser.add_argument('--output-dir', default='outputs', help='Output directory')
    
    args = parser.parse_args()
    
    # Initialize pipeline
    pipeline = AutomationPipeline(config_path=args.config)
    
    try:
        if args.pipeline == 'google-sheets':
            if not args.spreadsheet_id:
                print("❌ --spreadsheet-id is required for google-sheets pipeline")
                return False
            
            success = pipeline.run_google_sheets_to_reports_pipeline(
                spreadsheet_id=args.spreadsheet_id,
                sheet_name=args.sheet_name
            )
            
        elif args.pipeline == 'excel-word':
            if not args.excel_file or not args.word_template:
                print("❌ --excel-file and --word-template are required for excel-word pipeline")
                return False
            
            success = pipeline.run_excel_to_word_pipeline(
                excel_path=args.excel_file,
                word_template_path=args.word_template,
                output_dir=args.output_dir
            )
            
        elif args.pipeline == 'test':
            print("🧪 Running test pipeline...")
            
            # Generate sample report
            sample_path = "outputs/pdfs/test_report.pdf"
            success = generate_sample_report(sample_path)
            
            if success:
                print(f"✅ Test report generated: {sample_path}")
            else:
                print("❌ Test report generation failed")
        
        else:
            print(f"❌ Unknown pipeline: {args.pipeline}")
            return False
        
        if success:
            print("🏁 Pipeline completed successfully")
        else:
            print("❌ Pipeline failed")
        
        return success
        
    except KeyboardInterrupt:
        print("\n⚠️ Pipeline interrupted by user")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)