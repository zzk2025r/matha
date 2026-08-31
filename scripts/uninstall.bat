@echo off
REM ============================================================
REM Matha Windows 卸载程序（批处理版本）
REM ============================================================
setlocal enabledelayedexpansion

set "INSTALL_DIR=C:\Program Files\Matha"
set "DESKTOP=%USERPROFILE%\Desktop"
set "STARTMENU=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Matha"

echo ============================================================
echo   Matha 卸载程序
echo ============================================================
echo.

echo 删除桌面快捷方式...
del /q "%DESKTOP%\Matha REPL.lnk" 2>nul
del /q "%DESKTOP%\Matha 编译器.lnk" 2>nul
del /q "%DESKTOP%\Matha 安装目录.lnk" 2>nul

echo 删除开始菜单快捷方式...
rmdir /s /q "%STARTMENU%" 2>nul

echo 删除安装目录...
rmdir /s /q "%INSTALL_DIR%" 2>nul

echo.
echo ============================================================
echo   Matha 已完全卸载
echo ============================================================
echo.
pause
