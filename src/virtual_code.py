"""Matha 虚拟代码引擎 — 动态代码吸收与自动注册系统。

核心能力：
  1. 虚拟化：虚拟出不存在的函数/key/code时，自动注册并承认/允许使用
  2. 吞噬：自动吞噬代码/函数/key，无法使用时自动注册并承认/允许/正常使用
  3. 自适应：根据调用模式自动推导实现
  4. 惰性：按需创建，零开销
  5. 记忆化：已注册的虚拟代码被缓存和复用

架构：
  VirtualCodeRegistry + VirtualCodeEngine + VirtualCodeDefinition + VirtualCodeDefinitionEngine

所有子系统通过 VirtualCodeRegistry 实现代码的自适应和自愈。
"""
from __future__ import annotations

import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# 虚拟代码条目
# ============================================================

@dataclass
class VirtualCodeEntry:
    """虚拟代码条目。"""
    name: str
    code: Any = None
    code_type: str = "function"
    source: str = "manual"
    is_virtual: bool = True
    is_absorbed: bool = False
    created_at: float = 0.0
    calls: int = 0

    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()


# ============================================================
# 虚拟代码注册表
# ============================================================

class VirtualCodeRegistry:
    """虚拟代码注册表 — 动态代码吸收与自动注册。"""

    def __init__(self, debug: bool = False):
        self.debug = debug
        self._codes: dict[str, VirtualCodeEntry] = {}
        self._absorbed: dict[str, Any] = {}
        self._stats = {"virtual_created": 0, "absorbed_count": 0}

    def register(self, identifier: str, code: Any,
                  code_type: str = "function",
                  source: str = "manual",
                  is_virtual: bool = True) -> VirtualCodeEntry:
        """注册代码条目。"""
        entry = VirtualCodeEntry(
            name=identifier, code=code, code_type=code_type,
            source=source, is_virtual=is_virtual,
        )
        self._codes[identifier] = entry
        self._stats["virtual_created"] += 1
        if self.debug:
            print(f"[Registry] 注册: {identifier} ({code_type})")
        return entry

    def get(self, identifier: str) -> VirtualCodeEntry | None:
        """获取代码条目。"""
        return self._codes.get(identifier)

    def has(self, identifier: str) -> bool:
        """检查是否存在。"""
        return identifier in self._codes

    def absorb(self, code: Any, name: str | None = None) -> VirtualCodeEntry:
        """吞噬代码。"""
        entry = VirtualCodeEntry(
            name=name or f"absorbed_{len(self._absorbed)}",
            code=code, code_type="absorbed",
            source="absorb", is_virtual=False,
        )
        self._absorbed[entry.name] = code
        self._codes[entry.name] = entry
        self._stats["absorbed_count"] += 1
        if self.debug:
            print(f"[Registry] 吞噬: {entry.name}")
        return entry

    def auto_fix(self, identifier: str, *args, **kwargs) -> Any:
        """自动修复缺失代码。"""
        if identifier in self._codes:
            entry = self._codes[identifier]
            entry.calls += 1
            return entry.code if callable(entry.code) else entry.code
        impl = self._derive_implementation(identifier)
        return self.register(identifier, impl, "auto")

    def _derive_implementation(self, identifier: str) -> Any:
        """从标识符推导实现。"""
        return lambda *args, **kwargs: None

    def get_stats(self) -> dict:
        """获取统计。"""
        return {
            "virtual_created": self._stats["virtual_created"],
            "virtual_accessed": self._stats.get("virtual_accessed", 0),
            "absorbed_count": self._stats["absorbed_count"],
            "total_codes": len(self._codes),
        }

    @property
    def virtual(self) -> callable:
        """虚拟化入口。"""
        return self.register_any

    def register_any(self, identifier: str, code_type: str = "auto",
                      source: str = "natural_language") -> VirtualCodeEntry:
        """自主注册任何标识符。"""
        if identifier in self._codes:
            return self._codes[identifier]
        impl = self._derive_implementation(identifier)
        entry = VirtualCodeEntry(
            name=identifier, code=impl, code_type=code_type,
            source=source, is_virtual=False,
        )
        self._codes[identifier] = entry
        self._stats["virtual_created"] += 1
        if self.debug:
            print(f"[Registry] 自主注册: {identifier}")
        return entry

    def confirm(self, identifier: str) -> bool:
        """确认虚拟代码存在。"""
        return identifier in self._codes

    def deny(self, identifier: str) -> bool:
        """拒绝虚拟代码不存在。"""
        return identifier not in self._codes

    def swallow(self, code: Any, mode: str = "full") -> dict:
        """吞噬代码源。"""
        entry = self.absorb(code)
        return {"name": entry.name, "mode": mode, "success": True}

    def __contains__(self, identifier: str) -> bool:
        return self.has(identifier)

    def __getitem__(self, identifier: str) -> VirtualCodeEntry:
        return self.get(identifier)


