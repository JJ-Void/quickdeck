@echo off
chcp 65001 >nul
title QuickDeck - build installer
cd /d "%~dp0"
setlocal enableextensions

echo.
echo   === QuickDeck installer (Inno Setup) ===
echo.
echo   Note: the release installer is normally built on GitHub Actions,
echo   where Inno Setup is already installed. This script is for local builds.
echo.

if not exist "dist\QuickDeck\QuickDeck.exe" goto no_app

set "ISCC="
call :find_iscc
if not "%ISCC%"=="" goto compile

echo   Inno Setup 6 not found. Install it from https://jrsoftware.org/isdl.php
echo   or push a tag to GitHub and let the build run there.
goto end

:compile
echo   Using: %ISCC%
echo.
"%ISCC%" "installer\quickdeck.iss"
if errorlevel 1 goto failed
echo.
echo ==========================================================
dir /b "dist\QuickDeck-Setup-*.exe"
echo ==========================================================
start "" "%~dp0dist"
goto end

:find_iscc
set "P1=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
set "P2=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if exist "%P1%" set "ISCC=%P1%"
if exist "%P2%" set "ISCC=%P2%"
exit /b

:no_app
echo   [!] dist\QuickDeck\QuickDeck.exe not found. Run build.bat first.
goto end

:failed
echo   [!] Compilation failed. Copy the text above and send it to Claude.
goto end

:end
echo.
pause
