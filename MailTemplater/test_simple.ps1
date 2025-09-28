# Simple PowerShell Mail Merge Test
# Tests the logic with text files instead of Word documents

Write-Host "=== Simple Mail Merge Test (PowerShell) ===" -ForegroundColor Cyan

# Check data file
$dataFile = "data\test_data.csv"
if (!(Test-Path $dataFile)) {
    Write-Host "❌ Data file not found: $dataFile" -ForegroundColor Red
    exit 1
}

# Load CSV data
try {
    $data = Import-Csv -Path $dataFile
    Write-Host "✅ Loaded $($data.Count) records from $dataFile" -ForegroundColor Green
    Write-Host "📊 Columns: $($data[0].PSObject.Properties.Name -join ', ')" -ForegroundColor Yellow
} catch {
    Write-Host "❌ Error loading data: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Find text templates
$templateDir = "templates"
if (!(Test-Path $templateDir)) {
    Write-Host "❌ Template directory not found: $templateDir" -ForegroundColor Red
    exit 1
}

$textTemplates = Get-ChildItem -Path $templateDir -Name "*.txt"
if ($textTemplates.Count -eq 0) {
    Write-Host "❌ No .txt template files found in $templateDir" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Found $($textTemplates.Count) text template files" -ForegroundColor Green

# Create output directory
$outputDir = "generated_docs"
if (!(Test-Path $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
}

$totalGenerated = 0

# Process each template
foreach ($templateFile in $textTemplates) {
    Write-Host "`n📄 Processing: $templateFile" -ForegroundColor Cyan
    
    $templatePath = Join-Path $templateDir $templateFile
    
    try {
        # Read template content
        $templateContent = Get-Content -Path $templatePath -Raw -Encoding UTF8
        
        # Process each employee
        foreach ($employee in $data) {
            # Replace placeholders
            $processedContent = $templateContent
            
            $employee.PSObject.Properties | ForEach-Object {
                $placeholder = "{{$($_.Name)}}"
                $processedContent = $processedContent -replace [regex]::Escape($placeholder), $_.Value
            }
            
            # Create output filename
            $templateBaseName = [System.IO.Path]::GetFileNameWithoutExtension($templateFile)
            $safeName = $employee.Name -replace '[^a-zA-Z0-9_-]', '_'
            $outputFileName = "$templateBaseName`_$safeName.txt"
            $outputPath = Join-Path $outputDir $outputFileName
            
            # Write processed file
            $processedContent | Out-File -FilePath $outputPath -Encoding UTF8
            Write-Host "  ✅ Generated: $outputFileName" -ForegroundColor Green
            $totalGenerated++
        }
        
    } catch {
        Write-Host "  ❌ Error processing $templateFile`: $($_.Exception.Message)" -ForegroundColor Red
    }
}

# Summary
Write-Host "`n🎉 Test Complete!" -ForegroundColor Green
Write-Host "📈 Total documents generated: $totalGenerated" -ForegroundColor Yellow
Write-Host "📁 Check the '$outputDir' folder for generated documents" -ForegroundColor Yellow

if ($totalGenerated -gt 0) {
    Write-Host "`n✅ Mail merge logic is working correctly!" -ForegroundColor Green
    Write-Host "👉 Next step: Create real Word .docx templates using Microsoft Word" -ForegroundColor Cyan
} else {
    Write-Host "`n❌ Test failed. Please check the error messages above." -ForegroundColor Red
}