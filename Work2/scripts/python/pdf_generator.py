#!/usr/bin/env python3
"""
PDF Generation Module
Advanced PDF creation and manipulation utilities
"""

import os
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, timedelta
import tempfile

# PDF Libraries
try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.platypus import Image as ReportLabImage
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.colors import black, blue, red, green
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.graphics.shapes import Drawing
    from reportlab.graphics.charts.linecharts import HorizontalLineChart
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    from reportlab.graphics.charts.piecharts import Pie
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

try:
    import PyPDF2
    from PyPDF2 import PdfReader, PdfWriter
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False

try:
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use('Agg')  # Use non-interactive backend
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

logger = logging.getLogger(__name__)


class PDFGenerator:
    """Advanced PDF generation with ReportLab"""
    
    def __init__(self, title: str = "Generated Report", author: str = "Office Automation"):
        self.title = title
        self.author = author
        self.styles = None
        self.story = []
        
        if not REPORTLAB_AVAILABLE:
            raise ImportError("ReportLab is required for PDF generation. Install with: pip install reportlab")
        
        self._setup_styles()
    
    def _setup_styles(self):
        """Setup document styles"""
        self.styles = getSampleStyleSheet()
        
        # Custom styles
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.darkblue
        ))
        
        self.styles.add(ParagraphStyle(
            name='CustomSubtitle',
            parent=self.styles['Heading2'],
            fontSize=16,
            spaceAfter=20,
            alignment=TA_LEFT,
            textColor=colors.blue
        ))
        
        self.styles.add(ParagraphStyle(
            name='CustomBody',
            parent=self.styles['Normal'],
            fontSize=11,
            spaceAfter=12,
            alignment=TA_JUSTIFY
        ))
        
        self.styles.add(ParagraphStyle(
            name='Highlight',
            parent=self.styles['Normal'],
            fontSize=11,
            spaceAfter=12,
            backColor=colors.lightyellow,
            borderColor=colors.orange,
            borderWidth=1,
            borderPadding=5
        ))
    
    def add_title(self, title: str):
        """Add a title to the document"""
        self.story.append(Paragraph(title, self.styles['CustomTitle']))
        self.story.append(Spacer(1, 0.2 * inch))
    
    def add_subtitle(self, subtitle: str):
        """Add a subtitle to the document"""
        self.story.append(Paragraph(subtitle, self.styles['CustomSubtitle']))
        self.story.append(Spacer(1, 0.1 * inch))
    
    def add_paragraph(self, text: str, style: str = 'CustomBody'):
        """Add a paragraph of text"""
        self.story.append(Paragraph(text, self.styles[style]))
        self.story.append(Spacer(1, 0.1 * inch))
    
    def add_highlighted_text(self, text: str):
        """Add highlighted text"""
        self.story.append(Paragraph(text, self.styles['Highlight']))
        self.story.append(Spacer(1, 0.1 * inch))
    
    def add_table(self, data: List[List[str]], headers: List[str] = None, 
                  table_style: str = 'default') -> bool:
        """Add a table to the document"""
        try:
            if headers:
                table_data = [headers] + data
            else:
                table_data = data
            
            table = Table(table_data)
            
            # Apply table style
            if table_style == 'default':
                style = TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 12),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ])
            elif table_style == 'professional':
                style = TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('LINEBELOW', (0, 0), (-1, 0), 2, colors.darkblue),
                    ('GRID', (0, 1), (-1, -1), 0.5, colors.grey)
                ])
            else:
                style = TableStyle([
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ])
            
            table.setStyle(style)
            self.story.append(table)
            self.story.append(Spacer(1, 0.2 * inch))
            
            logger.info(f"✅ Added table with {len(data)} rows")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error adding table to PDF: {e}")
            return False
    
    def add_chart_from_data(self, data: Dict[str, List], chart_type: str = 'bar', 
                           title: str = "Chart", width: int = 400, height: int = 300) -> bool:
        """Add a chart to the document"""
        try:
            if not MATPLOTLIB_AVAILABLE:
                logger.warning("⚠️ Matplotlib not available, skipping chart")
                return False
            
            # Create chart with matplotlib
            fig, ax = plt.subplots(figsize=(width/100, height/100))
            
            if chart_type == 'bar':
                keys = list(data.keys())
                if len(keys) >= 2:
                    ax.bar(data[keys[0]], data[keys[1]])
                    ax.set_xlabel(keys[0])
                    ax.set_ylabel(keys[1])
            elif chart_type == 'line':
                keys = list(data.keys())
                if len(keys) >= 2:
                    ax.plot(data[keys[0]], data[keys[1]], marker='o')
                    ax.set_xlabel(keys[0])
                    ax.set_ylabel(keys[1])
            elif chart_type == 'pie':
                keys = list(data.keys())
                if len(keys) >= 2:
                    ax.pie(data[keys[1]], labels=data[keys[0]], autopct='%1.1f%%')
            
            ax.set_title(title)
            plt.tight_layout()
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                plt.savefig(tmp.name, dpi=150, bbox_inches='tight')
                temp_path = tmp.name
            
            plt.close(fig)
            
            # Add image to PDF
            self.add_image(temp_path, width=width, height=height)
            
            # Clean up temp file
            os.unlink(temp_path)
            
            logger.info(f"✅ Added {chart_type} chart to PDF")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error adding chart to PDF: {e}")
            return False
    
    def add_image(self, image_path: str, width: Optional[int] = None, 
                  height: Optional[int] = None, maintain_aspect: bool = True):
        """Add an image to the document"""
        try:
            if not os.path.exists(image_path):
                logger.error(f"❌ Image file not found: {image_path}")
                return False
            
            if width and height:
                img = ReportLabImage(image_path, width=width, height=height)
            elif width:
                img = ReportLabImage(image_path, width=width)
            elif height:
                img = ReportLabImage(image_path, height=height)
            else:
                img = ReportLabImage(image_path, width=4*inch, height=3*inch)
            
            self.story.append(img)
            self.story.append(Spacer(1, 0.2 * inch))
            
            logger.info(f"✅ Added image to PDF: {os.path.basename(image_path)}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error adding image to PDF: {e}")
            return False
    
    def add_page_break(self):
        """Add a page break"""
        self.story.append(PageBreak())
    
    def generate_pdf(self, output_path: str, page_size=A4) -> bool:
        """Generate the PDF file"""
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            doc = SimpleDocTemplate(
                output_path,
                pagesize=page_size,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=18,
                title=self.title,
                author=self.author
            )
            
            doc.build(self.story)
            
            logger.info(f"✅ Generated PDF: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error generating PDF: {e}")
            return False
    
    def clear_content(self):
        """Clear all content from the story"""
        self.story = []


