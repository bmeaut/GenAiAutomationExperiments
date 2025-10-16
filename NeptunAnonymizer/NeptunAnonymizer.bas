Attribute VB_Name = "NeptunAnonymizer"
Attribute VB_Name = "NeptunAnonymizer"
Option Explicit

' Main subroutine to anonymize Neptun codes in selected column
Sub AnonymizeNeptunCodes()
    Dim saltValue As String
    Dim selectedRange As Range
    Dim cell As Range
    Dim originalCode As String
    Dim anonymizedCode As String
    Dim processedCount As Long
    Dim detectedColumn As String
    Dim ws As Worksheet
    
    Set ws = ActiveSheet
    
    ' Prompt user for salt value
    saltValue = InputBox("Enter salt value for anonymization:" & vbCrLf & _
                        "(Use the same salt for all worksheets to maintain compatibility)", _
                        "Neptun Code Anonymization")
    
    ' Check if user cancelled or entered empty salt
    If saltValue = "" Then
        MsgBox "Anonymization cancelled. Salt value is required.", vbExclamation, "Cancelled"
        Exit Sub
    End If
    
    ' Check if a range is already selected
    If Not Selection Is Nothing Then
        If TypeName(Selection) = "Range" Then
            If Selection.Cells.Count > 0 And Not IsEmpty(Selection.Cells(1, 1).value) Then
                ' Ask user if they want to use the current selection
                Dim useSelection As VbMsgBoxResult
                useSelection = MsgBox("Use currently selected range?" & vbCrLf & _
                                    Selection.Address, vbYesNo + vbQuestion, "Use Selection?")
                If useSelection = vbYes Then
                    Set selectedRange = Selection
                End If
            End If
        End If
    End If
    
    ' If no range selected or user chose not to use it, try auto-detection or prompt
    If selectedRange Is Nothing Then
        detectedColumn = DetectNeptunColumn(ws)
        
        If detectedColumn <> "" Then
            Dim lastRow As Long
            lastRow = ws.Cells(ws.Rows.Count, detectedColumn).End(xlUp).row
            
            Dim useDetected As VbMsgBoxResult
            useDetected = MsgBox("Neptun column detected: " & detectedColumn & vbCrLf & _
                               "Range: " & detectedColumn & "2:" & detectedColumn & lastRow & vbCrLf & vbCrLf & _
                               "Use this range?", vbYesNo + vbQuestion, "Auto-Detected Range")
            
            If useDetected = vbYes Then
                Set selectedRange = ws.Range(detectedColumn & "2:" & detectedColumn & lastRow)
            End If
        End If
    End If
    
    ' If still no range, prompt user to select manually
    If selectedRange Is Nothing Then
        On Error Resume Next
        Set selectedRange = Application.InputBox("Select the range containing Neptun codes:", _
                                                "Select Range", _
                                                Type:=8)
        On Error GoTo 0
        
        ' Check if user cancelled selection
        If selectedRange Is Nothing Then
            MsgBox "No range selected. Operation cancelled.", vbInformation, "Cancelled"
            Exit Sub
        End If
    End If
    
    ' Disable screen updating for better performance
    Application.ScreenUpdating = False
    Application.Calculation = xlCalculationManual
    
    ' Format the entire range as Text to prevent Excel from converting hex to numbers
    selectedRange.NumberFormat = "@"
    
    processedCount = 0
    
    ' Process each cell in the selected range
    For Each cell In selectedRange
        If Not IsEmpty(cell.value) Then
            originalCode = Trim(CStr(cell.value))
            
            ' Only process if cell contains text (potential Neptun code)
            If Len(originalCode) > 0 Then
                anonymizedCode = GenerateAnonymizedCode(saltValue, originalCode)
                cell.value = anonymizedCode
                processedCount = processedCount + 1
            End If
        End If
    Next cell
    
    ' Re-enable screen updating
    Application.Calculation = xlCalculationAutomatic
    Application.ScreenUpdating = True
    
    ' Show completion message
    MsgBox "Anonymization complete!" & vbCrLf & _
           "Processed " & processedCount & " codes.", _
           vbInformation, "Complete"
