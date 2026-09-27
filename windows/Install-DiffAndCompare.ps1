<#
.SYNOPSIS
    Installs diff_and_compare_tool into Windows with full Registry integration.
.DESCRIPTION
    Deploys application binaries to %LOCALAPPDATA%\Programs\diff_and_compare_tool,
    creates Start Menu & Desktop shortcuts, adds the directory to User PATH,
    registers Windows Explorer right-click context menus (Compare, Select Left, Select Right),
    registers App Paths (Win+R / CMD launch), and creates Windows "Installed Apps" entry.
    Requires NO administrator privileges (installs to HKCU).
#>

[CmdletBinding()]
param (
    [string]$InstallDir = "$env:LOCALAPPDATA\Programs\diff_and_compare_tool",
    [switch]$DesktopShortcut = $true,
    [switch]$NoShortcuts,
    [switch]$NoContextMenu,
    [switch]$NoAppPaths,
    [switch]$NoPath,
    [switch]$Silent
)

function Write-InstallerLog {
    param([string]$Message, [string]$Color = "Cyan")
    if (-not $Silent) {
        Write-Host "[$([DateTime]::Now.ToString('HH:mm:ss'))] $Message" -ForegroundColor $Color
    }
}

Write-InstallerLog "==========================================================" "Green"
Write-InstallerLog "  diff_and_compare_tool Windows Installer" "Green"
Write-InstallerLog "==========================================================" "Green"

# 1. Resolve Source Files Directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$SourceDir = $null

$candidates = @(
    $ScriptDir,
    (Join-Path $ScriptDir "..\dist\diff_and_compare"),
    (Join-Path $ScriptDir "dist\diff_and_compare"),
    (Join-Path (Split-Path -Parent $ScriptDir) "dist\diff_and_compare")
)

foreach ($c in $candidates) {
    if (Test-Path (Join-Path $c "diff_and_compare.exe")) {
        $SourceDir = (Resolve-Path $c).Path
        break
    }
}

if (-not $SourceDir) {
    Write-InstallerLog "ERROR: Could not locate 'diff_and_compare.exe' in source packages!" "Red"
    Write-InstallerLog "Please build the application first (e.g. 'python build.py') or run installer from the release package." "Yellow"
    exit 1
}

Write-InstallerLog "Source package located at: $SourceDir" "White"
Write-InstallerLog "Destination directory:     $InstallDir" "White"

# 2. Terminate any running instances of the application
$running = Get-Process -Name "diff_and_compare", "diff_and_compare_tool", "diff_and_compare_x64" -ErrorAction SilentlyContinue
if ($running) {
    Write-InstallerLog "Closing running instances of diff_and_compare..." "Yellow"
    $running | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 500
}

# 3. Create Target Directory & Copy Files
if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}

Write-InstallerLog "Deploying program files..." "Cyan"
Copy-Item -Path "$SourceDir\*" -Destination $InstallDir -Recurse -Force -Exclude "*.log","*.tmp"

# Ensure assets directory and icon are at root of install directory
$targetIcon = Join-Path $InstallDir "assets\app_icon.ico"
if (-not (Test-Path $targetIcon)) {
    $altIcons = @(
        (Join-Path $InstallDir "_internal\assets\app_icon.ico"),
        (Join-Path $ScriptDir "..\assets\app_icon.ico"),
        (Join-Path $ScriptDir "Assets\app_icon.ico")
    )
    foreach ($ai in $altIcons) {
        if (Test-Path $ai) {
            $null = New-Item -ItemType Directory -Path (Join-Path $InstallDir "assets") -Force -ErrorAction SilentlyContinue
            Copy-Item -Path $ai -Destination $targetIcon -Force
            break
        }
    }
}

$targetExe = Join-Path $InstallDir "diff_and_compare.exe"
if (-not (Test-Path $targetIcon)) {
    $targetIcon = $targetExe
}

# 4. Deploy Uninstaller script & launcher inside InstallDir
$uninstallPs1 = Join-Path $InstallDir "uninstall.ps1"
$uninstallCmd = Join-Path $InstallDir "uninstall.cmd"

$srcUninstallPs1 = Join-Path $ScriptDir "Uninstall-DiffAndCompare.ps1"
if (Test-Path $srcUninstallPs1) {
    Copy-Item -Path $srcUninstallPs1 -Destination $uninstallPs1 -Force
}

# Deploy uninstall.cmd wrapper
@"
@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0uninstall.ps1" %*
"@ | Set-Content -Path $uninstallCmd -Encoding ASCII

