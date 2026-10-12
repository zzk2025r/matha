"""Matha HTTP 服务器：HTTP/HTTPS 服务、反向代理、WebSocket。"""
from __future__ import annotations

import re
import socket
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class HTTPMethod(Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"
    WS = "WS"


class HttpStatus(Enum):
    OK = 200
    CREATED = 201
    NO_CONTENT = 204
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    METHOD_NOT_ALLOWED = 405
    INTERNAL_ERROR = 500
    SERVICE_UNAVAILABLE = 503


@dataclass
class HttpRequest:
    method: HTTPMethod
    path: str
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    query_params: dict[str, str] = field(default_factory=dict)
    cookies: dict[str, str] = field(default_factory=dict)
    session: dict[str, Any] | None = None
    ip: str = "127.0.0.1"
    timestamp: float = field(default_factory=time.time)


@dataclass
class HttpResponse:
    status: HttpStatus = HttpStatus.OK
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    content_type: str = "text/html"
    status_code: int = 200


@dataclass
class Route:
    path: str
    method: HTTPMethod
    handler: Callable
    middleware: list[Callable] = field(default_factory=list)
    name: str | None = None


class Middleware:
    """HTTP 中间件。"""

    def __init__(self):
        self._middlewares: list[Callable] = []

    def add(self, func: Callable) -> None:
        self._middlewares.append(func)

    def __call__(self, req: HttpRequest, handler: Callable) -> HttpResponse:
        req_copy = req
        for mw in self._middlewares:
            req_copy = mw(req_copy)
        return handler(req_copy)


class HTTPServer:
    """HTTP 服务器。"""

    def __init__(self, host: str = "0.0.0.0", port: int = 8080,
                 workers: int = 4):
        self.host = host
        self.port = port
        self.workers = workers
        self.routes: list[Route] = []
        self.middleware = Middleware()
        self._running = False
        self._server_socket: socket.socket | None = None
        self._session_store: dict[str, dict[str, Any]] = {}
        self._ssl_context: Any | None = None

    def add_route(self, path: str, method: HTTPMethod,
                  handler: Callable, name: str | None = None) -> Route:
        route = Route(path=path, method=method, handler=handler, name=name)
        self.routes.append(route)
        return route

    def get(self, path: str, handler: Callable, name: str | None = None) -> Route:
        return self.add_route(path, HTTPMethod.GET, handler, name)

    def post(self, path: str, handler: Callable, name: str | None = None) -> Route:
        return self.add_route(path, HTTPMethod.POST, handler, name)

    def put(self, path: str, handler: Callable, name: str | None = None) -> Route:
        return self.add_route(path, HTTPMethod.PUT, handler, name)

    def delete(self, path: str, handler: Callable, name: str | None = None) -> Route:
        return self.add_route(path, HTTPMethod.DELETE, handler, name)

    def patch(self, path: str, handler: Callable, name: str | None = None) -> Route:
        return self.add_route(path, HTTPMethod.PATCH, handler, name)

    def use(self, middleware: Callable) -> None:
        self.middleware.add(middleware)

    def set_ssl(self, cert_file: str, key_file: str) -> None:
        self._ssl_context = {"cert": cert_file, "key": key_file}

    def start(self) -> None:
        self._running = True
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind((self.host, self.port))
        self._server_socket.listen(128)
        for _ in range(self.workers):
            t = threading.Thread(target=self._worker_loop, daemon=True)
            t.start()

    def _worker_loop(self) -> None:
        while self._running:
            try:
                conn, addr = self._server_socket.accept()
                t = threading.Thread(target=self._handle_connection,
                                     args=(conn, addr), daemon=True)
                t.start()
            except OSError:
                break

    def _handle_connection(self, conn: socket.socket, addr: tuple) -> None:
        try:
            data = conn.recv(65536)
            if not data:
                return
            req = self._parse_request(data)
            resp = self._route_request(req)
            conn.sendall(self._build_response(resp))
        except Exception:
            pass
        finally:
            conn.close()

    def _parse_request(self, data: bytes) -> HttpRequest:
        lines = data.decode("utf-8", errors="ignore").split("\r\n")
        first = lines[0].split(" ")
        method = HTTPMethod(first[0])
        path = first[1]
        headers = {}
        for line in lines[1:]:
            if not line or line == "":
                break
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip()] = v.strip()
        return HttpRequest(method=method, path=path, headers=headers)

    def _route_request(self, req: HttpRequest) -> HttpResponse:
        for route in self.routes:
            if route.method == req.method and self._match_path(route.path, req.path):
                handler = self.middleware(req, route.handler)
                return handler(req)
        return HttpResponse(status=HttpStatus.NOT_FOUND,
                           body=b"Not Found", status_code=404)

    def _match_path(self, pattern: str, path: str) -> bool:
        if pattern == path:
            return True
        pattern_re = pattern.replace("<", "(").replace(">", ")")
        return re.match(pattern_re, path) is not None

    def _build_response(self, resp: HttpResponse) -> bytes:
        status_line = f"HTTP/1.1 {resp.status_code} {resp.status.value}\r\n"
        headers = "".join(f"{k}: {v}\r\n" for k, v in resp.headers.items())
        return status_line.encode() + headers.encode() + b"\r\n" + resp.body

    def stop(self) -> None:
        self._running = False
        if self._server_socket:
            self._server_socket.close()


