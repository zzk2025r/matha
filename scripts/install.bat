@echo off
chcp 65001 >nul 2>nul
REM ============================================================
REM Matha Windows 安装程序（批处理版本）
REM 双支持：管理员权限 + 用户权限安装
REM ============================================================
REM 用法:
REM   install.bat              以管理员权限安装
REM   install.bat /user        以当前用户权限安装
REM   install.bat /uninstall   卸载
REM ============================================================

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
REM 本脚本住在 scripts\ 下：仓库根是它的上一级，dist\ src\ docs\ tests\ 与
REM pyproject.toml 全在根上——旧写法把这些一律拼在 %SCRIPT_DIR% 之后（即
REM scripts\dist、scripts\src…），所有 if exist 恒假，脚本却照样打印
REM 「安装完成！」，属假成功。
for %%I in ("%SCRIPT_DIR%..") do set "REPO_ROOT=%%~fI"
set "INSTALL_DIR=C:\Program Files\Matha"
REM 版本号单一来源 = src\__version__.py（安装脚本不各自硬编，避免与 matha --version 打架）
set "VERSION="
for /f "tokens=2 delims== " %%V in ('findstr /b "__version__" "%REPO_ROOT%\src\__version__.py"') do set "VERSION=%%V"
set VERSION=%VERSION:"=%
if not defined VERSION set "VERSION=未知"

echo ============================================================
echo   Matha v%VERSION% Windows 安装程序
echo ============================================================
echo.

REM 检查是否已安装
if exist "%INSTALL_DIR%\matha.exe" (
    echo [信息] Matha 已安装在: %INSTALL_DIR%
    echo 如需重新安装，请先运行卸载入口（见「Matha 卸载」快捷方式或 %LOCALAPPDATA%\Matha\uninstall.bat）
    echo.
    pause
    exit /b 0
)

REM 创建安装目录
echo 创建安装目录: %INSTALL_DIR%
mkdir "%INSTALL_DIR%" 2>nul
if not exist "%INSTALL_DIR%" (
    echo [错误] 无法创建安装目录，请以管理员身份运行
    pause
    exit /b 1
)

REM 复制主程序（产物落点 = 构建入口的扁平 dist\<名>.exe；缺件即失败，不报假成功）
echo.
echo 复制安装文件...
if not exist "%REPO_ROOT%\dist\matha.exe" (
    echo [错误] 缺少 dist\matha.exe，请先构建: scripts\build.bat 或 python scripts\build_exe.py --matha
    pause
    exit /b 1
)
copy "%REPO_ROOT%\dist\matha.exe" "%INSTALL_DIR%\" >nul
if errorlevel 1 (
    echo [错误] 复制 dist\matha.exe 到 %INSTALL_DIR% 失败
    pause
    exit /b 1
)
echo   ✓ matha.exe
if exist "%REPO_ROOT%\dist\matha-cc.exe" (
    copy "%REPO_ROOT%\dist\matha-cc.exe" "%INSTALL_DIR%\" >nul
    if errorlevel 1 (
        echo [错误] 复制 dist\matha-cc.exe 失败
        pause
        exit /b 1
    )
    echo   ✓ matha-cc.exe
) else (
    echo   - matha-cc.exe 未构建，跳过（python scripts\build_exe.py --matha-cc）
)

REM 复制脚本
if exist "%REPO_ROOT%\scripts" (
    mkdir "%INSTALL_DIR%\scripts" 2>nul
    copy "%REPO_ROOT%\scripts\*.py" "%INSTALL_DIR%\scripts\" >nul 2>nul
    copy "%REPO_ROOT%\scripts\*.bat" "%INSTALL_DIR%\scripts\" >nul 2>nul
    echo   ✓ scripts\
)

REM 复制文档
if exist "%REPO_ROOT%\docs" (
    mkdir "%INSTALL_DIR%\docs" 2>nul
    copy "%REPO_ROOT%\docs\*.md" "%INSTALL_DIR%\docs\" >nul 2>nul
    echo   ✓ docs\
)

REM 复制源文件（全子包递归：src\kernel 与 src\mbc 是解释器与 VM 的必需件，
REM 旧写法只拷 compiler\domains\offline\stdlib 四片，装出的树 import 不起来）
if exist "%REPO_ROOT%\src" (
    xcopy "%REPO_ROOT%\src\*.py" "%INSTALL_DIR%\src\" /s /i /y /q >nul 2>nul
    if errorlevel 1 echo   [警告] src\ 复制不完整
    echo   ✓ src\
)

REM 复制测试
if exist "%REPO_ROOT%\tests" (
    mkdir "%INSTALL_DIR%\tests" 2>nul
    copy "%REPO_ROOT%\tests\*.py" "%INSTALL_DIR%\tests\" >nul 2>nul
    echo   ✓ tests\
)

REM 复制配置文件
if exist "%REPO_ROOT%\pyproject.toml" copy "%REPO_ROOT%\pyproject.toml" "%INSTALL_DIR%\" >nul 2>nul
if exist "%REPO_ROOT%\README.md" copy "%REPO_ROOT%\README.md" "%INSTALL_DIR%\" >nul 2>nul
if exist "%REPO_ROOT%\requirements.txt" copy "%REPO_ROOT%\requirements.txt" "%INSTALL_DIR%\" >nul 2>nul
echo   ✓ 配置文件

