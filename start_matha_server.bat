@echo off
chcp 65001 >nul 2>&1
title Matha OpenAI 兼容服务
cd /d "%~dp0"

REM 阶段 43b 真化：旧版调用模块 src.matha_daemon——该模块在阶段 11 已删除，
REM 本脚本从此刻起从未启动过服务；echo 宣称的守护/自动重启/
REM 防火墙入站规则四项能力全仓无实现。现指向真实存在的入口，并只保留代码里
REM 确实存在的口径（端口冲突区间自动切换在 src/openai_compat_server.serve 内）。

echo ========================================
echo   Matha OpenAI 兼容 API 服务
echo   入口: 有 dist\matha.exe 则用冻结进程映像
echo         否则回退 python -m src.matha_main
echo   端口: 占用时在 原端口+1..+10 内自动切换
echo   停止: Ctrl-C
echo ========================================
echo.

set "PORT=%~1"
if "%PORT%"=="" set "PORT=8787"

if exist "dist\matha.exe" (
    "dist\matha.exe" server --port %PORT%
) else (
    python -m src.matha_main server --port %PORT%
)
set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" pause
exit /b %RC%