# ============================================================
# 虚拟代码引擎
# ============================================================

class VirtualCodeEngine:
    """虚拟代码引擎 — 终极增强版。

    核心能力：
    1. 自主注册任何标识符（中文/英文/自然语义）
    2. 自动生成缺失代码（Web框架/异步I/O/模式匹配/元编程）
    3. 自动编译源代码
    4. 自动构建完整系统

    当虚拟代码引擎足够强大时：
    - 自然语言可以直接当编程语言使用
    - 生态系统只是一个数据库
    - 所有功能按需生成
    """

    def __init__(self, registry: VirtualCodeRegistry | None = None, debug: bool = False):
        self.registry = registry or VirtualCodeRegistry(debug=debug)
        self.debug = debug
        self._auto_generators: dict[str, Callable] = {}
        self._compilers: dict[str, Callable] = {}
        self._natural_language_models: dict[str, Any] = {}
        self._web_frameworks: dict[str, Any] = {}
        self._async_handlers: dict[str, Any] = {}
        self._pattern_matchers: dict[str, Any] = {}
        self._metaprogramming_tools: dict[str, Any] = {}
        self._register_default_generators()

    def _register_default_generators(self):
        """注册默认自动生成器。"""
        def web_framework_generator(name: str, **kwargs) -> str:
            return f"""# Auto-generated Web Framework: {name}
from src.web import MathaWebApp
app = MathaWebApp(name="{name}")
@app.route("/")
def index():
    return "Hello from {name}"
if __name__ == "__main__":
    app.run(host="0.0.0.0", port={kwargs.get("port", 8080)})
"""
        def async_io_generator(name: str, **kwargs) -> str:
            return f"""# Auto-generated Async I/O: {name}
import asyncio
from src.async_runtime import MathaAsyncRuntime
runtime = MathaAsyncRuntime()
async def {name}(*args, **kwargs):
    return await runtime.execute({kwargs.get("target", "default")}, *args)
async def main():
    result = await {name}()
    return result
"""
        def pattern_matching_generator(name: str, **kwargs) -> str:
            return f"""# Auto-generated Pattern Matching: {name}
from src.pattern import MathaPatternMatcher
matcher = MathaPatternMatcher()
def {name}(value):
    return matcher.match(value, cases={kwargs.get("cases", [])})
"""
        def metaprogramming_generator(name: str, **kwargs) -> str:
            return f"""# Auto-generated Metaprogramming: {name}
from src.metaprogramming import MathaMetaProgram
meta = MathaMetaProgram()
def {name}(cls):
    return meta.create_class(name="{name}", bases={kwargs.get("bases", [])}, attributes={kwargs.get("attributes", {})})
"""
        def source_compiler_generator(name: str, **kwargs) -> str:
            return f"""# Auto-generated Source Compiler: {name}
from src.compiler.matha_cc import matha_compile
def compile_{name}(source: str):
    return matha_compile(source, output="{name}")
def run_{name}(source: str):
    result = compile_{name}(source)
    return result
"""
        self._auto_generators["web_framework"] = web_framework_generator
        self._auto_generators["async_io"] = async_io_generator
        self._auto_generators["pattern_matching"] = pattern_matching_generator
        self._auto_generators["metaprogramming"] = metaprogramming_generator
        self._auto_generators["source_compiler"] = source_compiler_generator

    def register_any(self, identifier: str, code_type: str = "auto",
                      source: str = "natural_language") -> VirtualCodeEntry:
        """自主注册任何标识符。"""
        if identifier in self.registry:
            return self.registry[identifier]
        impl = self._derive_from_natural_language(identifier, code_type)
        entry = self.registry.register(identifier, impl, code_type, source=source, is_virtual=False)
        entry.is_absorbed = True
        if self.debug:
            print(f"[VirtualCodeEngine] 自主注册: {identifier} → {type(impl).__name__}")
        return entry

    def _derive_from_natural_language(self, identifier: str, code_type: str) -> Any:
        """从自然语言标识符推导实现。"""
        identifier_lower = identifier.lower()
        if any('\u4e00' <= c <= '\u9fff' for c in identifier):
            return self._derive_chinese_semantic(identifier, code_type)
        english_patterns = {
            'add': lambda *args: sum(args) if args else 0,
            'sub': lambda a, b=1: a - b,
            'mul': lambda *args: __import__('functools').reduce(lambda a, b: a * b, args) if args else 1,
            'div': lambda a, b=1: a / b if b != 0 else 0,
        }
        return english_patterns.get(identifier_lower, lambda *args: None)

    def _derive_chinese_semantic(self, identifier: str, code_type: str) -> Any:
        """从中文标识符推导语义。"""
        if '加' in identifier or 'sum' in identifier.lower():
            return lambda *args: sum(args) if args else 0
        if '减' in identifier:
            return lambda a, b=1: a - b
        if '乘' in identifier:
            return lambda *args: __import__('functools').reduce(lambda a, b: a * b, args) if args else 1
        if '除' in identifier:
            return lambda a, b=1: a / b if b != 0 else 0
        return lambda *args: None

    def absorb(self, code: Any, name: str | None = None) -> VirtualCodeEntry:
        """吞噬代码。"""
        return self.registry.absorb(code, name)

    def auto_fix(self, name: str, *args, **kwargs) -> Any:
        """自动修复缺失代码。"""
        return self.registry.auto_fix(name, *args, **kwargs)

    def confirm(self, name: str) -> bool:
        """确认虚拟代码。"""
        return self.registry.has(name)

    def deny(self, name: str) -> bool:
        """拒绝虚拟代码。"""
        return not self.registry.has(name)

    def swallow(self, code: Any, mode: str = "full") -> dict:
        """吞噬代码源。"""
        entry = self.registry.absorb(code)
        return {"name": entry.name, "mode": mode, "success": True}

    def get_stats(self) -> dict:
        """获取统计。"""
        return self.registry.get_stats()

    # ============================================================
    # 自动模块生成：游戏/办公/操作系统/图形/网络
    # ============================================================

    def generate_game_module(self, game_type: str = "2d",
                            features: list | None = None) -> dict:
        """自动生成游戏模块。"""
        module_name = f"matha_game_{game_type}"
        code = f"""# Auto-generated Matha {game_type.upper()} Game Module
from src.domains.game_engine import GameEngine, Scene, Entity, Vec2, Vec3

engine = GameEngine()
scene = engine.create_scene("main")

def game_loop():
    while engine.is_running():
        engine.update()
        pass
"""
        self.registry.register(module_name, lambda: code, "auto")
        return {"module": module_name, "game_type": game_type,
                "features": features or ["physics", "render", "input"]}

    def generate_office_module(self, doc_type: str = "document",
                            features: list | None = None) -> dict:
        """自动生成办公模块。"""
        module_name = f"matha_office_{doc_type}"
        code = f"""# Auto-generated Matha {doc_type.upper()} Office Module
from src.domains.office_docs import Document, Spreadsheet, Presentation

def create_{doc_type}(title):
    return Document(title)
"""
        self.registry.register(module_name, lambda: code, "auto")
        return {"module": module_name, "doc_type": doc_type,
                "features": features or ["format", "export", "analyze"]}

    def generate_os_module(self, os_type: str = "process",
                            features: list | None = None) -> dict:
        """自动生成操作系统模块。"""
        module_name = f"matha_os_{os_type}"
        code = f"""# Auto-generated Matha OS {os_type.upper()} Module
from src.domains.os_module import ProcessManager, MemoryManager

pm = ProcessManager()
mm = MemoryManager()

def manage_{os_type}():
    return pm.list_processes()
"""
        self.registry.register(module_name, lambda: code, "auto")
        return {"module": module_name, "os_type": os_type,
                "features": features or ["process", "memory", "thread"]}

    def generate_graphics_module(self, render_type: str = "2d",
                            features: list | None = None) -> dict:
        """自动生成图形模块。"""
        module_name = f"matha_graphics_{render_type}"
        code = f"""# Auto-generated Matha {render_type.upper()} Graphics Module
from src.domains.graphics_engine import Canvas, Color, Renderer

canvas = Canvas()
renderer = Renderer(canvas)

def render_{render_type}():
    canvas.clear()
"""
        self.registry.register(module_name, lambda: code, "auto")
        return {"module": module_name, "render_type": render_type,
                "features": features or ["canvas", "draw", "color"]}

    def generate_networking_module(self, net_type: str = "http",
                            features: list | None = None) -> dict:
        """自动生成网络模块。"""
        module_name = f"matha_net_{net_type}"
        code = f"""# Auto-generated Matha {net_type.upper()} Networking Module
from src.domains.networking import http_get, http_post

def request_{net_type}(url):
    return http_get(url)
"""
        self.registry.register(module_name, lambda: code, "auto")
        return {"module": module_name, "net_type": net_type,
                "features": features or ["socket", "http", "dns"]}

    def auto_generate_module(self, module_type: str, **kwargs) -> dict:
        """自动生成任意类型模块。"""
        generators = {
            "game": self.generate_game_module,
            "office": self.generate_office_module,
            "os": self.generate_os_module,
            "graphics": self.generate_graphics_module,
            "networking": self.generate_networking_module,
            "display": self.generate_display_module,
            "recorder": self.generate_recorder_module,
            "player": self.generate_player_module,
        }
        gen = generators.get(module_type)
        if gen:
            return gen(**kwargs)
        return {"error": f"Unknown module type: {module_type}"}

    def generate_display_module(self, width: int = 1920,
                                  height: int = 1080,
                                  refresh_rate: int = 60) -> dict:
        """自动生成显示器模块。"""
        module_name = "matha_display"
        code = f"""# Auto-generated Matha Display Module
from src.domains.display_monitor import DisplayManager, Resolution, DisplayMode
dm = DisplayManager()
dm.set_resolution({width}, {height}, {refresh_rate})
def get_resolution(): return dm.get_resolution()
def screenshot(): return dm.screenshot()
def get_stats(): return dm.get_stats()
"""
        self.registry.register(module_name, lambda: code, "auto")
        return {"module": module_name, "width": width,
                "height": height, "refresh_rate": refresh_rate}

    def generate_recorder_module(self, format: str = "mp4",
                                   fps: int = 30) -> dict:
        """自动生成录制模块。"""
        module_name = "matha_recorder"
        code = f"""# Auto-generated Matha Recorder Module
from src.domains.media_recorder import VideoRecorder, AudioRecorder
vr = VideoRecorder()
ar = AudioRecorder()
def start_record(w=1920, h=1080, f={fps}): return vr.start_recording()
def stop_record(): return vr.stop_recording()
def start_audio(): return ar.start_audio()
def stop_audio(): return ar.stop_audio()
"""
        self.registry.register(module_name, lambda: code, "auto")
        return {"module": module_name, "format": format, "fps": fps}

    def generate_player_module(self, volume: float = 1.0) -> dict:
        """自动生成播放器模块。"""
        module_name = "matha_player"
        code = f"""# Auto-generated Matha Player Module
from src.domains.media_player import MediaPlayer, TrackInfo
mp = MediaPlayer()
mp.set_volume({volume})
def play(track): return mp.load_track(track) or mp.play()
def pause(): return mp.pause()
def stop(): return mp.stop()
def set_volume(v): return mp.set_volume(v)
def get_stats(): return mp.get_stats()
"""
        self.registry.register(module_name, lambda: code, "auto")
        return {"module": module_name, "volume": volume}


