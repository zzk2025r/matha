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

from matha_auth.models import User
from matha_auth.rbac import RBACMiddleware, AuthorizationError

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
        from matha_auth.service import SessionManager
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
        from matha_auth.service import SessionManager
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
        from matha_auth.service import SessionManager
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
        from matha_auth.service import SessionManager
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
        from matha_auth.service import SessionManager
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
            from matha_auth.service import SessionManager
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
    from matha_auth.rbac import RBACMiddleware

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