class PDFManipulator:
    """PDF manipulation utilities using PyPDF2"""
    
    def __init__(self):
        if not PYPDF2_AVAILABLE:
            raise ImportError("PyPDF2 is required for PDF manipulation. Install with: pip install PyPDF2")
    
    def merge_pdfs(self, pdf_paths: List[str], output_path: str) -> bool:
        """Merge multiple PDF files"""
        try:
            writer = PdfWriter()
            
            for pdf_path in pdf_paths:
                if not os.path.exists(pdf_path):
                    logger.warning(f"⚠️ PDF file not found: {pdf_path}")
                    continue
                
                reader = PdfReader(pdf_path)
                for page in reader.pages:
                    writer.add_page(page)
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'wb') as output_file:
                writer.write(output_file)
            
            logger.info(f"✅ Merged {len(pdf_paths)} PDFs into: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error merging PDFs: {e}")
            return False
    
    def split_pdf(self, pdf_path: str, output_dir: str, pages_per_file: int = 1) -> bool:
        """Split PDF into multiple files"""
        try:
            if not os.path.exists(pdf_path):
                logger.error(f"❌ PDF file not found: {pdf_path}")
                return False
            
            reader = PdfReader(pdf_path)
            total_pages = len(reader.pages)
            
            os.makedirs(output_dir, exist_ok=True)
            
            base_name = Path(pdf_path).stem
            
            for i in range(0, total_pages, pages_per_file):
                writer = PdfWriter()
                
                for j in range(i, min(i + pages_per_file, total_pages)):
                    writer.add_page(reader.pages[j])
                
                output_filename = f"{base_name}_part_{i//pages_per_file + 1}.pdf"
                output_filepath = os.path.join(output_dir, output_filename)
                
                with open(output_filepath, 'wb') as output_file:
                    writer.write(output_file)
            
            logger.info(f"✅ Split PDF into {(total_pages-1)//pages_per_file + 1} files")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error splitting PDF: {e}")
            return False
    
    def extract_pages(self, pdf_path: str, page_numbers: List[int], output_path: str) -> bool:
        """Extract specific pages from PDF"""
        try:
            if not os.path.exists(pdf_path):
                logger.error(f"❌ PDF file not found: {pdf_path}")
                return False
            
            reader = PdfReader(pdf_path)
            writer = PdfWriter()
            
            for page_num in page_numbers:
                if 0 <= page_num < len(reader.pages):
                    writer.add_page(reader.pages[page_num])
                else:
                    logger.warning(f"⚠️ Page {page_num} is out of range")
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'wb') as output_file:
                writer.write(output_file)
            
            logger.info(f"✅ Extracted {len(page_numbers)} pages to: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error extracting pages: {e}")
            return False
    
    def add_watermark(self, pdf_path: str, watermark_path: str, output_path: str) -> bool:
        """Add watermark to PDF"""
        try:
            if not os.path.exists(pdf_path) or not os.path.exists(watermark_path):
                logger.error("❌ PDF or watermark file not found")
                return False
            
            reader = PdfReader(pdf_path)
            watermark_reader = PdfReader(watermark_path)
            watermark_page = watermark_reader.pages[0]
            
            writer = PdfWriter()
            
            for page in reader.pages:
                page.merge_page(watermark_page)
                writer.add_page(page)
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'wb') as output_file:
                writer.write(output_file)
            
            logger.info(f"✅ Added watermark to PDF: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error adding watermark: {e}")
            return False
    
    def get_pdf_info(self, pdf_path: str) -> Dict[str, Any]:
        """Get PDF information"""
        try:
            if not os.path.exists(pdf_path):
                logger.error(f"❌ PDF file not found: {pdf_path}")
                return {}
            
            reader = PdfReader(pdf_path)
            
            info = {
                'title': reader.metadata.title if reader.metadata else 'Unknown',
                'author': reader.metadata.author if reader.metadata else 'Unknown',
                'creator': reader.metadata.creator if reader.metadata else 'Unknown',
                'producer': reader.metadata.producer if reader.metadata else 'Unknown',
                'subject': reader.metadata.subject if reader.metadata else 'Unknown',
                'creation_date': reader.metadata.creation_date if reader.metadata else None,
                'modification_date': reader.metadata.modification_date if reader.metadata else None,
                'pages': len(reader.pages),
                'file_size': os.path.getsize(pdf_path)
            }
            
            logger.info(f"✅ Retrieved PDF info for: {os.path.basename(pdf_path)}")
            return info
            
        except Exception as e:
            logger.error(f"❌ Error getting PDF info: {e}")
            return {}


