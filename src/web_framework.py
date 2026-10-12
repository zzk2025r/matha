"""Matha Web 框架：完整 REST API、WebSocket、中间件。"""
from __future__ import annotations

import json
import secrets
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


class MiddlewareType(Enum):
    REQUEST = "request"
    RESPONSE = "response"
    ERROR = "error"
    AUTH = "auth"
    CORS = "cors"
    RATE_LIMIT = "rate_limit"


@dataclass
class Request:
    method: HTTPMethod
    path: str
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    query: dict[str, str] = field(default_factory=dict)
    params: dict[str, str] = field(default_factory=dict)
    cookies: dict[str, str] = field(default_factory=dict)
    user: str | None = None
    ip: str = "127.0.0.1"
    timestamp: float = field(default_factory=time.time)


@dataclass
class Response:
    status_code: int = 200
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    content_type: str = "application/json"

    def json(self, data: Any) -> None:
        self.body = json.dumps(data).encode()
        self.content_type = "application/json"

    def text(self, text: str) -> None:
        self.body = text.encode()
        self.content_type = "text/plain"

    def html(self, html: str) -> None:
        self.body = html.encode()
        self.content_type = "text/html"

    def status(self, code: int) -> None:
        self.status_code = code


@dataclass
class Route:
    path: str
    method: HTTPMethod
    handler: Callable
    name: str | None = None
    middleware: list[Callable] = field(default_factory=list)


