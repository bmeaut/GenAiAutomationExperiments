
leventebajak:

> It would better if the macro could detect which column contains Neptun codes, either based on the Column name or the values.
>

GitHub Copilot:

> I'll modify the code to add automatic Neptun code column detection. Here's the solution:
>
> ## Step-by-step approach:
> 1. Add a function to detect Neptun code columns by checking header names and cell value patterns
> 2. Modify the `AnonymizeColumn` subroutine to automatically detect the column
> 3. Add validation to check if values match Neptun code pattern (6 alphanumeric characters)
> 4. Allow user to confirm or override the auto-detected column
>
> ### [NeptunAnonymizer.bas](file:///d%3A/School/BME/MSc/2025-26-1/Onlab2/GenAiAutomationExperiments/NeptunAnonymizer/NeptunAnonymizer.bas)
>
> Add automatic Neptun code column detection based on header names and value patterns.
>
> ````vb
> Attribute VB_Name = "NeptunAnonymizer"
> Option Explicit
> 
> ' ...existing code...
> 
> ' Function to detect if a string matches Neptun code pattern
> Private Function IsNeptunCode(ByVal value As String) As Boolean
>     Dim trimmedValue As String
>     trimmedValue = Trim(value)
>     
>     ' Neptun code is exactly 6 alphanumeric characters
>     If Len(trimmedValue) = 6 Then
>         Dim i As Integer
>         For i = 1 To 6
>             Dim char As String
>             char = Mid(trimmedValue, i, 1)
>             If Not ((char >= "A" And char <= "Z") Or (char >= "0" And char <= "9")) Then
>                 IsNeptunCode = False
>                 Exit Function
>             End If
>         Next i
>         IsNeptunCode = True
>     Else
>         IsNeptunCode = False
>     End If
> End Function
> 
> ' Function to detect column containing Neptun codes
> Private Function DetectNeptunColumn(ByVal ws As Worksheet) As String
>     Dim col As Long
>     Dim lastCol As Long
>     Dim headerValue As String
>     Dim matchScore As Long
>     Dim bestColumn As Long
>     Dim bestScore As Long
>     Dim sampleRows As Long
>     Dim neptunCount As Long
>     
>     bestScore = 0
>     bestColumn = 0
>     lastCol = ws.Cells(1, ws.Columns.Count).End(xlToLeft).Column
>     
>     ' Check each column
>     For col = 1 To lastCol
>         matchScore = 0
>         headerValue = UCase(Trim(CStr(ws.Cells(1, col).Value)))
>         
>         ' Check header name for Neptun-related keywords
>         If InStr(headerValue, "NEPTUN") > 0 Then
>             matchScore = matchScore + 100
>         ElseIf InStr(headerValue, "CODE") > 0 Or InStr(headerValue, "KOD") > 0 Or InStr(headerValue, "ID") > 0 Then
>             matchScore = matchScore + 50
>         End If
>         
>         ' Check cell values in first 10 rows (or less if fewer rows exist)
>         sampleRows = Application.Min(10, ws.Cells(ws.Rows.Count, col).End(xlUp).Row - 1)
>         neptunCount = 0
>         
>         Dim row As Long
>         For row = 2 To sampleRows + 1
>             If Not IsEmpty(ws.Cells(row, col).Value) Then
>                 If IsNeptunCode(CStr(ws.Cells(row, col).Value)) Then
>                     neptunCount = neptunCount + 1
>                 End If
>             End If
>         Next row
>         
>         ' Add score based on percentage of Neptun-like codes
>         If sampleRows > 0 Then
>             matchScore = matchScore + (neptunCount * 10)
>         End If
>         
>         ' Update best match
>         If matchScore > bestScore Then
>             bestScore = matchScore
>             bestColumn = col
>         End If
>     Next col
>     
>     ' Return column letter if found
>     If bestColumn > 0 And bestScore >= 10 Then
>         DetectNeptunColumn = Split(ws.Cells(1, bestColumn).Address, "$")(1)
>     Else
>         DetectNeptunColumn = ""
>     End If
> End Function
> 
> ' ...existing code...
> 
> ' Subroutine to anonymize entire column (alternative method)
> Sub AnonymizeColumn()
>     Dim saltValue As String
>     Dim ws As Worksheet
>     Dim lastRow As Long
>     Dim columnLetter As String
>     Dim targetColumn As Range
>     Dim detectedColumn As String
>     
>     ' Get active worksheet
>     Set ws = ActiveSheet
>     
>     ' Prompt user for salt value
>     saltValue = InputBox("Enter salt value for anonymization:" & vbCrLf & _
>                         "(Use the same salt for all worksheets to maintain compatibility)", _
>                         "Neptun Code Anonymization")
>     
>     ' Check if user cancelled or entered empty salt
>     If saltValue = "" Then
>         MsgBox "Anonymization cancelled. Salt value is required.", vbExclamation, "Cancelled"
>         Exit Sub
>     End If
>     
>     ' Try to auto-detect Neptun column
>     detectedColumn = DetectNeptunColumn(ws)
>     
>     ' Prompt for column letter with auto-detected suggestion
>     If detectedColumn <> "" Then
>         columnLetter = InputBox("Neptun column detected: " & detectedColumn & vbCrLf & vbCrLf & _
>                                "Enter the column letter containing Neptun codes" & vbCrLf & _
>                                "(or press OK to use detected column):", _
>                                "Column Selection", detectedColumn)
>     Else
>         columnLetter = InputBox("Enter the column letter containing Neptun codes (e.g., A, B, C):", _
>                                "Column Selection")
>     End If
>     
>     ' ...existing code...
> End Sub
> ````
>
> The changes include:
>
> 1. **`IsNeptunCode` function**: Validates if a string matches the Neptun code pattern (exactly 6 alphanumeric uppercase characters)
>
> 2. **`DetectNeptunColumn` function**: Automatically detects the column containing Neptun codes by:
     >     - Checking header names for keywords like "NEPTUN", "CODE", "KOD", "ID"
>     - Sampling the first 10 data rows to check if values match Neptun code pattern
>     - Scoring each column and returning the best match
>
> 3. **Modified `AnonymizeColumn`**: Now auto-detects the Neptun column and suggests it to the user, while still allowing manual override
>
> Made changes.
>

leventebajak:

> If a range is already selected, use that instead
>

GitHub Copilot:

