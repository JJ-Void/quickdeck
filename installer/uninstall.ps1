# Удаление QuickDeck: ярлыки, запись в реестре и папка программы.
# Настройки в %APPDATA%\QuickDeck остаются — их можно удалить вручную.
$App    = "QuickDeck"
$Target = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "  Удаление $App из папки:" -ForegroundColor Cyan
Write-Host "  $Target"
Write-Host ""
$ans = Read-Host "  Удалить? [Y/N]"
if ($ans -notmatch '^[YyДд]') { exit 0 }

Get-Process -Name "QuickDeck" -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Milliseconds 400

@(
    "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\$App.lnk",
    "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\$App.lnk",
    "$([Environment]::GetFolderPath('Desktop'))\$App.lnk"
) | ForEach-Object { Remove-Item $_ -Force -ErrorAction SilentlyContinue }

Remove-Item "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\QuickDeck" -Recurse -Force -ErrorAction SilentlyContinue
Remove-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name $App -ErrorAction SilentlyContinue

# папку сносим отложенно — скрипт сейчас выполняется изнутри неё
$bat = Join-Path $env:TEMP "quickdeck_remove.bat"
@"
@echo off
ping 127.0.0.1 -n 3 >nul
rmdir /s /q "$Target"
del /q "%~f0"
"@ | Set-Content -Path $bat -Encoding ASCII
Start-Process "cmd" -ArgumentList "/c", $bat -WindowStyle Hidden

Write-Host ""
Write-Host "  $App удалён." -ForegroundColor Green
Start-Sleep -Seconds 2
