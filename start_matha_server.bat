@echo off
chcp 65001 >nul 2>&1
title Matha OpenAI 兼容服务
cd /d "%~dp0"
echo ========================================
echo   Matha OpenAI 兼容服务启动中...
echo   地址: http://localhost:8787/v1
echo   模型: matha
echo ========================================
echo.
python -m src.openai_compat_server --port 8787
pause
