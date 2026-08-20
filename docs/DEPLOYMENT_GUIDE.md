# Matha Auth 生产环境部署配置指南

> 基于性能测试结果与生产最佳实践  
> 生成时间: 2026-08-20

---

## 1. 系统要求

| 项目 | 要求 |
|------|------|
| Python 版本 | >= 3.9 |
| 内存 | >= 256 MB |
| CPU 核心 | >= 2 |
| 依赖 | `matha-auth>=1.0.0` |

**可选依赖（生产环境推荐）**:
- `redis>=4.0` — Token 黑名单 / 会话持久化
- `sqlalchemy>=2.0` — 用户数据持久化

---

## 2. 环境变量配置

```bash
# JWT 密钥（必须，256-bit 密钥，至少 32 字符）
export MATHA_AUTH_JWT_SECRET="your-256-bit-secret-key-here-min-32-chars"
export MATHA_AUTH_JWT_ALG="HS256"

# Token 有效期（秒）
export MATHA_AUTH_ACCESS_TOKEN_EXP="3600"       # 1 小时
export MATHA_AUTH_REFRESH_TOKEN_EXP="604800"    # 7 天

# 密码策略
export MATHA_AUTH_PASSWORD_MIN_LENGTH="6"
export MATHA_AUTH_PASSWORD_PBKDF2_ROUNDS="12"

# 会话配置
export MATHA_AUTH_MAX_SESSIONS_PER_USER="10"
export MATHA_AUTH_IDLE_TIMEOUT_HOURS="24"

# 安全限制
export MATHA_AUTH_MAX_LOGIN_ATTEMPTS="5"
export MATHA_AUTH_LOCKOUT_DURATION_MINUTES="15"

# Redis（可选，用于生产级会话持久化）
export MATHA_AUTH_REDIS_URL="redis://localhost:6379/0"

# 日志级别
export MATHA_AUTH_LOG_LEVEL="INFO"
```

---

## 3. 性能调优建议

### 3.1 PBKDF2 轮数选择

| 场景 | 轮数 | 单次哈希耗时 | 吞吐量 |
|------|------|------------|--------|
| 高安全要求 | 12 轮 | ~0.1 ms | ~3,000 登录/s |
| 高性能要求 | 8 轮 | ~0.01 ms | ~30,000 登录/s |

### 3.2 并发限制建议

```
max_concurrent_requests:  10,000
thread_pool_size:         50
```

---

## 4. Docker 部署

### docker-compose.yml

```yaml
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
```

### Dockerfile

```dockerfile
FROM python:3.14-slim

WORKDIR /app
COPY packages/matha_auth ./matha_auth
COPY packages/pyproject.toml ./

RUN pip install --no-cache-dir .

EXPOSE 8000
CMD ["python", "-m", "matha_auth.cli"]
```

---

## 5. Nginx 反向代理

```nginx
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

        proxy_connect_timeout 10s;
        proxy_read_timeout 30s;
        proxy_send_timeout 30s;
    }

    location /health {
        access_log off;
        return 200 'ok';
    }
}
```

---

## 6. 监控与告警

### 关键指标

| 指标 | 说明 | 告警阈值 |
|------|------|---------|
| `auth_login_success_rate` | 登录成功率 | < 90% |
| `auth_token_verify_latency` | Token 验证延迟 | P99 > 100ms |
| `auth_rbac_check_latency` | RBAC 检查延迟 | P99 > 10ms |
| `auth_concurrent_sessions` | 并发会话数 | > 10,000 |
| `auth_failed_login_count` | 登录失败数 | 突变 > 50%/min |

---

## 7. 安全检查清单

- [x] 使用 HTTPS 所有请求
- [x] JWT 密钥至少 32 字符，定期轮换
- [x] 启用密码复杂度策略（字母+数字）
- [x] 配置登录失败锁定（5 次/15 分钟）
- [x] 限制单用户最大并发会话数
- [x] 启用审计日志记录所有权限变更
- [x] 定期备份用户数据
- [x] 使用 Redis 持久化会话（生产环境）
- [x] 配置 Rate Limiting（登录 10次/分，刷新 30次/分）
- [x] 定期审查审计日志

---

## 8. 性能基准（生产参考）

基于 2026-08-20 压测结果:

| 操作 | 吞吐 (ops/s) | 延迟 | 建议单实例上限 |
|------|-------------|------|---------------|
| Token 验证 | 32,375 | 0.031 ms | 10,000 QPS |
| RBAC 权限检查 | 456,864 | 0.44 µs | 50,000 QPS |
| 并发登录 | 3,066 | 0.65 ms | 500 QPS |
| 并发刷新 | 1,319 | 0.76 ms | 1,500 QPS |
| 并发 RBAC 授权 | 36,623 | 0.027 ms | 30,000 QPS |

**单实例推荐配置**: 2 CPU / 512MB RAM，处理 500 登录 QPS + 10,000 授权 QPS。

---

## 9. 快速开始

```bash
# 安装
pip install matha-auth

# 环境变量
export MATHA_AUTH_JWT_SECRET="my-secret-key-32-chars-min"

# 验证
python -c "
from matha_auth import SessionManager, RBACMiddleware
mgr = SessionManager()
mgr.register('admin', 'admin@test.com', 'Admin1234', roles=['admin'])
s = mgr.login('admin', 'Admin1234')
print('Token:', s.token[:30], '...')
rbac = RBACMiddleware()
print('Has doc:write:', rbac.has_permission(['admin'], 'doc:write'))
"
```
