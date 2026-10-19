[Setup]
AppId={{BA4B931F-2D52-49D1-A8A0-A947807532D0}
AppName=Paperlight
AppVersion=0.8.0
AppPublisher=Paperlight
DefaultDirName={localappdata}\Programs\Paperlight
DefaultGroupName=Paperlight
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=Paperlight-Setup
SetupIconFile=..\assets\paperlight.ico
UninstallDisplayIcon={app}\Paperlight.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
LicenseFile=..\LICENSE
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\Paperlight\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\dist\paperlight-source.zip"; DestDir: "{app}\source"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Paperlight"; Filename: "{app}\Paperlight.exe"
Name: "{group}\Quick guide"; Filename: "{app}\README.md"
Name: "{autodesktop}\Paperlight"; Filename: "{app}\Paperlight.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Paperlight.exe"; Description: "Open Paperlight"; Flags: nowait postinstall skipifsilent
