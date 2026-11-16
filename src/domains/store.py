# -*- coding: utf-8 -*-
"""Matha 应用商店自生凭据域：HMAC 令牌自签发/校验/吊销。

外部凭据自由的凭据面（阶段 25 拍板：商店自签发 HMAC 令牌）：
  - 密钥首启自生成（secrets.token_hex(32)），落 ``<root>/.matha/store/secret.key``；
  - 令牌 = HS256 形（header.payload.signature，base64url，hmac-sha256），
    载荷 sub/iat/exp/jti（复用 src/auth/jwt.py 的签名模式）；
  - 吊销表持久化 ``<root>/.matha/store/revoked.json``（jti → exp，过期条目回收）；
  - OS 原语（hmac/hashlib/secrets/base64）只落领域层，内核不 import（纯度棘轮）。

Matha 面：
  商店_签发令牌(主体)(过期秒) → 令牌串
  商店_校验令牌(令牌) → 载荷 dict（篡改/过期/吊销/形态错 诚实拒绝）
  商店_吊销令牌(令牌) → True
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from pathlib import Path

_STORE_DIRNAME = ".matha"
_SECRET_FILENAME = "secret.key"
_REVOKED_FILENAME = "revoked.json"
_REVOKED_PROTOCOL_VERSION = 1


def store_dir(root: str | Path | None = None) -> Path:
    base = Path(root) if root else Path.cwd()
    return base / _STORE_DIRNAME / "store"


def _ensure_secret(root: str | Path | None = None) -> bytes:
    d = store_dir(root)
    p = d / _SECRET_FILENAME
    if p.exists():
        text = p.read_text(encoding="utf-8").strip()
        if len(text) != 64:
            raise ValueError("商店_密钥: 密钥文件损坏（须为 64 位十六进制），拒绝签发")
        try:
            return bytes.fromhex(text)
        except ValueError as exc:
            raise ValueError("商店_密钥: 密钥文件损坏（非十六进制），拒绝签发") from exc
    d.mkdir(parents=True, exist_ok=True)
    secret = secrets.token_bytes(32)
    p.write_text(secret.hex(), encoding="utf-8")
    return secret


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def _sign(secret: bytes, signing_input: str) -> str:
    digest = hmac.new(secret, signing_input.encode("ascii"), hashlib.sha256).digest()
    return _b64url(digest)


def issue_token(subject: str, ttl_seconds: float = 3600,
                root: str | Path | None = None) -> str:
    if not isinstance(subject, str) or not subject.strip():
        raise ValueError("商店_签发令牌: 主体须为非空字符串")
    if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, (int, float)) \
            or ttl_seconds <= 0:
        raise ValueError("商店_签发令牌: 过期秒须为正数")
    secret = _ensure_secret(root)
    header = _b64url(json.dumps(
        {"alg": "HS256", "typ": "matha-store"},
        ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    now = int(time.time())
    payload = _b64url(json.dumps(
        {"sub": subject, "iat": now, "exp": now + int(ttl_seconds),
         "jti": secrets.token_hex(8)},
        ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    return f"{header}.{payload}.{_sign(secret, f'{header}.{payload}')}"


def _load_revoked(root: str | Path | None = None) -> dict:
    p = store_dir(root) / _REVOKED_FILENAME
    if not p.exists():
        return {}
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("revoked"), dict):
        raise ValueError("商店_校验令牌: 吊销表损坏，拒绝校验")
    return data["revoked"]


def _save_revoked(revoked: dict, root: str | Path | None = None) -> None:
    d = store_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    (d / _REVOKED_FILENAME).write_text(json.dumps(
        {"protocol_version": _REVOKED_PROTOCOL_VERSION, "revoked": revoked},
        ensure_ascii=False, indent=1), encoding="utf-8")


def verify_token(token: str, root: str | Path | None = None) -> dict:
    if not isinstance(token, str):
        raise ValueError("商店_校验令牌: 令牌须为字符串")
    parts = token.split(".")
    if len(parts) != 3 or not all(parts):
        raise ValueError("商店_校验令牌: 令牌须为 header.payload.signature 三段式")
    header_b64, payload_b64, sig_b64 = parts
    secret = _ensure_secret(root)
    expected = _sign(secret, f"{header_b64}.{payload_b64}")
    if not hmac.compare_digest(expected, sig_b64):
        raise ValueError("商店_校验令牌: 签名不符（令牌被篡改或密钥不同）")
    try:
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError(f"商店_校验令牌: 载荷不可解析: {exc}") from exc
    if not isinstance(payload, dict) or "exp" not in payload or "jti" not in payload:
        raise ValueError("商店_校验令牌: 载荷缺 exp/jti 字段")
    if time.time() >= payload["exp"]:
        raise ValueError("商店_校验令牌: 令牌已过期")
    revoked = _load_revoked(root)
    if payload["jti"] in revoked:
        raise ValueError("商店_校验令牌: 令牌已吊销")
    return payload


def revoke_token(token: str, root: str | Path | None = None) -> bool:
    payload = verify_token(token, root)
    revoked = _load_revoked(root)
    now = int(time.time())
    revoked = {jti: exp for jti, exp in revoked.items() if exp > now}
    revoked[payload["jti"]] = payload["exp"]
    _save_revoked(revoked, root)
    return True


def _register_store(builtins: dict) -> None:
    builtins["商店_签发令牌"] = lambda 主体: lambda 过期秒=3600: issue_token(主体, 过期秒)
    builtins["商店_校验令牌"] = verify_token
    builtins["商店_吊销令牌"] = revoke_token


def _store_symtab_names() -> list[str]:
    return ["商店_签发令牌", "商店_校验令牌", "商店_吊销令牌"]


__all__ = [
    "store_dir", "issue_token", "verify_token", "revoke_token",
    "_register_store", "_store_symtab_names",
]