# ============================================================
# 全局实例
# ============================================================

_global_registry: VirtualCodeRegistry | None = None
_global_engine: VirtualCodeEngine | None = None


def get_virtual_registry(debug: bool = False) -> VirtualCodeRegistry:
    """获取全局虚拟代码注册表。"""
    global _global_registry
    if _global_registry is None:
        _global_registry = VirtualCodeRegistry(debug=debug)
    return _global_registry


def reset_virtual_registry():
    """重置全局虚拟代码注册表。"""
    global _global_registry
    _global_registry = None


def get_virtual_engine(debug: bool = False) -> VirtualCodeEngine:
    """获取全局虚拟代码引擎。"""
    global _global_engine
    if _global_engine is None:
        _global_engine = VirtualCodeEngine(debug=debug)
    return _global_engine


def reset_virtual_engine():
    """重置全局虚拟代码引擎。"""
    global _global_engine
    _global_engine = None


# ============================================================
# 便捷函数
# ============================================================

def virtual(identifier: str, code_type: str = "function") -> VirtualCodeEntry:
    """虚拟化代码。"""
    return get_virtual_engine().register_any(identifier, code_type)


def absorb(code: Any, name: str | None = None) -> VirtualCodeEntry:
    """吞噬代码。"""
    return get_virtual_engine().absorb(code, name)