# 5. Create Shortcuts
if (-not $NoShortcuts) {
    Write-InstallerLog "Creating Start Menu shortcut..." "Cyan"
    $wsh = New-Object -ComObject WScript.Shell

    $startMenuDir = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs"
    $startShortcutPath = Join-Path $startMenuDir "diff_and_compare_tool.lnk"
    $shortcut = $wsh.CreateShortcut($startShortcutPath)
    $shortcut.TargetPath = $targetExe
    $shortcut.WorkingDirectory = $InstallDir
    $shortcut.IconLocation = "$targetIcon,0"
    $shortcut.Description = "diff_and_compare_tool - Multi-Format Diff & 3-Way Merge Studio"
    $shortcut.Save()

    if ($DesktopShortcut) {
        Write-InstallerLog "Creating Desktop shortcut..." "Cyan"
        $desktopShortcutPath = "$env:USERPROFILE\Desktop\diff_and_compare_tool.lnk"
        $dShortcut = $wsh.CreateShortcut($desktopShortcutPath)
        $dShortcut.TargetPath = $targetExe
        $dShortcut.WorkingDirectory = $InstallDir
        $dShortcut.IconLocation = "$targetIcon,0"
        $dShortcut.Description = "diff_and_compare_tool"
        $dShortcut.Save()
    }
}

# 6. Add to User PATH
if (-not $NoPath) {
    Write-InstallerLog "Updating User PATH environment variable..." "Cyan"
    $userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
    $paths = ($userPath -split ";") | Where-Object { $_ -ne "" }
    if ($paths -notcontains $InstallDir) {
        $newPath = ($paths + $InstallDir) -join ";"
        [Environment]::SetEnvironmentVariable("PATH", $newPath, "User")
    }
}

# 7. Register Windows Explorer Context Menu via .NET Registry API
if (-not $NoContextMenu) {
    Write-InstallerLog "Configuring Windows Explorer Context Menus..." "Cyan"
    $regTargets = @(
        "Software\Classes\*\shell",
        "Software\Classes\Directory\shell",
        "Software\Classes\Directory\Background\shell"
    )

    $menuItems = @(
        @{ Key = "DiffAndCompareToolCompare";    Title = "Compare with diff_and_compare_tool"; Flag = "--compare" },
        @{ Key = "DiffAndCompareToolSelectLeft";  Title = "diff_and_compare_tool: Select Left"; Flag = "--select-left" },
        @{ Key = "DiffAndCompareToolSelectRight"; Title = "diff_and_compare_tool: Select Right"; Flag = "--select-right" }
    )

    foreach ($target in $regTargets) {
        foreach ($item in $menuItems) {
            $itemSubKey = "$target\$($item.Key)"
            $k = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($itemSubKey)
            $k.SetValue("", $item.Title)
            $k.SetValue("Icon", $targetIcon)
            $k.Close()

            $cmdSubKey = "$itemSubKey\command"
            $argMacro = if ($target -like "*Background*") { "%V" } else { "%1" }
            $cmdLine = "`"$targetExe`" $($item.Flag) `"$argMacro`""
            $ck = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($cmdSubKey)
            $ck.SetValue("", $cmdLine)
            $ck.Close()
        }
    }
}

# 8. Register App Paths (Win+R / CMD launch)
if (-not $NoAppPaths) {
    Write-InstallerLog "Registering Windows App Paths..." "Cyan"
    $appNames = @("diff_and_compare.exe", "diff_and_compare_tool.exe")
    foreach ($app in $appNames) {
        $appSubKey = "Software\Microsoft\Windows\CurrentVersion\App Paths\$app"
        $ak = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($appSubKey)
        $ak.SetValue("", $targetExe)
        $ak.SetValue("Path", $InstallDir)
        $ak.Close()
    }
}

# 9. Register Windows "Installed Apps" / "Add or Remove Programs"
Write-InstallerLog "Registering in Windows Installed Apps..." "Cyan"
$unSubKey = "Software\Microsoft\Windows\CurrentVersion\Uninstall\diff_and_compare_tool"
$uk = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($unSubKey)
$uk.SetValue("DisplayName", "diff_and_compare_tool")
$uk.SetValue("DisplayVersion", "1.0.0")
$uk.SetValue("Publisher", "diff_and_compare_tool")
$uk.SetValue("DisplayIcon", "$targetExe,0")
$uk.SetValue("InstallLocation", $InstallDir)
$uk.SetValue("UninstallString", "`"$uninstallCmd`"")
$uk.SetValue("QuietUninstallString", "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$uninstallPs1`" -Silent")
$uk.SetValue("EstimatedSize", 420000, [Microsoft.Win32.RegistryValueKind]::DWord)
$uk.SetValue("NoModify", 1, [Microsoft.Win32.RegistryValueKind]::DWord)
$uk.SetValue("NoRepair", 1, [Microsoft.Win32.RegistryValueKind]::DWord)
$uk.Close()

# 10. Generate localized .reg file in InstallDir
$regFile = Join-Path $InstallDir "Register-Win32ContextMenu.reg"
$unregFile = Join-Path $InstallDir "Unregister-Win32ContextMenu.reg"

