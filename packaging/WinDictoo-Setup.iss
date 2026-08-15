; WinDictoo installer (Inno Setup 6).
; Build from the repo root, after building the folder app with WinDictoo.spec:
;   uv run pyinstaller packaging/WinDictoo.spec --noconfirm --distpath dist --workpath build
;   & "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" /DAppVersion=1.8.0 packaging\WinDictoo-Setup.iss
; Output: dist\WinDictoo-Setup-<version>.exe
;
; Design goals: an installer for non-technical users — no admin rights,
; no terminal, minimal questions (desktop-icon checkbox, then Install → Run).

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
; Same AppId as the previously shipped 1.7.3 installer, so upgrades replace
; the existing install instead of creating a second entry in Apps & Features.
AppId={{F9172409-8B90-43EB-8F2F-9FB8BCC48BFF}
AppName=WinDictoo
AppVersion={#AppVersion}
AppPublisher=nowoandi
AppPublisherURL=https://github.com/nowoandi/WinDictoo
AppSupportURL=https://github.com/nowoandi/WinDictoo/issues
AppUpdatesURL=https://github.com/nowoandi/WinDictoo/releases/latest
; Per-user install (%LOCALAPPDATA%\Programs\WinDictoo): no UAC prompt.
DefaultDirName={userpf}\WinDictoo
PrivilegesRequired=lowest
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
ShowLanguageDialog=no
OutputDir=..\dist
; Name matters: GitHub sorts release assets by name (case-insensitively) and
; WinDictoo up to 1.7.3 downloaded the first .exe it was given. "Installer"
; sorts ahead of "portable", so even those old builds get a real installer.
; Releases also ship no portable .exe any more, which makes this the only
; .exe on the page — belt and braces. Do not rename back to WinDictoo-Setup-*.
OutputBaseFilename=WinDictoo-{#AppVersion}-Installer
SetupIconFile=..\assets\windictoo.ico
UninstallDisplayIcon={app}\WinDictoo.exe
UninstallDisplayName=WinDictoo
VersionInfoVersion={#AppVersion}.0
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
MinVersion=10.0
; We close the app ourselves in PrepareToInstall; RestartManager would stall
; on the tray icon.
CloseApplications=no

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; PyInstaller's private folder is replaced wholesale so stale libraries from
; an older version can never mix with the new ones.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist\WinDictoo\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{userprograms}\WinDictoo"; Filename: "{app}\WinDictoo.exe"
Name: "{userdesktop}\WinDictoo"; Filename: "{app}\WinDictoo.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\WinDictoo.exe"; Description: "{cm:LaunchProgram,WinDictoo}"; Flags: nowait postinstall skipifsilent

[Code]
procedure TaskKillApp();
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM WinDictoo.exe', '',
    SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  { A running copy (tray) would lock the files being replaced. }
  TaskKillApp();
  Result := '';
end;

function InitializeUninstall(): Boolean;
begin
  TaskKillApp();
  Result := True;
end;
