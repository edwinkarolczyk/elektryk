@echo off
title Domowy Elektryk - Uruchamianie
echo ============================================
echo   DOMOWY ELEKTRYK - uruchamianie programu
echo ============================================

REM --- sprawdzenie folderu projektu ---
set PROJECT_DIR=%~dp0
cd /d "%PROJECT_DIR%"

REM --- sprawdzenie czy python jest zainstalowany ---
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [BŁĄD] Nie znaleziono Pythona w systemie.
    echo Pobierz i zainstaluj: https://www.python.org/downloads/
    pause
    exit /b
)

REM --- tworzenie wirtualnego środowiska ---
if not exist venv (
    echo Tworzenie środowiska wirtualnego...
    python -m venv venv
)

REM --- aktywacja środowiska ---
call venv\Scripts\activate.bat

REM --- instalacja wymaganych bibliotek ---
echo Instalowanie wymaganych pakietów...
python -m pip install --upgrade pip >nul
python -m pip install PyQt6 reportlab >nul

REM --- uruchomienie programu ---
echo.
echo Uruchamianie programu Domowy Elektryk...
echo (zamknij okno, aby zakończyć)
echo.
python elektryk.py

REM --- po zakończeniu ---
echo.
echo Program został zamknięty.
pause
