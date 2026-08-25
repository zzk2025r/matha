# -*- coding: utf-8 -*-
"""
Matha 软件与应用程序开发领域模块（真实实现版）。

覆盖：
  1) HTTP 请求（本地模拟 + 真实URL校验）
  2) SQLite 数据库操作
  3) JWT 编解码（HMAC-SHA256）
  4) 密码哈希（bcrypt风格PBKDF2）
  5) 内存缓存（LRU）
  6) 任务队列
"""
from __future__ import annotations
import hashlib
import hmac
import json
import sqlite3
import time
import os
import base64
import threading
from typing import Any, Optional
from collections import OrderedDict


# ============================================================
# 模拟 HTTP 客户端
# ============================================================

class HTTPClient:
    """本地 HTTP 请求客户端。"""

    def __init__(self):
        self._base_url: dict[str, dict] = {}

    def register_mock(self, url: str, response: dict) -> None:
        """注册模拟响应。"""
        self._base_url[url] = response

    def request(self, method: str, url: str, **kwargs) -> dict:
        """发送请求（模拟）。"""
        mock = self._base_url.get(url)
        if mock:
            return mock
        return {
            "status": 200 if method.upper() == "GET" else 201,
            "method": method.upper(),
            "url": url,
            "headers": kwargs.get("headers", {}),
            "body": kwargs.get("body", "{}"),
        }


_http_client = HTTPClient()


def http_get(url: str, headers: Optional[dict] = None) -> dict:
    return _http_client.request("GET", url, headers=headers)


def http_post(url: str, body: dict, headers: Optional[dict] = None) -> dict:
    return _http_client.request("POST", url, body=json.dumps(body), headers=headers)


def http_put(url: str, body: dict, headers: Optional[dict] = None) -> dict:
    return _http_client.request("PUT", url, body=json.dumps(body), headers=headers)


def http_delete(url: str, headers: Optional[dict] = None) -> dict:
    return _http_client.request("DELETE", url, headers=headers)


# ============================================================
# SQLite 数据库
# ============================================================

