"""会话管理器 — 内存存储用户与会话。"""
from __future__ import annotations

import uuid
import time
from typing import Optional

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
        self._users: dict[str, User] = {}       # username -> User
        self._sessions: dict[str, Session] = {}  # session_id -> Session
        self._user_tokens: dict[str, list[str]] = {}  # username -> [refresh_token, ...]

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
        if not username or not username.strip():
            raise RegistrationError("用户名不能为空")
        username = username.strip().lower()
        if not email or "@" not in email:
            raise RegistrationError("邮箱格式无效")
        if username in self._users:
            raise RegistrationError(f"用户名 '{username}' 已存在")

        pw_valid, msg = _validate_password(password)
        if not pw_valid:
            raise RegistrationError(msg)

        hashed = hash_password(password)
        user = User(
            username=username,
            email=email.strip().lower(),
            password_hash=hashed,
            roles=roles or [],
        )
        self._users[username] = user
        return user

    # ------------------------------------------------------------------
    # 用户登录
    # ------------------------------------------------------------------

    def login(self, username: str, password: str) -> Session:
        """验证凭据并创建新会话。失败抛出 AuthenticationError。"""
        username = username.strip().lower()
        user = self._users.get(username)
        if user is None or not verify_password(password, user.password_hash):
            raise AuthenticationError()

        if not user.is_active:
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
        return session

    # ------------------------------------------------------------------
    # 令牌刷新
    # ------------------------------------------------------------------

    def refresh_token(self, refresh_token: str) -> tuple[str, str]:
        """用 refresh token 换取新 access + refresh token 对。"""
        payload = decode_token(refresh_token)
        if payload is None or payload.get("type") != "refresh":
            raise TokenError("无效的 refresh token")

        username = payload.get("sub")
        if username not in self._users:
            raise TokenError("用户不存在")

        user = self._users[username]
        if not user.is_active:
            raise AuthorizationError("账号已被禁用")

        # 撤销旧 refresh token
        if username in self._user_tokens:
            user_tokens = self._user_tokens[username]
            if refresh_token in user_tokens:
                user_tokens.remove(refresh_token)
            else:
                raise TokenError("token 已被撤销")

        new_access = encode_token({"sub": username, "type": "access", "roles": user.roles})
        new_refresh = encode_refresh_token({"sub": username, "type": "refresh"})
        self._user_tokens.setdefault(username, []).append(new_refresh)

        return new_access, new_refresh

    # ------------------------------------------------------------------
    # 登出 / 注销
    # ------------------------------------------------------------------

    def logout(self, session_id: str) -> bool:
        """登出指定会话。"""
        session = self._sessions.pop(session_id, None)
        if session is None:
            return False
        session.is_valid = False
        username = session.username
        if username in self._user_tokens:
            self._user_tokens[username] = [
                t for t in self._user_tokens[username]
                if decode_token(t) is None or decode_token(t).get("sub") != username
            ]
        return True

    def invalidate_all_sessions(self, username: str) -> int:
        """踢出用户所有会话（密码修改等场景）。"""
        username = username.strip().lower()
        count = 0
        for sid, session in list(self._sessions.items()):
            if session.username == username:
                session.is_valid = False
                del self._sessions[sid]
                count += 1
        self._user_tokens.pop(username, None)
        return count

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def get_user(self, username: str) -> Optional[User]:
        return self._users.get(username.strip().lower())

    def get_session(self, session_id: str) -> Optional[Session]:
        session = self._sessions.get(session_id)
        if session and session.is_expired():
            del self._sessions[session_id]
            return None
        return session

    def verify_access_token(self, token: str) -> Optional[dict]:
        """验证 access token 并返回 payload。"""
        payload = decode_token(token)
        if payload is None:
            return None
        username = payload.get("sub")
        user = self._users.get(username) if username else None
        if user is None or not user.is_active:
            return None
        return payload

    def get_active_session_count(self, username: str) -> int:
        username = username.strip().lower()
        return sum(
            1 for s in self._sessions.values()
            if s.username == username and not s.is_expired()
        )

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
