# -*- coding: utf-8 -*-
"""Matha v4.0 — 语言适配器层

设计原则：
  1. Matha 代码 → 目标语言代码（翻译）
  2. 目标语言代码 → 可执行（编译/解释）
  3. 执行结果 → 返回给 Matha 运行时

架构：
  Matha IR → LanguageAdapter → 目标语言 → 执行 → 结果
"""
from __future__ import annotations
import abc
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Optional


# ============================================================
# 适配器基类
# ============================================================

@dataclass
class AdaptResult:
    """适配结果。"""
    success: bool
    target_code: str = ""
    executable: Optional[Any] = None
    output: Any = None
    error: str = ""
    compile_time_ms: float = 0.0
    exec_time_ms: float = 0.0


class LanguageAdapter(abc.ABC):
    """语言适配器基类。"""

    def __init__(self, name: str, ext: str = ".py"):
        self.name = name
        self.ext = ext
        self._cache: Dict[str, Any] = {}
        self._cache_dir = Path(".matha_cache") / name
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    @abc.abstractmethod
    def adapt(self, matha_ir: str) -> AdaptResult:
        """将 Matha IR 适配为目标语言并执行。"""
        pass

    @abc.abstractmethod
    def translate(self, matha_ir: str) -> str:
        """Matha IR → 目标语言代码。"""
        pass

    def _cache_key(self, code: str) -> str:
        """生成缓存键。"""
        return hashlib.sha256(code.encode()).hexdigest()[:16]

    def _get_cached(self, key: str) -> Optional[Any]:
        """获取缓存的执行结果。"""
        cache_file = self._cache_dir / f"{key}.json"
        if cache_file.exists():
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None

    def _save_cache(self, key: str, result: Any):
        """保存执行结果到缓存。"""
        cache_file = self._cache_dir / f"{key}.json"
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False)


# ============================================================
# Python 适配器
# ============================================================

class PythonAdapter(LanguageAdapter):
    """
    Python 适配器。

    Matha IR → Python 代码 → exec() 执行
    """

    def __init__(self):
        super().__init__("python", ".py")

    def adapt(self, matha_ir: str) -> AdaptResult:
        """适配并执行 Python 代码。"""
        import time
        start = time.perf_counter()

        # 1. 翻译
        python_code = self.translate(matha_ir)

        # 2. 缓存检查
        cache_key = self._cache_key(python_code)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return AdaptResult(
                success=True,
                target_code=python_code,
                output=cached['output'],
                exec_time_ms=0.0,
            )

        # 3. 执行
        try:
            local_vars = {}
            exec(python_code, {"__builtins__": __builtins__}, local_vars)
            output = local_vars.get('result', local_vars.get('output'))
        except Exception as e:
            return AdaptResult(
                success=False,
                target_code=python_code,
                error=str(e),
            )

        # 4. 缓存
        self._save_cache(cache_key, {'output': output})

        exec_time = (time.perf_counter() - start) * 1000

        return AdaptResult(
            success=True,
            target_code=python_code,
            output=output,
            exec_time_ms=exec_time,
        )

    def translate(self, matha_ir: str) -> str:
        """Matha IR → Python 代码。"""
        # 简单的数学翻译
        python_code = matha_ir

        # 替换数学函数
        replacements = {
            'sin': 'math.sin',
            'cos': 'math.cos',
            'tan': 'math.tan',
            'sqrt': 'math.sqrt',
            'log': 'math.log',
            'abs': 'abs',
            'pow': 'pow',
            'sorted': 'sorted',
            'sum': 'sum',
            'len': 'len',
        }
        for math_fn, py_fn in replacements.items():
            python_code = python_code.replace(f"{math_fn}(", f"{py_fn}(")

        # 添加 imports
        if any(fn in python_code for fn in ['sin', 'cos', 'tan', 'sqrt', 'log']):
            python_code = "import math\n" + python_code

        # 确保有 result 变量
        if 'result' not in python_code:
            python_code += "\nresult = None"

        return python_code


# ============================================================
# Rust 适配器
# ============================================================

