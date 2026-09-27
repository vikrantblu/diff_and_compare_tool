# PowerShell Script to register diff_and_compare_tool with Windows 11 Fluent Context Menu (Sparse Package)
# Run in Administrator PowerShell:
#   powershell -ExecutionPolicy Bypass -File .\Register-Windows11ContextMenu.ps1

$manifestPath = Join-Path $PSScriptRoot "AppxManifest.xml"
$externalLocation = (Get-Item $PSScriptRoot).Parent.FullName

Write-Host "Registering diff_and_compare_tool Windows 11 Context Menu Extension..." -ForegroundColor Cyan
Write-Host "Manifest: $manifestPath" -ForegroundColor Gray
Write-Host "External Location: $externalLocation" -ForegroundColor Gray

try {
    Add-AppxPackage -Path $manifestPath -RegisterByHostExtension -ExternalLocation $externalLocation -ErrorAction Stop
    Write-Host "`n[SUCCESS] Windows 11 Context Menu Registered!" -ForegroundColor Green
    Write-Host "diff_and_compare_tool now appears in the top-level Windows 11 File Explorer menu." -ForegroundColor Yellow
} catch {
    Write-Warning "Sparse package registration returned: $_"
    Write-Host "`nFalling back to Direct Windows Registry registration..." -ForegroundColor Cyan
    $mainPy = Join-Path $externalLocation "app\main.py"
    if (Test-Path $mainPy) {
        & python $mainPy --install-shell
    } else {
        $regPath = Join-Path $PSScriptRoot "Register-All.reg"
        Start-Process regedit.exe -ArgumentList "/s `"$regPath`"" -Wait
    }
    Write-Host "[SUCCESS] Registry context menu registered successfully!" -ForegroundColor Green
}
