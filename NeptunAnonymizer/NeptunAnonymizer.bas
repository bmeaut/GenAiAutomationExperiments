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
    
    ' Prompt user for salt value
    saltValue = InputBox("Enter salt value for anonymization:" & vbCrLf & _
                        "(Use the same salt for all worksheets to maintain compatibility)", _
                        "Neptun Code Anonymization")
    
    ' Check if user cancelled or entered empty salt
    If saltValue = "" Then
        MsgBox "Anonymization cancelled. Salt value is required.", vbExclamation, "Cancelled"
        Exit Sub
    End If
    
    ' Get the selected range
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
    
    ' Disable screen updating for better performance
    Application.ScreenUpdating = False
    Application.Calculation = xlCalculationManual
    
    ' Format the entire range as Text to prevent Excel from converting hex to numbers
    selectedRange.NumberFormat = "@"
    
    processedCount = 0
    
    ' Process each cell in the selected range
    For Each cell In selectedRange
        If Not IsEmpty(cell.Value) Then
            originalCode = Trim(CStr(cell.Value))
            
            ' Only process if cell contains text (potential Neptun code)
            If Len(originalCode) > 0 Then
                anonymizedCode = GenerateAnonymizedCode(saltValue, originalCode)
                cell.Value = anonymizedCode
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

' Subroutine to anonymize entire column (alternative method)
Sub AnonymizeColumn()
    Dim saltValue As String
    Dim ws As Worksheet
    Dim lastRow As Long
    Dim columnLetter As String
    Dim targetColumn As Range
    
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
    
    ' Prompt for column letter
    columnLetter = InputBox("Enter the column letter containing Neptun codes (e.g., A, B, C):", _
                           "Column Selection")
    
    If columnLetter = "" Then
        MsgBox "No column specified. Operation cancelled.", vbInformation, "Cancelled"
        Exit Sub
    End If
    
    ' Find last row with data in the specified column
    lastRow = ws.Cells(ws.Rows.Count, columnLetter).End(xlUp).Row
    
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
        If Not IsEmpty(cell.Value) Then
            Dim originalCode As String
            originalCode = Trim(CStr(cell.Value))
            
            If Len(originalCode) > 0 Then
                cell.Value = GenerateAnonymizedCode(saltValue, originalCode)
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
