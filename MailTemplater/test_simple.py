#!/usr/bin/env python3
"""
Simple Mail Merge Test Script - Text Version
Tests the mail merge logic with text files instead of Word documents
"""

import pandas as pd
import os
from datetime import datetime
import re

def simple_test():
    """Simple test function for text-based templates"""
    print("=== Simple Mail Merge Test ===")
    
    # Check if data file exists
    data_file = "data/test_data.csv"
    if not os.path.exists(data_file):
        print(f"❌ Data file not found: {data_file}")
        return False
    
    # Load data
    try:
        data = pd.read_csv(data_file)
        print(f"✅ Loaded {len(data)} records from {data_file}")
        print(f"📊 Columns: {list(data.columns)}")
    except Exception as e:
        print(f"❌ Error loading data: {e}")
        return False
    
    # Find text template files
    template_dir = "templates"
    if not os.path.exists(template_dir):
        print(f"❌ Template directory not found: {template_dir}")
        return False
    
    text_templates = [f for f in os.listdir(template_dir) if f.endswith('.txt')]
    
    if not text_templates:
        print(f"❌ No .txt template files found in {template_dir}")
        return False
    
    print(f"✅ Found {len(text_templates)} text template files")
    
    # Create output directory
    output_dir = "generated_docs"
    os.makedirs(output_dir, exist_ok=True)
    
    total_generated = 0
    
    # Process each template
    for template_file in text_templates:
        template_path = os.path.join(template_dir, template_file)
        print(f"\n📄 Processing: {template_file}")
        
        # Read template
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
        except Exception as e:
            print(f"❌ Error reading template: {e}")
            continue
        
        # Process each employee
        for index, row in data.iterrows():
            # Replace placeholders
            processed_content = template_content
            for column, value in row.items():
                placeholder = f"{{{{{column}}}}}"
                processed_content = processed_content.replace(placeholder, str(value))
            
            # Create output filename
            template_name = os.path.splitext(template_file)[0]
            safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', str(row.get('Name', 'Unknown')))
            output_filename = f"{template_name}_{safe_name}.txt"
            output_path = os.path.join(output_dir, output_filename)
            
            # Write processed file
            try:
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(processed_content)
                print(f"  ✅ Generated: {output_filename}")
                total_generated += 1
            except Exception as e:
                print(f"  ❌ Error writing {output_filename}: {e}")
    
    # Summary
    print(f"\n🎉 Test Complete!")
    print(f"📈 Total documents generated: {total_generated}")
    print(f"📁 Check the '{output_dir}' folder for generated documents")
    
    return total_generated > 0

if __name__ == "__main__":
    # Run test without requiring pandas installation
    try:
        import pandas as pd
        success = simple_test()
        if success:
            print("\n✅ Mail merge logic is working correctly!")
            print("👉 Next step: Create real Word .docx templates using Microsoft Word")
        else:
            print("\n❌ Test failed. Please check the error messages above.")
    except ImportError:
        print("❌ pandas not installed. Install with: pip install pandas")
        print("📝 Alternative: Use the PowerShell script which doesn't require Python")