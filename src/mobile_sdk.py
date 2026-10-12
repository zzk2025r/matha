"""Matha 移动 SDK：iOS/Android 生命周期、UI 组件、传感器、推送。"""
from __future__ import annotations

import base64
import collections
import hashlib
import math
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PlatformType(Enum):
    IOS = "ios"
    ANDROID = "android"
    HARMONYOS = "harmonyos"
    CROSS = "cross"


class LifecycleState(Enum):
    CREATED = "created"
    STARTED = "started"
    RESUMED = "resumed"
    PAUSED = "paused"
    STOPPED = "stopped"
    DESTROYED = "destroyed"
    BACKGROUND = "background"
    FOREGROUND = "foreground"


class AppState(Enum):
    NOT_INSTALLED = "not_installed"
    INSTALLED = "installed"
    RUNNING = "running"
    BACKGROUNDED = "backgrounded"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"


class LayoutType(Enum):
    VERTICAL = "vertical"
    HORIZONTAL = "horizontal"
    ZIGZAG = "zigzag"


class WidgetType(Enum):
    CONTAINER = "container"
    TEXT = "text"
    IMAGE = "image"
    BUTTON = "button"
    TEXT_FIELD = "text_field"
    SWITCH = "switch"
    SLIDER = "slider"
    LIST_VIEW = "list_view"
    SCROLL_VIEW = "scroll_view"
    GRID_VIEW = "grid_view"
    TAB_BAR = "tab_bar"
    NAV_BAR = "nav_bar"
    CARD = "card"


class Permission(Enum):
    CAMERA = "camera"
    MICROPHONE = "microphone"
    LOCATION = "location"
    CONTACTS = "contacts"
    CALENDAR = "calendar"
    PHOTOS = "photos"
    STORAGE = "storage"
    NOTIFICATIONS = "notifications"
    BLUETOOTH = "bluetooth"
    NFC = "nfc"
    MOTION = "motion"
    HEALTH = "health"


class SensorType(Enum):
    ACCELEROMETER = "accelerometer"
    GYROSCOPE = "gyroscope"
    MAGNETOMETER = "magnetometer"
    BAROMETER = "barometer"
    PROXIMITY = "proximity"
    AMBIENT_LIGHT = "ambient_light"
    STEP_COUNTER = "step_counter"
    HEART_RATE = "heart_rate"
    GPS = "gps"
    FINGERPRINT = "fingerprint"
    FACE_ID = "face_id"


class UIDensity(Enum):
    MDPI = "mdpi"
    XHDPI = "xhdpi"
    XXHDPI = "xxhdpi"
    XXXHDPI = "xxxhdpi"


class Orientation(Enum):
    PORTRAIT = "portrait"
    LANDSCAPE_LEFT = "landscape_left"
    LANDSCAPE_RIGHT = "landscape_right"
    PORTRAIT_UPSIDE_DOWN = "portrait_upside_down"


@dataclass
class Widget:
    widget_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: WidgetType = WidgetType.CONTAINER
    text: str = ""
    children: list[Widget] = field(default_factory=list)
    parent: Widget | None = None
    props: dict[str, Any] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)
    constraints: dict[str, Any] = field(default_factory=dict)
    frame: tuple[float, float, float, float] = (0, 0, 0, 0)
    padding: tuple[float, float, float, float] = (0, 0, 0, 0)
    margin: tuple[float, float, float, float] = (0, 0, 0, 0)
    background: str = "#00000000"
    on_tap: Callable | None = None
    visible: bool = True
    enabled: bool = True

    def add(self, child: Widget) -> Widget:
        child.parent = self
        self.children.append(child)
        return child

    def remove(self, child: Widget) -> bool:
        if child in self.children:
            self.children.remove(child)
            child.parent = None
            return True
        return False

    def find(self, widget_id: str) -> Widget | None:
        if self.widget_id == widget_id:
            return self
        for c in self.children:
            r = c.find(widget_id)
            if r:
                return r
        return None

    def walk(self) -> list[Widget]:
        out = [self]
        for c in self.children:
            out.extend(c.walk())
        return out

    def set_state(self, key: str, value: Any) -> None:
        self.state[key] = value
        self._invalidate()

    def get_state(self, key: str, default: Any = None) -> Any:
        return self.state.get(key, default)

    def _invalidate(self) -> None:
        n = self.parent
        while n:
            n.state["dirty"] = True
            n = n.parent

    def tap(self) -> Any:
        if not self.enabled:
            return None
        if self.on_tap:
            return self.on_tap()
        return None


