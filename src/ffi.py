# -*- coding: utf-8 -*-
"""
Matha FFI 层 v1.3.0
====================
外部函数接口（Foreign Function Interface）— 桥接 Matha 与 Python/其他语言。

功能：
  • register_func    — 注册 Python 函数到 Matha 符号系统
  • call_external    — 从 Matha 调用外部函数
  • import_py_module — 导入 Python 模块作为 Matha 库
  • import_math_func — 导入数学函数
  • FFI Bridge       — 跨语言调用协议
  • 动态函数注册表
"""
from __future__ import annotations
import sys
import os
import logging
import threading
import importlib
import inspect
from dataclasses import dataclass, field
from typing import Optional, Any, Callable, Dict, List, Tuple

logger = logging.getLogger("matha.ffi")

# ═══════════════════════════════════════════════════════════════════════════════
#  FFI 调用协议
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class FFIImport:
    """FFI 导入描述。"""
    name: str
    source: str           # "python" / "math" / "numpy" / "module"
    target_name: str = ""  # 导入后在 Matha 中的名称
    params: List[str] = field(default_factory=list)
    doc: str = ""


@dataclass
class FFICall:
    """FFI 调用记录。"""
    func_name: str
    args: List[Any]
    result: Any = None
    latency_ms: float = 0.0
    success: bool = True
    error: str = ""


class MathaFFIBridge:
    """
    Matha 外部函数接口桥接器。

    支持：
      1. Python 函数注册 → Matha 内建函数
      2. Python 模块导入 → Matha 命名空间
      3. 跨语言调用协议（通过 FFI 描述符）
      4. 动态函数注册/注销
      5. 调用链日志和性能追踪
    """

    def __init__(self):
        self._registry: Dict[str, Callable] = {}
        self._imports: Dict[str, FFIImport] = {}
        self._call_log: List[FFICall] = []
        self._max_log = 1000
        self._lock = threading.Lock()  # 线程安全锁

        # 预注册常用数学函数
        self._register_math_builtins()
        logger.info("  [FFI] 桥接器初始化完成")

    def _register_math_builtins(self):
        """注册数学内建函数。"""
        import math
        math_funcs = {
            'sqrt': math.sqrt, 'sin': math.sin, 'cos': math.cos,
            'tan': math.tan, 'asin': math.asin, 'acos': math.acos,
            'atan': math.atan, 'atan2': math.atan2, 'exp': math.exp,
            'log': math.log, 'log2': math.log2, 'log10': math.log10,
            'abs': abs, 'floor': math.floor, 'ceil': math.ceil,
            'pow': math.pow, 'fmod': math.fmod, 'factorial': math.factorial,
            'gcd': math.gcd, 'hypot': math.hypot,
            'sinhl': math.sinh, 'cosh': math.cosh, 'tanh': math.tanh,
            'deg': math.degrees, 'rad': math.radians,
            'pi': math.pi, 'e': math.e,
        }
        for name, func in math_funcs.items():
            self._registry[name] = func
        logger.info(f"  [FFI] 注册 {len(math_funcs)} 个数学内建函数")

    # ── 注册接口 ──────────────────────────────────────────────────────────────

    def register(self, name: str, func: Callable, params: List[str] = None, doc: str = ""):
        """注册 Python 函数到 Matha FFI。"""
        with self._lock:
            self._registry[name] = func
            self._imports[name] = FFIImport(
                name=name, source="python", target_name=name,
                params=params or [], doc=doc
            )
        logger.info(f"  [FFI] 注册函数: {name} → {func.__name__} (params={params})")
        return self

    def unregister(self, name: str):
        """注销 Matha 函数。"""
        with self._lock:
            if name in self._registry:
                del self._registry[name]
            if name in self._imports:
                del self._imports[name]
        logger.info(f"  [FFI] 注销函数: {name}")
        return self

    def import_module(self, module_name: str, alias: str = None,
                      exclude: List[str] = None, include: List[str] = None):
        """导入 Python 模块到 Matha 命名空间。"""
        mod = importlib.import_module(module_name)
        exclude = set(exclude or [])
        include = set(include or [])
        count = 0
        for attr_name in dir(mod):
            if attr_name.startswith('_'):
                continue
            if exclude and attr_name in exclude:
                continue
            if include and attr_name not in include:
                continue
            attr = getattr(mod, attr_name)
            if callable(attr) and not isinstance(attr, type):
                target = f"{alias}.{attr_name}" if alias else attr_name
                self._registry[target] = attr
                self._imports[target] = FFIImport(
                    name=attr_name, source=module_name,
                    target_name=target, doc=getattr(attr, '__doc__', '')
                )
                count += 1
                logger.info(f"  [FFI] 导入模块函数: {module_name}.{attr_name} → {target}")
        logger.info(f"  [FFI] 模块 {module_name} 导入完成: {count} 个函数")
        return self

    def import_numpy(self):
        """导入 NumPy 作为 'np' 命名空间。"""
        try:
            import numpy as np
            for attr_name in dir(np):
                if attr_name.startswith('_') or attr_name in (' ndarray', 'dtype'):
                    continue
                attr = getattr(np, attr_name)
                if callable(attr):
                    target = f"np.{attr_name}"
                    self._registry[target] = attr
                    self._imports[target] = FFIImport(
                        name=attr_name, source="numpy",
                        target_name=target, doc=getattr(attr, '__doc__', '')
                    )
            logger.info("  [FFI] NumPy 导入完成")
        except ImportError:
            logger.warning("  [FFI] NumPy 未安装，跳过")
        return self

    # ── 调用接口 ──────────────────────────────────────────────────────────────

    def call(self, name: str, *args) -> Any:
        """调用已注册的 FFI 函数。"""
        import time
        start = time.time()
        call_record = FFICall(func_name=name, args=list(args))
        try:
            func = self._registry.get(name)
            if func is None:
                # 尝试从命名空间解析
                func = self._resolve(name)
            if func is None:
                call_record.error = f"未找到函数: {name}"
                call_record.success = False
            else:
                result = func(*args)
                call_record.result = result
                call_record.success = True
                logger.debug(f"  [FFI] {name}({args}) → {result}")
        except Exception as e:
            call_record.error = str(e)
            call_record.success = False
            logger.error(f"  [FFI] {name}({args}) 异常: {e}")

        call_record.latency_ms = (time.time() - start) * 1000
        self._call_log.append(call_record)
        if len(self._call_log) > self._max_log:
            self._call_log = self._call_log[-self._max_log:]
        return call_record.result if call_record.success else None

    def _resolve(self, name: str) -> Optional[Callable]:
        """解析函数名（支持嵌套命名空间如 np.sin）。"""
        if '.' in name:
            parts = name.split('.')
            base = self._registry.get(parts[0])
            if base and hasattr(base, parts[1]):
                return getattr(base, parts[1])
        return self._registry.get(name)

    def get_function(self, name: str) -> Optional[Callable]:
        """获取已注册函数。"""
        with self._lock:
            return self._resolve(name) or self._registry.get(name)

    def is_registered(self, name: str) -> bool:
        """检查函数是否已注册。"""
        with self._lock:
            return name in self._registry or self._resolve(name) is not None

    # ── 查询接口 ──────────────────────────────────────────────────────────────

    def list_functions(self, source: str = None) -> List[dict]:
        """列出所有注册函数。"""
        with self._lock:
            items = list(self._imports.items())
        result = []
        for name, imp in items:
            if source and imp.source != source:
                continue
            result.append({
                "name": name, "source": imp.source,
                "params": imp.params, "doc": imp.doc[:80] if imp.doc else ""
            })
        return result

    def get_stats(self) -> dict:
        """获取 FFI 调用统计。"""
        total = len(self._call_log)
        errors = sum(1 for c in self._call_log if not c.success)
        total_latency = sum(c.latency_ms for c in self._call_log)
        return {
            "registered_functions": len(self._registry),
            "total_calls": total,
            "error_count": errors,
            "error_rate": errors / max(total, 1),
            "avg_latency_ms": total_latency / max(total, 1),
            "imports": len(self._imports),
        }

    def clear_log(self):
        """清空调用日志。"""
        self._call_log.clear()