class RustAdapter(LanguageAdapter):
    """
    Rust 适配器。

    Matha IR → Rust 代码 → rustc 编译 → 可执行文件
    """

    def __init__(self, optimize: bool = True):
        super().__init__("rust", ".rs")
        self.optimize = optimize

    def adapt(self, matha_ir: str) -> AdaptResult:
        """适配并执行 Rust 代码。"""
        import time
        start = time.perf_counter()

        # 1. 翻译
        rust_code = self.translate(matha_ir)

        # 2. 缓存检查
        cache_key = self._cache_key(rust_code)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return AdaptResult(
                success=True,
                target_code=rust_code,
                output=cached['output'],
                exec_time_ms=0.0,
            )

        # 3. 编译
        try:
            exe_path = self._compile(rust_code, cache_key)
            if not exe_path:
                return AdaptResult(success=False, error="Rust 编译失败")
        except Exception as e:
            return AdaptResult(success=False, error=f"Rust 编译失败: {e}")

        # 4. 执行
        try:
            result = subprocess.run(
                [exe_path],
                capture_output=True,
                text=True,
                timeout=10,
            )
            output = result.stdout.strip()
            if result.returncode != 0:
                return AdaptResult(
                    success=False,
                    target_code=rust_code,
                    error=result.stderr,
                )
        except Exception as e:
            return AdaptResult(success=False, error=f"Rust 执行失败: {e}")

        # 5. 缓存
        self._save_cache(cache_key, {'output': output})

        exec_time = (time.perf_counter() - start) * 1000

        return AdaptResult(
            success=True,
            target_code=rust_code,
            output=output,
            exec_time_ms=exec_time,
        )

    def translate(self, matha_ir: str) -> str:
        """Matha IR → Rust 代码。"""
        # 提取数学表达式
        expr = matha_ir

        # 替换数学函数为 Rust 语法
        rust_replacements = {
            'sin': 'f64::sin',
            'cos': 'f64::cos',
            'tan': 'f64::tan',
            'sqrt': 'f64::sqrt',
            'log': 'f64::ln',
            'pow': 'f64::powf',
            'sorted': '.sort()',
            'sum': '.iter().sum()',
        }
        for math_fn, rust_fn in rust_replacements.items():
            expr = expr.replace(f"{math_fn}(", f"{rust_fn}(")

        # 生成完整 Rust 程序
        rust_code = f'''fn main() {{
    let result = {expr};
    println!("{{:.6}}", result);
}}
'''
        return rust_code

    def _compile(self, rust_code: str, cache_key: str) -> Optional[str]:
        """编译 Rust 代码。"""
        src_file = self._cache_dir / f"{cache_key}.rs"
        exe_file = self._cache_dir / f"{cache_key}"

        # 写入源码
        with open(src_file, 'w', encoding='utf-8') as f:
            f.write(rust_code)

        # 编译
        flags = ['-O'] if self.optimize else []
        result = subprocess.run(
            ['rustc', str(src_file), '-o', str(exe_file)] + flags,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return None

        return str(exe_file)


# ============================================================
# 语言适配器注册表
# ============================================================

class LanguageAdapterRegistry:
    """语言适配器注册表。"""

    _adapters: Dict[str, LanguageAdapter] = {}

    @classmethod
    def register(cls, name: str, adapter: LanguageAdapter):
        """注册语言适配器。"""
        cls._adapters[name] = adapter

    @classmethod
    def get(cls, name: str) -> Optional[LanguageAdapter]:
        """获取语言适配器。"""
        return cls._adapters.get(name)

    @classmethod
    def list_adapters(cls) -> List[str]:
        """列出所有已注册的适配器。"""
        return list(cls._adapters.keys())


# 自动注册内置适配器
LanguageAdapterRegistry.register("python", PythonAdapter())
LanguageAdapterRegistry.register("rust", RustAdapter())


# ============================================================
# 测试入口
# ============================================================

if __name__ == "__main__":
    import sys
    sys.path.insert(0, r"D:\trae")
    from src.adapters.language_adapters import LanguageAdapterRegistry

    registry = LanguageAdapterRegistry()

    test_cases = [
        "result = 3.0 + 5.0 * 2.0",
        "result = sqrt(16.0) + sin(3.14/2.0)",
        "primes = [p for p in range(2, 100) if all(p%d!=0 for d in range(2, int(p**0.5)+1))]",
        "result = sorted([3.0, 1.0, 2.0])",
    ]

    print("=" * 70)
    print("  Matha v4.0 — 语言适配器层测试")
    print("=" * 70)

    for code in test_cases:
        print(f"\n输入 Matha IR: {code!r}")
        print("-" * 50)

        # Python 适配
        py_adapter = registry.get("python")
        py_result = py_adapter.adapt(code)
        print(f"[Python] 成功: {py_result.success}")
        print(f"         输出: {py_result.output}")
        print(f"         耗时: {py_result.exec_time_ms:.1f}ms")

        # Rust 适配
        rust_adapter = registry.get("rust")
        rust_result = rust_adapter.adapt(code)
        print(f"[Rust]   成功: {rust_result.success}")
        print(f"         输出: {rust_result.output}")
        print(f"         耗时: {rust_result.exec_time_ms:.1f}ms")

    print("\n" + "=" * 70)
    print("  测试完成")
    print("=" * 70)
