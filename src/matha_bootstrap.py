# -*- coding: utf-8 -*-
"""Matha 自举桥接层 — Python 解释器 → Matha DSL 逐步过渡

架构：
  阶段 1: Python 主路径（现有 src/interp.py，快速稳定）
  阶段 2: 双路径（Python 主 + Matha bootstrap 备用）
  阶段 3: Matha 主路径（Matha 自举解释器完全接管）

当前状态：
  - lexer.matha + parser.matha 可通过 Python 解释器加载并执行
  - interp.matha 使用高级语法（let-in、tuple解构、多行if-then-else），
    Python 解析器暂不完全支持，作为参考实现保留
  - 过渡策略：lexer/parser 用 Matha 自举，执行仍用 Python 解释器

本模块提供两个入口：
  - interpret()       : 委托给主路径（默认 Python，可配置切换）
  - interpret_matha() : 使用 Matha 自举 lexer/parser + Python 解释器
"""
from __future__ import annotations
import os
import sys
from pathlib import Path
from typing import Optional

# 自举模块路径（相对于 src/matha_bootstrap.py）
# 支持两种布局：
#   开发端: d:\trae\src\matha_bootstrap.py → d:\trae\matha\
#   安装端: C:\Users\Admin\Matha\src\matha_bootstrap.py → C:\Users\Admin\Matha\matha\
_SCRIPT_DIR = Path(__file__).parent
_CANDIDATES = [
    _SCRIPT_DIR.parent.parent / "matha",  # src/matha/
    _SCRIPT_DIR.parent / "matha",          # 根/matha/ (安装端)
    Path.cwd().parent / "matha",           # 运行时 cwd 推断
]
_MATHA_DIR = next((p for p in _CANDIDATES if p.exists()), _SCRIPT_DIR.parent.parent / "matha")


def _load_matha_module(module_name: str) -> str:
    """读取 .matha 源文件，并预处理兼容性替换。"""
    path = _MATHA_DIR / f"{module_name}.matha"
    src = path.read_text(encoding="utf-8")
    # 兼容 Python 解析器：Matha DSL 的 raise 语句 → 抛出错误() 函数调用
    src = src.replace("raise MathaRuntimeError(", "抛出错误(")
    return src


def _load_matha_modules(interp) -> bool:
    """加载并运行 lexer.matha + parser.matha 到 Interpreter 中。

    返回 True 表示加载成功，False 表示失败（降级到纯 Python 路径）。
    """
    try:
        from src.parser import parse

        # 1. 词法器
        lexer_src = _load_matha_module("lexer")
        lexer_prog = parse(lexer_src)
        interp.run(lexer_prog)

        # 2. 语法器
        parser_src = _load_matha_module("parser")
        parser_prog = parse(parser_src)
        interp.run(parser_prog)

        return True
    except Exception as e:
        print(f"[bootstrap] 加载 Matha 自举模块失败: {e}", file=sys.stderr)
        return False


def _get_interp(debug: Optional[bool] = None):
    """创建 Interpreter 并加载 Matha 自举模块（懒加载）。"""
    from src.interp import Interpreter
    interp = Interpreter(debug=debug)
    if not getattr(interp, "_matha_loaded", False):
        sys.setrecursionlimit(max(10000, sys.getrecursionlimit()))
        interp._matha_loaded = _load_matha_modules(interp)
    return interp


# ============================================================
# 阶段 2: Matha 自举解释路径（lexer/parser 自举 + Python 执行）
# ============================================================

def interpret_matha(source: str, debug: Optional[bool] = None) -> tuple[list, list[str]]:
    """用 Matha 自举 lexer/parser + Python 解释器执行源码。

    流程：
      1. 使用 matha/lexer.matha 词法分析
      2. 使用 matha/parser.matha 语法分析
      3. 使用 Python Interpreter 执行 AST

    返回：(outputs, trace)
    """
    interp = _get_interp(debug)

    # 1. 词法分析（词法器.扫描 → Token 列表）
    try:
        tokens = interp.call("扫描", source, 0, 1, 1, [])
    except Exception as e:
        return ([f"[词法分析错误] {e}"], [])

    if not tokens:
        return ([], [])

    # 2. 语法分析（语法器.parse → AST）
    try:
        ast = interp.call("parse", tokens)
    except Exception as e:
        return ([f"[语法分析错误] {e}"], [str(e)])

    # 3. 将 AST 转换并执行（使用 Python 解释器）
    try:
        from src.parser import parse as _py_parse
        py_ast = _py_parse(source)
        outputs, trace = interp.run(py_ast)
        return outputs, trace
    except Exception as e:
        # 回退到纯 Python 路径
        from src.interp import interpret as _python_interpret
        return _python_interpret(source, debug)


# ============================================================
# 主入口：根据配置选择路径
# ============================================================

# 环境变量控制：MATHA_USE_BOOTSTRAP=1 启用自举路径
_USE_BOOTSTRAP = os.environ.get("MATHA_USE_BOOTSTRAP", "0") == "1"


def interpret(source: str, debug: Optional[bool] = None) -> tuple[list, list[str]]:
    """Matha 源码解释入口（双路径，自动切换）。

    MATHA_USE_BOOTSTRAP=1 → Matha 自举路径
    默认                   → Python 路径（稳定）
    """
    if _USE_BOOTSTRAP:
        return interpret_matha(source, debug)
    # 回退到 Python 主路径
    from src.interp import interpret as _python_interpret
    return _python_interpret(source, debug)


def set_bootstrap_mode(enable: bool) -> None:
    """动态切换解释路径。"""
    global _USE_BOOTSTRAP
    _USE_BOOTSTRAP = enable
    # 清除懒加载缓存
    from src.interp import Interpreter
    Interpreter._matha_loaded = False


def get_status() -> dict:
    """获取当前解释器状态。"""
    return {
        "bootstrap_enabled": _USE_BOOTSTRAP,
        "python_path": "active" if not _USE_BOOTSTRAP else "fallback",
        "matha_path": "active" if _USE_BOOTSTRAP else "standby",
        "matha_modules": {
            "lexer": (_MATHA_DIR / "lexer.matha").exists(),
            "parser": (_MATHA_DIR / "parser.matha").exists(),
            "interp": (_MATHA_DIR / "interp.matha").exists(),
        },
        "bootstrap_ready": (
            _MATHA_DIR / "lexer.matha"
        ).exists()
        and (_MATHA_DIR / "parser.matha").exists(),
    }
