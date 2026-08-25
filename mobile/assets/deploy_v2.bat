@echo off
REM Matha 移动端自动化部署脚本 v2.0 (Windows 版本)
REM 一键完成环境配置、打包和部署

setlocal enabledelayedexpansion

:: ========== 配置 ==========
set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%..\..\.."
set "MOBILE_DIR=%PROJECT_ROOT%\mobile"
set "WASM_DIR=%MOBILE_DIR%\assets\pyodide"
set "DEPLOY_DIR=%PROJECT_ROOT%\deploy"

:: 版本信息
set "MATHA_VERSION=4.4.22"

echo ========================================
echo   Matha 移动端自动化部署脚本 v%MATHA_VERSION%
echo ========================================
echo.

:: ========== 步骤 1: 检查环境 ==========
echo [步骤 1/6] 检查开发环境...
echo.

where flutter >nul 2>&1
if errorlevel 1 (
    echo   [警告] Flutter 未安装
    echo   [提示] 请先运行: scripts\install_flutter.bat
    goto :error
) else (
    for /f "tokens=*" %%i in ('flutter --version') do echo   [成功] %%i
)

where python >nul 2>&1
if errorlevel 1 (
    echo   [警告] Python 未安装
    goto :error
) else (
    for /f "tokens=*" %%i in ('python --version') do echo   [成功] %%i
)
echo.

:: ========== 步骤 2: 安装依赖 ==========
echo [步骤 2/6] 安装项目依赖...
echo.

cd /d "%MOBILE_DIR%"
echo   安装 Flutter 依赖...
flutter pub get
if errorlevel 1 (
    echo   [错误] Flutter 依赖安装失败
    goto :error
)
echo   [成功] Flutter 依赖安装完成
echo.

echo   安装 Python 依赖...
pip install pyodide-pack websockets --quiet
if errorlevel 1 (
    echo   [警告] Python 依赖安装失败（可选）
) else (
    echo   [成功] Python 依赖安装完成
)
echo.

:: ========== 步骤 3: 构建 WebAssembly ==========
echo [步骤 3/6] 构建 WebAssembly...
echo.

if exist "%WASM_DIR%\build_wasm_v2.sh" (
    echo   [信息] 跳过 WASM 构建（需要 Linux/Mac 环境）
    echo   [提示] 请在 Linux/Mac 环境下运行: bash build_wasm_v2.sh --package
) else if exist "%WASM_DIR%\build_wasm.bat" (
    cd /d "%WASM_DIR%"
    call build_wasm.bat
    if errorlevel 1 (
        echo   [警告] WASM 构建失败
    ) else (
        echo   [成功] WebAssembly 构建完成
    )
) else (
    echo   [警告] WASM 打包脚本不存在，跳过 WASM 构建
)
echo.

:: ========== 步骤 4: 运行测试 ==========
echo [步骤 4/6] 运行测试...
echo.

cd /d "%PROJECT_ROOT%"
echo   运行 Python 测试...
python -B tests\run_all_tests.py
if errorlevel 1 (
    echo   [警告] 测试执行失败
) else (
    echo   [成功] 测试完成
)
echo.

:: ========== 步骤 5: 构建 Flutter ==========
echo [步骤 5/6] 构建 Flutter 应用...
echo.

cd /d "%MOBILE_DIR%"
echo   构建 Web 版本...
flutter build web --release --web-renderer canvaskit
if errorlevel 1 (
    echo   [警告] Flutter Web 构建失败
) else (
    echo   [成功] Web 版本构建完成: build\web\
)
echo.

:: ========== 步骤 6: 生成部署包 ==========
echo [步骤 6/6] 生成部署包...
echo.

:: 创建部署目录
if not exist "%DEPLOY_DIR%" mkdir "%DEPLOY_DIR%"

:: 复制构建产物
if exist "%MOBILE_DIR%\build\web" (
    xcopy /E /I /Q "%MOBILE_DIR%\build\web" "%DEPLOY_DIR%\web\"
    echo   [成功] Web 构建产物已复制
)

:: 复制 WASM 包
if exist "%WASM_DIR%\packages" (
    mkdir "%DEPLOY_DIR%\wasm" 2>nul
    xcopy /E /I /Q "%WASM_DIR%\packages\*" "%DEPLOY_DIR%\wasm\"
    echo   [成功] WASM 包已复制
)

:: 复制构建配置
if exist "%WASM_DIR%\build_config.json" (
    copy "%WASM_DIR%\build_config.json" "%DEPLOY_DIR%\" >nul
    echo   [成功] 构建配置已复制
)

:: 生成部署说明
(
echo # Matha 移动端部署包
echo.
echo "## 版本信息"
echo - 版本: %MATHA_VERSION%
echo - 构建时间: %date% %time%
echo - 平台: Windows
echo.
echo "## 目录结构"
echo ```
echo deploy/
echo ├── web/              # Flutter Web 构建产物
echo ├── wasm/             # WebAssembly 包
echo ├── build_config.json # 构建配置
echo └── README.md         # 本文件
echo ```
echo.
echo "## 快速启动"
echo ```bash
echo cd deploy
echo python -m http.server 8080
echo ```
echo.
echo "## 访问地址"
echo http://localhost:8080
) > "%DEPLOY_DIR%\README.md"

echo   [成功] 部署说明已生成
echo.

echo ========================================
echo   部署完成!
echo ========================================
echo.
echo   构建产物: %DEPLOY_DIR%\
echo   Web 版本: %DEPLOY_DIR%\web\
echo.
echo   下一步:
echo     1. 启动本地服务器: cd %DEPLOY_DIR% && python -m http.server 8080
echo     2. 访问: http://localhost:8080
echo     3. 测试 WebSocket 连接和 Pyodide 功能
echo.

goto :end

:error
echo.
echo ========================================
echo   部署失败!
echo ========================================
echo.

:end
endlocal
pause
