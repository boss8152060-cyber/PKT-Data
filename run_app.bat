@echo off
REM =========================================================================
REM Use this AFTER you have already run "install_and_run.bat" once.
REM Just opens PK Studio directly - does not check/reinstall anything.
REM
REM If double-clicking this shows an error about Python 3.12 or ultralytics
REM not being found, go back and run "install_and_run.bat" once first.
REM =========================================================================

title PK Studio
cd /d "%~dp0"

py -3.12 "%~dp0main.py"

if errorlevel 1 (
    echo.
    echo Failed to open PK Studio - setup may not be complete.
    echo Please run "install_and_run.bat" first.
    echo.
    pause
)