class WidgetBuilder:
    """Widget 构建器。"""

    def __init__(self, platform: PlatformType = PlatformType.ANDROID):
        self.platform = platform

    def container(self, **kwargs: Any) -> Widget:
        return self._make(WidgetType.CONTAINER, **kwargs)

    def text(self, content: str, **kwargs: Any) -> Widget:
        w = self._make(WidgetType.TEXT, **kwargs)
        w.text = content
        return w

    def button(self, label: str,
               on_tap: Callable | None = None) -> Widget:
        w = self._make(WidgetType.BUTTON)
        w.text = label
        w.on_tap = on_tap
        return w

    def text_field(self, hint: str = "") -> Widget:
        w = self._make(WidgetType.TEXT_FIELD)
        w.state["hint"] = hint
        w.state["value"] = ""
        return w

    def image(self, source: str) -> Widget:
        w = self._make(WidgetType.IMAGE)
        w.props["source"] = source
        return w

    def card(self, **kwargs: Any) -> Widget:
        return self._make(WidgetType.CARD, **kwargs)

    def list_view(self, items: list[str] | None = None) -> Widget:
        w = self._make(WidgetType.LIST_VIEW)
        w.state["items"] = items or []
        w.state["scroll_offset"] = 0
        return w

    def _make(self, wtype: WidgetType, **kwargs: Any) -> Widget:
        w = Widget(type=wtype)
        for k, v in kwargs.items():
            if k in ("width", "height", "x", "y"):
                continue
            w.props[k] = v
        return w


class FlexLayout:
    """Flex 布局引擎。"""

    def __init__(self, main_axis: LayoutType = LayoutType.VERTICAL,
                 main_axis_alignment: str = "start",
                 cross_axis_alignment: str = "start",
                 spacing: float = 0.0):
        self.main_axis = main_axis
        self.main_align = main_axis_alignment
        self.cross_align = cross_axis_alignment
        self.spacing = spacing
        self._laid_out = 0

    def layout(self, root: Widget,
               width: float = 375.0, height: float = 812.0
               ) -> int:
        self._laid_out = 0
        self._layout(root, 0, 0, width, height)
        return self._laid_out

    def _layout(self, w: Widget, x: float, y: float,
                avail_w: float, avail_h: float) -> None:
        self._laid_out += 1
        pt, pr, pb, pl = w.padding
        mt, mr, mb, ml = w.margin
        x, y = x + ml, y + mt
        avail_w = max(0.0, avail_w - pl - pr - ml - mr)
        avail_h = max(0.0, avail_h - pt - pb - mt - mb)
        kids = [c for c in w.children if c.visible]
        if not kids:
            w.frame = (x, y, avail_w, avail_h)
            return
        horizontal = self.main_axis == LayoutType.HORIZONTAL
        pos = 0.0
        n = len(kids)
        for c in kids:
            cw = c.props.get("width") or (avail_w if horizontal
                                          else avail_w / n)
            ch = c.props.get("height") or (avail_h if not horizontal
                                          else avail_h / n)
            if horizontal:
                self._layout(c, x + pl + pos, y + pt, cw, avail_h)
            else:
                self._layout(c, x + pl, y + pt + pos, avail_w, ch)
            pos += ch + self.spacing
        w.frame = (x, y, avail_w, avail_h)


