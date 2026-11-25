@echo off
chcp 65001 >nul 2>nul
REM ============================================================
REM Matha Windows 卸载程序（批处理版本）
REM 同一份文件三处可用：仓库 scripts\、安装目录、%LOCALAPPDATA%\Matha\（开始菜单入口）。
REM 旧写法是 install.bat 用 echo 逐行另拼一套卸载规则，两套必然漂移。
REM 用法:
REM   uninstall.bat                     自动定位安装目录后卸载（交互确认）
REM   uninstall.bat "D:\My Matha"       指定安装目录
REM   uninstall.bat /force ["目录"]     跳过交互确认（脚本化）
REM ============================================================
setlocal enabledelayedexpansion
set "SELF_DIR=%~dp0"

REM 搬迁副本回调：目标目录走环境变量不走命令行入参——
REM 含空格的路径当参数经 start 交给副本会被截断成 "...\\p43"（实测），环境变量原样继承。
if /i "%~1"=="--relocated" (
    set "INSTALL_DIR=%MATHA_UNINST_TARGET%"
    goto body
)

set "ARG_DIR="
if /i "%~1"=="/force" (set "ASSUME_YES=1" & set "ARG_DIR=%~2") else set "ARG_DIR=%~1"

REM 安装目录判定优先级：入参 > 脚本所在目录 > 默认安装位置。
REM 旧写法恒为 C:\Program Files\Matha 硬编，且不校验目录里真有 Matha 产物就
REM rmdir /s——拷到别处运行就等于对着一个猜出来的路径执行递归删除。
set "INSTALL_DIR="
if defined ARG_DIR if exist "!ARG_DIR!\matha.exe" set "INSTALL_DIR=!ARG_DIR!"
if defined ARG_DIR if not defined INSTALL_DIR if exist "!ARG_DIR!\src\matha_main.py" set "INSTALL_DIR=!ARG_DIR!"
if not defined INSTALL_DIR if exist "%SELF_DIR%matha.exe" set "INSTALL_DIR=%SELF_DIR:~0,-1%"
if not defined INSTALL_DIR if exist "C:\Program Files\Matha\matha.exe" set "INSTALL_DIR=C:\Program Files\Matha"
if not defined INSTALL_DIR if exist "%USERPROFILE%\Matha\matha.exe" set "INSTALL_DIR=%USERPROFILE%\Matha"

if not defined INSTALL_DIR (
    echo ============================================================
    echo   [中止] 找不到 Matha 安装目录，未删除任何内容。
    echo           已试: 入参、本脚本所在目录、C:\Program Files\Matha、%USERPROFILE%\Matha
    echo           用法: uninstall.bat "[安装目录]"
    echo ============================================================
    exit /b 1
)

for %%I in ("!INSTALL_DIR!") do set "TARGET_FULL=%%~fI"
for %%I in ("%SELF_DIR%.") do set "SELF_FULL=%%~fI"
if /i not "!TARGET_FULL!"=="!SELF_FULL!" goto body

REM 脚本自己就住在要删的目录里 -> 复制一份到 TEMP，由副本脱离父进程完成删除。
REM 就地删的实测后果：目录一没，cmd 读不到后续行，打「The system cannot find the
REM path specified.」并把返回值改成 1。交接与同行 exit 缺一不可——只写交接不写
REM exit，父脚本会往下把卸载体再跑一遍（实测两遍横幅）。
set "COPY=%TEMP%\matha_uninstall.bat"
del /q "!COPY!" 2>nul
copy /y "%~f0" "!COPY!" >nul 2>nul
if not exist "!COPY!" goto body
set "MATHA_UNINST_TARGET=!TARGET_FULL!"
start "" /b "!COPY!" --relocated & exit /b 0

:body
echo ============================================================
echo   Matha 卸载程序（!INSTALL_DIR!）
echo ============================================================
echo.

REM 桌面取 Shell Folders 注册表：目录被重定向（OneDrive）时
REM %USERPROFILE%\Desktop 是错路径，删的是根本不存在的图标。
set "DESKTOP=%USERPROFILE%\Desktop"
set "DESKTOP_RAW="
for /f "tokens=2,*" %%A in ('reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders" /v Desktop 2^>nul') do set "DESKTOP_RAW=%%B"
if defined DESKTOP_RAW call set "DESKTOP=!DESKTOP_RAW!"
REM MATHA_UNINST_DESKTOP：显式指定桌面落点（重定向/多配置文件与无人值守脚本用）。
REM 也便于在临时目录里完整跑通卸载流程而不触碰真实桌面。
if defined MATHA_UNINST_DESKTOP set "DESKTOP=!MATHA_UNINST_DESKTOP!"
set "USER_STARTMENU=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Matha"
set "COMMON_STARTMENU=%ProgramData%\Microsoft\Windows\Start Menu\Programs\Matha"

REM 递归删除整个目录不可逆：默认先确认，/force 才静默
if not defined ASSUME_YES (
    set /p ANS=确认卸载 Matha（输入 Y 继续）:
    if /i not "!ANS!"=="Y" (
        echo 已取消卸载，未删除任何内容。
        exit /b 0
    )
)

echo 删除桌面快捷方式（!DESKTOP!）...
del /q "!DESKTOP!\Matha REPL.lnk" 2>nul
del /q "!DESKTOP!\Matha 编译器.lnk" 2>nul
del /q "!DESKTOP!\Matha 安装目录.lnk" 2>nul

echo 删除开始菜单快捷方式...
rmdir /s /q "!USER_STARTMENU!" 2>nul
rmdir /s /q "!COMMON_STARTMENU!" 2>nul

echo 删除安装目录...
rmdir /s /q "!INSTALL_DIR!" 2>nul

echo.
echo ============================================================
if not exist "!INSTALL_DIR!" (
    echo   Matha 已完全卸载
) else (
    echo   [提示] !INSTALL_DIR! 未删净（可能正被占用），请手动删除。
)
echo 卸载入口本身保留在 !SELF_DIR!（不在删除范围内，重跑只会提示找不到安装目录）。
echo ============================================================
echo.
pause
exit /b 0
