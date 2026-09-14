@echo off
chcp 65001 >nul
title QuickDeck - apply update
cd /d "%~dp0"
echo.
echo   Unpacking quickdeck-update.zip ...
python -c "import zipfile; zipfile.ZipFile('quickdeck-update.zip').extractall('.'); print('   done')"
if errorlevel 1 (
  echo   Failed to unpack. Is Python installed?
  pause
  exit /b 1
)
echo.
echo   Checking dependencies...
python -m pip install --upgrade "pynput>=1.8" "PySide6>=6.6"
python check_env.py
pause
