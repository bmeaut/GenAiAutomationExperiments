"""
Excel Macro Injector for Neptun Anonymizer
Scans a directory for Excel files and adds the NeptunAnonymizer macro to each file.
Saves the files as .xlsm (macro-enabled) format in an output directory.
"""

import os
import sys
import shutil
import argparse
from pathlib import Path
import win32com.client
from win32com.client import constants
import tkinter as tk
from tkinter import filedialog

def select_folder(title, initial_dir=None):
    """Show folder picker dialog"""
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    root.attributes('-topmost', True)  # Bring dialog to front
    
    folder_path = filedialog.askdirectory(
        title=title,
        initialdir=initial_dir
    )
    
    root.destroy()
    return folder_path

def select_file(title, initial_dir=None, filetypes=None):
    """Show file picker dialog"""
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    
    if filetypes is None:
        filetypes = [("VBA Files", "*.bas"), ("All Files", "*.*")]
    
    file_path = filedialog.askopenfilename(
        title=title,
        initialdir=initial_dir,
        filetypes=filetypes
    )
    
    root.destroy()
    return file_path

def read_vba_code(vba_file_path):
    """Read VBA code from .bas file"""
    try:
        with open(vba_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        # Try with different encoding if UTF-8 fails
        with open(vba_file_path, 'r', encoding='latin-1') as f:
            content = f.read()
    
    # Remove VBA export attributes (Attribute lines)
    # These cause syntax errors when added via AddFromString
    lines = content.split('\n')
    cleaned_lines = []
    for line in lines:
        # Skip lines starting with "Attribute" (case-insensitive)
        if not line.strip().upper().startswith('ATTRIBUTE '):
            cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines)

def add_macro_to_workbook(excel_app, workbook_path, vba_code, output_path):
    """Add VBA macro to an Excel workbook"""
    try:
        # Open workbook
        wb = excel_app.Workbooks.Open(workbook_path)
        
        # Access VBA project
        vb_project = wb.VBProject
        
        # Check if module already exists
        module_name = "NeptunAnonymizer"
        module_exists = False
        
        for component in vb_project.VBComponents:
            if component.Name == module_name:
                print(f"  - Module '{module_name}' already exists, removing old version...")
                vb_project.VBComponents.Remove(component)
                break
        
        # Add new module
        vb_module = vb_project.VBComponents.Add(1)  # 1 = vbext_ct_StdModule
        vb_module.Name = module_name
        
        # Add code to module
        vb_module.CodeModule.AddFromString(vba_code)
        
        # Save as macro-enabled workbook (.xlsm)
        wb.SaveAs(output_path, FileFormat=52)  # 52 = xlOpenXMLWorkbookMacroEnabled
        wb.Close(SaveChanges=True)
        
        return True
    except Exception as e:
        print(f"  ERROR: {str(e)}")
        try:
            wb.Close(SaveChanges=False)
        except:
            pass
        return False

def process_directory(input_dir, output_dir, vba_file_path):
    """Process all Excel files in the input directory"""
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Read VBA code
    print(f"Reading VBA code from: {vba_file_path}")
    vba_code = read_vba_code(vba_file_path)
    print(f"VBA code loaded successfully ({len(vba_code)} characters)\n")
    
    # Initialize Excel application
    print("Initializing Excel application...")
    excel_app = win32com.client.Dispatch("Excel.Application")
    excel_app.Visible = False
    excel_app.DisplayAlerts = False
    
    # Enable VBA project access (must be enabled in Excel Trust Center)
    try:
        excel_app.VBE.MainWindow.Visible = False
    except:
        print("WARNING: VBA project access might be restricted.")
        print("Please enable 'Trust access to the VBA project object model' in Excel Trust Center.\n")
    
    # Supported Excel extensions
    excel_extensions = ['.xlsx', '.xls', '.xlsm', '.xlsb']
    
    # Normalize paths for comparison
    input_path = Path(input_dir).resolve()
    output_path = Path(output_dir).resolve()
    
    # Find all Excel files, excluding the output directory
    excel_files = []
    for ext in excel_extensions:
        for file in input_path.glob(f'**/*{ext}'):
            # Skip files in the output directory
            try:
                if not file.resolve().is_relative_to(output_path):
                    excel_files.append(file)
            except (ValueError, AttributeError):
                # For Python < 3.9, use alternative method
                try:
                    file.resolve().relative_to(output_path)
                    # If no error, file is in output dir, skip it
                except ValueError:
                    # File is not in output dir, include it
                    excel_files.append(file)
    
    if not excel_files:
        print(f"No Excel files found in: {input_dir}")
        excel_app.Quit()
        return
    
    print(f"Found {len(excel_files)} Excel file(s) to process:\n")
    
    # Process each file
    success_count = 0
    failed_count = 0
    
    for excel_file in excel_files:
        rel_path = excel_file.relative_to(input_path)
        output_file = output_path / rel_path.with_suffix('.xlsm')
        
        # Create subdirectories in output if needed
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        print(f"Processing: {rel_path}")
        print(f"  Output: {output_file.name}")
        
        if add_macro_to_workbook(excel_app, str(excel_file.absolute()), vba_code, str(output_file.absolute())):
            print(f"  ✓ SUCCESS\n")
            success_count += 1
        else:
            print(f"  ✗ FAILED\n")
            failed_count += 1
    
    # Cleanup
    excel_app.Quit()
    
    # Summary
    print("=" * 60)
    print(f"Processing complete!")
    print(f"  Successful: {success_count}")
    print(f"  Failed: {failed_count}")
    print(f"  Output directory: {output_dir}")
    print("=" * 60)

