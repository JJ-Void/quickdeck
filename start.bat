@echo off
chcp 65001 >nul
title QuickDeck
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo   Python not found. Install Python 3.10+ from python.org with "Add python.exe to PATH".
  pause
  exit /b 1
)
python -c "import PySide6, pynput" 2>nul
if errorlevel 1 (
  echo   Dependencies missing. Run install.bat first.
  pause
  exit /b 1
)
echo.
echo   Starting QuickDeck. Tray icon appears near the clock.
echo   Keep this window open - errors show up here.
echo.
python run.py
echo.
echo   QuickDeck exited. If there is an error above, send it to Claude.
pause
