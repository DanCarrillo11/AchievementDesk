#ifndef BuildSource
  #define BuildSource "dist\SteamAchievementManager"
#endif
#ifndef OutputFolder
  #define OutputFolder "installer-output"
#endif
[Setup]
AppId={{C40ABBD0-6868-467A-AC2D-D27F4E53B01A}
AppName=SteamAchievementManager
AppVersion=1.3.0
AppPublisher=DanCarrillo11
AppPublisherURL=https://github.com/DanCarrillo11/AchievementDesk
AppSupportURL=https://github.com/DanCarrillo11/AchievementDesk/issues
AppUpdatesURL=https://github.com/DanCarrillo11/AchievementDesk/releases/latest
DefaultDirName={localappdata}\Programs\SteamAchievementManager
DefaultGroupName=SteamAchievementManager
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputFolder}
OutputBaseFilename=SteamAchievementManager-1.3.0-Setup
SetupIconFile=assets\app.ico
UninstallDisplayIcon={app}\SteamAchievementManager.exe
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
[InstallDelete]
Type: files; Name: "{app}\AchievementDesk.exe"
Type: files; Name: "{app}\AchievementDeskWorker.exe"
Type: files; Name: "{group}\Achievement Desk.lnk"
Type: files; Name: "{autodesktop}\Achievement Desk.lnk"
[Icons]
Name: "{group}\SteamAchievementManager"; Filename: "{app}\SteamAchievementManager.exe"; AppUserModelID: "DanCarrillo11.AchievementDesk"
Name: "{autodesktop}\SteamAchievementManager"; Filename: "{app}\SteamAchievementManager.exe"; Tasks: desktopicon; AppUserModelID: "DanCarrillo11.AchievementDesk"
[Run]
Filename: "{app}\SteamAchievementManager.exe"; Description: "Open SteamAchievementManager"; Flags: nowait postinstall skipifsilent unchecked
; User preferences, cache and history live outside {app} and are retained on uninstall.