class LifecycleManager:
    """生命周期管理器。"""

    def __init__(self):
        self.state = LifecycleState.CREATED
        self.history: list[LifecycleState] = [self.state]
        self._callbacks: dict[LifecycleState,
                              list[Callable]] = collections.defaultdict(
                                  list)
        self._lock = threading.Lock()
        self._elapsed = 0.0
        self._start_time = time.time()

    def on(self, state: LifecycleState,
           callback: Callable) -> None:
        self._callbacks[state].append(callback)

    def transition(self, to: LifecycleState) -> bool:
        with self._lock:
            if to == self.state:
                return False
            self.state = to
            self.history.append(to)
            if to in (LifecycleState.RESUMED,
                      LifecycleState.STARTED):
                self._start_time = time.time()
            elif to in (LifecycleState.PAUSED,
                        LifecycleState.STOPPED,
                        LifecycleState.DESTROYED):
                self._elapsed += time.time() - self._start_time
        for cb in self._callbacks.get(to, []):
            cb(to)
        return True

    def uptime(self) -> float:
        if self.state in (LifecycleState.RESUMED,
                          LifecycleState.STARTED):
            return self._elapsed + (time.time() - self._start_time)
        return self._elapsed

    def snapshot(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "transitions": len(self.history) - 1,
            "uptime_s": round(self.uptime(), 3),
        }


class PermissionManager:
    """权限管理器。"""

    def __init__(self):
        self._granted: dict[Permission, bool] = {}
        self._requested: dict[Permission, float] = {}
        self._pending: set = set()
        self._usage: dict[Permission, int] = collections.Counter()
        self._lock = threading.Lock()

    def check(self, perm: Permission) -> str:
        if perm in self._pending:
            return "pending"
        if perm not in self._requested:
            return "not_requested"
        return "granted" if self._granted.get(perm) else "denied"

    def request(self, perm: Permission,
                auto_grant: bool = True) -> str:
        with self._lock:
            self._requested[perm] = time.time()
            self._pending.add(perm)
        time.sleep(0.01)
        with self._lock:
            self._granted[perm] = auto_grant
            self._pending.discard(perm)
        return self.check(perm)

    def revoke(self, perm: Permission) -> bool:
        with self._lock:
            if perm in self._requested:
                self._granted[perm] = False
                return True
        return False

    def record_use(self, perm: Permission) -> None:
        self._usage[perm] += 1

    def granted_list(self) -> list[str]:
        return [p.value for p, g in self._granted.items() if g]

    def get_usage(self) -> dict[str, int]:
        return {p.value: c for p, c in self._usage.items()}


class SensorHub:
    """传感器中枢。"""

    def __init__(self):
        self._readings: dict[SensorType, list[dict[str, Any]]] = \
            collections.defaultdict(list)
        self._subscribers: dict[SensorType,
                                list[Callable]] = \
            collections.defaultdict(list)
        self._active: set = set()
        self._interval = 0.05
        self._lock = threading.Lock()

    def subscribe(self, stype: SensorType,
                  callback: Callable) -> bool:
        self._subscribers[stype].append(callback)
        self._active.add(stype)
        return True

    def unsubscribe(self, stype: SensorType) -> bool:
        if stype in self._subscribers:
            self._subscribers[stype].clear()
            self._active.discard(stype)
            return True
        return False

    def start(self, stype: SensorType) -> bool:
        self._active.add(stype)
        return True

    def stop(self, stype: SensorType) -> bool:
        self._active.discard(stype)
        return True

    def emit(self, stype: SensorType, data: dict[str, Any]) -> None:
        reading = {
            "type": stype.value,
            "timestamp": time.time(),
            **data,
        }
        self._readings[stype].append(reading)
        if len(self._readings[stype]) > 1000:
            self._readings[stype] = self._readings[stype][-500:]
        for cb in self._subscribers.get(stype, []):
            cb(reading)

    def simulate_accelerometer(self, steps: int = 20) -> list[dict[str, Any]]:
        out = []
        for i in range(steps):
            t = i * 0.1
            reading = {
                "x": math.sin(t) * 9.8,
                "y": math.cos(t) * 9.8,
                "z": 9.8,
                "magnitude": 9.8,
            }
            self.emit(SensorType.ACCELEROMETER, reading)
            out.append(reading)
        return out

    def latest(self, stype: SensorType) -> dict[str, Any] | None:
        rs = self._readings.get(stype)
        return rs[-1] if rs else None

    def history(self, stype: SensorType,
                limit: int = 10) -> list[dict[str, Any]]:
        return self._readings.get(stype, [])[-limit:]

    def active_sensors(self) -> list[str]:
        return [s.value for s in self._active]


