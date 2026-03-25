@echo off
setlocal
cd /d "%~dp0"

:: Check for virtual environment
if exist bot-env\Scripts\python.exe (
    echo [Ravenn] Starting via virtual environment...
    bot-env\Scripts\python.exe discord_bot.py
) else (
    echo [Ravenn] Virtual environment not found. Starting via system python...
    python discord_bot.py
)

if %errorlevel% neq 0 (
    echo [Ravenn] Error detected. Press any key to exit.
    pause
)
endlocal
