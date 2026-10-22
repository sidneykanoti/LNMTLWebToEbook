@echo off
cd /d "%~dp0"
python -m venv .venv
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
set PLAYWRIGHT_BROWSERS_PATH=0
".venv\Scripts\python.exe" -m playwright install chromium --only-shell
if errorlevel 1 goto failed
echo Setup complete. Double-click Start Library.cmd to open the app.
pause
exit /b 0
:failed
echo Setup failed. Check that Python 3.11 or later is installed and your internet connection is working.
pause
exit /b 1
