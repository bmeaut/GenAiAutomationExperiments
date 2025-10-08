# 🔑 Simple API Key Setup Guide

## ✅ Much Easier Setup - No OAuth Required!

Instead of complex OAuth setup, you can now use simple Google API keys for read operations.

## 📋 Step-by-Step Setup

### 1. **Get Google API Key** (5 minutes)

1. **Go to Google Cloud Console**:
   - Visit: https://console.cloud.google.com/
   - Sign in with your Google account

2. **Create or Select Project**:
   - Click "Select a project" → "New Project"
   - Name: "Office Automation" 
   - Click "Create"

3. **Enable APIs**:
   - Go to "APIs & Services" → "Library"
   - Search and enable:
     - ✅ **Google Sheets API**
     - ✅ **Google Docs API**

4. **Create API Key**:
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "API Key"
   - Copy the API key (looks like: `AIzaSyDxxxxxxxxxxxxxxxxxxxxxxx`)

5. **Configure API Key** (Optional but Recommended):
   - Click on your API key to edit
   - Under "Application restrictions": Choose "None" for testing
   - Under "API restrictions": Select "Restrict key" and choose:
     - Google Sheets API
     - Google Docs API
   - Click "Save"

### 2. **Update Configuration**

Edit `settings.yaml`:
```yaml
google:
  enabled: true  # Change to true
  api_key: "AIzaSyDxxxxxxxxxxxxxxxxxxxxxxx"  # Paste your API key here
```

### 3. **Test the Setup**

```cmd
cd "D:\onlab\GenAiAutomationExperiments\Work2"
python scripts\python\google_integration_simple.py
```

### 4. **Create a Test Google Sheet**

1. **Go to Google Sheets**: https://sheets.google.com/
2. **Create New Sheet**: Click "Blank"
3. **Add Sample Data**:
   ```
   Name          | Department | Email                | Salary
   John Doe      | IT         | john@company.com     | 75000
   Jane Smith    | HR         | jane@company.com     | 65000
   Bob Johnson   | Finance    | bob@company.com      | 80000
   Alice Brown   | Marketing  | alice@company.com    | 70000
   ```
4. **Get Sheet ID**: From URL `https://docs.google.com/spreadsheets/d/SHEET_ID_HERE/edit`
5. **Make it Public** (for API key access):
   - Click "Share" → "Change to anyone with the link"
   - Set to "Viewer" permissions

### 5. **Test with Your Sheet**

```cmd
python scripts\python\main_pipeline_simple.py --pipeline google-sheets --spreadsheet-id "YOUR_SHEET_ID_HERE"
```

## 🚀 What You Can Do Now

### ✅ **Working Features**
- ✅ Read Google Sheets data → Generate PDF reports
- ✅ Process CSV files → Generate documents  
- ✅ PDF generation with tables and charts
- ✅ Basic email automation (when configured)

### ⚠️ **Limitations with API Key**
- ❌ Cannot write to Google Sheets (read-only)
- ❌ Cannot create new Google Docs
- ❌ Gmail integration still needs OAuth

### 🔧 **For Full Write Access** (Optional)
If you need to write to Google Sheets/Docs, you'll need:
1. Service Account (for server apps)
2. OAuth (for user apps)

But for most automation tasks, read access is sufficient!

## 📖 Usage Examples

### 1. **Google Sheets → PDF Report**
```cmd
python scripts\python\main_pipeline_simple.py --pipeline google-sheets --spreadsheet-id "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
```

### 2. **CSV Data → Documents**
```cmd
python scripts\python\main_pipeline_simple.py --pipeline csv-docs --csv-file "sample_employee_data.csv"
```

### 3. **Test PDF Generation**
```cmd
python scripts\python\main_pipeline_simple.py --pipeline test
```

## 🔍 Troubleshooting

### **API Key Not Working?**
- ✅ Check if APIs are enabled in Google Cloud Console
- ✅ Verify API key is not restricted to wrong APIs
- ✅ Make sure Google Sheet is public (shared with "anyone with link")

### **Permission Denied?**
- ✅ Sheet must be public for API key access
- ✅ For private sheets, you need OAuth or Service Account

### **Import Errors?**
- ✅ Run: `pip install -r requirements_minimal.txt`
- ✅ Make sure you're in the Work2 directory

## 📊 Sample Google Sheets for Testing

### Public Test Sheet (Google's Example):
- **ID**: `1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms`
- **URL**: https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit

This contains student data and is perfect for testing!

---

**🎉 Much simpler than OAuth, right?** 

You can now read from Google Sheets and generate automated reports without any complex authentication flow!