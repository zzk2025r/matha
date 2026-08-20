"""matha-auth 单元测试 — SessionManager 核心逻辑"""
from __future__ import annotations
import sys
import time
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).parent.parent))

from matha_auth import (
    SessionManager,
    RBACMiddleware,
    PermissionChangeAPI,
    AuthenticationError,
    AuthorizationError,
    TokenError,
    RegistrationError,
)
from matha_auth.rbac import reset_rbac, Permission


# 所有测试用密码均满足 >=6 字符 + 字母 + 数字 要求
PW = "Pass1x"


class TestSessionManagerRegister(unittest.TestCase):
    """用户注册测试。"""

    def setUp(self):
        self.mgr = SessionManager()

    def test_register_success(self):
        user = self.mgr.register("alice", "alice@test.com", PW)
        self.assertEqual(user.username, "alice")
        self.assertEqual(user.email, "alice@test.com")
        self.assertEqual(user.roles, [])
        self.assertTrue(user.is_active)
        self.assertIsNotNone(user.password_hash)

    def test_register_with_roles(self):
        user = self.mgr.register("bob", "bob@test.com", PW, roles=["viewer"])
        self.assertEqual(user.roles, ["viewer"])

    def test_register_duplicate_user(self):
        self.mgr.register("alice", "alice@test.com", PW)
        with self.assertRaises(RegistrationError):
            self.mgr.register("alice", "alice2@test.com", PW)

    def test_register_empty_username(self):
        with self.assertRaises(RegistrationError):
            self.mgr.register("", "x@test.com", PW)

    def test_register_whitespace_username(self):
        user = self.mgr.register("  Alice  ", "a@test.com", PW)
        self.assertEqual(user.username, "alice")

    def test_register_invalid_email(self):
        with self.assertRaises(RegistrationError):
            self.mgr.register("x", "notanemail", PW)

    def test_register_weak_password_short(self):
        with self.assertRaises(RegistrationError):
            self.mgr.register("x", "x@test.com", "Ab1")

    def test_register_weak_password_no_letter(self):
        with self.assertRaises(RegistrationError):
            self.mgr.register("x", "x@test.com", "123456")

    def test_register_weak_password_no_digit(self):
        with self.assertRaises(RegistrationError):
            self.mgr.register("x", "x@test.com", "abcdefgh")

    def test_register_case_insensitive_username(self):
        self.mgr.register("Alice", "a@test.com", PW)
        with self.assertRaises(RegistrationError):
            self.mgr.register("ALICE", "a2@test.com", PW)


class TestSessionManagerLogin(unittest.TestCase):
    """用户登录测试。"""

    def setUp(self):
        self.mgr = SessionManager()
        self.mgr.register("alice", "alice@test.com", PW)

    def test_login_success(self):
        session = self.mgr.login("alice", PW)
        self.assertIsNotNone(session.session_id)
        self.assertEqual(session.username, "alice")
        self.assertTrue(session.is_valid)
        self.assertIsNotNone(session.token)
        self.assertIsNotNone(session.refresh_token)

    def test_login_case_insensitive(self):
        session = self.mgr.login("ALICE", PW)
        self.assertIsNotNone(session)

    def test_login_wrong_password(self):
        with self.assertRaises(AuthenticationError):
            self.mgr.login("alice", "WrongPass")

    def test_login_nonexistent_user(self):
        with self.assertRaises(AuthenticationError):
            self.mgr.login("nobody", PW)

    def test_login_disabled_user(self):
        self.mgr.get_user("alice").is_active = False
        with self.assertRaises(AuthenticationError):
            self.mgr.login("alice", PW)

    def test_login_sets_last_login(self):
        self.mgr.login("alice", PW)
        user = self.mgr.get_user("alice")
        self.assertIsNotNone(user.last_login)
        self.assertGreater(user.last_login, time.time() - 60)


class TestSessionManagerLogout(unittest.TestCase):
    """登出测试。"""

    def setUp(self):
        self.mgr = SessionManager()
        self.mgr.register("alice", "alice@test.com", PW)
        self.session = self.mgr.login("alice", PW)

    def test_logout_success(self):
        result = self.mgr.logout(self.session.session_id)
        self.assertTrue(result)

    def test_logout_invalidates_token(self):
        self.mgr.logout(self.session.session_id)
        payload = self.mgr.verify_access_token(self.session.token)
        self.assertIsNone(payload)

    def test_logout_nonexistent_session(self):
        result = self.mgr.logout("nonexistent-id")
        self.assertFalse(result)

    def test_logout_cleans_reverse_index(self):
        self.mgr.logout(self.session.session_id)
        self.assertNotIn("alice", self.mgr._user_sessions)


