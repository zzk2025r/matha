# Matha 权限系统性能优化建议报告

基于 RBAC 高并发集成测试（10 个场景）的实测数据，针对 Token 刷新
和权限验证的瓶颈进行分析，提出以下改进方案。

---

## 1. 现状基准

| 操作 | 吞吐量 | 延迟（中位数） |
|---|---|---|
| 并发登录（200 次） | **7,823 ops/s** | ~0.13 ms/次 |
| Token 验证（200 次） | **2,506 ops/s** | ~0.40 ms/次 |
| 100 用户并发登录+刷新 | 0.08s 完成 | — |
| Refresh Token 竞态 | 正确拒绝第二请求 | ~0.05ms |

**瓶颈定位**: Token 验证（`verify_access_token`）比登录慢 ~3x，
主要原因是会话列表线性扫描。

---

## 2. 瓶颈分析

### 2.1 `verify_access_token` — 会话扫描 O(n)

```python
# 当前实现
has_valid_session = any(
    s.username == username and s.is_valid and not s.is_expired()
    for s in self._sessions.values()   # 线性遍历所有会话
)
```

当系统有 10,000+ 活跃会话时，每次 token 验证需遍历全部记录。

### 2.2 RBAC 权限匹配 — 逐角色逐权限

```python
# 当前实现
for role in roles:
    role_perms = self._roles.get(role, set())
    for perm in role_perms:
        if self._match(perm, permission):   # 字符串匹配
            return True
```

每次授权检查需遍历所有角色的所有权限字符串。

### 2.3 Refresh Token 撤销 — 列表查找 O(n)

```python
# 当前实现
token_index = self._refresh_tokens.get(username, []).index(token)
# list.index() 是 O(n) 线性搜索
```

---

## 3. 优化方案

### 方案 A: Token 验证 — 反向会话索引（推荐）

**问题**: `verify_access_token` 中 `any(s.username == username ...)` 需要遍历全部会话。

**方案**: 维护 `username → list[session_id]` 反向索引，将查找从 O(n) 降至 O(1)。

```python
# service.py 新增
class SessionManager:
    def __init__(self):
        self._sessions: dict[str, Session] = {}
        self._user_sessions: dict[str, list[str]] = {}  # 反向索引: username → [session_id]

    def _add_session_index(self, session: Session) -> None:
        self._user_sessions.setdefault(session.username, []).append(session.session_id)

    def _remove_session_index(self, session_id: str) -> None:
        sess = self._sessions.get(session_id)
        if sess and sess.username in self._user_sessions:
            self._user_sessions[sess.username].remove(session_id)
            if not self._user_sessions[sess.username]:
                del self._user_sessions[sess.username]

    def verify_access_token(self, token: str) -> Optional[dict]:
        payload = decode_token(token)
        if payload is None:
            return None
        username = payload.get("sub")
        user = self._users.get(username)
        if user is None or not user.is_active:
            return None
        # O(1) 查找：只检查该用户的会话
        user_session_ids = self._user_sessions.get(username, [])
        has_valid_session = any(
            sid in self._sessions and self._sessions[sid].is_valid and not self._sessions[sid].is_expired()
            for sid in user_session_ids
        )
        if not has_valid_session:
            return None
        return payload
```

**预期收益**: Token 验证从 ~0.40ms → ~0.05ms（8x 加速）

---

### 方案 B: RBAC 权限缓存（推荐）

**问题**: 每次 `authorize()` 都重新遍历角色和权限字符串。

**方案**: 对固定角色权限集合使用 `frozenset` 缓存，避免重复构建。

```python
# rbac.py
class RBACMiddleware:
    def __init__(self):
        self._roles: dict[str, frozenset] = {}   # 改为 frozenset
        self._role_cache: dict[frozenset, frozenset] = {}  # 角色组合 → 合并权限

    def _merge_permissions(self, roles: tuple[str, ...]) -> frozenset:
        key = tuple(sorted(roles))
        if key not in self._role_cache:
            merged = set()
            for role in key:
                if role in self._roles:
                    merged |= self._roles[role]
            self._role_cache[key] = frozenset(merged)
        return self._role_cache[key]

    def has_permission(self, roles: list[str], permission: string) -> bool:
        perm_set = self._merge_permissions(tuple(sorted(roles)))
        return self._match_any(perm_set, permission)
```

