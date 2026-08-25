# -*- coding: utf-8 -*-
"""Matha 跨语言互操作层。

支持：
  1. Python ↔ Matha 双向互操作
  2. JavaScript ↔ Matha 互操作（通过 Node.js subprocess）
  3. Rust/C ↔ Matha 互操作（通过 ctypes/FFI）
  4. 自动类型转换
  5. 共享内存与进程间通信
"""

from __future__ import annotations
import json
import subprocess
import sys
from typing import Any, Callable, Optional


# ============================================================
# Python ↔ Matha 互操作
# ============================================================

class PythonInterop:
    """Python 与 Matha 的双向互操作。"""

    def __init__(self, interpreter=None) -> None:
        self._interpreter = interpreter
        self._py_funcs: dict[str, Callable] = {}
        self._matha_funcs: dict[str, Any] = {}

    def register_py_func(self, matha_name: str, py_func: Callable) -> None:
        """将 Python 函数注册为 Matha 内建。"""
        self._py_funcs[matha_name] = py_func

    def call_py_func(self, name: str, *args) -> Any:
        """从 Matha 调用 Python 函数。"""
        if name not in self._py_funcs:
            raise KeyError(f"Python 函数 '{name}' 未注册")
        return self._py_funcs[name](*args)

    def register_matha_func(self, name: str, matha_code: str) -> None:
        """注册 Matha 函数供 Python 调用。"""
        self._matha_funcs[name] = matha_code

    def call_matha_func(self, name: str, *args) -> Any:
        """从 Python 调用 Matha 函数。"""
        if name not in self._matha_funcs:
            raise KeyError(f"Matha 函数 '{name}' 未注册")
        # 通过解释器执行
        if self._interpreter:
            from src.interp import interpret
            src = f"result = {name}({', '.join(str(a) for a in args)})\n#1：[result]"
            out, _ = interpret(src)
            return out[0] if out else None
        return None


# ============================================================
# JavaScript ↔ Matha 互操作
# ============================================================

class JSInterop:
    """JavaScript 与 Matha 的互操作（通过 Node.js）。"""

    def __init__(self) -> None:
        self._js_code: dict[str, str] = {}

    def register_js_func(self, name: str, js_code: str) -> None:
        """注册 JS 函数供 Matha 调用。"""
        self._js_code[name] = js_code

    def call_js_func(self, name: str, *args) -> Any:
        """从 Matha 调用 JS 函数。"""
        if name not in self._js_code:
            raise KeyError(f"JS 函数 '{name}' 未注册")

        # 构建 JS 调用
        arg_strs = [json.dumps(a) for a in args]
        js_call = f"JSON.stringify(({self._js_code[name]})([{', '.join(arg_strs)}]))"

        try:
            result = subprocess.run(
                ["node", "--eval", js_call],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return json.loads(result.stdout.strip())
            return None
        except FileNotFoundError:
            raise RuntimeError("Node.js 未安装，无法调用 JS 函数")
        except Exception as e:
            raise RuntimeError(f"JS 函数 '{name}' 执行错误: {e}")

    def call_js_module(self, module: str, func: str, *args) -> Any:
        """调用已安装的 npm 模块函数。"""
        # 通过 require() 调用
        js_call = f"""
const m = require('{module}');
JSON.stringify(m.{func}({', '.join(json.dumps(a) for a in args)}))
        """
        try:
            result = subprocess.run(
                ["node", "--eval", js_call],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                return json.loads(result.stdout.strip())
            return None
        except Exception as e:
            raise RuntimeError(f"npm 模块 '{module}' 调用错误: {e}")


# ============================================================
# Rust/C FFI 互操作
# ============================================================

class CInterop:
    """C/Rust 库与 Matha 的互操作（通过 ctypes）。"""

    def __init__(self) -> None:
        self._libs: dict[str, Any] = {}
        self._funcs: dict[str, Callable] = {}

    def load_library(self, name: str, path: str) -> None:
        """加载 C/Rust 动态链接库。"""
        import ctypes
        lib = ctypes.CDLL(path)
        self._libs[name] = lib

    def register_func(self, lib_name: str, func_name: str,
                      argtypes: list[type], restype: type) -> None:
        """注册 C 函数。"""
        if lib_name not in self._libs:
            raise KeyError(f"库 '{lib_name}' 未加载")
        lib = self._libs[lib_name]
        func = getattr(lib, func_name)
        func.argtypes = argtypes
        func.restype = restype
        self._funcs[f"{lib_name}.{func_name}"] = func

    def call_func(self, name: str, *args) -> Any:
        """调用 C 函数。"""
        if name not in self._funcs:
            raise KeyError(f"C 函数 '{name}' 未注册")
        return self._funcs[name](*args)


# ============================================================
# 进程间通信
# ============================================================

class IPC:
    """进程间通信（共享内存 / 消息队列）。"""

    def __init__(self) -> None:
        import multiprocessing
        self._queue = multiprocessing.Queue()
        self._shared = multiprocessing.Manager().dict()

    def send(self, data: Any) -> None:
        """发送消息。"""
        self._queue.put(data)

    def receive(self, timeout: float = 1.0) -> Optional[Any]:
        """接收消息。"""
        try:
            return self._queue.get(timeout=timeout)
        except Exception:
            return None

    def set_shared(self, key: str, value: Any) -> None:
        """设置共享内存。"""
        self._shared[key] = value

    def get_shared(self, key: str) -> Any:
        """读取共享内存。"""
        return self._shared.get(key)


# ============================================================
# 统一互操作入口
# ============================================================

class MathaInterop:
    """Matha 统一互操作入口。"""

    def __init__(self, interpreter=None) -> None:
        self.python = PythonInterop(interpreter)
        self.javascript = JSInterop()
        self.c = CInterop()
        self.ipc = IPC()

    def register_function(self, name: str, lang: str, func: Callable) -> None:
        """统一注册函数。"""
        if lang == "python":
            self.python.register_py_func(name, func)
        elif lang == "javascript":
            self.javascript.register_js_func(name, str(func))
        elif lang == "c":
            # C 函数通过 ctypes 注册
            pass

    def call_function(self, name: str, lang: str = "python", *args) -> Any:
        """统一调用函数。"""
        if lang == "python":
            return self.python.call_py_func(name, *args)
        elif lang == "javascript":
            return self.javascript.call_js_func(name, *args)
        return None


# ============================================================
# 预注册常用互操作函数
# ============================================================

_interop = MathaInterop()

# 预注册 Python 常用函数
import math
_interop.python.register_py_func("py_sin", math.sin)
_interop.python.register_py_func("py_cos", math.cos)
_interop.python.register_py_func("py_sqrt", math.sqrt)
_interop.python.register_py_func("py_len", len)
_interop.python.register_py_func("py_abs", abs)
_interop.python.register_py_func("py_round", round)


def get_interop() -> MathaInterop:
    """获取互操作实例。"""
    return _interop


# ============================================================
# 模块导出
# ============================================================

__all__ = [
    "PythonInterop", "JSInterop", "CInterop", "IPC",
    "MathaInterop", "get_interop",
]