def generate_sample_report(output_path: str) -> bool:
    """Generate a sample PDF report"""
    try:
        pdf = PDFGenerator(title="Sample Automation Report", author="Office Automation System")
        
        # Add content
        pdf.add_title("Office Automation Report")
        pdf.add_subtitle("System Performance Analysis")
        
        pdf.add_paragraph(
            "This report demonstrates the PDF generation capabilities of our office automation system. "
            "The following sections contain various types of content including tables, charts, and formatted text."
        )
        
        # Add a table
        table_data = [
            ['Department', 'Employees', 'Productivity Score', 'Budget (USD)'],
            ['IT', '25', '92%', '$125,000'],
            ['HR', '12', '88%', '$85,000'],
            ['Finance', '18', '95%', '$110,000'],
            ['Marketing', '22', '87%', '$95,000']
        ]
        
        pdf.add_subtitle("Department Performance Metrics")
        pdf.add_table(table_data[1:], headers=table_data[0], table_style='professional')
        
        # Add highlighted content
        pdf.add_highlighted_text(
            "Key Finding: The Finance department shows the highest productivity score at 95%, "
            "while maintaining efficient budget utilization."
        )
        
        # Add chart data
        chart_data = {
            'Departments': ['IT', 'HR', 'Finance', 'Marketing'],
            'Scores': [92, 88, 95, 87]
        }
        
        pdf.add_subtitle("Productivity Score Visualization")
        pdf.add_chart_from_data(chart_data, chart_type='bar', title='Department Productivity Scores')
        
        # Generate PDF
        result = pdf.generate_pdf(output_path)
        
        if result:
            logger.info(f"✅ Sample report generated: {output_path}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Error generating sample report: {e}")
        return False


def test_pdf_generation():
    """Test function for PDF generation"""
    print("🧪 Testing PDF Generation...")
    
    output_dir = Path("test_output")
    output_dir.mkdir(exist_ok=True)
    
    # Test report generation
    sample_path = output_dir / "sample_report.pdf"
    success = generate_sample_report(str(sample_path))
    
    if success:
        print(f"✅ PDF generation test passed: {sample_path}")
    else:
        print("❌ PDF generation test failed")
    
    # Test PDF manipulation if file exists
    if success and PYPDF2_AVAILABLE:
        manipulator = PDFManipulator()
        
        # Test PDF info
        info = manipulator.get_pdf_info(str(sample_path))
        print(f"📄 PDF Info: {info.get('pages', 0)} pages, {info.get('file_size', 0)} bytes")
        
        # Test page extraction
        extract_path = output_dir / "extracted_pages.pdf"
        manipulator.extract_pages(str(sample_path), [0], str(extract_path))
        print(f"✅ Page extraction test completed: {extract_path}")
    
    print("🏁 PDF generation tests completed")


if __name__ == "__main__":
    test_pdf_generation()