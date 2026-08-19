"""密码哈希工具 — 基于 PBKDF2-HMAC-SHA256。"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    """解码 base64url 字符串（兼容 Python 3.14 严格模式）。"""
    std = s.replace("-", "+").replace("_", "/")
    padding = (4 - len(s) % 4) % 4
    if padding:
        std += "=" * padding
    return base64.b64decode(std)


def hash_password(password: str, rounds: int = 12) -> str:
    """对密码进行 PBKDF2 哈希。格式: base64url(salt) . base64url(dk)。"""
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, rounds)
    return f"{_b64url_encode(salt)}.{_b64url_encode(dk)}"


def verify_password(password: str, password_hash: str) -> bool:
    """验证密码是否匹配哈希值。"""
    try:
        salt_b64, dk_b64 = password_hash.split(".")
        salt = _b64url_decode(salt_b64)
        expected_dk = _b64url_decode(dk_b64)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 12)
        return hmac.compare_digest(dk, expected_dk)
    except Exception:
        return False


def validate_password_strength(password: str) -> tuple[bool, str]:
    """校验密码强度，返回 (是否通过, 错误信息)。"""
    if len(password) < 6:
        return False, "密码长度至少 6 位"
    if len(password) > 128:
        return False, "密码长度不能超过 128 位"
    if not any(c.isalpha() for c in password):
        return False, "密码必须包含字母"
    if not any(c.isdigit() for c in password):
        return False, "密码必须包含数字"
    return True, ""