def main():
    """Main entry point"""
    
    # Get script directory
    script_dir = Path(__file__).parent
    
    # Default VBA file path
    default_vba = script_dir / "NeptunAnonymizer.bas"
    
    # Setup argument parser
    parser = argparse.ArgumentParser(
        description='Excel Macro Injector - Adds Neptun Anonymizer macro to Excel files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=''':
Examples:
  %(prog)s . output                                      # Process current directory
  %(prog)s . output NeptunAnonymizer.bas                 # Specify VBA file
  %(prog)s input output                                  # Process 'input' folder
  %(prog)s                                                # Use GUI folder pickers
        '''
    )
    
    parser.add_argument(
        'input_dir',
        nargs='?',
        help='Input directory containing Excel files (.xlsx, .xls, .xlsm, .xlsb)'
    )
    
    parser.add_argument(
        'output_dir',
        nargs='?',
        help='Output directory for processed .xlsm files'
    )
    
    parser.add_argument(
        'vba_file',
        nargs='?',
        default=str(default_vba) if default_vba.exists() else None,
        help=f'Path to VBA macro file (.bas) (default: {default_vba.name})'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version='%(prog)s 1.0'
    )
    
    args = parser.parse_args()
    
    # Get input directory from args or folder picker
    if args.input_dir:
        input_dir = args.input_dir
    else:
        print("Select input directory containing Excel files...")
        input_dir = select_folder(
            "Select Input Directory (Excel files)",
            initial_dir=str(script_dir)
        )
        if not input_dir:
            print("ERROR: No input directory selected. Exiting.")
            return
    
    # Get output directory from args or folder picker
    if args.output_dir:
        output_dir = args.output_dir
    else:
        print("Select output directory for processed files...")
        output_dir = select_folder(
            "Select Output Directory (for .xlsm files)",
            initial_dir=str(script_dir)
        )
        if not output_dir:
            print("ERROR: No output directory selected. Exiting.")
            return
    
    # Get VBA file from args or file picker
    if args.vba_file:
        vba_file = args.vba_file
    else:
        print("Select VBA macro file...")
        vba_file = select_file(
            "Select VBA Macro File (.bas)",
            initial_dir=str(script_dir),
            filetypes=[("VBA Files", "*.bas"), ("All Files", "*.*")]
        )
        if not vba_file:
            print("ERROR: No VBA file selected. Exiting.")
            return
    
    # Validate paths
    if not os.path.exists(input_dir):
        print(f"ERROR: Input directory not found: {input_dir}")
        return
    
    if not os.path.exists(vba_file):
        print(f"ERROR: VBA file not found: {vba_file}")
        return
    
    print("\n" + "=" * 60)
    print("Excel Macro Injector - Neptun Anonymizer")
    print("=" * 60)
    print(f"Input directory:  {input_dir}")
    print(f"Output directory: {output_dir}")
    print(f"VBA macro file:   {vba_file}")
    print("=" * 60 + "\n")
    
    # Process files
    process_directory(input_dir, output_dir, vba_file)

if __name__ == "__main__":
    main()
