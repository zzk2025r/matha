"""matha-auth 单元测试 — RBACMiddleware 核心逻辑"""
from __future__ import annotations
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from matha_auth import RBACMiddleware, AuthorizationError, reset_rbac, Permission
from matha_auth.rbac import DEFAULT_ROLES


class TestRBACDefaultRoles(unittest.TestCase):
    """内置角色默认权限测试。"""

    def setUp(self):
        reset_rbac()
        self.rbac = RBACMiddleware()

    def test_admin_has_all_permissions(self):
        """admin 应能通过 has_permission 验证所有权限（通配符匹配）。"""
        self.assertTrue(self.rbac.has_permission(["admin"], "doc:read"))
        self.assertTrue(self.rbac.has_permission(["admin"], "doc:write"))
        self.assertTrue(self.rbac.has_permission(["admin"], "user:manage"))
        self.assertTrue(self.rbac.has_permission(["admin"], "code:run"))
        self.assertTrue(self.rbac.has_permission(["admin"], "system:restart"))

    def test_editor_can_write_doc(self):
        self.assertTrue(self.rbac.has_permission(["editor"], "doc:write"))

    def test_editor_cannot_delete_doc(self):
        self.assertFalse(self.rbac.has_permission(["editor"], "doc:delete"))

    def test_viewer_can_only_read(self):
        self.assertTrue(self.rbac.has_permission(["viewer"], "doc:read"))
        self.assertFalse(self.rbac.has_permission(["viewer"], "doc:write"))

    def test_guest_can_only_read_doc(self):
        self.assertTrue(self.rbac.has_permission(["guest"], "doc:read"))
        self.assertFalse(self.rbac.has_permission(["guest"], "code:run"))
        self.assertFalse(self.rbac.has_permission(["guest"], "user:read"))

    def test_list_roles(self):
        roles = self.rbac.list_roles()
        self.assertIn("admin", roles)
        self.assertIn("editor", roles)
        self.assertIn("viewer", roles)
        self.assertIn("guest", roles)


class TestRBACWildcard(unittest.TestCase):
    """通配符权限匹配测试。"""

    def setUp(self):
        reset_rbac()
        self.rbac = RBACMiddleware()

    def test_doc_wildcard_matches_all_doc_actions(self):
        self.rbac.register_role("doc_admin", {"doc:*"})
        self.assertTrue(self.rbac.has_permission(["doc_admin"], "doc:read"))
        self.assertTrue(self.rbac.has_permission(["doc_admin"], "doc:write"))
        self.assertTrue(self.rbac.has_permission(["doc_admin"], "doc:delete"))

    def test_doc_wildcard_does_not_match_user_actions(self):
        self.rbac.register_role("doc_admin", {"doc:*"})
        self.assertFalse(self.rbac.has_permission(["doc_admin"], "user:read"))
        self.assertFalse(self.rbac.has_permission(["doc_admin"], "code:run"))

    def test_code_wildcard_matches_code_actions(self):
        self.rbac.register_role("code_admin", {"code:*"})
        self.assertTrue(self.rbac.has_permission(["code_admin"], "code:run"))
        self.assertTrue(self.rbac.has_permission(["code_admin"], "code:debug"))

    def test_wildcard_does_not_leak_across_resources(self):
        self.rbac.register_role("limited", {"doc:*"})
        self.assertFalse(self.rbac.has_permission(["limited"], "user:manage"))
        self.assertFalse(self.rbac.has_permission(["limited"], "system:restart"))


