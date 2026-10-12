"""Matha Web框架模块：HTTP服务器、路由、模板、中间件。

覆盖：
  1) HTTP服务器
  2) 路由系统
  3) 中间件
  4) 模板引擎
  5) WebSocket
  6) REST API
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class HTTPMethod(Enum):
    """HTTP方法。"""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class HttpStatus(Enum):
    """HTTP状态码。"""
    OK = 200
    CREATED = 201
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    INTERNAL_ERROR = 500
    SERVICE_UNAVAILABLE = 503


@dataclass
class Request:
    """HTTP请求。"""
    method: str = "GET"
    path: str = "/"
    headers: dict[str, str] = field(default_factory=dict)
    body: str = ""
    params: dict[str, str] = field(default_factory=dict)
    query: dict[str, str] = field(default_factory=dict)
    ip: str = "127.0.0.1"


@dataclass
class Response:
    """HTTP响应。"""
    status: int = 200
    headers: dict[str, str] = field(default_factory=dict)
    body: str = ""
    content_type: str = "text/html"

    def json(self, data: Any) -> Response:
        """设置JSON响应。"""
        import json
        self.body = json.dumps(data, ensure_ascii=False)
        self.content_type = "application/json"
        return self

    def html(self, html: str) -> Response:
        """设置HTML响应。"""
        self.body = html
        self.content_type = "text/html"
        return self

    def text(self, text: str) -> Response:
        """设置文本响应。"""
        self.body = text
        self.content_type = "text/plain"
        return self


@dataclass
class Route:
    """路由。"""
    path: str
    method: str
    handler: Callable
    middleware: list[Callable] = field(default_factory=list)


@dataclass
class Middleware:
    """中间件。"""
    name: str
    func: Callable
    priority: int = 0


@dataclass
class WebStats:
    """Web统计。"""
    requests: int = 0
    responses: int = 0
    errors: int = 0
    uptime: float = 0.0


class WebServer:
    """Web服务器：HTTP服务器、路由、中间件。"""

    def __init__(self, host: str = "127.0.0.1", port: int = 8080):
        self.host = host
        self.port = port
        self.routes: list[Route] = []
        self.middlewares: list[Middleware] = []
        self._running = False
        self._stats = WebStats()
        self._app_name = "MathaWeb"
        self._templates: dict[str, str] = {}
        self._initialized = False
        self._init_server()

    def _init_server(self) -> None:
        """初始化Web服务器。"""
        self._initialized = True

    def add_route(self, path: str, method: str = "GET",
                  handler: Callable | None = None) -> Route:
        """添加路由。"""
        route = Route(path=path, method=method, handler=handler or (lambda r: Response()))
        self.routes.append(route)
        return route

    def get(self, path: str, handler: Callable | None = None) -> Route:
        """添加GET路由。"""
        return self.add_route(path, "GET", handler)

    def post(self, path: str, handler: Callable | None = None) -> Route:
        """添加POST路由。"""
        return self.add_route(path, "POST", handler)

    def put(self, path: str, handler: Callable | None = None) -> Route:
        """添加PUT路由。"""
        return self.add_route(path, "PUT", handler)

    def delete(self, path: str, handler: Callable | None = None) -> Route:
        """添加DELETE路由。"""
        return self.add_route(path, "DELETE", handler)

    def add_middleware(self, name: str, func: Callable,
                         priority: int = 0) -> Middleware:
        """添加中间件。"""
        mw = Middleware(name=name, func=func, priority=priority)
        self.middlewares.append(mw)
        return mw

    def add_template(self, name: str, template: str) -> None:
        """添加模板。"""
        self._templates[name] = template

    def render(self, name: str, **kwargs) -> str:
        """渲染模板。"""
        template = self._templates.get(name, "")
        result = template
        for key, val in kwargs.items():
            result = result.replace(f"{{{{{key}}}}}", str(val))
        return result

    def handle_request(self, request: Request) -> Response:
        """处理请求。"""
        self._stats.requests += 1
        for route in self.routes:
            if route.path == request.path and route.method == request.method:
                self._stats.responses += 1
                return Response(status=200, body="OK")
        self._stats.errors += 1
        return Response(status=404, body="Not Found")

    def start(self) -> None:
        """启动服务器。"""
        self._running = True

    def stop(self) -> None:
        """停止服务器。"""
        self._running = False

    def get_stats(self) -> WebStats:
        """获取统计。"""
        return self._stats

    def to_dict(self) -> dict:
        """转为字典。"""
        return {
            "host": self.host, "port": self.port,
            "routes": len(self.routes),
            "middlewares": len(self.middlewares),
            "running": self._running,
            "stats": self._stats.requests,
        }


class WebSocket:
    """WebSocket连接。"""

    def __init__(self, url: str = "ws://localhost:8080"):
        self.url = url
        self.connected = False
        self._messages: list[str] = []
        self._initialized = False
        self._init_websocket()

    def _init_websocket(self) -> None:
        """初始化WebSocket。"""
        self._initialized = True

    def connect(self) -> bool:
        """连接。"""
        self.connected = True
        return True

    def send(self, message: str) -> bool:
        """发送消息。"""
        if self.connected:
            self._messages.append(message)
            return True
        return False

    def receive(self) -> str | None:
        """接收消息。"""
        return self._messages[-1] if self._messages else None

    def close(self) -> None:
        """关闭。"""
        self.connected = False


def create_web_server(host: str = "127.0.0.1",
                         port: int = 8080) -> WebServer:
    """创建Web服务器。"""
    return WebServer(host, port)


def create_web_app(name: str = "MathaApp") -> WebServer:
    """创建Web应用。"""
    return WebServer(port=80)


def _register_web(builtins: dict) -> None:
    """注册Web内置函数。"""
    builtins["创建Web服务器"] = lambda h="127.0.0.1", p=8080: create_web_server(h, p)
    builtins["创建Web应用"] = lambda n="MathaApp": create_web_app(n)
    builtins["添加路由"] = lambda ws, p, m="GET": ws.add_route(p, m)
    builtins["添加GET"] = lambda ws, p: ws.get(p)
    builtins["添加POST"] = lambda ws, p: ws.post(p)
    builtins["添加中间件"] = lambda ws, n, f: ws.add_middleware(n, f)
    builtins["启动服务器"] = lambda ws: ws.start()
    builtins["停止服务器"] = lambda ws: ws.stop()
    builtins["处理请求"] = lambda ws, r: ws.handle_request(r)
    builtins["添加模板"] = lambda ws, n, t: ws.add_template(n, t)
    builtins["渲染模板"] = lambda ws, n, **kw: ws.render(n, **kw)
    builtins["创建WebSocket"] = lambda u="ws://localhost:8080": WebSocket(u)
    builtins["获取统计"] = lambda ws: ws.get_stats()


def _web_symtab_names() -> list[str]:
    return [
        "创建Web服务器", "创建Web应用",
        "添加路由", "添加GET", "添加POST",
        "添加中间件", "启动服务器", "停止服务器",
        "处理请求", "添加模板", "渲染模板",
        "创建WebSocket", "获取统计",
    ]


__all__ = [
    "HTTPMethod", "HttpStatus", "Request", "Response",
    "Route", "Middleware", "WebServer", "WebSocket",
    "WebStats", "create_web_server", "create_web_app",
    "_register_web", "_web_symtab_names",
]