# ═══════════════════════════════════════════════════════════════════════════════
#  单例
# ═══════════════════════════════════════════════════════════════════════════════

_ffi_instance: Optional[MathaFFIBridge] = None


def get_ffi() -> MathaFFIBridge:
    """获取 FFI 桥接器单例。"""
    global _ffi_instance
    if _ffi_instance is None:
        _ffi_instance = MathaFFIBridge()
    return _ffi_instance


def ffi_register(name: str, func: Callable, **kwargs):
    """便捷注册函数。"""
    return get_ffi().register(name, func, **kwargs)


def ffi_call(name: str, *args) -> Any:
    """便捷调用函数。"""
    return get_ffi().call(name, *args)


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  Matha FFI 层 v1.3.0")
    print("=" * 60)

    ffi = get_ffi()
    print(f"\n[FFI 统计]")
    print(f"  注册函数: {ffi.get_stats()['registered_functions']}")

    # 注册自定义函数
    def my_add(a, b): return a + b
    ffi.register("my_add", my_add, params=["a", "b"], doc="自定义加法")

    # 调用
    result = ffi.call("my_add", 3, 4)
    print(f"  my_add(3,4) = {result}")

    # 调用数学函数
    result = ffi.call("sqrt", 16)
    print(f"  sqrt(16) = {result}")

    result = ffi.call("sin", 3.14159/2)
    print(f"  sin(π/2) = {result}")

    print("\n完成。")
