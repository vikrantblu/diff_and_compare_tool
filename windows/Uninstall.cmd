@echo off
setlocal
title diff_and_compare_tool Uninstaller

echo ========================================================
echo   Launching diff_and_compare_tool Uninstaller...
echo ========================================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Uninstall-DiffAndCompare.ps1" %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Uninstallation encountered warnings or errors (exit code %ERRORLEVEL%).
) else (
    echo.
    echo Uninstallation completed successfully.
)

echo.
pause
