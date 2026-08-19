"""用户登录认证模块 — 单元测试。"""
from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.auth import (
    SessionManager,
    User,
    Session,
    encode_token,
    decode_token,
    encode_refresh_token,
    hash_password,
    verify_password,
    validate_password_strength,
    AuthenticationError,
    AuthorizationError,
    TokenError,
    RegistrationError,
)


class TestPasswordHash(unittest.TestCase):
    """密码哈希单元测试。"""

    def test_hash_and_verify(self):
        """正确密码验证通过。"""
        h = hash_password("MyPass123")
        self.assertTrue(verify_password("MyPass123", h))

    def test_wrong_password(self):
        """错误密码验证失败。"""
        h = hash_password("MyPass123")
        self.assertFalse(verify_password("WrongPass1", h))

    def test_unique_hashes(self):
        """同一密码每次哈希结果不同（salt 随机）。"""
        h1 = hash_password("SamePass1")
        h2 = hash_password("SamePass1")
        self.assertNotEqual(h1, h2)
        self.assertTrue(verify_password("SamePass1", h1))
        self.assertTrue(verify_password("SamePass1", h2))

    def test_validate_strength_pass(self):
        """强度足够的密码通过校验。"""
        ok, msg = validate_password_strength("Abcdefg1")
        self.assertTrue(ok)

    def test_validate_strength_too_short(self):
        """短密码被拒绝。"""
        ok, msg = validate_password_strength("Ab1")
        self.assertFalse(ok)
        self.assertIn("6", msg)

    def test_validate_strength_no_digit(self):
        """无数字的密码被拒绝。"""
        ok, msg = validate_password_strength("Abcdefgh")
        self.assertFalse(ok)
        self.assertIn("数字", msg)

    def test_validate_strength_no_letter(self):
        """无字母的密码被拒绝。"""
        ok, msg = validate_password_strength("12345678")
        self.assertFalse(ok)
        self.assertIn("字母", msg)

    def test_verify_malformed_hash(self):
        """格式错误的哈希不会崩溃。"""
        self.assertFalse(verify_password("any", "bad-format"))


class TestJWT(unittest.TestCase):
    """JWT 令牌单元测试。"""

    def test_encode_decode(self):
        """正常编码解码。"""
        tok = encode_token({"sub": "test", "type": "access"})
        payload = decode_token(tok)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["sub"], "test")
        self.assertEqual(payload["type"], "access")

    def test_expired_token(self):
        """过期令牌返回 None。"""
        tok = encode_token({"sub": "test"}, exp_hours=-1)
        self.assertIsNone(decode_token(tok))

    def test_tampered_token(self):
        """篡改签名后解码失败。"""
        tok = encode_token({"sub": "test"})
        parts = tok.split(".")
        parts[2] = "tampered" + parts[2][10:]
        bad_tok = ".".join(parts)
        self.assertIsNone(decode_token(bad_tok))

    def test_invalid_format(self):
        """格式错误的令牌返回 None。"""
        self.assertIsNone(decode_token("not-a-token"))
        self.assertIsNone(decode_token("a.b"))


