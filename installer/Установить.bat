@echo off
chcp 65001 >nul
title QuickDeck - install
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
pause
