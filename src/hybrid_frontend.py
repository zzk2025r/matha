# -*- coding: utf-8 -*-
"""
Matha 混合语言编译器（Hybrid Frontend）

整合所有原生语言前端：
  - Rust 前端 (matha/frontends/rust/frontend.rs)
  - Go 前端 (matha/frontends/go/frontend.go)
  - C 前端 (matha/frontends/c/frontend.c)
  - JavaScript 前端 (matha/frontends/js/frontend.js)
  - Matha 原生前端 (matha/frontends/matha/frontend.matha)

当各语言工具链可用时，使用原生前端编译；
否则回退到 Python 正则解析前端。
"""
from __future__ import annotations
import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("matha.hybrid_frontend")

# ── 原生前端路径 ──────────────────────────────────────────────────

FRONTENDS_DIR = Path(__file__).parent.parent / "matha" / "frontends"

# ── IR 结果格式 ──────────────────────────────────────────────────


@dataclass
class IRResult:
    """IR 编译结果。"""
    language: str
    source: str
    functions: dict = field(default_factory=dict)
    types: dict = field(default_factory=dict)
    effects: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "language": self.language,
            "source": self.source,
            "functions": self.functions,
            "types": self.types,
            "effects": self.effects,
            "errors": self.errors,
        }


# ── 语言前端注册表 ────────────────────────────────────────────────


class LanguageFrontendRegistry:
    """语言前端注册表。"""

    def __init__(self):
        self._frontends: dict[str, Any] = {}

    def register(self, language: str, frontend: Any) -> None:
        self._frontends[language.lower()] = frontend

    def get(self, language: str) -> Optional[Any]:
        return self._frontends.get(language.lower())

    def supported(self) -> list[str]:
        return list(self._frontends.keys())


# ── 原生前端调用器 ────────────────────────────────────────────────


