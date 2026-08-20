"""
matha-auth 集成验证 — SessionManager + RBAC + API 端到端测试
可作为 unittest 或独立脚本运行。
"""
from __future__ import annotations
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from matha_auth import SessionManager, RBACMiddleware, PermissionChangeAPI
from matha_auth.rbac import reset_rbac
from matha_auth.exceptions import AuthorizationError, AuthenticationError

# 满足密码复杂度要求
PW = "Pass1x"


class TestSessionLifecycle(unittest.TestCase):
    """完整会话生命周期测试。"""

    def test_register_login_logout(self):
        mgr = SessionManager()
        user = mgr.register("alice", "alice@test.com", PW)
        self.assertEqual(user.username, "alice")
        self.assertEqual(user.roles, [])

        session = mgr.login("alice", PW)
        self.assertIsNotNone(session.token)
        self.assertIsNotNone(session.refresh_token)

        payload = mgr.verify_access_token(session.token)
        self.assertEqual(payload["sub"], "alice")
        self.assertEqual(payload["type"], "access")

        mgr.logout(session.session_id)
        self.assertIsNone(mgr.verify_access_token(session.token))

    def test_token_refresh_chain(self):
        mgr = SessionManager()
        mgr.register("ref_user", "ref@test.com", PW)
        session = mgr.login("ref_user", PW)

        access, new_refresh = mgr.refresh_token(session.refresh_token)
        self.assertTrue(len(access) > 50)
        self.assertTrue(len(new_refresh) > 50)
        self.assertNotEqual(new_refresh, session.refresh_token)

        # 旧 refresh token 已被撤销
        with self.assertRaises(Exception):
            mgr.refresh_token(session.refresh_token)

        mgr.logout(session.session_id)

    def test_invalid_token(self):
        mgr = SessionManager()
        self.assertIsNone(mgr.verify_access_token("bad-token"))

    def test_disabled_user_cannot_login(self):
        mgr = SessionManager()
        mgr.register("disp", "d@test.com", PW)
        mgr.get_user("disp").is_active = False
        with self.assertRaises(AuthenticationError):
            mgr.login("disp", PW)


class TestReverseIndex(unittest.TestCase):
    """反向会话索引测试。"""

    def test_index_maintained(self):
        mgr = SessionManager()
        mgr.register("u1", "u1@t.com", PW)
        s1 = mgr.login("u1", PW)
        s2 = mgr.login("u1", PW)
        self.assertEqual(len(mgr._user_sessions.get("u1", [])), 2)

        mgr.logout(s1.session_id)
        self.assertEqual(len(mgr._user_sessions.get("u1", [])), 1)

        mgr.invalidate_all_sessions("u1")
        self.assertNotIn("u1", mgr._user_sessions)


class TestRBACPermissions(unittest.TestCase):
    """RBAC 权限矩阵测试。"""

    def setUp(self):
        reset_rbac()
        self.rbac = RBACMiddleware()

    def test_builtin_roles(self):
        self.assertTrue(self.rbac.has_permission(["admin"], "doc:write"))
        self.assertTrue(self.rbac.has_permission(["admin"], "user:manage"))
        self.assertTrue(self.rbac.has_permission(["editor"], "doc:write"))
        self.assertFalse(self.rbac.has_permission(["editor"], "user:manage"))
        self.assertTrue(self.rbac.has_permission(["viewer"], "doc:read"))
        self.assertFalse(self.rbac.has_permission(["viewer"], "doc:write"))
        self.assertTrue(self.rbac.has_permission(["guest"], "doc:read"))
        self.assertFalse(self.rbac.has_permission(["guest"], "code:run"))

    def test_wildcard(self):
        self.rbac.register_role("doc_admin", {"doc:*"})
        self.assertTrue(self.rbac.has_permission(["doc_admin"], "doc:read"))
        self.assertTrue(self.rbac.has_permission(["doc_admin"], "doc:delete"))
        self.assertFalse(self.rbac.has_permission(["doc_admin"], "user:read"))

    def test_multi_role_merge(self):
        self.rbac.register_role("sec", {"user:manage", "system:*"})
        roles = ["viewer", "sec"]
        self.assertTrue(self.rbac.has_permission(roles, "doc:read"))
        self.assertTrue(self.rbac.has_permission(roles, "user:manage"))
        self.assertTrue(self.rbac.has_permission(roles, "system:restart"))
        self.assertFalse(self.rbac.has_permission(roles, "doc:write"))

    def test_cache_consistency(self):
        self.rbac.register_role("temp", {"doc:write"})
        self.assertTrue(self.rbac.has_permission(["temp"], "doc:write"))
        self.assertGreater(len(self.rbac._perm_cache), 0)

        self.rbac.register_role("temp", {"doc:read"})  # 覆盖
        self.assertFalse(self.rbac.has_permission(["temp"], "doc:write"))
        self.assertTrue(self.rbac.has_permission(["temp"], "doc:read"))

        self.rbac.remove_role("temp")
        self.assertEqual(len(self.rbac._perm_cache), 0)
        self.assertFalse(self.rbac.has_permission(["temp"], "doc:read"))


class TestPermissionAPI(unittest.TestCase):
    """权限变更 API 测试。"""

    def setUp(self):
        reset_rbac()
        self.mgr = SessionManager()
        self.rbac = RBACMiddleware()
        self.api = PermissionChangeAPI(self.rbac, self.mgr)
        self.mgr.register("admin_u", "admin@test.com", "AdminPass1", roles=["admin"])
        self.mgr.register("user_u", "user@test.com", "UserPass1", roles=["viewer"])
        self.mgr.login("admin_u", "AdminPass1")

    def test_set_roles(self):
        result = self.api.set_roles("user_u", ["editor"], "admin_u")
        self.assertTrue(result.success)
        self.assertIn("user_u", result.changed)
        self.assertEqual(self.mgr.get_user("user_u").roles, ["editor"])

    def test_audit_log(self):
        self.api.set_roles("user_u", ["editor"], "admin_u")
        entry = self.api.audit_log[0]
        self.assertEqual(entry["type"], "set_role")
        self.assertEqual(entry["target"], "user_u")
        self.assertIn("time", entry)
        self.assertIn("data", entry)

    def test_no_permission(self):
        self.mgr.register("no_perm", "nop@test.com", "NoPerPass1", roles=["viewer"])
        with self.assertRaises(AuthorizationError):
            self.api.set_roles("user_u", ["admin"], "no_perm")

    def test_batch_update(self):
        self.mgr.register("u2", "u2@t.com", "Upass2", roles=["viewer"])
        result = self.api.update_users(["user_u", "u2"], is_active=False, operator="admin_u")
        self.assertEqual(len(result.changed), 2)
        self.assertFalse(self.mgr.get_user("user_u").is_active)
        self.assertFalse(self.mgr.get_user("u2").is_active)


class TestLoginFailures(unittest.TestCase):
    """登录异常场景测试。"""

    def setUp(self):
        self.mgr = SessionManager()
        self.mgr.register("fail_user", "f@test.com", PW)

    def test_wrong_password(self):
        with self.assertRaises(AuthenticationError):
            self.mgr.login("fail_user", "WrongPass")

    def test_nonexistent_user(self):
        with self.assertRaises(AuthenticationError):
            self.mgr.login("nobody", PW)


def main():
    """独立运行入口。"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in [TestSessionLifecycle, TestReverseIndex, TestRBACPermissions,
                TestPermissionAPI, TestLoginFailures]:
        suite.addTests(loader.loadTestsFromTestCase(cls))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
