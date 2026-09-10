# -*- coding: utf-8 -*-
"""Matha 自举桥接层 — 纯 Matha 主路径

架构：
  - Python 负责：读取 .matha 源文件，用 Python 解释器加载核心模块
  - Matha 负责：词法分析、语法分析、表达式求值、语句执行

Python 层不再调用 src.parser.parse()，仅用 interp.run() 将
lexer/parser/stdlib/interp_matha 注册到解释器中。
用户源码的解析和执行完全由 Matha 自举解释器完成。
"""
from __future__ import annotations
import os
import sys
from pathlib import Path
from typing import Optional

# ============================================================
# 路径配置
# ============================================================

_SCRIPT_DIR = Path(__file__).parent
_CANDIDATES = [
    _SCRIPT_DIR.parent / "matha",
    _SCRIPT_DIR.parent.parent / "matha",
    Path.cwd().parent / "matha",
]
_MATHA_DIR = next((p for p in _CANDIDATES if p.exists()), _SCRIPT_DIR.parent.parent / "matha")


def _load_matha_source(module_name: str) -> str:
    """读取 .matha 源文件。"""
    if module_name == "运行时引擎":
        path = _MATHA_DIR / "runtime" / "matha_runtime.matha"
    else:
        path = _MATHA_DIR / f"{module_name}.matha"
    if not path.exists():
        raise FileNotFoundError(f"找不到模块: {path}")
    return path.read_text(encoding="utf-8")


# ============================================================
# 模块加载（Python 解释器只用于初始化核心模块）
# ============================================================

def _load_matha_modules(interp) -> bool:
    """用 Python 解释器加载核心 Matha 模块（lexer/parser/stdlib/interp_matha）。

    这些模块在 Python 中仅需一次初始化；
    之后用户源码完全由 Matha 自举解释器解析和执行。
    返回 True 表示加载成功。
    """
    try:
        from src.parser import parse as _python_parse

        for mod_name in ("运行时引擎", "lexer", "parser", "stdlib", "interp_matha", "bootstrap_matha"):
            src = _load_matha_source(mod_name)
            prog = _python_parse(src)
            interp.run(prog)

        return True
    except Exception as e:
        print(f"[bootstrap] 加载 Matha 核心模块失败: {e}", file=sys.stderr)
        return False


def _get_interp(debug: Optional[bool] = None):
    """创建 Interpreter 并加载 Matha 核心模块（懒加载）。"""
    from src.interp import Interpreter
    interp = Interpreter(debug=debug)
    if not getattr(interp, "_matha_loaded", False):
        sys.setrecursionlimit(max(10000, sys.getrecursionlimit()))
        interp._matha_loaded = _load_matha_modules(interp)
    return interp


# ============================================================
# 主入口：Matha 自举优先
# ============================================================

_USE_BOOTSTRAP = os.environ.get("MATHA_USE_BOOTSTRAP", "1") == "1"


def interpret(source: str, debug: Optional[bool] = None) -> tuple[list, list[str]]:
    """Matha 源码解释入口（Matha 自举优先，Python 降级）。

    流程：
      1. 加载核心模块（首次调用时初始化）
      2. 使用 Matha 词法器扫描源码
      3. 使用 Matha 语法器解析 AST
      4. 使用 Matha 自举解释器执行
    """
    if not _USE_BOOTSTRAP:
        from src.interp import interpret as _python_interpret
        return _python_interpret(source, debug)

    interp = _get_interp(debug)

    try:
        # 步骤 1：Matha 词法分析
        toks = interp.call("扫描", source, 0, 1, 1, [])
        if not toks:
            return ([], [])
    except Exception as e:
        return ([f"[词法分析错误] {e}"], [])

    try:
        # 步骤 2：Matha 语法分析
        ast = interp.call("parse", toks)
    except Exception as e:
        return ([f"[语法分析错误] {e}"], [str(e)])

    try:
        # 步骤 3：Matha 自举解释器执行
        run_ast = interp.modules.get("自举加载器", {}).get("run_ast")
        if run_ast is None:
            raise RuntimeError("自举加载器.run_ast 未找到，请重新加载核心模块")
        result, _ = run_ast(ast)
        return ([result], [])
    except Exception:
        # 降级到 Python 解释器
        from src.interp import interpret as _python_interpret
        return _python_interpret(source, debug)


def set_bootstrap_mode(enable: bool) -> None:
    """动态切换解释路径。"""
    global _USE_BOOTSTRAP
    _USE_BOOTSTRAP = enable
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
            "interp": (_MATHA_DIR / "interp_matha.matha").exists(),
            "stdlib": (_MATHA_DIR / "stdlib.matha").exists(),
            "runtime": (_MATHA_DIR / "runtime" / "matha_runtime.matha").exists(),
            "bootstrap": (_MATHA_DIR / "bootstrap_matha.matha").exists(),
        },
        "bootstrap_ready": (
            (_MATHA_DIR / "lexer.matha").exists()
            and (_MATHA_DIR / "parser.matha").exists()
            and (_MATHA_DIR / "interp_matha.matha").exists()
            and (_MATHA_DIR / "stdlib.matha").exists()
            and (_MATHA_DIR / "runtime" / "matha_runtime.matha").exists()
        ),
    }
