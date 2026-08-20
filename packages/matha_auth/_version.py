"""
用户权限变更 API 接口设计。

提供管理端接口，用于运行时动态变更用户角色和权限。

设计原则:
  - 所有变更需管理员权限（user:manage）
  - 变更记录审计日志
  - 支持批量操作
  - 变更即时生效（影响后续请求）
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .models import User
from .rbac import RBACMiddleware, AuthorizationError

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# 数据模型
# ----------------------------------------------------------------------

class ChangeType(str, Enum):
    """权限变更类型。"""
    ADD_ROLE    = "add_role"
    REMOVE_ROLE = "remove_role"
    SET_ROLE    = "set_role"       # 完全替换角色列表
    UPDATE_USER = "update_user"    # 修改用户属性（is_active 等）


class ChangeTarget(str, Enum):
    """变更作用目标。"""
    SINGLE_USER  = "single_user"
    ALL_USERS    = "all_users"
    BY_ROLE      = "by_role"      # 批量变更某角色的所有用户


@dataclass
class PermissionChangeRequest:
    """权限变更请求。"""
    operator: str                # 操作者用户名
    target_usernames: list[str]  # 目标用户列表
    change_type: ChangeType
    new_roles: list[str] = field(default_factory=list)
    is_active: Optional[bool] = None
    reason: str = ""
    timestamp: float = field(default_factory=time.time)


@dataclass
class PermissionChangeResult:
    """权限变更结果。"""
    success: bool
    changed: list[str] = field(default_factory=list)       # 成功变更的用户
    skipped: list[str] = field(default_factory=list)       # 跳过的用户
    errors: list[str] = field(default_factory=list)        # 错误信息
    change_type: str = ""
    operator: str = ""


# ----------------------------------------------------------------------
# 权限变更 API
# ----------------------------------------------------------------------

class PermissionChangeAPI:
    """用户权限变更 API。

    用法:
        api = PermissionChangeAPI(session_mgr, rbac)

        # 给用户添加角色
        result = api.add_role("admin_user", ["editor"], operator="super_admin")

        # 修改用户角色列表
        result = api.set_roles("viewer_user", ["editor"], operator="super_admin")

        # 批量启用/禁用用户
        result = api.update_users(["u1", "u2"], is_active=False, operator="admin")

        # 审计日志
        for entry in api.audit_log:
            print(entry)
    """

    def __init__(self, rbac: RBACMiddleware, mgr = None) -> None:
        self._rbac = rbac
        self._mgr = mgr
        self._audit_log: list[dict] = []

    # ------------------------------------------------------------------
    # 变更操作
    # ------------------------------------------------------------------

    def add_role(self, username, roles, operator, reason=""):
        from .service import SessionManager
        mgr = self._mgr if self._mgr else SessionManager()
        logger.info("添加角色请求: user=%s roles=%s operator=%s", username, roles, operator)
        self._check_admin_permission(operator)
        result = PermissionChangeResult(success=True, change_type=ChangeType.ADD_ROLE.value, operator=operator)
        user = mgr.get_user(username)
        if user is None:
            result.errors.append(f"{username}: 用户不存在")
            return result
        for r in roles:
            if r not in user.roles:
                user.roles.append(r)
        result.changed.append(username)
        self._audit_log.append({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "type": result.change_type, "operator": operator, "target": username, "data": {"new_roles": roles, "reason": reason}})
        logger.info("添加角色成功: operator=%s target=%s roles=%s", operator, username, roles)
        return result

    def remove_role(self, username, roles, operator, reason=""):
        from .service import SessionManager
        mgr = self._mgr if self._mgr else SessionManager()
        logger.info("移除角色请求: user=%s roles=%s operator=%s", username, roles, operator)
        self._check_admin_permission(operator)
        result = PermissionChangeResult(success=True, change_type=ChangeType.REMOVE_ROLE.value, operator=operator)
        user = mgr.get_user(username)
        if user is None:
            result.errors.append(f"{username}: 用户不存在")
            return result
        for r in roles:
            if r in user.roles:
                user.roles.remove(r)
        result.changed.append(username)
        self._audit_log.append({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "type": result.change_type, "operator": operator, "target": username, "data": {"removed_roles": roles, "reason": reason}})
        logger.info("移除角色成功: operator=%s target=%s roles=%s", operator, username, roles)
        return result

    def set_roles(self, username, roles, operator, reason=""):
        from .service import SessionManager
        mgr = self._mgr if self._mgr else SessionManager()
        logger.info("设置角色请求: user=%s roles=%s operator=%s", username, roles, operator)
        self._check_admin_permission(operator)
        result = PermissionChangeResult(success=True, change_type=ChangeType.SET_ROLE.value, operator=operator)
        user = mgr.get_user(username)
        if user is None:
            result.errors.append(f"{username}: 用户不存在")
            return result
        user.roles = list(roles)
        result.changed.append(username)
        self._audit_log.append({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "type": result.change_type, "operator": operator, "target": username, "data": {"new_roles": roles, "reason": reason}})
        logger.info("设置角色成功: operator=%s target=%s roles=%s", operator, username, roles)
        return result

    def update_users(self, usernames, *, is_active=None, operator="", reason=""):
        from .service import SessionManager
        mgr = self._mgr if self._mgr else SessionManager()
        logger.info("批量更新请求: users=%s is_active=%s operator=%s", usernames, is_active, operator)
        self._check_admin_permission(operator)
        result = PermissionChangeResult(success=True, change_type=ChangeType.UPDATE_USER.value, operator=operator)
        for username in usernames:
            user = mgr.get_user(username)
            if user is None:
                result.errors.append(f"{username}: 用户不存在")
                result.skipped.append(username)
            else:
                if is_active is not None:
                    user.is_active = is_active
                result.changed.append(username)
        self._audit_log.append({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "type": result.change_type, "operator": operator, "targets": usernames, "data": {"is_active": is_active, "reason": reason}})
        logger.info("批量更新完成: %d 成功, %d 跳过, %d 错误", len(result.changed), len(result.skipped), len(result.errors))
        return result

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def get_user_roles(self, username: str) -> list[str]:
        """查询用户当前角色列表。"""
        from .service import SessionManager
        mgr = SessionManager()
        user = mgr.get_user(username)
        return user.roles if user else []

    def get_role_permissions(self, role: str) -> set[str]:
        """查询角色权限集合。"""
        return self._rbac.get_role_permissions(role)

    def list_roles(self) -> list[str]:
        """列出所有可用角色。"""
        return self._rbac.list_roles()

    @property
    def audit_log(self) -> list[dict]:
        """审计日志（只读）。"""
        return list(self._audit_log)

    def clear_audit_log(self) -> int:
        """清空审计日志，返回清理条数。"""
        count = len(self._audit_log)
        self._audit_log.clear()
        return count

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _check_admin_permission(self, operator: str) -> None:
        """检查操作者是否拥有 user:manage 权限。"""
        if not operator:
            raise AuthorizationError("操作者不能为空")

        # 优先使用传入的 SessionManager
        mgr = self._mgr
        if mgr is None:
            from .service import SessionManager
            mgr = SessionManager()

        user = mgr.get_user(operator)
        if user is None:
            raise AuthorizationError(f"操作者不存在: {operator}")
        if "admin" not in user.roles and "user:manage" not in self._rbac.get_effective_permissions(user.roles):
            raise AuthorizationError(f"操作者无管理权限: {operator}")

        logger.debug("操作者权限检查通过: operator=%s roles=%s", operator, user.roles)


# ----------------------------------------------------------------------
# 集成示例
# ----------------------------------------------------------------------

def example_usage() -> None:
    """权限变更 API 使用示例。"""
    from src.auth import SessionManager
    from .rbac import RBACMiddleware

    mgr = SessionManager()
    rbac = RBACMiddleware()
    api = PermissionChangeAPI(rbac)

    # 注册用户
    mgr.register("super_admin", "admin@test.com", "Admin1234", roles=["admin"])
    mgr.register("viewer_user", "viewer@test.com", "Viewer1234", roles=["viewer"])
    mgr.register("editor_user", "editor@test.com", "Editor1234", roles=["editor"])

    # 1. 提升用户角色
    result = api.set_roles("viewer_user", ["editor"], operator="super_admin")
    print(f"变更结果: success={result.success} changed={result.changed}")

    # 2. 添加角色（不覆盖）
    result = api.add_role("editor_user", ["admin"], operator="super_admin")
    print(f"添加角色: {result.changed}")

    # 3. 移除角色
    result = api.remove_role("editor_user", ["admin"], operator="super_admin")
    print(f"移除角色: {result.changed}")

    # 4. 批量禁用用户
    result = api.update_users(["viewer_user", "editor_user"], is_active=False, operator="super_admin")
    print(f"批量禁用: changed={result.changed}")

    # 5. 查询审计日志
    print(f"\n审计日志 ({len(api.audit_log)} 条):")
    for entry in api.audit_log:
        print(f"  [{entry['type']}] {entry['operator']} -> {entry['target']}")


if __name__ == "__main__":
    example_usage()
"""认证异常定义。"""
from __future__ import annotations


class AuthError(Exception):
    """认证基础异常。"""

    def __init__(self, message: str, code: str = "AUTH_ERROR"):
        super().__init__(message)
        self.message = message
        self.code = code


class AuthenticationError(AuthError):
    """登录失败 — 用户名/密码错误。"""

    def __init__(self, message: str = "用户名或密码错误"):
        super().__init__(message, "AUTHENTICATION_ERROR")


class AuthorizationError(AuthError):
    """权限不足。"""

    def __init__(self, message: str = "权限不足"):
        super().__init__(message, "AUTHORIZATION_ERROR")


class TokenError(AuthError):
    """令牌相关错误。"""

    def __init__(self, message: str = "令牌无效或已过期"):
        super().__init__(message, "TOKEN_ERROR")


class RegistrationError(AuthError):
    """注册失败。"""

    def __init__(self, message: str = "注册失败", code: str = "REGISTRATION_ERROR"):
        super().__init__(message, code)
"""JWT 令牌管理。"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Optional

