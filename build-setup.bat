@echo off
chcp 65001 >nul
title QuickDeck - build setup exe
cd /d "%~dp0"
setlocal enableextensions

echo.
echo   === Building QuickDeck-Setup.exe ===
echo.

if not exist "dist\QuickDeck\QuickDeck.exe" goto no_app

where python >nul 2>nul
if errorlevel 1 goto no_python

echo   Installing PyInstaller if needed...
python -m pip install --upgrade pyinstaller >nul
echo   Packing the app into the installer...
echo.

python -m PyInstaller --noconfirm --clean --onefile --windowed --noupx ^
  --name QuickDeck-Setup ^
  --icon "quickdeck\assets\quickdeck.ico" ^
  --add-data "dist\QuickDeck;payload" ^
  --add-data "quickdeck\assets\quickdeck.ico;." ^
  --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtQuick ^
  --exclude-module PySide6.Qt3DCore --exclude-module PySide6.QtMultimedia ^
  --exclude-module tkinter ^
  --distpath dist --workpath build\setup ^
  installer\setup.py
if errorlevel 1 goto failed

echo.
echo ==========================================================
dir /b "dist\QuickDeck-Setup.exe"
echo   Ready: %~dp0dist\QuickDeck-Setup.exe
echo   This single file is what you send to people.
echo ==========================================================
start "" "%~dp0dist"
goto end

:no_app
echo   [!] dist\QuickDeck\QuickDeck.exe not found. Run build.bat first.
goto end

:no_python
echo   [!] Python not found. Install it from python.org with "Add python.exe to PATH".
goto end

:failed
echo.
echo   [!] Build failed. Copy the text above and send it to Claude.
goto end

:end
echo.
pause
