"""认证异常定义。"""
from __future__ import annotations


class AuthError(Exception):
    """认证基础异常。"""

    def __init__(self, message: str, code: str = "AUTH_ERROR"):
        super().__init__(message)
        self.message = message
        self.code = code


class AuthenticationError(AuthError):
    """登录失败 — 用户名/密码错误。"""

    def __init__(self, message: str = "用户名或密码错误"):
        super().__init__(message, "AUTHENTICATION_ERROR")


class AuthorizationError(AuthError):
    """权限不足。"""

    def __init__(self, message: str = "权限不足"):
        super().__init__(message, "AUTHORIZATION_ERROR")


class TokenError(AuthError):
    """令牌相关错误。"""

    def __init__(self, message: str = "令牌无效或已过期"):
        super().__init__(message, "TOKEN_ERROR")


class RegistrationError(AuthError):
    """注册失败。"""

    def __init__(self, message: str = "注册失败", code: str = "REGISTRATION_ERROR"):
        super().__init__(message, code)