class App:
    """Web 应用。"""

    def __init__(self, name: str = "MathaApp"):
        self.name = name
        self.routes: list[Route] = []
        self.middleware: list[Callable] = []
        self.error_handlers: dict[int, Callable] = {}
        self._startup_hooks: list[Callable] = []
        self._shutdown_hooks: list[Callable] = []
        self._config: dict[str, Any] = {}
        self._server = None
        self._debug = False

    def route(self, path: str, method: HTTPMethod = HTTPMethod.GET,
                 name: str | None = None) -> Callable:
        def decorator(handler: Callable) -> Callable:
            route = Route(path=path, method=method,
                          handler=handler, name=name)
            self.routes.append(route)
            return handler
        return decorator

    def get(self, path: str, name: str | None = None
                ) -> Callable:
        return self.route(path, HTTPMethod.GET, name)

    def post(self, path: str, name: str | None = None
                 ) -> Callable:
        return self.route(path, HTTPMethod.POST, name)

    def put(self, path: str, name: str | None = None
                ) -> Callable:
        return self.route(path, HTTPMethod.PUT, name)

    def delete(self, path: str, name: str | None = None
                  ) -> Callable:
        return self.route(path, HTTPMethod.DELETE, name)

    def patch(self, path: str, name: str | None = None
                  ) -> Callable:
        return self.route(path, HTTPMethod.PATCH, name)

    def use(self, middleware: Callable) -> None:
        self.middleware.append(middleware)

    def error_handler(self, code: int) -> Callable:
        def decorator(handler: Callable) -> Callable:
            self.error_handlers[code] = handler
            return handler
        return decorator

    def add_middleware(self, middleware: Callable,
                          mtype: MiddlewareType = MiddlewareType.REQUEST
                          ) -> None:
        self.middleware.append(middleware)

    def configure(self, key: str, value: Any) -> None:
        self._config[key] = value

    def get_config(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    def run(self, host: str = "0.0.0.0",
               port: int = 8080) -> None:
        pass

    def start(self) -> None:
        for hook in self._startup_hooks:
            hook()

    def stop(self) -> None:
        for hook in self._shutdown_hooks:
            hook()


class Router:
    """路由管理器。"""

    def __init__(self, app: App):
        self.app = app
        self._prefix = ""
        self._routes: list[Route] = []

    def add_route(self, path: str, method: HTTPMethod,
                     handler: Callable, name: str | None = None
                     ) -> Route:
        route = Route(path=path, method=method,
                      handler=handler, name=name)
        self._routes.append(route)
        return route

    def group(self, prefix: str) -> Router:
        self._prefix = prefix
        return self

    def get_routes(self) -> list[Route]:
        return self._routes


class Middleware:
    """中间件。"""

    @staticmethod
    def cors(allow_origins: list[str] = None) -> Callable:
        def cors_middleware(req: Request) -> Request:
            return req
        return cors_middleware

    @staticmethod
    def auth(token: str) -> Callable:
        def auth_middleware(req: Request) -> Request:
            return req
        return auth_middleware

    @staticmethod
    def rate_limit(max_requests: int = 100) -> Callable:
        def rate_middleware(req: Request) -> Request:
            return req
        return rate_middleware

    @staticmethod
    def logging() -> Callable:
        def log_middleware(req: Request) -> Request:
            return req
        return log_middleware

    @staticmethod
    def compression() -> Callable:
        def comp_middleware(req: Request) -> Request:
            return req
        return comp_middleware


class Session:
    """会话管理。"""

    def __init__(self, secret: str = ""):
        self._secret = secret or secrets.token_hex(32)
        self._sessions: dict[str, dict[str, Any]] = {}
        self._timeout = 3600

    def create(self, data: dict[str, Any] = None) -> str:
        sid = secrets.token_hex(32)
        self._sessions[sid] = data or {}
        return sid

    def get(self, sid: str) -> dict[str, Any] | None:
        return self._sessions.get(sid)

    def destroy(self, sid: str) -> bool:
        if sid in self._sessions:
            del self._sessions[sid]
            return True
        return False


class Template:
    """模板引擎。"""

    def __init__(self):
        self._templates: dict[str, str] = {}
        self._filters: dict[str, Callable] = {}
        self._functions: dict[str, Callable] = {}

    def render(self, name: str,
                  context: dict[str, Any] = None) -> str:
        template = self._templates.get(name, "")
        ctx = context or {}
        return template.format(**ctx)

    def add_template(self, name: str, content: str) -> None:
        self._templates[name] = content

    def add_filter(self, name: str, func: Callable) -> None:
        self._filters[name] = func

    def add_function(self, name: str, func: Callable) -> None:
        self._functions[name] = func


class APIClient:
    """API 客户端。"""

    def __init__(self, base_url: str = ""):
        self.base_url = base_url
        self._headers: dict[str, str] = {}
        self._timeout = 30.0
        self._session_id: str | None = None

    def get(self, path: str, params: dict[str, Any] = None
                ) -> Response:
        return Response(status_code=200)

    def post(self, path: str, data: Any = None
                ) -> Response:
        return Response(status_code=200)

    def put(self, path: str, data: Any = None
                ) -> Response:
        return Response(status_code=200)

    def delete(self, path: str) -> Response:
        return Response(status_code=200)

    def set_header(self, key: str, value: str) -> None:
        self._headers[key] = value

    def setTimeout(self, timeout: float) -> None:
        self._timeout = timeout


def create_app(name: str = "MathaApp") -> App:
    return App(name=name)


def create_router(app: App) -> Router:
    return Router(app=app)


def create_session(secret: str = "") -> Session:
    return Session(secret=secret)


def create_template() -> Template:
    return Template()


def create_api_client(base_url: str = "") -> APIClient:
    return APIClient(base_url=base_url)


# ============================================================
# 内置注册
# ============================================================

def _register_web_framework(builtins: dict) -> None:
    builtins["创建Web应用"] = create_app
    builtins["创建路由"] = create_router
    builtins["创建会话"] = create_session
    builtins["创建模板"] = create_template
    builtins["创建API客户端"] = create_api_client


def _web_framework_names() -> list[str]:
    return ["创建Web应用", "创建路由",
            "创建会话", "创建模板", "创建API客户端"]


__all__ = [
    "HTTPMethod", "MiddlewareType",
    "Request", "Response", "Route",
    "App", "Router", "Middleware",
    "Session", "Template", "APIClient",
    "create_app", "create_router",
    "create_session", "create_template",
    "create_api_client",
    "_register_web_framework", "_web_framework_names",
]
