@echo off
REM Matha WebAssembly 打包脚本 (Windows 版本)
REM 一键完成环境配置和 WASM 打包

setlocal enabledelayedexpansion

:: 颜色定义
color 0A

:: 配置
set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%..\..\.."
set "WASM_DIR=%PROJECT_ROOT%\mobile\assets\pyodide"
set "EMSDK_DIR=%USERPROFILE%\.emsdk"
set "PYTHON_WASM_DIR=%WASM_DIR%\python-wasm"
set "MATHA_WASM_DIR=%WASM_DIR%\matha-wasm"

:: Matha 模块列表
set "MODULES=calculus_symbolic linear_algebra probability_stats graph computer_science"

echo ========================================
echo   Matha WebAssembly 打包工具 v4.4.16
echo ========================================
echo.

:: 检查 Python
echo [Matha WASM] 检查 Python 环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo [Matha WASM] [错误] 未找到 Python，请安装 Python 3.8+
    exit /b 1
)
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set "PYTHON_VERSION=%%i"
echo [Matha WASM] [信息] Python 版本: !PYTHON_VERSION!

:: 创建目录
echo [Matha WASM] 创建目录结构...
if not exist "%WASM_DIR%" mkdir "%WASM_DIR%"
if not exist "%WASM_DIR%\packages" mkdir "%WASM_DIR%\packages"
if not exist "%WASM_DIR%\third_party" mkdir "%WASM_DIR%\third_party"
if not exist "%PYTHON_WASM_DIR%" mkdir "%PYTHON_WASM_DIR%"
if not exist "%MATHA_WASM_DIR%" mkdir "%MATHA_WASM_DIR%"
echo [Matha WASM] [成功] 目录创建完成

:: 打包 Matha 模块
echo [Matha WASM] 打包 Matha 核心模块...
cd /d "%MATHA_WASM_DIR%"

:: 创建 Matha 包结构
if not exist "matha" mkdir "matha"
if not exist "matha\stdlib" mkdir "matha\stdlib"
if not exist "matha\domains" mkdir "matha\domains"

:: 复制模块文件
for %%M in (%MODULES%) do (
    echo [Matha WASM] 打包模块: %%M
    if exist "%PROJECT_ROOT%\src\stdlib\%%M.py" (
        copy "%PROJECT_ROOT%\src\stdlib\%%M.py" "matha\stdlib\%%M.py" >nul
        echo [Matha WASM] [成功] 已复制 %%M
    ) else (
        echo [Matha WASM] [警告] 未找到 %%M
    )
)

:: 创建 __init__.py
(
echo """Matha 数学计算库 - WebAssembly 版本"""
echo __version__ = "4.4.16"
) > matha\__init__.py

(
echo """Matha 标准库"""
echo from . import calculus_symbolic
echo from . import linear_algebra
echo from . import probability_stats
echo from . import graph
) > matha\stdlib\__init__.py

echo [Matha WASM] [成功] Matha 模块打包完成

:: 创建 package.json
(
echo {
echo   "name": "matha-wasm",
echo   "version": "4.4.16",
echo   "description": "Matha 数学计算库 WebAssembly 版本",
echo   "main": "matha/__init__.py",
echo   "pyodide": {
echo     "packageType": "stdlib",
echo     "version": "0.24.1"
echo   }
echo }
) > package.json

:: 生成构建配置
echo [Matha WASM] 生成构建配置...
(
echo {
echo   "version": "4.4.16",
echo   "pyodideVersion": "0.24.1",
echo   "pythonVersion": "!PYTHON_VERSION!",
echo   "modules": ["calculus_symbolic", "linear_algebra", "probability_stats", "graph", "computer_science"],
echo   "outputDir": "%WASM_DIR%",
echo   "timestamp": "%date% %time%"
echo }
) > "%WASM_DIR%\build_config.json"

echo [Matha WASM] [成功] 构建配置已生成

:: 验证构建结果
echo [Matha WASM] 验证构建结果...
set "errors=0"

if exist "%WASM_DIR%\build_config.json" (
    echo [Matha WASM] [成功] build_config.json
) else (
    echo [Matha WASM] [错误] 缺少 build_config.json
    set /a "errors+=1"
)

if exist "%WASM_DIR%\packages" (
    echo [Matha WASM] [成功] packages 目录
) else (
    echo [Matha WASM] [警告] packages 目录不存在
)

if !errors! == 0 (
    echo [Matha WASM] [成功] 验证通过
) else (
    echo [Matha WASM] [错误] 验证失败，有 !errors! 个错误
)

echo.
echo ========================================
echo   打包完成!
echo   输出目录: %WASM_DIR%
echo ========================================

endlocal
pause
