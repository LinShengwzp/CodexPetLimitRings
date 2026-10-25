@echo off
setlocal
cd /d "%~dp0"
where pythonw.exe >nul 2>&1
if not errorlevel 1 (
  start "" pythonw.exe "%~dp0main.py"
  exit /b
)
python.exe "%~dp0main.py"
pause
