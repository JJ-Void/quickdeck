@echo off
chcp 65001 >nul
title QuickDeck - install dependencies
cd /d "%~dp0"
echo.
echo   Installing PySide6 and pynput. Full pip output below.
echo.
python -m pip install --upgrade pip
echo.
python -m pip install --upgrade "pynput>=1.8" "PySide6>=6.6"
python check_env.py
pause
