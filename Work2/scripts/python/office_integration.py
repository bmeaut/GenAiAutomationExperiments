#!/usr/bin/env python3
"""
Office Integration Module
Handles Excel, Word, PowerPoint automation via COM objects
"""

import os
import pandas as pd
import pythoncom
import win32com.client as win32
from typing import Optional, List, Dict, Any, Union
from pathlib import Path
import time

import logging
logger = logging.getLogger(__name__)


class ExcelIntegration:
    """Excel automation via COM objects"""
    
    def __init__(self, visible: bool = False):
        self.visible = visible
        self.excel_app = None
        self.workbook = None
        self.worksheet = None
        
        self.initialize_excel()
    
    def initialize_excel(self):
        """Initialize Excel COM application"""
        try:
            pythoncom.CoInitialize()
            self.excel_app = win32.gencache.EnsureDispatch('Excel.Application')
            self.excel_app.Visible = self.visible
            self.excel_app.DisplayAlerts = False
            logger.info("✅ Excel COM connection established")
        except Exception as e:
            logger.error(f"❌ Error initializing Excel: {e}")
            raise
    
    def open_workbook(self, file_path: str) -> bool:
        """Open an Excel workbook"""
        try:
            if not os.path.exists(file_path):
                logger.error(f"❌ Excel file not found: {file_path}")
                return False
            
            self.workbook = self.excel_app.Workbooks.Open(os.path.abspath(file_path))
            self.worksheet = self.workbook.ActiveSheet
            
            logger.info(f"✅ Opened Excel workbook: {os.path.basename(file_path)}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error opening Excel workbook: {e}")
            return False
    
    def create_new_workbook(self) -> bool:
        """Create a new Excel workbook"""
        try:
            self.workbook = self.excel_app.Workbooks.Add()
            self.worksheet = self.workbook.ActiveSheet
            logger.info("✅ Created new Excel workbook")
            return True
        except Exception as e:
            logger.error(f"❌ Error creating Excel workbook: {e}")
            return False
    
    def read_data_to_dataframe(self, range_addr: str = None, sheet_name: str = None) -> pd.DataFrame:
        """Read Excel data to pandas DataFrame"""
        try:
            if self.workbook is None:
                logger.error("❌ No workbook is open")
                return pd.DataFrame()
            
            # Select worksheet if specified
            if sheet_name:
                try:
                    worksheet = self.workbook.Sheets(sheet_name)
                except:
                    logger.error(f"❌ Worksheet '{sheet_name}' not found")
                    return pd.DataFrame()
            else:
                worksheet = self.worksheet
            
            # Get range
            if range_addr:
                excel_range = worksheet.Range(range_addr)
            else:
                excel_range = worksheet.UsedRange
            
            # Get values
            values = excel_range.Value
            
            if values is None:
                return pd.DataFrame()
            
            # Convert to DataFrame
            if isinstance(values, tuple) and len(values) > 1:
                df = pd.DataFrame(list(values[1:]), columns=list(values[0]))
            elif isinstance(values, tuple) and len(values) == 1:
                df = pd.DataFrame([list(values[0])])
            else:
                df = pd.DataFrame([values])
            
            logger.info(f"✅ Read {len(df)} rows from Excel")
            return df
            
        except Exception as e:
            logger.error(f"❌ Error reading Excel data: {e}")
            return pd.DataFrame()
    
    def write_dataframe_to_excel(self, df: pd.DataFrame, start_cell: str = "A1", 
                                sheet_name: str = None, include_headers: bool = True) -> bool:
        """Write pandas DataFrame to Excel"""
        try:
            if self.workbook is None:
                logger.error("❌ No workbook is open")
                return False
            
            # Select or create worksheet
            if sheet_name:
                try:
                    worksheet = self.workbook.Sheets(sheet_name)
                except:
                    worksheet = self.workbook.Sheets.Add()
                    worksheet.Name = sheet_name
            else:
                worksheet = self.worksheet
            
            # Prepare data
            if include_headers:
                data = [list(df.columns)] + df.values.tolist()
            else:
                data = df.values.tolist()
            
            # Calculate range
            start_range = worksheet.Range(start_cell)
            rows = len(data)
            cols = len(data[0]) if data else 0
            
            if rows > 0 and cols > 0:
                end_col = chr(ord(start_cell[0]) + cols - 1)
                end_row = start_range.Row + rows - 1
                end_cell = f"{end_col}{end_row}"
                
                # Write data
                write_range = worksheet.Range(f"{start_cell}:{end_cell}")
                write_range.Value = data
            
            logger.info(f"✅ Wrote {len(df)} rows to Excel at {start_cell}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error writing to Excel: {e}")
            return False
    
    def run_macro(self, macro_name: str, *args) -> Any:
        """Run an Excel macro"""
        try:
            if self.excel_app is None:
                logger.error("❌ Excel application not initialized")
                return None
            
            result = self.excel_app.Run(macro_name, *args)
            logger.info(f"✅ Executed Excel macro: {macro_name}")
            return result
        except Exception as e:
            logger.error(f"❌ Error running Excel macro {macro_name}: {e}")
            return None
    
    def save_workbook(self, file_path: str = None) -> bool:
        """Save the workbook"""
        try:
            if self.workbook is None:
                logger.error("❌ No workbook to save")
                return False
            
            if file_path:
                self.workbook.SaveAs(os.path.abspath(file_path))
                logger.info(f"✅ Saved Excel workbook as: {file_path}")
            else:
                self.workbook.Save()
                logger.info("✅ Saved Excel workbook")
            
            return True
        except Exception as e:
            logger.error(f"❌ Error saving Excel workbook: {e}")
            return False
    
    def close_workbook(self):
        """Close the current workbook"""
        try:
            if self.workbook:
                self.workbook.Close()
                self.workbook = None
                self.worksheet = None
                logger.info("✅ Closed Excel workbook")
        except Exception as e:
            logger.error(f"❌ Error closing Excel workbook: {e}")
    
    def quit_excel(self):
        """Quit Excel application"""
        try:
            if self.excel_app:
                self.excel_app.Quit()
                self.excel_app = None
                logger.info("✅ Excel application closed")
            pythoncom.CoUninitialize()
        except Exception as e:
            logger.error(f"❌ Error quitting Excel: {e}")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_workbook()
        self.quit_excel()


