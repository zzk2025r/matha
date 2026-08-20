FROM python:3.14-slim

LABEL maintainer="matha-team@example.com"
LABEL description="Matha Auth - Authentication & RBAC service"

WORKDIR /app

# 安装依赖
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir gunicorn uvicorn[standard]

# 复制包
COPY packages/matha_auth /app/matha_auth

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "from matha_auth import SessionManager; print('OK')" || exit 1

# 启动命令（可由环境变量覆盖）
CMD ["gunicorn", "matha_auth.server:app", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "4"]
