' VBA Module for Excel - Google Sheets Synchronization
' Place this code in a VBA module in Excel

Option Explicit

' Constants for Google Sheets API
Private Const GOOGLE_SHEETS_API_URL As String = "https://sheets.googleapis.com/v4/spreadsheets/"
Private Const HTTP_TIMEOUT As Long = 30000

' Configuration variables
Private GoogleApiKey As String
Private SpreadsheetId As String
Private SheetName As String

' Initialize Google Sheets connection
Public Sub InitializeGoogleSheets()
    On Error GoTo ErrorHandler
    
    ' Load configuration from worksheet or prompt user
    GoogleApiKey = GetConfigValue("GoogleApiKey")
    SpreadsheetId = GetConfigValue("SpreadsheetId") 
    SheetName = GetConfigValue("SheetName")
    
    If GoogleApiKey = "" Or SpreadsheetId = "" Then
        MsgBox "Please configure Google API credentials first!", vbExclamation
        Exit Sub
    End If
    
    MsgBox "Google Sheets integration initialized successfully!", vbInformation
    Exit Sub
    
ErrorHandler:
    MsgBox "Error initializing Google Sheets: " & Err.Description, vbCritical
End Sub

' Sync Excel data to Google Sheets
Public Sub SyncToGoogleSheets()
    On Error GoTo ErrorHandler
    
    ' Check initialization
    If GoogleApiKey = "" Or SpreadsheetId = "" Then
        InitializeGoogleSheets
        If GoogleApiKey = "" Then Exit Sub
    End If
    
    Application.ScreenUpdating = False
    Application.Calculation = xlCalculationManual
    
    Dim ws As Worksheet
    Set ws = ActiveSheet
    
    ' Get data range
    Dim dataRange As Range
    Set dataRange = GetDataRange(ws)
    
    If dataRange Is Nothing Then
        MsgBox "No data found to sync!", vbExclamation
        GoTo Cleanup
    End If
    
    ' Convert data to JSON format
    Dim jsonData As String
    jsonData = ConvertRangeToJson(dataRange)
    
    ' Send to Google Sheets
    Dim result As Boolean
    result = UpdateGoogleSheet(jsonData)
    
    If result Then
        MsgBox "Data synced to Google Sheets successfully!", vbInformation
        ' Log sync operation
        LogSyncOperation ws.Name, dataRange.Rows.Count, "SUCCESS"
    Else
        MsgBox "Failed to sync data to Google Sheets!", vbCritical
        LogSyncOperation ws.Name, dataRange.Rows.Count, "FAILED"
    End If
    
Cleanup:
    Application.ScreenUpdating = True
    Application.Calculation = xlCalculationAutomatic
    Exit Sub
    
ErrorHandler:
    MsgBox "Error syncing to Google Sheets: " & Err.Description, vbCritical
    GoTo Cleanup
End Sub

' Sync Google Sheets data to Excel
Public Sub SyncFromGoogleSheets()
    On Error GoTo ErrorHandler
    
    ' Check initialization
    If GoogleApiKey = "" Or SpreadsheetId = "" Then
        InitializeGoogleSheets
        If GoogleApiKey = "" Then Exit Sub
    End If
    
    Application.ScreenUpdating = False
    Application.Calculation = xlCalculationManual
    
    ' Get data from Google Sheets
    Dim jsonResponse As String
    jsonResponse = GetGoogleSheetData()
    
    If jsonResponse = "" Then
        MsgBox "No data received from Google Sheets!", vbExclamation
        GoTo Cleanup
    End If
    
    ' Parse JSON and update Excel
    Dim ws As Worksheet
    Set ws = ActiveSheet
    
    Dim result As Boolean
    result = UpdateExcelFromJson(ws, jsonResponse)
    
    If result Then
        MsgBox "Data synced from Google Sheets successfully!", vbInformation
        LogSyncOperation ws.Name, 0, "IMPORT_SUCCESS"
    Else
        MsgBox "Failed to sync data from Google Sheets!", vbCritical
        LogSyncOperation ws.Name, 0, "IMPORT_FAILED"
    End If
    
Cleanup:
    Application.ScreenUpdating = True
    Application.Calculation = xlCalculationAutomatic
    Exit Sub
    
ErrorHandler:
    MsgBox "Error syncing from Google Sheets: " & Err.Description, vbCritical
    GoTo Cleanup
End Sub