class WordIntegration:
    """Word automation via COM objects"""
    
    def __init__(self, visible: bool = False):
        self.visible = visible
        self.word_app = None
        self.document = None
        
        self.initialize_word()
    
    def initialize_word(self):
        """Initialize Word COM application"""
        try:
            pythoncom.CoInitialize()
            self.word_app = win32.gencache.EnsureDispatch('Word.Application')
            self.word_app.Visible = self.visible
            self.word_app.DisplayAlerts = 0  # Disable alerts
            logger.info("✅ Word COM connection established")
        except Exception as e:
            logger.error(f"❌ Error initializing Word: {e}")
            raise
    
    def open_document(self, file_path: str) -> bool:
        """Open a Word document"""
        try:
            if not os.path.exists(file_path):
                logger.error(f"❌ Word file not found: {file_path}")
                return False
            
            self.document = self.word_app.Documents.Open(os.path.abspath(file_path))
            logger.info(f"✅ Opened Word document: {os.path.basename(file_path)}")
            return True
        except Exception as e:
            logger.error(f"❌ Error opening Word document: {e}")
            return False
    
    def create_new_document(self) -> bool:
        """Create a new Word document"""
        try:
            self.document = self.word_app.Documents.Add()
            logger.info("✅ Created new Word document")
            return True
        except Exception as e:
            logger.error(f"❌ Error creating Word document: {e}")
            return False
    
    def process_template(self, template_path: str, replacements: Dict[str, Any], 
                        output_path: str) -> bool:
        """Process Word template with data replacements"""
        try:
            # Open template
            if not self.open_document(template_path):
                return False
            
            # Perform replacements
            for placeholder, value in replacements.items():
                self.replace_text(f"{{{{{placeholder}}}}}", str(value))
            
            # Save as new document
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            self.document.SaveAs2(os.path.abspath(output_path))
            
            logger.info(f"✅ Processed Word template: {os.path.basename(output_path)}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error processing Word template: {e}")
            return False
        finally:
            if self.document:
                self.document.Close()
                self.document = None
    
    def replace_text(self, find_text: str, replace_text: str) -> bool:
        """Replace text in the current document"""
        try:
            if self.document is None:
                logger.error("❌ No document is open")
                return False
            
            # Replace in main document
            find_range = self.document.Content
            find_range.Find.ClearFormatting()
            find_range.Find.Replacement.ClearFormatting()
            find_range.Find.Execute(
                FindText=find_text,
                ReplaceWith=replace_text,
                Replace=2  # wdReplaceAll
            )
            
            # Replace in headers and footers
            for section in self.document.Sections:
                # Headers
                for header in section.Headers:
                    if header.Exists:
                        header_range = header.Range
                        header_range.Find.Execute(
                            FindText=find_text,
                            ReplaceWith=replace_text,
                            Replace=2
                        )
                
                # Footers
                for footer in section.Footers:
                    if footer.Exists:
                        footer_range = footer.Range
                        footer_range.Find.Execute(
                            FindText=find_text,
                            ReplaceWith=replace_text,
                            Replace=2
                        )
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error replacing text in Word: {e}")
            return False
    
    def convert_to_pdf(self, output_path: str) -> bool:
        """Convert current document to PDF"""
        try:
            if self.document is None:
                logger.error("❌ No document is open")
                return False
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            self.document.ExportAsFixedFormat(
                OutputFileName=os.path.abspath(output_path),
                ExportFormat=17,  # wdExportFormatPDF
                OpenAfterExport=False,
                OptimizeFor=0,  # wdExportOptimizeForPrint
                BitmapMissingFonts=True,
                DocStructureTags=True,
                CreateBookmarks=0,  # wdExportDocumentContent
                IncludeDocProps=True,
                KeepIRM=True
            )
            
            logger.info(f"✅ Converted to PDF: {os.path.basename(output_path)}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error converting Word to PDF: {e}")
            return False
    
    def save_document(self, file_path: str = None) -> bool:
        """Save the document"""
        try:
            if self.document is None:
                logger.error("❌ No document to save")
                return False
            
            if file_path:
                self.document.SaveAs2(os.path.abspath(file_path))
                logger.info(f"✅ Saved Word document as: {file_path}")
            else:
                self.document.Save()
                logger.info("✅ Saved Word document")
            
            return True
        except Exception as e:
            logger.error(f"❌ Error saving Word document: {e}")
            return False
    
    def close_document(self):
        """Close the current document"""
        try:
            if self.document:
                self.document.Close()
                self.document = None
                logger.info("✅ Closed Word document")
        except Exception as e:
            logger.error(f"❌ Error closing Word document: {e}")
    
    def quit_word(self):
        """Quit Word application"""
        try:
            if self.word_app:
                self.word_app.Quit()
                self.word_app = None
                logger.info("✅ Word application closed")
            pythoncom.CoUninitialize()
        except Exception as e:
            logger.error(f"❌ Error quitting Word: {e}")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_document()
        self.quit_word()