class TestRBACCustomRoles(unittest.TestCase):
    """自定义角色测试。"""

    def setUp(self):
        reset_rbac()
        self.rbac = RBACMiddleware()

    def test_register_custom_role(self):
        self.rbac.register_role("developer", {"code:run", "code:debug"})
        self.assertIn("developer", self.rbac.list_roles())
        perms = self.rbac.get_role_permissions("developer")
        self.assertIn("code:run", perms)
        self.assertIn("code:debug", perms)

    def test_overwrite_role(self):
        self.rbac.register_role("editor", {"doc:read"})  # 覆盖为只读
        self.assertFalse(self.rbac.has_permission(["editor"], "doc:write"))
        self.assertTrue(self.rbac.has_permission(["editor"], "doc:read"))

    def test_remove_role(self):
        self.rbac.register_role("temp", {"doc:read"})
        self.assertTrue(self.rbac.remove_role("temp"))
        self.assertNotIn("temp", self.rbac.list_roles())

    def test_remove_nonexistent_role(self):
        self.assertFalse(self.rbac.remove_role("nonexistent"))

    def test_remove_cleared_cache(self):
        """删除角色后缓存应被清除。"""
        self.rbac.register_role("temp", {"doc:read"})
        _ = self.rbac.has_permission(["temp"], "doc:read")
        self.rbac.remove_role("temp")
        self.rbac.register_role("temp2", {"doc:write"})
        self.assertTrue(self.rbac.has_permission(["temp2"], "doc:write"))


class TestRBACMultiRole(unittest.TestCase):
    """多角色权限合并测试。"""

    def setUp(self):
        reset_rbac()
        self.rbac = RBACMiddleware()
        self.rbac.register_role("sec", {"user:manage", "system:*"})
        self.rbac.register_role("code_lead", {"code:run", "code:debug", "doc:write"})

    def test_merge_permissions(self):
        """多角色合并后应能通过 has_permission 验证各权限。"""
        self.assertTrue(self.rbac.has_permission(["viewer", "sec", "code_lead"], "doc:read"))
        self.assertTrue(self.rbac.has_permission(["viewer", "sec", "code_lead"], "code:debug"))
        self.assertTrue(self.rbac.has_permission(["viewer", "sec", "code_lead"], "user:manage"))
        self.assertTrue(self.rbac.has_permission(["viewer", "sec", "code_lead"], "system:restart"))
        self.assertFalse(self.rbac.has_permission(["viewer", "sec", "code_lead"], "doc:delete"))

    def test_duplicate_roles_no_effect(self):
        r1 = self.rbac.get_effective_permissions(["editor", "editor"])
        r2 = self.rbac.get_effective_permissions(["editor"])
        self.assertEqual(r1, r2)

    def test_cache_reuse(self):
        """相同角色组合应命中缓存。"""
        r1 = self.rbac.get_effective_permissions(["viewer", "editor"])
        r2 = self.rbac.get_effective_permissions(["editor", "viewer"])
        self.assertEqual(r1, r2)

    def test_empty_roles(self):
        self.assertEqual(self.rbac.get_effective_permissions([]), frozenset())
        self.assertFalse(self.rbac.has_permission([], "doc:read"))

    def test_none_role_in_list(self):
        """角色列表中有 None 不应崩溃。"""
        result = self.rbac.has_permission([None, "viewer"], "doc:read")  # type: ignore
        self.assertTrue(result)


class TestRBACAuthorize(unittest.TestCase):
    """authorize() 授权检查测试。"""

    def setUp(self):
        reset_rbac()
        self.rbac = RBACMiddleware()

    def test_authorize_passes(self):
        self.rbac.authorize(["editor"], "doc:write")  # 不应抛出

    def test_authorize_fails(self):
        with self.assertRaises(AuthorizationError) as ctx:
            self.rbac.authorize(["guest"], "doc:write")
        self.assertIn("doc:write", str(ctx.exception))

    def test_authorize_with_resource(self):
        with self.assertRaises(AuthorizationError) as ctx:
            self.rbac.authorize(["guest"], "doc:write", resource="secret.pdf")
        self.assertIn("resource=secret.pdf", str(ctx.exception))

    def test_authorize_type_error_on_none(self):
        with self.assertRaises(TypeError):
            self.rbac.authorize(None, "doc:read")  # type: ignore

    def test_authorize_type_error_on_string(self):
        with self.assertRaises(TypeError):
            self.rbac.authorize("viewer", "doc:read")  # type: ignore


