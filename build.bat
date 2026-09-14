@echo off
chcp 65001 >nul
title QuickDeck - build
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo   Python not found. Install Python 3.10+ from python.org with "Add python.exe to PATH".
  pause
  exit /b 1
)
echo.
echo   Installing build dependencies...
python -m pip install --upgrade "pynput>=1.8" "PySide6>=6.6" pyinstaller
if errorlevel 1 (
  echo   Failed to install dependencies.
  pause
  exit /b 1
)
echo.
echo   Building QuickDeck (folder build - fewer antivirus false positives)...
python -m PyInstaller --noconfirm --clean --onedir --windowed --noupx --name QuickDeck ^
  --icon "quickdeck/assets/quickdeck.ico" ^
  --version-file "version_info.txt" ^
  --add-data "quickdeck/assets;quickdeck/assets" ^
  --add-data "presets;presets" ^
  --hidden-import pynput.keyboard._win32 --hidden-import pynput.mouse._win32 ^
  --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtQuick ^
  --exclude-module PySide6.Qt3DCore --exclude-module PySide6.QtMultimedia ^
  --exclude-module tkinter ^
  run.py
if errorlevel 1 (
  echo   Build failed. Send the error above to Claude.
  pause
  exit /b 1
)
if not exist "dist\QuickDeck\presets" mkdir "dist\QuickDeck\presets"
copy /y "presets\*.json" "dist\QuickDeck\presets\" >nul
echo.
echo ==========================================================
echo   Done: %~dp0dist\QuickDeck\QuickDeck.exe
echo.
echo   Share the WHOLE dist\QuickDeck folder (zip it).
echo   If Kaspersky still removes the file, read ANTIVIRUS.md
echo ==========================================================
echo.
pause