End Sub

' Function to generate anonymized code using SHA-1 hash
Private Function GenerateAnonymizedCode(ByVal saltValue As String, ByVal neptunCode As String) As String
    Dim inputString As String
    Dim hashValue As String
    
    ' Combine salt and Neptun code
    inputString = saltValue & neptunCode
    
    ' Generate SHA-1 hash and take first 6 characters
    hashValue = ComputeSHA1(inputString)
    GenerateAnonymizedCode = UCase(Left(hashValue, 6))
End Function

' Function to compute SHA-1 hash of a string
Private Function ComputeSHA1(ByVal textToHash As String) As String
    Dim bytes() As Byte
    Dim hashBytes() As Byte
    Dim i As Long
    Dim result As String
    
    ' Convert string to UTF-8 bytes
    bytes = StrConv(textToHash, vbFromUnicode)
    
    ' Create SHA-1 hash object
    Dim sha1 As Object
    Set sha1 = CreateObject("System.Security.Cryptography.SHA1CryptoServiceProvider")
    
    ' Compute hash
    hashBytes = sha1.ComputeHash_2(bytes)
    
    ' Convert bytes to hex string
    result = ""
    For i = LBound(hashBytes) To UBound(hashBytes)
        result = result & Right("0" & Hex(hashBytes(i)), 2)
    Next i
    
    ComputeSHA1 = LCase(result)
    
    Set sha1 = Nothing
End Function

' Function to detect if a string matches Neptun code pattern
Private Function IsNeptunCode(ByVal value As String) As Boolean
    Dim trimmedValue As String
    trimmedValue = Trim(value)
    
    ' Neptun code is exactly 6 alphanumeric characters
    If Len(trimmedValue) = 6 Then
        Dim i As Integer
        For i = 1 To 6
            Dim char As String
            char = Mid(trimmedValue, i, 1)
            If Not ((char >= "A" And char <= "Z") Or (char >= "0" And char <= "9")) Then
                IsNeptunCode = False
                Exit Function
            End If
        Next i
        IsNeptunCode = True
    Else
        IsNeptunCode = False
    End If
End Function

' Function to detect column containing Neptun codes
Private Function DetectNeptunColumn(ByVal ws As Worksheet) As String
    Dim col As Long
    Dim lastCol As Long
    Dim headerValue As String
    Dim matchScore As Long
    Dim bestColumn As Long
    Dim bestScore As Long
    Dim sampleRows As Long
    Dim neptunCount As Long
    
    bestScore = 0
    bestColumn = 0
    lastCol = ws.Cells(1, ws.Columns.Count).End(xlToLeft).Column
    
    ' Check each column
    For col = 1 To lastCol
        matchScore = 0
        headerValue = UCase(Trim(CStr(ws.Cells(1, col).value)))
        
        ' Check header name for Neptun-related keywords
        If InStr(headerValue, "NEPTUN") > 0 Then
            matchScore = matchScore + 100
        ElseIf InStr(headerValue, "CODE") > 0 Or InStr(headerValue, "KOD") > 0 Or InStr(headerValue, "ID") > 0 Then
            matchScore = matchScore + 50
        End If
        
        ' Check cell values in first 10 rows (or less if fewer rows exist)
        sampleRows = Application.Min(10, ws.Cells(ws.Rows.Count, col).End(xlUp).row - 1)
        neptunCount = 0
        
        Dim row As Long
        For row = 2 To sampleRows + 1
            If Not IsEmpty(ws.Cells(row, col).value) Then
                If IsNeptunCode(CStr(ws.Cells(row, col).value)) Then
                    neptunCount = neptunCount + 1
                End If
            End If
        Next row
        
        ' Add score based on percentage of Neptun-like codes
        If sampleRows > 0 Then
            matchScore = matchScore + (neptunCount * 10)
        End If
        
        ' Update best match
        If matchScore > bestScore Then
            bestScore = matchScore
            bestColumn = col
        End If
    Next col
    
    ' Return column letter if found
    If bestColumn > 0 And bestScore >= 10 Then
        DetectNeptunColumn = Split(ws.Cells(1, bestColumn).Address, "$")(1)
    Else
        DetectNeptunColumn = ""
    End If