> I'll modify the `AnonymizeNeptunCodes` subroutine to use an already selected range if one exists, and add the same auto-detection capability to it.
>
> ### [NeptunAnonymizer.bas](file:///d%3A/School/BME/MSc/2025-26-1/Onlab2/GenAiAutomationExperiments/NeptunAnonymizer/NeptunAnonymizer.bas)
>
> Modify to use pre-selected range and add auto-detection for Neptun columns.
>
> ````vb
> ' ...existing code...
> 
> ' Main subroutine to anonymize Neptun codes in selected column
> Sub AnonymizeNeptunCodes()
>     Dim saltValue As String
>     Dim selectedRange As Range
>     Dim cell As Range
>     Dim originalCode As String
>     Dim anonymizedCode As String
>     Dim processedCount As Long
>     Dim detectedColumn As String
>     Dim ws As Worksheet
>     
>     Set ws = ActiveSheet
>     
>     ' Prompt user for salt value
>     saltValue = InputBox("Enter salt value for anonymization:" & vbCrLf & _
>                         "(Use the same salt for all worksheets to maintain compatibility)", _
>                         "Neptun Code Anonymization")
>     
>     ' Check if user cancelled or entered empty salt
>     If saltValue = "" Then
>         MsgBox "Anonymization cancelled. Salt value is required.", vbExclamation, "Cancelled"
>         Exit Sub
>     End If
>     
>     ' Check if a range is already selected
>     If Not Selection Is Nothing Then
>         If TypeName(Selection) = "Range" Then
>             If Selection.Cells.Count > 0 And Not IsEmpty(Selection.Cells(1, 1).Value) Then
>                 ' Ask user if they want to use the current selection
>                 Dim useSelection As VbMsgBoxResult
>                 useSelection = MsgBox("Use currently selected range?" & vbCrLf & _
>                                     Selection.Address, vbYesNo + vbQuestion, "Use Selection?")
>                 If useSelection = vbYes Then
>                     Set selectedRange = Selection
>                 End If
>             End If
>         End If
>     End If
>     
>     ' If no range selected or user chose not to use it, try auto-detection or prompt
>     If selectedRange Is Nothing Then
>         detectedColumn = DetectNeptunColumn(ws)
>         
>         If detectedColumn <> "" Then
>             Dim lastRow As Long
>             lastRow = ws.Cells(ws.Rows.Count, detectedColumn).End(xlUp).Row
>             
>             Dim useDetected As VbMsgBoxResult
>             useDetected = MsgBox("Neptun column detected: " & detectedColumn & vbCrLf & _
>                                "Range: " & detectedColumn & "2:" & detectedColumn & lastRow & vbCrLf & vbCrLf & _
>                                "Use this range?", vbYesNo + vbQuestion, "Auto-Detected Range")
>             
>             If useDetected = vbYes Then
>                 Set selectedRange = ws.Range(detectedColumn & "2:" & detectedColumn & lastRow)
>             End If
>         End If
>     End If
>     
>     ' If still no range, prompt user to select manually
>     If selectedRange Is Nothing Then
>         On Error Resume Next
>         Set selectedRange = Application.InputBox("Select the range containing Neptun codes:", _
>                                                 "Select Range", _
>                                                 Type:=8)
>         On Error GoTo 0
>         
>         ' Check if user cancelled selection
>         If selectedRange Is Nothing Then
>             MsgBox "No range selected. Operation cancelled.", vbInformation, "Cancelled"
>             Exit Sub
>         End If
>     End If
>     
>     ' Disable screen updating for better performance
>     Application.ScreenUpdating = False
>     Application.Calculation = xlCalculationManual
>     
>     ' Format the entire range as Text to prevent Excel from converting hex to numbers
>     selectedRange.NumberFormat = "@"
>     
>     processedCount = 0
>     
>     ' Process each cell in the selected range
>     For Each cell In selectedRange
>         If Not IsEmpty(cell.Value) Then
>             originalCode = Trim(CStr(cell.Value))
>             
>             ' Only process if cell contains text (potential Neptun code)
>             If Len(originalCode) > 0 Then
>                 anonymizedCode = GenerateAnonymizedCode(saltValue, originalCode)
>                 cell.Value = anonymizedCode
>                 processedCount = processedCount + 1
>             End If
>         End If
>     Next cell
>     
>     ' Re-enable screen updating
>     Application.Calculation = xlCalculationAutomatic
>     Application.ScreenUpdating = True
>     
>     ' Show completion message
>     MsgBox "Anonymization complete!" & vbCrLf & _
>            "Processed " & processedCount & " codes.", _
>            vbInformation, "Complete"
> End Sub
> 
> ' ...existing code...
> ````
>
> The changes now make `AnonymizeNeptunCodes` work in this priority order:
>
> 1. **Use pre-selected range** - If cells are already selected, ask user to confirm
> 2. **Auto-detect Neptun column** - If no selection, detect column and suggest the range
> 3. **Manual selection** - If auto-detection fails or is declined, prompt user to select manually
>
> This makes the workflow more efficient by respecting existing selections and providing smart defaults.
>
> Made changes.
>

leventebajak:

> Great! Modify the readme accordingly.
>

GitHub Copilot:

