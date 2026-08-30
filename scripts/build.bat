@echo off
REM ============================================================
REM Matha 一键打包脚本 (Windows)
REM ============================================================
REM 用法:
REM   build.bat              打包所有可执行文件
REM   build.bat matha        仅打包 matha REPL
REM   build.bat matha-cc     仅打包 matha-cc 编译器
REM   build.bat clean        清理构建目录
REM ============================================================

setlocal enabledelayedexpansion

set "PROJECT_ROOT=%~dp0.."
set "BUILD_DIR=%PROJECT_ROOT%\build"
set "DIST_DIR=%PROJECT_ROOT%\dist"
set "PYTHON=python"

echo ============================================================
echo Matha 可执行文件打包脚本
echo ============================================================
echo.

REM 检查 Python
%PYTHON% --version 2>nul || (
    echo [ERROR] 未找到 Python，请先安装 Python >= 3.10
    pause
    exit /b 1
)

%PYTHON% --version

REM 检查 PyInstaller
%PYTHON% -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [INFO] 安装 PyInstaller...
    %PYTHON% -m pip install pyinstaller
)

REM 处理命令行参数
if "%1"=="clean" (
    echo [INFO] 清理构建目录...
    if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"
    if exist "%DIST_DIR%" rmdir /s /q "%DIST_DIR%"
    echo [OK] 清理完成
    pause
    exit /b 0
)

if "%1"=="matha" (
    set "TARGETS=matha"
) else if "%1"=="matha-cc" (
    set "TARGETS=matha-cc"
) else (
    set "TARGETS=matha matha-cc"
)

REM 清理旧构建
if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"
if exist "%DIST_DIR%" rmdir /s /q "%DIST_DIR%"
mkdir "%DIST_DIR%"

echo.
echo [INFO] 开始构建...
echo.

for %%T in (%TARGETS%) do (
    echo ============================================================
    echo 构建: %%T
    echo ============================================================

    if "%%T"=="matha" (
        %PYTHON% -m PyInstaller --clean --noconfirm ^
            --distpath "%DIST_DIR%\matha" ^
            --workpath "%BUILD_DIR%\matha" ^
            --specpath "%PROJECT_ROOT%" ^
            "%PROJECT_ROOT%\matha.spec"
    ) else if "%%T"=="matha-cc" (
        %PYTHON% -m PyInstaller --clean --noconfirm ^
            --distpath "%DIST_DIR%\matha-cc" ^
            --workpath "%BUILD_DIR%\matha-cc" ^
            --specpath "%PROJECT_ROOT%" ^
            "%PROJECT_ROOT%\matha-cc.spec"
    )

    if errorlevel 1 (
        echo [FAIL] %%T 构建失败
    ) else (
        echo [OK] %%T 构建成功
        dir "%DIST_DIR%\%%T" 2>nul
    )
    echo.
)

echo ============================================================
echo 构建完成！
echo ============================================================
echo.
echo 可执行文件位置:
for %%T in (%TARGETS%) do (
    echo   %DIST_DIR%\%%T\%%T.exe
)
echo.
echo 使用方法:
echo   matha.exe                          # 启动 REPL
echo   matha.exe eval "sin(pi)"           # 计算表达式
echo   matha.exe run demo.matha           # 运行源文件
echo   matha-cc.exe compile demo.matha -o c  # 编译到 C
echo.
pause
