# matha-auth

Matha 认证与 RBAC 权限管理系统 — 独立 Python 包

[![CI](https://github.com/matha-project/matha-auth/actions/workflows/ci.yml/badge.svg)](https://github.com/matha-project/matha-auth/actions)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://python.org)

## 安装

```bash
# 从私有 PyPI 仓库
pip install matha-auth --index-url https://pypi.your-company.com/simple/

# 或从源码
git clone https://github.com/matha-project/matha-auth
cd matha-auth/packages
pip install -e .
```

## 快速开始

```python
from matha_auth import SessionManager, RBACMiddleware, PermissionChangeAPI
from matha_auth.exceptions import AuthorizationError

# ---- 会话管理 ----
mgr = SessionManager()
user = mgr.register("alice", "alice@example.com", "AlicePass1", roles=["viewer"])
session = mgr.login("alice", "AlicePass1")
print(session.token[:50])           # eyJhbGciOiAiSFMyNTYiLCAidHlwIjogIkpXVCJ9...
print(session.refresh_token[:50])   # eyJhbGciOiAiSFMyNTYiLCAidHlwIjogIkpXVCJ9...

# 验证 Token
payload = mgr.verify_access_token(session.token)
print(payload["sub"], payload["roles"])   # alice ['viewer']

# 刷新 Token
access, new_refresh = mgr.refresh_token(session.refresh_token)

# 登出
mgr.logout(session.session_id)
# 登出后 Token 立即失效
assert mgr.verify_access_token(session.token) is None
```

## RBAC 权限控制

```python
from matha_auth import RBACMiddleware

rbac = RBACMiddleware()

# 内置角色：admin / editor / viewer / guest
rbac.has_permission(["admin"],    "doc:write")    # True  — admin 拥有所有权限
rbac.has_permission(["editor"],   "doc:write")    # True  — 可写文档
rbac.has_permission(["editor"],   "user:manage")  # False — 不能管理用户
rbac.has_permission(["viewer"],   "doc:read")     # True  — 可读文档
rbac.has_permission(["viewer"],   "code:run")     # True  — 可运行代码
rbac.has_permission(["guest"],    "doc:read")     # True  — 仅可读
rbac.has_permission(["guest"],    "code:run")     # False — 不能运行代码

# 授权检查（失败时抛出 AuthorizationError）
rbac.authorize(["editor"], "doc:write")            # OK
try:
    rbac.authorize(["guest"], "code:run")
except AuthorizationError as e:
    print(e)  # 权限不足: 需要 'code:run'

# 多角色权限合并（自动缓存）
rbac.register_role("sec", {"user:manage", "system:*"})
rbac.register_role("code_lead", {"code:run", "code:debug", "doc:write"})
roles = ["viewer", "sec", "code_lead"]
rbac.has_permission(roles, "doc:read")     # True  (viewer)
rbac.has_permission(roles, "code:debug")   # True  (code_lead)
rbac.has_permission(roles, "user:manage")  # True  (sec)
rbac.has_permission(roles, "system:restart")  # True  (sec)
rbac.has_permission(roles, "doc:delete")   # False — 无此权限

# 通配符权限
rbac.register_role("doc_admin", {"doc:*"})
rbac.has_permission(["doc_admin"], "doc:read")    # True
rbac.has_permission(["doc_admin"], "doc:write")   # True
rbac.has_permission(["doc_admin"], "user:read")   # False — 通配符不跨资源

# 装饰器用法
@rbac.require_permission("doc:write")
def create_document(user, content):
    return f"Created: {content}"

result = create_document({"roles": ["editor"]}, "Hello")  # OK
# create_document({"roles": ["guest"]}, "Hello")           # AuthorizationError
```

## 权限变更 API

```python
from matha_auth import SessionManager, RBACMiddleware, PermissionChangeAPI

mgr = SessionManager()
rbac = RBACMiddleware()
api = PermissionChangeAPI(rbac, mgr)

# 注册管理员
mgr.register("super_admin", "admin@test.com", "AdminPass1", roles=["admin"])
mgr.login("super_admin", "AdminPass1")

# 注册用户
mgr.register("alice", "alice@test.com", "AlicePass1", roles=["viewer"])

# 提升角色
result = api.set_roles("alice", ["editor"], "super_admin")
print(result.changed)  # ['alice']

# 审计日志
for entry in api.audit_log:
    print(f"[{entry['time']}] {entry['operator']} -> {entry['target']}: {entry['type']}")
    # [2026-08-20 14:00:00] super_admin -> alice: set_role
```

## HTTP API 示例

```python
# packages/matha_auth/server.py — FastAPI 最小化服务
from matha_auth.server import app
# 启动: uvicorn matha_auth.server:app --host 0.0.0.0 --port 8000
```

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/register` | POST | 用户注册 |
| `/login` | POST | 用户登录 |
| `/refresh` | POST | 刷新 Token |
| `/logout` | POST | 登出 |
| `/roles/{username}` | GET/POST | 查询/设置角色 |
| `/audit` | GET | 审计日志 |

## Docker 部署

```bash
# 构建镜像
docker build -t matha-auth:latest -f packages/Dockerfile .

# 运行
docker run -p 8000:8000 \
  -e MATHA_AUTH_JWT_SECRET="your-32-char-min-secret" \
  matha-auth:latest
```

## Kubernetes (Helm)

```bash
helm upgrade --install matha-auth ./charts/matha-auth \
  --set jwtSecret="your-secure-secret-key" \
  --set ingress.hosts[0].host=auth.example.com
```

## 测试

```bash
# matha-auth 包测试
cd packages
python -m unittest tests.test_session_manager tests.test_rbac_middleware tests.test_permission_api tests.test_concurrent

# 主项目测试
python -m unittest tests.test_auth tests.test_rbac tests.test_rbac_integration tests.test_rbac_denials

# 压力测试
python scripts/stress_test_rbac.py
```

## 性能基准

| 操作 | 吞吐 | 延迟 |
|------|------|------|
| Token 验证 | 32,375 ops/s | 0.031 ms |
| RBAC 权限检查 | 456,864 ops/s | 0.44 µs |
| 并发登录 | 3,066 ops/s | 0.65 ms |
| 并发刷新 | 1,319 ops/s | 0.76 ms |
| 并发 RBAC | 36,623 ops/s | 0.027 ms |

## 版本

- v1.0.0 — 初始发布，含反向会话索引和权限缓存优化
