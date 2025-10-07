@echo off
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Brak Pythona 3.11+. Zainstaluj i sprobuj ponownie.
  pause
  exit /b 1
)
python elektryka.py
pause
