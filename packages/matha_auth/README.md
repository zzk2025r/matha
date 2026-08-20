# matha-auth

Matha 认证与 RBAC 权限管理系统 — 独立 Python 包

## 安装

```bash
pip install -e .
```

## 快速开始

```python
from matha_auth import SessionManager, RBACMiddleware, PermissionChangeAPI

# 会话管理
mgr = SessionManager()
user = mgr.register("alice", "alice@example.com", "AlicePass1")
session = mgr.login("alice", "AlicePass1")
payload = mgr.verify_access_token(session.token)  # {"sub": "alice", "roles": [...], ...}
mgr.logout(session.session_id)

# RBAC 权限检查
rbac = RBACMiddleware()
rbac.has_permission(["editor"], "doc:write")      # True
rbac.has_permission(["viewer"], "doc:write")      # False
rbac.authorize(["editor"], "doc:write")           # OK
rbac.authorize(["viewer"], "doc:write")           # raises AuthorizationError

# 权限变更
api = PermissionChangeAPI(rbac, mgr)
api.set_roles("alice", ["admin"], "super_admin")
print(api.audit_log)  # [{"time": "...", "type": "set_role", ...}]
```

## 功能

- 用户注册/登录/登出
- JWT Access Token + Refresh Token
- PBKDF2 密码哈希
- RBAC 基于角色的访问控制（含通配符权限）
- 权限缓存（多角色合并加速）
- 反向会话索引（登出即时失效）
- 权限变更 API（审计日志）

## 测试

```bash
python -m unittest tests.test_auth tests.test_rbac tests.test_rbac_integration tests.test_rbac_denials
python scripts/stress_test_rbac.py
python scripts/integration_test_types.py
```

## 版本

- v1.0.0 — 初始发布，含反向索引和权限缓存优化
