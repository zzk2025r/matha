@echo off
chcp 65001 >nul 2>&1
title Matha 服务守护进程
cd /d "%~dp0"

echo ========================================
echo   Matha 服务守护进程启动中...
echo   守护模式: 自动启动 / 健康检查 / 自动重启
echo   端口冲突: 自动清理旧进程 / 自动查找可用端口
echo   防火墙: 自动添加入站规则
echo ========================================
echo.

REM 持续守护模式（推荐日常使用）
python -m src.matha_daemon --port 8787

pause
