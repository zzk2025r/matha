# Inno Setup 安装脚本 — Matha 独立可执行文件安装程序
#
# 功能:
# - 安装 matha.exe 和 matha-cc.exe 到指定目录
# - 创建桌面快捷方式
# - 创建开始菜单快捷方式
# - 添加到系统 PATH
# - 添加卸载程序
#
# 编译命令 (需要 Inno Setup 6.x，从仓库根运行):
#   iscc scripts\matha_installer.iss /DVersion=4.6.0
# 相对路径基准由 [Setup] SourceDir=.. 定为仓库根（本文件住在 scripts\ 下——
# 旧写法没有 SourceDir，所有 Source 一律按 .iss 所在目录解析，指向
# scripts\matha-offline\matha.exe 这类早就不存在的路径，iscc 直接编译失败）。

; 版本号单一来源 = src\__version__.py 的内容，命令行 /DVersion= 传入；
; 未传时回落到与 src\__version__.py 同步的字面值（不写死旧版号）。
#ifndef Version
  #define Version "4.6.0"
#endif

[Setup]
AppName=Matha
AppVersion={#Version}
AppVerName=Matha {#Version}
DefaultDirName={commonpf}\Matha
DefaultGroupName=Matha
; dist\ 平铺产物（与 scripts\build.bat / .github\workflows\build.yml /
; scripts\build_exe.py 同口径），不再是已退役的 matha-offline\ 嵌套布局
SourceDir=..
#ifdef OutputDir
OutputDir={#OutputDir}
#else
OutputDir=dist
#endif
OutputBaseFilename=Matha-Setup-{#Version}-Windows-x64
UninstallDisplayIcon={app}\matha.exe
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=admin
WizardStyle=modern
; 安装后启动
; ShowNotes=yes

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "快捷方式:"; Flags: checkedonce
Name: "quicklaunchicon"; Description: "创建快速启动栏快捷方式"; GroupDescription: "快捷方式:"; Flags: checkedonce
Name: "startmenuicon"; Description: "创建开始菜单快捷方式"; GroupDescription: "快捷方式:"; Flags: checkedonce
Name: "addtopath"; Description: "添加到系统 PATH 环境变量"; GroupDescription: "高级选项:"

[Files]
Source: "dist\matha.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\matha-cc.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "scripts\*"; DestDir: "{app}\scripts"; Flags: ignoreversion recursesubdirs createallsubdirs Excludes: "*.log,__pycache__\*"
Source: "docs\*.md"; DestDir: "{app}\docs"; Flags: ignoreversion
; src 全子包递归（旧写法只列 compiler/domains/offline/stdlib 四片，
; 装出来的树缺 src\kernel 与 src\mbc——解释器与 VM 根本 import 不起来）
Source: "src\*.py"; DestDir: "{app}\src"; Flags: ignoreversion recursesubdirs Excludes: "*.pyc"
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
    MsgBox('Matha v{#Version} 安装成功！'#13#13'桌面快捷方式已创建。'#13'双击 "Matha REPL" 启动交互式使用。', mbInformation, MB_OK);
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