class NavigationStack:
    """导航栈。"""

    def __init__(self):
        self._stack: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    def push(self, route: str, **params: Any) -> int:
        with self._lock:
            self._stack.append({
                "route": route, "params": params,
                "pushed_at": time.time(),
            })
            return len(self._stack)

    def pop(self) -> dict[str, Any] | None:
        with self._lock:
            return self._stack.pop() if self._stack else None

    def replace(self, route: str, **params: Any) -> bool:
        with self._lock:
            if not self._stack:
                return False
            self._stack[-1] = {
                "route": route, "params": params,
                "pushed_at": time.time(),
            }
            return True

    def set_root(self, route: str, **params: Any) -> None:
        with self._lock:
            self._stack = [{"route": route, "params": params,
                            "pushed_at": time.time()}]

    def top(self) -> dict[str, Any] | None:
        return self._stack[-1] if self._stack else None

    def depth(self) -> int:
        return len(self._stack)

    def can_pop(self) -> bool:
        return len(self._stack) > 1

    def routes(self) -> list[str]:
        return [s["route"] for s in self._stack]


class StateManagement:
    """状态管理。"""

    def __init__(self):
        self._store: dict[str, Any] = {}
        self._listeners: dict[str, list[Callable]] = \
            collections.defaultdict(list)
        self._history: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            old = self._store.get(key)
            self._store[key] = value
            self._history.append({
                "key": key, "old": old, "new": value,
                "at": time.time(),
            })
        for cb in self._listeners.get(key, []):
            cb(value, old)

    def get(self, key: str, default: Any = None) -> Any:
        return self._store.get(key, default)

    def watch(self, key: str, callback: Callable) -> None:
        self._listeners[key].append(callback)

    def delete(self, key: str) -> bool:
        with self._lock:
            return self._store.pop(key, None) is not None

    def snapshot(self) -> dict[str, Any]:
        return dict(self._store)

    def undo_depth(self) -> int:
        return len(self._history)


class PushNotification:
    """推送通知。"""

    def __init__(self):
        self._tokens: dict[PlatformType, str] = {}
        self._delivered: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    def register_token(self, platform: PlatformType,
                       token: str) -> str:
        with self._lock:
            self._tokens[platform] = token
        return token

    def notify(self, platform: PlatformType, title: str,
               body: str, data: dict | None = None) -> bool:
        with self._lock:
            if platform not in self._tokens:
                return False
            self._delivered.append({
                "platform": platform.value,
                "title": title, "body": body,
                "data": data or {},
                "at": time.time(),
            })
        return True

    def badge(self, platform: PlatformType) -> int:
        return sum(1 for d in self._delivered
                   if d["platform"] == platform.value)

    def history(self, limit: int = 10) -> list[dict[str, Any]]:
        return self._delivered[-limit:]


class NetworkClient:
    """移动网络客户端。"""

    def __init__(self):
        self._cache: dict[str, tuple[float, Any]] = {}
        self._inflight: dict[str, float] = {}
        self._request_count = 0
        self._cache_ttl = 60.0
        self._lock = threading.Lock()

    def get(self, url: str, use_cache: bool = True) -> dict[str, Any]:
        with self._lock:
            self._request_count += 1
            if use_cache and url in self._cache:
                ts, val = self._cache[url]
                if time.time() - ts < self._cache_ttl:
                    return {"url": url, "data": val,
                            "cached": True,
                            "age": round(time.time() - ts, 2)}
        time.sleep(0.01)
        payload = self._fake_response(url)
        with self._lock:
            self._cache[url] = (time.time(), payload)
        return {"url": url, "data": payload,
                "cached": False, "age": 0.0}

    def _fake_response(self, url: str) -> dict[str, Any]:
        h = hashlib.sha256(url.encode()).hexdigest()[:12]
        return {"id": h, "url": url,
                "items": [h[i % len(h)] for i in range(5)],
                "ts": time.time()}

    def invalidate(self, url: str) -> bool:
        with self._lock:
            return self._cache.pop(url, None) is not None

    def stats(self) -> dict[str, Any]:
        return {"requests": self._request_count,
                "cached": len(self._cache)}


