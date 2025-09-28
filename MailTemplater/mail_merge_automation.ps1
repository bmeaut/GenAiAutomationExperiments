# PowerShell Mail Merge Automation Script
# Automates Word document generation from Excel data using COM objects

param(
    [string]$DataFile = "data/test_data.csv",
    [string]$TemplateDir = "templates",
    [string]$OutputDir = "generated_docs",
    [string]$TemplatePattern = "*.docx"
)

# Function to ensure output directory exists
function Ensure-OutputDirectory {
    param([string]$Path)
    if (!(Test-Path $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
        Write-Host "Created output directory: $Path" -ForegroundColor Green
    }
}

# Function to load CSV data
function Load-CSVData {
    param([string]$FilePath)
    
    try {
        $data = Import-Csv -Path $FilePath
        Write-Host "Loaded $($data.Count) records from $FilePath" -ForegroundColor Green
        return $data
    }
    catch {
        Write-Error "Failed to load CSV data: $($_.Exception.Message)"
        return $null
    }
}

# Function to process a single template with employee data
function Process-Template {
    param(
        [string]$TemplatePath,
        [psobject]$EmployeeData,
        [string]$OutputPath
    )
    
    try {
        # Create Word Application
        $word = New-Object -ComObject Word.Application
        $word.Visible = $false
        
        # Open template document
        $doc = $word.Documents.Open($TemplatePath)
        
        # Get all properties of the employee data
        $properties = $EmployeeData | Get-Member -MemberType NoteProperty
        
        # Replace each field in the document
        foreach ($property in $properties) {
            $fieldName = "{{$($property.Name)}}"
            $fieldValue = $EmployeeData.$($property.Name)
            
            # Use Find and Replace to replace all instances
            $findReplace = $word.Selection.Find
            $findReplace.Text = $fieldName
            $findReplace.Replacement.Text = $fieldValue
            $findReplace.Forward = $true
            $findReplace.Wrap = 1  # wdFindContinue
            $findReplace.Format = $false
            $findReplace.MatchCase = $false
            $findReplace.MatchWholeWord = $false
            $findReplace.MatchWildcards = $false
            $findReplace.MatchSoundsLike = $false
            $findReplace.MatchAllWordForms = $false
            
            # Execute replace all
            $null = $findReplace.Execute($fieldName, $false, $false, $false, $false, $false, $true, 1, $false, $fieldValue, 2)
        }
        
        # Save the document
        $doc.SaveAs2($OutputPath)
        $doc.Close()
        $word.Quit()
        
        # Release COM objects
        [System.Runtime.Interopservices.Marshal]::ReleaseComObject($doc) | Out-Null
        [System.Runtime.Interopservices.Marshal]::ReleaseComObject($word) | Out-Null
        
        Write-Host "Generated: $OutputPath" -ForegroundColor Green
        return $true
    }
    catch {
        Write-Error "Failed to process template $TemplatePath`: $($_.Exception.Message)"
        
        # Clean up COM objects in case of error
        try {
            if ($doc) { $doc.Close() }
            if ($word) { $word.Quit() }
            [System.Runtime.Interopservices.Marshal]::ReleaseComObject($doc) | Out-Null
            [System.Runtime.Interopservices.Marshal]::ReleaseComObject($word) | Out-Null
        }
        catch { }
        
        return $false
    }
}

# Main execution
Write-Host "=== Mail Merge Automation Script ===" -ForegroundColor Cyan
Write-Host "Data File: $DataFile" -ForegroundColor Yellow
Write-Host "Template Directory: $TemplateDir" -ForegroundColor Yellow
Write-Host "Output Directory: $OutputDir" -ForegroundColor Yellow
Write-Host "Template Pattern: $TemplatePattern" -ForegroundColor Yellow
Write-Host ""

# Ensure directories exist
if (!(Test-Path $TemplateDir)) {
    New-Item -ItemType Directory -Path $TemplateDir -Force | Out-Null
    Write-Host "Created template directory: $TemplateDir" -ForegroundColor Green
    Write-Host "Please place your .docx template files in the '$TemplateDir' directory." -ForegroundColor Yellow
}

# Ensure output directory exists
Ensure-OutputDirectory -Path $OutputDir

# Load CSV data
$employeeData = Load-CSVData -FilePath $DataFile
if ($employeeData -eq $null) {
    Write-Error "Cannot proceed without data. Exiting."
    exit 1
}

# Find template files
$templateFiles = Get-ChildItem -Path $TemplateDir -Name $TemplatePattern
if ($templateFiles.Count -eq 0) {
    Write-Warning "No template files found matching pattern: $TemplatePattern in directory: $TemplateDir"
    Write-Host "Make sure you have .docx files in the '$TemplateDir' directory." -ForegroundColor Yellow
    exit 1
}

Write-Host "Found $($templateFiles.Count) template file(s):" -ForegroundColor Green
foreach ($template in $templateFiles) {
    Write-Host "  - $template" -ForegroundColor White
}
Write-Host ""

# Process each template for each employee
$totalGenerated = 0
$errors = 0

foreach ($template in $templateFiles) {
    Write-Host "Processing template: $template" -ForegroundColor Cyan
    $templateBaseName = [System.IO.Path]::GetFileNameWithoutExtension($template)
    
    foreach ($employee in $employeeData) {
        # Create safe filename
        $employeeName = $employee.Name -replace '[^a-zA-Z0-9_-]', '_'
        $outputFileName = "$templateBaseName`_$employeeName.docx"
        $outputPath = Join-Path $OutputDir $outputFileName
        $templateFullPath = Join-Path $TemplateDir $template
        $templateFullPath = (Resolve-Path $templateFullPath).Path
        
        # Process the template
        if (Process-Template -TemplatePath $templateFullPath -EmployeeData $employee -OutputPath $outputPath) {
            $totalGenerated++
        } else {
            $errors++
        }
    }
    Write-Host ""
}

# Generate summary
$summaryPath = Join-Path $OutputDir "processing_summary.txt"
$summary = @"
MAIL MERGE PROCESSING SUMMARY
=============================

Processing Date: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
Data Source: $DataFile
Templates Processed: $($templateFiles.Count)
Employee Records: $($employeeData.Count)
Documents Generated: $totalGenerated
Errors: $errors

Template Files:
$($templateFiles | ForEach-Object { "  - $_" } | Out-String)

Generated Files:
$(Get-ChildItem -Path $OutputDir -Name "*.docx" | ForEach-Object { "  - $_" } | Out-String)
"@

$summary | Out-File -FilePath $summaryPath -Encoding UTF8

Write-Host "=== SUMMARY ===" -ForegroundColor Cyan
Write-Host "Documents Generated: $totalGenerated" -ForegroundColor Green
Write-Host "Errors: $errors" -ForegroundColor $(if($errors -gt 0) { "Red" } else { "Green" })
Write-Host "Summary saved to: $summaryPath" -ForegroundColor Yellow
Write-Host ""
Write-Host "All generated documents are in the '$OutputDir' directory." -ForegroundColor Green