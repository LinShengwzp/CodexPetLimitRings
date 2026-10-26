@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Autostart.ps1" -Mode Install
if errorlevel 1 (
  echo.
  echo Failed to enable autostart.
) else (
  echo.
  echo Autostart enabled. It will run at the next Windows sign-in.
)
pause
