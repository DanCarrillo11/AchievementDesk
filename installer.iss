#ifndef BuildSource
  #define BuildSource "dist\AchievementDesk"
#endif
#ifndef OutputFolder
  #define OutputFolder "installer-output"
#endif
[Setup]
AppId={{C40ABBD0-6868-467A-AC2D-D27F4E53B01A}
AppName=Achievement Desk
AppVersion=1.1.0
AppPublisher=DanCarrillo11
AppPublisherURL=https://github.com/DanCarrillo11/AchievementDesk
AppSupportURL=https://github.com/DanCarrillo11/AchievementDesk/issues
AppUpdatesURL=https://github.com/DanCarrillo11/AchievementDesk/releases/latest
DefaultDirName={localappdata}\Programs\Achievement Desk
DefaultGroupName=Achievement Desk
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputFolder}
OutputBaseFilename=AchievementDesk-1.1.0-Setup
SetupIconFile=assets\app.ico
UninstallDisplayIcon={app}\AchievementDesk.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
LicenseFile=LICENSE
CloseApplications=yes
RestartApplications=no
AppMutex=AchievementDeskInstaller
[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked
[Files]
Source: "{#BuildSource}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\Achievement Desk"; Filename: "{app}\AchievementDesk.exe"; AppUserModelID: "DanCarrillo11.AchievementDesk"
Name: "{autodesktop}\Achievement Desk"; Filename: "{app}\AchievementDesk.exe"; Tasks: desktopicon; AppUserModelID: "DanCarrillo11.AchievementDesk"
[Run]
Filename: "{app}\AchievementDesk.exe"; Description: "Open Achievement Desk"; Flags: nowait postinstall skipifsilent unchecked
; User preferences, cache and history live outside {app} and are retained on uninstall.
