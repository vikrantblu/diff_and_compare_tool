@echo off
setlocal
title diff_and_compare_tool Setup

echo ========================================================
echo   Launching diff_and_compare_tool Installer...
echo ========================================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-DiffAndCompare.ps1" %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Installation failed with exit code %ERRORLEVEL%.
) else (
    echo.
    echo Setup completed successfully.
)

echo.
pause