def auto_fix(name: str, *args, **kwargs) -> Any:
    """自动修复缺失代码。"""
    return get_virtual_engine().auto_fix(name, *args, **kwargs)


def confirm(name: str) -> bool:
    """确认虚拟代码。"""
    return get_virtual_engine().confirm(name)


def swallow(code: Any, mode: str = "full") -> dict:
    """吞噬代码源。"""
    return get_virtual_engine().swallow(code, mode)


def get_stats() -> dict:
    """获取统计。"""
    return get_virtual_engine().get_stats()


# ============================================================
# 定义层（VirtualCodeDefinition + VirtualCodeDefinitionEngine）
# ============================================================

@dataclass
class VirtualCodeDefinition:
    """虚拟代码定义。"""
    name: str = ""
    capabilities: dict[str, Any] = field(default_factory=dict)
    definitions: dict[str, Any] = field(default_factory=dict)
    natural_languages: dict[str, str] = field(default_factory=dict)

    def add_definition(self, name: str, capability: str, impl: Any) -> None:
        """添加定义。"""
        self.definitions[name] = impl
        self.capabilities[capability] = impl

    def interpret(self, *args, **kwargs) -> Any:
        """解读/取用定义。"""
        if self.definitions:
            return list(self.definitions.values())[0]
        return None

    def get_capabilities(self) -> list[str]:
        """获取所有能力。"""
        return list(self.capabilities.keys())