class AppBundle:
    """应用包。"""

    def __init__(self, package: str = "com.matha.app",
                 version: str = "4.5.0",
                 build: int = 450):
        self.package = package
        self.version = version
        self.build = build
        self.min_sdk = "24"
        self.permissions: list[Permission] = []
        self.activities: dict[str, str] = {}
        self.receivers: list[str] = []
        self.services: list[str] = []
        self.assets: dict[str, str] = {}
        self.signature: str = ""

    def add_permission(self, perm: Permission) -> AppBundle:
        if perm not in self.permissions:
            self.permissions.append(perm)
        return self

    def add_activity(self, name: str, label: str) -> AppBundle:
        self.activities[name] = label
        return self

    def add_receiver(self, name: str) -> AppBundle:
        self.receivers.append(name)
        return self

    def add_service(self, name: str) -> AppBundle:
        self.services.append(name)
        return self

    def sign(self, keystore: bytes) -> str:
        self.signature = base64.b64encode(
            hashlib.sha256(keystore).digest()).decode()
        return self.signature

    def manifest(self) -> dict[str, Any]:
        return {
            "package": self.package,
            "version": self.version,
            "build": self.build,
            "min_sdk": self.min_sdk,
            "permissions": [p.value for p in self.permissions],
            "activities": dict(self.activities),
            "receivers": list(self.receivers),
            "services": list(self.services),
            "signature": self.signature[:20],
        }


class MobileApp:
    """移动应用主控。"""

    def __init__(self, platform: PlatformType = PlatformType.ANDROID,
                 name: str = "Matha"):
        self.platform = platform
        self.name = name
        self.app_state = AppState.NOT_INSTALLED
        self.lifecycle = LifecycleManager()
        self.permissions = PermissionManager()
        self.sensors = SensorHub()
        self.navigation = NavigationStack()
        self.store = StateManagement()
        self.push = PushNotification()
        self.network = NetworkClient()
        self.bundle = AppBundle()
        self.root: Widget | None = None
        self.builder = WidgetBuilder(platform)
        self.layout = FlexLayout()
        self._view_stack: list[Widget] = []
        self._theme: dict[str, Any] = {}

    def install(self) -> bool:
        self.app_state = AppState.INSTALLED
        return True

    def launch(self) -> bool:
        if self.app_state == AppState.NOT_INSTALLED:
            self.install()
        self.app_state = AppState.RUNNING
        self.lifecycle.transition(LifecycleState.CREATED)
        self.lifecycle.transition(LifecycleState.STARTED)
        self.lifecycle.transition(LifecycleState.RESUMED)
        if self.root:
            self._view_stack = [self.root]
        return True

    def pause(self) -> bool:
        self.app_state = AppState.BACKGROUNDED
        return self.lifecycle.transition(LifecycleState.PAUSED)

    def resume(self) -> bool:
        self.app_state = AppState.RUNNING
        return self.lifecycle.transition(LifecycleState.RESUMED)

    def background(self) -> bool:
        self.app_state = AppState.SUSPENDED
        return self.lifecycle.transition(LifecycleState.BACKGROUND)

    def terminate(self) -> bool:
        self.app_state = AppState.TERMINATED
        return self.lifecycle.transition(LifecycleState.DESTROYED)

    def set_root_view(self, widget: Widget) -> Widget:
        self.root = widget
        self._view_stack = [widget]
        return widget

    def push_route(self, route: str, view: Widget | None = None,
                   **params: Any) -> int:
        depth = self.navigation.push(route, **params)
        if view is not None:
            self._view_stack.append(view)
        return depth

    def pop_route(self) -> dict[str, Any] | None:
        r = self.navigation.pop()
        if len(self._view_stack) > 1:
            self._view_stack.pop()
        return r

    def current_view(self) -> Widget | None:
        return self._view_stack[-1] if self._view_stack else None

    def set_theme(self, **kwargs: Any) -> dict[str, Any]:
        self._theme.update(kwargs)
        return dict(self._theme)

    def relayout(self, width: float = 375.0,
                 height: float = 812.0) -> int:
        if self.root is None:
            return 0
        return self.layout.layout(self.root, width, height)

    def build_ui(self) -> Widget:
        b = self.builder
        root = b.container()
        root.padding = (44, 16, 0, 16)
        nav = b.container()
        nav.props.update({"width": 375, "height": 56,
                          "background": "#1A1A2E"})
        title = b.text(self.name, color="#FFFFFF",
                       font_size=20, font_weight="bold")
        nav.add(title)
        root.add(nav)
        body = b.container()
        body.props.update({"width": 343, "height": 500})
        card = b.card()
        card.props.update({"width": 343, "height": 120,
                           "background": "#16213E"})
        card.add(b.text("欢迎使用 Matha 移动 SDK",
                        color="#FFFFFF", font_size=16))
        body.add(card)
        field = b.text_field("请输入内容")
        body.add(field)
        counter = {"n": 0}
        label = b.text("点击次数: 0", color="#4ECDC4")

        def on_tap() -> str:
            counter["n"] += 1
            label.set_state("text", f"点击次数: {counter['n']}")
            label.text = label.state["text"]
            return label.text
        btn = b.button("点我", on_tap)
        btn.props.update({"width": 160, "height": 44,
                          "background": "#0F3460"})
        body.add(btn)
        body.add(label)
        lst = b.list_view([f"列表项 {i}" for i in range(1, 6)])
        lst.props.update({"width": 343, "height": 200})
        body.add(lst)
        root.add(body)
        root.state["text_field"] = field
        root.state["counter_label"] = label
        return root

    def snapshot(self) -> dict[str, Any]:
        return {
            "app": self.name,
            "platform": self.platform.value,
            "state": self.app_state.value,
            "lifecycle": self.lifecycle.snapshot(),
            "nav_depth": self.navigation.depth(),
            "current_route": (self.navigation.top() or {}).get("route"),
            "permissions": self.permissions.granted_list(),
            "sensors": self.sensors.active_sensors(),
            "network": self.network.stats(),
            "badges": {p.value: self.push.badge(p)
                       for p in (PlatformType.IOS,
                                 PlatformType.ANDROID)},
        }


