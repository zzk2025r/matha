"""RBAC 集成测试 — 与 SessionManager 联合测试。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.auth import SessionManager, RBACMiddleware, AuthorizationError, AuthenticationError
from src.auth.rbac import Permission, get_rbac, reset_rbac


class TestRBACWithSessionManager(unittest.TestCase):
    """RBAC + SessionManager 联合集成测试。"""

    def setUp(self):
        reset_rbac()
        self.mgr = SessionManager()
        self.rbac = RBACMiddleware()

    # ---- 基于角色的访问控制 ----

    def test_admin_full_access(self):
        """管理员拥有所有权限。"""
        self.mgr.register("admin", "admin@test.com", "Admin1234", roles=["admin"])
        session = self.mgr.login("admin", "Admin1234")
        payload = self.mgr.verify_access_token(session.token)

        self.rbac.authorize(payload["roles"], "doc:read")
        self.rbac.authorize(payload["roles"], "doc:write")
        self.rbac.authorize(payload["roles"], "doc:delete")
        self.rbac.authorize(payload["roles"], "user:manage")
        self.rbac.authorize(payload["roles"], "code:run")
        self.rbac.authorize(payload["roles"], "code:debug")

    def test_editor_can_write_doc(self):
        """编辑者可读写文档，但不能管理用户。"""
        self.mgr.register("editor", "editor@test.com", "Editor1234", roles=["editor"])
        session = self.mgr.login("editor", "Editor1234")
        payload = self.mgr.verify_access_token(session.token)

        self.rbac.authorize(payload["roles"], "doc:read")
        self.rbac.authorize(payload["roles"], "doc:write")
        self.rbac.authorize(payload["roles"], "code:run")

        with self.assertRaises(AuthorizationError):
            self.rbac.authorize(payload["roles"], "doc:delete")
        with self.assertRaises(AuthorizationError):
            self.rbac.authorize(payload["roles"], "user:manage")

    def test_viewer_read_only(self):
        """查看者只能阅读，不能写入。"""
        self.mgr.register("viewer", "viewer@test.com", "Viewer1234", roles=["viewer"])
        session = self.mgr.login("viewer", "Viewer1234")
        payload = self.mgr.verify_access_token(session.token)

        self.rbac.authorize(payload["roles"], "doc:read")
        self.rbac.authorize(payload["roles"], "code:run")

        with self.assertRaises(AuthorizationError):
            self.rbac.authorize(payload["roles"], "doc:write")
        with self.assertRaises(AuthorizationError):
            self.rbac.authorize(payload["roles"], "doc:delete")

    def test_guest_limited(self):
        """访客只能阅读文档。"""
        self.mgr.register("guest", "guest@test.com", "Guest1234", roles=["guest"])
        session = self.mgr.login("guest", "Guest1234")
        payload = self.mgr.verify_access_token(session.token)

        self.rbac.authorize(payload["roles"], "doc:read")

        with self.assertRaises(AuthorizationError):
            self.rbac.authorize(payload["roles"], "doc:write")
        with self.assertRaises(AuthorizationError):
            self.rbac.authorize(payload["roles"], "code:run")

    def test_disabled_user_cannot_auth(self):
        """禁用用户在 RBAC 检查前就被拒绝。"""
        self.mgr.register("banned", "banned@test.com", "Banned1234", roles=["admin"])
        user = self.mgr.get_user("banned")
        user.is_active = False
        self.assertFalse(user.is_active)

        with self.assertRaises(AuthenticationError):
            self.mgr.login("banned", "Banned1234")

    def test_custom_role(self):
        """自定义角色的权限控制。"""
        self.rbac.register_role("developer", {"doc:read", "doc:write", "code:run", "code:debug"})
        self.mgr.register("dev", "dev@test.com", "Dev1234", roles=["developer"])
        session = self.mgr.login("dev", "Dev1234")
        payload = self.mgr.verify_access_token(session.token)

        self.rbac.authorize(payload["roles"], "doc:write")
        self.rbac.authorize(payload["roles"], "code:debug")
        with self.assertRaises(AuthorizationError):
            self.rbac.authorize(payload["roles"], "user:manage")

    def test_permission_decorator_with_session(self):
        """装饰器在真实会话上下文中的使用。"""
        self.mgr.register("writer", "writer@test.com", "Writer1234", roles=["editor"])
        session = self.mgr.login("writer", "Writer1234")
        payload = self.mgr.verify_access_token(session.token)

        @self.rbac.require_permission("doc:write")
        def create_doc(user_info, name):
            return f"Created: {name}"

        result = create_doc(payload, "report.md")
        self.assertEqual(result, "Created: report.md")

        # 降权后应拒绝
        payload["roles"] = ["viewer"]
        with self.assertRaises(AuthorizationError):
            create_doc(payload, "report.md")

    def test_multiple_roles_combined(self):
        """多角色权限合并。"""
        self.rbac.register_role("sec_admin", {"user:manage", "system:*"})
        self.mgr.register("user1", "u1@test.com", "User1Pass1", roles=["viewer", "sec_admin"])
        session = self.mgr.login("user1", "User1Pass1")
        payload = self.mgr.verify_access_token(session.token)

        self.rbac.authorize(payload["roles"], "doc:read")       # from viewer
        self.rbac.authorize(payload["roles"], "user:manage")    # from sec_admin
        self.rbac.authorize(payload["roles"], "system:shutdown")  # from sec_admin wildcard

    def test_all_roles_matrix(self):
        """全角色权限矩阵测试。"""
        roles_config = {
            "admin":    {"doc:read", "doc:write", "doc:delete", "user:manage", "code:run", "code:debug", "system:restart"},
            "editor":   {"doc:read", "doc:write", "code:run"},
            "viewer":   {"doc:read", "code:run"},
            "guest":    {"doc:read"},
        }

        for role_name, expected_perms in roles_config.items():
            self.mgr.register(role_name, f"{role_name}@test.com", f"{role_name.capitalize()}Pass1", roles=[role_name])
            session = self.mgr.login(role_name, f"{role_name.capitalize()}Pass1")
            payload = self.mgr.verify_access_token(session.token)

            for perm in expected_perms:
                with self.subTest(role=role_name, perm=perm):
                    self.assertTrue(
                        self.rbac.has_permission(payload["roles"], perm),
                        f"{role_name} 应拥有 {perm}"
                    )

            self.mgr.logout(session.session_id)


if __name__ == "__main__":
    unittest.main()