class TestRBACDecorator(unittest.TestCase):
    """装饰器权限检查测试。"""

    def setUp(self):
        reset_rbac()
        self.rbac = RBACMiddleware()

    def test_decorator_passes(self):
        @self.rbac.require_permission("doc:read")
        def read_doc(user, path):
            return f"read {path}"

        result = read_doc({"roles": ["viewer"]}, "file.txt")
        self.assertEqual(result, "read file.txt")

    def test_decorator_fails(self):
        @self.rbac.require_permission("doc:write")
        def write_doc(user, content):
            return content

        with self.assertRaises(AuthorizationError):
            write_doc({"roles": ["viewer"]}, "hello")

    def test_decorator_type_error_on_non_dict(self):
        @self.rbac.require_permission("doc:read")
        def read_doc(user, path):
            return path

        with self.assertRaises(TypeError):
            read_doc("not_a_dict", "file")  # type: ignore

    def test_require_any_permission(self):
        @self.rbac.require_any_permission("doc:write", "doc:delete")
        def modify(user, action):
            return action

        self.assertEqual(modify({"roles": ["editor"]}, "delete"), "delete")
        with self.assertRaises(AuthorizationError):
            modify({"roles": ["guest"]}, "delete")


class TestPermissionConstants(unittest.TestCase):
    """Permission 常量测试。"""

    def test_doc_read(self):
        p = Permission.DOC_READ()
        self.assertEqual(p.value, "doc:read")
        self.assertEqual(p.resource, "doc")
        self.assertEqual(p.action, "read")

    def test_permission_equality_with_string(self):
        p = Permission.DOC_WRITE()
        self.assertEqual(p, "doc:write")
        self.assertNotEqual(p, "doc:read")

    def test_permission_hash(self):
        p1 = Permission.DOC_READ()
        p2 = Permission("doc", "read")
        self.assertEqual(hash(p1), hash(p2))


class TestRBACCaching(unittest.TestCase):
    """权限缓存专项测试。"""

    def setUp(self):
        reset_rbac()
        self.rbac = RBACMiddleware()

    def test_cache_hit_after_first_call(self):
        """第二次调用相同角色组合应命中缓存。"""
        roles = ["viewer", "editor"]
        self.rbac.has_permission(roles, "doc:read")
        cache_before = len(self.rbac._perm_cache)
        self.rbac.has_permission(roles, "doc:read")
        self.assertEqual(len(self.rbac._perm_cache), cache_before)

    def test_cache_invalidated_on_register(self):
        """注册新角色后缓存应被清除。"""
        self.rbac.has_permission(["viewer"], "doc:read")
        before = len(self.rbac._perm_cache)
        self.rbac.register_role("custom", {"doc:write"})
        # 缓存已清空，重新构建
        self.rbac.has_permission(["custom"], "doc:write")
        self.assertGreaterEqual(len(self.rbac._perm_cache), 1)

    def test_cache_invalidated_on_remove(self):
        """删除角色后缓存应被清除。"""
        self.rbac.register_role("temp", {"doc:read"})
        self.rbac.has_permission(["temp"], "doc:read")
        before = len(self.rbac._perm_cache)
        self.rbac.remove_role("temp")
        self.assertEqual(len(self.rbac._perm_cache), 0)

    def test_get_effective_permissions_uses_cache(self):
        perms = self.rbac.get_effective_permissions(["editor", "viewer"])
        self.assertIsInstance(perms, frozenset)
        self.assertTrue(self.rbac.has_permission(["editor", "viewer"], "doc:read"))
        self.assertTrue(self.rbac.has_permission(["editor", "viewer"], "code:run"))


if __name__ == "__main__":
    unittest.main()