def create_mobile_app(platform: PlatformType = PlatformType.ANDROID,
                      name: str = "Matha") -> MobileApp:
    return MobileApp(platform, name)


def create_widget_builder(
    platform: PlatformType = PlatformType.ANDROID
) -> WidgetBuilder:
    return WidgetBuilder(platform)


def create_flex_layout(main_axis: LayoutType = LayoutType.VERTICAL
                       ) -> FlexLayout:
    return FlexLayout(main_axis)


def create_sensor_hub() -> SensorHub:
    return SensorHub()


def create_permission_manager() -> PermissionManager:
    return PermissionManager()


def create_navigation_stack() -> NavigationStack:
    return NavigationStack()


def create_app_bundle(package: str = "com.matha.app") -> AppBundle:
    return AppBundle(package)


# ============================================================
# 内置注册
# ============================================================

def _register_mobile(builtins: dict) -> None:
    builtins["创建移动应用"] = create_mobile_app
    builtins["创建组件构建器"] = create_widget_builder
    builtins["创建弹性布局"] = create_flex_layout
    builtins["创建传感器中枢"] = create_sensor_hub
    builtins["创建权限管理器"] = create_permission_manager
    builtins["创建导航栈"] = create_navigation_stack
    builtins["创建应用包"] = create_app_bundle


def _mobile_names() -> list[str]:
    return ["创建移动应用", "创建组件构建器", "创建弹性布局",
            "创建传感器中枢", "创建权限管理器", "创建导航栈",
            "创建应用包"]


__all__ = [
    "PlatformType", "LifecycleState", "AppState",
    "LayoutType", "WidgetType", "Permission",
    "SensorType", "UIDensity", "Orientation",
    "Widget", "WidgetBuilder", "FlexLayout",
    "LifecycleManager", "PermissionManager", "SensorHub",
    "NavigationStack", "StateManagement",
    "PushNotification", "NetworkClient", "AppBundle",
    "MobileApp",
    "create_mobile_app", "create_widget_builder",
    "create_flex_layout", "create_sensor_hub",
    "create_permission_manager", "create_navigation_stack",
    "create_app_bundle",
    "_register_mobile", "_mobile_names",
]
