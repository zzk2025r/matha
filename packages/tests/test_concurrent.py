"""matha-auth 单元测试 — 并发安全与边界场景"""
from __future__ import annotations
import sys
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from matha_auth import (
    SessionManager,
    RBACMiddleware,
    PermissionChangeAPI,
    TokenError,
    AuthorizationError,
)
from matha_auth.rbac import reset_rbac


# 密码满足 >=6 字符 + 字母 + 数字
PW = "Pass1x"


class TestConcurrentLogin(unittest.TestCase):
    """并发登录安全测试。"""

    def test_concurrent_registration_and_login(self):
        mgr = SessionManager()
        errors = []

        def worker(i: int):
            try:
                mgr.register(f"conuser{i}", f"con{i}@t.com", PW)
                s = mgr.login(f"conuser{i}", PW)
                self.assertIsNotNone(s.token)
                mgr.logout(s.session_id)
            except Exception as e:
                errors.append(e)

        with ThreadPoolExecutor(max_workers=20) as pool:
            futures = [pool.submit(worker, i) for i in range(50)]
            for f in as_completed(futures):
                f.result()

        self.assertEqual(len(errors), 0, f"并发错误: {errors[:3]}")
        self.assertEqual(mgr.count_users(), 50)


class TestConcurrentRefresh(unittest.TestCase):
    """并发 Token 刷新安全测试。"""

    def test_concurrent_refresh_same_user(self):
        mgr = SessionManager()
        mgr.register("race_user", "race@test.com", PW)
        session = mgr.login("race_user", PW)
        original_rt = session.refresh_token

        results = {"first": None, "second_error": False}

        def try_refresh():
            try:
                access, refresh = mgr.refresh_token(original_rt)
                results["first"] = access
            except TokenError:
                results["second_error"] = True

        t1 = threading.Thread(target=try_refresh)
        t2 = threading.Thread(target=try_refresh)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        self.assertIsNotNone(results["first"], "第一次刷新应成功")
        self.assertTrue(results["second_error"], "并发第二次应被拒绝")
        mgr.logout(session.session_id)


class TestConcurrentRBAC(unittest.TestCase):
    """并发 RBAC 权限检查测试。"""

    def test_concurrent_permission_checks(self):
        rbac = RBACMiddleware()
        errors = []

        def worker(i: int):
            try:
                roles = ["viewer", "editor"] if i % 2 == 0 else ["guest"]
                rbac.authorize(roles, "doc:read")
            except Exception as e:
                errors.append(e)

        with ThreadPoolExecutor(max_workers=20) as pool:
            futures = [pool.submit(worker, i) for i in range(100)]
            for f in as_completed(futures):
                f.result()

        self.assertEqual(len(errors), 0)


class TestEdgeCases(unittest.TestCase):
    """边界条件测试。"""

    def test_logout_already_logout_session(self):
        mgr = SessionManager()
        mgr.register("user_u", "u@t.com", PW)
        s = mgr.login("user_u", PW)
        mgr.logout(s.session_id)
        result = mgr.logout(s.session_id)
        self.assertFalse(result)

    def test_verify_after_multiple_logouts(self):
        mgr = SessionManager()
        mgr.register("user_u", "u@t.com", PW)
        s = mgr.login("user_u", PW)
        mgr.logout(s.session_id)
        self.assertIsNone(mgr.verify_access_token(s.token))
        self.assertIsNone(mgr.verify_access_token(s.token))

    def test_refresh_after_logout(self):
        mgr = SessionManager()
        mgr.register("user_u", "u@t.com", PW)
        s = mgr.login("user_u", PW)
        mgr.logout(s.session_id)
        with self.assertRaises(TokenError):
            mgr.refresh_token(s.refresh_token)

    def test_get_session_expired(self):
        mgr = SessionManager()
        mgr.register("user_u", "u@t.com", PW)
        s = mgr.login("user_u", PW)
        s.expires_at = time.time() - 100
        result = mgr.get_session(s.session_id)
        self.assertIsNone(result)

    def test_empty_role_list(self):
        reset_rbac()
        rbac = RBACMiddleware()
        self.assertFalse(rbac.has_permission([], "doc:read"))
        with self.assertRaises(AuthorizationError):
            rbac.authorize([], "doc:read")

    def test_role_with_empty_string(self):
        reset_rbac()
        rbac = RBACMiddleware()
        self.assertFalse(rbac.has_permission(["", "viewer"], "doc:write"))
        self.assertTrue(rbac.has_permission(["", "viewer"], "doc:read"))


class TestRBACCacheConsistency(unittest.TestCase):
    """权限缓存一致性测试。"""

    def test_cache_consistent_after_register(self):
        reset_rbac()
        rbac = RBACMiddleware()
        rbac.register_role("custom", {"doc:write"})
        _ = rbac.get_effective_permissions(["custom"])
        rbac.register_role("custom", {"doc:read"})
        r2 = rbac.get_effective_permissions(["custom"])
        self.assertTrue(rbac.has_permission(["custom"], "doc:read"))
        self.assertFalse(rbac.has_permission(["custom"], "doc:write"))

    def test_cache_consistent_after_remove(self):
        reset_rbac()
        rbac = RBACMiddleware()
        rbac.register_role("temp", {"doc:write"})
        r1 = rbac.get_effective_permissions(["temp"])
        self.assertTrue(rbac.has_permission(["temp"], "doc:write"))
        rbac.remove_role("temp")
        r2 = rbac.get_effective_permissions(["temp"])
        self.assertEqual(r2, frozenset())


if __name__ == "__main__":
    unittest.main()
