"""
Matha 认证模块。

提供用户注册、登录、登出、令牌刷新等完整认证功能。

用法:
    from src.auth.service import SessionManager

    mgr = SessionManager()
    user = mgr.register("张三", "zhangsan@example.com", "Pass1234")
    session = mgr.login("zhangsan", "Pass1234")
    print(session.token)          # JWT access token
    print(session.refresh_token)  # JWT refresh token

    new_access, new_refresh = mgr.refresh_token(session.refresh_token)
    mgr.logout(session.session_id)
"""
from src.auth.models import User, Session
from src.auth.jwt import encode_token, decode_token, encode_refresh_token, decode_refresh_token
from src.auth.password import hash_password, verify_password, validate_password_strength
from src.auth.service import SessionManager
from src.auth.exceptions import (
    AuthError,
    AuthenticationError,
    AuthorizationError,
    TokenError,
    RegistrationError,
)

__all__ = [
    # Models
    "User",
    "Session",
    # JWT
    "encode_token",
    "decode_token",
    "encode_refresh_token",
    "decode_refresh_token",
    "get_token_expiry",
    # Password
    "hash_password",
    "verify_password",
    "validate_password_strength",
    # Service
    "SessionManager",
    # Exceptions
    "AuthError",
    "AuthenticationError",
    "AuthorizationError",
    "TokenError",
    "RegistrationError",
]
