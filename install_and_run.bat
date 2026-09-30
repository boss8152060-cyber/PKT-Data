@echo off
REM =========================================================================
REM Double-click this file once. It will automatically install:
REM Python 3.12, PyTorch (GPU or CPU depending on your machine), ultralytics,
REM opencv-python, pillow, pyyaml
REM Then it will open PK Studio for you at the end.
REM
REM First run may take a few minutes (needs to download large files).
REM Requires an internet connection.
REM After the first successful run, use "run_app.bat" instead - it is faster.
REM =========================================================================

title Installing PK Studio...
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"

echo.
echo Press any key to close this window...
pause >nul