class TestSessionManager(unittest.TestCase):
    """SessionManager 核心功能单元测试。"""

    def setUp(self):
        self.mgr = SessionManager()

    # ---- 注册 ----

    def test_register_success(self):
        """正常注册返回 User。"""
        user = self.mgr.register("alice", "alice@test.com", "Alice123")
        self.assertIsInstance(user, User)
        self.assertEqual(user.username, "alice")
        self.assertEqual(user.email, "alice@test.com")
        self.assertTrue(user.is_active)
        self.assertEqual(user.roles, [])

    def test_register_duplicate_username(self):
        """重复用户名抛出 RegistrationError。"""
        self.mgr.register("bob", "bob@test.com", "Bob1234")
        with self.assertRaises(RegistrationError):
            self.mgr.register("bob", "bob2@test.com", "Bob1234")

    def test_register_empty_username(self):
        """空用户名抛出异常。"""
        with self.assertRaises(RegistrationError):
            self.mgr.register("", "x@x.com", "Xxx12345")

    def test_register_invalid_email(self):
        """无效邮箱抛出异常。"""
        with self.assertRaises(RegistrationError):
            self.mgr.register("charlie", "noemail", "Charlie1")

    def test_register_weak_password(self):
        """弱密码抛出异常。"""
        with self.assertRaises(RegistrationError):
            self.mgr.register("dave", "dave@test.com", "weak")

    def test_register_roles(self):
        """注册时指定角色。"""
        user = self.mgr.register("eve", "eve@test.com", "EvePass1", roles=["admin"])
        self.assertEqual(user.roles, ["admin"])

    # ---- 登录 ----

    def test_login_success(self):
        """正确凭据登录成功。"""
        self.mgr.register("frank", "frank@test.com", "Frank123")
        session = self.mgr.login("frank", "Frank123")
        self.assertIsInstance(session, Session)
        self.assertEqual(session.username, "frank")
        self.assertTrue(len(session.token) > 10)
        self.assertTrue(len(session.refresh_token) > 10)

    def test_login_wrong_password(self):
        """错误密码抛出 AuthenticationError。"""
        self.mgr.register("grace", "grace@test.com", "Grace123")
        with self.assertRaises(AuthenticationError):
            self.mgr.login("grace", "WrongPass")

    def test_login_nonexistent_user(self):
        """不存在的用户抛出 AuthenticationError。"""
        with self.assertRaises(AuthenticationError):
            self.mgr.login("nobody", "AnyPass1")

    def test_login_case_insensitive(self):
        """用户名大小写不敏感。"""
        self.mgr.register("Hank", "hank@test.com", "Hank1234")
        session = self.mgr.login("hank", "Hank1234")
        self.assertEqual(session.username, "hank")

    # ---- 令牌刷新 ----

    def test_refresh_token(self):
        """refresh token 可以换取新令牌对。"""
        self.mgr.register("iris", "iris@test.com", "Iris1234")
        session = self.mgr.login("iris", "Iris1234")
        new_access, new_refresh = self.mgr.refresh_token(session.refresh_token)
        self.assertTrue(len(new_access) > 10)
        self.assertTrue(len(new_refresh) > 10)
        # 旧 refresh token 失效
        with self.assertRaises(TokenError):
            self.mgr.refresh_token(session.refresh_token)

    # ---- 登出 ----

    def test_logout(self):
        """登出后会话失效。"""
        self.mgr.register("jack", "jack@test.com", "Jack1234")
        session = self.mgr.login("jack", "Jack1234")
        self.assertTrue(self.mgr.logout(session.session_id))
        self.assertIsNone(self.mgr.get_session(session.session_id))

    def test_logout_invalid_session(self):
        """登出不存在的会话返回 False。"""
        self.assertFalse(self.mgr.logout("nonexistent-session-id"))

    # ---- 多会话 ----

    def test_multiple_sessions(self):
        """同一用户可有多条活跃会话。"""
        self.mgr.register("kate", "kate@test.com", "Kate1234")
        s1 = self.mgr.login("kate", "Kate1234")
        s2 = self.mgr.login("kate", "Kate1234")
        self.assertEqual(self.mgr.get_active_session_count("kate"), 2)
        self.mgr.logout(s1.session_id)
        self.assertEqual(self.mgr.get_active_session_count("kate"), 1)

    def test_invalidate_all_sessions(self):
        """踢出所有会话。"""
        self.mgr.register("leo", "leo@test.com", "Leo1234")
        s1 = self.mgr.login("leo", "Leo1234")
        s2 = self.mgr.login("leo", "Leo1234")
        count = self.mgr.invalidate_all_sessions("leo")
        self.assertEqual(count, 2)
        self.assertEqual(self.mgr.get_active_session_count("leo"), 0)

    # ---- 权限 ----

    def test_disabled_user_cannot_login(self):
        """禁用账号无法登录。"""
        self.mgr.register("mike", "mike@test.com", "Mike1234")
        user = self.mgr.get_user("mike")
        user.is_active = False
        with self.assertRaises(AuthenticationError):
            self.mgr.login("mike", "Mike1234")

    def test_verify_access_token(self):
        """access token 验证正确。"""
        self.mgr.register("nancy", "nancy@test.com", "Nancy1234")
        session = self.mgr.login("nancy", "Nancy1234")
        payload = self.mgr.verify_access_token(session.token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["sub"], "nancy")

    def test_verify_invalid_token(self):
        """无效 token 验证失败。"""
        self.assertIsNone(self.mgr.verify_access_token("invalid-token"))

    # ---- 查询 ----

    def test_get_user(self):
        """查询用户。"""
        self.mgr.register("oscar", "oscar@test.com", "Oscar1234")
        user = self.mgr.get_user("oscar")
        self.assertIsNotNone(user)
        self.assertEqual(user.email, "oscar@test.com")
        self.assertIsNone(self.mgr.get_user("nobody"))

    def test_get_all_usernames(self):
        """列出所有用户。"""
        self.mgr.register("u1", "u1@test.com", "U1Pass123")
        self.mgr.register("u2", "u2@test.com", "U2Pass123")
        names = self.mgr.get_all_usernames()
        self.assertEqual(sorted(names), ["u1", "u2"])

    def test_count_users(self):
        """用户计数正确。"""
        self.assertEqual(self.mgr.count_users(), 0)
        self.mgr.register("a", "a@t.com", "APass123")
        self.assertEqual(self.mgr.count_users(), 1)


class TestAuthIntegration(unittest.TestCase):
    """端到端认证流程集成测试。"""

    def test_full_flow(self):
        """注册 → 登录 → 刷新 → 登出 完整流程。"""
        mgr = SessionManager()

        # 注册
        user = mgr.register("testuser", "test@example.com", "TestPass1")
        self.assertEqual(user.username, "testuser")

        # 登录
        session = mgr.login("testuser", "TestPass1")
        self.assertIsNotNone(session.token)

        # 验证 token
        payload = mgr.verify_access_token(session.token)
        self.assertEqual(payload["sub"], "testuser")

        # 刷新
        new_access, new_refresh = mgr.refresh_token(session.refresh_token)
        self.assertIsNotNone(new_access)

        # 登出
        self.assertTrue(mgr.logout(session.session_id))
        self.assertIsNone(mgr.get_session(session.session_id))


if __name__ == "__main__":
    unittest.main()
