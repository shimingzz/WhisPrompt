@echo off
rem WhisPrompt one-time setup: venv + dependencies
cd /d "%~dp0.."
if not exist .venv (
    python -m venv .venv
)
.venv\Scripts\pip install -r windows\requirements.txt
echo.
echo Setup complete. Run windows\run.bat to start WhisPrompt.
pause
