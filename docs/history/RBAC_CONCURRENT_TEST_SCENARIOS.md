# Matha RBAC 高并发集成测试场景文档

## 概述

本文档描述了 RBAC 中间件与权限变更 API 在高并发场景下的集成测试方案，
覆盖 10 个核心场景，确保权限系统在生产环境中的正确性和一致性。

---

## 场景列表

### S1 — 多用户并发登录 + Token 刷新

**目的**: 验证 100 个用户并发登录和 Token 刷新的正确性。

**步骤**:
1. 创建 100 个用户（平均分配 admin/editor/viewer/guest 角色）
2. 20 线程并发登录
3. 每个用户验证 access token → 刷新 refresh token → 登出
4. 统计成功数

**预期**: 100/100 全部通过，耗时 < 2s

---

### S2 — 角色变更期间 Token 一致性

**目的**: 验证管理员在用户已有活跃会话时变更角色，原 Token 不立即失效。

**步骤**:
1. 用户 A 以 viewer 角色登录
2. 管理员将 A 的角色改为 editor
3. 验证 A 的原 access token 仍有效（JWT 无黑名单）
4. 验证 A 的新角色权限已通过 RBAC 检查

**预期**: 原 token 有效 + 新权限生效

---

### S3 — 批量权限变更

**目的**: 验证 20 个用户批量从 viewer 提升到 editor 的一致性。

**步骤**:
1. 注册 20 个 viewer 用户
2. 逐个调用 `api.setRoles()` 提升为 editor
3. 验证每个用户的 editor 权限（doc:write）

**预期**: 20/20 权限正确

---

### S4 — Refresh Token 竞态条件

**目的**: 验证同一 refresh token 并发刷新的原子性。

**步骤**:
1. 用户登录获得 refresh token
2. 两个线程同时调用 `refresh_token()`
3. 第一个成功，第二个应抛出 TokenError

**预期**: 第一个成功 ✓，第二个抛出 TokenError ✓

---

### S5 — 登出并发请求

**目的**: 验证登出操作与并发 token 验证的竞态安全。

**步骤**:
1. 用户登录获得 token
2. 10 个线程同时验证该 token
3. 主线程执行登出
4. 所有线程完成后检查 token 状态

**预期**: 登出后所有验证返回 None

---

### S6 — 禁用账号后活跃 Token

**目的**: 验证禁用账号后，已有 Token 立即失效。

**步骤**:
1. 管理员用户登录
2. 禁用该账号 (`is_active = False`)
3. 验证原 access token 失效
4. 验证 refresh token 被拒绝

**预期**: Token 验证返回 None，刷新抛出 AuthorizationError

---

### S7 — 多角色权限合并

**目的**: 验证用户拥有多个角色时权限正确合并。

**步骤**:
1. 创建 3 个自定义角色：sec_admin(user:manage, system:*)、code_lead(code:run, code:debug, doc:write)
2. 用户同时拥有 viewer + sec_admin + code_lead
3. 验证合并权限：应可 doc:read/code:debug/user:manage/system:restart，不可 doc:delete

**预期**: 4 个权限通过，1 个拒绝

---

### S8 — 审计日志并发写入

**目的**: 验证 20 线程并发权限变更时审计日志完整性。

**步骤**:
1. 20 个线程各执行一次 `api.setRoles()`
2. 检查 `api.audit_log` 条数

**预期**: 恰好 20 条审计记录

---

### S9 — Refresh Token 生命周期

**目的**: 验证 refresh token 链式刷新的唯一性和旧 token 失效。

**步骤**:
1. 登录获得初始 refresh token
2. 连续刷新 5 次，记录每次的 token
3. 验证 6 个 token 全部唯一
4. 尝试使用每个旧 token 刷新 → 应全部失败

**预期**: 6 个唯一 token，旧 token 全部被拒

---

### S10 — 权限降级即时生效

**目的**: 验证权限降级后新会话立即生效。

**步骤**:
1. 用户以 editor 角色登录（有 doc:write）
2. 管理员将角色降级为 viewer
3. 用户重新登录（新 token）
4. 验证新 token 无 doc:write，但有 doc:read

**预期**: 降级前可写，降级后仅可读

---

## 性能基准

| 操作 | 数量 | 预期耗时 |
|---|---|---|
| 并发登录 | 200 次 | < 1s |
| Token 验证 | 200 次 | < 1s |

---

## 运行方式

```bash
# 运行所有场景
python scripts/integration_test_rbac_concurrent.py

# 运行单个场景
python -m unittest tests.test_rbac_denials
```

---

## 依赖

- `src/auth/service.py` — SessionManager
- `src/auth/rbac.py` — RBACMiddleware
- `src/auth/api.py` — PermissionChangeAPI
- `src/auth/jwt.py` — Token 签发/验证
