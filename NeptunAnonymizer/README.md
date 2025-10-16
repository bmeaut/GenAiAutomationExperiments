# Neptun Code Anonymizer

A VBA macro for Excel that anonymizes Neptun student codes using SHA-1 hashing with a salt value. This tool ensures consistent anonymization across multiple worksheets when using the same salt.

## Features

- **Automatic Column Detection**: Intelligently detects Neptun code columns based on:
  - Header names (searches for keywords like "NEPTUN", "CODE", "KÓD", "ID")
  - Cell value patterns (validates 6-character alphanumeric format)
- **Pre-selection Support**: Automatically uses already selected ranges
- **SHA-1 Hashing**: Generates secure, deterministic anonymized codes
- **Consistent Results**: Same salt + same Neptun code = same anonymized code
- **Two Operating Modes**: Range-based or column-based anonymization
- **User-Friendly**: Interactive prompts with smart defaults

## How It Works

The macro generates anonymized codes by:
1. Combining a user-provided salt value with each Neptun code
2. Computing the SHA-1 hash of the combined string
3. Taking the first 6 characters of the hash (uppercase)
4. Formatting cells as text to preserve hex values

## Usage

### Method 1: AnonymizeNeptunCodes (Recommended)

This method offers the most flexible workflow with automatic detection:

1. **Option A - Use Pre-selected Range**:
   - Select the range containing Neptun codes
   - Run the macro `AnonymizeNeptunCodes`
   - Confirm you want to use the selected range
   - Enter your salt value

2. **Option B - Auto-detect Column**:
   - Simply place your cursor anywhere on the worksheet
   - Run the macro `AnonymizeNeptunCodes`
   - The macro will automatically detect the Neptun column
   - Confirm the detected range or choose manual selection
   - Enter your salt value

3. **Option C - Manual Selection**:
   - Run the macro `AnonymizeNeptunCodes`
   - Decline auto-detected range (or if none found)
   - Manually select the range when prompted
   - Enter your salt value

### Method 2: AnonymizeColumn

For column-based processing with auto-detection:

1. Run the macro `AnonymizeColumn`
2. Enter your salt value
3. The macro will auto-detect the Neptun column (if found)
4. Confirm the detected column or enter manually
5. Specify the starting row (typically 2 to skip headers)

## Auto-Detection Algorithm

The macro scores each column based on:
- **Header keywords** (+100 for "NEPTUN", +50 for "CODE"/"KÓD"/"ID")
- **Value patterns** (+10 per valid Neptun code found in first 10 rows)
- **Neptun code format**: Exactly 6 uppercase alphanumeric characters

The column with the highest score (minimum 10 points) is suggested.

## Important Notes

- **Salt Consistency**: Use the **same salt value** across all worksheets to ensure the same Neptun code is anonymized identically
- **Security**: Keep your salt value confidential and secure
- **Backup**: Always work on a copy of your data
- **Text Formatting**: Cells are automatically formatted as text to prevent Excel from converting hex values to numbers
- **Validation**: The macro validates Neptun code format (6 alphanumeric characters)

## Example

Original Neptun Code: `ABC123`  
Salt Value: `mySecretSalt2024`  
Result: First 6 characters of SHA-1 hash of `mySecretSalt2024ABC123`

Using the same salt on another worksheet:
- `ABC123` → Same anonymized code
- `XYZ789` → Different anonymized code

## Installation

### Manual Installation

1. Open your Excel workbook
2. Press `Alt + F11` to open VBA Editor
3. Go to `Insert` → `Module`
4. Copy and paste the code from `NeptunAnonymizer.bas`
5. Close VBA Editor
6. Run the macro from `Developer` → `Macros` or assign to a button

### Automated Installation (Batch Processing)

Use the Python script to automatically add the macro to multiple Excel files:

#### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

#### 2. Enable VBA Project Access (One-time setup)

- Open Excel
- Go to `File` → `Options` → `Trust Center` → `Trust Center Settings`
- Click `Macro Settings`
- Check "Trust access to the VBA project object model"
- Click OK

#### 3. Run the script

**Command Line Usage:**

```bash
# View help and usage information
python add_macro_to_excel.py --help
```

```bash
# Process files in current directory, output to 'output' folder
python add_macro_to_excel.py . output
```

```bash
# Process files in current directory with default VBA file
python add_macro_to_excel.py . output NeptunAnonymizer.bas
```

```bash
# Process specific input folder
python add_macro_to_excel.py input output
```

```bash
# Process with custom VBA macro file
python add_macro_to_excel.py input output custom_macro.bas
```

```bash
# Use GUI folder pickers (no arguments)
python add_macro_to_excel.py
```

**Arguments:**

- `input_dir` - Directory containing Excel files to process (`.` for current directory, optional - uses GUI picker if not provided)
- `output_dir` - Directory for output .xlsm files (optional - uses GUI picker if not provided)
- `vba_file` - Path to VBA macro file (optional, defaults to `NeptunAnonymizer.bas`)

**Options:**

- `--help`, `-h` - Show help message and exit
- `--version` - Show version information

#### 4. Directory Structure

```
NeptunAnonymizer/
├── NeptunAnonymizer.bas        # VBA macro code
├── add_macro_to_excel.py       # Python automation script
├── requirements.txt            # Python dependencies
├── input/                      # Place your Excel files here (optional)
│   └── data.xlsx
└── output/                     # Processed files saved here (created automatically)
    └── data.xlsm
```

#### 5. What the Script Does

- Scans input directory for all Excel files (.xlsx, .xls, .xlsm, .xlsb)
- Adds the NeptunAnonymizer macro to each workbook
- Saves files as macro-enabled .xlsm format in output directory
- Preserves directory structure for nested folders
- Removes and replaces existing macro if already present
- Provides detailed progress and error reporting

## Requirements

### For VBA Macro
- Microsoft Excel (Windows)
- Macros must be enabled
- .NET Framework (for SHA-1 cryptography provider)

### For Python Script
- Python 3.6 or higher
- pywin32 package
- Windows operating system (for COM automation)

## Troubleshooting

### VBA Project Access Error

If you get an error about VBA project access:
1. Open Excel
2. File → Options → Trust Center → Trust Center Settings
3. Macro Settings → Check "Trust access to the VBA project object model"

### Script Can't Find Default VBA File

If the script can't find `NeptunAnonymizer.bas`:
- Ensure the file is in the same directory as the Python script
- Or specify the full path as the third argument

### Excel Files Not Processing

- Ensure Excel files are not open in another program
- Check that you have write permissions to the output directory
- Verify Excel is properly installed with COM support

## License

This tool is provided as-is for educational and administrative purposes.