> I'll update the README to reflect the new auto-detection features and workflow improvements.
>
> ### [README.md](file:///d%3A/School/BME/MSc/2025-26-1/Onlab2/GenAiAutomationExperiments/NeptunAnonymizer/README.md)
>
> Update documentation to describe the auto-detection feature and improved workflow.
>
> ````markdown
> # Neptun Code Anonymizer
> 
> A VBA macro for Excel that anonymizes Neptun student codes using SHA-1 hashing with a salt value. This tool ensures consistent anonymization across multiple worksheets when using the same salt.
> 
> ## Features
> 
> - **Automatic Column Detection**: Intelligently detects Neptun code columns based on:
>   - Header names (searches for keywords like "NEPTUN", "CODE", "KÓD", "ID")
>   - Cell value patterns (validates 6-character alphanumeric format)
> - **Pre-selection Support**: Automatically uses already selected ranges
> - **SHA-1 Hashing**: Generates secure, deterministic anonymized codes
> - **Consistent Results**: Same salt + same Neptun code = same anonymized code
> - **Two Operating Modes**: Range-based or column-based anonymization
> - **User-Friendly**: Interactive prompts with smart defaults
> 
> ## How It Works
> 
> The macro generates anonymized codes by:
> 1. Combining a user-provided salt value with each Neptun code
> 2. Computing the SHA-1 hash of the combined string
> 3. Taking the first 6 characters of the hash (uppercase)
> 4. Formatting cells as text to preserve hex values
> 
> ## Usage
> 
> ### Method 1: AnonymizeNeptunCodes (Recommended)
> 
> This method offers the most flexible workflow with automatic detection:
> 
> 1. **Option A - Use Pre-selected Range**:
>    - Select the range containing Neptun codes
>    - Run the macro `AnonymizeNeptunCodes`
>    - Confirm you want to use the selected range
>    - Enter your salt value
> 
> 2. **Option B - Auto-detect Column**:
>    - Simply place your cursor anywhere on the worksheet
>    - Run the macro `AnonymizeNeptunCodes`
>    - The macro will automatically detect the Neptun column
>    - Confirm the detected range or choose manual selection
>    - Enter your salt value
> 
> 3. **Option C - Manual Selection**:
>    - Run the macro `AnonymizeNeptunCodes`
>    - Decline auto-detected range (or if none found)
>    - Manually select the range when prompted
>    - Enter your salt value
> 
> ### Method 2: AnonymizeColumn
> 
> For column-based processing with auto-detection:
> 
> 1. Run the macro `AnonymizeColumn`
> 2. Enter your salt value
> 3. The macro will auto-detect the Neptun column (if found)
> 4. Confirm the detected column or enter manually
> 5. Specify the starting row (typically 2 to skip headers)
> 
> ## Auto-Detection Algorithm
> 
> The macro scores each column based on:
> - **Header keywords** (+100 for "NEPTUN", +50 for "CODE"/"KÓD"/"ID")
> - **Value patterns** (+10 per valid Neptun code found in first 10 rows)
> - **Neptun code format**: Exactly 6 uppercase alphanumeric characters
> 
> The column with the highest score (minimum 10 points) is suggested.
> 
> ## Important Notes
> 
> - **Salt Consistency**: Use the **same salt value** across all worksheets to ensure the same Neptun code is anonymized identically
> - **Security**: Keep your salt value confidential and secure
> - **Backup**: Always work on a copy of your data
> - **Text Formatting**: Cells are automatically formatted as text to prevent Excel from converting hex values to numbers
> - **Validation**: The macro validates Neptun code format (6 alphanumeric characters)
> 
> ## Example
> 
> Original Neptun Code: `ABC123`  
> Salt Value: `mySecretSalt2024`  
> Result: First 6 characters of SHA-1 hash of `mySecretSalt2024ABC123`
> 
> Using the same salt on another worksheet:
> - `ABC123` → Same anonymized code
> - `XYZ789` → Different anonymized code
> 
> ## Installation
> 
> 1. Open your Excel workbook
> 2. Press `Alt + F11` to open VBA Editor
> 3. Go to `Insert` → `Module`
> 4. Copy and paste the code from `NeptunAnonymizer.bas`
> 5. Close VBA Editor
> 6. Run the macro from `Developer` → `Macros` or assign to a button
> 
> ## Requirements
> 
> - Microsoft Excel (Windows)
> - Macros must be enabled
> - .NET Framework (for SHA-1 cryptography provider)
> 
> ## License
> 
> This tool is provided as-is for educational and administrative purposes.
> ````
>
> Made changes.
>

leventebajak:

> Now make a python script that scans a directory and add the macro to all excel sheets and saves them as xlsm in the output folder.
>

GitHub Copilot:

> I'll create a Python script that scans a directory, adds the VBA macro to all Excel files, and saves them as .xlsm files in an output folder.
>
> [add_macro_to_excel.py](./add_macro_to_excel.py)
>
> Create a Python script to automatically add the Neptun Anonymizer macro to all Excel files in a directory.
>
> ````python
> """
> Excel Macro Injector for Neptun Anonymizer
> Scans a directory for Excel files and adds the NeptunAnonymizer macro to each file.
> Saves the files as .xlsm (macro-enabled) format in an output directory.
> """
> 
> import os
> import sys
> import shutil
> from pathlib import Path
> import win32com.client
> from win32com.client import constants
> 
> def read_vba_code(vba_file_path):
>     """Read VBA code from .bas file"""
>     try:
>         with open(vba_file_path, 'r', encoding='utf-8') as f:
>             return f.read()
>     except UnicodeDecodeError:
>         # Try with different encoding if UTF-8 fails
>         with open(vba_file_path, 'r', encoding='latin-1') as f:
>             return f.read()
> 
> def add_macro_to_workbook(excel_app, workbook_path, vba_code, output_path):
>     """Add VBA macro to an Excel workbook"""
>     try:
>         # Open workbook
>         wb = excel_app.Workbooks.Open(workbook_path)
>         
>         # Access VBA project
>         vb_project = wb.VBProject
>         
>         # Check if module already exists
>         module_name = "NeptunAnonymizer"
>         module_exists = False
>         
>         for component in vb_project.VBComponents:
>             if component.Name == module_name:
>                 print(f"  - Module '{module_name}' already exists, removing old version...")
>                 vb_project.VBComponents.Remove(component)
>                 break
>         
>         # Add new module
>         vb_module = vb_project.VBComponents.Add(1)  # 1 = vbext_ct_StdModule
>         vb_module.Name = module_name
>         
>         # Add code to module
>         vb_module.CodeModule.AddFromString(vba_code)
>         
>         # Save as macro-enabled workbook (.xlsm)
>         wb.SaveAs(output_path, FileFormat=52)  # 52 = xlOpenXMLWorkbookMacroEnabled
>         wb.Close(SaveChanges=True)
>         
>         return True
>     except Exception as e:
>         print(f"  ERROR: {str(e)}")
>         try:
>             wb.Close(SaveChanges=False)
>         except:
>             pass
>         return False
> 
> def process_directory(input_dir, output_dir, vba_file_path):
>     """Process all Excel files in the input directory"""
>     
>     # Create output directory if it doesn't exist
>     os.makedirs(output_dir, exist_ok=True)
>     
>     # Read VBA code
>     print(f"Reading VBA code from: {vba_file_path}")
>     vba_code = read_vba_code(vba_file_path)
>     print(f"VBA code loaded successfully ({len(vba_code)} characters)\n")
>     
>     # Initialize Excel application
>     print("Initializing Excel application...")
>     excel_app = win32com.client.Dispatch("Excel.Application")
>     excel_app.Visible = False
>     excel_app.DisplayAlerts = False
>     
>     # Enable VBA project access (must be enabled in Excel Trust Center)
>     try:
>         excel_app.VBE.MainWindow.Visible = False
>     except:
>         print("WARNING: VBA project access might be restricted.")
>         print("Please enable 'Trust access to the VBA project object model' in Excel Trust Center.\n")
>     
>     # Supported Excel extensions
>     excel_extensions = ['.xlsx', '.xls', '.xlsm', '.xlsb']
>     
>     # Find all Excel files
>     excel_files = []
>     for ext in excel_extensions:
>         excel_files.extend(Path(input_dir).glob(f'**/*{ext}'))
>     
>     if not excel_files:
>         print(f"No Excel files found in: {input_dir}")
>         excel_app.Quit()
>         return
>     
>     print(f"Found {len(excel_files)} Excel file(s) to process:\n")
>     
>     # Process each file
>     success_count = 0
>     failed_count = 0
>     
>     for excel_file in excel_files:
>         rel_path = excel_file.relative_to(input_dir)
>         output_file = Path(output_dir) / rel_path.with_suffix('.xlsm')
>         
>         # Create subdirectories in output if needed
>         output_file.parent.mkdir(parents=True, exist_ok=True)
>         
>         print(f"Processing: {rel_path}")
>         print(f"  Output: {output_file.name}")
>         
>         if add_macro_to_workbook(excel_app, str(excel_file.absolute()), vba_code, str(output_file.absolute())):
>             print(f"  ✓ SUCCESS\n")
>             success_count += 1
>         else:
>             print(f"  ✗ FAILED\n")
>             failed_count += 1
>     
>     # Cleanup
>     excel_app.Quit()
>     
>     # Summary
>     print("=" * 60)
>     print(f"Processing complete!")
>     print(f"  Successful: {success_count}")
>     print(f"  Failed: {failed_count}")
>     print(f"  Output directory: {output_dir}")
>     print("=" * 60)
> 
> def main():
>     """Main entry point"""
>     
>     # Get script directory
>     script_dir = Path(__file__).parent
>     
>     # Default paths
>     default_input = script_dir / "input"
>     default_output = script_dir / "output"
>     default_vba = script_dir / "NeptunAnonymizer.bas"
>     
>     # Parse command line arguments or use defaults
>     if len(sys.argv) > 1:
>         input_dir = sys.argv[1]
>     else:
>         input_dir = input("Enter input directory (or press Enter for default 'input' folder): ").strip()
>         if not input_dir:
>             input_dir = str(default_input)
>     
>     if len(sys.argv) > 2:
>         output_dir = sys.argv[2]
>     else:
>         output_dir = input("Enter output directory (or press Enter for default 'output' folder): ").strip()
>         if not output_dir:
>             output_dir = str(default_output)
>     
>     if len(sys.argv) > 3:
>         vba_file = sys.argv[3]
>     else:
>         vba_file = str(default_vba)
>     
>     # Validate paths
>     if not os.path.exists(input_dir):
>         print(f"ERROR: Input directory not found: {input_dir}")
>         return
>     
>     if not os.path.exists(vba_file):
>         print(f"ERROR: VBA file not found: {vba_file}")
>         return
>     
>     print("\n" + "=" * 60)
>     print("Excel Macro Injector - Neptun Anonymizer")
>     print("=" * 60)
>     print(f"Input directory:  {input_dir}")
>     print(f"Output directory: {output_dir}")
>     print(f"VBA macro file:   {vba_file}")
>     print("=" * 60 + "\n")
>     
>     # Process files
>     process_directory(input_dir, output_dir, vba_file)
> 
> if __name__ == "__main__":
>     main()
> ````
>
> ### [requirements.txt](file:///d%3A/School/BME/MSc/2025-26-1/Onlab2/GenAiAutomationExperiments/NeptunAnonymizer/requirements.txt)
>
> Create requirements file for Python dependencies.
>
> ````text
> pywin32>=305
> ````
>
> ### [README.md](file:///d%3A/School/BME/MSc/2025-26-1/Onlab2/GenAiAutomationExperiments/NeptunAnonymizer/README.md)
>
> Update README with Python script usage instructions.
>
> ````markdown
> // ...existing code...
> 
> ## Installation
> 
> ### Manual Installation
> 
> 1. Open your Excel workbook
> 2. Press `Alt + F11` to open VBA Editor
> 3. Go to `Insert` → `Module`
> 4. Copy and paste the code from `NeptunAnonymizer.bas`
> 5. Close VBA Editor
> 6. Run the macro from `Developer` → `Macros` or assign to a button
> 
> ### Automated Installation (Batch Processing)
> 
> Use the Python script to automatically add the macro to multiple Excel files:
> 
> 1. **Install Python dependencies**:
>    ```bash
>    pip install -r requirements.txt
>    ```
> 
> 2. **Enable VBA Project Access** (One-time setup):
>    - Open Excel
>    - Go to `File` → `Options` → `Trust Center` → `Trust Center Settings`
>    - Click `Macro Settings`
>    - Check "Trust access to the VBA project object model"
>    - Click OK
> 
> 3. **Run the script**:
>    ```bash
>    python add_macro_to_excel.py [input_dir] [output_dir]
>    ```
>    
>    Or simply run without arguments to use default folders:
>    ```bash
>    python add_macro_to_excel.py
>    ```
>    
>    - Default input directory: `./input`
>    - Default output directory: `./output`
>    - The script will process all Excel files (.xlsx, .xls, .xlsm, .xlsb) in the input directory
>    - Output files are saved as `.xlsm` (macro-enabled) format
> 
> 4. **Directory Structure**:
>    ```
>    NeptunAnonymizer/
>    ├── NeptunAnonymizer.bas
>    ├── add_macro_to_excel.py
>    ├── requirements.txt
>    ├── input/              # Place your Excel files here
>    │   └── data.xlsx
>    └── output/             # Processed files will be saved here
>        └── data.xlsm
>    ```
> 
> // ...existing code...
> ````
>
> The Python script:
> - Scans the input directory for all Excel files (supports .xlsx, .xls, .xlsm, .xlsb)
> - Adds the NeptunAnonymizer macro to each file
> - Saves them as macro-enabled .xlsm files in the output directory
> - Preserves directory structure if processing nested folders
> - Provides detailed progress and error reporting
> - Requires pywin32 for Excel COM automation
>
> Made changes.
>

leventebajak:

> Take the paths from the command line arguments, or if they are not provided, whoq a folder picker window
>

GitHub Copilot:

> I'll modify the script to use a folder picker dialog when command line arguments are not provided.
>
> [add_macro_to_excel.py](./add_macro_to_excel.py)
>
> Add GUI folder picker functionality when command line arguments are not provided.
>
> ````python
> """
> Excel Macro Injector for Neptun Anonymizer
> Scans a directory for Excel files and adds the NeptunAnonymizer macro to each file.
> Saves the files as .xlsm (macro-enabled) format in an output directory.
> """
> 
> import os
> import sys
> import shutil
> from pathlib import Path
> import win32com.client
> from win32com.client import constants
> import tkinter as tk
> from tkinter import filedialog
> 
> def select_folder(title, initial_dir=None):
>     """Show folder picker dialog"""
>     root = tk.Tk()
>     root.withdraw()  # Hide the main window
>     root.attributes('-topmost', True)  # Bring dialog to front
>     
>     folder_path = filedialog.askdirectory(
>         title=title,
>         initialdir=initial_dir
>     )
>     
>     root.destroy()
>     return folder_path
> 
> def select_file(title, initial_dir=None, filetypes=None):
>     """Show file picker dialog"""
>     root = tk.Tk()
>     root.withdraw()
>     root.attributes('-topmost', True)
>     
>     if filetypes is None:
>         filetypes = [("VBA Files", "*.bas"), ("All Files", "*.*")]
>     
>     file_path = filedialog.askopenfilename(
>         title=title,
>         initialdir=initial_dir,
>         filetypes=filetypes
>     )
>     
>     root.destroy()
>     return file_path
> 
> // ...existing code...
> 
> def main():
>     """Main entry point"""
>     
>     # Get script directory
>     script_dir = Path(__file__).parent
>     
>     # Default paths
>     default_input = script_dir / "input"
>     default_output = script_dir / "output"
>     default_vba = script_dir / "NeptunAnonymizer.bas"
>     
>     # Parse command line arguments or use folder picker
>     if len(sys.argv) > 1:
>         input_dir = sys.argv[1]
>     else:
>         print("Select input directory containing Excel files...")
>         input_dir = select_folder(
>             "Select Input Directory (Excel files)",
>             initial_dir=str(default_input) if default_input.exists() else str(script_dir)
>         )
>         if not input_dir:
>             print("ERROR: No input directory selected. Exiting.")
>             return
>     
>     if len(sys.argv) > 2:
>         output_dir = sys.argv[2]
>     else:
>         print("Select output directory for processed files...")
>         output_dir = select_folder(
>             "Select Output Directory (for .xlsm files)",
>             initial_dir=str(default_output) if default_output.exists() else str(script_dir)
>         )
>         if not output_dir:
>             print("ERROR: No output directory selected. Exiting.")
>             return
>     
>     if len(sys.argv) > 3:
>         vba_file = sys.argv[3]
>     else:
>         print("Select VBA macro file...")
>         vba_file = select_file(
>             "Select VBA Macro File (.bas)",
>             initial_dir=str(script_dir),
>             filetypes=[("VBA Files", "*.bas"), ("All Files", "*.*")]
>         )
>         if not vba_file:
>             # Try default if user cancels
>             if default_vba.exists():
>                 vba_file = str(default_vba)
>                 print(f"Using default VBA file: {vba_file}")
>             else:
>                 print("ERROR: No VBA file selected. Exiting.")
>                 return
>     
>     # Validate paths
>     if not os.path.exists(input_dir):
>         print(f"ERROR: Input directory not found: {input_dir}")
>         return
>     
>     if not os.path.exists(vba_file):
>         print(f"ERROR: VBA file not found: {vba_file}")
>         return
>     
>     print("\n" + "=" * 60)
>     print("Excel Macro Injector - Neptun Anonymizer")
>     print("=" * 60)
>     print(f"Input directory:  {input_dir}")
>     print(f"Output directory: {output_dir}")
>     print(f"VBA macro file:   {vba_file}")
>     print("=" * 60 + "\n")
>     
>     # Process files
>     process_directory(input_dir, output_dir, vba_file)
> 
> if __name__ == "__main__":
>     main()
> ````
>
> The script now uses tkinter's folder/file picker dialogs when command line arguments are not provided, making it more user-friendly while still supporting command-line automation.
>
> Made changes.
>

leventebajak:

> I said Take the paths from the command line arguments by default
>

GitHub Copilot:

> I'll fix the logic to prioritize command line arguments and only show the folder picker when arguments are not provided.
>
> [add_macro_to_excel.py](./add_macro_to_excel.py)
>
> Fix the command line argument handling to use arguments by default, folder picker as fallback.
>
> ````python
> // ...existing code...
> 
> def main():
>     """Main entry point"""
>     
>     # Get script directory
>     script_dir = Path(__file__).parent
>     
>     # Default paths
>     default_vba = script_dir / "NeptunAnonymizer.bas"
>     
>     # Get input directory from command line or folder picker
>     if len(sys.argv) > 1:
>         input_dir = sys.argv[1]
>     else:
>         print("Select input directory containing Excel files...")
>         input_dir = select_folder(
>             "Select Input Directory (Excel files)",
>             initial_dir=str(script_dir)
>         )
>         if not input_dir:
>             print("ERROR: No input directory selected. Exiting.")
>             return
>     
>     # Get output directory from command line or folder picker
>     if len(sys.argv) > 2:
>         output_dir = sys.argv[2]
>     else:
>         print("Select output directory for processed files...")
>         output_dir = select_folder(
>             "Select Output Directory (for .xlsm files)",
>             initial_dir=str(script_dir)
>         )
>         if not output_dir:
>             print("ERROR: No output directory selected. Exiting.")
>             return
>     
>     # Get VBA file from command line or file picker
>     if len(sys.argv) > 3:
>         vba_file = sys.argv[3]
>     else:
>         if default_vba.exists():
>             vba_file = str(default_vba)
>             print(f"Using default VBA file: {vba_file}")
>         else:
>             print("Select VBA macro file...")
>             vba_file = select_file(
>                 "Select VBA Macro File (.bas)",
>                 initial_dir=str(script_dir),
>                 filetypes=[("VBA Files", "*.bas"), ("All Files", "*.*")]
>             )
>             if not vba_file:
>                 print("ERROR: No VBA file selected. Exiting.")
>                 return
>     
>     # ...existing code...
> ````
>
> Now the script properly uses command line arguments when provided, and only shows the folder/file picker dialogs when arguments are missing.
>
> Made changes.
>

leventebajak:

> Use argparse
>

GitHub Copilot:

