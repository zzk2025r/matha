"""用户与会话数据模型。"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class User:
    """用户数据模型。"""
    username: str
    email: str
    password_hash: str   # PBKDF2 哈希值
    created_at: float = field(default_factory=time.time)
    last_login: Optional[float] = None
    is_active: bool = True
    roles: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "username": self.username,
            "email": self.email,
            "created_at": self.created_at,
            "last_login": self.last_login,
            "is_active": self.is_active,
            "roles": self.roles,
        }


@dataclass
class Session:
    """会话数据模型。"""
    session_id: str
    username: str
    token: str           # JWT access token
    refresh_token: str   # JWT refresh token
    created_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 3600)
    is_valid: bool = True

    def is_expired(self) -> bool:
        return time.time() > self.expires_at or not self.is_valid

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "username": self.username,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
        }
