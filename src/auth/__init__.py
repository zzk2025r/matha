"""
Matha 认证模块。

提供用户注册、登录、登出、令牌刷新等完整认证功能。

用法:
    from src.auth.service import SessionManager
    from src.auth.rbac import RBACMiddleware, Permission

    mgr = SessionManager()
    user = mgr.register("张三", "zhangsan@example.com", "Pass1234", roles=["viewer"])
    session = mgr.login("zhangsan", "Pass1234")

    rbac = RBACMiddleware()
    rbac.authorize(user.roles, "doc:read")  # OK
    rbac.authorize(user.roles, "doc:write") # raises AuthorizationError
"""
from src.auth.api import PermissionChangeAPI
from src.auth.exceptions import (
    AuthenticationError,
    AuthError,
    AuthorizationError,
    RegistrationError,
    TokenError,
)
from src.auth.jwt import decode_refresh_token, decode_token, encode_refresh_token, encode_token
from src.auth.models import Session, User
from src.auth.password import hash_password, validate_password_strength, verify_password
from src.auth.rbac import Permission, RBACMiddleware, get_rbac, reset_rbac
from src.auth.service import SessionManager

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
    # RBAC
    "RBACMiddleware",
    "Permission",
    "get_rbac",
    "reset_rbac",
    # API
    "PermissionChangeAPI",
    # Exceptions
    "AuthError",
    "AuthenticationError",
    "AuthorizationError",
    "TokenError",
    "RegistrationError",
]