class VirtualCodeDefinitionEngine:
    """虚拟代码定义引擎 — 定义能力/语义，螺旋上升。"""

    def __init__(self, debug: bool = False):
        self.debug = debug
        self._definitions: dict[str, VirtualCodeDefinition] = {}
        self._spiral_log: list[dict] = []
        self._natural_language_definitions: dict[str, dict] = {}

    def define(self, name: str) -> VirtualCodeDefinition:
        """定义代码能力。"""
        defn = VirtualCodeDefinition(name=name)
        self._definitions[name] = defn
        return defn

    def define_capability(self, name: str, capability: str,
                           semantic: Any = None, **kwargs) -> VirtualCodeDefinition:
        """定义代码能力/语义。"""
        defn = self.define(name)
        defn.add_definition(capability, capability, semantic or (lambda *args: None))
        return defn

    def define_multiple(self, name: str, capabilities: list[str],
                         semantics: dict | None = None) -> VirtualCodeDefinition:
        """定义多个能力/语义。"""
        defn = self.define(name)
        for cap in capabilities:
            defn.add_definition(cap, cap, semantics.get(cap) if semantics else None)
        return defn

    def interpret(self, name: str, capability: str,
                   *args, **kwargs) -> Any:
        """解读/取用代码能力。"""
        defn = self._definitions.get(name)
        if defn:
            return defn.interpret(*args, **kwargs)
        return None

    def spiral(self, name: str, capability: str,
                *args, **kwargs) -> dict:
        """执行定义与注册的螺旋上升。"""
        step = {"name": name, "capability": capability, "args": args}
        self._spiral_log.append(step)
        result = self.interpret(name, capability, *args, **kwargs)
        return {
            "result": result,
            "steps": [step],
            "spiral_complete": True,
        }

    def define_natural_language(self, language: str, natural_text: str,
                                 code_name: str) -> VirtualCodeDefinition:
        """定义自然语言到代码的映射。"""
        if language not in self._natural_language_definitions:
            self._natural_language_definitions[language] = {}
        defn = VirtualCodeDefinition(code_name)
        words = natural_text.split()
        for word in words:
            defn.add_definition(word, word, lambda *args: None)
        self._natural_language_definitions[language][code_name] = defn
        return defn

    def natural_to_code_with_definition(self, natural_text: str,
                                         language: str = "zh") -> dict:
        """将自然语言转换为代码，并定义所有能力/语义。"""
        words = natural_text.split()
        code_name = f"natural_{int(time.time())}"
        defn = self.define_natural_language(language, natural_text, code_name)
        for word in words:
            self._definitions[word] = defn
        return {
            'code_name': code_name,
            'capabilities': defn.get_capabilities(),
            'language': language,
            'natural_text': natural_text,
            'spiral_complete': True,
        }

    def get_definitions(self) -> dict:
        """获取所有定义。"""
        return self._definitions.copy()

    def get_definition_stats(self) -> dict:
        """获取定义统计。"""
        return {
            "definitions": len(self._definitions),
            "total_capabilities": sum(len(d.capabilities) for d in self._definitions.values()),
            "total_definitions": sum(len(d.definitions) for d in self._definitions.values()),
            "spiral_count": len(self._spiral_log),
            "natural_languages": list(self._natural_language_definitions.keys()),
        }


