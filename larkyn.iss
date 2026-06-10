; Inno Setup script for Larkyn.
; Build (after PyInstaller):  ISCC.exe installer\larkyn.iss
; Produces dist\installer\LarkynSetup.exe

#define AppName "Larkyn"
#define AppVersion "0.2.1"
#define AppPublisher "Dermatology Solutions Group"
#define AppExeName "Larkyn.exe"

[Setup]
AppId={{B7D31C2E-9A5F-4E8B-8D2C-6F1A3E9B0C4D}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist\installer
OutputBaseFilename=LarkynSetup
SetupIconFile=..\assets\larkyn.ico
UninstallDisplayIcon={app}\{#AppExeName}
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"
Name: "autostart"; Description: "Start {#AppName} automatically when I sign in (runs minimized in the tray)"; GroupDescription: "Startup:"

[Files]
Source: "..\dist\Larkyn\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Comment: "Voice to polished writing. 100% local."
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Parameters: "--minimized"; Tasks: autostart

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; App data (config/history/logs in %APPDATA%\Larkyn) is preserved on uninstall.
Type: filesandordirs; Name: "{app}"
