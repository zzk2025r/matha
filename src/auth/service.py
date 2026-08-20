"""会话管理器 — 内存存储用户与会话。"""
from __future__ import annotations

import logging
import uuid
import time
from typing import Optional

logger = logging.getLogger(__name__)

from src.auth.models import User, Session
from src.auth.jwt import encode_token, encode_refresh_token, decode_token
from src.auth.password import hash_password, verify_password
from src.auth.exceptions import (
    AuthenticationError,
    AuthorizationError,
    TokenError,
    RegistrationError,
)


class SessionManager:
    """内存会话管理器。支持多用户注册、登录、登出、令牌刷新。"""

    def __init__(self) -> None:
        self._users: dict[str, User] = {}
        self._sessions: dict[str, Session] = {}
        self._user_tokens: dict[str, list[str]] = {}
        logger.info("SessionManager 初始化完成")

    # ------------------------------------------------------------------
    # 用户注册
    # ------------------------------------------------------------------

    def register(
        self,
        username: str,
        email: str,
        password: str,
        roles: list[str] | None = None,
    ) -> User:
        """注册新用户。重复用户名抛出 RegistrationError。"""
        logger.info("注册请求: username=%s email=%s roles=%s", username, email, roles)

        if not username or not username.strip():
            raise RegistrationError("用户名不能为空")
        username = username.strip().lower()

        if not email or "@" not in email:
            raise RegistrationError("邮箱格式无效")

        if username in self._users:
            logger.warning("注册失败: 用户名已存在 '%s'", username)
            raise RegistrationError(f"用户名 '{username}' 已存在")

        pw_valid, msg = _validate_password(password)
        if not pw_valid:
            logger.warning("注册失败: 密码强度不足 '%s': %s", username, msg)
            raise RegistrationError(msg)

        hashed = hash_password(password)
        user = User(
            username=username,
            email=email.strip().lower(),
            password_hash=hashed,
            roles=roles or [],
        )
        self._users[username] = user
        logger.info("注册成功: username=%s roles=%s", username, user.roles)
        return user

    # ------------------------------------------------------------------
    # 用户登录
    # ------------------------------------------------------------------

    def login(self, username: str, password: str) -> Session:
        """验证凭据并创建新会话。失败抛出 AuthenticationError。"""
        logger.info("登录请求: username=%s", username)

        username = username.strip().lower()
        user = self._users.get(username)

        if user is None:
            logger.warning("登录失败: 用户不存在 '%s'", username)
            raise AuthenticationError()

        if not verify_password(password, user.password_hash):
            logger.warning("登录失败: 密码错误 user=%s", username)
            raise AuthenticationError()

        if not user.is_active:
            logger.warning("登录失败: 账号已禁用 user=%s", username)
            raise AuthenticationError("账号已被禁用")

        user.last_login = time.time()
        session_id = uuid.uuid4().hex
        token = encode_token({"sub": username, "type": "access", "roles": user.roles})
        refresh = encode_refresh_token({"sub": username, "type": "refresh"})

        session = Session(
            session_id=session_id,
            username=username,
            token=token,
            refresh_token=refresh,
        )
        self._sessions[session_id] = session
        self._user_tokens.setdefault(username, []).append(refresh)

        logger.info(
            "登录成功: username=%s session_id=%s roles=%s",
            username, session_id, user.roles,
        )
        return session

    # ------------------------------------------------------------------
    # 令牌刷新
    # ------------------------------------------------------------------

    def refresh_token(self, refresh_token: str) -> tuple[str, str]:
        """用 refresh token 换取新 access + refresh token 对。"""
        logger.info("刷新令牌请求")
        logger.debug("  token 前缀: %.20s...", refresh_token[:40])

        # 1. 解码并验证 token
        payload = decode_token(refresh_token)
        if payload is None:
            logger.warning("刷新令牌失败: token 解码结果为 None（可能已过期或签名无效）")
            raise TokenError("无效的 refresh token")

        token_type = payload.get("type")
        token_jti = payload.get("jti", "N/A")
        token_exp = payload.get("exp", 0)
        import time as _time
        time_left = token_exp - _time.time()
        logger.debug("  token type=%s jti=%s 剩余有效期=%.1fs", token_type, token_jti, time_left)

        if token_type != "refresh":
            logger.warning(
                "刷新令牌失败: type=%s != 'refresh'（可能是 access token 误用）", token_type
            )
            raise TokenError("无效的 refresh token")

        # 2. 校验用户状态
        username = payload.get("sub")
        logger.debug("  解析用户: username=%s", username)

        if username not in self._users:
            logger.warning("刷新令牌失败: 用户不存在 '%s'", username)
            raise TokenError("用户不存在")

        user = self._users[username]
        logger.debug(
            "  用户状态: is_active=%s roles=%s last_login=%s",
            user.is_active, user.roles, user.last_login,
        )
        if not user.is_active:
            logger.warning("刷新令牌失败: 账号已禁用 '%s'", username)
            raise AuthorizationError("账号已被禁用")

        # 3. 撤销旧 refresh token
        old_token_count = len(self._user_tokens.get(username, []))
        logger.debug(
            "  活跃 refresh tokens: %d 个（用户 %s）", old_token_count, username
        )

        if username in self._user_tokens:
            user_tokens = self._user_tokens[username]
            if refresh_token in user_tokens:
                user_tokens.remove(refresh_token)
                logger.info(
                    "旧 refresh token 已撤销: user=%s jti=%s tokens剩余=%d",
                    username, token_jti, len(user_tokens),
                )
            else:
                logger.warning(
                    "刷新令牌失败: token 不在活跃列表中（可能被登出或踢出）"
                )
                raise TokenError("token 已被撤销")
        else:
            logger.warning("刷新令牌失败: 用户无 token 记录 '%s'", username)
            raise TokenError("token 已被撤销")

        # 4. 签发新 token
        new_access = encode_token({"sub": username, "type": "access", "roles": user.roles})
        new_refresh = encode_refresh_token({"sub": username, "type": "refresh"})

        # 提取新 token 的 jti 用于日志
        new_payload = decode_token(new_refresh)
        new_jti = new_payload.get("jti", "N/A") if new_payload else "N/A"

        self._user_tokens.setdefault(username, []).append(new_refresh)
        new_token_count = len(self._user_tokens[username])
        logger.info(
            "令牌刷新成功: user=%s jti=%s -> new_jti=%s tokens=%d",
            username, token_jti, new_jti, new_token_count,
        )
        return new_access, new_refresh

    # ------------------------------------------------------------------
    # 登出 / 注销
    # ------------------------------------------------------------------

    def logout(self, session_id: str) -> bool:
        """登出指定会话。"""
        logger.info("登出请求: session_id=%s", session_id)

        session = self._sessions.pop(session_id, None)
        if session is None:
            logger.warning("登出失败: session 不存在 '%s'", session_id)
            return False

        session.is_valid = False
        username = session.username
        logger.info("登出成功: username=%s session_id=%s", username, session_id)

        # 清理该用户的所有 token
        if username in self._user_tokens:
            self._user_tokens[username] = [
                t for t in self._user_tokens[username]
                if decode_token(t) is None or decode_token(t).get("sub") != username
            ]
        return True

    def invalidate_all_sessions(self, username: str) -> int:
        """踢出用户所有会话（密码修改等场景）。"""
        username = username.strip().lower()
        logger.info("踢出所有会话: username=%s", username)

        count = 0
        for sid, session in list(self._sessions.items()):
            if session.username == username:
                session.is_valid = False
                del self._sessions[sid]
                count += 1

        self._user_tokens.pop(username, None)
        logger.info("踢出完成: user=%s 踢出 %d 个会话", username, count)
        return count

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def get_user(self, username: str) -> Optional[User]:
        username_lower = username.strip().lower()
        logger.debug("查询用户: username=%s", username_lower)
        return self._users.get(username_lower)

    def get_session(self, session_id: str) -> Optional[Session]:
        logger.debug("查询会话: session_id=%s", session_id)
        session = self._sessions.get(session_id)
        if session and session.is_expired():
            del self._sessions[session_id]
            logger.debug("会话已过期，已清理: session_id=%s", session_id)
            return None
        return session

    def verify_access_token(self, token: str) -> Optional[dict]:
        """验证 access token 并返回 payload。"""
        payload = decode_token(token)
        if payload is None:
            logger.debug("验证 token 失败: token 无效")
            return None
        username = payload.get("sub")
        user = self._users.get(username) if username else None
        if user is None or not user.is_active:
            logger.debug("验证 token 失败: 用户不存在或已禁用 '%s'", username)
            return None
        # 检查是否存在有效会话（防止已登出但仍持有效 token 的情况）
        has_valid_session = any(
            s.username == username and s.is_valid and not s.is_expired()
            for s in self._sessions.values()
        )
        if not has_valid_session:
            logger.debug("验证 token 失败: 用户无活跃会话 '%s'", username)
            return None
        logger.debug("验证 token 成功: username=%s", username)
        return payload

    def get_active_session_count(self, username: str) -> int:
        username = username.strip().lower()
        count = sum(
            1 for s in self._sessions.values()
            if s.username == username and not s.is_expired()
        )
        logger.debug("活跃会话数: username=%s count=%d", username, count)
        return count

    def get_all_usernames(self) -> list[str]:
        return list(self._users.keys())

    def count_users(self) -> int:
        return len(self._users)


# ----------------------------------------------------------------------
# 内部辅助
# ----------------------------------------------------------------------

def _validate_password(password: str) -> tuple[bool, str]:
    if not password or len(password) < 6:
        return False, "密码长度至少 6 位"
    if len(password) > 128:
        return False, "密码长度不能超过 128 位"
    if not any(c.isalpha() for c in password):
        return False, "密码必须包含字母"
    if not any(c.isdigit() for c in password):
        return False, "密码必须包含数字"
    return True, ""
