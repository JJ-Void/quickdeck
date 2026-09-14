@echo off
chcp 65001 >nul
title QuickDeck - cleanup
cd /d "%~dp0"

echo.
echo   Removing build leftovers, screenshots and debug files.
echo   Source code, presets, settings and dist\ are kept.
echo.

if exist "build" rmdir /s /q "build"
if exist "QuickDeck.spec" del /q "QuickDeck.spec"
if exist "quickdeck\__pycache__" rmdir /s /q "quickdeck\__pycache__"
if exist "__pycache__" rmdir /s /q "__pycache__"

del /q "preview_*.png" 2>nul
del /q "quickdeck-update.zip" 2>nul
del /q "setup-deps.bat" 2>nul
del /q "diag.bat" 2>nul
del /q "diag.py" 2>nul
del /q "build-installer.bat" 2>nul
del /q "icon_preview.png" 2>nul

echo   Kept:
echo     quickdeck\  presets\  dist\
echo     run.py  requirements.txt  quickdeck.json
echo     build.bat  build-onefile.bat  start.bat  install.bat  version_info.txt
echo     README.md  ANTIVIRUS.md
echo.
echo   Done.
echo.
pause