' Auto-sync function (can be triggered by worksheet change)
Private Sub Worksheet_Change(ByVal Target As Range)
    ' Only trigger on data changes, not formatting
    If Target.Count > 100 Then Exit Sub ' Avoid large operations
    
    ' Check if auto-sync is enabled
    If GetConfigValue("AutoSync") = "TRUE" Then
        ' Delay sync to avoid conflicts
        Application.OnTime Now + TimeValue("00:00:05"), "SyncToGoogleSheets"
    End If
End Sub

' Helper function to get data range
Private Function GetDataRange(ws As Worksheet) As Range
    On Error GoTo ErrorHandler
    
    Dim lastRow As Long
    Dim lastCol As Long
    
    ' Find last used row and column
    lastRow = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row
    lastCol = ws.Cells(1, ws.Columns.Count).End(xlToLeft).Column
    
    If lastRow > 1 And lastCol > 0 Then
        Set GetDataRange = ws.Range(ws.Cells(1, 1), ws.Cells(lastRow, lastCol))
    Else
        Set GetDataRange = Nothing
    End If
    Exit Function
    
ErrorHandler:
    Set GetDataRange = Nothing
End Function

' Convert Excel range to JSON format
Private Function ConvertRangeToJson(dataRange As Range) As String
    On Error GoTo ErrorHandler
    
    Dim json As String
    Dim i As Long, j As Long
    Dim cellValue As String
    
    json = "{"
    json = json & """range"": """ & dataRange.Address & ""","
    json = json & """majorDimension"": ""ROWS"","
    json = json & """values"": ["
    
    ' Convert each row
    For i = 1 To dataRange.Rows.Count
        json = json & "["
        
        For j = 1 To dataRange.Columns.Count
            cellValue = CStr(dataRange.Cells(i, j).Value)
            cellValue = Replace(cellValue, """", """""") ' Escape quotes
            cellValue = Replace(cellValue, vbCrLf, "\n") ' Handle line breaks
            
            json = json & """" & cellValue & """"
            
            If j < dataRange.Columns.Count Then
                json = json & ","
            End If
        Next j
        
        json = json & "]"
        
        If i < dataRange.Rows.Count Then
            json = json & ","
        End If
    Next i
    
    json = json & "]}"
    
    ConvertRangeToJson = json
    Exit Function
    
ErrorHandler:
    ConvertRangeToJson = ""
End Function

' Send data to Google Sheets via HTTP
Private Function UpdateGoogleSheet(jsonData As String) As Boolean
    On Error GoTo ErrorHandler
    
    Dim http As Object
    Set http = CreateObject("MSXML2.XMLHTTP")
    
    Dim url As String
    url = GOOGLE_SHEETS_API_URL & SpreadsheetId & "/values/" & SheetName & "?valueInputOption=RAW&key=" & GoogleApiKey
    
    ' Configure HTTP request
    http.Open "PUT", url, False
    http.setRequestHeader "Content-Type", "application/json"
    http.setTimeouts 0, 0, 0, HTTP_TIMEOUT
    
    ' Send request
    http.send jsonData
    
    ' Check response
    If http.Status = 200 Then
        UpdateGoogleSheet = True
    Else
        Debug.Print "HTTP Error: " & http.Status & " - " & http.responseText
        UpdateGoogleSheet = False
    End If
    
    Set http = Nothing
    Exit Function
    
ErrorHandler:
    UpdateGoogleSheet = False
    Set http = Nothing
End Function

' Get data from Google Sheets
Private Function GetGoogleSheetData() As String
    On Error GoTo ErrorHandler
    
    Dim http As Object
    Set http = CreateObject("MSXML2.XMLHTTP")
    
    Dim url As String
    url = GOOGLE_SHEETS_API_URL & SpreadsheetId & "/values/" & SheetName & "?key=" & GoogleApiKey
    
    ' Configure HTTP request
    http.Open "GET", url, False
    http.setTimeouts 0, 0, 0, HTTP_TIMEOUT
    
    ' Send request
    http.send
    
    ' Check response
    If http.Status = 200 Then
        GetGoogleSheetData = http.responseText
    Else
        Debug.Print "HTTP Error: " & http.Status & " - " & http.responseText
        GetGoogleSheetData = ""
    End If
    
    Set http = Nothing
    Exit Function
    
ErrorHandler:
    GetGoogleSheetData = ""
    Set http = Nothing
End Function

' Update Excel from JSON response
Private Function UpdateExcelFromJson(ws As Worksheet, jsonResponse As String) As Boolean
    On Error GoTo ErrorHandler
    
    ' Simple JSON parsing for Google Sheets response
    ' Note: This is a basic implementation. For production, consider using a proper JSON parser
    
    Dim startPos As Long
    Dim endPos As Long
    Dim valuesSection As String
    
    ' Find the values array in JSON
    startPos = InStr(jsonResponse, """values"":")
    If startPos = 0 Then
        UpdateExcelFromJson = False
        Exit Function
    End If
    
    ' Extract values section (simplified parsing)
    startPos = InStr(startPos, jsonResponse, "[")
    endPos = InStrRev(jsonResponse, "]")
    
    If startPos = 0 Or endPos = 0 Then
        UpdateExcelFromJson = False
        Exit Function
    End If
    
    valuesSection = Mid(jsonResponse, startPos + 1, endPos - startPos - 1)
    
    ' Clear existing data
    ws.Cells.Clear
    
    ' Parse and populate data (basic implementation)
    Dim rows() As String
    Dim currentRow As Long
    Dim i As Long
    
    ' Split by rows (simplified)
    rows = Split(valuesSection, "],[")
    currentRow = 1
    
    For i = 0 To UBound(rows)
        Dim rowData As String
        rowData = rows(i)
        
        ' Clean up row data
        rowData = Replace(rowData, "[", "")
        rowData = Replace(rowData, "]", "")
        rowData = Replace(rowData, """", "")
        
        ' Split by columns
        Dim cols() As String
        cols = Split(rowData, ",")
        
        ' Populate row
        Dim j As Long
        For j = 0 To UBound(cols)
            ws.Cells(currentRow, j + 1).Value = Trim(cols(j))
        Next j
        
        currentRow = currentRow + 1
    Next i
    
    UpdateExcelFromJson = True
    Exit Function
    
ErrorHandler:
    UpdateExcelFromJson = False
End Function

' Configuration management
Private Function GetConfigValue(configKey As String) As String
    On Error GoTo ErrorHandler
    
    ' Try to get from named range first
    Dim configRange As Range
    Set configRange = Nothing
    
    ' Look for config sheet
    Dim configSheet As Worksheet
    On Error Resume Next
    Set configSheet = ThisWorkbook.Worksheets("Config")
    On Error GoTo ErrorHandler
    
    If Not configSheet Is Nothing Then
        ' Look for the config key in column A and get value from column B
        Dim i As Long
        For i = 1 To 100 ' Search first 100 rows
            If configSheet.Cells(i, 1).Value = configKey Then
                GetConfigValue = CStr(configSheet.Cells(i, 2).Value)
                Exit Function
            End If
        Next i
    End If
    
    ' If not found in config sheet, prompt user
    Select Case configKey
        Case "GoogleApiKey"
            GetConfigValue = InputBox("Enter Google API Key:", "Configuration", "")
        Case "SpreadsheetId"
            GetConfigValue = InputBox("Enter Google Spreadsheet ID:", "Configuration", "")
        Case "SheetName"
            GetConfigValue = InputBox("Enter Sheet Name:", "Configuration", "Sheet1")
        Case "AutoSync"
            GetConfigValue = "FALSE" ' Default to disabled
        Case Else
            GetConfigValue = ""
    End Select
    
    ' Save the value to config sheet for next time
    If GetConfigValue <> "" And Not configSheet Is Nothing Then
        SaveConfigValue configKey, GetConfigValue
    End If
    
    Exit Function
    
ErrorHandler:
    GetConfigValue = ""
End Function

' Save configuration value
Private Sub SaveConfigValue(configKey As String, configValue As String)
    On Error GoTo ErrorHandler
    
    Dim configSheet As Worksheet
    On Error Resume Next
    Set configSheet = ThisWorkbook.Worksheets("Config")
    On Error GoTo ErrorHandler
    
    ' Create config sheet if it doesn\'t exist
    If configSheet Is Nothing Then
        Set configSheet = ThisWorkbook.Worksheets.Add
        configSheet.Name = "Config"
        configSheet.Cells(1, 1).Value = "Setting"
        configSheet.Cells(1, 2).Value = "Value"
    End If
    
    ' Find existing setting or add new one
    Dim i As Long
    Dim found As Boolean
    found = False
    
    For i = 2 To 100 ' Start from row 2 (after headers)
        If configSheet.Cells(i, 1).Value = configKey Then
            configSheet.Cells(i, 2).Value = configValue
            found = True
            Exit For
        ElseIf configSheet.Cells(i, 1).Value = "" Then
            configSheet.Cells(i, 1).Value = configKey
            configSheet.Cells(i, 2).Value = configValue
            found = True
            Exit For
        End If
    Next i
    
    Exit Sub
    
ErrorHandler:
    ' Ignore save errors
End Sub

' Log sync operations
Private Sub LogSyncOperation(sheetName As String, rowCount As Long, status As String)
    On Error GoTo ErrorHandler
    
    Dim logSheet As Worksheet
    On Error Resume Next
    Set logSheet = ThisWorkbook.Worksheets("SyncLog")
    On Error GoTo ErrorHandler
    
    ' Create log sheet if it doesn\'t exist
    If logSheet Is Nothing Then
        Set logSheet = ThisWorkbook.Worksheets.Add
        logSheet.Name = "SyncLog"
        logSheet.Cells(1, 1).Value = "Timestamp"
        logSheet.Cells(1, 2).Value = "Sheet"
        logSheet.Cells(1, 3).Value = "Rows"
        logSheet.Cells(1, 4).Value = "Status"
    End If
    
    ' Find next empty row
    Dim nextRow As Long
    nextRow = logSheet.Cells(logSheet.Rows.Count, 1).End(xlUp).Row + 1
    
    ' Add log entry
    logSheet.Cells(nextRow, 1).Value = Now
    logSheet.Cells(nextRow, 2).Value = sheetName
    logSheet.Cells(nextRow, 3).Value = rowCount
    logSheet.Cells(nextRow, 4).Value = status
    
    Exit Sub
    
ErrorHandler:
    ' Ignore logging errors
End Sub

' Create sync buttons in ribbon (optional)
Public Sub CreateSyncButtons()
    On Error GoTo ErrorHandler
    
    ' This would create custom ribbon buttons for sync operations
    ' Implementation depends on Excel version and custom UI requirements
    
    MsgBox "Sync buttons can be added to Quick Access Toolbar manually." & vbCrLf & _
           "Right-click on the ribbon and add macros:" & vbCrLf & _
           "- SyncToGoogleSheets" & vbCrLf & _
           "- SyncFromGoogleSheets", vbInformation
    
    Exit Sub
    
ErrorHandler:
    MsgBox "Error creating sync buttons: " & Err.Description, vbCritical
End Sub

' Setup configuration wizard
Public Sub SetupGoogleSheetsIntegration()
    On Error GoTo ErrorHandler
    
    MsgBox "Google Sheets Integration Setup" & vbCrLf & vbCrLf & _
           "You will need:" & vbCrLf & _
           "1. Google API Key" & vbCrLf & _
           "2. Google Spreadsheet ID" & vbCrLf & _
           "3. Sheet name to sync", vbInformation
    
    ' Guide user through setup
    Dim apiKey As String
    Dim spreadsheetId As String
    Dim sheetName As String
    
    apiKey = InputBox("Enter your Google API Key:" & vbCrLf & _
                     "(Get from Google Cloud Console)", "Google API Key")
    
    If apiKey = "" Then Exit Sub
    
    spreadsheetId = InputBox("Enter Google Spreadsheet ID:" & vbCrLf & _
                           "(From the URL: docs.google.com/spreadsheets/d/[ID]/edit)", "Spreadsheet ID")
    
    If spreadsheetId = "" Then Exit Sub
    
    sheetName = InputBox("Enter Sheet Name:", "Sheet Name", "Sheet1")
    
    If sheetName = "" Then sheetName = "Sheet1"
    
    ' Save configuration
    SaveConfigValue "GoogleApiKey", apiKey
    SaveConfigValue "SpreadsheetId", spreadsheetId
    SaveConfigValue "SheetName", sheetName
    SaveConfigValue "AutoSync", "FALSE"
    
    ' Test connection
    GoogleApiKey = apiKey
    SpreadsheetId = spreadsheetId
    SheetName = sheetName
    
    Dim testResult As String
    testResult = GetGoogleSheetData()
    
    If testResult <> "" Then
        MsgBox "Setup completed successfully!" & vbCrLf & _
               "You can now use:" & vbCrLf & _
               "- SyncToGoogleSheets" & vbCrLf & _
               "- SyncFromGoogleSheets", vbInformation
    Else
        MsgBox "Setup completed, but connection test failed." & vbCrLf & _
               "Please verify your settings.", vbExclamation
    End If
    
    Exit Sub
    
ErrorHandler:
    MsgBox "Error during setup: " & Err.Description, vbCritical
End Sub