$regExeEsc = $targetExe.Replace("\", "\\")
$regIconEsc = $targetIcon.Replace("\", "\\")
$regDirEsc = $InstallDir.Replace("\", "\\")

@"
Windows Registry Editor Version 5.00

; diff_and_compare_tool Context Menu Registration
[HKEY_CURRENT_USER\Software\Classes\*\shell\DiffAndCompareToolCompare]
@="Compare with diff_and_compare_tool"
"Icon"="\"$regIconEsc\""

[HKEY_CURRENT_USER\Software\Classes\*\shell\DiffAndCompareToolCompare\command]
@="\"\"$regExeEsc\" --compare \"%1\"\""

[HKEY_CURRENT_USER\Software\Classes\*\shell\DiffAndCompareToolSelectLeft]
@="diff_and_compare_tool: Select Left"
"Icon"="\"$regIconEsc\""

[HKEY_CURRENT_USER\Software\Classes\*\shell\DiffAndCompareToolSelectLeft\command]
@="\"\"$regExeEsc\" --select-left \"%1\"\""

[HKEY_CURRENT_USER\Software\Classes\*\shell\DiffAndCompareToolSelectRight]
@="diff_and_compare_tool: Select Right"
"Icon"="\"$regIconEsc\""

[HKEY_CURRENT_USER\Software\Classes\*\shell\DiffAndCompareToolSelectRight\command]
@="\"\"$regExeEsc\" --select-right \"%1\"\""

[HKEY_CURRENT_USER\Software\Classes\Directory\shell\DiffAndCompareToolCompare]
@="Compare with diff_and_compare_tool"
"Icon"="\"$regIconEsc\""

[HKEY_CURRENT_USER\Software\Classes\Directory\shell\DiffAndCompareToolCompare\command]
@="\"\"$regExeEsc\" --compare \"%1\"\""

[HKEY_CURRENT_USER\Software\Classes\Directory\shell\DiffAndCompareToolSelectLeft]
@="diff_and_compare_tool: Select Left"
"Icon"="\"$regIconEsc\""

[HKEY_CURRENT_USER\Software\Classes\Directory\shell\DiffAndCompareToolSelectLeft\command]
@="\"\"$regExeEsc\" --select-left \"%1\"\""

[HKEY_CURRENT_USER\Software\Classes\Directory\shell\DiffAndCompareToolSelectRight]
@="diff_and_compare_tool: Select Right"
"Icon"="\"$regIconEsc\""

[HKEY_CURRENT_USER\Software\Classes\Directory\shell\DiffAndCompareToolSelectRight\command]
@="\"\"$regExeEsc\" --select-right \"%1\"\""

[HKEY_CURRENT_USER\Software\Classes\Directory\Background\shell\DiffAndCompareToolCompare]
@="Compare with diff_and_compare_tool"
"Icon"="\"$regIconEsc\""

[HKEY_CURRENT_USER\Software\Classes\Directory\Background\shell\DiffAndCompareToolCompare\command]
@="\"\"$regExeEsc\" --compare \"%V\"\""
"@ | Set-Content -Path $regFile -Encoding UTF8

@"
Windows Registry Editor Version 5.00

[-HKEY_CURRENT_USER\Software\Classes\*\shell\DiffAndCompareToolCompare]
[-HKEY_CURRENT_USER\Software\Classes\*\shell\DiffAndCompareToolSelectLeft]
[-HKEY_CURRENT_USER\Software\Classes\*\shell\DiffAndCompareToolSelectRight]
[-HKEY_CURRENT_USER\Software\Classes\Directory\shell\DiffAndCompareToolCompare]
[-HKEY_CURRENT_USER\Software\Classes\Directory\shell\DiffAndCompareToolSelectLeft]
[-HKEY_CURRENT_USER\Software\Classes\Directory\shell\DiffAndCompareToolSelectRight]
[-HKEY_CURRENT_USER\Software\Classes\Directory\Background\shell\DiffAndCompareToolCompare]
"@ | Set-Content -Path $unregFile -Encoding UTF8

Write-InstallerLog "==========================================================" "Green"
Write-InstallerLog "  Installation Completed Successfully!" "Green"
Write-InstallerLog "==========================================================" "Green"
Write-InstallerLog "Installed to: $InstallDir" "White"
Write-InstallerLog "Quick Start:" "Yellow"
Write-InstallerLog "  1. Right-click any file or directory -> 'Compare with diff_and_compare_tool'" "White"
Write-InstallerLog "  2. Run via Win+R: type 'diff_and_compare' and press Enter" "White"
Write-InstallerLog "  3. Launch from Start Menu or Desktop shortcut" "White"
Write-InstallerLog "To uninstall, run: '$uninstallCmd' or visit Windows 'Installed Apps'" "Cyan"