class TestSessionManagerTokenRefresh(unittest.TestCase):
    """Token 刷新测试。"""

    def setUp(self):
        self.mgr = SessionManager()
        self.mgr.register("alice", "alice@test.com", PW)
        self.session = self.mgr.login("alice", PW)

    def test_refresh_success(self):
        access, refresh = self.mgr.refresh_token(self.session.refresh_token)
        self.assertIsInstance(access, str)
        self.assertIsInstance(refresh, str)
        self.assertNotEqual(access, self.session.token)
        self.assertNotEqual(refresh, self.session.refresh_token)

    def test_refresh_invalid_token(self):
        with self.assertRaises(TokenError):
            self.mgr.refresh_token("invalid-token")

    def test_refresh_used_token_revoked(self):
        """同一 refresh token 只能使用一次。"""
        self.mgr.refresh_token(self.session.refresh_token)
        with self.assertRaises(TokenError):
            self.mgr.refresh_token(self.session.refresh_token)

    def test_refresh_disabled_user(self):
        self.mgr.get_user("alice").is_active = False
        with self.assertRaises(AuthorizationError):
            self.mgr.refresh_token(self.session.refresh_token)

    def test_refresh_token_chain_uniqueness(self):
        """连续刷新产生的 token 全部唯一。"""
        tokens = [self.session.refresh_token]
        current = self.session.refresh_token
        for _ in range(5):
            _, current = self.mgr.refresh_token(current)
            tokens.append(current)
        self.assertEqual(len(set(tokens)), 6)


class TestSessionManagerTokenVerify(unittest.TestCase):
    """Token 验证测试。"""

    def setUp(self):
        self.mgr = SessionManager()
        self.mgr.register("alice", "alice@test.com", PW)
        self.session = self.mgr.login("alice", PW)

    def test_verify_valid_token(self):
        payload = self.mgr.verify_access_token(self.session.token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["sub"], "alice")
        self.assertEqual(payload["type"], "access")

    def test_verify_invalid_token(self):
        self.assertIsNone(self.mgr.verify_access_token("bad-token"))

    def test_verify_after_logout(self):
        self.mgr.logout(self.session.session_id)
        self.assertIsNone(self.mgr.verify_access_token(self.session.token))

    def test_verify_after_disable(self):
        self.mgr.get_user("alice").is_active = False
        self.assertIsNone(self.mgr.verify_access_token(self.session.token))

    def test_verify_reverse_index_efficiency(self):
        """反向索引：只查找该用户的会话，不扫描全部。"""
        for i in range(50):
            self.mgr.register(f"user{i}", f"u{i}@t.com", PW)
        payload = self.mgr.verify_access_token(self.session.token)
        self.assertIsNotNone(payload)
        self.assertIn(self.session.session_id, self.mgr._user_sessions.get("alice", []))


class TestSessionManagerInvalidate(unittest.TestCase):
    """踢出所有会话测试。"""

    def setUp(self):
        self.mgr = SessionManager()
        self.mgr.register("alice", "alice@test.com", PW)

    def test_invalidate_all(self):
        s1 = self.mgr.login("alice", PW)
        s2 = self.mgr.login("alice", PW)
        count = self.mgr.invalidate_all_sessions("alice")
        self.assertEqual(count, 2)
        self.assertIsNone(self.mgr.verify_access_token(s1.token))
        self.assertIsNone(self.mgr.verify_access_token(s2.token))

    def test_invalidate_nonexistent_user(self):
        count = self.mgr.invalidate_all_sessions("nobody")
        self.assertEqual(count, 0)

    def test_invalidate_cleans_reverse_index(self):
        self.mgr.login("alice", PW)
        self.mgr.invalidate_all_sessions("alice")
        self.assertNotIn("alice", self.mgr._user_sessions)


class TestSessionManagerQuery(unittest.TestCase):
    """查询方法测试。"""

    def setUp(self):
        self.mgr = SessionManager()
        self.mgr.register("alice", "alice@test.com", PW)
        self.mgr.login("alice", PW)

    def test_get_user(self):
        user = self.mgr.get_user("alice")
        self.assertIsNotNone(user)
        self.assertEqual(user.username, "alice")

    def test_get_session(self):
        s = self.mgr.login("alice", PW)
        session = self.mgr.get_session(s.session_id)
        self.assertIsNotNone(session)
        self.assertEqual(session.username, "alice")

    def test_get_all_usernames(self):
        self.mgr.register("bob", "bob@test.com", PW)
        names = self.mgr.get_all_usernames()
        self.assertIn("alice", names)
        self.assertIn("bob", names)

    def test_count_users(self):
        self.mgr.register("bob", "bob@test.com", PW)
        self.assertEqual(self.mgr.count_users(), 2)

    def test_get_active_session_count(self):
        self.mgr.login("alice", PW)
        count = self.mgr.get_active_session_count("alice")
        self.assertGreaterEqual(count, 1)


class TestReverseIndex(unittest.TestCase):
    """反向会话索引专项测试。"""

    def test_index_maintained_on_login(self):
        mgr = SessionManager()
        mgr.register("u1", "u1@t.com", PW)
        mgr.register("u2", "u2@t.com", PW)
        s1 = mgr.login("u1", PW)
        s2 = mgr.login("u2", PW)
        self.assertIn(s1.session_id, mgr._user_sessions.get("u1", []))
        self.assertIn(s2.session_id, mgr._user_sessions.get("u2", []))
        self.assertNotIn(s2.session_id, mgr._user_sessions.get("u1", []))

    def test_index_cleaned_on_logout(self):
        mgr = SessionManager()
        mgr.register("u1", "u1@t.com", PW)
        s = mgr.login("u1", PW)
        mgr.logout(s.session_id)
        self.assertNotIn("u1", mgr._user_sessions)

    def test_index_cleaned_on_invalidate(self):
        mgr = SessionManager()
        mgr.register("u1", "u1@t.com", PW)
        mgr.login("u1", PW)
        mgr.invalidate_all_sessions("u1")
        self.assertNotIn("u1", mgr._user_sessions)


if __name__ == "__main__":
    unittest.main()
