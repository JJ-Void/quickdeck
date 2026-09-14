# Установка QuickDeck из портативной папки: копирует программу в профиль
# пользователя, делает ярлыки и регистрирует в списке установленных программ.
# Не требует прав администратора и не создаёт самораспаковывающийся exe,
# на который ругаются антивирусы.
param(
    [string]$Target  = "$env:LOCALAPPDATA\Programs\QuickDeck",
    [switch]$NoDesktop,
    [switch]$NoStartup
)

$ErrorActionPreference = "Stop"
$App    = "QuickDeck"
$Exe    = "QuickDeck.exe"
$Source = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "  Установка $App" -ForegroundColor Cyan
Write-Host "  откуда: $Source"
Write-Host "  куда:   $Target"
Write-Host ""

if (-not (Test-Path (Join-Path $Source $Exe))) {
    Write-Host "  [!] Рядом со скриптом нет $Exe — запустите его из папки программы." -ForegroundColor Red
    Read-Host "  Enter — закрыть"; exit 1
}

if ((Resolve-Path $Source).Path -eq (Resolve-Path -ErrorAction SilentlyContinue $Target).Path) {
    Write-Host "  Программа уже лежит в этой папке — устанавливать некуда." -ForegroundColor Yellow
    Read-Host "  Enter — закрыть"; exit 0
}

Get-Process -Name "QuickDeck" -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Milliseconds 400

Write-Host "  Копирую файлы…"
New-Item -ItemType Directory -Force -Path $Target | Out-Null

# старую версию убираем, но настройки и наборы пользователя не трогаем
Get-ChildItem $Target -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -notin @("quickdeck.json", "presets") } |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

foreach ($item in Get-ChildItem -Path $Source -Exclude "*.ps1", "*.bat") {
    if ($item.PSIsContainer -and $item.Name -eq "presets") {
        # заготовки досыпаем к тем, что уже есть
        New-Item -ItemType Directory -Force -Path (Join-Path $Target "presets") | Out-Null
        Copy-Item "$($item.FullName)\*" -Destination (Join-Path $Target "presets") -Force
    } elseif ($item.PSIsContainer) {
        Copy-Item $item.FullName -Destination $Target -Recurse -Force
    } else {
        Copy-Item $item.FullName -Destination $Target -Force
    }
}

$exePath = Join-Path $Target $Exe
$shell   = New-Object -ComObject WScript.Shell

function New-Shortcut($linkPath) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $linkPath) | Out-Null
    $s = $shell.CreateShortcut($linkPath)
    $s.TargetPath       = $exePath
    $s.WorkingDirectory = $Target
    $s.IconLocation     = $exePath
    $s.Description      = "Быстрый доступ к документам, текстам и папкам"
    $s.Save()
}

Write-Host "  Создаю ярлыки…"
New-Shortcut "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\$App.lnk"
if (-not $NoDesktop) { New-Shortcut "$([Environment]::GetFolderPath('Desktop'))\$App.lnk" }
if (-not $NoStartup) { New-Shortcut "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\$App.lnk" }

Write-Host "  Регистрирую в списке программ…"
$key = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\QuickDeck"
New-Item -Path $key -Force | Out-Null
Set-ItemProperty $key DisplayName     $App
Set-ItemProperty $key DisplayVersion  "1.0.0"
Set-ItemProperty $key Publisher       $App
Set-ItemProperty $key DisplayIcon     $exePath
Set-ItemProperty $key InstallLocation $Target
Set-ItemProperty $key UninstallString "powershell -NoProfile -ExecutionPolicy Bypass -File `"$Target\uninstall.ps1`""
Set-ItemProperty $key NoModify 1 -Type DWord
Set-ItemProperty $key NoRepair 1 -Type DWord

Copy-Item (Join-Path $Source "uninstall.ps1") $Target -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "  Готово. $App установлен." -ForegroundColor Green
Write-Host "  Ярлык в меню «Пуск», удаление — через «Установку и удаление программ»."
Write-Host ""
$run = Read-Host "  Запустить сейчас? [Y/N]"
if ($run -match '^[YyДд]') { Start-Process $exePath }
