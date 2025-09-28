# Mail Templater - Automated Document Generation

This project**Usage:**
```powershell
# Basic usage
.\mail_merge_automation.ps1

# With custom parameters
.\mail_merge_automation.ps1 -DataFile "data/custom_data.csv" -TemplateDir "my_templates" -OutputDir "my_output" -TemplatePattern "*.docx"
```s automated mail merge functionality to generate personalized documents from Excel/CSV data using Word templates.

## 📁 Project Structure

```
MailTemplater/
├── data/
│   └── test_data.csv                # Sample employee data
├── templates/
│   ├── test_document.docx           # Welcome letter template
│   ├── performance_review_template.docx # Performance review template
│   ├── salary_adjustment_template.docx  # Salary adjustment template
│   └── birthday_template.docx       # Birthday wishes template
├── generated_docs/                  # Output folder (auto-created)
├── mail_merge_automation.py         # Python automation script
├── mail_merge_vba.bas              # VBA macro for Word
├── mail_merge_automation.ps1        # PowerShell automation script
└── README.md                       # This file
```

## 🎯 Template Fields

All templates use these custom fields that correspond to Excel columns:

- `{{Name}}` - Employee full name
- `{{Email}}` - Employee email address
- `{{Department}}` - Department name
- `{{Position}}` - Job position/title
- `{{Salary}}` - Salary amount
- `{{Start Date}}` - Employment start date

## 📊 Data Format

The Excel/CSV file should be placed in the `data/` folder and have these column headers:
```csv
Name,Email,Department,Position,Salary,Start Date
John Smith,john.smith@company.com,Engineering,Software Developer,75000,2023-01-15
```

## 🚀 Usage Methods

### Method 1: Python Script (Recommended)

**Prerequisites:**
- Python 3.6+
- pandas library: `pip install pandas`

**Usage:**
```bash
python mail_merge_automation.py
```

**Features:**
- Cross-platform compatibility
- Automatic template discovery
- Batch processing
- Summary report generation
- Error handling

### Method 2: PowerShell Script (Windows)

**Prerequisites:**
- Windows PowerShell
- Microsoft Word installed

**Usage:**
```powershell
# Basic usage
.\\mail_merge_automation.ps1

# With custom parameters
.\\mail_merge_automation.ps1 -DataFile "custom_data.csv" -OutputDir "my_output" -TemplatePattern "*.docx"
```

**Features:**
- Native Windows COM automation
- Real Word document processing
- Preserves formatting
- Batch processing

### Method 3: VBA Macro (Word)

**Prerequisites:**
- Microsoft Word with macro support enabled

**Usage:**
1. Open Microsoft Word
2. Press `Alt + F11` to open VBA editor
3. Insert > Module
4. Copy and paste the VBA code from `mail_merge_vba.bas`
5. Run the `AutoFillTemplateFromExcel` macro

**Features:**
- Native Word integration
- Direct document manipulation
- Preserves all Word formatting
- Interactive processing

## 📋 Template Creation Guide

### 1. Custom Field Syntax
Use double curly braces: `{{FieldName}}`

### 2. Example Template Structure
```
DOCUMENT TITLE

Dear {{Name}},

Your information:
- Email: {{Email}}
- Department: {{Department}}
- Position: {{Position}}
- Salary: ${{Salary}}
- Start Date: {{Start Date}}

Best regards,
Management
```

### 3. Naming and Location
Save templates in the `templates/` folder with `.docx` extension:
- `templates/welcome_template.docx`
- `templates/review_template.docx`
- `templates/promotion_template.docx`

## 🔧 Configuration

### Python Script Configuration
Edit variables in `mail_merge_automation.py`:
```python
data_file = "test_data.csv"          # Input CSV file
output_dir = "generated_docs"        # Output directory
```

### PowerShell Script Parameters
```powershell
-DataFile "data.csv"                 # Input data file
-OutputDir "output"                  # Output directory
-TemplatePattern "*_template.docx"   # Template file pattern
```

### VBA Macro Configuration
Edit constants in the VBA code:
```vba
Const EXCEL_FILE_PATH = "test_data.csv"
Const OUTPUT_FOLDER = "generated_docs\\"
```

## 📤 Output

All methods generate:
- Individual documents for each employee
- Organized in output directory
- Named: `{template}_{employee_name}.docx`
- Processing summary report

### Example Output Structure
```
generated_docs/
├── test_document_John_Smith.docx
├── test_document_Jane_Doe.docx
├── performance_review_template_John_Smith.docx
├── salary_adjustment_template_Jane_Doe.docx
└── processing_summary.txt
```

## 🎨 Template Examples

### 1. Welcome Letter (`test_document.docx`)
- Employee onboarding
- Basic information display
- Formal welcome message

### 2. Performance Review (`performance_review_template.docx`)
- Review notifications
- Employee details summary
- Professional communication

### 3. Salary Adjustment (`salary_adjustment_template.docx`)
- Confidential salary communications
- Current and new salary information
- Management notifications

### 4. Birthday Template (`birthday_template.docx`)
- Casual employee recognition
- Department-specific messages
- Celebration communications

## 🔍 Troubleshooting

### Common Issues

**Python Script:**
- Install pandas: `pip install pandas`
- Check file paths are correct
- Ensure CSV has proper headers

**PowerShell Script:**
- Enable execution policy: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`
- Ensure Word is installed and accessible
- Check COM object permissions

**VBA Macro:**
- Enable macros in Word security settings
- Trust the document location
- Verify Excel file access permissions

### Field Not Replacing
- Check field name spelling in template
- Verify column header in CSV matches exactly
- Ensure proper `{{FieldName}}` syntax

### File Access Errors
- Close all Word documents before running
- Check file permissions
- Ensure output directory is writable

## 🚀 Advanced Usage

### Batch Processing Multiple Data Files
```bash
# Python
for file in *.csv; do python mail_merge_automation.py "$file"; done

# PowerShell
Get-ChildItem *.csv | ForEach-Object { .\\mail_merge_automation.ps1 -DataFile $_.Name }
```

### Custom Template Processing
Create templates with specific naming patterns and modify the scripts to process them selectively.

### Integration with Other Systems
The Python script can be easily integrated into larger automation workflows or called from other applications.

## 📈 Performance Tips

- Use CSV instead of Excel for better performance
- Process templates in smaller batches for large datasets
- Close unnecessary applications when running COM-based scripts
- Use SSD storage for faster file I/O

## 🔒 Security Considerations

- Review VBA macros before enabling
- Validate input data for malicious content
- Use trusted document locations
- Consider running scripts in isolated environments

## 📝 License

This project is provided as-is for educational and automation purposes.

---

**Created:** September 28, 2025  
**Last Updated:** September 28, 2025  
**Version:** 1.0