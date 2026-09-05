# -*- coding: utf-8 -*-
"""
Matha 多语言统一层（Unified Multi-Language）

合并：
  - multi_lang_frontend.py: 多语言前端（Rust/Go/JS/C → Matha MIR）
  - multi_lang_codegen.py: 多语言代码生成（Matha → 目标语言）
  - multi_lang_verifier.py: 多语言交叉验证
  - cross_language_verifier.py: 旧版交叉验证器
  - transpiler.py: Matha → Python/JS 转译
  - transpiler_ts.py: Matha → TypeScript 转译

统一后所有功能通过 UnifiedMultiLang 类访问。
"""
from __future__ import annotations
import logging
from typing import Any, Optional

logger = logging.getLogger("matha.unified_multilang")

# ── 懒导入各子系统（避免循环依赖）───────────────────────────────────────────


def _get_frontend():
    from src.multi_lang_frontend import MultiLanguageFrontend
    return MultiLanguageFrontend


def _get_hybrid_frontend():
    from src.hybrid_frontend import HybridFrontend
    return HybridFrontend


def _get_codegen():
    from src.multi_lang_codegen import MultiLangCodeGen
    return MultiLangCodeGen


def _get_verifier():
    try:
        from src.multi_lang_verifier import MultiLangVerifierV2
        return MultiLangVerifierV2
    except ImportError:
        from src.cross_language_verifier import CrossLanguageVerifier
        return CrossLanguageVerifier


def _get_transpiler():
    from src.transpiler import PythonTranspiler
    return PythonTranspiler


def _get_transpiler_ts():
    try:
        from src.transpiler_ts import TypeScriptTranspiler
        return TypeScriptTranspiler
    except ImportError:
        return None


# ── 统一多语言接口 ──────────────────────────────────────────────────────────


class UnifiedMultiLang:
    """统一多语言接口：前端 + 代码生成 + 验证 + 转译。"""

    def __init__(self):
        self._frontend = None
        self._hybrid_frontend = None
        self._codegen = None
        self._verifier_cls = None
        self._python_transpiler = None
        self._ts_transpiler_cls = None

    def _ensure_initialized(self):
        if self._frontend is None:
            self._frontend = _get_frontend()
        if self._hybrid_frontend is None:
            self._hybrid_frontend = _get_hybrid_frontend()
        if self._codegen is None:
            self._codegen = _get_codegen()
        if self._verifier_cls is None:
            self._verifier_cls = _get_verifier()
        if self._python_transpiler is None:
            self._python_transpiler = _get_transpiler()()
        if self._ts_transpiler_cls is None:
            self._ts_transpiler_cls = _get_transpiler_ts()

    # ── 前端：其他语言 → Matha MIR ─────────────────────────────────────────

    def parse_foreign(self, source: str, lang: str) -> Any:
        """将其他语言源码解析为 Matha MIR。

        策略：先尝试原生前端（如果二进制存在），回退到 Python 前端。
        """
        self._ensure_initialized()
        # 先尝试混合前端（原生 → Python 回退）
        try:
            result = self._hybrid_frontend.compile(source, lang)
            if result and not result.errors:
                return result.to_dict()
        except Exception as e:
            logger.debug(f"混合前端失败，回退到 Python 前端: {e}")
        # 回退到 Python 前端
        try:
            frontend = self._frontend()
            return frontend.parse(source, lang)
        except Exception as e:
            logger.warning(f"前端解析失败 ({lang}): {e}")
            return None

    # ── 代码生成：Matha → 其他语言 ─────────────────────────────────────────

    def generate_code(self, language: str, func_name: str,
                      params: list, expr: str,
                      return_type: str = "Any") -> str:
        """将 Matha 函数生成为目标语言代码。"""
        self._ensure_initialized()
        try:
            result = self._codegen.generate(language, func_name, params, expr, return_type)
            return result.code if hasattr(result, 'code') else str(result)
        except Exception as e:
            logger.warning(f"代码生成失败 ({language}): {e}")
            return ""

    # ── 验证：多语言交叉验证 ───────────────────────────────────────────────

    def verify_cross_language(
        self,
        matha_source: str,
        languages: list[str] = None,
        test_cases: list = None,
    ) -> dict:
        """跨语言交叉验证 Matha 代码。"""
        self._ensure_initialized()
        try:
            verifier = self._verifier_cls()
            return verifier.verify(matha_source, languages or ["python", "rust"], test_cases or [])
        except Exception as e:
            logger.warning(f"交叉验证失败: {e}")
            return {"success": False, "error": str(e)}

    # ── 转译：Matha ↔ 目标语言 ────────────────────────────────────────────

    def transpile_to_python(self, matha_source: str) -> str:
        """Matha → Python。"""
        self._ensure_initialized()
        return self._python_transpiler.transpile(matha_source)

    def transpile_to_typescript(self, matha_source: str) -> str:
        """Matha → TypeScript。"""
        self._ensure_initialized()
        if self._ts_transpiler_cls is None:
            return "# TypeScript transpiler not available"
        return self._ts_transpiler_cls().transpile(matha_source)

    def transpile_from_python(self, python_source: str) -> str:
        """Python → Matha（启发式反向转译）。"""
        from src.hybrid_compiler import LanguageBridge
        return LanguageBridge().python_to_matha(python_source)

    # ── 综合：完整多语言工作流 ─────────────────────────────────────────────

    def full_workflow(
        self,
        matha_source: str,
        target_langs: list[str] = None,
        verify: bool = True,
    ) -> dict:
        """完整多语言工作流：生成 → 验证 → 报告。

        Returns:
            {
                "generations": {lang: code},
                "verification": {...},
                "success": bool,
            }
        """
        langs = target_langs or ["python", "typescript", "rust"]
        generations = {}
        errors = []

        for lang in langs:
            try:
                code = self.generate_code(matha_source, lang)
                generations[lang] = code
            except Exception as e:
                errors.append(f"{lang}: {e}")

        verification = {}
        if verify and generations:
            verification = self.verify_cross_language(matha_source, langs)

        return {
            "generations": generations,
            "verification": verification,
            "success": len(errors) == 0,
            "errors": errors,
        }


# ── 单例 ────────────────────────────────────────────────────────────────────

_unified_multilang: Optional[UnifiedMultiLang] = None


def get_unified_multilang() -> UnifiedMultiLang:
    global _unified_multilang
    if _unified_multilang is None:
        _unified_multilang = UnifiedMultiLang()
    return _unified_multilang


# ── 向后兼容导出 ────────────────────────────────────────────────────────────
# 让旧的 import 路径仍然有效

MultiLangFrontend = _get_frontend
MultiLangCodegen = _get_codegen
MultiLangVerifier = _get_verifier
PythonTranspiler = _get_transpiler
TypeScriptTranspiler = _get_transpiler_ts