REM 创建桌面快捷方式
echo.
echo 创建桌面快捷方式...
REM 落点取 Shell Folders 注册表的 Desktop：目录被重定向（OneDrive）时
REM %USERPROFILE%\Desktop 是错路径——建出的图标用户在桌面上看不见。
set "DESKTOP=%USERPROFILE%\Desktop"
set "DESKTOP_RAW="
for /f "tokens=2,*" %%A in ('reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders" /v Desktop 2^>nul') do set "DESKTOP_RAW=%%B"
if defined DESKTOP_RAW call set "DESKTOP=%DESKTOP_RAW%"
REM 与 uninstall.bat 同一开关：MATHA_UNINST_DESKTOP 显式指定快捷方式落点（建/删必须同源，
REM 否则一侧走重定向目录、另一侧走注册表，卸载就删不到自己建的图标）。
if defined MATHA_UNINST_DESKTOP set "DESKTOP=%MATHA_UNINST_DESKTOP%"
set "WSCRIPT=CScript //nologo //E:JScript"
set "MAKELNK=%REPO_ROOT%\scripts\create_shortcut.js"
if not exist "%MAKELNK%" (
    echo [错误] 缺少 scripts\create_shortcut.js，快捷方式建不出来
    pause
    exit /b 1
)

%WSCRIPT% "%MAKELNK%" "%DESKTOP%\Matha REPL.lnk" "%INSTALL_DIR%\matha.exe" "Matha REPL 交互式编程环境"
%WSCRIPT% "%MAKELNK%" "%DESKTOP%\Matha 编译器.lnk" "%INSTALL_DIR%\matha-cc.exe" "Matha 编译器工具"
%WSCRIPT% "%MAKELNK%" "%DESKTOP%\Matha 安装目录.lnk" "%INSTALL_DIR%" "Matha 安装目录"
echo   ✓ 桌面快捷方式

REM 卸载入口 = scripts\uninstall.bat 原样拷贝（单一真源，不再 echo 逐行另拼一套规则）。
REM 主入口放 %LOCALAPPDATA%\Matha\（安装目录之外）：卸载脚本一旦住在自己要删的目录里，
REM 目录一没，cmd 就读不到后续行——实测只能打「The system cannot find the path
REM specified.」并把返回值改成 1，脚本里那段自我搬迁到 TEMP 只作兜底。
echo.
echo 创建卸载入口...
set "STARTMENU=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Matha"
if not defined LOCALAPPDATA set "LOCALAPPDATA=%USERPROFILE%\AppData\Local"
set "UNINST_HOME=%LOCALAPPDATA%\Matha"
mkdir "%UNINST_HOME%" 2>nul
set "UNINST=%UNINST_HOME%\uninstall.bat"
if not exist "%UNINST_HOME%" (
    echo   [警告] 无法创建 %UNINST_HOME%，卸载入口退回安装目录内
    set "UNINST=%INSTALL_DIR%\uninstall.bat"
)
copy /y "%REPO_ROOT%\scripts\uninstall.bat" "%UNINST%" >nul
if not exist "%UNINST%" (
    echo [错误] 卸载脚本没拷到 %UNINST%
    pause
    exit /b 1
)
REM 安装目录内再放一份便于直接双击（该份会自我搬迁到 TEMP 后完成删除）
copy /y "%REPO_ROOT%\scripts\uninstall.bat" "%INSTALL_DIR%\uninstall.bat" >nul
echo   ✓ 卸载入口 %UNINST%

REM 创建开始菜单快捷方式
echo.
echo 创建开始菜单快捷方式...
mkdir "%STARTMENU%" 2>nul

%WSCRIPT% "%MAKELNK%" "%STARTMENU%\Matha REPL.lnk" "%INSTALL_DIR%\matha.exe" "Matha REPL"
%WSCRIPT% "%MAKELNK%" "%STARTMENU%\Matha 编译器.lnk" "%INSTALL_DIR%\matha-cc.exe" "Matha 编译器"
%WSCRIPT% "%MAKELNK%" "%STARTMENU%\Matha 文档.lnk" "%INSTALL_DIR%\docs\OFFLINE_GUIDE.md" "Matha 离线文档"
%WSCRIPT% "%MAKELNK%" "%STARTMENU%\Matha 卸载.lnk" "%UNINST%" "卸载 Matha"
echo   ✓ 开始菜单快捷方式

echo.
echo ============================================================
echo   安装完成！
echo ============================================================
echo.
echo 使用方法（安装目录未加入 PATH，用完整路径或快捷方式）:
echo   "%INSTALL_DIR%\matha.exe" repl            # 启动 REPL
echo   "%INSTALL_DIR%\matha.exe" eval "sin(3.14)" # 计算表达式
echo   "%INSTALL_DIR%\matha.exe" run demo.matha  # 运行 Matha 文件
echo   "%INSTALL_DIR%\matha.exe" matha2c demo.matha -o out.c  # 转译为 C
echo   "%INSTALL_DIR%\matha-cc.exe" compile demo.matha        # 编译（LLVM 工具链）
echo.
echo 快捷方式:
echo   桌面: Matha REPL / Matha 编译器
echo   开始菜单: Matha 程序组
echo.
echo 安装目录: %INSTALL_DIR%
echo.
pause
