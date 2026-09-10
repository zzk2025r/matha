# -*- coding: utf-8 -*-
"""Matha 集成服务层 — Trae 开发环境的统一 Matha 入口

提供：
  - eval_expr()      : 求值 Matha 表达式
  - run_file()       : 运行 .matha 文件
  - compile_to_c()   : 编译到 C
  - compile_to_llvm() : 生成 LLVM IR
  - generate_code()  : 无中生有 — 从自然语言生成 Matha 代码
  - monitor()        : 文件监听，Matha 源码更新时自动重载

自动更新机制：
  - 启动时记录 src/ 目录下所有 .py 文件的 mtime
  - 每次调用前检查 mtime，若有变化则重新导入模块
  - 无需重启 Trae 即可使用最新 Matha 功能
"""
from __future__ import annotations

import hashlib
import importlib
import logging
import sys
import time
from pathlib import Path
from typing import Any, Optional

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger("matha.service")

# ── 模块缓存 ─────────────────────────────────────────────────────────────────
_modules: dict[str, Any] = {}
_last_mtime: dict[str, float] = {}


def _watched_paths() -> list[Path]:
    """返回需要监听变化的 Matha 核心源文件列表。"""
    src = PROJECT_ROOT / "src"
    return [
        src / "interp.py",
        src / "parser.py",
        src / "ast_nodes.py",
        src / "tokens.py",
        src / "lexer.py",
        src / "mathlib.py",
        src / "compiler" / "matha_cc.py",
        src / "multi_lang_frontend.py",
        src / "matha_bootstrap.py",
    ]


def _compute_signature() -> str:
    """计算所有核心文件的哈希作为变更检测指纹。"""
    hasher = hashlib.md5()
    for p in _watched_paths():
        if p.exists():
            try:
                stat = p.stat()
                hasher.update(f"{p}:{stat.st_mtime}:{stat.st_size}".encode())
            except OSError:
                pass
    return hasher.hexdigest()


def _reload_if_changed() -> bool:
    """检测文件变化并重新导入模块。返回 True 表示有更新。"""
    sig = _compute_signature()
    if getattr(_reload_if_changed, "_last_sig", None) == sig:
        return False
    _reload_if_changed._last_sig = sig

    for mod_name in list(_modules.keys()):
        try:
            importlib.reload(_modules[mod_name])
        except Exception as e:
            logger.warning(f"reload {mod_name} 失败: {e}")
    logger.info("Matha 模块已更新（新版本生效）")
    return True


# ── 统一入口 ─────────────────────────────────────────────────────────────────

def _get_interp() -> Any:
    """懒加载解释器模块，带自动重载。"""
    if "src.interp" not in _modules or _reload_if_changed():
        _modules["src.interp"] = importlib.import_module("src.interp")
    return _modules["src.interp"]


def _get_parser() -> Any:
    """懒加载解析器模块。"""
    if "src.parser" not in _modules or _reload_if_changed():
        _modules["src.parser"] = importlib.import_module("src.parser")
    return _modules["src.parser"]


def _get_bootstrap() -> Any:
    """懒加载自举模块。"""
    if "src.matha_bootstrap" not in _modules:
        _modules["src.matha_bootstrap"] = importlib.import_module("src.matha_bootstrap")
    return _modules["src.matha_bootstrap"]


def _get_compiler() -> Any:
    """懒加载编译器模块。"""
    if "src.compiler.matha_cc" not in _modules:
        try:
            _modules["src.compiler.matha_cc"] = importlib.import_module(
                "src.compiler.matha_cc"
            )
        except ImportError:
            return None
    return _modules.get("src.compiler.matha_cc")


# ── 公开 API ─────────────────────────────────────────────────────────────────

def eval_expr(expr: str, debug: bool = False) -> dict[str, Any]:
    """
    求值 Matha 表达式。

    Args:
        expr:  Matha 表达式字符串，如 "sin(3.14) + cos(0)"
        debug: 是否输出调试追踪

    Returns:
        {"output": [...], "trace": [...], "error": None|str}
    """
    interp_mod = _get_interp()
    wrapped = f"result = {expr}\n#1：[result]"
    try:
        out, trace = interp_mod.interpret(wrapped, debug=debug)
        return {"output": out, "trace": trace, "error": None}
    except Exception as e:
        return {"output": [], "trace": [], "error": str(e)}


def run_file(file_path: str, debug: bool = False) -> dict[str, Any]:
    """
    运行 .matha 文件。

    Args:
        file_path: .matha 文件路径
        debug:     是否输出调试追踪

    Returns:
        {"output": [...], "trace": [...], "error": None|str}
    """
    path = Path(file_path)
    if not path.exists():
        return {"output": [], "trace": [], "error": f"文件不存在: {file_path}"}
    source = path.read_text(encoding="utf-8")
    interp_mod = _get_interp()
    try:
        out, trace = interp_mod.interpret(source, debug=debug)
        return {"output": out, "trace": trace, "error": None}
    except Exception as e:
        return {"output": [], "trace": [], "error": str(e)}


