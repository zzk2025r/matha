"""基于角色的访问控制（RBAC）中间件。

设计:
  - 角色（Role）：admin, editor, viewer, guest
  - 权限（Permission）：资源操作的最小粒度，如 "doc:read", "user:write"
  - 角色包含权限集合，用户继承角色
  - 支持通配符权限匹配： "doc:*" 匹配所有 doc 操作

用法:
    from src.auth.rbac import RBACMiddleware, Permission

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
from src.auth.exceptions import AuthorizationError  # noqa: E402
