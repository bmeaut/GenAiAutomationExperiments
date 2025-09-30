#!/usr/bin/env python3
"""
Mail Merge Automation Script
Automatically fills Word document templates with data from Excel/CSV files
"""

import pandas as pd
import os
from datetime import datetime
import re

class MailMergeProcessor:
    def __init__(self, data_file="data/test_data.csv", template_dir="templates", output_dir="generated_docs"):
        self.data_file = data_file
        self.template_dir = template_dir
        self.output_dir = output_dir
        self.data = None
        self.load_data()
        
    def load_data(self):
        """Load data from CSV file"""
        try:
            self.data = pd.read_csv(self.data_file)
            print(f"Loaded {len(self.data)} records from {self.data_file}")
            print(f"Columns: {list(self.data.columns)}")
        except Exception as e:
            print(f"Error loading data: {e}")
            
    def process_template(self, template_path, row_data, output_filename=None):
        """Process a single template with row data"""
        try:
            # Read template content
            with open(template_path, 'r', encoding='utf-8') as file:
                template_content = file.read()
            
            # Replace placeholders with actual data
            processed_content = template_content
            for column, value in row_data.items():
                placeholder = f"{{{{{column}}}}}"
                processed_content = processed_content.replace(placeholder, str(value))
            
            # Create output directory if it doesn't exist
            os.makedirs(self.output_dir, exist_ok=True)
            
            # Generate output filename if not provided
            if not output_filename:
                base_name = os.path.splitext(os.path.basename(template_path))[0]
                safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', str(row_data.get('Name', 'Unknown')))
                # Keep original extension for output
                template_ext = os.path.splitext(template_path)[1]
                output_filename = f"{base_name}_{safe_name}{template_ext}"
            
            output_path = os.path.join(self.output_dir, output_filename)
            
            # Write processed content
            with open(output_path, 'w', encoding='utf-8') as file:
                file.write(processed_content)
                
            return output_path
            
        except Exception as e:
            print(f"Error processing template {template_path}: {e}")
            return None
    
    def process_all_templates(self):
        """Process all template files for all employees"""
        if self.data is None:
            print("No data loaded. Cannot process templates.")
            return []
            
        # Create template directory if it doesn't exist
        if not os.path.exists(self.template_dir):
            print(f"Template directory '{self.template_dir}' does not exist. Creating it...")
            os.makedirs(self.template_dir, exist_ok=True)
            print(f"Please place your template files (ending with '.docx') in the '{self.template_dir}' directory.")
            return []
            
        # Find all template files
        template_files = [f for f in os.listdir(self.template_dir) 
                         if f.endswith('.txt') or f.endswith('.docx')]
        
        if not template_files:
            print(f"No .txt or .docx template files found in '{self.template_dir}' directory")
            return []
        
        print(f"Found {len(template_files)} template files")
        
        results = []
        
        for template_file in template_files:
            template_path = os.path.join(self.template_dir, template_file)
            print(f"\nProcessing template: {template_file}")
            
            for index, row in self.data.iterrows():
                row_dict = row.to_dict()
                output_file = self.process_template(template_path, row_dict)
                if output_file:
                    results.append({
                        'template': template_file,
                        'employee': row_dict.get('Name', 'Unknown'),
                        'output': output_file
                    })
                    print(f"  Generated: {output_file}")
        
        return results
    
    def generate_summary_report(self, results):
        """Generate a summary report of processed documents"""
        summary_path = os.path.join(self.output_dir, "processing_summary.txt")
        
        with open(summary_path, 'w') as f:
            f.write("MAIL MERGE PROCESSING SUMMARY\n")
            f.write("=" * 40 + "\n\n")
            f.write(f"Processing Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total Documents Generated: {len(results)}\n\n")
            
            # Group by template
            templates = {}
            for result in results:
                template = result['template']
                if template not in templates:
                    templates[template] = []
                templates[template].append(result)
            
            for template, template_results in templates.items():
                f.write(f"Template: {template}\n")
                f.write(f"Documents Generated: {len(template_results)}\n")
                for result in template_results:
                    f.write(f"  - {result['employee']}: {result['output']}\n")
                f.write("\n")
        
        print(f"Summary report generated: {summary_path}")
        return summary_path

def main():
    # Initialize processor with new folder structure
    processor = MailMergeProcessor(
        data_file="data/test_data.csv",
        template_dir="templates", 
        output_dir="generated_docs"
    )
    
    # Process all templates
    results = processor.process_all_templates()
    
    if results:
        # Generate summary
        processor.generate_summary_report(results)
        print(f"\nProcessing complete! Check the '{processor.output_dir}' directory for generated documents.")
    else:
        print("No documents were processed.")
        print(f"Make sure you have:")
        print(f"1. Data file: {processor.data_file}")
        print(f"2. Template files in: {processor.template_dir}/")
        print(f"3. Template files should end with '.txt' or '.docx'")

if __name__ == "__main__":
    main()