from .exceptions import TokenError

_JWT_SECRET = "matha-auth-jwt-secret-key-2024-v2"


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    """解码 base64url 字符串（兼容 Python 3.14 严格模式）。"""
    std = s.replace("-", "+").replace("_", "/")
    padding = (4 - len(s) % 4) % 4
    if padding:
        std += "=" * padding
    return base64.b64decode(std)


def encode_token(payload: dict, secret: str = _JWT_SECRET, exp_hours: float = 1.0) -> str:
    """签发 JWT access token。"""
    import uuid as _uuid
    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload_data = {
        **payload,
        "jti": _uuid.uuid4().hex,
        "iat": int(time.time()),
        "exp": int(time.time()) + int(exp_hours * 3600),
    }
    body = _b64url_encode(json.dumps(payload_data).encode())
    signature = _b64url_encode(
        hmac.new(secret.encode(), f"{header}.{body}".encode(), hashlib.sha256).digest()
    )
    return f"{header}.{body}.{signature}"


def decode_token(token: str, secret: str = _JWT_SECRET) -> Optional[dict]:
    """验证并解码 JWT。过期或签名不符返回 None。"""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header, payload_b64, signature = parts
        expected = _b64url_encode(
            hmac.new(secret.encode(), f"{header}.{payload_b64}".encode(), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(expected, signature):
            return None
        payload = json.loads(_b64url_decode(payload_b64))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


def encode_refresh_token(payload: dict, secret: str = _JWT_SECRET, exp_days: float = 7.0) -> str:
    """签发 JWT refresh token（有效期更长）。"""
    return encode_token(payload, secret, exp_hours=exp_days * 24)


def decode_refresh_token(token: str, secret: str = _JWT_SECRET) -> Optional[dict]:
    """验证 refresh token。"""
    return decode_token(token, secret)


def get_token_expiry(token: str, secret: str = _JWT_SECRET) -> Optional[float]:
    """获取 token 剩余有效时间（秒），无效时返回 None。"""
    payload = decode_token(token, secret)
    if payload is None:
        return None
    return payload.get("exp", 0) - time.time()
"""用户与会话数据模型。"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class User:
    """用户数据模型。"""
    username: str
    email: str
    password_hash: str   # PBKDF2 哈希值
    created_at: float = field(default_factory=time.time)
    last_login: Optional[float] = None
    is_active: bool = True
    roles: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "username": self.username,
            "email": self.email,
            "created_at": self.created_at,
            "last_login": self.last_login,
            "is_active": self.is_active,
            "roles": self.roles,
        }


@dataclass
class Session:
    """会话数据模型。"""
    session_id: str
    username: str
    token: str           # JWT access token
    refresh_token: str   # JWT refresh token
    created_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 3600)
    is_valid: bool = True

    def is_expired(self) -> bool:
        return time.time() > self.expires_at or not self.is_valid

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "username": self.username,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
        }
"""密码哈希工具 — 基于 PBKDF2-HMAC-SHA256。"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    """解码 base64url 字符串（兼容 Python 3.14 严格模式）。"""
    std = s.replace("-", "+").replace("_", "/")
    padding = (4 - len(s) % 4) % 4
    if padding:
        std += "=" * padding
    return base64.b64decode(std)


def hash_password(password: str, rounds: int = 12) -> str:
    """对密码进行 PBKDF2 哈希。格式: base64url(salt) . base64url(dk)。"""
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, rounds)
    return f"{_b64url_encode(salt)}.{_b64url_encode(dk)}"


def verify_password(password: str, password_hash: str) -> bool:
    """验证密码是否匹配哈希值。"""
    try:
        salt_b64, dk_b64 = password_hash.split(".")
        salt = _b64url_decode(salt_b64)
        expected_dk = _b64url_decode(dk_b64)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 12)
        return hmac.compare_digest(dk, expected_dk)
    except Exception:
        return False


def validate_password_strength(password: str) -> tuple[bool, str]:
    """校验密码强度，返回 (是否通过, 错误信息)。"""
    if len(password) < 6:
        return False, "密码长度至少 6 位"
    if len(password) > 128:
        return False, "密码长度不能超过 128 位"
    if not any(c.isalpha() for c in password):
        return False, "密码必须包含字母"
    if not any(c.isdigit() for c in password):
        return False, "密码必须包含数字"
    return True, ""
"""基于角色的访问控制（RBAC）中间件。

设计:
  - 角色（Role）：admin, editor, viewer, guest
  - 权限（Permission）：资源操作的最小粒度，如 "doc:read", "user:write"
  - 角色包含权限集合，用户继承角色
  - 支持通配符权限匹配： "doc:*" 匹配所有 doc 操作

用法:
    from .rbac import RBACMiddleware, Permission

    rbac = RBACMiddleware()
    rbac.register_role("admin", {"doc:read", "doc:write", "user:manage"})
    rbac.register_role("viewer", {"doc:read"})

    # 授权检查
    rbac.authorize(user.roles, "doc:read")       # OK
    rbac.authorize(user.roles, "doc:write")      # raises AuthorizationError
    rbac.authorize(user.roles, "doc:read", resource="my_doc")  # OK

    # 装饰器用法
    @rbac.require_permission("doc:write")
    def create_doc(user, name): ...

    # 检查用户是否拥有某权限
    rbac.has_permission(user.roles, "doc:read")  # True/False
"""
from __future__ import annotations

import logging
from functools import wraps
from typing import Callable, Collection, Iterable, Optional

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# 权限常量
# ----------------------------------------------------------------------

class Permission:
    """权限标识符。格式: '资源:操作'。"""

    def __init__(self, resource: str, action: str):
        self.resource = resource
        self.action = action
        self.value = f"{resource}:{action}"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Permission):
            return self.value == other.value
        if isinstance(other, str):
            return self.value == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.value)

    def __repr__(self) -> str:
        return f"Permission({self.value!r})"

    # 常用权限
    DOC_READ     = staticmethod(lambda: Permission("doc", "read"))
    DOC_WRITE    = staticmethod(lambda: Permission("doc", "write"))
    DOC_DELETE   = staticmethod(lambda: Permission("doc", "delete"))
    USER_READ    = staticmethod(lambda: Permission("user", "read"))
    USER_WRITE   = staticmethod(lambda: Permission("user", "write"))
    USER_DELETE  = staticmethod(lambda: Permission("user", "delete"))
    USER_MANAGE  = staticmethod(lambda: Permission("user", "manage"))
    RUN_CODE     = staticmethod(lambda: Permission("code", "run"))
    DEBUG_RUN    = staticmethod(lambda: Permission("code", "debug"))


# ----------------------------------------------------------------------
# 内置角色定义
# ----------------------------------------------------------------------

DEFAULT_ROLES: dict[str, set[str]] = {
    "admin":    {"doc:*", "user:*", "code:*", "system:*"},
    "editor":   {"doc:read", "doc:write", "code:run"},
    "viewer":   {"doc:read", "code:run"},
    "guest":    {"doc:read"},
}


# ----------------------------------------------------------------------
# RBAC 中间件
# ----------------------------------------------------------------------

class RBACMiddleware:
    """基于角色的访问控制中间件。支持权限缓存加速多角色合并。"""

    def __init__(self) -> None:
        self._roles: dict[str, frozenset] = {k: frozenset(v) for k, v in DEFAULT_ROLES.items()}
        # 权限缓存：冻结的角色元组 → 合并后的权限 frozenset
        self._perm_cache: dict[tuple, frozenset] = {}

    # ------------------------------------------------------------------
    # 角色管理
    # ------------------------------------------------------------------

    def register_role(self, name: str, permissions: Collection[str]) -> None:
        """注册或更新角色及其权限集合。"""
        self._roles[name] = set(permissions)
        logger.info("注册角色: %s (权限=%d)", name, len(permissions))

    def remove_role(self, name: str) -> bool:
        """删除角色。"""
        if name in self._roles:
            del self._roles[name]
            self._perm_cache.clear()
            logger.info("删除角色: %s", name)
            return True
        return False

    def get_role_permissions(self, role: str) -> frozenset:
        """获取角色的权限集合。"""
        return self._roles.get(role, frozenset())

    def list_roles(self) -> list[str]:
        """列出所有角色。"""
        return list(self._roles.keys())

    # ------------------------------------------------------------------
    # 权限匹配
    # ------------------------------------------------------------------

    def _match(self, pattern: str, target: str) -> bool:
        """通配符匹配：'doc:*' 匹配 'doc:read' / 'doc:*' 匹配 'doc:*'。"""
        if pattern == target:
            return True
        if pattern.endswith(":*"):
            prefix = pattern[:-1]  # 'doc:*' -> 'doc:'
            return target.startswith(prefix)
        return False

    def _user_has_permission(
        self,
        roles: list[str],
        permission: str,
    ) -> bool:
        """检查用户角色是否拥有指定权限（使用缓存加速多角色合并）。"""
        if not roles:
            return False
        # 获取合并后的权限集合（带缓存）
        perm_set = self._get_merged_permissions(roles)
        for perm in perm_set:
            if self._match(perm, permission):
                return True
        return False

    def _get_merged_permissions(self, roles: list[str]) -> frozenset:
        """获取角色合并后的权限集合，使用缓存加速。"""
        # 过滤空值并排序，保证缓存 key 一致
        clean = tuple(sorted(r for r in roles if r))
        if not clean:
            return frozenset()
        if clean in self._perm_cache:
            return self._perm_cache[clean]
        merged = frozenset().union(*(self._roles.get(r, frozenset()) for r in clean))
        self._perm_cache[clean] = merged
        return merged

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------

    def has_permission(
        self,
        roles: list[str],
        permission: str,
    ) -> bool:
        """检查用户是否拥有指定权限。"""
        result = self._user_has_permission(roles, permission)
        logger.debug("权限检查: roles=%s perm=%s result=%s", roles, permission, result)
        return result

    def authorize(
        self,
        roles: list[str],
        permission: str,
        resource: str = "",
    ) -> None:
        """授权检查，无权限时抛出 AuthorizationError。"""
        if not isinstance(roles, (list, tuple)):
            raise TypeError(f"roles 必须是 list 或 tuple，收到 {type(roles).__name__}")
        if not self._user_has_permission(roles, permission):
            ctx = f" [resource={resource}]" if resource else ""
            logger.warning("授权拒绝: roles=%s perm=%s%s", roles, permission, ctx)
            raise AuthorizationError(
                f"权限不足: 需要 '{permission}'{ctx}"
            )
        logger.debug("授权通过: roles=%s perm=%s", roles, permission)

    def get_effective_permissions(self, roles: list[str]) -> frozenset:
        """获取用户所有角色合并后的权限集合（使用缓存）。"""
        return self._get_merged_permissions(roles)

    # ------------------------------------------------------------------
    # 装饰器
    # ------------------------------------------------------------------

    def require_permission(self, permission: str) -> Callable:
        """权限检查装饰器。

        用法:
            @rbac.require_permission("doc:write")
            def create_doc(user, name):
                ...
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(user, *args, **kwargs):
                if not isinstance(user, dict):
                    raise TypeError("require_permission 装饰器需要 dict 类型 user")
                self.authorize(user.get("roles", []), permission)
                return func(user, *args, **kwargs)
            return wrapper
        return decorator

    def require_any_permission(self, *permissions: str) -> Callable:
        """多权限 OR 检查装饰器（满足其一即可）。"""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(user, *args, **kwargs):
                roles = user.get("roles", []) if isinstance(user, dict) else []
                for perm in permissions:
                    if self._user_has_permission(roles, perm):
                        return func(user, *args, **kwargs)
                raise AuthorizationError(
                    f"权限不足: 需要以下任一权限 {permissions}"
                )
            return wrapper
        return decorator


# ----------------------------------------------------------------------
# 全局单例
# ----------------------------------------------------------------------

_default_rbac: Optional[RBACMiddleware] = None


def get_rbac() -> RBACMiddleware:
    """获取全局 RBAC 实例。"""
    global _default_rbac
    if _default_rbac is None:
        _default_rbac = RBACMiddleware()
    return _default_rbac


def reset_rbac() -> None:
    """重置全局 RBAC 实例（用于测试）。"""
    global _default_rbac
    _default_rbac = None


# ----------------------------------------------------------------------
# 重新导出异常
# ----------------------------------------------------------------------
from .exceptions import AuthorizationError  # noqa: E402
"""会话管理器 — 内存存储用户与会话。"""
from __future__ import annotations

import logging
import uuid
import time
from typing import Optional

logger = logging.getLogger(__name__)

from .models import User, Session
from .jwt import encode_token, encode_refresh_token, decode_token
from .password import hash_password, verify_password
from .exceptions import (
    AuthenticationError,
    AuthorizationError,
    TokenError,
    RegistrationError,
)


class SessionManager:
    """内存会话管理器。支持多用户注册、登录、登出、令牌刷新。"""

    def __init__(self) -> None:
        self._users: dict[str, User] = {}
        self._sessions: dict[str, Session] = {}
        self._user_tokens: dict[str, list[str]] = {}
        # 反向索引：username → list[session_id]，加速 verify_access_token
        self._user_sessions: dict[str, list[str]] = {}
        logger.info("SessionManager 初始化完成")

    # ------------------------------------------------------------------
    # 用户注册
    # ------------------------------------------------------------------

    def register(
        self,
        username: str,
        email: str,
        password: str,
        roles: list[str] | None = None,
    ) -> User:
        """注册新用户。重复用户名抛出 RegistrationError。"""
        logger.info("注册请求: username=%s email=%s roles=%s", username, email, roles)

        if not username or not username.strip():
            raise RegistrationError("用户名不能为空")
        username = username.strip().lower()

        if not email or "@" not in email:
            raise RegistrationError("邮箱格式无效")

        if username in self._users:
            logger.warning("注册失败: 用户名已存在 '%s'", username)
            raise RegistrationError(f"用户名 '{username}' 已存在")

        pw_valid, msg = _validate_password(password)
        if not pw_valid:
            logger.warning("注册失败: 密码强度不足 '%s': %s", username, msg)
            raise RegistrationError(msg)

        hashed = hash_password(password)
        user = User(
            username=username,
            email=email.strip().lower(),
            password_hash=hashed,
            roles=roles or [],
        )
        self._users[username] = user
        logger.info("注册成功: username=%s roles=%s", username, user.roles)
        return user

    # ------------------------------------------------------------------
    # 用户登录
    # ------------------------------------------------------------------

    def login(self, username: str, password: str) -> Session:
        """验证凭据并创建新会话。失败抛出 AuthenticationError。"""
        logger.info("登录请求: username=%s", username)

        username = username.strip().lower()
        user = self._users.get(username)

        if user is None:
            logger.warning("登录失败: 用户不存在 '%s'", username)
            raise AuthenticationError()

        if not verify_password(password, user.password_hash):
            logger.warning("登录失败: 密码错误 user=%s", username)
            raise AuthenticationError()

        if not user.is_active:
            logger.warning("登录失败: 账号已禁用 user=%s", username)
            raise AuthenticationError("账号已被禁用")

        user.last_login = time.time()
        session_id = uuid.uuid4().hex
        token = encode_token({"sub": username, "type": "access", "roles": user.roles})
        refresh = encode_refresh_token({"sub": username, "type": "refresh"})

        session = Session(
            session_id=session_id,
            username=username,
            token=token,
            refresh_token=refresh,
        )
        self._sessions[session_id] = session
        self._user_tokens.setdefault(username, []).append(refresh)
        # 维护反向索引：username → [session_id]
        self._user_sessions.setdefault(username, []).append(session_id)

        logger.info(
            "登录成功: username=%s session_id=%s roles=%s",
            username, session_id, user.roles,
        )
        return session

    # ------------------------------------------------------------------
    # 令牌刷新
    # ------------------------------------------------------------------

    def refresh_token(self, refresh_token: str) -> tuple[str, str]:
        """用 refresh token 换取新 access + refresh token 对。"""
        logger.info("刷新令牌请求")
        logger.debug("  token 前缀: %.20s...", refresh_token[:40])

        # 1. 解码并验证 token
        payload = decode_token(refresh_token)
        if payload is None:
            logger.warning("刷新令牌失败: token 解码结果为 None（可能已过期或签名无效）")
            raise TokenError("无效的 refresh token")

        token_type = payload.get("type")
        token_jti = payload.get("jti", "N/A")
        token_exp = payload.get("exp", 0)
        import time as _time
        time_left = token_exp - _time.time()
        logger.debug("  token type=%s jti=%s 剩余有效期=%.1fs", token_type, token_jti, time_left)

        if token_type != "refresh":
            logger.warning(
                "刷新令牌失败: type=%s != 'refresh'（可能是 access token 误用）", token_type
            )
            raise TokenError("无效的 refresh token")

        # 2. 校验用户状态
        username = payload.get("sub")
        logger.debug("  解析用户: username=%s", username)

        if username not in self._users:
            logger.warning("刷新令牌失败: 用户不存在 '%s'", username)
            raise TokenError("用户不存在")

        user = self._users[username]
        logger.debug(
            "  用户状态: is_active=%s roles=%s last_login=%s",
            user.is_active, user.roles, user.last_login,
        )
        if not user.is_active:
            logger.warning("刷新令牌失败: 账号已禁用 '%s'", username)
            raise AuthorizationError("账号已被禁用")

        # 3. 撤销旧 refresh token
        old_token_count = len(self._user_tokens.get(username, []))
        logger.debug(
            "  活跃 refresh tokens: %d 个（用户 %s）", old_token_count, username
        )

        if username in self._user_tokens:
            user_tokens = self._user_tokens[username]
            if refresh_token in user_tokens:
                user_tokens.remove(refresh_token)
                logger.info(
                    "旧 refresh token 已撤销: user=%s jti=%s tokens剩余=%d",
                    username, token_jti, len(user_tokens),
                )
            else:
                logger.warning(
                    "刷新令牌失败: token 不在活跃列表中（可能被登出或踢出）"
                )
                raise TokenError("token 已被撤销")
        else:
            logger.warning("刷新令牌失败: 用户无 token 记录 '%s'", username)
            raise TokenError("token 已被撤销")

        # 4. 签发新 token
        new_access = encode_token({"sub": username, "type": "access", "roles": user.roles})
        new_refresh = encode_refresh_token({"sub": username, "type": "refresh"})

        # 提取新 token 的 jti 用于日志
        new_payload = decode_token(new_refresh)
        new_jti = new_payload.get("jti", "N/A") if new_payload else "N/A"

        self._user_tokens.setdefault(username, []).append(new_refresh)
        new_token_count = len(self._user_tokens[username])
        logger.info(
            "令牌刷新成功: user=%s jti=%s -> new_jti=%s tokens=%d",
            username, token_jti, new_jti, new_token_count,
        )
        return new_access, new_refresh

    # ------------------------------------------------------------------
    # 登出 / 注销
    # ------------------------------------------------------------------

    def logout(self, session_id: str) -> bool:
        """登出指定会话。"""
        logger.info("登出请求: session_id=%s", session_id)

        session = self._sessions.pop(session_id, None)
        if session is None:
            logger.warning("登出失败: session 不存在 '%s'", session_id)
            return False

        session.is_valid = False
        username = session.username
        logger.info("登出成功: username=%s session_id=%s", username, session_id)

        # 清理反向索引
        if username in self._user_sessions:
            sids = self._user_sessions[username]
            if session_id in sids:
                sids.remove(session_id)
            if not sids:
                del self._user_sessions[username]

        # 清理该用户的所有 token
        if username in self._user_tokens:
            self._user_tokens[username] = [
                t for t in self._user_tokens[username]
                if decode_token(t) is None or decode_token(t).get("sub") != username
            ]
        return True

    def invalidate_all_sessions(self, username: str) -> int:
        """踢出用户所有会话（密码修改等场景）。"""
        username = username.strip().lower()
        logger.info("踢出所有会话: username=%s", username)

        count = 0
        user_sids = self._user_sessions.pop(username, [])
        for sid in user_sids:
            if sid in self._sessions:
                self._sessions[sid].is_valid = False
                del self._sessions[sid]
                count += 1

        self._user_tokens.pop(username, None)
        logger.info("踢出完成: user=%s 踢出 %d 个会话", username, count)
        return count

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def get_user(self, username: str) -> Optional[User]:
        username_lower = username.strip().lower()
        logger.debug("查询用户: username=%s", username_lower)
        return self._users.get(username_lower)

    def get_session(self, session_id: str) -> Optional[Session]:
        logger.debug("查询会话: session_id=%s", session_id)
        session = self._sessions.get(session_id)
        if session and session.is_expired():
            del self._sessions[session_id]
            logger.debug("会话已过期，已清理: session_id=%s", session_id)
            return None
        return session

    def verify_access_token(self, token: str) -> Optional[dict]:
        """验证 access token 并返回 payload。"""
        payload = decode_token(token)
        if payload is None:
            logger.debug("验证 token 失败: token 无效")
            return None
        username = payload.get("sub")
        user = self._users.get(username) if username else None
        if user is None or not user.is_active:
            logger.debug("验证 token 失败: 用户不存在或已禁用 '%s'", username)
            return None
        # 检查是否存在有效会话（反向索引 O(k)，k = 该用户会话数）
        user_session_ids = self._user_sessions.get(username, [])
        has_valid_session = any(
            sid in self._sessions and self._sessions[sid].is_valid and not self._sessions[sid].is_expired()
            for sid in user_session_ids
        )
        if not has_valid_session:
            logger.debug("验证 token 失败: 用户无活跃会话 '%s'", username)
            return None
        logger.debug("验证 token 成功: username=%s", username)
        return payload

    def get_active_session_count(self, username: str) -> int:
        username = username.strip().lower()
        count = sum(
            1 for s in self._sessions.values()
            if s.username == username and not s.is_expired()
        )
        logger.debug("活跃会话数: username=%s count=%d", username, count)
        return count

    def get_all_usernames(self) -> list[str]:
        return list(self._users.keys())

    def count_users(self) -> int:
        return len(self._users)


# ----------------------------------------------------------------------
# 内部辅助
# ----------------------------------------------------------------------

def _validate_password(password: str) -> tuple[bool, str]:
    if not password or len(password) < 6:
        return False, "密码长度至少 6 位"
    if len(password) > 128:
        return False, "密码长度不能超过 128 位"
    if not any(c.isalpha() for c in password):
        return False, "密码必须包含字母"
    if not any(c.isdigit() for c in password):
        return False, "密码必须包含数字"
    return True, ""
"""matha-auth 包元数据"""
__version__ = "1.0.0"
__author__ = "Matha Team"
__email__ = "matha@example.com"
"""
Matha 认证模块。

提供用户注册、登录、登出、令牌刷新等完整认证功能。

用法:
    from .service import SessionManager
    from .rbac import RBACMiddleware, Permission

    mgr = SessionManager()
    user = mgr.register("张三", "zhangsan@example.com", "Pass1234", roles=["viewer"])
    session = mgr.login("zhangsan", "Pass1234")

    rbac = RBACMiddleware()
    rbac.authorize(user.roles, "doc:read")  # OK
    rbac.authorize(user.roles, "doc:write") # raises AuthorizationError
"""
from .models import User, Session
from .jwt import encode_token, decode_token, encode_refresh_token, decode_refresh_token
from .password import hash_password, verify_password, validate_password_strength
from .service import SessionManager
from .rbac import RBACMiddleware, Permission, get_rbac, reset_rbac
from .api import PermissionChangeAPI
from .exceptions import (
    AuthError,
    AuthenticationError,
    AuthorizationError,
    TokenError,
    RegistrationError,
)

__all__ = [
    # Models
    "User",
    "Session",
    # JWT
    "encode_token",
    "decode_token",
    "encode_refresh_token",
    "decode_refresh_token",
    "get_token_expiry",
    # Password
    "hash_password",
    "verify_password",
    "validate_password_strength",
    # Service
    "SessionManager",
    # RBAC
    "RBACMiddleware",
    "Permission",
    "get_rbac",
    "reset_rbac",
    # API
    "PermissionChangeAPI",
    # Exceptions
    "AuthError",
    "AuthenticationError",
    "AuthorizationError",
    "TokenError",
    "RegistrationError",
]
