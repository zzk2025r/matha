@echo off
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
set "INSTALL_DIR=C:\Program Files\Matha"
set "VERSION=4.4"

echo ============================================================
echo   Matha v%VERSION% Windows 安装程序
echo ============================================================
echo.

REM 检查是否已安装
if exist "%INSTALL_DIR%\matha.exe" (
    echo [信息] Matha 已安装在: %INSTALL_DIR%
    echo 如需重新安装，请先运行 uninstall.bat
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

REM 复制主程序
echo.
echo 复制安装文件...
copy "%SCRIPT_DIR%dist\matha-offline\matha.exe" "%INSTALL_DIR%\" >nul
copy "%SCRIPT_DIR%dist\matha-cc-offline\matha-cc.exe" "%INSTALL_DIR%\" >nul
echo   ✓ matha.exe
echo   ✓ matha-cc.exe

REM 复制脚本
if exist "%SCRIPT_DIR%scripts" (
    mkdir "%INSTALL_DIR%\scripts" 2>nul
    copy "%SCRIPT_DIR%scripts\*.py" "%INSTALL_DIR%\scripts\" >nul 2>nul
    copy "%SCRIPT_DIR%scripts\*.bat" "%INSTALL_DIR%\scripts\" >nul 2>nul
    echo   ✓ scripts\
)

REM 复制文档
if exist "%SCRIPT_DIR%docs" (
    mkdir "%INSTALL_DIR%\docs" 2>nul
    copy "%SCRIPT_DIR%docs\*.md" "%INSTALL_DIR%\docs\" >nul 2>nul
    echo   ✓ docs\
)

REM 复制源文件
if exist "%SCRIPT_DIR%src" (
    mkdir "%INSTALL_DIR%\src" 2>nul
    copy "%SCRIPT_DIR%src\*.py" "%INSTALL_DIR%\src\" >nul 2>nul
    if exist "%SCRIPT_DIR%src\compiler" (
        mkdir "%INSTALL_DIR%\src\compiler" 2>nul
        copy "%SCRIPT_DIR%src\compiler\*.py" "%INSTALL_DIR%\src\compiler\" >nul 2>nul
    )
    if exist "%SCRIPT_DIR%src\domains" (
        mkdir "%INSTALL_DIR%\src\domains" 2>nul
        copy "%SCRIPT_DIR%src\domains\*.py" "%INSTALL_DIR%\src\domains\" >nul 2>nul
    )
    if exist "%SCRIPT_DIR%src\offline" (
        mkdir "%INSTALL_DIR%\src\offline" 2>nul
        copy "%SCRIPT_DIR%src\offline\*.py" "%INSTALL_DIR%\src\offline\" >nul 2>nul
    )
    if exist "%SCRIPT_DIR%src\stdlib" (
        mkdir "%INSTALL_DIR%\src\stdlib" 2>nul
        copy "%SCRIPT_DIR%src\stdlib\*.py" "%INSTALL_DIR%\src\stdlib\" >nul 2>nul
    )
    echo   ✓ src\
)

REM 复制测试
if exist "%SCRIPT_DIR%tests" (
    mkdir "%INSTALL_DIR%\tests" 2>nul
    copy "%SCRIPT_DIR%tests\*.py" "%INSTALL_DIR%\tests\" >nul 2>nul
    echo   ✓ tests\
)

REM 复制配置文件
copy "%SCRIPT_DIR%pyproject.toml" "%INSTALL_DIR%\" >nul 2>nul
copy "%SCRIPT_DIR%README.md" "%INSTALL_DIR%\" >nul 2>nul
copy "%SCRIPT_DIR%requirements.txt" "%INSTALL_DIR%\" >nul 2>nul
echo   ✓ 配置文件

REM 创建桌面快捷方式
echo.
echo 创建桌面快捷方式...
set "DESKTOP=%USERPROFILE%\Desktop"
set "WSCRIPT=CScript //nologo //E:JScript"

%WSCRIPT% "%SCRIPT_DIR%scripts\create_shortcut.js" "%DESKTOP%\Matha REPL.lnk" "%INSTALL_DIR%\matha.exe" "Matha REPL 交互式编程环境"
%WSCRIPT% "%DESKTOP%\Matha 编译器.lnk" "%INSTALL_DIR%\matha-cc.exe" "Matha 编译器工具"
%WSCRIPT% "%DESKTOP%\Matha 安装目录.lnk" "%INSTALL_DIR%" "Matha 安装目录"
echo   ✓ 桌面快捷方式

REM 创建开始菜单快捷方式
echo.
echo 创建开始菜单快捷方式...
set "STARTMENU=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Matha"
mkdir "%STARTMENU%" 2>nul

%WSCRIPT% "%STARTMENU%\Matha REPL.lnk" "%INSTALL_DIR%\matha.exe" "Matha REPL"
%WSCRIPT% "%STARTMENU%\Matha 编译器.lnk" "%INSTALL_DIR%\matha-cc.exe" "Matha 编译器"
%WSCRIPT% "%STARTMENU%\Matha 文档.lnk" "%INSTALL_DIR%\docs\OFFLINE_GUIDE.md" "Matha 离线文档"
%WSCRIPT% "%STARTMENU%\Matha 卸载.lnk" "%SCRIPT_DIR%uninstall.bat" "卸载 Matha"
echo   ✓ 开始菜单快捷方式

REM 创建卸载脚本
echo.
echo 创建卸载脚本...
(
echo @echo off
echo set SCRIPT_DIR=%SCRIPT_DIR%
echo set INSTALL_DIR=%INSTALL_DIR%
echo echo 卸载 Matha...
echo rmdir /s /q "%INSTALL_DIR%" 2>nul
echo del /q "%DESKTOP%\Matha REPL.lnk" 2>nul
echo del /q "%DESKTOP%\Matha 编译器.lnk" 2>nul
echo del /q "%DESKTOP%\Matha 安装目录.lnk" 2>nul
echo rmdir /s /q "%STARTMENU%" 2>nul
echo echo Matha 已卸载。
) > "%INSTALL_DIR%\uninstall.bat"
echo   ✓ 卸载脚本

echo.
echo ============================================================
echo   安装完成！
echo ============================================================
echo.
echo 使用方法:
echo   matha                          # 启动 REPL
echo   matha eval 'sin(3.14)'         # 计算表达式
echo   matha-cc compile demo.matha    # 编译到 C
echo.
echo 快捷方式:
echo   桌面: Matha REPL / Matha 编译器
echo   开始菜单: Matha 程序组
echo.
echo 安装目录: %INSTALL_DIR%
echo.
pause