> I'll refactor the script to use argparse for better command line argument handling.
>
> [add_macro_to_excel.py](./add_macro_to_excel.py)
>
> Replace command line argument handling with argparse for better usability.
>
> ````python
> """
> Excel Macro Injector for Neptun Anonymizer
> Scans a directory for Excel files and adds the NeptunAnonymizer macro to each file.
> Saves the files as .xlsm (macro-enabled) format in an output directory.
> """
> 
> import os
> import sys
> import shutil
> import argparse
> from pathlib import Path
> import win32com.client
> from win32com.client import constants
> import tkinter as tk
> from tkinter import filedialog
> 
> // ...existing code...
> 
> def main():
>     """Main entry point"""
>     
>     # Get script directory
>     script_dir = Path(__file__).parent
>     
>     # Default VBA file path
>     default_vba = script_dir / "NeptunAnonymizer.bas"
>     
>     # Setup argument parser
>     parser = argparse.ArgumentParser(
>         description='Excel Macro Injector - Adds Neptun Anonymizer macro to Excel files',
>         formatter_class=argparse.RawDescriptionHelpFormatter,
>         epilog='''
> Examples:
>   %(prog)s input_folder output_folder                    # Use specified directories
>   %(prog)s input_folder output_folder my_macro.bas       # Specify custom VBA file
>   %(prog)s                                                # Use GUI folder pickers
>         '''
>     )
>     
>     parser.add_argument(
>         'input_dir',
>         nargs='?',
>         help='Input directory containing Excel files (.xlsx, .xls, .xlsm, .xlsb)'
>     )
>     
>     parser.add_argument(
>         'output_dir',
>         nargs='?',
>         help='Output directory for processed .xlsm files'
>     )
>     
>     parser.add_argument(
>         'vba_file',
>         nargs='?',
>         default=str(default_vba) if default_vba.exists() else None,
>         help=f'Path to VBA macro file (.bas) (default: {default_vba.name})'
>     )
>     
>     parser.add_argument(
>         '--version',
>         action='version',
>         version='%(prog)s 1.0'
>     )
>     
>     args = parser.parse_args()
>     
>     # Get input directory from args or folder picker
>     if args.input_dir:
>         input_dir = args.input_dir
>     else:
>         print("Select input directory containing Excel files...")
>         input_dir = select_folder(
>             "Select Input Directory (Excel files)",
>             initial_dir=str(script_dir)
>         )
>         if not input_dir:
>             print("ERROR: No input directory selected. Exiting.")
>             return
>     
>     # Get output directory from args or folder picker
>     if args.output_dir:
>         output_dir = args.output_dir
>     else:
>         print("Select output directory for processed files...")
>         output_dir = select_folder(
>             "Select Output Directory (for .xlsm files)",
>             initial_dir=str(script_dir)
>         )
>         if not output_dir:
>             print("ERROR: No output directory selected. Exiting.")
>             return
>     
>     # Get VBA file from args or file picker
>     if args.vba_file:
>         vba_file = args.vba_file
>     else:
>         print("Select VBA macro file...")
>         vba_file = select_file(
>             "Select VBA Macro File (.bas)",
>             initial_dir=str(script_dir),
>             filetypes=[("VBA Files", "*.bas"), ("All Files", "*.*")]
>         )
>         if not vba_file:
>             print("ERROR: No VBA file selected. Exiting.")
>             return
>     
>     # Validate paths
>     if not os.path.exists(input_dir):
>         print(f"ERROR: Input directory not found: {input_dir}")
>         return
>     
>     if not os.path.exists(vba_file):
>         print(f"ERROR: VBA file not found: {vba_file}")
>         return
>     
>     print("\n" + "=" * 60)
>     print("Excel Macro Injector - Neptun Anonymizer")
>     print("=" * 60)
>     print(f"Input directory:  {input_dir}")
>     print(f"Output directory: {output_dir}")
>     print(f"VBA macro file:   {vba_file}")
>     print("=" * 60 + "\n")
>     
>     # Process files
>     process_directory(input_dir, output_dir, vba_file)
> 
> if __name__ == "__main__":
>     main()
> ````
>
> Now the script uses argparse which provides:
> - Better help message with `--help` or `-h`
> - Version information with `--version`
> - Clear argument descriptions
> - Proper usage examples
> - Maintains backward compatibility with GUI folder pickers when arguments are not provided
>
> Made changes.
>

leventebajak:

> Update readme
>

GitHub Copilot:

