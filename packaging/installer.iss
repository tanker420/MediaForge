; MediaForge Windows 安装程序脚本 (Inno Setup 6)
; 编译： iscc packaging\installer.iss

#define MyAppName "MediaForge"
#define MyAppNameCN "MediaForge 全能格式转换器"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "MediaForge"
#define MyAppExeName "MediaForge.exe"

[Setup]
AppId={{7C4B1E36-2F58-4A9D-9E31-5B8A1D0C7F42}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppNameCN} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=..\LICENSE
OutputDir=..\dist_installer
OutputBaseFilename=MediaForge-{#MyAppVersion}-Setup
SetupIconFile=..\app\resources\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
PrivilegesRequiredOverridesAllowed=dialog
MinVersion=10.0

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Default.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加快捷方式:"
Name: "addtopath"; Description: "把 MediaForge 加入系统 PATH（可在命令行使用）"; GroupDescription: "其它:"; Flags: unchecked
Name: "contextmenu"; Description: "在文件右键菜单中添加“用 MediaForge 转换”"; GroupDescription: "其它:"

[Files]
Source: "..\dist\MediaForge\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\MediaForge\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion isreadme

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; 右键菜单（对所有文件生效）
Root: HKA; Subkey: "Software\Classes\*\shell\MediaForge"; ValueType: string; ValueName: ""; ValueData: "用 MediaForge 转换"; Tasks: contextmenu; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\*\shell\MediaForge"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\{#MyAppExeName}"; Tasks: contextmenu
Root: HKA; Subkey: "Software\Classes\*\shell\MediaForge\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: contextmenu
; 文件夹右键菜单
Root: HKA; Subkey: "Software\Classes\Directory\shell\MediaForge"; ValueType: string; ValueName: ""; ValueData: "用 MediaForge 批量转换"; Tasks: contextmenu; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Directory\shell\MediaForge\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: contextmenu

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "立即运行 {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
const EnvKey = 'System\CurrentControlSet\Control\Session Manager\Environment';

function NeedsAddPath(Param: string): boolean;
var
  OrigPath: string;
begin
  if not RegQueryStringValue(HKLM, EnvKey, 'Path', OrigPath) then
  begin
    Result := True;
    exit;
  end;
  Result := Pos(';' + Param + ';', ';' + OrigPath + ';') = 0;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  OrigPath: string;
begin
  if (CurStep = ssPostInstall) and WizardIsTaskSelected('addtopath') then
  begin
    if NeedsAddPath(ExpandConstant('{app}')) then
    begin
      RegQueryStringValue(HKLM, EnvKey, 'Path', OrigPath);
      RegWriteExpandStringValue(HKLM, EnvKey, 'Path',
        OrigPath + ';' + ExpandConstant('{app}'));
    end;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  OrigPath: string;
  AppDir: string;
  P: Integer;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    AppDir := ExpandConstant('{app}');
    if RegQueryStringValue(HKLM, EnvKey, 'Path', OrigPath) then
    begin
      P := Pos(';' + AppDir, OrigPath);
      if P > 0 then
      begin
        Delete(OrigPath, P, Length(';' + AppDir));
        RegWriteExpandStringValue(HKLM, EnvKey, 'Path', OrigPath);
      end;
    end;
  end;
end;
