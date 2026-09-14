@echo off
chcp 65001 >nul
title QuickDeck - package for sharing
cd /d "%~dp0"

if not exist "dist\QuickDeck\QuickDeck.exe" (
  echo   dist\QuickDeck\QuickDeck.exe not found. Run build.bat first.
  pause
  exit /b 1
)

echo.
echo   Preparing a clean copy for sharing...
echo   Your quickdeck.json is NOT included - the other person starts fresh.
echo.

if exist "share" rmdir /s /q "share"
mkdir "share"
robocopy "dist\QuickDeck" "share\QuickDeck" /e /xf quickdeck.json >nul
if errorlevel 8 (
  echo   Copy failed.
  pause
  exit /b 1
)

echo   Presets included in the package:
dir /b "share\QuickDeck\presets\*.json" 2>nul
echo.
choice /c YN /n /m "   Keep all of them? [Y/N] "
if errorlevel 2 (
  echo.
  echo   Opening the presets folder - delete what should not be shared,
  echo   then come back to this window.
  start "" "%~dp0share\QuickDeck\presets"
  pause
)

echo.
echo   Creating archive...
powershell -NoProfile -Command "Compress-Archive -Path 'share\QuickDeck' -DestinationPath 'share\QuickDeck.zip' -Force"
if not exist "share\QuickDeck.zip" (
  echo   Archive failed. You can zip the share\QuickDeck folder manually.
  pause
  exit /b 1
)

for %%F in ("share\QuickDeck.zip") do set SIZE=%%~zF
echo.
echo ==========================================================
echo   Ready: %~dp0share\QuickDeck.zip
echo   Size in bytes: %SIZE%
echo.
echo   Send this archive. The person unpacks it anywhere
echo   and runs QuickDeck.exe - nothing to install.
echo ==========================================================
echo.
start "" "%~dp0share"
pause
