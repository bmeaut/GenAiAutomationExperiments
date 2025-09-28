' Mail Merge VBA Macro for Microsoft Word
' This macro automates the process of filling Word templates with Excel data

Sub AutoFillTemplateFromExcel()
    Dim xlApp As Object
    Dim xlWorkbook As Object
    Dim xlWorksheet As Object
    Dim docTemplate As Document
    Dim docNew As Document
    Dim lastRow As Long
    Dim i As Long
    Dim j As Long
    Dim fieldName As String
    Dim fieldValue As String
    Dim outputPath As String
    Dim templatePath As String
    
    ' Configuration
    Const DATA_FILE_PATH = "data\test_data.csv" ' Update this path as needed
    Const TEMPLATE_FOLDER = "templates\" ' Template folder
    Const OUTPUT_FOLDER = "generated_docs\"
    
    ' Create directories if they don't exist
    If Dir("templates", vbDirectory) = "" Then
        MkDir "templates"
    End If
    If Dir("data", vbDirectory) = "" Then
        MkDir "data"
    End If
    If Dir(OUTPUT_FOLDER, vbDirectory) = "" Then
        MkDir OUTPUT_FOLDER
    End If
    
    ' Open Excel application and workbook
    Set xlApp = CreateObject("Excel.Application")
    xlApp.Visible = False
    Set xlWorkbook = xlApp.Workbooks.Open(ActiveDocument.Path & "\" & DATA_FILE_PATH)
    Set xlWorksheet = xlWorkbook.Sheets(1)
    
    ' Find the last row with data
    lastRow = xlWorksheet.Cells(xlWorksheet.Rows.Count, 1).End(-4162).Row ' xlUp = -4162
    
    ' Get column headers
    Dim headers() As String
    Dim colCount As Long
    colCount = xlWorksheet.Cells(1, xlWorksheet.Columns.Count).End(-4159).Column ' xlToLeft = -4159
    
    ReDim headers(1 To colCount)
    For j = 1 To colCount
        headers(j) = xlWorksheet.Cells(1, j).Value
    Next j
    
    ' Find all template files in templates folder
    Dim templateFiles() As String
    Dim templateCount As Long
    templateCount = 0
    
    ' Get all .docx files from templates folder
    ReDim templateFiles(1 To 20) ' Adjust size as needed
    
    Dim fileName As String
    fileName = Dir(ActiveDocument.Path & "\" & TEMPLATE_FOLDER & "*.docx")
    
    Do While fileName <> ""
        templateCount = templateCount + 1
        templateFiles(templateCount) = fileName
        fileName = Dir
    Loop
    
    If templateCount = 0 Then
        MsgBox "No template files found in " & TEMPLATE_FOLDER & " folder!", vbExclamation
        GoTo Cleanup
    End If
    
    ' Process each template
    For k = 1 To templateCount
        Dim templatePath As String
        templatePath = ActiveDocument.Path & "\" & TEMPLATE_FOLDER & templateFiles(k)
        
        If Dir(templatePath) <> "" Then
            ' Process each row of data (skip header row)
            For i = 2 To lastRow
                ' Open template document
                Set docTemplate = Documents.Open(templatePath)
                
                ' Replace placeholders with data
                For j = 1 To colCount
                    fieldName = "{{" & headers(j) & "}}"
                    fieldValue = CStr(xlWorksheet.Cells(i, j).Value)
                    
                    ' Replace all instances of the field
                    With docTemplate.Range.Find
                        .Text = fieldName
                        .Replacement.Text = fieldValue
                        .Forward = True
                        .Wrap = 1 ' wdFindContinue = 1
                        .Format = False
                        .MatchCase = False
                        .MatchWholeWord = False
                        .MatchWildcards = False
                        .MatchSoundsLike = False
                        .MatchAllWordForms = False
                        .Execute Replace:=2 ' wdReplaceAll = 2
                    End With
                Next j
                
                ' Save the processed document
                Dim employeeName As String
                employeeName = Replace(CStr(xlWorksheet.Cells(i, 1).Value), " ", "_")
                Dim templateBaseName As String
                templateBaseName = Left(templateFiles(k), InStrRev(templateFiles(k), ".") - 1)
                outputPath = ActiveDocument.Path & "\" & OUTPUT_FOLDER & templateBaseName & "_" & employeeName & ".docx"
                
                docTemplate.SaveAs2 outputPath
                docTemplate.Close
                
                Debug.Print "Generated: " & outputPath
            Next i
        End If
    Next k
    
Cleanup:
    ' Clean up
    xlWorkbook.Close False
    xlApp.Quit
    Set xlWorksheet = Nothing
    Set xlWorkbook = Nothing
    Set xlApp = Nothing
    
    If templateCount > 0 Then
        MsgBox "Mail merge complete! Check the " & OUTPUT_FOLDER & " folder for generated documents.", vbInformation
    End If
End Sub

' Helper function to check if file exists
Function FileExists(filePath As String) As Boolean
    FileExists = (Dir(filePath) <> "")
End Function

' Alternative simplified version for single template processing
Sub ProcessSingleTemplate()
    Dim templateName As String
    templateName = InputBox("Enter template filename:", "Template Name", "test_document.docx")
    
    If templateName <> "" And FileExists(templateName) Then
        ' Call the main function with specific template
        ' You can modify the main function to accept template parameter
        AutoFillTemplateFromExcel
    Else
        MsgBox "Template file not found: " & templateName, vbExclamation
    End If
End Sub