End Function

' Subroutine to anonymize entire column (alternative method)
Sub AnonymizeColumn()
    Dim saltValue As String
    Dim ws As Worksheet
    Dim lastRow As Long
    Dim columnLetter As String
    Dim targetColumn As Range
    Dim detectedColumn As String
    
    ' Get active worksheet
    Set ws = ActiveSheet
    
    ' Prompt user for salt value
    saltValue = InputBox("Enter salt value for anonymization:" & vbCrLf & _
                        "(Use the same salt for all worksheets to maintain compatibility)", _
                        "Neptun Code Anonymization")
    
    ' Check if user cancelled or entered empty salt
    If saltValue = "" Then
        MsgBox "Anonymization cancelled. Salt value is required.", vbExclamation, "Cancelled"
        Exit Sub
    End If
    
    ' Try to auto-detect Neptun column
    detectedColumn = DetectNeptunColumn(ws)
    
    ' Prompt for column letter with auto-detected suggestion
    If detectedColumn <> "" Then
        columnLetter = InputBox("Neptun column detected: " & detectedColumn & vbCrLf & vbCrLf & _
                               "Enter the column letter containing Neptun codes" & vbCrLf & _
                               "(or press OK to use detected column):", _
                               "Column Selection", detectedColumn)
    Else
        columnLetter = InputBox("Enter the column letter containing Neptun codes (e.g., A, B, C):", _
                               "Column Selection")
    End If
    
    If columnLetter = "" Then
        MsgBox "No column specified. Operation cancelled.", vbInformation, "Cancelled"
        Exit Sub
    End If
    
    ' Find last row with data in the specified column
    lastRow = ws.Cells(ws.Rows.Count, columnLetter).End(xlUp).row
    
    ' Check if column has data
    If lastRow < 2 Then
        MsgBox "No data found in column " & columnLetter, vbExclamation, "No Data"
        Exit Sub
    End If
    
    ' Set target range (excluding header if starting from row 2)
    Dim startRow As Long
    startRow = Application.InputBox("Enter starting row number (typically 2 to skip header):", _
                                   "Start Row", 2, Type:=1)
    
    If startRow < 1 Or startRow > lastRow Then
        MsgBox "Invalid start row.", vbExclamation, "Error"
        Exit Sub
    End If
    
    Set targetColumn = ws.Range(columnLetter & startRow & ":" & columnLetter & lastRow)
    
    ' Process the column
    Application.ScreenUpdating = False
    Application.Calculation = xlCalculationManual
    
    ' Format the entire column as Text to prevent Excel from converting hex to numbers
    targetColumn.NumberFormat = "@"
    
    Dim cell As Range
    Dim processedCount As Long
    processedCount = 0
    
    For Each cell In targetColumn
        If Not IsEmpty(cell.value) Then
            Dim originalCode As String
            originalCode = Trim(CStr(cell.value))
            
            If Len(originalCode) > 0 Then
                cell.value = GenerateAnonymizedCode(saltValue, originalCode)
                processedCount = processedCount + 1
            End If
        End If
    Next cell
    
    Application.Calculation = xlCalculationAutomatic
    Application.ScreenUpdating = True
    
    MsgBox "Anonymization complete!" & vbCrLf & _
           "Processed " & processedCount & " codes in column " & columnLetter, _
           vbInformation, "Complete"
End Sub


