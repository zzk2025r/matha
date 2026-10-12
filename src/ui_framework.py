"""Matha UI 框架：React/Vue/Svelte 兼容的声明式 UI。"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ComponentType(Enum):
    ELEMENT = "element"
    COMPOSITE = "composite"
    CONTAINER = "container"
    TEXT = "text"
    INPUT = "input"
    BUTTON = "button"
    LAYOUT = "layout"
    CANVAS = "canvas"
    SVG = "svg"
    CUSTOM = "custom"


class EventType(Enum):
    CLICK = "click"
    CHANGE = "change"
    INPUT = "input"
    FOCUS = "focus"
    BLUR = "blur"
    SUBMIT = "submit"
    MOUSE_ENTER = "mouse_enter"
    MOUSE_LEAVE = "mouse_leave"
    KEY_DOWN = "key_down"
    KEY_UP = "key_up"
    SCROLL = "scroll"
    RESIZE = "resize"
    TOUCH_START = "touch_start"
    TOUCH_END = "touch_end"
    DRAG_START = "drag_start"
    DROP = "drop"


class LayoutDirection(Enum):
    ROW = "row"
    COLUMN = "column"
    ROW_REVERSE = "row-reverse"
    COLUMN_REVERSE = "column-reverse"


@dataclass
class VNode:
    tag: str = "div"
    props: dict[str, Any] = field(default_factory=dict)
    children: list[VNode] = field(default_factory=list)
    text: str | None = None
    key: str | None = None
    event_handlers: dict[str, Callable] = field(default_factory=dict)


@dataclass
class Style:
    display: str = "block"
    position: str = "relative"
    width: str | None = None
    height: str | None = None
    margin: str | None = None
    padding: str | None = None
    background: str | None = None
    color: str | None = None
    font_size: str | None = None
    font_weight: str | None = None
    border: str | None = None
    border_radius: str | None = None
    box_shadow: str | None = None
    flex: str | None = None
    flex_direction: str | None = None
    justify_content: str | None = None
    align_items: str | None = None
    overflow: str | None = None
    cursor: str | None = None
    opacity: float | None = None
    transform: str | None = None
    transition: str | None = None
    z_index: int | None = None


@dataclass
class State:
    _data: dict[str, Any] = field(default_factory=dict)
    _listeners: list[Callable] = field(default_factory=list)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        for listener in self._listeners:
            listener(key, value)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def subscribe(self, listener: Callable) -> None:
        self._listeners.append(listener)


@dataclass
class Props:
    _data: dict[str, Any] = field(default_factory=dict)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)


class Component:
    """UI 组件基类。"""

    def __init__(self, name: str = "Component",
                 props: Props | None = None):
        self.name = name
        self.props = props or Props()
        self.state = State()
        self._children: list[Component] = []
        self._mounted = False
        self._style = Style()
        self._event_handlers: dict[str, Callable] = {}
        self._vnode = VNode(tag="div")

    def render(self) -> VNode:
        return VNode(tag=self.name, props=self.props._data)

    def mount(self, container: Any) -> None:
        self._mounted = True
        self._vnode = self.render()

    def unmount(self) -> None:
        self._mounted = False

    def set_state(self, **kwargs) -> None:
        for k, v in kwargs.items():
            self.state.set(k, v)
        self._vnode = self.render()

    def on(self, event: str, handler: Callable) -> None:
        self._event_handlers[event] = handler

    def add_child(self, child: Component) -> None:
        self._children.append(child)

    def remove_child(self, child: Component) -> None:
        self._children.remove(child)

    def style(self, **kwargs) -> Component:
        for k, v in kwargs.items():
            setattr(self._style, k, v)
        return self


class Element(Component):
    """HTML 元素。"""

    def __init__(self, tag: str = "div",
                 props: Props | None = None):
        super().__init__(name=tag, props=props)
        self.tag = tag

    def render(self) -> VNode:
        return VNode(
            tag=self.tag,
            props=self.props._data,
            children=[c.render() if isinstance(c, Component) else c for c in self._children],
        )


class Text(Component):
    """文本元素。"""

    def __init__(self, content: str = ""):
        super().__init__(name="text")
        self.content = content

    def render(self) -> VNode:
        return VNode(tag="span", text=self.content)


class Button(Component):
    """按钮组件。"""

    def __init__(self, label: str = "Button",
                 variant: str = "primary",
                 disabled: bool = False):
        super().__init__(name="button")
        self.label = label
        self.variant = variant
        self.disabled = disabled
        self._on_click: Callable | None = None

    def render(self) -> VNode:
        return VNode(
            tag="button",
            props={"label": self.label, "disabled": self.disabled},
            children=[],
        )

    def on_click(self, handler: Callable) -> None:
        self._on_click = handler


class Input(Component):
    """输入组件。"""

    def __init__(self, input_type: str = "text",
                 placeholder: str = "",
                 value: str = ""):
        super().__init__(name="input")
        self.input_type = input_type
        self.placeholder = placeholder
        self.value = value
        self._on_change: Callable | None = None

    def render(self) -> VNode:
        return VNode(
            tag="input",
            props={"type": self.input_type, "placeholder": self.placeholder,
                   "value": self.value},
        )

    def on_change(self, handler: Callable) -> None:
        self._on_change = handler


class Container(Component):
    """布局容器。"""

    def __init__(self, direction: LayoutDirection = LayoutDirection.ROW,
                 gap: str = "8px"):
        super().__init__(name="container")
        self.direction = direction
        self.gap = gap
        self._flex_direction = direction.value.replace("_", "-")

    def render(self) -> VNode:
        return VNode(
            tag="div",
            props={"flex-direction": self._flex_direction, "gap": self.gap},
        )


class StateManager:
    """状态管理器。"""

    def __init__(self):
        self._stores: dict[str, State] = {}
        self._middlewares: list[Callable] = []

    def create_store(self, name: str,
                        initial: dict[str, Any] = None) -> State:
        store = State(_data=initial or {})
        self._stores[name] = store
        return store

    def get_store(self, name: str) -> State | None:
        return self._stores.get(name)

    def dispatch(self, action: str, payload: Any = None) -> None:
        for middleware in self._middlewares:
            middleware(action, payload)

    def subscribe(self, store_name: str, listener: Callable) -> None:
        store = self._stores.get(store_name)
        if store:
            store.subscribe(listener)


class EventEmitter:
    """事件发射器。"""

    def __init__(self):
        self._events: dict[str, list[Callable]] = {}

    def on(self, event: str, handler: Callable) -> None:
        if event not in self._events:
            self._events[event] = []
        self._events[event].append(handler)

    def emit(self, event: str, *args, **kwargs) -> None:
        for handler in self._events.get(event, []):
            handler(*args, **kwargs)

    def off(self, event: str, handler: Callable) -> None:
        if event in self._events:
            self._events[event].remove(handler)


class Router:
    """路由管理器。"""

    def __init__(self):
        self._routes: dict[str, Callable] = {}
        self._current_path = "/"
        self._params: dict[str, str] = {}

    def add_route(self, path: str, handler: Callable) -> None:
        self._routes[path] = handler

    def navigate(self, path: str) -> None:
        self._current_path = path
        self._params = self._parse_params(path)
        handler = self._routes.get(path)
        if handler:
            handler(self._params)

    def _parse_params(self, path: str) -> dict[str, str]:
        params = {}
        for part in path.split("/"):
            if part.startswith(":"):
                params[part[1:]] = ""
        return params

    def get_current_path(self) -> str:
        return self._current_path


class VirtualDOM:
    """虚拟 DOM 引擎。"""

    def __init__(self):
        self._root: VNode | None = None
        self._patches: list[dict[str, Any]] = []

    def create_element(self, tag: str,
                          props: dict[str, Any] = None,
                          *children) -> VNode:
        return VNode(tag=tag, props=props or {}, children=list(children))

    def render(self, vnode: VNode, container: Any) -> None:
        self._root = vnode

    def diff(self, old: VNode, new: VNode) -> list[dict[str, Any]]:
        patches = []
        if old.tag != new.tag:
            patches.append({"type": "replace", "new": new})
        elif old.text != new.text:
            patches.append({"type": "text", "new": new.text})
        else:
            for i, (oc, nc) in enumerate(zip(old.children, new.children)):
                patches.extend(self.diff(oc, nc))
        return patches

    def patch(self, patches: list[dict[str, Any]]) -> None:
        for p in patches:
            self._patches.append(p)


class CSS:
    """CSS 引擎。"""

    def __init__(self):
        self._rules: list[dict[str, str]] = []
        self._animations: list[dict[str, Any]] = []

    def add_rule(self, selector: str,
                    declarations: dict[str, str]) -> None:
        self._rules.append({"selector": selector, "declarations": declarations})

    def animate(self, element: Any,
                   keyframes: list[dict[str, Any]],
                   duration: float = 300,
                   easing: str = "ease") -> None:
        self._animations.append({
            "element": element, "keyframes": keyframes,
            "duration": duration, "easing": easing,
        })


def create_component(name: str = "Component") -> Component:
    return Component(name=name)


def create_element(tag: str, props: dict[str, Any] = None,
                       *children) -> VNode:
    return VNode(tag=tag, props=props or {}, children=list(children))


def create_container(direction: LayoutDirection = LayoutDirection.ROW,
                         gap: str = "8px") -> Container:
    return Container(direction=direction, gap=gap)


def create_button(label: str = "Button",
                      variant: str = "primary") -> Button:
    return Button(label=label, variant=variant)


def create_input(input_type: str = "text",
                     placeholder: str = "") -> Input:
    return Input(input_type=input_type, placeholder=placeholder)


def create_router() -> Router:
    return Router()


def create_state_manager() -> StateManager:
    return StateManager()


def create_event_emitter() -> EventEmitter:
    return EventEmitter()


def create_virtual_dom() -> VirtualDOM:
    return VirtualDOM()


def create_css() -> CSS:
    return CSS()


# ============================================================
# 内置注册
# ============================================================

def _register_ui_framework(builtins: dict) -> None:
    builtins["创建组件"] = create_component
    builtins["创建元素"] = create_element
    builtins["创建容器"] = create_container
    builtins["创建按钮"] = create_button
    builtins["创建输入"] = create_input
    builtins["创建路由"] = create_router
    builtins["创建状态管理器"] = create_state_manager
    builtins["创建事件发射器"] = create_event_emitter
    builtins["创建虚拟DOM"] = create_virtual_dom
    builtins["创建CSS"] = create_css


def _ui_framework_names() -> list[str]:
    return ["创建组件", "创建元素", "创建容器",
            "创建按钮", "创建输入", "创建路由",
            "创建状态管理器", "创建事件发射器",
            "创建虚拟DOM", "创建CSS"]


__all__ = [
    "ComponentType", "EventType", "LayoutDirection",
    "VNode", "Style", "State", "Props",
    "Component", "Element", "Text", "Button", "Input",
    "Container", "StateManager", "EventEmitter",
    "Router", "VirtualDOM", "CSS",
    "create_component", "create_element", "create_container",
    "create_button", "create_input", "create_router",
    "create_state_manager", "create_event_emitter",
    "create_virtual_dom", "create_css",
    "_register_ui_framework", "_ui_framework_names",
]
