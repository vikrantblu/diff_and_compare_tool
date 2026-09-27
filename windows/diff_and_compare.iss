; Inno Setup 6 Script for diff_and_compare_tool
; Builds standalone setup executable: Setup_diff_and_compare_tool.exe
; Installs per-user (no admin rights required) or system-wide.

#define MyAppName "diff_and_compare_tool"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "diff_and_compare_tool"
#define MyAppURL "https://github.com/vikrantblu/diff_and_compare_tool"
#define MyAppExeName "diff_and_compare.exe"

[Setup]
AppId={{E681BC45-8B29-45C0-94C3-956BDFF5F810}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist
OutputBaseFilename=Setup_diff_and_compare_tool
SetupIconFile=..\assets\app_icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
ChangesAssociations=yes
ChangesEnvironment=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "contextmenu"; Description: "Register Windows Explorer right-click context menu"; GroupDescription: "Windows Shell Integration:"; Flags: checkedonce
Name: "apppaths"; Description: "Register App Paths (launch via Win+R or Command Prompt)"; GroupDescription: "Windows Shell Integration:"; Flags: checkedonce

[Files]
Source: "..\dist\diff_and_compare\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\assets\app_icon.ico"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "Install-DiffAndCompare.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "Uninstall-DiffAndCompare.ps1"; DestDir: "{app}"; DestName: "uninstall.ps1"; Flags: ignoreversion
Source: "Uninstall.cmd"; DestDir: "{app}"; DestName: "uninstall.cmd"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\app_icon.ico"; Comment: "Multi-Format Diff & 3-Way Merge Studio"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\app_icon.ico"; Tasks: desktopicon

[Registry]
; 1. Explorer Context Menu: All Files
Root: HKCU; Subkey: "Software\Classes\*\shell\DiffAndCompareToolCompare"; ValueType: string; ValueData: "Compare with diff_and_compare_tool"; Tasks: contextmenu; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\*\shell\DiffAndCompareToolCompare"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\assets\app_icon.ico"""; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\*\shell\DiffAndCompareToolCompare\command"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"" --compare ""%1"""; Tasks: contextmenu

Root: HKCU; Subkey: "Software\Classes\*\shell\DiffAndCompareToolSelectLeft"; ValueType: string; ValueData: "diff_and_compare_tool: Select Left"; Tasks: contextmenu; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\*\shell\DiffAndCompareToolSelectLeft"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\assets\app_icon.ico"""; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\*\shell\DiffAndCompareToolSelectLeft\command"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"" --select-left ""%1"""; Tasks: contextmenu

Root: HKCU; Subkey: "Software\Classes\*\shell\DiffAndCompareToolSelectRight"; ValueType: string; ValueData: "diff_and_compare_tool: Select Right"; Tasks: contextmenu; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\*\shell\DiffAndCompareToolSelectRight"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\assets\app_icon.ico"""; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\*\shell\DiffAndCompareToolSelectRight\command"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"" --select-right ""%1"""; Tasks: contextmenu

; 2. Explorer Context Menu: Directories
Root: HKCU; Subkey: "Software\Classes\Directory\shell\DiffAndCompareToolCompare"; ValueType: string; ValueData: "Compare with diff_and_compare_tool"; Tasks: contextmenu; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\Directory\shell\DiffAndCompareToolCompare"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\assets\app_icon.ico"""; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\Directory\shell\DiffAndCompareToolCompare\command"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"" --compare ""%1"""; Tasks: contextmenu

Root: HKCU; Subkey: "Software\Classes\Directory\shell\DiffAndCompareToolSelectLeft"; ValueType: string; ValueData: "diff_and_compare_tool: Select Left"; Tasks: contextmenu; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\Directory\shell\DiffAndCompareToolSelectLeft"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\assets\app_icon.ico"""; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\Directory\shell\DiffAndCompareToolSelectLeft\command"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"" --select-left ""%1"""; Tasks: contextmenu

Root: HKCU; Subkey: "Software\Classes\Directory\shell\DiffAndCompareToolSelectRight"; ValueType: string; ValueData: "diff_and_compare_tool: Select Right"; Tasks: contextmenu; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\Directory\shell\DiffAndCompareToolSelectRight"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\assets\app_icon.ico"""; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\Directory\shell\DiffAndCompareToolSelectRight\command"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"" --select-right ""%1"""; Tasks: contextmenu

; 3. Explorer Context Menu: Directory Background
Root: HKCU; Subkey: "Software\Classes\Directory\Background\shell\DiffAndCompareToolCompare"; ValueType: string; ValueData: "Compare with diff_and_compare_tool"; Tasks: contextmenu; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\Directory\Background\shell\DiffAndCompareToolCompare"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\assets\app_icon.ico"""; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\Directory\Background\shell\DiffAndCompareToolCompare\command"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"" --compare ""%V"""; Tasks: contextmenu

; 4. App Paths (Win+R / CMD launch)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\App Paths\diff_and_compare.exe"; ValueType: string; ValueData: "{app}\{#MyAppExeName}"; Tasks: apppaths; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\App Paths\diff_and_compare.exe"; ValueType: string; ValueName: "Path"; ValueData: "{app}"; Tasks: apppaths
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\App Paths\diff_and_compare_tool.exe"; ValueType: string; ValueData: "{app}\{#MyAppExeName}"; Tasks: apppaths; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\App Paths\diff_and_compare_tool.exe"; ValueType: string; ValueName: "Path"; ValueData: "{app}"; Tasks: apppaths

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