def run_source(source: str, debug: bool = False) -> dict[str, Any]:
    """
    运行 Matha 源码字符串。

    Returns:
        {"output": [...], "trace": [...], "error": None|str}
    """
    interp_mod = _get_interp()
    try:
        out, trace = interp_mod.interpret(source, debug=debug)
        return {"output": out, "trace": trace, "error": None}
    except Exception as e:
        return {"output": [], "trace": [], "error": str(e)}


def compile_to_c(source: str, output: Optional[str] = None) -> dict[str, Any]:
    """
    将 Matha 源码编译为 C 代码。

    Returns:
        {"output_path": str, "error": None|str}
    """
    compiler_mod = _get_compiler()
    if compiler_mod is None:
        return {"output_path": "", "error": "编译器模块不可用"}
    try:
        target = output or "output.c"
        result = compiler_mod.matha_compile(source, target, optimize=True)
        return {"output_path": result, "error": None}
    except Exception as e:
        return {"output_path": "", "error": str(e)}


def compile_to_llvm(source: str, output: Optional[str] = None) -> dict[str, Any]:
    """
    将 Matha 源码生成 LLVM IR。

    Returns:
        {"ir": str, "output_path": str|None, "error": None|str}
    """
    compiler_mod = _get_compiler()
    if compiler_mod is None:
        return {"ir": "", "output_path": None, "error": "编译器模块不可用"}
    try:
        llvm_ir = compiler_mod.matha_to_llvm(source)
        out_path = None
        if output:
            Path(output).write_text(llvm_ir, encoding="utf-8")
            out_path = output
        return {"ir": llvm_ir, "output_path": out_path, "error": None}
    except Exception as e:
        return {"ir": "", "output_path": None, "error": str(e)}


def generate_code(prompt: str, target_language: str = "matha") -> dict[str, Any]:
    """
    无中生有：从自然语言描述生成 Matha/Python/JS/Rust 代码。

    Args:
        prompt:           自然语言描述，如 "实现一个计算轴承受力的函数"
        target_language:  目标语言: "matha" | "python" | "rust" | "js"

    Returns:
        {"source": str, "language": str, "error": None|str}
    """
    from src.matha.growth import generate_from_natural_language
    try:
        source = generate_from_natural_language(prompt, target_language)
        # 验证生成的代码可以解析
        parser_mod = _get_parser()
        parsed = parser_mod.parse(source)
        return {
            "source": source,
            "language": target_language,
            "parse_ok": True,
            "error": None,
        }
    except Exception as e:
        return {
            "source": "",
            "language": target_language,
            "parse_ok": False,
            "error": str(e),
        }


def generate_matha_code(prompt: str) -> dict[str, Any]:
    """
    专用于生成 Matha 代码的无中生有入口。
    """
    return generate_code(prompt, target_language="matha")


def generate_python_code(prompt: str) -> dict[str, Any]:
    """专用于生成 Python 代码的无中生有入口。"""
    return generate_code(prompt, target_language="python")


def generate_rust_code(prompt: str) -> dict[str, Any]:
    """专用于生成 Rust 代码的无中生有入口。"""
    return generate_code(prompt, target_language="rust")


def generate_js_code(prompt: str) -> dict[str, Any]:
    """专用于生成 JavaScript 代码的无中生有入口。"""
    return generate_code(prompt, target_language="js")


def parse_matha(source: str) -> dict[str, Any]:
    """
    解析 Matha 源码，返回 AST 结构。

    Returns:
        {"ast": dict, "error": None|str}
    """
    parser_mod = _get_parser()
    try:
        ast_tree = parser_mod.parse(source)
        return {"ast": ast_tree, "error": None}
    except Exception as e:
        return {"ast": None, "error": str(e)}


def get_info() -> dict[str, Any]:
    """获取 Matha 系统信息。"""
    from src.matha_main import VERSION as _VERSION
    return {
        "name": "Matha",
        "version": _VERSION,
        "project_root": str(PROJECT_ROOT),
        "signature": getattr(_reload_if_changed, "_last_sig", ""),
        "watched_files": [str(p) for p in _watched_paths()],
    }


# ── 自动更新监控 ──────────────────────────────────────────────────────────────

def start_watching(callback=None) -> None:
    """
    启动文件监控线程，当 Matha 核心文件变化时自动调用 callback。

    Args:
        callback: 变更回调函数，接收 (changed_paths: list[str]) 参数
    """
    import threading

    def _watch_loop():
        last_sig = ""
        while True:
            time.sleep(2)
            try:
                sig = _compute_signature()
                if sig != last_sig:
                    last_sig = sig
                    changed = [str(p) for p in _watched_paths() if p.exists()]
                    logger.info(f"Matha 文件变化，自动重载: {len(changed)} 个文件")
                    _reload_if_changed()
                    if callback:
                        callback(changed)
            except Exception as e:
                logger.warning(f"监控线程异常: {e}")

    t = threading.Thread(target=_watch_loop, daemon=True, name="matha-watcher")
    t.start()
    logger.info("Matha 文件监控已启动（每 2 秒检测一次）")


# ── 初始化 ────────────────────────────────────────────────────────────────────

# 启动时记录初始签名
_reload_if_changed._last_sig = _compute_signature()
logger.info(f"Matha 服务初始化完成，签名={_reload_if_changed._last_sig[:12]}...")
