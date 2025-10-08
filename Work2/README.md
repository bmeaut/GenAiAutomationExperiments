# Office Automation Framework

A comprehensive office automation framework that integrates Google Sheets, Google Docs, Microsoft Excel, Word, and email automation with PDF generation capabilities.

## 🎯 Project Overview

This framework provides seamless integration between different office productivity tools:

- **Google Integration**: Google Sheets and Google Docs API integration (simplified with API keys)
- **Microsoft Office**: Excel and Word automation via COM objects  
- **PDF Generation**: Create professional reports and documents
- **Email Automation**: SMTP/IMAP with template support
- **Cross-Platform**: Python-based with VBA macros for enhanced Excel integration

## 📁 Project Structure

```
Work2/
├── main.py                     # Main entry point - run this!
├── README.md                   # This file
├── requirements.txt            # Python dependencies
├── requirements_minimal.txt    # Minimal dependencies
│
├── config/                     # Configuration files
│   ├── .env.example           # Environment variables template
│   ├── settings.yaml          # Main configuration file
│   ├── test_settings.yaml     # Test configuration
│   └── test_settings.json     # Test configuration (JSON)
│
├── scripts/                    # Source code
│   ├── python/                # Python modules
│   │   ├── env_config.py      # Environment configuration loader
│   │   ├── google_integration_simple.py  # Google APIs (simplified)
│   │   ├── office_integration.py         # Excel/Word automation
│   │   ├── pdf_generator.py              # PDF creation
│   │   ├── email_automation.py           # Email automation
│   │   ├── main_pipeline_simple.py       # Main automation pipeline
│   │   └── setup_guide.py               # Setup helper
│   ├── vba/                   # VBA macros
│   │   └── excel_google_sync.bas         # Excel ↔ Google Sheets sync
│   └── powershell/            # PowerShell scripts
│
├── data/                      # Input data files
│   ├── sample_employee_data.csv
│   └── test_data.csv
│
├── templates/                 # Document templates
│   ├── email/                # Email templates
│   └── documents/            # Word/PDF templates
│
├── tests/                     # Test files
│   ├── test_basic.py         # Basic functionality tests
│   ├── test_env_config.py    # Environment configuration tests
│   ├── test_google_sheets_public.py  # Google Sheets tests
│   └── test_simple.py        # Simple integration tests
│
├── outputs/                   # Generated files
│   ├── pdfs/                 # Generated PDF reports
│   ├── documents/            # Generated documents
│   ├── data/                 # Processed data
│   └── reports/              # Analysis reports
│
├── logs/                      # Log files
├── temp/                      # Temporary files
└── docs/                      # Documentation
    ├── API_KEY_SETUP.md      # Google API setup guide
    └── PROJECT_STATUS.md     # Project status and roadmap
```

## 🚀 Quick Start

### 1. Setup Environment

```bash
# Install dependencies
pip install -r requirements.txt

# Setup configuration
python main.py setup --action env

# Edit .env file with your settings
notepad .env  # or your preferred editor
```

### 2. Configure Google API (Optional)

```bash
# Get setup instructions
python main.py setup --action google

# Test Google integration
python main.py test --module google
```

### 3. Run the Pipeline

```bash
# Run basic pipeline
python main.py pipeline --type simple

# Run Google Sheets pipeline (requires API key)
python main.py pipeline --type google-sheets

# Check system status
python main.py setup --action check
```

## 🔧 Configuration

The framework uses environment variables for configuration. Copy `config/.env.example` to `.env` and update:

### Required Settings

```env
# Google API (for Google Sheets/Docs integration)
GOOGLE_API_KEY=your_google_api_key_here

# Email (for automation notifications)
EMAIL_USERNAME=your_email@gmail.com
EMAIL_PASSWORD=your_app_password_here
```

### Optional Settings

```env
# File paths
INPUT_DIR=data
OUTPUT_DIR=outputs
TEMPLATES_DIR=templates

# Automation settings
AUTO_CONVERT_TO_PDF=true
AUTO_SEND_EMAIL=false
MAX_RECORDS_PER_BATCH=1000
```

## 📊 Features

### Google Integration
- **Google Sheets**: Read/write data, format cells, create charts
- **Google Docs**: Create documents, insert data, apply formatting
- **API Key Authentication**: Simplified setup, no OAuth complexity

### Microsoft Office Integration
- **Excel**: Read/write workbooks, format cells, create charts
- **Word**: Create documents, mail merge, apply templates
- **COM Objects**: Direct integration with installed Office applications

### PDF Generation
- **ReportLab**: Create professional PDF reports
- **PyPDF2**: Manipulate existing PDFs (merge, split, extract)
- **Automated**: Convert Office documents to PDF

### Email Automation
- **SMTP/IMAP**: Send/receive emails with attachments
- **Templates**: HTML and text email templates with variables
- **Notifications**: Automated pipeline notifications

## 🧪 Testing

```bash
# Run all tests
python main.py test --module all

# Test specific modules
python main.py test --module google
python main.py test --module office
python main.py test --module pdf
python main.py test --module email
python main.py test --module env
```

## 📋 Common Use Cases

### 1. Google Sheets → PDF Report
```bash
python main.py pipeline --type google-sheets
```

### 2. Excel Data → Word Documents
```bash
python main.py pipeline --type excel-word
```

### 3. Automated Email Reports
Configure email settings and enable `AUTO_SEND_EMAIL=true`

### 4. Batch Document Generation
Process large datasets with `MAX_RECORDS_PER_BATCH` configuration

## 🔑 API Keys Setup

### Google API Key
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create or select a project
3. Enable Google Sheets API and Google Docs API
4. Create credentials (API key)
5. Add to `.env` file as `GOOGLE_API_KEY`

### Email App Password
1. Enable 2-factor authentication in Gmail
2. Generate app password in account settings
3. Add to `.env` file as `EMAIL_PASSWORD`

## 🐛 Troubleshooting

### Import Errors
```bash
pip install -r requirements.txt
```

### Google API Errors
```bash
python main.py setup --action google
python main.py test --module google
```

### Office COM Errors
- Ensure Microsoft Office is installed
- Run as administrator if needed
- Check `OFFICE_*_VISIBLE` settings

### Configuration Issues
```bash
python main.py setup --action check
```

## 📈 Project Status

- ✅ **Core Framework**: Complete
- ✅ **Google Integration**: Simplified API key approach
- ✅ **Office Integration**: Excel/Word COM automation
- ✅ **PDF Generation**: ReportLab + PyPDF2
- ✅ **Email Automation**: SMTP with templates
- ✅ **Environment Configuration**: .env support
- 🚧 **Advanced Pipelines**: In development
- 🚧 **Web Interface**: Planned
- 🚧 **Database Integration**: Planned

## 🤝 Contributing

This is an experimental automation framework. Feel free to:
- Report issues
- Suggest improvements
- Add new integrations
- Share use cases

## 📄 License

This project is for educational and experimental purposes.

---

**Getting Started**: Run `python main.py setup --action check` to see what's configured!