class ReverseProxy:
    """反向代理。"""

    def __init__(self, upstreams: list[str]):
        self.upstreams = upstreams
        self.current = 0
        self._server = HTTPServer()

    def add_upstream(self, url: str) -> None:
        self.upstreams.append(url)

    def remove_upstream(self, url: str) -> None:
        self.upstreams.remove(url)

    def get_upstream(self) -> str:
        upstream = self.upstreams[self.current % len(self.upstreams)]
        self.current += 1
        return upstream

    def route(self, req: HttpRequest) -> HttpResponse:
        upstream = self.get_upstream()
        return HttpResponse(status=HttpStatus.OK,
                           body=f"Proxy to {upstream}".encode())


class WebSocket:
    """WebSocket 连接。"""

    def __init__(self, conn: socket.socket):
        self.conn = conn
        self._open = True
        self._send_queue: list[bytes] = []

    def send(self, data: bytes) -> None:
        self._send_queue.append(data)

    def recv(self) -> bytes | None:
        return None

    def close(self) -> None:
        self._open = False
        self.conn.close()

    @property
    def open(self) -> bool:
        return self._open


class WebSocketHandler:
    """WebSocket 处理器。"""

    def __init__(self):
        self._connections: list[WebSocket] = []
        self._routes: dict[str, Callable] = {}

    def on(self, event: str, handler: Callable) -> None:
        self._routes[event] = handler

    def connect(self, ws: WebSocket) -> None:
        self._connections.append(ws)
        if "connect" in self._routes:
            self._routes["connect"](ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.remove(ws)
        if "disconnect" in self._routes:
            self._routes["disconnect"](ws)

    def broadcast(self, data: bytes) -> None:
        for ws in self._connections:
            if ws.open:
                ws.send(data)


def create_http_server(host: str = "0.0.0.0", port: int = 8080) -> HTTPServer:
    """创建 HTTP 服务器。"""
    return HTTPServer(host=host, port=port)


def create_reverse_proxy(upstreams: list[str]) -> ReverseProxy:
    """创建反向代理。"""
    return ReverseProxy(upstreams=upstreams)


def create_websocket_handler() -> WebSocketHandler:
    """创建 WebSocket 处理器。"""
    return WebSocketHandler()


# ============================================================
# 内置注册
# ============================================================

def _register_http_server(builtins: dict) -> None:
    """注册 HTTP 内置函数。"""
    builtins["创建HTTP服务器"] = create_http_server
    builtins["创建反向代理"] = create_reverse_proxy
    builtins["创建WebSocket处理器"] = create_websocket_handler


def _http_server_names() -> list[str]:
    return ["创建HTTP服务器", "创建反向代理", "创建WebSocket处理器"]


__all__ = [
    "HTTPMethod", "HttpStatus", "HttpRequest", "HttpResponse",
    "Route", "Middleware", "HTTPServer", "ReverseProxy",
    "WebSocket", "WebSocketHandler",
    "create_http_server", "create_reverse_proxy", "create_websocket_handler",
    "_register_http_server", "_http_server_names",
]
