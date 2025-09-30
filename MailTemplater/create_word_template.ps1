# PowerShell script to create a real Word document template
$word = New-Object -ComObject Word.Application
$word.Visible = $false

try {
    $doc = $word.Documents.Add()
    
    # Create the template content
    $templateText = @"
EMPLOYEE WELCOME LETTER TEMPLATE

Dear {{Name}},

We are pleased to welcome you to our company! 

Employee Details:
- Position: {{Position}}
- Department: {{Department}}
- Start Date: {{Start Date}}
- Salary: ${{Salary}}
- Email: {{Email}}

We look forward to working with you!

Best regards,
HR Department
"@
    
    $doc.Content.Text = $templateText
    $doc.SaveAs("d:\onlab\GenAiAutomationExperiments\MailTemplater\templates\real_welcome_template.docx")
    Write-Host "Created real Word template: real_welcome_template.docx"
    $doc.Close()
}
finally {
    $word.Quit()
    [System.Runtime.Interopservices.Marshal]::ReleaseComObject($word) | Out-Null
}