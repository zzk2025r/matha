"""RBAC 权限拒绝场景专项单元测试。

覆盖所有可能触发 AuthorizationError 的路径：
  - 无角色用户访问任何资源
  - 各默认角色越权操作
  - 通配符权限边界（跨资源、跨操作）
  - 装饰器拒绝路径
  - 多权限 OR 拒绝路径
  - 自定义角色缺失权限
  - 资源上下文敏感拒绝
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.auth.rbac import RBACMiddleware, Permission, get_rbac, reset_rbac
from src.auth.exceptions import AuthorizationError


class TestDenialGuest(unittest.TestCase):
    """访客（最低权限）所有拒绝场景。"""

    def setUp(self):
        reset_rbac()
        self.rbac = RBACMiddleware()

    # 访客只能 doc:read
    def test_guest_cannot_write_doc(self):
        with self.assertRaises(AuthorizationError) as ctx:
            self.rbac.authorize(["guest"], "doc:write")
        self.assertIn("doc:write", str(ctx.exception))

    def test_guest_cannot_delete_doc(self):
        with self.assertRaises(AuthorizationError):
            self.rbac.authorize(["guest"], "doc:delete")

    def test_guest_cannot_read_user(self):
        with self.assertRaises(AuthorizationError):
            self.rbac.authorize(["guest"], "user:read")

    def test_guest_cannot_write_user(self):
        with self.assertRaises(AuthorizationError):
            self.rbac.authorize(["guest"], "user:write")

    def test_guest_cannot_manage_user(self):
        with self.assertRaises(AuthorizationError):
            self.rbac.authorize(["guest"], "user:manage")

    def test_guest_cannot_run_code(self):
        with self.assertRaises(AuthorizationError):
            self.rbac.authorize(["guest"], "code:run")

    def test_guest_cannot_debug_code(self):
        with self.assertRaises(AuthorizationError):
            self.rbac.authorize(["guest"], "code:debug")

    def test_guest_cannot_system_action(self):
        with self.assertRaises(AuthorizationError):
            self.rbac.authorize(["guest"], "system:restart")

    def test_guest_has_no_effective_perms_beyond_read(self):
        perms = self.rbac.get_effective_permissions(["guest"])
        self.assertEqual(perms, {"doc:read"})


class TestDenialViewer(unittest.TestCase):
    """查看者（doc:read, code:run）拒绝场景。"""

    def setUp(self):
        reset_rbac()
        self.rbac = RBACMiddleware()

    def test_viewer_cannot_write_doc(self):
        with self.assertRaises(AuthorizationError):
            self.rbac.authorize(["viewer"], "doc:write")

    def test_viewer_cannot_delete_doc(self):
        with self.assertRaises(AuthorizationError):
            self.rbac.authorize(["viewer"], "doc:delete")

    def test_viewer_cannot_read_user(self):
        with self.assertRaises(AuthorizationError):
            self.rbac.authorize(["viewer"], "user:read")

    def test_viewer_cannot_write_user(self):
        with self.assertRaises(AuthorizationError):
            self.rbac.authorize(["viewer"], "user:write")

    def test_viewer_cannot_delete_user(self):
        with self.assertRaises(AuthorizationError):
            self.rbac.authorize(["viewer"], "user:delete")

    def test_viewer_cannot_manage_user(self):
        with self.assertRaises(AuthorizationError):
            self.rbac.authorize(["viewer"], "user:manage")

    def test_viewer_cannot_debug_code(self):
        with self.assertRaises(AuthorizationError):
            self.rbac.authorize(["viewer"], "code:debug")

    def test_viewer_cannot_system_action(self):
        with self.assertRaises(AuthorizationError):
            self.rbac.authorize(["viewer"], "system:shutdown")

    def test_viewer_effective_perms(self):
        perms = self.rbac.get_effective_permissions(["viewer"])
        self.assertEqual(perms, {"doc:read", "code:run"})


class TestDenialEditor(unittest.TestCase):
    """编辑者（doc:read/write, code:run）拒绝场景。"""

    def setUp(self):
        reset_rbac()
        self.rbac = RBACMiddleware()

    def test_editor_cannot_delete_doc(self):
        with self.assertRaises(AuthorizationError):
            self.rbac.authorize(["editor"], "doc:delete")

    def test_editor_cannot_read_user(self):
        with self.assertRaises(AuthorizationError):
            self.rbac.authorize(["editor"], "user:read")

    def test_editor_cannot_write_user(self):
        with self.assertRaises(AuthorizationError):
            self.rbac.authorize(["editor"], "user:write")

    def test_editor_cannot_delete_user(self):
        with self.assertRaises(AuthorizationError):
            self.rbac.authorize(["editor"], "user:delete")

    def test_editor_cannot_manage_user(self):
        with self.assertRaises(AuthorizationError):
            self.rbac.authorize(["editor"], "user:manage")

    def test_editor_cannot_debug_code(self):
        with self.assertRaises(AuthorizationError):
            self.rbac.authorize(["editor"], "code:debug")

    def test_editor_cannot_system_action(self):
        with self.assertRaises(AuthorizationError):
            self.rbac.authorize(["editor"], "system:restart")

    def test_editor_effective_perms(self):
        perms = self.rbac.get_effective_permissions(["editor"])
        self.assertEqual(perms, {"doc:read", "doc:write", "code:run"})


class TestDenialAnonymous(unittest.TestCase):
    """无角色（匿名用户）拒绝场景。"""

    def setUp(self):
        reset_rbac()
        self.rbac = RBACMiddleware()

    def test_no_roles_cannot_read_doc(self):
        with self.assertRaises(AuthorizationError):
            self.rbac.authorize([], "doc:read")

    def test_no_roles_cannot_write_doc(self):
        with self.assertRaises(AuthorizationError):
            self.rbac.authorize([], "doc:write")

    def test_no_roles_cannot_run_code(self):
        with self.assertRaises(AuthorizationError):
            self.rbac.authorize([], "code:run")

    def test_no_roles_cannot_manage_user(self):
        with self.assertRaises(AuthorizationError):
            self.rbac.authorize([], "user:manage")

    def test_none_roles_list(self):
        """None 作为 roles 应抛出 TypeError（类型不匹配）。"""
        with self.assertRaises(TypeError):
            self.rbac.authorize(None, "doc:read")  # type: ignore

    def test_empty_effective_perms(self):
        perms = self.rbac.get_effective_permissions([])
        self.assertEqual(perms, set())


class TestDenialWildcardBoundary(unittest.TestCase):
    """通配符权限边界拒绝场景。"""

    def setUp(self):
        reset_rbac()
        self.rbac = RBACMiddleware()
        # 只给 doc:* 不给 user:*
        self.rbac.register_role("doc_admin", {"doc:*"})

    def test_doc_admin_cannot_manage_user(self):
        with self.assertRaises(AuthorizationError):
            self.rbac.authorize(["doc_admin"], "user:manage")

    def test_doc_admin_cannot_run_code(self):
        with self.assertRaises(AuthorizationError):
            self.rbac.authorize(["doc_admin"], "code:run")

    def test_doc_admin_can_delete_doc(self):
        # 确保 doc:* 确实匹配 doc:delete
        self.assertTrue(self.rbac.has_permission(["doc_admin"], "doc:delete"))

    def test_doc_admin_can_read_doc(self):
        self.assertTrue(self.rbac.has_permission(["doc_admin"], "doc:read"))

    # code:* 只匹配 code 资源
    def test_code_admin_cannot_read_doc(self):
        self.rbac.register_role("code_admin", {"code:*"})
        with self.assertRaises(AuthorizationError):
            self.rbac.authorize(["code_admin"], "doc:read")

    def test_code_admin_can_debug_code(self):
        self.rbac.register_role("code_admin", {"code:*"})
        self.assertTrue(self.rbac.has_permission(["code_admin"], "code:debug"))

    # 跨资源通配符不应泄漏
    def test_wildcard_does_not_leak_across_resources(self):
        self.rbac.register_role("limited", {"doc:read"})
        with self.assertRaises(AuthorizationError):
            self.rbac.authorize(["limited"], "user:read")


class TestDenialDecorator(unittest.TestCase):
    """装饰器权限拒绝场景。"""

    def setUp(self):
        reset_rbac()
        self.rbac = RBACMiddleware()

    def test_decorator_rejects_unauthorized(self):
        @self.rbac.require_permission("doc:write")
        def write_doc(user, content):
            return content

        guest_user = {"roles": ["guest"], "username": "guest"}
        with self.assertRaises(AuthorizationError):
            write_doc(guest_user, "hello")

    def test_decorator_accepts_authorized(self):
        @self.rbac.require_permission("doc:read")
        def read_doc(user, path):
            return f"read {path}"

        guest_user = {"roles": ["guest"], "username": "guest"}
        result = read_doc(guest_user, "file.txt")
        self.assertEqual(result, "read file.txt")

    def test_decorator_rejects_non_dict_user(self):
        @self.rbac.require_permission("doc:read")
        def read_doc(user, path):
            return path

        with self.assertRaises(TypeError):
            read_doc("not_a_dict", "file.txt")  # type: ignore

    def test_decorator_rejects_empty_roles(self):
        @self.rbac.require_permission("doc:read")
        def read_doc(user, path):
            return path

        empty_user = {"roles": [], "username": "anonymous"}
        with self.assertRaises(AuthorizationError):
            read_doc(empty_user, "file.txt")

    def test_require_any_all_fail(self):
        @self.rbac.require_any_permission("doc:write", "user:manage")
        def modify(user, action):
            return action

        guest_user = {"roles": ["guest"], "username": "guest"}
        with self.assertRaises(AuthorizationError) as ctx:
            modify(guest_user, "delete")
        self.assertIn("doc:write", str(ctx.exception))
        self.assertIn("user:manage", str(ctx.exception))

    def test_require_any_one_succeeds(self):
        @self.rbac.require_any_permission("doc:write", "doc:delete")
        def modify_doc(user, action):
            return action

        editor_user = {"roles": ["editor"], "username": "editor"}
        result = modify_doc(editor_user, "delete")
        self.assertEqual(result, "delete")


class TestDenialCustomRole(unittest.TestCase):
    """自定义角色拒绝场景。"""

    def setUp(self):
        reset_rbac()
        self.rbac = RBACMiddleware()

    def test_custom_role_missing_permission(self):
        self.rbac.register_role("reader", {"doc:read"})
        with self.assertRaises(AuthorizationError):
            self.rbac.authorize(["reader"], "doc:write")

    def test_custom_role_has_expected_perms(self):
        self.rbac.register_role("reader", {"doc:read"})
        self.assertTrue(self.rbac.has_permission(["reader"], "doc:read"))
        self.assertFalse(self.rbac.has_permission(["reader"], "doc:write"))

    def test_custom_role_no_default_perms(self):
        self.rbac.register_role("stranger", set())
        with self.assertRaises(AuthorizationError):
            self.rbac.authorize(["stranger"], "doc:read")

    def test_unknown_role_denied(self):
        with self.assertRaises(AuthorizationError):
            self.rbac.authorize(["nonexistent_role"], "doc:read")


class TestDenialResourceContext(unittest.TestCase):
    """带 resource 上下文的授权拒绝。"""

    def setUp(self):
        reset_rbac()
        self.rbac = RBACMiddleware()

    def test_denial_message_includes_resource(self):
        with self.assertRaises(AuthorizationError) as ctx:
            self.rbac.authorize(["guest"], "doc:write", resource="secret_doc.pdf")
        self.assertIn("resource=secret_doc.pdf", str(ctx.exception))

    def test_denial_message_without_resource(self):
        with self.assertRaises(AuthorizationError) as ctx:
            self.rbac.authorize(["guest"], "doc:write")
        self.assertNotIn("resource=", str(ctx.exception))
        self.assertIn("doc:write", str(ctx.exception))


class TestDenialMultiRole(unittest.TestCase):
    """多角色合并后的权限拒绝场景。"""

    def setUp(self):
        reset_rbac()
        self.rbac = RBACMiddleware()

    def test_guest_plus_viewer_still_cannot_write(self):
        """guest + viewer 合并后仍不能写文档。"""
        with self.assertRaises(AuthorizationError):
            self.rbac.authorize(["guest", "viewer"], "doc:write")

    def test_guest_plus_editor_can_write(self):
        """guest + editor 合并后可写文档。"""
        self.assertTrue(self.rbac.has_permission(["guest", "editor"], "doc:write"))

    def test_viewer_plus_guest_no_extra_perms(self):
        """viewer + guest 合并后权限与 viewer 相同。"""
        perms = self.rbac.get_effective_permissions(["viewer", "guest"])
        self.assertEqual(perms, {"doc:read", "code:run"})

    def test_three_roles_combined(self):
        self.rbac.register_role("sec", {"user:manage"})
        perms = self.rbac.get_effective_permissions(["guest", "viewer", "sec"])
        self.assertIn("doc:read", perms)
        self.assertIn("code:run", perms)
        self.assertIn("user:manage", perms)
        self.assertNotIn("doc:write", perms)


class TestDenialEdgeCases(unittest.TestCase):
    """边界与异常场景。"""

    def setUp(self):
        reset_rbac()
        self.rbac = RBACMiddleware()

    def test_duplicate_roles_no_effect(self):
        """重复角色不应产生额外权限。"""
        self.assertTrue(self.rbac.has_permission(["viewer", "viewer"], "doc:read"))
        with self.assertRaises(AuthorizationError):
            self.rbac.authorize(["viewer", "viewer"], "doc:write")

    def test_permission_with_colon_in_value(self):
        """权限值包含冒号时匹配行为。"""
        self.rbac.register_role("custom", {"api:v1:read"})
        self.assertTrue(self.rbac.has_permission(["custom"], "api:v1:read"))
        self.assertFalse(self.rbac.has_permission(["custom"], "api:v2:read"))

    def test_remove_role_then_check(self):
        """删除角色后权限立即失效。"""
        self.rbac.register_role("temp", {"doc:write"})
        self.assertTrue(self.rbac.has_permission(["temp"], "doc:write"))
        self.rbac.remove_role("temp")
        with self.assertRaises(AuthorizationError):
            self.rbac.authorize(["temp"], "doc:write")

    def test_overwrite_role_restricts_perms(self):
        """覆盖角色定义缩小权限范围。"""
        self.rbac.register_role("editor", {"doc:read"})  # 原 editor 有 write
        with self.assertRaises(AuthorizationError):
            self.rbac.authorize(["editor"], "doc:write")
        self.assertTrue(self.rbac.has_permission(["editor"], "doc:read"))

    def test_empty_string_role(self):
        """空字符串角色不应授予权限。"""
        with self.assertRaises(AuthorizationError):
            self.rbac.authorize([""], "doc:read")

    def test_none_in_roles_list(self):
        """roles 列表中包含 None 不应崩溃且仍拒绝。"""
        with self.assertRaises(AuthorizationError):
            self.rbac.authorize([None], "doc:read")  # type: ignore


if __name__ == "__main__":
    unittest.main()
