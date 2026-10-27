"""Matha 内核（kernel）—— 核心主线的零外部依赖运行基座。

核心主线为：
    src.lexer -> src.parser -> src.ast_nodes -> src.mbc.compiler -> src.mbc.vm
                                                          \\-> src.mbc.native

本包承载「不属于任何领域、却必须存在于语言里」的能力：内建符号注册、
执行门面、以及后续从 stdlib 下沉的纯算子实现。

红线（由 tests/test_kernel_purity.py + scripts/dep_audit.py 机器强制）：
  1. 不得 import 任何 ``src.domains.*``（领域层是插件，须经 src.plugin_api 按需加载）。
  2. 不得 import 第三方库（sympy / numpy / scipy / numba / tree_sitter ...）。
  3. 不得使用逃逸模块（启进程 / 线程 / 并行 / 共享内存 / FFI 直调等，
     即 threading、concurrent、multiprocessing、ctypes 一类的宿主交互能力）。
  4. 不得调用 exec / eval / compile / __import__（禁止借宿主解释器执行代码）。

包内的注册函数一律采用函数体内 import，使 ``import src.kernel`` 本身保持零成本，
只有真正取用内建符号时才加载对应实现。

子包 ``src.kernel.symbolic``（阶段 3 下沉）为符号微积分基座：纯标准库的
Expr 代数层 + 求导 / 积分 / 极限 / 级数 / ODE / 定义域 / LaTeX 发射，
不依赖任何第三方计算机代数系统。
"""
from __future__ import annotations


def register_kernel_builtins(builtins: dict[str, object] | None = None) -> dict[str, object]:
    """把内核级内建符号注册进给定字典，返回该字典。

    内核内建 = 数学函数 + 单位换算 + 正则 + 时间 + 文件。五者均为纯标准库实现，
    是语言可运行最小集；领域符号不在此列，须经 src.plugin_api 按需加载。

    注意：VM 侧 src.mbc.vm._default_builtins() 只取 math / regex / time / file，
    不含 `_register_unit_builtins`；两者内建符号集合有意不同，不可互相替换，
    否则单位换算符号会进入 VM 而改变既有语义与 VM↔native 对拍基线。
    """
    if builtins is None:
        builtins = {}
    from src.kernel.math_builtin import _register_math_builtins, _register_unit_builtins
    from src.kernel.regex_builtin import _register_regex_builtins
    from src.kernel.file_builtin import _register_file
    from src.kernel.time_builtin import _register_time

    _register_math_builtins(builtins)
    _register_unit_builtins(builtins)
    _register_regex_builtins(builtins)
    _register_time(builtins)
    _register_file(builtins)
    return builtins


def kernel_builtin_names() -> list[str]:
    """内核内建符号名清单（供语义分析、LSP 补全、插件冲突检查使用）。"""
    return sorted(register_kernel_builtins({}).keys())


__all__ = ["register_kernel_builtins", "kernel_builtin_names"]