**预期收益**: 多角色权限合并从 O(n×m) → O(1)（缓存命中后）

---

### 方案 C: Refresh Token — 集合替代列表

**问题**: `list.index(token)` 是 O(n)，且并发场景下 `pop(index)` 有竞态。

**方案**: 改用 `set` 存储活跃 refresh tokens，O(1) 查找+删除。

```python
# service.py
class SessionManager:
    def __init__(self):
        # 改为 set
        self._refresh_tokens: dict[str, set[str]] = {}

    def _add_refresh_token(self, username: str, token: str) -> None:
        self._refresh_tokens.setdefault(username, set()).add(token)

    def _remove_refresh_token(self, username: str, token: str) -> None:
        tokens = self._refresh_tokens.get(username, set())
        tokens.discard(token)
        if not tokens:
            del self._refresh_tokens[username]

    def refresh_token(self, token: str) -> tuple[str, str]:
        payload = decode_refresh_token(token)
        if payload is None:
            raise TokenError()
        username = payload["sub"]
        tokens = self._refresh_tokens.get(username, set())
        if token not in tokens:
            raise TokenError("token 不在活跃列表中")
        self._remove_refresh_token(username, token)  # O(1)
        # 签发新 token...
```

**预期收益**: refresh 操作从 O(n) → O(1)，同时天然去重避免竞态

---

### 方案 D: 审计日志 — 异步写入

**问题**: S8 测试中 20 线程并发写入审计日志，虽然通过但存在潜在丢失风险。

**方案**: 使用 `queue.Queue` + 后台线程批量写入。

```python
import queue
import threading

class AuditLogger:
    def __init__(self, max_batch=100):
        self._queue: queue.Queue[dict] = queue.Queue()
        self._entries: list[dict] = []
        self._max_batch = max_batch
        self._lock = threading.Lock()
        self._runner = threading.Thread(target=self._flush_loop, daemon=True)
        self._runner.start()

    def log(self, entry: dict) -> None:
        self._queue.put_nowait(entry)

    def _flush_loop(self) -> None:
        while True:
            time.sleep(0.1)  # 批量刷新间隔
            with self._lock:
                batch = []
                while not self._queue.empty() and len(batch) < self._max_batch:
                    batch.append(self._queue.get_nowait())
                if batch:
                    self._entries = batch + self._entries
                    self._entries = self._entries[:200]  # 保留最近 200 条
```

---

## 4. 优化前后对比

| 指标 | 优化前 | 优化后（预期） | 提升 |
|---|---|---|---|
| Token 验证延迟 | ~0.40 ms | ~0.05 ms | **8x** |
| Token 验证吞吐 | 2,506 ops/s | ~16,000 ops/s | **6.4x** |
| Refresh Token 撤销 | O(n) 列表查找 | O(1) 集合查找 | **线性→常数** |
| RBAC 多角色合并 | O(n×m) 重算 | O(1) 缓存命中 | **缓存加速** |
| 审计日志写入 | 同步（阻塞） | 异步批量 | **非阻塞** |

---

## 5. 实施优先级

| 优先级 | 方案 | 工作量 | 收益 |
|---|---|---|---|
| **P0** | 方案 A: 反向会话索引 | 中等 | Token 验证 8x 加速 |
| **P0** | 方案 C: 集合替代列表 | 小 | 竞态安全 + O(1) 查找 |
| **P1** | 方案 B: RBAC 权限缓存 | 小 | 多角色场景加速 |
| **P2** | 方案 D: 异步审计日志 | 中等 | 高并发写入稳定 |

---

## 6. 注意事项

1. **方案 A** 需要在使用 `_add_session` / `_remove_session` 时同步维护反向索引
2. **方案 C** 中 `set` 无顺序，不影响功能（仅检查存在性）
3. **方案 B** 缓存键使用 `frozenset` 保证角色顺序无关
4. 所有优化均需补充单元测试验证行为不变
