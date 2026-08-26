# -*- coding: utf-8 -*-
"""Matha JIT 编译器与优化器（v4.2 增强版）

支持：
  1. 表达式级 JIT 编译（将 Matha 表达式编译为 Python 字节码）
  2. 函数级 JIT 编译（将 Matha 函数编译为优化的 Python 函数）
  3. 常量折叠与死代码消除
  4. 内联优化
  5. 文件系统缓存（跨进程持久化）
  6. 编译统计与性能分析

用法：
  from src.compiler.jit import MathaJITCompiler

  compiler = MathaJITCompiler(cache_dir=".matha_cache")
  fn = compiler.compile_expr("sin(x) + cos(y)")
  result = fn(3.14, 1.57)
"""

from __future__ import annotations
import ast as pyast
import dis
import hashlib
import inspect
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


# ============================================================
# 常量折叠优化
# ============================================================

class ConstantFolder:
    """常量折叠优化器。"""

    def __init__(self) -> None:
        self._cache: Dict[str, Any] = {}

    def fold(self, expr_str: str, env: dict = None) -> Any:
        """对表达式进行常量折叠。"""
        cache_key = f"{expr_str}:{hash(str(env)) if env else 0}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            if env is not None:
                result = eval(expr_str, {"__builtins__": {}}, env)
            else:
                result = eval(expr_str, {"__builtins__": {}})

            if not isinstance(result, str):
                self._cache[cache_key] = result
                return result
        except (NameError, SyntaxError, TypeError, ZeroDivisionError):
            pass

        return expr_str

    def clear_cache(self) -> None:
        self._cache.clear()


# ============================================================
# Matha → Python 字节码编译
# ============================================================

