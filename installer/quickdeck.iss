; Установщик QuickDeck на Inno Setup — стандартный для Windows формат.
; Собирается командой: ISCC.exe installer\quickdeck.iss
; На GitHub Actions Inno Setup уже установлен, ставить локально ничего не нужно.

#define AppName      "QuickDeck"
#define AppVersion   "1.0.0"
#define AppPublisher "QuickDeck"
#define AppURL       "https://github.com/JJ-Void/quickdeck"
#define AppExe       "QuickDeck.exe"

[Setup]
AppId={{7C4E1F60-3A2B-4D51-9D0C-9B3E2F8A55E1}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}/releases
VersionInfoVersion={#AppVersion}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName} installer
; ставим в профиль пользователя — без прав администратора и запроса UAC
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableDirPage=auto
OutputDir=..\dist
OutputBaseFilename=QuickDeck-Setup-{#AppVersion}
SetupIconFile=..\quickdeck\assets\quickdeck.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "startup"; Description: "Запускать QuickDeck при входе в Windows"; GroupDescription: "Дополнительно:"

[Files]
Source: "..\dist\QuickDeck\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon
Name: "{userstartup}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: startup

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\_internal"
