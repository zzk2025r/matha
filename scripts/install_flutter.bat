@echo off
REM Matha Flutter SDK 安装脚本 (Windows 版本)
REM 自动检测系统并安装 Flutter SDK

setlocal enabledelayedexpansion

:: ========== 版本配置 ==========
set "FLUTTER_VERSION=3.24.0"
set "FLUTTER_CHANNEL=stable"
set "INSTALL_DIR=%USERPROFILE%\flutter"
set "CACHE_DIR=%USERPROFILE%\.cache\flutter"

:: ========== 日志函数 ==========
echo ========================================
echo   Matha Flutter SDK 安装脚本
echo   版本: %FLUTTER_VERSION%
echo ========================================
echo.

:: ========== 检查依赖 ==========
echo [步骤 1/5] 检查系统依赖...

where git >nul 2>&1
if errorlevel 1 (
    echo   [警告] Git 未安装，请手动安装: https://git-scm.com/download/win
    goto :install_flutter
) else (
    for /f "tokens=*" %%i in ('git --version') do echo   [成功] %%i
)

where curl >nul 2>&1
if errorlevel 1 (
    echo   [警告] curl 未安装，将使用 PowerShell 下载
) else (
    echo   [成功] curl 已安装
)
echo.

:: ========== 下载 Flutter ==========
:install_flutter
echo [步骤 2/5] 下载 Flutter SDK...

if not exist "%CACHE_DIR%" mkdir "%CACHE_DIR%"
cd /d "%CACHE_DIR%"

set "ARCHIVE_NAME=flutter_%FLUTTER_VERSION%-stable-windows-x64.zip"
set "DOWNLOAD_URL=https://storage.googleapis.com/flutter_infra_release/releases/stable/windows/flutter_%FLUTTER_VERSION%-stable-windows-x64.zip"

if exist "%CACHE_DIR%\%ARCHIVE_NAME%" (
    echo   [信息] 已找到缓存文件
) else (
    echo   [信息] 正在下载 Flutter SDK...
    echo   [信息] 下载地址: %DOWNLOAD_URL%
    
    where curl >nul 2>&1
    if not errorlevel 1 (
        curl -L "%DOWNLOAD_URL%" -o "%ARCHIVE_NAME%"
    ) else (
        powershell -Command "Invoke-WebRequest -Uri '%DOWNLOAD_URL%' -OutFile '%ARCHIVE_NAME%'"
    )
    
    echo   [成功] 下载完成
)
echo.

:: ========== 解压 Flutter ==========
echo [步骤 3/5] 解压 Flutter SDK...

if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
if not exist "%INSTALL_DIR%\flutter" (
    powershell -Command "Expand-Archive -Path '%CACHE_DIR%\%ARCHIVE_NAME%' -DestinationPath '%INSTALL_DIR%' -Force"
    echo   [成功] 解压完成
) else (
    echo   [信息] Flutter 已存在，跳过解压
)
echo.

:: ========== 配置环境变量 ==========
echo [步骤 4/5] 配置环境变量...

set "FLUTTER_PATH=%INSTALL_DIR%\flutter\bin"

:: 检查是否已添加到 PATH
set "PATH=%PATH%;%FLUTTER_PATH%"

echo   [信息] Flutter 路径: %FLUTTER_PATH%
echo   [信息] 请将以下内容添加到系统 PATH:
echo.
echo     %FLUTTER_PATH%
echo.
echo   或者运行以下命令永久添加:
echo     setx PATH "%PATH%"
echo.

:: ========== 运行 Flutter Doctor ==========
:run_doctor
echo [步骤 5/5] 运行 Flutter Doctor...
echo.

if exist "%FLUTTER_PATH%\flutter.bat" (
    cd /d "%FLUTTER_PATH%"
    flutter.bat doctor
) else (
    echo   [警告] Flutter 命令未找到
    echo   [提示] 请先配置环境变量，然后运行:
    echo.
    echo     set PATH=%PATH%;%FLUTTER_PATH%
    echo     flutter doctor
)
echo.

echo ========================================
echo   Flutter SDK 安装完成!
echo ========================================
echo.
echo   安装路径: %INSTALL_DIR%\flutter
echo   版本: %FLUTTER_VERSION%
echo.
echo   下一步:
echo     1. 配置环境变量 (如果尚未配置)
echo     2. 运行: flutter doctor
echo     3. 运行: flutter precache
echo.
pause

endlocal