class NativeFrontendRunner:
    """运行原生前端可执行文件，返回 JSON IR。"""

    def __init__(self, frontend_dir: Path):
        self._dir = frontend_dir

    def _find_binary(self, name: str) -> Optional[str]:
        """查找原生前端可执行文件。"""
        # 优先查找编译好的二进制
        for ext in (".exe", "", ".bin"):
            path = self._dir / f"{name}{ext}"
            if path.exists():
                return str(path)
        return None

    def _run(self, binary: str, source: str) -> Optional[dict]:
        """运行前端并返回解析结果。"""
        try:
            result = subprocess.run(
                [binary, source],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                return json.loads(result.stdout)
            logger.warning(f"前端返回错误: {result.stderr[:200]}")
            return None
        except FileNotFoundError:
            return None
        except subprocess.TimeoutExpired:
            return None
        except json.JSONDecodeError:
            return None

    def run_rust(self, source: str) -> Optional[dict]:
        binary = self._find_binary("matha_rust_frontend")
        if binary:
            return self._run(binary, source)
        return None

    def run_go(self, source: str) -> Optional[dict]:
        binary = self._find_binary("matha_go_frontend")
        if binary:
            return self._run(binary, source)
        # 回退：用 go run
        go_file = self._dir / "go" / "frontend.go"
        if go_file.exists():
            try:
                result = subprocess.run(
                    ["go", "run", str(go_file), source],
                    capture_output=True, text=True, timeout=30,
                )
                if result.returncode == 0:
                    return json.loads(result.stdout)
            except FileNotFoundError:
                pass
        return None

    def run_c(self, source: str) -> Optional[dict]:
        binary = self._find_binary("matha_c_frontend")
        if binary:
            return self._run(binary, source)
        # 回退：用 gcc
        c_file = self._dir / "c" / "frontend.c"
        if c_file.exists():
            try:
                exe = str(self._dir / "c" / "matha_c_frontend.exe")
                subprocess.run(["gcc", "-o", exe, str(c_file)], capture_output=True, timeout=30)
                return self._run(exe, source)
            except FileNotFoundError:
                pass
        return None

    def run_js(self, source: str) -> Optional[dict]:
        js_file = self._dir / "js" / "frontend.js"
        if js_file.exists():
            try:
                result = subprocess.run(
                    ["node", str(js_file), source],
                    capture_output=True, text=True, timeout=30,
                )
                if result.returncode == 0:
                    return json.loads(result.stdout)
            except FileNotFoundError:
                pass
        return None

    def run_matha(self, source: str) -> Optional[dict]:
        """Matha 原生前端（通过 Python 解释器执行）。"""
        matha_file = self._dir / "matha" / "frontend.matha"
        if matha_file.exists():
            try:
                from src.parser import parse
                from src.interp import Interpreter
                prog = parse(source)
                interp = Interpreter()
                outputs, trace = interp.run(prog)
                return {
                    "language": "matha",
                    "source": source,
                    "functions": {d.name: d.body for d in prog.decls
                                  if hasattr(d, 'name') and hasattr(d, 'body')},
                    "types": {},
                    "effects": {},
                    "outputs": outputs,
                }
            except Exception as e:
                logger.warning(f"Matha 前端执行失败: {e}")
        return None


# ── 混合语言编译器 ────────────────────────────────────────────────


class HybridFrontend:
    """混合语言编译器：整合所有原生前端，自动降级。"""

    def __init__(self):
        self._runner = NativeFrontendRunner(FRONTENDS_DIR)
        self._registry = LanguageFrontendRegistry()
        self._register_builtin_frontends()

    def _register_builtin_frontends(self):
        """注册内置 Python 前端作为回退。"""
        from src.multi_lang_frontend import (
            RustFrontend, GoFrontend, JSFrontend, CFrontend,
        )
        self._registry.register("rust", RustFrontend())
        self._registry.register("go", GoFrontend())
        self._registry.register("javascript", JSFrontend())
        self._registry.register("c", CFrontend())
        self._registry.register("python", None)  # Python 由 mir2_frontend 处理

    def compile(self, source: str, language: str = "python") -> IRResult:
        """编译源码为 IR。

        策略：
          1. 尝试原生前端（如果二进制存在）
          2. 回退到 Python 正则前端
          3. 最后回退到 tree-sitter
        """
        lang = language.lower()

        # ── 第 1 步：尝试原生前端 ─────────────────────────────────
        native_result = self._try_native(source, lang)
        if native_result is not None:
            logger.info(f"使用原生前端编译 {lang} 成功")
            return self._to_ir_result(native_result, lang, source)

        # ── 第 2 步：回退到 Python 前端 ───────────────────────────
        builtin = self._registry.get(lang)
        if builtin is not None:
            try:
                result = builtin.compile(source)
                return IRResult(
                    language=lang,
                    source=source,
                    functions=result.functions,
                    types=result.types,
                    effects=result.effects,
                    errors=result.errors,
                )
            except Exception as e:
                logger.warning(f"Python 前端编译失败: {e}")

        # ── 第 3 步：尝试 tree-sitter ─────────────────────────────
        try:
            ts_result = self._try_tree_sitter(source, lang)
            if ts_result is not None:
                return self._to_ir_result(ts_result, lang, source)
        except Exception as e:
            logger.warning(f"tree-sitter 失败: {e}")

        # ── 全部失败 ──────────────────────────────────────────────
        return IRResult(
            language=lang,
            source=source,
            errors=[f"无法编译 {lang} 代码: 所有前端均不可用"],
        )

    def _try_native(self, source: str, lang: str) -> Optional[dict]:
        """尝试使用原生前端。"""
        # Matha 原生前端（优先）
        if lang == "matha":
            return self._try_matha_frontend(source)
        # 其他语言：尝试原生二进制
        if lang == "rust":
            return self._runner.run_rust(source)
        elif lang == "go":
            return self._runner.run_go(source)
        elif lang == "c":
            return self._runner.run_c(source)
        elif lang in ("javascript", "js"):
            return self._runner.run_js(source)
        return None

    def _try_matha_frontend(self, source: str) -> Optional[dict]:
        """使用 Matha 原生前端编译。"""
        # 先尝试标准 Matha 解释器
        try:
            from src.parser import parse
            from src.interp import Interpreter
            prog = parse(source)
            interp = Interpreter()
            outputs, trace = interp.run(prog)
            funcs = {}
            for d in prog.decls:
                if hasattr(d, 'name') and hasattr(d, 'body'):
                    funcs[d.name] = d.body
            return {
                "language": "matha",
                "source": source,
                "functions": funcs,
                "types": {},
                "effects": {},
                "outputs": outputs,
            }
        except Exception as e:
            logger.debug(f"Matha 解释器编译失败: {e}")

        # 回退：加载并执行 matha/native 前端模块
        frontend_file = FRONTENDS_DIR / "matha" / "frontend.matha"
        multi_file = FRONTENDS_DIR / "multi_lang.matha"
        if multi_file.exists():
            try:
                from src.parser import parse as matha_parse
                from src.interp import Interpreter
                content = multi_file.read_text(encoding="utf-8")
                prog = matha_parse(content)
                interp = Interpreter()
                interp.run(prog)
                # 尝试从解释器上下文获取编译结果
                result = interp.globals.get("编译", None)
                if callable(result):
                    return result(source)
            except Exception as e:
                logger.debug(f"Matha 前端模块加载失败: {e}")

        # 最终回退：用 Python 前端
        return None

    def _try_tree_sitter(self, source: str, lang: str) -> Optional[dict]:
        """尝试使用 tree-sitter。"""
        try:
            from src.tree_sitter_backends import get_parser
            parser = get_parser(lang)
            if parser is None:
                return None
            tree = parser.parse(source.encode())
            # 转换为 IR 格式
            return {"language": lang, "source": source, "tree": tree.root_node.sexp()}
        except ImportError:
            return None
        except Exception:
            return None

    def _to_ir_result(self, native_result: dict, lang: str, source: str) -> IRResult:
        """将原生前端结果转换为 IRResult。"""
        return IRResult(
            language=lang,
            source=source,
            functions=native_result.get("functions", {}),
            types=native_result.get("types", {}),
            effects=native_result.get("effects", {}),
            errors=native_result.get("errors", []),
        )

    def get_supported_languages(self) -> list[str]:
        """返回支持的语言列表。"""
        return self._registry.supported() + ["matha"]

    def has_native_frontend(self, lang: str) -> bool:
        """检查是否有原生前端可用。"""
        return self._try_native("", lang) is not None or self._registry.get(lang) is not None


# ── 单例 ────────────────────────────────────────────────────────

_hybrid_frontend: Optional[HybridFrontend] = None


def get_hybrid_frontend() -> HybridFrontend:
    global _hybrid_frontend
    if _hybrid_frontend is None:
        _hybrid_frontend = HybridFrontend()
    return _hybrid_frontend


# ── 向后兼容 ────────────────────────────────────────────────────

# 让旧代码仍然能正常工作
def compile_to_ir(source: str, language: str = "python") -> IRResult:
    return get_hybrid_frontend().compile(source, language)


def parse_foreign(source: str, lang: str) -> Optional[dict]:
    return get_hybrid_frontend().compile(source, lang).to_dict()
