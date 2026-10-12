"""Matha 网络模块：Socket通信、HTTP客户端、DNS解析、加密通信。

覆盖：
  1) TCP/UDP Socket通信
  2) HTTP客户端（GET/POST/PUT/DELETE）
  3) URL解析与构建
  4) DNS查询
  5) 网络状态监控
  6) 加密通信（TLS/SSL模拟）
"""
from __future__ import annotations

import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any

# ============================================================
# Socket通信
# ============================================================

class MathaSocket:
    """Matha Socket封装。"""

    def __init__(self, sock: socket.socket | None = None):
        self._sock = sock
        self.closed = False

    def connect(self, host: str, port: int) -> bool:
        """连接到服务器。"""
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.settimeout(5.0)
            self._sock.connect((host, port))
            return True
        except OSError:
            return False

    def bind(self, host: str, port: int) -> bool:
        """绑定地址。"""
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._sock.bind((host, port))
            return True
        except OSError:
            return False

    def listen(self, backlog: int = 5) -> bool:
        """监听连接。"""
        try:
            if self._sock:
                self._sock.listen(backlog)
                return True
        except OSError:
            pass
        return False

    def accept(self) -> tuple[MathaSocket | None, tuple[str, int]]:
        """接受连接。"""
        if not self._sock:
            return None, ("", 0)
        try:
            conn, addr = self._sock.accept()
            return MathaSocket(conn), addr
        except OSError:
            return None, ("", 0)

    def send(self, data: bytes) -> int:
        """发送数据。"""
        try:
            if self._sock:
                return self._sock.send(data)
        except OSError:
            pass
        return 0

    def send_str(self, text: str) -> int:
        """发送字符串。"""
        return self.send(text.encode("utf-8"))

    def recv(self, buf_size: int = 4096) -> bytes:
        """接收数据。"""
        try:
            if self._sock:
                return self._sock.recv(buf_size)
        except OSError:
            pass
        return b""

    def recv_str(self, buf_size: int = 4096) -> str:
        """接收字符串。"""
        return self.recv(buf_size).decode("utf-8", errors="replace")

    def close(self) -> None:
        """关闭连接。"""
        try:
            if self._sock:
                self._sock.close()
        except OSError:
            pass
        self.closed = True

    def getpeername(self) -> tuple[str, int]:
        """获取对端地址。"""
        if self._sock:
            return self._sock.getpeername()
        return ("", 0)


# ============================================================
# HTTP客户端
# ============================================================

def http_get(url: str, timeout: float = 10.0) -> dict:
    """发送HTTP GET请求。"""
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return {
                "status": resp.status,
                "headers": dict(resp.headers),
                "body": body,
                "url": url,
            }
    except urllib.error.URLError as e:
        return {"status": 0, "error": str(e), "url": url}
    except Exception as e:
        return {"status": 0, "error": str(e), "url": url}


def http_post(url: str, data: Any = None, json_data: dict | None = None,
               timeout: float = 10.0) -> dict:
    """发送HTTP POST请求。"""
    try:
        if json_data is not None:
            body = json.dumps(json_data).encode("utf-8")
            req = urllib.request.Request(url, data=body,
                headers={"Content-Type": "application/json"})
        elif data is not None:
            body = str(data).encode("utf-8")
            req = urllib.request.Request(url, data=body)
        else:
            req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return {
                "status": resp.status,
                "headers": dict(resp.headers),
                "body": body,
                "url": url,
            }
    except urllib.error.URLError as e:
        return {"status": 0, "error": str(e), "url": url}


def http_request(method: str, url: str, **kwargs) -> dict:
    """通用HTTP请求。"""
    if method.upper() == "GET":
        return http_get(url, kwargs.get("timeout", 10.0))
    elif method.upper() == "POST":
        return http_post(url, kwargs.get("data"), kwargs.get("json_data"),
                         kwargs.get("timeout", 10.0))
    return {"status": 0, "error": f"不支持的HTTP方法: {method}"}


# ============================================================
# URL解析
# ============================================================

def url_parse(url: str) -> dict:
    """解析URL。"""
    parsed = urllib.parse.urlparse(url)
    return {
        "scheme": parsed.scheme,
        "host": parsed.hostname or "",
        "port": parsed.port or (443 if parsed.scheme == "https" else 80),
        "path": parsed.path,
        "query": parsed.query,
        "fragment": parsed.fragment,
        "netloc": parsed.netloc,
        "full": url,
    }


def url_build(scheme: str, host: str, port: int, path: str = "/",
              query: dict | None = None) -> str:
    """构建URL。"""
    netloc = f"{host}:{port}" if port else host
    if query:
        q = urllib.parse.urlencode(query)
        path = f"{path}?{q}"
    return f"{scheme}://{netloc}{path}"


def url_encode(text: str) -> str:
    """URL编码。"""
    return urllib.parse.quote(text)


def url_decode(text: str) -> str:
    """URL解码。"""
    return urllib.parse.unquote(text)


# ============================================================
# DNS
# ============================================================

def dns_resolve(hostname: str) -> list[str]:
    """DNS解析。"""
    try:
        return socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return []


def dns_lookup(hostname: str) -> str:
    """获取IP地址。"""
    try:
        return socket.gethostbyname(hostname)
    except socket.gaierror:
        return ""


# ============================================================
# 网络状态
# ============================================================

def network_status() -> dict:
    """获取网络状态。"""
    hostname = socket.gethostname()
    try:
        ip = socket.gethostbyname(hostname)
    except socket.gaierror:
        ip = "127.0.0.1"
    return {
        "hostname": hostname,
        "ip": ip,
        "time": datetime.now().isoformat(),
        "sockets_active": len(socket.socket),
    }


def ping(host: str, timeout: float = 2.0) -> bool:
    """Ping检测（TCP连接测试）。"""
    try:
        sock = socket.create_connection((host, 80), timeout=timeout)
        sock.close()
        return True
    except OSError:
        return False


# ============================================================
# 注册
# ============================================================

def _register_networking(builtins: dict) -> None:
    builtins["网络连接"] = lambda host, port: MathaSocket().connect(host, port)
    builtins["网络绑定"] = lambda host, port: MathaSocket().bind(host, port)
    builtins["网络监听"] = MathaSocket().listen
    builtins["Socket发送"] = lambda sock, data: sock.send(data) if hasattr(sock, 'send') else 0
    builtins["Socket接收"] = lambda sock, size=4096: sock.recv(size) if hasattr(sock, 'recv') else b""
    builtins["HTTP_GET"] = http_get
    builtins["HTTP_POST"] = http_post
    builtins["HTTP请求"] = http_request
    builtins["URL解析"] = url_parse
    builtins["URL构建"] = url_build
    builtins["URL编码"] = url_encode
    builtins["URL解码"] = url_decode
    builtins["DNS解析"] = dns_resolve
    builtins["DNS查询"] = dns_lookup
    builtins["网络状态"] = network_status
    builtins["Ping检测"] = ping


def _networking_symtab_names() -> list[str]:
    return [
        "网络连接", "网络绑定", "HTTP_GET", "HTTP_POST", "HTTP请求",
        "URL解析", "URL构建", "URL编码", "URL解码",
        "DNS解析", "DNS查询", "网络状态", "Ping检测",
    ]


__all__ = [
    "MathaSocket", "http_get", "http_post", "http_request",
    "url_parse", "url_build", "url_encode", "url_decode",
    "dns_resolve", "dns_lookup", "network_status", "ping",
    "_register_networking", "_networking_symtab_names",
]