class PowerPointIntegration:
    """PowerPoint automation via COM objects"""
    
    def __init__(self, visible: bool = False):
        self.visible = visible
        self.ppt_app = None
        self.presentation = None
        
        self.initialize_powerpoint()
    
    def initialize_powerpoint(self):
        """Initialize PowerPoint COM application"""
        try:
            pythoncom.CoInitialize()
            self.ppt_app = win32.gencache.EnsureDispatch('PowerPoint.Application')
            self.ppt_app.Visible = self.visible
            logger.info("✅ PowerPoint COM connection established")
        except Exception as e:
            logger.error(f"❌ Error initializing PowerPoint: {e}")
            raise
    
    def open_presentation(self, file_path: str) -> bool:
        """Open a PowerPoint presentation"""
        try:
            if not os.path.exists(file_path):
                logger.error(f"❌ PowerPoint file not found: {file_path}")
                return False
            
            self.presentation = self.ppt_app.Presentations.Open(os.path.abspath(file_path))
            logger.info(f"✅ Opened PowerPoint presentation: {os.path.basename(file_path)}")
            return True
        except Exception as e:
            logger.error(f"❌ Error opening PowerPoint presentation: {e}")
            return False
    
    def create_new_presentation(self) -> bool:
        """Create a new PowerPoint presentation"""
        try:
            self.presentation = self.ppt_app.Presentations.Add()
            logger.info("✅ Created new PowerPoint presentation")
            return True
        except Exception as e:
            logger.error(f"❌ Error creating PowerPoint presentation: {e}")
            return False
    
    def replace_text_in_slides(self, replacements: Dict[str, str]) -> bool:
        """Replace text in all slides"""
        try:
            if self.presentation is None:
                logger.error("❌ No presentation is open")
                return False
            
            for slide in self.presentation.Slides:
                for shape in slide.Shapes:
                    if hasattr(shape, 'TextFrame'):
                        if shape.TextFrame.HasText:
                            for placeholder, value in replacements.items():
                                find_text = f"{{{{{placeholder}}}}}"
                                shape.TextFrame.TextRange.Replace(find_text, str(value))
            
            logger.info(f"✅ Replaced text in {len(self.presentation.Slides)} slides")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error replacing text in PowerPoint: {e}")
            return False
    
    def export_as_pdf(self, output_path: str) -> bool:
        """Export presentation as PDF"""
        try:
            if self.presentation is None:
                logger.error("❌ No presentation is open")
                return False
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            self.presentation.ExportAsFixedFormat(
                Path=os.path.abspath(output_path),
                FixedFormatType=2  # ppFixedFormatTypePDF
            )
            
            logger.info(f"✅ Exported PowerPoint as PDF: {os.path.basename(output_path)}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error exporting PowerPoint as PDF: {e}")
            return False
    
    def save_presentation(self, file_path: str = None) -> bool:
        """Save the presentation"""
        try:
            if self.presentation is None:
                logger.error("❌ No presentation to save")
                return False
            
            if file_path:
                self.presentation.SaveAs(os.path.abspath(file_path))
                logger.info(f"✅ Saved PowerPoint presentation as: {file_path}")
            else:
                self.presentation.Save()
                logger.info("✅ Saved PowerPoint presentation")
            
            return True
        except Exception as e:
            logger.error(f"❌ Error saving PowerPoint presentation: {e}")
            return False
    
    def close_presentation(self):
        """Close the current presentation"""
        try:
            if self.presentation:
                self.presentation.Close()
                self.presentation = None
                logger.info("✅ Closed PowerPoint presentation")
        except Exception as e:
            logger.error(f"❌ Error closing PowerPoint presentation: {e}")
    
    def quit_powerpoint(self):
        """Quit PowerPoint application"""
        try:
            if self.ppt_app:
                self.ppt_app.Quit()
                self.ppt_app = None
                logger.info("✅ PowerPoint application closed")
            pythoncom.CoUninitialize()
        except Exception as e:
            logger.error(f"❌ Error quitting PowerPoint: {e}")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_presentation()
        self.quit_powerpoint()


def test_office_integration():
    """Test function for Office Integration"""
    print("🧪 Testing Office Integration...")
    
    # Test Excel
    try:
        with ExcelIntegration(visible=True) as excel:
            excel.create_new_workbook()
            
            # Create test data
            test_data = pd.DataFrame({
                'Name': ['John Doe', 'Jane Smith', 'Bob Johnson'],
                'Email': ['john@email.com', 'jane@email.com', 'bob@email.com'],
                'Department': ['IT', 'HR', 'Finance']
            })
            
            excel.write_dataframe_to_excel(test_data)
            read_data = excel.read_data_to_dataframe()
            
            print("✅ Excel integration test passed")
            print(f"Data shape: {read_data.shape}")
            
    except Exception as e:
        print(f"❌ Excel integration test failed: {e}")
    
    # Test Word
    try:
        with WordIntegration(visible=True) as word:
            word.create_new_document()
            word.replace_text("Test", "Hello World")
            
            print("✅ Word integration test passed")
            
    except Exception as e:
        print(f"❌ Word integration test failed: {e}")
    
    print("🏁 Office integration tests completed")


if __name__ == "__main__":
    test_office_integration()