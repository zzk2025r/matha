"""matha-auth 单元测试 — PermissionChangeAPI 核心逻辑"""
from __future__ import annotations
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from matha_auth import SessionManager, RBACMiddleware, PermissionChangeAPI, AuthorizationError
from matha_auth.rbac import reset_rbac
from matha_auth.api import ChangeType

# 密码满足 >=6 字符 + 字母 + 数字
PW = "Pass1x"


class TestPermissionChangeAPI(unittest.TestCase):
    """权限变更 API 测试。"""

    def setUp(self):
        reset_rbac()
        self.mgr = SessionManager()
        self.rbac = RBACMiddleware()
        self.api = PermissionChangeAPI(self.rbac, self.mgr)

        self.mgr.register("admin_user", "admin@test.com", "AdminPass1", roles=["admin"])
        self.mgr.register("target_user", "target@test.com", "TargetPass1", roles=["viewer"])
        self.mgr.login("admin_user", "AdminPass1")

    # ---- add_role ----

    def test_add_role_success(self):
        result = self.api.add_role("target_user", ["editor"], "admin_user")
        self.assertTrue(result.success)
        self.assertEqual(result.changed, ["target_user"])
        user = self.mgr.get_user("target_user")
        self.assertIn("editor", user.roles)

    def test_add_role_already_present(self):
        self.api.add_role("target_user", ["editor"], "admin_user")
        result = self.api.add_role("target_user", ["editor"], "admin_user")
        self.assertTrue(result.success)
        user = self.mgr.get_user("target_user")
        self.assertEqual(user.roles.count("editor"), 1)

    def test_add_role_nonexistent_user(self):
        result = self.api.add_role("nobody", ["editor"], "admin_user")
        self.assertTrue(result.success)
        self.assertEqual(result.errors, ["nobody: 用户不存在"])

    def test_add_role_no_admin_permission(self):
        self.mgr.register("regular", "r@test.com", "RegPass1", roles=["viewer"])
        with self.assertRaises(AuthorizationError):
            self.api.add_role("target_user", ["editor"], "regular")

    # ---- remove_role ----

    def test_remove_role_success(self):
        self.api.add_role("target_user", ["editor"], "admin_user")
        result = self.api.remove_role("target_user", ["editor"], "admin_user")
        self.assertTrue(result.success)
        user = self.mgr.get_user("target_user")
        self.assertNotIn("editor", user.roles)

    def test_remove_role_not_present(self):
        result = self.api.remove_role("target_user", ["editor"], "admin_user")
        self.assertTrue(result.success)
        self.assertEqual(result.changed, ["target_user"])

    # ---- set_roles ----

    def test_set_roles_success(self):
        result = self.api.set_roles("target_user", ["editor"], "admin_user")
        self.assertTrue(result.success)
        user = self.mgr.get_user("target_user")
        self.assertEqual(user.roles, ["editor"])

    def test_set_roles_replaces_all(self):
        self.api.add_role("target_user", ["editor"], "admin_user")
        self.api.add_role("target_user", ["admin"], "admin_user")
        self.api.set_roles("target_user", ["viewer"], "admin_user")
        user = self.mgr.get_user("target_user")
        self.assertEqual(user.roles, ["viewer"])

    def test_set_roles_nonexistent_user(self):
        result = self.api.set_roles("nobody", ["editor"], "admin_user")
        self.assertEqual(result.errors, ["nobody: 用户不存在"])

    # ---- update_users ----

    def test_update_users_activate(self):
        self.mgr.register("disabled_u", "d@test.com", "DisPass1", roles=["viewer"])
        self.mgr.get_user("disabled_u").is_active = False
        result = self.api.update_users(["disabled_u"], is_active=True, operator="admin_user")
        self.assertTrue(result.success)
        self.assertEqual(result.changed, ["disabled_u"])
        self.assertTrue(self.mgr.get_user("disabled_u").is_active)

    def test_update_users_batch(self):
        self.mgr.register("u2", "u2@t.com", "Pass2x", roles=["viewer"])
        self.mgr.register("u3", "u3@t.com", "Pass3x", roles=["viewer"])
        result = self.api.update_users(["u2", "u3"], is_active=False, operator="admin_user")
        self.assertEqual(result.changed, ["u2", "u3"])
        self.assertFalse(self.mgr.get_user("u2").is_active)
        self.assertFalse(self.mgr.get_user("u3").is_active)

    def test_update_users_skip_nonexistent(self):
        result = self.api.update_users(["nobody"], is_active=False, operator="admin_user")
        self.assertEqual(result.skipped, ["nobody"])
        self.assertEqual(result.errors, ["nobody: 用户不存在"])

    # ---- audit log ----

    def test_audit_log_recorded(self):
        self.api.set_roles("target_user", ["editor"], "admin_user")
        log = self.api.audit_log
        self.assertEqual(len(log), 1)
        entry = log[0]
        self.assertEqual(entry["type"], "set_role")
        self.assertEqual(entry["target"], "target_user")
        self.assertEqual(entry["operator"], "admin_user")
        self.assertIn("time", entry)
        self.assertIn("data", entry)
        self.assertEqual(entry["data"]["new_roles"], ["editor"])

    def test_audit_log_multiple_operations(self):
        self.api.add_role("target_user", ["editor"], "admin_user")
        self.api.remove_role("target_user", ["editor"], "admin_user")
        self.assertEqual(len(self.api.audit_log), 2)
        # 审计日志按添加顺序存储（最新在末尾）
        types = [e["type"] for e in self.api.audit_log]
        self.assertEqual(types, ["add_role", "remove_role"])

    def test_clear_audit_log(self):
        self.api.set_roles("target_user", ["editor"], "admin_user")
        count = self.api.clear_audit_log()
        self.assertEqual(count, 1)
        self.assertEqual(len(self.api.audit_log), 0)

    def test_audit_log_is_readonly_copy(self):
        self.api.set_roles("target_user", ["editor"], "admin_user")
        log = self.api.audit_log
        log.append({"fake": True})
        self.assertEqual(len(self.api.audit_log), 1)

    # ---- query ----

    def test_get_user_roles(self):
        self.api.set_roles("target_user", ["editor"], "admin_user")
        roles = self.api.get_user_roles("target_user")
        self.assertEqual(roles, ["editor"])

    def test_get_role_permissions(self):
        """admin 角色原始权限包含 doc:*，通过 has_permission 验证通配符。"""
        perms = self.api.get_role_permissions("admin")
        self.assertTrue(self.api._rbac.has_permission(["admin"], "doc:read"))
        self.assertTrue(self.api._rbac.has_permission(["admin"], "user:manage"))

    def test_list_roles(self):
        roles = self.api.list_roles()
        self.assertIn("admin", roles)
        self.assertIn("editor", roles)
        self.assertIn("viewer", roles)
        self.assertIn("guest", roles)

    # ---- ChangeType enum ----

    def test_change_type_values(self):
        self.assertEqual(ChangeType.ADD_ROLE.value, "add_role")
        self.assertEqual(ChangeType.REMOVE_ROLE.value, "remove_role")
        self.assertEqual(ChangeType.SET_ROLE.value, "set_role")
        self.assertEqual(ChangeType.UPDATE_USER.value, "update_user")


if __name__ == "__main__":
    unittest.main()
