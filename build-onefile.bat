@echo off
chcp 65001 >nul
title QuickDeck - build single exe
cd /d "%~dp0"
echo.
echo   WARNING: single-file build unpacks itself into %%TEMP%% on every start.
echo   Antivirus heuristics flag that pattern much more often than a folder build.
echo   Use build.bat unless you really need one file.
echo.
choice /c YN /n /m "   Continue? [Y/N] "
if errorlevel 2 exit /b 0
python -m pip install --upgrade "pynput>=1.8" "PySide6>=6.6" pyinstaller
python -m PyInstaller --noconfirm --clean --onefile --windowed --noupx --name QuickDeck ^
  --icon "quickdeck/assets/quickdeck.ico" ^
  --version-file "version_info.txt" ^
  --add-data "quickdeck/assets;quickdeck/assets" ^
  --add-data "presets;presets" ^
  --hidden-import pynput.keyboard._win32 --hidden-import pynput.mouse._win32 ^
  --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtQuick ^
  --exclude-module PySide6.Qt3DCore --exclude-module PySide6.QtMultimedia ^
  run.py
if not exist "dist\presets" mkdir "dist\presets"
copy /y "presets\*.json" "dist\presets\" >nul
echo.
echo   Done: %~dp0dist\QuickDeck.exe
pause