> ### [README.md](file:///d%3A/School/BME/MSc/2025-26-1/Onlab2/GenAiAutomationExperiments/NeptunAnonymizer/README.md)
>
> Update README with argparse usage examples and improved documentation.
>
> ````markdown
> # Neptun Code Anonymizer
> 
> A VBA macro for Excel that anonymizes Neptun student codes using SHA-1 hashing with a salt value. This tool ensures consistent anonymization across multiple worksheets when using the same salt.
> 
> ## Features
> 
> - **Automatic Column Detection**: Intelligently detects Neptun code columns based on:
>   - Header names (searches for keywords like "NEPTUN", "CODE", "KÓD", "ID")
>   - Cell value patterns (validates 6-character alphanumeric format)
> - **Pre-selection Support**: Automatically uses already selected ranges
> - **SHA-1 Hashing**: Generates secure, deterministic anonymized codes
> - **Consistent Results**: Same salt + same Neptun code = same anonymized code
> - **Two Operating Modes**: Range-based or column-based anonymization
> - **User-Friendly**: Interactive prompts with smart defaults
> 
> ## How It Works
> 
> The macro generates anonymized codes by:
> 1. Combining a user-provided salt value with each Neptun code
> 2. Computing the SHA-1 hash of the combined string
> 3. Taking the first 6 characters of the hash (uppercase)
> 4. Formatting cells as text to preserve hex values
> 
> ## Usage
> 
> ### Method 1: AnonymizeNeptunCodes (Recommended)
> 
> This method offers the most flexible workflow with automatic detection:
> 
> 1. **Option A - Use Pre-selected Range**:
>    - Select the range containing Neptun codes
>    - Run the macro `AnonymizeNeptunCodes`
>    - Confirm you want to use the selected range
>    - Enter your salt value
> 
> 2. **Option B - Auto-detect Column**:
>    - Simply place your cursor anywhere on the worksheet
>    - Run the macro `AnonymizeNeptunCodes`
>    - The macro will automatically detect the Neptun column
>    - Confirm the detected range or choose manual selection
>    - Enter your salt value
> 
> 3. **Option C - Manual Selection**:
>    - Run the macro `AnonymizeNeptunCodes`
>    - Decline auto-detected range (or if none found)
>    - Manually select the range when prompted
>    - Enter your salt value
> 
> ### Method 2: AnonymizeColumn
> 
> For column-based processing with auto-detection:
> 
> 1. Run the macro `AnonymizeColumn`
> 2. Enter your salt value
> 3. The macro will auto-detect the Neptun column (if found)
> 4. Confirm the detected column or enter manually
> 5. Specify the starting row (typically 2 to skip headers)
> 
> ## Auto-Detection Algorithm
> 
> The macro scores each column based on:
> - **Header keywords** (+100 for "NEPTUN", +50 for "CODE"/"KÓD"/"ID")
> - **Value patterns** (+10 per valid Neptun code found in first 10 rows)
> - **Neptun code format**: Exactly 6 uppercase alphanumeric characters
> 
> The column with the highest score (minimum 10 points) is suggested.
> 
> ## Important Notes
> 
> - **Salt Consistency**: Use the **same salt value** across all worksheets to ensure the same Neptun code is anonymized identically
> - **Security**: Keep your salt value confidential and secure
> - **Backup**: Always work on a copy of your data
> - **Text Formatting**: Cells are automatically formatted as text to prevent Excel from converting hex values to numbers
> - **Validation**: The macro validates Neptun code format (6 alphanumeric characters)
> 
> ## Example
> 
> Original Neptun Code: `ABC123`  
> Salt Value: `mySecretSalt2024`  
> Result: First 6 characters of SHA-1 hash of `mySecretSalt2024ABC123`
> 
> Using the same salt on another worksheet:
> - `ABC123` → Same anonymized code
> - `XYZ789` → Different anonymized code
> 
> ## Installation
> 
> ### Manual Installation
> 
> 1. Open your Excel workbook
> 2. Press `Alt + F11` to open VBA Editor
> 3. Go to `Insert` → `Module`
> 4. Copy and paste the code from `NeptunAnonymizer.bas`
> 5. Close VBA Editor
> 6. Run the macro from `Developer` → `Macros` or assign to a button
> 
> ### Automated Installation (Batch Processing)
> 
> Use the Python script to automatically add the macro to multiple Excel files:
> 
> #### 1. Install Python dependencies
> 
> ```bash
> pip install -r requirements.txt
> ```
> 
> #### 2. Enable VBA Project Access (One-time setup)
> 
> - Open Excel
> - Go to `File` → `Options` → `Trust Center` → `Trust Center Settings`
> - Click `Macro Settings`
> - Check "Trust access to the VBA project object model"
> - Click OK
> 
> #### 3. Run the script
> 
> **Command Line Usage:**
> 
> ```bash
> # View help and usage information
> python add_macro_to_excel.py --help
> 
> # Process with command line arguments
> python add_macro_to_excel.py input_folder output_folder
> 
> # Specify custom VBA file
> python add_macro_to_excel.py input_folder output_folder custom_macro.bas
> 
> # Use GUI folder pickers (no arguments)
> python add_macro_to_excel.py
> ```
> 
> **Arguments:**
> 
> - `input_dir` - Directory containing Excel files to process (optional, uses GUI picker if not provided)
> - `output_dir` - Directory for output .xlsm files (optional, uses GUI picker if not provided)
> - `vba_file` - Path to VBA macro file (optional, defaults to `NeptunAnonymizer.bas`)
> 
> **Options:**
> 
> - `--help`, `-h` - Show help message and exit
> - `--version` - Show version information
> 
> #### 4. Directory Structure
> 
> ```
> NeptunAnonymizer/
> ├── NeptunAnonymizer.bas        # VBA macro code
> ├── add_macro_to_excel.py       # Python automation script
> ├── requirements.txt            # Python dependencies
> ├── input/                      # Place your Excel files here (optional)
> │   └── data.xlsx
> └── output/                     # Processed files saved here (created automatically)
>     └── data.xlsm
> ```
> 
> #### 5. What the Script Does
> 
> - Scans input directory for all Excel files (.xlsx, .xls, .xlsm, .xlsb)
> - Adds the NeptunAnonymizer macro to each workbook
> - Saves files as macro-enabled .xlsm format in output directory
> - Preserves directory structure for nested folders
> - Removes and replaces existing macro if already present
> - Provides detailed progress and error reporting
> 
> ## Requirements
> 
> ### For VBA Macro
> - Microsoft Excel (Windows)
> - Macros must be enabled
> - .NET Framework (for SHA-1 cryptography provider)
> 
> ### For Python Script
> - Python 3.6 or higher
> - pywin32 package
> - Windows operating system (for COM automation)
> 
> ## Troubleshooting
> 
> ### VBA Project Access Error
> 
> If you get an error about VBA project access:
> 1. Open Excel
> 2. File → Options → Trust Center → Trust Center Settings
> 3. Macro Settings → Check "Trust access to the VBA project object model"
> 
> ### Script Can't Find Default VBA File
> 
> If the script can't find `NeptunAnonymizer.bas`:
> - Ensure the file is in the same directory as the Python script
> - Or specify the full path as the third argument
> 
> ### Excel Files Not Processing
> 
> - Ensure Excel files are not open in another program
> - Check that you have write permissions to the output directory
> - Verify Excel is properly installed with COM support
> 
> ## License
> 
> This tool is provided as-is for educational and administrative purposes.
> ````
>
> Made changes.
>

leventebajak:

> Make the examples runnable and use arguments like input=., output=output, vba=NeptunAnonymizer.bas
>

GitHub Copilot:

> ### [README.md](file:///d%3A/School/BME/MSc/2025-26-1/Onlab2/GenAiAutomationExperiments/NeptunAnonymizer/README.md)
>
> Update README with practical, runnable examples using current directory syntax.
>
> ````markdown
> // ...existing code...
> 
> #### 3. Run the script
> 
> **Command Line Usage:**
> 
> ```bash
> # View help and usage information
> python add_macro_to_excel.py --help
> 
> # Process files in current directory, output to 'output' folder
> python add_macro_to_excel.py . output
> 
> # Process files in current directory with default VBA file
> python add_macro_to_excel.py . output NeptunAnonymizer.bas
> 
> # Process specific input folder
> python add_macro_to_excel.py input output
> 
> # Process with custom VBA macro file
> python add_macro_to_excel.py input output custom_macro.bas
> 
> # Use GUI folder pickers (no arguments)
> python add_macro_to_excel.py
> ```
> 
> **Practical Examples:**
> 
> ```bash
> # Example 1: Process Excel files in current directory
> python add_macro_to_excel.py . output
> 
> # Example 2: Process files from 'data' folder
> python add_macro_to_excel.py data processed
> 
> # Example 3: Use absolute paths
> python add_macro_to_excel.py "C:\Users\YourName\Documents\ExcelFiles" "C:\Users\YourName\Documents\Output"
> 
> # Example 4: Process with custom macro
> python add_macro_to_excel.py . output MyCustomMacro.bas
> ```
> 
> **Arguments:**
> 
> - `input_dir` - Directory containing Excel files to process (`.` for current directory, optional - uses GUI picker if not provided)
> - `output_dir` - Directory for output .xlsm files (optional - uses GUI picker if not provided)
> - `vba_file` - Path to VBA macro file (optional, defaults to `NeptunAnonymizer.bas`)
> 
> **Options:**
> 
> - `--help`, `-h` - Show help message and exit
> - `--version` - Show version information
> 
> // ...existing code...
> ````
>
> [add_macro_to_excel.py](./add_macro_to_excel.py)
>
> Update the examples in the argparse epilog to match the README.
>
> ````python
> ````python
> // ...existing code...
> 
>     # Setup argument parser
>     parser = argparse.ArgumentParser(
>         description='Excel Macro Injector - Adds Neptun Anonymizer macro to Excel files',
>         formatter_class=argparse.RawDescriptionHelpFormatter,
>         epilog='''
> Examples:
>   %(prog)s . output                                      # Process current directory
>   %(prog)s . output NeptunAnonymizer.bas                 # Specify VBA file
>   %(prog)s input output                                  # Process 'input' folder
>   %(prog)s                                                # Use GUI folder pickers
>         '''
>     )
>     
> // ...existing code...
> ````
>
> Made changes.
>

