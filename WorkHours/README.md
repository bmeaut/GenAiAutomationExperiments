# Redmine Timesheet Automation Suite

This Python automation suite provides complete workflow automation for Redmine timesheet generation.

## 🎯 **Complete Automation (Recommended)**

**`redmine_timesheet_automation.py`** - One-click complete workflow:
1. ✅ Export CSV from Redmine (Selenium automation)
2. ✅ Parse CSV and create Excel timesheet  
3. ✅ Clean up temporary files
4. ✅ Ready-to-submit Excel file

### Quick Usage:
```powershell
python redmine_timesheet_automation.py           # Quiet mode (minimal output)
```

```powershell
python redmine_timesheet_automation.py --verbose # Detailed step-by-step logging
```

**✨ Output Modes:**

- **Quiet Mode** (default): Shows only essential information and results, suppresses DevTools messages and browser debug output
- **Verbose Mode** (`--verbose` or `-v`): Shows detailed step-by-step progress, browser window, and debug information

## 🔧 **Individual Components**

### Redmine CSV Export (`redmine_automation.py`)

Automated Redmine CSV export with Selenium:

- Automatic login to Redmine
- Sets date filter to "múlt hónap" (last month)
- Adds user filter and applies filters
- Exports results to CSV
- Handles export dialog
- Supports quiet and verbose modes

**Usage:**
```powershell
python redmine_automation.py           # Quiet mode (headless browser)
python redmine_automation.py --verbose # Verbose mode (visible browser + logs)
```

### CSV to Excel Parser (`csv_parser.py`)

CSV parsing and Excel timesheet generation:

- Parses CSV with ANSI encoding (Hungarian characters)
- Creates properly formatted Excel timesheet
- Handles weekends, multiple entries, special characters
- Generates clean filename with date and user
- Clears existing data before filling template

**Usage:**
```powershell
python csv_parser.py           # Quiet mode
python csv_parser.py --verbose # Detailed parsing information
```

## Prerequisites

1. **Python 3.7+** installed on your system
2. **Google Chrome** browser installed
3. **ChromeDriver** installed and in your PATH, or Chrome will auto-download it

## Setup

1. **Install Python dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```

2. **Configure credentials:**
   - The `.env` file should already contain your Redmine credentials
   - If not, update the `.env` file with your username and password:
   
     ```env
     REDMINE_URL=https://web.innovitech.hu/redmine/
     REDMINE_USERNAME=your_username
     REDMINE_PASSWORD=your_password
     ```

3. **Install ChromeDriver (if not already installed):**
   - Download from: https://chromedriver.chromium.org/
   - Extract and add to your PATH, or place in the same directory as the script
   - Alternatively, modern Chrome versions can auto-download the appropriate driver

## Usage

### Complete Workflow (Recommended)
```powershell
python redmine_timesheet_automation.py           # Quiet mode
python redmine_timesheet_automation.py --verbose # Verbose mode
```

### Individual Scripts
```powershell
# Redmine CSV export only
python redmine_automation.py [--verbose]

# CSV to Excel conversion only (requires existing timelog.csv)
python csv_parser.py [--verbose]
```

### Command Line Options

- **`--verbose` or `-v`:** Enable detailed step-by-step logging and show browser window
- **Default (quiet mode):** Minimal output, headless browser operation
- **Error handling:** Screenshots saved as `error_screenshot.png` on failures

## How it works

1. **Login:** Navigates to Redmine and logs in if redirected to login page
2. **Navigate:** Goes to the time entries page
3. **Filter Setup:** 
   - Sets date filter to "múlt hónap" (last month)
   - Adds "Felhasználó" (User) filter
4. **Apply:** Applies the configured filters
5. **Export:** Initiates CSV export

## Troubleshooting

### Common Issues

1. **ChromeDriver not found:**
   - Install ChromeDriver and ensure it's in your PATH
   - Or place chromedriver.exe in the same folder as the script

2. **Login fails:**
   - Verify credentials in `.env` file
   - Check if Redmine site is accessible

3. **Elements not found:**
   - The website might have changed its structure
   - Check the error screenshot for visual debugging

4. **Timeout errors:**
   - Increase wait times in the script if your internet connection is slow
   - The script waits up to 10 seconds for elements to load

### Debug Mode

If the script fails, it will:
- Print detailed error messages
- Save a screenshot as `error_screenshot.png` for visual debugging
- Keep the browser open briefly so you can see what happened

## Script Structure

- `RedmineTimeEntriesExporter`: Main class handling the automation
- `login()`: Handles authentication
- `navigate_to_time_entries()`: Goes to the time entries page
- `set_date_filter_to_last_month()`: Sets date filter
- `add_user_filter()`: Adds user filter
- `apply_filters()`: Applies all filters
- `export_to_csv()`: Initiates CSV download
- `run_automation()`: Orchestrates the entire process

## Customization

You can modify the script to:
- Change the date filter (modify `select_by_value('lm')` in `set_date_filter_to_last_month()`)
- Add different filters (modify `add_user_filter()` method)
- Change wait times (modify `WebDriverWait` timeout values)
- Run in headless mode (set `headless=True`)

## Recent Improvements

### ✨ **Output Suppression (v2.0)**
- **Quiet Mode Enhancement**: Suppresses Chrome DevTools messages, registration errors, and TensorFlow warnings
- **Headless Operation**: Runs in background when not in verbose mode
- **Clean Output**: Only shows essential progress and results in quiet mode

### 🔧 **Configuration Management**
- **Environment Variables**: All URLs and credentials loaded from `.env` file
- **Dynamic URL Construction**: No hardcoded URLs, fully configurable
- **Flexible Deployment**: Easy to adapt for different Redmine instances

### 🛠️ **Error Handling & Debugging**
- **Enhanced Screenshots**: Automatic error screenshot capture
- **Verbose Logging**: Detailed step-by-step information with `--verbose` flag
- **Graceful Failures**: Informative error messages with troubleshooting hints

## Security Notes

- Keep your `.env` file secure and never commit it to version control
- The script uses HTTPS for secure communication with Redmine
- Credentials are loaded from environment variables, not hardcoded
