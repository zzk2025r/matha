@echo off
REM Matha 移动端自动化部署脚本 (Windows 版本)

setlocal enabledelayedexpansion

echo ========================================
echo   Matha 移动端自动化部署脚本
echo   版本: 4.4.16
echo ========================================
echo.

:: 步骤 1: 检查环境
echo [步骤 1/6] 检查开发环境...
where flutter >nul 2>&1
if errorlevel 1 (
    echo   [警告] 未找到 Flutter
) else (
    echo   [成功] Flutter: %~dp0
)

where python >nul 2>&1
if errorlevel 1 (
    echo   [警告] 未找到 Python
) else (
    for /f "tokens=2" %%i in ('python --version 2^>^&1') do echo   [成功] Python: %%i
)
echo.

:: 步骤 2: 安装依赖
echo [步骤 2/6] 安装项目依赖...
cd /d "%~dp0.."
flutter pub get
pip install pyodide-pack websockets
echo   [成功] 依赖安装完成
echo.

:: 步骤 3: 构建 WebAssembly
echo [步骤 3/6] 构建 WebAssembly...
if exist "%~dp0assets\pyodide\build_wasm.bat" (
    cd /d "%~dp0assets\pyodide"
    call build_wasm.bat
) else (
    echo   [警告] 跳过 WASM 打包（脚本不存在）
)
echo.

:: 步骤 4: 运行测试
echo [步骤 4/6] 运行测试...
cd /d "%~dp0..\.."
python -B tests\run_all_tests.py
echo   [成功] 测试完成
echo.

:: 步骤 5: 构建 Flutter 应用
echo [步骤 5/6] 构建 Flutter 应用...
cd /d "%~dp0.."
flutter build web --release --web-renderer canvaskit
echo   [成功] Web 版本构建完成
echo.

:: 步骤 6: 生成部署包
echo [步骤 6/6] 生成部署包...
set "DEPLOY_DIR=%~dp0..\deploy"
mkdir "%DEPLOY_DIR%" 2>nul
xcopy /E /I "%~dp0build\web" "%DEPLOY_DIR%\web\"
echo   [成功] 部署包生成完成
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

endlocal
pause
