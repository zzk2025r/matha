#!/usr/bin/env python3
"""
Matha Auth 生产环境部署配置指南

基于性能测试结果和生产最佳实践，提供完整的部署配置方案。
"""

# ============================================================
# 1. 系统要求
# ============================================================
SYSTEM_REQUIREMENTS = {
    "python_version": ">=3.9",
    "memory_min_mb": 256,
    "cpu_cores_min": 2,
    "dependencies": [
        "matha-auth>=1.0.0",
        # 生产环境建议使用持久化存储
        "redis>=4.0",      # Token 黑名单 / 会话持久化
        "sqlalchemy>=2.0",  # 用户数据持久化（可选）
    ],
}

# ============================================================
# 2. 环境变量配置
# ============================================================
ENV_VARS = {
    # JWT 密钥（必须，生产环境使用 256-bit 密钥）
    "MATHA_AUTH_JWT_SECRET": "your-256-bit-secret-key-here-min-32-chars",
    "MATHA_AUTH_JWT_ALG": "HS256",

    # Token 有效期（秒）
    "MATHA_AUTH_ACCESS_TOKEN_EXP": "3600",       # 1 小时
    "MATHA_AUTH_REFRESH_TOKEN_EXP": "604800",    # 7 天

    # 密码策略
    "MATHA_AUTH_PASSWORD_MIN_LENGTH": "6",
    "MATHA_AUTH_PASSWORD_PBKDF2_ROUNDS": "12",

    # 会话配置
    "MATHA_AUTH_MAX_SESSIONS_PER_USER": "10",
    "MATHA_AUTH_IDLE_TIMEOUT_HOURS": "24",

    # 安全限制
    "MATHA_AUTH_MAX_LOGIN_ATTEMPTS": "5",
    "MATHA_AUTH_LOCKOUT_DURATION_MINUTES": "15",

    # Redis（可选，用于生产级会话持久化）
    "MATHA_AUTH_REDIS_URL": "redis://localhost:6379/0",

    # 日志级别
    "MATHA_AUTH_LOG_LEVEL": "INFO",
}

# ============================================================
# 3. 性能调优配置
# ============================================================
PERFORMANCE_CONFIG = {
    # Token 验证：反向索引已内置，无需额外配置
    # 实测: 500 用户 32,375 ops/s, 2000 用户 23,615 ops/s

    # RBAC 权限缓存：已内置，自动生效
    # 实测: 50k 检查 456,864 ops/s, 延迟 0.44µs

    # 并发限制（建议）
    "max_concurrent_requests": 10000,
    "thread_pool_size": 50,

    # 密码哈希轮数（根据服务器性能调整）
    # 12 轮: ~0.1ms/次 (安全优先)
    # 8 轮:  ~0.01ms/次 (性能优先)
    "pbkdf2_rounds_production": 12,
    "pbkdf2_rounds_perf": 8,
}

# ============================================================
# 4. Docker 部署配置
# ============================================================
DOCKER_COMPOSE = """
version: '3.8'

services:
  matha-auth:
    build: .
    environment:
      - MATHA_AUTH_JWT_SECRET=${MATHA_AUTH_JWT_SECRET}
      - MATHA_AUTH_ACCESS_TOKEN_EXP=3600
      - MATHA_AUTH_REFRESH_TOKEN_EXP=604800
      - MATHA_AUTH_LOG_LEVEL=INFO
    ports:
      - "8000:8000"
    depends_on:
      - redis
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '2'

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped

volumes:
  redis_data:
"""

# ============================================================
# 5. Nginx 反向代理配置
# ============================================================
NGINX_CONFIG = """
upstream matha_auth {
    server 127.0.0.1:8000;
    keepalive 32;
}

server {
    listen 443 ssl http2;
    server_name auth.example.com;

    ssl_certificate     /etc/ssl/certs/auth.example.com.crt;
    ssl_certificate_key /etc/ssl/private/auth.example.com.key;

    # 安全头
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header Strict-Transport-Security "max-age=31536000";

    location / {
        proxy_pass http://matha_auth;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 超时配置
        proxy_connect_timeout 10s;
        proxy_read_timeout 30s;
        proxy_send_timeout 30s;
    }

    # 健康检查
    location /health {
        access_log off;
        return 200 'ok';
    }
}
"""

# ============================================================
# 6. 监控与告警
# ============================================================
MONITORING = {
    "metrics_to_track": [
        "auth_login_success_rate",      # 登录成功率
        "auth_token_verify_latency",    # Token 验证延迟
        "auth_rbac_check_latency",      # RBAC 检查延迟
        "auth_concurrent_sessions",     # 并发会话数
        "auth_failed_login_count",      # 登录失败数（异常检测）
    ],
    "alert_thresholds": {
        "login_failure_rate": 0.1,      # 失败率 > 10% 告警
        "token_verify_p99_ms": 100,     # P99 延迟 > 100ms 告警
        "concurrent_sessions": 10000,   # 并发会话 > 10k 告警
    },
}

# ============================================================
# 7. 安全建议
# ============================================================
SECURITY_CHECKLIST = [
    "✓ 使用 HTTPS 所有请求",
    "✓ JWT 密钥至少 32 字符，定期轮换",
    "✓ 启用密码复杂度策略（字母+数字）",
    "✓ 配置登录失败锁定（5 次/15 分钟）",
    "✓ 限制单用户最大并发会话数",
    "✓ 启用审计日志记录所有权限变更",
    "✓ 定期备份用户数据",
    "✓ 使用 Redis 持久化会话（生产环境）",
    "✓ 配置 Rate Limiting（登录 10次/分，刷新 30次/分）",
    "✓ 定期审查审计日志",
]

# ============================================================
# 8. 性能基准（生产参考）
# ============================================================
PERFORMANCE_BASELINE = """
基于 2026-08-20 压测结果:

  Token 验证:        32,375 ops/s (500 用户)
  RBAC 权限检查:     456,864 ops/s (50k 检查)
  并发登录:          3,066 ops/s (2,000 用户)
  并发刷新:          1,319 ops/s (2,000 用户)
  并发 RBAC 授权:    36,623 ops/s (10k 请求)
  反向索引查找:      19M ops/s (2,000 用户)

  建议单实例处理:
    - 登录请求: < 500 QPS
    - Token 验证: < 10,000 QPS
    - RBAC 授权:  < 50,000 QPS
"""

if __name__ == "__main__":
    print("=" * 60)
    print("  Matha Auth 生产环境部署配置指南")
    print("=" * 60)
    print(f"\n{'='*20} 系统要求 {'='*20}")
    for k, v in SYSTEM_REQUIREMENTS.items():
        print(f"  {k}: {v}")
    print(f"\n{'='*20} 环境变量 {'='*20}")
    for k, v in ENV_VARS.items():
        print(f"  export {k}={v}")
    print(f"\n{'='*20} 性能基准 {'='*20}")
    print(PERFORMANCE_BASELINE)
    print(f"\n{'='*20} 安全检查清单 {'='*20}")
    for item in SECURITY_CHECKLIST:
        print(f"  {item}")
    print()