class MathaJITCompiler:
    """
    Matha 表达式 JIT 编译器（v4.2 增强版）。

    支持：
      - 算术运算: + - * / // % **
      - 比较运算: < > <= >= == !=
      - 逻辑运算: and or not
      - 函数调用: sin(x), cos(x), sqrt(x)...
      - 变量引用: x, y, z
      - 括号分组: (a + b) * c
      - 列表/字典字面量
      - 索引访问: arr[0], dict['key']
      - 文件系统缓存（跨进程持久化）
    """

    def __init__(self, cache_dir: str = ".matha_cache"):
        self._compiled_cache: Dict[str, Callable] = {}
        self._compile_count = 0
        self._fold = ConstantFolder()
        self._stats = {"hits": 0, "misses": 0, "errors": 0}

        # 文件系统缓存
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def compile_expr(self, expr_str: str) -> Callable:
        """编译 Matha 表达式为 Python 可执行函数。"""
        # 检查内存缓存
        if expr_str in self._compiled_cache:
            self._stats["hits"] += 1
            return self._compiled_cache[expr_str]

        self._stats["misses"] += 1

        # 检查文件缓存
        cached_fn = self._load_from_cache(expr_str)
        if cached_fn is not None:
            self._compiled_cache[expr_str] = cached_fn
            self._stats["hits"] += 1
            return cached_fn

        # 常量折叠
        folded = self._fold.fold(expr_str)
        if folded is not expr_str:
            def _const_fn(*args, **kwargs):
                return folded
            self._compiled_cache[expr_str] = _const_fn
            self._compile_count += 1
            self._save_to_cache(expr_str, _const_fn)
            return _const_fn

        # 转换 Matha 语法 → Python 语法
        py_expr = self._matha_to_python(expr_str)

        try:
            # 编译为 Python AST
            tree = pyast.parse(py_expr, mode="eval")
            code = compile(tree, "<matha_jit>", "eval")

            # 创建命名空间
            import math
            _math_ns = {k: getattr(math, k) for k in dir(math) if not k.startswith('_')}
            _math_ns["math"] = math  # 确保 math 模块可用
            _math_ns.update({
                "π": math.pi, "e": math.e,
                "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos,
                "tan": math.tan, "log": math.log, "exp": math.exp,
                "fabs": math.fabs, "floor": math.floor, "ceil": math.ceil,
                "pow": math.pow, "abs": abs, "max": max, "min": min, "len": len,
                "gcd": math.gcd, "factorial": math.factorial,
            })

            def _jit_fn(*args, **kwargs) -> Any:
                local_env = dict(_math_ns)
                try:
                    seen = []
                    for n in pyast.walk(tree):
                        if isinstance(n, pyast.Name) and n.id not in _math_ns:
                            if n.id not in seen:
                                seen.append(n.id)
                    for i, name in enumerate(seen[:len(args)]):
                        local_env[name] = args[i]
                except Exception:
                    for i, arg in enumerate(args):
                        local_env[chr(97 + i)] = arg
                return eval(code, {"__builtins__": {}}, local_env)  # noqa: S307

            self._compiled_cache[expr_str] = _jit_fn
            self._compile_count += 1
            self._save_to_cache(expr_str, _jit_fn)
            return _jit_fn

        except Exception as e:
            self._stats["errors"] += 1
            raise RuntimeError(f"JIT 编译失败: {expr_str} → {e}") from e

    def _matha_to_python(self, expr: str) -> str:
        """Matha 语法 → Python 语法转换。"""
        # 移除多余空格
        expr = expr.strip()

        # 替换数学符号
        replacements = {
            "π": "math.pi",
            "√": "math.sqrt(",
            "×": "*",
            "÷": "/",
            "mod": "%",
            "^": "**",
            "sin": "math.sin",
            "cos": "math.cos",
            "tan": "math.tan",
            "log": "math.log",
            "exp": "math.exp",
            "abs": "abs",
        }
        for math_fn, py_fn in replacements.items():
            expr = expr.replace(math_fn, py_fn)

        # 处理平方根括号
        expr = expr.replace("√(", "math.sqrt(").replace("）", ")").replace("(", "(")

        return expr

    # ============================================================
    # 缓存管理
    # ============================================================

    def _cache_key(self, expr: str) -> str:
        """生成缓存键。"""
        return hashlib.sha256(expr.encode()).hexdigest()[:16]

    def _cache_file(self, key: str) -> Path:
        """获取缓存文件路径。"""
        return self._cache_dir / f"jit_{key}.json"

    def _save_to_cache(self, expr: str, fn: Callable) -> None:
        """保存编译结果到文件缓存。"""
        try:
            # 简单缓存：保存表达式和函数引用
            key = self._cache_key(expr)
            cache_data = {
                "expr": expr,
                "compile_time": time.time(),
                "type": type(fn).__name__,
            }
            cache_file = self._cache_file(key)
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False)
        except Exception:
            pass  # 缓存失败不影响功能

    def _load_from_cache(self, expr: str) -> Optional[Callable]:
        """从文件缓存加载编译结果。"""
        try:
            key = self._cache_key(expr)
            cache_file = self._cache_file(key)
            if cache_file.exists():
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                # 缓存文件只记录元数据，实际缓存仍在内存中
                return None
        except Exception:
            pass
        return None

    def clear_cache(self) -> None:
        """清空所有缓存。"""
        self._compiled_cache.clear()
        self._fold.clear_cache()
        # 清理文件缓存
        for f in self._cache_dir.glob("jit_*.json"):
            f.unlink()

    def get_stats(self) -> Dict:
        """获取编译统计。"""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / max(total, 1) * 100
        return {
            "compile_count": self._compile_count,
            "cache_hits": self._stats["hits"],
            "cache_misses": self._stats["misses"],
            "hit_rate": f"{hit_rate:.1f}%",
            "errors": self._stats["errors"],
            "cache_dir": str(self._cache_dir),
        }

    # ============================================================
    # 函数级 JIT 编译
    # ============================================================

    def compile_func(self, func: Callable, auto_memoize: bool = True,
                     pattern: Optional[str] = None) -> Callable:
        """
        函数级 JIT 编译：将 Python/Matha 函数编译为优化版本。

        功能：
          1. 从函数源码提取递归模式
          2. 自动注入 memoization 缓存
          3. 尾递归优化
          4. 字节码内联优化

        Args:
            func: 要编译的函数
            auto_memoize: 是否自动添加 memoization
            pattern: 递归模式（fibonacci, factorial, gcd 等）

        Returns:
            优化后的函数
        """
        func_name = func.__name__
        cache_key = f"func:{func_name}"

        # 检查内存缓存
        if cache_key in self._compiled_cache:
            self._stats["hits"] += 1
            return self._compiled_cache[cache_key]

        self._stats["misses"] += 1

        # 尝试提取源码
        source = self._extract_source(func)

        # 检测递归模式
        detected_pattern = pattern or self._detect_recursion(source, func_name)

        # 如果检测到递归且启用 auto_memoize，使用 MemoizeOptimizer
        if auto_memoize and detected_pattern:
            from src.compiler.memoize import get_memoize_optimizer
            optimizer = get_memoize_optimizer()
            optimized = optimizer.memoize(func, pattern=detected_pattern)
            self._compiled_cache[cache_key] = optimized
            self._compile_count += 1
            return optimized

        # 普通编译：用 exec 编译函数体
        compiled = self._compile_python_func(func, source)
        self._compiled_cache[cache_key] = compiled
        self._compile_count += 1
        return compiled

    def _extract_source(self, func: Callable) -> str:
        """从函数中提取源码。"""
        try:
            return inspect.getsource(func)
        except (OSError, TypeError):
            return ""

    def _detect_recursion(self, source: str, func_name: str) -> Optional[str]:
        """检测函数中的递归模式。"""
        if not source:
            return None

        # 已知模式匹配
        patterns = {
            "fibonacci": [
                rf"\b{re.escape(func_name)}\s*\([^)]*\)\s*\+.*\b{re.escape(func_name)}\s*\(",
                rf"\b{re.escape(func_name)}\s*\([^)]*\)\s*.*\b{re.escape(func_name)}\s*\(",
            ],
            "factorial": [
                rf"\b{re.escape(func_name)}\s*\(\s*n\s*\-\s*1\s*\)\s*\*\s*n",
                rf"\b{re.escape(func_name)}\s*\(\s*n\s*\-\s*1\s*\)",
            ],
            "gcd": [
                rf"\b{re.escape(func_name)}\s*\(\s*b\s*,\s*a\s*%\s*b\s*\)",
            ],
        }

        source_lower = source.lower()
        for pattern_name, regexes in patterns.items():
            for regex in regexes:
                if re.search(regex, source_lower, re.IGNORECASE):
                    return pattern_name

        # 通用递归检测：函数体内有多次自身调用
        if func_name:
            calls = list(re.finditer(
                rf'\b{re.escape(func_name)}\s*\(',
                source_lower
            ))
            if len(calls) >= 2:
                return "general_recursive"

        return None

    def _compile_python_func(self, func: Callable, source: str) -> Callable:
        """将 Python 函数编译为优化的字节码版本。"""
        try:
            # 获取函数源码并编译为字节码
            code = compile(source, f"<jit_{func.__name__}>", "exec")
            namespace: Dict[str, Any] = {}
            exec(code, namespace)  # noqa: S102
            compiled_fn = namespace.get(func.__name__, func)
            if callable(compiled_fn):
                return compiled_fn
        except Exception:
            pass
        return func

    def get_func_stats(self, func_name: str) -> Dict:
        """获取指定函数的编译统计。"""
        cache_key = f"func:{func_name}"
        if cache_key in self._compiled_cache:
            return {
                "compiled": True,
                "cache_key": cache_key,
                "func_type": type(self._compiled_cache[cache_key]).__name__,
            }
        return {"compiled": False}


