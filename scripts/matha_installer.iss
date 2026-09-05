# Inno Setup 安装脚本 — Matha 独立可执行文件安装程序
#
# 功能:
# - 安装 matha.exe 和 matha-cc.exe 到指定目录
# - 创建桌面快捷方式
# - 创建开始菜单快捷方式
# - 添加到系统 PATH
# - 添加卸载程序
#
# 编译命令 (需要 Inno Setup 6.x):
#   iscc matha_installer.iss /DOutputDir=dist /DVersion=4.4

[Setup]
AppName=Matha
AppVersion=4.4
DefaultDirName={commonpf}\Matha
DefaultGroupName=Matha
OutputDir=.\dist
OutputBaseFilename=Matha-Setup-4.4-Windows-x64
SetupIconFile=matha_icon.ico
UninstallDisplayIcon={app}\matha.exe
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=admin
WizardStyle=modern
LicenseFile=
; 安装后启动
; ShowNotes=yes

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "快捷方式:"; Flags: checkedonce
Name: "quicklaunchicon"; Description: "创建快速启动栏快捷方式"; GroupDescription: "快捷方式:"; Flags: checkedonce
Name: "startmenuicon"; Description: "创建开始菜单快捷方式"; GroupDescription: "快捷方式:"; Flags: checkedonce
Name: "addtopath"; Description: "添加到系统 PATH 环境变量"; GroupDescription: "高级选项:"

[Files]
Source: "matha-offline\matha.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "matha-cc-offline\matha-cc.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "scripts\*"; DestDir: "{app}\scripts"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "docs\*.md"; DestDir: "{app}\docs"; Flags: ignoreversion
Source: "src\*.py"; DestDir: "{app}\src"; Flags: ignoreversion
Source: "src\compiler\*.py"; DestDir: "{app}\src\compiler"; Flags: ignoreversion
Source: "src\domains\*.py"; DestDir: "{app}\src\domains"; Flags: ignoreversion
Source: "src\offline\*.py"; DestDir: "{app}\src\offline"; Flags: ignoreversion
Source: "src\stdlib\*.py"; DestDir: "{app}\src\stdlib"; Flags: ignoreversion
Source: "tests\*.py"; DestDir: "{app}\tests"; Flags: ignoreversion
Source: "pyproject.toml"; DestDir: "{app}"; Flags: ignoreversion
Source: "matha.spec"; DestDir: "{app}"; Flags: ignoreversion
Source: "matha-cc.spec"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "requirements.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; 桌面快捷方式
Name: "{autodesktop}\Matha REPL"; Filename: "{app}\matha.exe"; Tasks: desktopicon
Name: "{autodesktop}\Matha 编译器"; Filename: "{app}\matha-cc.exe"; Tasks: desktopicon
Name: "{autodesktop}\Matha 安装目录"; Filename: "{app}"; Tasks: desktopicon
; 快速启动栏
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\Matha REPL.lnk"; Filename: "{app}\matha.exe"; Tasks: quicklaunchicon
; 开始菜单
Name: "{group}\Matha REPL"; Filename: "{app}\matha.exe"; Tasks: startmenuicon
Name: "{group}\Matha 编译器"; Filename: "{app}\matha-cc.exe"; Tasks: startmenuicon
Name: "{group}\Matha 文档"; Filename: "{app}\docs\OFFLINE_GUIDE.md"; Tasks: startmenuicon
Name: "{group}\Matha 安装目录"; Filename: "{app}"; Tasks: startmenuicon
Name: "{group}\Matha 卸载"; Filename: "{uninstallexe}"; Tasks: startmenuicon
Name: "{group}\打开命令提示符"; Filename: "cmd.exe"; Parameters: "/k cd /d ""{app}"""; Tasks: startmenuicon

[Code]
var
  AddToPathPage: TInputQueryWizardPage;
  PathBacked: Boolean;

function AddToPath(InstallDir: String): Boolean;
var
  PathValue: String;
  NewPath: String;
  ResultCode: Integer;
begin
  Result := False;
  // 读取当前 PATH
  if not RegQueryStringValue(HKLM, 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment', 'PATH', PathValue) then
    PathValue := '';

  // 检查是否已存在
  if Pos(InstallDir, PathValue) > 0 then
  begin
    Result := True;
    Exit;
  end;

  // 添加新路径
  if PathValue <> '' then
    NewPath := PathValue + ';' + InstallDir
  else
    NewPath := InstallDir;

  // 写入注册表
  if RegWriteStringValue(HKLM, 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment', 'PATH', NewPath) then
  begin
    // 通知系统更新 PATH
    SystemParametersInfo(25, 0, nil, 1);
    Result := True;
  end;
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  InstallDir: String;
begin
  if CurStep = ssPostInstall then
  begin
    InstallDir := ExpandConstant('{app}');
    // 添加到 PATH
    if IsTaskSelected('addtopath') then
      AddToPath(InstallDir);

    // 显示完成消息
    MsgBox('Matha v4.4 安装成功！'#13#13'桌面快捷方式已创建。'#13'双击 "Matha REPL" 启动交互式使用。', mbInformation, MB_OK);
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  InstallDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    InstallDir := ExpandConstant('{app}');
    // 从 PATH 中移除
    if IsTaskSelected('addtopath') then
    begin
      var
        PathValue: String;
        NewPath: String;
      begin
        if RegQueryStringValue(HKLM, 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment', 'PATH', PathValue) then
        begin
          NewPath := StringReplace(PathValue, InstallDir + ';', '', [rfReplaceAll, rfIgnoreCase]);
          NewPath := StringReplace(NewPath, ';' + InstallDir, '', [rfReplaceAll, rfIgnoreCase]);
          RegWriteStringValue(HKLM, 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment', 'PATH', NewPath);
        end;
      end;
    end;
  end;
end;

[Run]
Filename: "{app}\matha.exe"; Description: "启动 Matha REPL"; Flags: nowait postinstall skipifsilent unchecked
Filename: "{cmd}"; Parameters: "/k ""cd /d {app}"""; Description: "打开 Matha 命令提示符"; Flags: nowait postinstall skipifsilent unchecked
