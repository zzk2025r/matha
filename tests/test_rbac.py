"""RBAC 权限中间件 — 单元测试。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.auth.rbac import RBACMiddleware, Permission, get_rbac, reset_rbac
from src.auth.exceptions import AuthorizationError


class TestPermission(unittest.TestCase):
    """Permission 标识符单元测试。"""

    def test_equality(self):
        p1 = Permission("doc", "read")
        p2 = Permission("doc", "read")
        self.assertEqual(p1, p2)
        self.assertEqual(p1, "doc:read")

    def test_hash(self):
        p1 = Permission("doc", "read")
        p2 = Permission("doc", "read")
        self.assertEqual(hash(p1), hash(p2))

    def test_repr(self):
        p = Permission("doc", "write")
        self.assertEqual(repr(p), "Permission('doc:write')")

    def test_builtin_permissions(self):
        self.assertEqual(Permission.DOC_READ().value, "doc:read")
        self.assertEqual(Permission.USER_MANAGE().value, "user:manage")
        self.assertEqual(Permission.RUN_CODE().value, "code:run")


class TestRBACMatching(unittest.TestCase):
    """通配符权限匹配单元测试。"""

    def setUp(self):
        self.rbac = RBACMiddleware()

    def test_exact_match(self):
        self.assertTrue(self.rbac._match("doc:read", "doc:read"))

    def test_wildcard_match(self):
        self.assertTrue(self.rbac._match("doc:*", "doc:read"))
        self.assertTrue(self.rbac._match("doc:*", "doc:write"))
        self.assertTrue(self.rbac._match("doc:*", "doc:delete"))

    def test_wildcard_no_cross_resource(self):
        self.assertFalse(self.rbac._match("doc:*", "user:read"))

    def test_no_match(self):
        self.assertFalse(self.rbac._match("doc:read", "doc:write"))


class TestRBACMiddleware(unittest.TestCase):
    """RBACMiddleware 核心功能单元测试。"""

    def setUp(self):
        reset_rbac()
        self.rbac = RBACMiddleware()

    # ---- 角色注册 ----

    def test_register_role(self):
        self.rbac.register_role("custom", {"doc:read", "doc:write"})
        perms = self.rbac.get_role_permissions("custom")
        self.assertEqual(perms, {"doc:read", "doc:write"})

    def test_register_wildcard_role(self):
        self.rbac.register_role("super", {"doc:*", "user:manage"})
        perms = self.rbac.get_role_permissions("super")
        # 权限以通配符形式存储，通过 _match 匹配
        self.assertIn("doc:*", perms)
        self.assertIn("user:manage", perms)
        # 通配符匹配正常工作
        self.assertTrue(self.rbac.has_permission(["super"], "doc:read"))
        self.assertTrue(self.rbac.has_permission(["super"], "doc:write"))

    def test_remove_role(self):
        self.rbac.register_role("tmp", {"doc:read"})
        self.assertTrue(self.rbac.remove_role("tmp"))
        self.assertFalse(self.rbac.remove_role("nonexistent"))

    def test_list_roles(self):
        roles = self.rbac.list_roles()
        self.assertIn("admin", roles)
        self.assertIn("viewer", roles)

    # ---- 权限检查 ----

    def test_admin_has_all(self):
        self.assertTrue(self.rbac.has_permission(["admin"], "doc:read"))
        self.assertTrue(self.rbac.has_permission(["admin"], "user:manage"))
        self.assertTrue(self.rbac.has_permission(["admin"], "code:run"))

    def test_viewer_can_read(self):
        self.assertTrue(self.rbac.has_permission(["viewer"], "doc:read"))
        self.assertTrue(self.rbac.has_permission(["viewer"], "code:run"))

    def test_viewer_cannot_write(self):
        self.assertFalse(self.rbac.has_permission(["viewer"], "doc:write"))
        self.assertFalse(self.rbac.has_permission(["viewer"], "doc:delete"))

    def test_guest_can_only_read(self):
        self.assertTrue(self.rbac.has_permission(["guest"], "doc:read"))
        self.assertFalse(self.rbac.has_permission(["guest"], "doc:write"))
        self.assertFalse(self.rbac.has_permission(["guest"], "code:run"))

    def test_editor_permissions(self):
        self.assertTrue(self.rbac.has_permission(["editor"], "doc:write"))
        self.assertTrue(self.rbac.has_permission(["editor"], "code:run"))
        self.assertFalse(self.rbac.has_permission(["editor"], "user:manage"))

    def test_multi_role(self):
        """多角色权限合并。"""
        self.assertTrue(self.rbac.has_permission(["guest", "editor"], "doc:write"))
        self.assertFalse(self.rbac.has_permission(["guest", "editor"], "user:manage"))

    def test_empty_roles(self):
        self.assertFalse(self.rbac.has_permission([], "doc:read"))

    # ---- 授权检查 ----

    def test_authorize_pass(self):
        self.rbac.authorize(["admin"], "doc:read")

    def test_authorize_fail(self):
        with self.assertRaises(AuthorizationError) as ctx:
            self.rbac.authorize(["guest"], "doc:write")
        self.assertIn("权限不足", str(ctx.exception))

    def test_authorize_with_resource(self):
        with self.assertRaises(AuthorizationError) as ctx:
            self.rbac.authorize(["guest"], "doc:write", resource="report.pdf")
        self.assertIn("resource=report.pdf", str(ctx.exception))

    # ---- 有效权限集合 ----

    def test_effective_permissions(self):
        perms = self.rbac.get_effective_permissions(["viewer", "editor"])
        self.assertIn("doc:read", perms)
        self.assertIn("doc:write", perms)
        self.assertIn("code:run", perms)
        self.assertNotIn("user:manage", perms)

    # ---- 装饰器 ----

    def test_require_permission_decorator(self):
        rbac = RBACMiddleware()

        @rbac.require_permission("doc:write")
        def write_doc(user, name):
            return f"Created: {name}"

        admin_user = {"roles": ["admin"]}
        guest_user = {"roles": ["guest"]}

        result = write_doc(admin_user, "test.md")
        self.assertEqual(result, "Created: test.md")

        with self.assertRaises(AuthorizationError):
            write_doc(guest_user, "test.md")

    def test_require_any_permission(self):
        rbac = RBACMiddleware()

        @rbac.require_any_permission("doc:write", "doc:delete")
        def modify_doc(user, name):
            return f"Modified: {name}"

        admin_user = {"roles": ["admin"]}
        editor_user = {"roles": ["editor"]}
        viewer_user = {"roles": ["viewer"]}

        self.assertEqual(modify_doc(admin_user, "x.md"), "Modified: x.md")
        self.assertEqual(modify_doc(editor_user, "x.md"), "Modified: x.md")
        with self.assertRaises(AuthorizationError):
            modify_doc(viewer_user, "x.md")

    def test_require_permission_wrong_input(self):
        rbac = RBACMiddleware()

        @rbac.require_permission("doc:read")
        def read_doc(user, name):
            return name

        with self.assertRaises(TypeError):
            read_doc("not_a_dict")  # type: ignore


class TestRBACGlobal(unittest.TestCase):
    """全局单例测试。"""

    def setUp(self):
        reset_rbac()

    def tearDown(self):
        reset_rbac()

    def test_get_rbac_singleton(self):
        r1 = get_rbac()
        r2 = get_rbac()
        self.assertIs(r1, r2)

    def test_default_roles_exist(self):
        rbac = get_rbac()
        self.assertIn("admin", rbac.list_roles())
        self.assertIn("viewer", rbac.list_roles())


if __name__ == "__main__":
    unittest.main()