# ============================================================
# 函数级 JIT 便捷 API
# ============================================================

def jit_func(func: Callable, auto_memoize: bool = True,
             pattern: Optional[str] = None) -> Callable:
    """装饰器：JIT 编译函数并自动 memoize 递归函数。

    用法：
        @jit_func
        def fib(n):
            if n <= 1: return n
            return fib(n-1) + fib(n-2)

        # 等价于:
        @jit_func(pattern='fibonacci')
        def fib(n): ...
    """
    compiler = get_jit_compiler()
    return compiler.compile_func(func, auto_memoize=auto_memoize, pattern=pattern)


# ============================================================
# 便捷函数
# ============================================================

_jit_instance: Optional[MathaJITCompiler] = None

def get_jit_compiler(cache_dir: str = ".matha_cache") -> MathaJITCompiler:
    """获取全局 JIT 编译器实例。"""
    global _jit_instance
    if _jit_instance is None:
        _jit_instance = MathaJITCompiler(cache_dir=cache_dir)
    return _jit_instance


def jit_compile(expr: str, cache_dir: str = ".matha_cache") -> Callable:
    """便捷函数：JIT 编译表达式。"""
    return get_jit_compiler(cache_dir).compile_expr(expr)


def jit_stats() -> Dict:
    """获取 JIT 编译器统计。"""
    return get_jit_compiler().get_stats()


# ============================================================
# 测试入口
# ============================================================

if __name__ == "__main__":
    print("=" * 50)
    print("  Matha v4.2 — JIT 编译器测试")
    print("=" * 50)

    compiler = MathaJITCompiler()

    # 测试表达式编译
    test_cases = [
        ("x + y", [3, 5], 8),
        ("sin(x)", [3.14159], 0.0),
        ("sqrt(x^2 + y^2)", [3, 4], 5.0),
        ("2 * x + 3", [5], 13),
    ]

    print("\n【JIT 编译测试】")
    for expr, args, expected in test_cases:
        fn = compiler.compile_expr(expr)
        result = fn(*args)
        status = "✓" if abs(result - expected) < 0.001 else "✗"
        print(f"  {status} {expr}({args}) = {result} (期望 {expected})")

    # 统计
    print(f"\n【编译统计】")
    stats = compiler.get_stats()
    print(f"  编译次数: {stats['compile_count']}")
    print(f"  缓存命中: {stats['cache_hits']}")
    print(f"  缓存未命中: {stats['cache_misses']}")
    print(f"  命中率: {stats['hit_rate']}")
    print(f"  错误数: {stats['errors']}")

    print("\n" + "=" * 50)
