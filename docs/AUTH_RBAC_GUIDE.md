# Matha 认证模块权限配置指南

## 1. 默认角色与权限矩阵

| 角色 | 文档 | 用户管理 | 代码执行 | 系统管理 |
|---|---|---|---|---|
| **admin** | ✅ 全部 | ✅ 全部 | ✅ 全部 | ✅ 全部 |
| **editor** | read + write | ❌ | run | ❌ |
| **viewer** | read | ❌ | run | ❌ |
| **guest** | read | ❌ | ❌ | ❌ |

### 权限通配符说明

- `"doc:*"` — 匹配所有文档操作（read/write/delete）
- `"user:*"` — 匹配所有用户操作（read/write/delete/manage）
- `"code:*"` — 匹配所有代码操作（run/debug）
- `"system:*"` — 匹配所有系统操作

---

## 2. 快速开始

### 2.1 基础用法

```python
from src.auth import SessionManager, RBACMiddleware

# 创建会话管理器和权限中间件
mgr = SessionManager()
rbac = RBACMiddleware()

# 注册不同角色的用户
admin = mgr.register("admin_user", "admin@test.com", "Admin1234", roles=["admin"])
editor = mgr.register("editor_user", "editor@test.com", "Editor1234", roles=["editor"])
viewer = mgr.register("viewer_user", "viewer@test.com", "Viewer1234", roles=["viewer"])

# 登录获取会话
session = mgr.login("editor_user", "Editor1234")
payload = mgr.verify_access_token(session.token)

# 检查权限
rbac.authorize(payload["roles"], "doc:write")        # ✅ 通过
rbac.authorize(payload["roles"], "user:manage")      # ❌ 抛出 AuthorizationError

# 装饰器用法
@rbac.require_permission("doc:write")
def create_document(user_info, name):
    return f"Created: {name}"

result = create_document(payload, "report.md")  # ✅ "Created: report.md"
```

### 2.2 自定义角色

```python
from src.auth.rbac import RBACMiddleware

rbac = RBACMiddleware()

# 注册自定义角色
rbac.register_role("developer", {
    "doc:read", "doc:write", "code:run", "code:debug"
})

rbac.register_role("moderator", {
    "doc:read", "doc:write", "doc:delete",
    "user:read", "user:write"
})

# 用户可拥有多个角色
mgr.register("dev_user", "dev@test.com", "DevPass1", roles=["developer"])
mgr.register("mod_user", "mod@test.com", "ModPass1", roles=["moderator", "viewer"])
```

---

## 3. 权限常量

```python
from src.auth.rbac import Permission

# 文档权限
Permission.DOC_READ()    # "doc:read"
Permission.DOC_WRITE()   # "doc:write"
Permission.DOC_DELETE()  # "doc:delete"

# 用户权限
Permission.USER_READ()   # "user:read"
Permission.USER_WRITE()  # "user:write"
Permission.USER_DELETE() # "user:delete"
Permission.USER_MANAGE() # "user:manage"

# 代码权限
Permission.RUN_CODE()    # "code:run"
Permission.DEBUG_RUN()   # "code:debug"
```

---

## 4. 会话管理

### 4.1 Token 结构

**Access Token**（有效期 1 小时）：
```json
{
  "sub": "username",
  "type": "access",
  "roles": ["viewer"],
  "jti": "a1b2c3d4e5f6...",   // 唯一标识符
  "iat": 1787170000,           // 签发时间
  "exp": 1787173600            // 过期时间
}
```

**Refresh Token**（有效期 7 天）：
```json
{
  "sub": "username",
  "type": "refresh",
  "jti": "f6e5d4c3b2a1...",
  "iat": 1787170000,
  "exp": 1793218000
}
```

### 4.2 Token 刷新流程

```
用户登录 → 获得 access_token + refresh_token
    ↓
access_token 过期 → 用 refresh_token 换取新 token 对
    ↓
旧 refresh_token 被撤销（一次性使用）
    ↓
新 refresh_token 加入活跃列表
```

### 4.3 会话操作

```python
# 登录
session = mgr.login("username", "password")

# 验证 access token
payload = mgr.verify_access_token(session.token)

# 刷新令牌
new_access, new_refresh = mgr.refresh_token(session.refresh_token)

# 登出（单设备）
mgr.logout(session.session_id)

# 踢出所有设备
mgr.invalidate_all_sessions("username")

# 查询活跃会话数
count = mgr.get_active_session_count("username")
```

---

## 5. 日志说明

| 级别 | 场景 | 示例 |
|---|---|---|
| **INFO** | 正常操作 | `登录成功: username=alice session_id=... roles=['viewer']` |
| **WARNING** | 认证失败 | `登录失败: 密码错误 user=bob` |
| **DEBUG** | 详细状态 | `活跃 refresh tokens: 2 个（用户 alice）` |

### 5.1 启用日志

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 5.2 日志示例

```
INFO: 注册请求: username=alice email=alice@example.com roles=['viewer']
INFO: 注册成功: username=alice roles=['viewer']
INFO: 登录请求: username=alice
INFO: 登录成功: username=alice session_id=7f2ead5e... roles=['viewer']
DEBUG: 验证 token 成功: username=alice
INFO: 刷新令牌请求
DEBUG:   token type=refresh jti=f3bc6600... 剩余有效期=5999.8s
DEBUG:   活跃 refresh tokens: 1 个（用户 alice）
INFO: 旧 refresh token 已撤销: user=alice jti=f3bc6600... tokens剩余=0
INFO: 令牌刷新成功: user=alice jti=f3bc6600... -> new_jti=67e952f0... tokens=1
INFO: 登出请求: session_id=7f2ead5e...
INFO: 登出成功: username=alice session_id=7f2ead5e...
```

---

## 6. 常见问题排查

### 6.1 Token 刷新失败

```
WARNING: 刷新令牌失败: token 不在活跃列表中
```
**原因**: token 已被使用过（refresh token 一次性使用）或已被登出。  
**解决**: 重新登录后使用新的 refresh token。

### 6.2 账号被禁用

```
WARNING: 登录失败: 账号已禁用 user=bob
WARNING: 刷新令牌失败: 账号已禁用 'bob'
```
**原因**: `user.is_active = False`。  
**解决**: 管理员恢复账号 `user.is_active = True`。

### 6.3 Token 过期

```
WARNING: 刷新令牌失败: token 无效或类型不匹配
```
**原因**: token 已过期（access token > 1h, refresh token > 7d）。  
**解决**: 重新登录获取新 token。

---

## 7. 安全最佳实践

1. **密码存储**: 使用 PBKDF2-HMAC-SHA256（12 轮）+ 随机 salt
2. **Token 安全**: access token 1 小时过期，refresh token 7 天过期
3. **一次性 refresh**: 每次刷新后旧 token 立即失效
4. **密码强度**: 最小 6 位，需包含字母和数字
5. **会话管理**: 支持多设备登录 + 全量踢出
6. **大小写规范**: 用户名统一转为小写存储
