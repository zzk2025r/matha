"""JWT 令牌管理。"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Optional

from matha_auth.exceptions import TokenError

_JWT_SECRET = "matha-auth-jwt-secret-key-2024-v2"


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    """解码 base64url 字符串（兼容 Python 3.14 严格模式）。"""
    std = s.replace("-", "+").replace("_", "/")
    padding = (4 - len(s) % 4) % 4
    if padding:
        std += "=" * padding
    return base64.b64decode(std)


def encode_token(payload: dict, secret: str = _JWT_SECRET, exp_hours: float = 1.0) -> str:
    """签发 JWT access token。"""
    import uuid as _uuid
    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload_data = {
        **payload,
        "jti": _uuid.uuid4().hex,
        "iat": int(time.time()),
        "exp": int(time.time()) + int(exp_hours * 3600),
    }
    body = _b64url_encode(json.dumps(payload_data).encode())
    signature = _b64url_encode(
        hmac.new(secret.encode(), f"{header}.{body}".encode(), hashlib.sha256).digest()
    )
    return f"{header}.{body}.{signature}"


def decode_token(token: str, secret: str = _JWT_SECRET) -> Optional[dict]:
    """验证并解码 JWT。过期或签名不符返回 None。"""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header, payload_b64, signature = parts
        expected = _b64url_encode(
            hmac.new(secret.encode(), f"{header}.{payload_b64}".encode(), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(expected, signature):
            return None
        payload = json.loads(_b64url_decode(payload_b64))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


def encode_refresh_token(payload: dict, secret: str = _JWT_SECRET, exp_days: float = 7.0) -> str:
    """签发 JWT refresh token（有效期更长）。"""
    return encode_token(payload, secret, exp_hours=exp_days * 24)


def decode_refresh_token(token: str, secret: str = _JWT_SECRET) -> Optional[dict]:
    """验证 refresh token。"""
    return decode_token(token, secret)


def get_token_expiry(token: str, secret: str = _JWT_SECRET) -> Optional[float]:
    """获取 token 剩余有效时间（秒），无效时返回 None。"""
    payload = decode_token(token, secret)
    if payload is None:
        return None
    return payload.get("exp", 0) - time.time()