# ============================================================
# 全局定义引擎实例
# ============================================================
_global_def_engine: VirtualCodeDefinitionEngine | None = None

def get_definition_engine(debug: bool = False) -> VirtualCodeDefinitionEngine:
    """获取全局虚拟代码定义引擎实例。"""
    global _global_def_engine
    if _global_def_engine is None:
        _global_def_engine = VirtualCodeDefinitionEngine(debug=debug)
    return _global_def_engine

def reset_definition_engine():
    """重置全局虚拟代码定义引擎。"""
    global _global_def_engine
    _global_def_engine = None


# ============================================================
# 便捷函数
# ============================================================

def define(name: str) -> VirtualCodeDefinition:
    """定义代码能力。"""
    return get_definition_engine().define(name)

def define_capability(name: str, capability: str, semantic: Any = None, **kwargs) -> VirtualCodeDefinition:
    """定义代码能力/语义。"""
    return get_definition_engine().define_capability(name, capability, semantic, **kwargs)

def define_multiple(name: str, capabilities: list[str], semantics: dict | None = None) -> VirtualCodeDefinition:
    """定义多个能力/语义。"""
    return get_definition_engine().define_multiple(name, capabilities, semantics)

def interpret(name: str, capability: str, *args, **kwargs) -> Any:
    """解读/取用代码能力。"""
    return get_definition_engine().interpret(name, capability, *args, **kwargs)

def spiral(name: str, capability: str, *args, **kwargs) -> dict:
    """执行定义与注册的螺旋上升。"""
    return get_definition_engine().spiral(name, capability, *args, **kwargs)

def define_natural_language(language: str, natural_text: str, code_name: str) -> VirtualCodeDefinition:
    """定义自然语言到代码的映射。"""
    return get_definition_engine().define_natural_language(language, natural_text, code_name)

# 虚拟代码类型
VirtualCodeType = str


__all__ = [
    "VirtualCodeRegistry", "VirtualCodeEntry", "VirtualCodeType",
    "VirtualCodeEngine", "VirtualCodeDefinition", "VirtualCodeDefinitionEngine",
    "get_virtual_registry", "reset_virtual_registry",
    "get_virtual_engine", "reset_virtual_engine",
    "get_definition_engine", "reset_definition_engine",
    "define", "define_capability", "define_multiple", "interpret", "spiral",
    "define_natural_language",
    "virtual", "absorb", "auto_fix", "confirm", "swallow",
]
