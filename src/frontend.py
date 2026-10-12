"""Matha 前端框架：组件、状态管理、虚拟 DOM。"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ComponentType(Enum):
    DIV = "div"
    SPAN = "span"
    INPUT = "input"
    BUTTON = "button"
    TEXT = "text"
    CONTAINER = "container"
    LIST = "list"
    FORM = "form"
    TABLE = "table"
    MODAL = "modal"
    NAVBAR = "navbar"
    CANVAS = "canvas"
    SVG_ELEMENT = "svg"
    VIDEO = "video"
    AUDIO = "audio"
    CUSTOM = "custom"


class EventType(Enum):
    CLICK = "click"
    CHANGE = "change"
    INPUT = "input"
    SUBMIT = "submit"
    FOCUS = "focus"
    BLUR = "blur"
    MOUSE_OVER = "mouseover"
    MOUSE_OUT = "mouseout"
    KEY_PRESS = "keypress"
    TOUCH_START = "touchstart"
    TOUCH_END = "touchend"
    SCROLL = "scroll"
    LOAD = "load"
    ERROR = "error"
    RESIZE = "resize"


class BindingType(Enum):
    ONE_WAY = "one-way"
    TWO_WAY = "two-way"
    COMPUTED = "computed"
    EVENT = "event"
    SLOT = "slot"


@dataclass
class VNode:
    tag: str = "div"
    props: dict[str, Any] = field(default_factory=dict)
    children: list[VNode] = field(default_factory=list)
    text: str | None = None
    key: str | None = None
    events: dict[str, Callable] = field(default_factory=dict)
    style: dict[str, str] = field(default_factory=dict)
    class_name: str | None = None


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


@dataclass
class Style:
    display: str = "block"
    flex_direction: str = "row"
    justify_content: str = "flex-start"
    align_items: str = "stretch"
    width: str | None = None
    height: str | None = None
    margin: str | None = None
    padding: str | None = None
    background: str | None = None
    color: str | None = None
    font_size: str | None = None
    border: str | None = None
    border_radius: str | None = None
    box_shadow: str | None = None
    overflow: str | None = None
    position: str = "relative"
    z_index: int | None = None
    opacity: float | None = None
    transform: str | None = None
    transition: str | None = None


class Component:
    """前端组件。"""

    def __init__(self, name: str = "Component",
                 props: Props | None = None):
        self.name = name
        self.props = props or Props()
        self.state = State()
        self._children: list[Component] = []
        self._style = Style()
        self._events: dict[str, Callable] = {}
        self._vnode = VNode(tag="div")
        self._mounted = False
        self._slots: dict[str, Component] = {}

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
        self._events[event] = handler

    def add_child(self, child: Component) -> None:
        self._children.append(child)

    def style(self, **kwargs) -> Component:
        for k, v in kwargs.items():
            setattr(self._style, k, v)
        return self

    def slot(self, name: str, component: Component) -> None:
        self._slots[name] = component


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
            children=[c.render() if isinstance(c, Component) else c
                      for c in self._children],
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

    def render(self) -> VNode:
        return VNode(tag="button",
                     props={"label": self.label,
                            "disabled": self.disabled})


class Input(Component):
    """输入组件。"""

    def __init__(self, type: str = "text",
                 placeholder: str = "",
                 value: str = ""):
        super().__init__(name="input")
        self.type = type
        self.placeholder = placeholder
        self.value = value

    def render(self) -> VNode:
        return VNode(tag="input",
                     props={"type": self.type,
                            "placeholder": self.placeholder,
                            "value": self.value})


class Container(Component):
    """布局容器。"""

    def __init__(self, direction: str = "row",
                 gap: str = "8px",
                 justify: str = "flex-start"):
        super().__init__(name="container")
        self.direction = direction
        self.gap = gap
        self.justify = justify

    def render(self) -> VNode:
        return VNode(tag="div",
                     props={"flex-direction": self.direction,
                            "gap": self.gap,
                            "justify": self.justify})


class StateManager:
    """状态管理器。"""

    def __init__(self):
        self._stores: dict[str, State] = {}
        self._middlewares: list[Callable] = []

    def create_store(self, name: str,
                        initial: dict[str, Any] = None
                        ) -> State:
        store = State(_data=initial or {})
        self._stores[name] = store
        return store

    def get_store(self, name: str) -> State | None:
        return self._stores.get(name)

    def dispatch(self, action: str, payload: Any = None) -> None:
        for mw in self._middlewares:
            mw(action, payload)


class Store(Component):
    """状态存储组件。"""

    def __init__(self, name: str, initial: dict[str, Any] = None):
        super().__init__(name=name)
        self._state = State(_data=initial or {})
        self._reducers: list[Callable] = []

    def dispatch(self, action: str, payload: Any = None) -> None:
        for reducer in self._reducers:
            reducer(self._state, action, payload)

    def get_state(self) -> State:
        return self._state


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
    """路由器。"""

    def __init__(self):
        self._routes: dict[str, Callable] = {}
        self._current_path = "/"
        self._params: dict[str, str] = {}

    def add_route(self, path: str, handler: Callable) -> None:
        self._routes[path] = handler

    def navigate(self, path: str) -> None:
        self._current_path = path
        handler = self._routes.get(path)
        if handler:
            handler()


class VirtualDOM:
    """虚拟 DOM。"""

    def __init__(self):
        self._root: VNode | None = None
        self._patches: list[dict[str, Any]] = []

    def create(self, tag: str, props: dict[str, Any] = None,
                  *children) -> VNode:
        return VNode(tag=tag, props=props or {},
                     children=list(children))

    def render(self, vnode: VNode, container: Any) -> None:
        self._root = vnode

    def diff(self, old: VNode, new: VNode
                 ) -> list[dict[str, Any]]:
        patches = []
        if old.tag != new.tag:
            patches.append({"type": "replace", "new": new})
        elif old.text != new.text:
            patches.append({"type": "text", "new": new.text})
        return patches

    def patch(self, patches: list[dict[str, Any]]) -> None:
        self._patches.extend(patches)


class CSS:
    """CSS 引擎。"""

    def __init__(self):
        self._rules: list[dict[str, str]] = []
        self._animations: list[dict[str, Any]] = []

    def add_rule(self, selector: str,
                    declarations: dict[str, str]) -> None:
        self._rules.append({"selector": selector,
                            "declarations": declarations})

    def animate(self, element: Any, keyframes: list[dict[str, Any]],
                   duration: float = 300,
                   easing: str = "ease") -> None:
        self._animations.append({
            "element": element, "keyframes": keyframes,
            "duration": duration, "easing": easing,
        })

    def keyframes(self, name: str,
                     frames: dict[str, dict[str, str]]) -> None:
        pass


class ComponentBuilder:
    """组件构建器。"""

    def __init__(self, tag: str = "div"):
        self._tag = tag
        self._props: dict[str, Any] = {}
        self._children: list[Any] = []
        self._style: dict[str, str] = {}
        self._events: dict[str, Callable] = {}

    def prop(self, key: str, value: Any) -> ComponentBuilder:
        self._props[key] = value
        return self

    def style(self, **kwargs) -> ComponentBuilder:
        self._style.update(kwargs)
        return self

    def on(self, event: str, handler: Callable) -> ComponentBuilder:
        self._events[event] = handler
        return self

    def child(self, child: Any) -> ComponentBuilder:
        self._children.append(child)
        return self

    def build(self) -> VNode:
        return VNode(tag=self._tag, props=self._props,
                     children=self._children)


def create_component(name: str = "Component") -> Component:
    return Component(name=name)


def create_element(tag: str, props: dict[str, Any] = None,
                       *children) -> VNode:
    return VNode(tag=tag, props=props or {}, children=list(children))


def create_container(direction: str = "row") -> Container:
    return Container(direction=direction)


def create_button(label: str = "Button",
                      variant: str = "primary") -> Button:
    return Button(label=label, variant=variant)


def create_input(type: str = "text",
                      placeholder: str = "") -> Input:
    return Input(type=type, placeholder=placeholder)


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


def create_component_builder(tag: str = "div") -> ComponentBuilder:
    return ComponentBuilder(tag=tag)


# ============================================================
# 内置注册
# ============================================================

def _register_frontend(builtins: dict) -> None:
    builtins["创建组件"] = create_component
    builtins["创建元素"] = create_element
    builtins["创建容器"] = create_container
    builtins["创建按钮"] = create_button
    builtins["创建输入"] = create_input
    builtins["创建路由器"] = create_router
    builtins["创建状态管理器"] = create_state_manager
    builtins["创建事件发射器"] = create_event_emitter
    builtins["创建虚拟DOM"] = create_virtual_dom
    builtins["创建CSS"] = create_css
    builtins["创建组件构建器"] = create_component_builder


def _frontend_names() -> list[str]:
    return ["创建组件", "创建元素", "创建容器",
            "创建按钮", "创建输入", "创建路由器",
            "创建状态管理器", "创建事件发射器",
            "创建虚拟DOM", "创建CSS",
            "创建组件构建器"]


__all__ = [
    "ComponentType", "EventType", "BindingType",
    "VNode", "Style", "State", "Props",
    "Component", "Element", "Text", "Button", "Input",
    "Container", "StateManager", "Store",
    "EventEmitter", "Router", "VirtualDOM", "CSS",
    "ComponentBuilder",
    "create_component", "create_element", "create_container",
    "create_button", "create_input", "create_router",
    "create_state_manager", "create_event_emitter",
    "create_virtual_dom", "create_css",
    "create_component_builder",
    "_register_frontend", "_frontend_names",
]