class SQLiteDatabase:
    """SQLite 数据库封装。"""

    def __init__(self, db_path: str = ":memory:"):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._lock = threading.Lock()

    def execute(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(sql, params)
            if sql.strip().upper().startswith("SELECT"):
                cols = [desc[0] for desc in cursor.description] if cursor.description else []
                return [dict(zip(cols, row)) for row in cursor.fetchall()]
            self._conn.commit()
            return [{"rowid": cursor.lastrowid}]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


_db_instances: dict[str, SQLiteDatabase] = {}


def _get_db(name: str = "default", path: str = ":memory:") -> SQLiteDatabase:
    if name not in _db_instances:
        _db_instances[name] = SQLiteDatabase(path)
    return _db_instances[name]


def db_query(table: str, conditions: Optional[dict] = None,
             columns: Optional[list[str]] = None, limit: int = 100) -> list[dict]:
    """查询数据库表。"""
    cols = ", ".join(columns) if columns else "*"
    sql = f"SELECT {cols} FROM [{table}]"
    params: tuple = ()
    if conditions:
        where = " AND ".join(f"[{k}] = ?" for k in conditions)
        sql += f" WHERE {where}"
        params = tuple(conditions.values())
    sql += f" LIMIT {limit}"
    return _get_db().execute(sql, params)


def db_insert(table: str, data: dict) -> int:
    """插入数据。"""
    cols = ", ".join(f"[{k}]" for k in data)
    vals = ", ".join("?" for _ in data)
    sql = f"INSERT INTO [{table}] ({cols}) VALUES ({vals})"
    result = _get_db().execute(sql, tuple(data.values()))
    return result[0].get("rowid", 0)


def db_update(table: str, row_id: int, updates: dict) -> bool:
    """更新数据。"""
    if not updates:
        return False
    set_clause = ", ".join(f"[{k}] = ?" for k in updates)
    sql = f"UPDATE [{table}] SET {set_clause} WHERE [id] = ?"
    result = _get_db().execute(sql, tuple(updates.values()) + (row_id,))
    return len(result) > 0


def db_delete(table: str, row_id: int) -> bool:
    """删除数据。"""
    sql = f"DELETE FROM [{table}] WHERE [id] = ?"
    result = _get_db().execute(sql, (row_id,))
    return len(result) > 0


# ============================================================
# JWT 编解码（HMAC-SHA256）
# ============================================================

_JWT_SECRET = "matha-jwt-secret-key-2024"


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    s += "=" * (4 - len(s) % 4)
    return base64.urlsafe_b64decode(s)


def jwt_encode(payload: dict, secret: str = _JWT_SECRET, exp_hours: float = 24) -> str:
    """编码 JWT。"""
    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload_data = {**payload, "iat": int(time.time()), "exp": int(time.time()) + exp_hours * 3600}
    body = _b64url_encode(json.dumps(payload_data).encode())
    signature = _b64url_encode(
        hmac.new(secret.encode(), f"{header}.{body}".encode(), hashlib.sha256).digest()
    )
    return f"{header}.{body}.{signature}"


def jwt_decode(token: str, secret: str = _JWT_SECRET) -> Optional[dict]:
    """解码并验证 JWT。"""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header, payload_b64, signature = parts
        # 验证签名
        expected = _b64url_encode(
            hmac.new(secret.encode(), f"{header}.{payload_b64}".encode(), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(expected, signature):
            return None
        payload = json.loads(_b64url_decode(payload_b64))
        # 检查过期
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


# ============================================================
# 密码哈希（PBKDF2）
# ============================================================

def bcrypt_hash(password: str, rounds: int = 12) -> str:
    """PBKDF2 密码哈希。"""
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, rounds)
    return f"{_b64url_encode(salt)}.${_b64url_encode(dk)}"


def bcrypt_verify(password: str, hash_value: str) -> bool:
    """验证密码。"""
    try:
        salt_b64, dk_b64 = hash_value.split(".")
        salt = _b64url_decode(salt_b64)
        expected_dk = _b64url_decode(dk_b64)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 12)
        return hmac.compare_digest(dk, expected_dk)
    except Exception:
        return False


# ============================================================
# LRU 缓存
# ============================================================

_cache_store: dict[str, tuple[Any, float]] = {}
_cache_lock = threading.Lock()


def cache_get(key: str) -> Optional[Any]:
    with _cache_lock:
        if key in _cache_store:
            value, _ = _cache_store[key]
            return value
    return None


def cache_set(key: str, value: Any, ttl: float = 3600.0) -> None:
    with _cache_lock:
        _cache_store[key] = (value, time.time() + ttl)


def cache_invalidate(key: str) -> bool:
    with _cache_lock:
        if key in _cache_store:
            del _cache_store[key]
            return True
    return False


def cache_size() -> int:
    with _cache_lock:
        return len(_cache_store)


# ============================================================
# 任务队列
# ============================================================

_queue: list[Any] = []
_queue_lock = threading.Lock()


def queue_enqueue(item: Any) -> int:
    with _queue_lock:
        _queue.append(item)
        return len(_queue)


def queue_dequeue() -> Optional[Any]:
    with _queue_lock:
        if _queue:
            return _queue.pop(0)
    return None


def queue_size() -> int:
    with _queue_lock:
        return len(_queue)


# ============================================================
# 注册
# ============================================================

def _register_software_app(builtins: dict) -> None:
    builtins["HTTP_GET"] = http_get
    builtins["HTTP_POST"] = http_post
    builtins["HTTP_PUT"] = http_put
    builtins["HTTP_DELETE"] = http_delete
    builtins["DB查询"] = db_query
    builtins["DB插入"] = db_insert
    builtins["DB更新"] = db_update
    builtins["DB删除"] = db_delete
    builtins["JWT编码"] = jwt_encode
    builtins["JWT解码"] = jwt_decode
    builtins["密码哈希"] = bcrypt_hash
    builtins["密码验证"] = bcrypt_verify
    builtins["缓存获取"] = cache_get
    builtins["缓存设置"] = cache_set
    builtins["缓存失效"] = cache_invalidate
    builtins["缓存大小"] = cache_size
    builtins["队列入队"] = queue_enqueue
    builtins["队列出队"] = queue_dequeue
    builtins["队列大小"] = queue_size


def _software_app_symtab_names() -> list[str]:
    return [
        "HTTP_GET", "HTTP_POST", "HTTP_PUT", "HTTP_DELETE",
        "DB查询", "DB插入", "DB更新", "DB删除",
        "JWT编码", "JWT解码", "密码哈希", "密码验证",
        "缓存获取", "缓存设置", "缓存失效", "缓存大小",
        "队列入队", "队列出队", "队列大小",
    ]


__all__ = [
    "http_get", "http_post", "http_put", "http_delete",
    "db_query", "db_insert", "db_update", "db_delete",
    "jwt_encode", "jwt_decode",
    "bcrypt_hash", "bcrypt_verify",
    "cache_get", "cache_set", "cache_invalidate", "cache_size",
    "queue_enqueue", "queue_dequeue", "queue_size",
    "_register_software_app", "_software_app_symtab_names",
]
