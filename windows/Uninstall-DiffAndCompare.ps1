<#
.SYNOPSIS
    Uninstalls diff_and_compare_tool and completely removes all registry keys and shortcuts.
.DESCRIPTION
    Removes:
    - Windows Explorer Context Menus
    - App Paths (Win+R / CMD launch)
    - Windows "Installed Apps" entry
    - User PATH entry
    - Start Menu & Desktop shortcuts
    - Application files and directory
#>

[CmdletBinding()]
param (
    [string]$InstallDir = "$env:LOCALAPPDATA\Programs\diff_and_compare_tool",
    [switch]$KeepAppData,
    [switch]$Silent
)

function Write-UninstallerLog {
    param([string]$Message, [string]$Color = "Cyan")
    if (-not $Silent) {
        Write-Host "[$([DateTime]::Now.ToString('HH:mm:ss'))] $Message" -ForegroundColor $Color
    }
}

Write-UninstallerLog "==========================================================" "Yellow"
Write-UninstallerLog "  Uninstalling diff_and_compare_tool" "Yellow"
Write-UninstallerLog "==========================================================" "Yellow"

# 1. Close running processes
$procs = Get-Process -Name "diff_and_compare", "diff_and_compare_tool", "diff_and_compare_x64" -ErrorAction SilentlyContinue
if ($procs) {
    Write-UninstallerLog "Closing running instances..." "Yellow"
    $procs | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 500
}

# 2. Remove Explorer Context Menu entries via .NET Registry API
Write-UninstallerLog "Removing Windows Explorer Context Menu entries..." "Cyan"
$regTargets = @(
    "Software\Classes\*\shell",
    "Software\Classes\Directory\shell",
    "Software\Classes\Directory\Background\shell"
)

$menuKeys = @(
    "DiffAndCompareToolCompare",
    "DiffAndCompareToolSelectLeft",
    "DiffAndCompareToolSelectRight",
    "DiffAndCompareCompare",
    "DiffAndCompareSelectLeft",
    "DiffAndCompareSelectRight",
    "BeyondCompareCompare",
    "BeyondCompareSelectLeft",
    "BeyondCompareSelectRight"
)

foreach ($target in $regTargets) {
    foreach ($keyName in $menuKeys) {
        try {
            [Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree("$target\$keyName", $false)
        } catch {}
    }
}

# 3. Remove App Paths
Write-UninstallerLog "Removing Windows App Paths..." "Cyan"
try {
    [Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree("Software\Microsoft\Windows\CurrentVersion\App Paths\diff_and_compare.exe", $false)
} catch {}
try {
    [Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree("Software\Microsoft\Windows\CurrentVersion\App Paths\diff_and_compare_tool.exe", $false)
} catch {}

# 4. Remove Windows Installed Apps entry
Write-UninstallerLog "Removing Windows Installed Apps registration..." "Cyan"
try {
    [Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree("Software\Microsoft\Windows\CurrentVersion\Uninstall\diff_and_compare_tool", $false)
} catch {}

# 5. Remove from User PATH
Write-UninstallerLog "Removing from User PATH..." "Cyan"
try {
    $userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
    if ($userPath) {
        $paths = ($userPath -split ";") | Where-Object { $_ -ne "" -and $_ -ne $InstallDir }
        $newPath = $paths -join ";"
        [Environment]::SetEnvironmentVariable("PATH", $newPath, "User")
    }
} catch {}

# 6. Remove Shortcuts
Write-UninstallerLog "Removing shortcuts..." "Cyan"
$shortcuts = @(
    "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\diff_and_compare_tool.lnk",
    "$env:USERPROFILE\Desktop\diff_and_compare_tool.lnk"
)
foreach ($sc in $shortcuts) {
    if (Test-Path $sc) {
        Remove-Item -Path $sc -Force -ErrorAction SilentlyContinue
    }
}

# 7. Optional AppData cleanup
if (-not $KeepAppData) {
    $appData = "$env:APPDATA\diff_and_compare"
    if (Test-Path $appData) {
        Remove-Item -Path $appData -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# 8. Clean up installation directory
Write-UninstallerLog "Removing program files..." "Cyan"
if (Test-Path $InstallDir) {
    $runningDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
    if ($runningDir.TrimEnd('\') -eq $InstallDir.TrimEnd('\')) {
        Start-Process cmd.exe -ArgumentList "/c ping 127.0.0.1 -n 2 >nul & rmdir /s /q `"$InstallDir`"" -WindowStyle Hidden
    } else {
        Remove-Item -Path $InstallDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-UninstallerLog "==========================================================" "Green"
Write-UninstallerLog "  Uninstallation Complete!" "Green"
Write-UninstallerLog "  All registry entries, shortcuts, and files were removed." "White"
Write-UninstallerLog "==========================================================" "Green"
