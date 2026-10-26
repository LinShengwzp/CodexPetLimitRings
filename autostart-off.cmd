@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Autostart.ps1" -Mode Remove
if errorlevel 1 (
  echo.
  echo Failed to disable autostart.
) else (
  echo.
  echo Autostart disabled. The current rings process is unchanged.
)
pause