leventebajak:

> When opening an xlsm file:
> Compile error: Syntax error
>
> Attribute VB_Name = "NeptunAnonymizer"
>

GitHub Copilot:

> The issue is that the `.bas` file contains metadata attributes that shouldn't be included when adding code via `AddFromString`. I'll fix the script to strip out these VBA export attributes.
>
> [add_macro_to_excel.py](./add_macro_to_excel.py)
>
> Strip VBA export attributes from the code before adding to workbook.
>
> ````python
> // ...existing code...
> 
> def read_vba_code(vba_file_path):
>     """Read VBA code from .bas file"""
>     try:
>         with open(vba_file_path, 'r', encoding='utf-8') as f:
>             content = f.read()
>     except UnicodeDecodeError:
>         # Try with different encoding if UTF-8 fails
>         with open(vba_file_path, 'r', encoding='latin-1') as f:
>             content = f.read()
>     
>     # Remove VBA export attributes (Attribute lines)
>     # These cause syntax errors when added via AddFromString
>     lines = content.split('\n')
>     cleaned_lines = []
>     for line in lines:
>         # Skip lines starting with "Attribute" (case-insensitive)
>         if not line.strip().upper().startswith('ATTRIBUTE '):
>             cleaned_lines.append(line)
>     
>     return '\n'.join(cleaned_lines)
> 
> // ...existing code...
> ````
>
> The problem occurs because `.bas` export files contain metadata like `Attribute VB_Name = "NeptunAnonymizer"` that are only valid in exported files, not when programmatically adding code. The fix strips these attribute lines before injecting the code into the workbook.
>
> Made changes.
>

leventebajak:

> Found 2 Excel file(s) to process:
>
> Processing: TestNeptunCodes.xlsx
> Output: TestNeptunCodes.xlsm
> ✓ SUCCESS
>
> Processing: output\TestNeptunCodes.xlsm
> Output: TestNeptunCodes.xlsm
> - Module 'NeptunAnonymizer' already exists, removing old version...
    >   ✓ SUCCESS
>
> Do not search in the output folder
>

GitHub Copilot:

> I'll modify the script to exclude the output directory from the search to prevent reprocessing already-processed files.
>
> [add_macro_to_excel.py](./add_macro_to_excel.py)
>
> Exclude output directory from input file search to prevent reprocessing.
>
> ````python
> // ...existing code...
> 
> def process_directory(input_dir, output_dir, vba_file_path):
>     """Process all Excel files in the input directory"""
>     
>     # Create output directory if it doesn't exist
>     os.makedirs(output_dir, exist_ok=True)
>     
>     # Read VBA code
>     print(f"Reading VBA code from: {vba_file_path}")
>     vba_code = read_vba_code(vba_file_path)
>     print(f"VBA code loaded successfully ({len(vba_code)} characters)\n")
>     
>     # Initialize Excel application
>     print("Initializing Excel application...")
>     excel_app = win32com.client.Dispatch("Excel.Application")
>     excel_app.Visible = False
>     excel_app.DisplayAlerts = False
>     
>     # Enable VBA project access (must be enabled in Excel Trust Center)
>     try:
>         excel_app.VBE.MainWindow.Visible = False
>     except:
>         print("WARNING: VBA project access might be restricted.")
>         print("Please enable 'Trust access to the VBA project object model' in Excel Trust Center.\n")
>     
>     # Supported Excel extensions
>     excel_extensions = ['.xlsx', '.xls', '.xlsm', '.xlsb']
>     
>     # Normalize paths for comparison
>     input_path = Path(input_dir).resolve()
>     output_path = Path(output_dir).resolve()
>     
>     # Find all Excel files, excluding the output directory
>     excel_files = []
>     for ext in excel_extensions:
>         for file in input_path.glob(f'**/*{ext}'):
>             # Skip files in the output directory
>             try:
>                 if not file.resolve().is_relative_to(output_path):
>                     excel_files.append(file)
>             except (ValueError, AttributeError):
>                 # For Python < 3.9, use alternative method
>                 try:
>                     file.resolve().relative_to(output_path)
>                     # If no error, file is in output dir, skip it
>                 except ValueError:
>                     # File is not in output dir, include it
>                     excel_files.append(file)
>     
>     if not excel_files:
>         print(f"No Excel files found in: {input_dir}")
>         excel_app.Quit()
>         return
>     
>     print(f"Found {len(excel_files)} Excel file(s) to process:\n")
>     
>     # Process each file
>     success_count = 0
>     failed_count = 0
>     
>     for excel_file in excel_files:
>         rel_path = excel_file.relative_to(input_path)
>         output_file = output_path / rel_path.with_suffix('.xlsm')
>         
>         # Create subdirectories in output if needed
>         output_file.parent.mkdir(parents=True, exist_ok=True)
>         
>         print(f"Processing: {rel_path}")
>         print(f"  Output: {output_file.name}")
>         
>         if add_macro_to_workbook(excel_app, str(excel_file.absolute()), vba_code, str(output_file.absolute())):
>             print(f"  ✓ SUCCESS\n")
>             success_count += 1
>         else:
>             print(f"  ✗ FAILED\n")
>             failed_count += 1
>     
>     # Cleanup
>     excel_app.Quit()
>     
>     # Summary
>     print("=" * 60)
>     print(f"Processing complete!")
>     print(f"  Successful: {success_count}")
>     print(f"  Failed: {failed_count}")
>     print(f"  Output directory: {output_dir}")
>     print("=" * 60)
> 
> // ...existing code...
> ````
>
> The script now:
> 1. Resolves both input and output paths to absolute paths
> 2. Checks if each found Excel file is within the output directory
> 3. Skips files that are in the output directory to prevent reprocessing
> 4. Supports both Python 3.9+ (`is_relative_to`) and older versions (try/except with `relative_to`)
>
> Made changes.