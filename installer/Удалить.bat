@echo off
chcp 65001 >nul
title QuickDeck - uninstall
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0uninstall.ps1"
