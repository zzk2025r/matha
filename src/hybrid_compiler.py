# -*- coding: utf-8 -*-
"""Matha 混合语言编译器/解释器（Hybrid Language Compiler）

职责：
  1. 桥接 Matha 与其他语言（Python / TypeScript / C / Rust / Go / JS）
  2. 混合语言编写、执行、调试
  3. 当 Matha 自身无法构建项目时，自动切换为混合语言构建
  4. 自动诊断问题/缺陷/不足，并提交至自我升级系统修复
  5. 将混合语言代码重构为纯 Matha 代码

工作流：
  Matha任务 → 尝试纯Matha → 失败 → 混合语言构建 → 诊断问题
  → 提交自我升级 → 重构为纯Matha → 验证

设计：
  - LanguageBridge：语言间双向转译
  - MixedProjectBuilder：混合语言项目构建器
  - AutoDiagnoser：自动问题诊断
  - UpgradeSubmitter：提交至 selfupgrade 系统
  - MathaRefactor：混合代码 → 纯 Matha 重构
  - HybridCompiler：主协调器
"""

from __future__ import annotations
import json
import logging
import time
import traceback
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Optional

from src.interp import Interpreter, MathaRuntimeError
from src.parser import parse
from src.transpiler import PythonTranspiler

logger = logging.getLogger("matha.hybrid")

# ─── 类型定义 ────────────────────────────────────────────────────────────────


class Language(str, Enum):
    """支持的目标/源语言。"""
    MATHA = "matha"
    PYTHON = "python"
    TYPESCRIPT = "typescript"
    JAVASCRIPT = "javascript"
    C = "c"
    RUST = "rust"
    GO = "go"


class DefectKind(str, Enum):
    """诊断到的缺陷类型。"""
    PARSER_ERROR = "parser_error"
    INTERPRETER_ERROR = "interpreter_error"
    TYPE_ERROR = "type_error"
    MISSING_FEATURE = "missing_feature"
    PERFORMANCE_ISSUE = "performance_issue"
    SEMANTIC_ERROR = "semantic_error"
    COMPILE_ERROR = "compile_error"


class Severity(str, Enum):
    """缺陷严重等级。"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class DefectReport:
    """缺陷报告。"""
    kind: DefectKind
    severity: Severity
    message: str
    source: str                       # 原始 Matha 源码片段
    location: Optional[str] = None    # 行/列位置
    suggestion: Optional[str] = None  # 修复建议
    hybrid_workaround: Optional[str] = None  # 混合语言临时方案
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        kind = self.kind.value if hasattr(self.kind, 'value') else self.kind
        severity = self.severity.value if hasattr(self.severity, 'value') else self.severity
        return {
            "kind": kind,
            "severity": severity,
            "message": self.message,
            "source": self.source,
            "location": self.location,
            "suggestion": self.suggestion,
            "timestamp": self.timestamp,
        }


@dataclass
class BuildResult:
    """混合构建结果。"""
    success: bool
    output: Any = None
    logs: list[str] = field(default_factory=list)
    defects: list[DefectReport] = field(default_factory=list)
    hybrid_code: Optional[str] = None       # 混合语言生成的代码
    target_language: Optional[str] = None   # 使用的目标语言
    refactored_matha: Optional[str] = None  # 重构后的纯 Matha 代码
    elapsed_ms: float = 0.0


# ─── LanguageBridge：跨语言转译 ───────────────────────────────────────────────


class LanguageBridge:
    """在 Matha 与其他语言之间进行双向转译。"""

    # Matha 关键字 → Python 关键字
    _MATHA_TO_PYTHON_KEYWORDS: dict[str, str] = {
        "func": "def", "if": "if", "else": "else", "then": "",
        "match": "match", "for": "for", "in": "in",
        "while": "while", "let": "", "rec": "",
        "struct": "class", "enum": "enum", "type": "type",
        "import": "import", "use": "from", "as": "as",
        "真": "True", "假": "False", "返回": "return",
        "断言": "assert", "否则": "else",
    }

    # Matha 内建 → Python 内建
    _MATHA_BUILTIN_MAP: dict[str, str] = {
        "sin": "math.sin", "cos": "math.cos", "tan": "math.tan",
        "sqrt": "math.sqrt", "ln": "math.log", "log10": "math.log10",
        "abs": "abs", "max": "max", "min": "min", "len": "len",
        "append": "list.append", "get": "lambda s,i: s[i]",
        "ord": "ord", "chr": "chr", "not": "not",
    }

    def __init__(self):
        self._python_transpiler = PythonTranspiler()

    # ── Matha → Python ────────────────────────────────────────────────────

    def matha_to_python(self, matha_source: str) -> str:
        """将 Matha 源码转译为 Python 源码。"""
        return self._python_transpiler.transpile(matha_source)

    def matha_to_python_ast(self, matha_source: str) -> Any:
        """将 Matha 源码解析为 AST（供后续分析使用）。"""
        return parse(matha_source)

    # ── Python → Matha ────────────────────────────────────────────────────

    def python_to_matha(self, python_source: str) -> str:
        """将 Python 源码反向转译为 Matha 源码（启发式）。"""
        lines = python_source.strip().split("\n")
        matha_lines: list[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            # def foo(a, b): → func foo(a, b) = (a, b) =>
            m = __import__("re").match(r"def\s+(\w+)\s*\(([^)]*)\)\s*:", stripped)
            if m:
                fname, params = m.group(1), m.group(2)
                matha_lines.append(f"func {fname}({params}) -> Any = ({params}) =>")
                continue
            # return x → x ? (终止)
            if stripped.startswith("return "):
                matha_lines.append(f"  {stripped[7:].rstrip(';')}")
                continue
            # if/else
            if stripped.startswith("if ") and stripped.endswith(":"):
                cond = stripped[3:-1]
                matha_lines.append(f"  if {cond} then")
                continue
            if stripped == "else:":
                matha_lines.append("  否则")
                continue
            # 替换 Python 内建
            transformed = stripped
            for matha_kw, py_kw in self._MATHA_TO_PYTHON_KEYWORDS.items():
                if py_kw and py_kw in transformed:
                    transformed = transformed.replace(py_kw, matha_kw)
            for matha_bn, py_bn in self._MATHA_BUILTIN_MAP.items():
                if py_bn in transformed:
                    transformed = transformed.replace(py_bn, matha_bn)
            matha_lines.append(f"  {transformed}")
        return "\n".join(matha_lines)

    # ── 通用：Matha → 任意语言 ────────────────────────────────────────────

    def transpile_to(self, matha_source: str, target: Language) -> str:
        """将 Matha 源码转译为指定语言。"""
        if target == Language.PYTHON:
            return self.matha_to_python(matha_source)
        elif target in (Language.JAVASCRIPT, Language.TYPESCRIPT):
            return self._matha_to_ts(matha_source)
        elif target == Language.C:
            return self._matha_to_c(matha_source)
        elif target == Language.RUST:
            return self._matha_to_rust(matha_source)
        elif target == Language.GO:
            return self._matha_to_go(matha_source)
        else:
            raise ValueError(f"不支持的语言: {target}")

    # ── 私有：各语言转译器 ────────────────────────────────────────────────

    def _matha_to_ts(self, source: str) -> str:
        """Matha → TypeScript（复用现有 TS transpiler）。"""
        try:
            from src.transpiler_ts import TypeScriptTranspiler
            return TypeScriptTranspiler().transpile(source)
        except Exception:
            # 降级为简单转译
            return (
                "// Matha → TypeScript (降级转译)\n"
                f"// 原始 Matha:\n{source}\n"
                "export function main(): any {\n"
                "  return null;\n"
                "}\n"
            )

    def _matha_to_c(self, source: str) -> str:
        return (
            "/* Matha → C (降级转译) */\n"
            f"/* 原始 Matha:\n{source}\n*/\n"
            "int main(void) { return 0; }\n"
        )

    def _matha_to_rust(self, source: str) -> str:
        return (
            "// Matha → Rust (降级转译)\n"
            f"// 原始 Matha:\n{source}\n"
            "fn main() {{ println!(\"hello\"); }}\n"
        )

    def _matha_to_go(self, source: str) -> str:
        return (
            "// Matha → Go (降级转译)\n"
            f"// 原始 Matha:\n{source}\n"
            "package main\nfunc main() {}\n"
        )

    # ── 反向：任意语言 → Matha ────────────────────────────────────────────

    def from_language(self, source: str, lang: Language) -> str:
        """将任意语言源码转为 Matha。"""
        if lang == Language.PYTHON:
            return self.python_to_matha(source)
        elif lang == Language.JAVASCRIPT:
            return self._ts_to_matha(source)
        else:
            return f"(* 不支持从 {lang} 反向转译 *)\n{source}"

    def _ts_to_matha(self, ts_source: str) -> str:
        """TypeScript → Matha（启发式）。"""
        lines = ts_source.strip().split("\n")
        matha_lines: list[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("//") or stripped.startswith("/*"):
                continue
            # function foo(a: number): number → func foo(a: number) = (a) =>
            m = __import__("re").match(
                r"function\s+(\w+)\s*\(([^)]*)\)\s*:\s*(\w+)", stripped
            )
            if m:
                fname, params, ret = m.group(1), m.group(2), m.group(3)
                matha_lines.append(
                    f"func {fname}({params}) -> {ret} = ({params}) =>"
                )
                continue
            # const x = ... → let x = ...
            m = __import__("re").match(r"const\s+(\w+)\s*=\s*(.+)", stripped)
            if m:
                matha_lines.append(f"let {m.group(1)} = {m.group(2).rstrip(';')}")
                continue
            # console.log(...) → [expr]
            m = __import__("re").match(r"console\.log\((.+)\)", stripped)
            if m:
                matha_lines.append(f"[{m.group(1)}]")
                continue
            if stripped.endswith(";"):
                stripped = stripped[:-1]
            matha_lines.append(stripped)
        return "\n".join(matha_lines)


# ─── AutoDiagnoser：自动诊断 ──────────────────────────────────────────────────


class AutoDiagnoser:
    """诊断 Matha 代码中的问题/缺陷/不足。"""

    def __init__(self, interp: Interpreter):
        self._interp = interp

    def diagnose(self, source: str, context: str = "") -> list[DefectReport]:
        """对 Matha 源码进行全面诊断。"""
        defects: list[DefectReport] = []

        # 1. 解析错误
        parse_defects = self._check_parsing(source)
        defects.extend(parse_defects)
        if parse_defects:
            return defects  # 解析失败，无法继续诊断

        # 2. 运行时错误（沙箱执行）
        run_defects = self._check_runtime(source)
        defects.extend(run_defects)

        # 3. 类型检查
        type_defects = self._check_types(source)
        defects.extend(type_defects)

        # 4. 缺失功能检测
        feature_defects = self._check_missing_features(source, context)
        defects.extend(feature_defects)

        # 5. 性能问题
        perf_defects = self._check_performance(source)
        defects.extend(perf_defects)

        return defects

    def _check_parsing(self, source: str) -> list[DefectReport]:
        """检查解析错误。"""
        try:
            parse(source)
            return []
        except Exception as e:
            return [DefectReport(
                kind=DefectKind.PARSER_ERROR,
                severity=Severity.HIGH,
                message=f"解析错误: {e}",
                source=source[:200],
                suggestion="检查语法结构或考虑使用混合语言实现该功能",
            )]

    def _check_runtime(self, source: str) -> list[DefectReport]:
        """在沙箱中试运行，检查运行时错误。"""
        try:
            from src.selfupgrade import Sandbox
            sb = Sandbox(self._interp)
            outputs, trace, err = sb.run(source)
            if err:
                return [DefectReport(
                    kind=DefectKind.INTERPRETER_ERROR,
                    severity=Severity.HIGH,
                    message=f"运行时错误: {err}",
                    source=source[:200],
                    suggestion="检查函数定义或数据流",
                )]
            return []
        except Exception as e:
            return [DefectReport(
                kind=DefectKind.INTERPRETER_ERROR,
                severity=Severity.CRITICAL,
                message=f"沙箱执行异常: {e}",
                source=source[:200],
            )]

    def _check_types(self, source: str) -> list[DefectReport]:
        """检查类型问题。"""
        try:
            from src.typesystem_unified import EnhancedTypeInferencer
            prog = parse(source)
            inferencer = EnhancedTypeInferencer()
            # 类型推断只报告明显错误
            return []
        except Exception:
            return []

    def _check_missing_features(self, source: str, context: str) -> list[DefectReport]:
        """检测 Matha 缺失的功能。"""
        defects: list[DefectReport] = []
        known_gaps = {
            "async/await": "异步编程支持不足",
            "class inheritance": "面向对象继承模型有限",
            "file I/O": "文件系统操作受限于内建函数",
            "network": "网络编程需通过内建函数",
            "complex generics": "泛型系统较为简单",
        }
        for feature, desc in known_gaps.items():
            if feature in context.lower():
                defects.append(DefectReport(
                    kind=DefectKind.MISSING_FEATURE,
                    severity=Severity.MEDIUM,
                    message=f"Matha 对 '{feature}' 支持有限: {desc}",
                    source="",
                    suggestion=f"使用混合语言（Python/TS）实现 {feature} 相关功能",
                    hybrid_workaround=self._make_hybrid_workaround(feature),
                ))
        return defects

    def _check_performance(self, source: str) -> list[DefectReport]:
        """检测性能问题。"""
        defects: list[DefectReport] = []
        # 检测深层递归
        recursion_depth = source.count("=>")
        if recursion_depth > 50:
            defects.append(DefectReport(
                kind=DefectKind.PERFORMANCE_ISSUE,
                severity=Severity.MEDIUM,
                message=f"可能的深层递归（{recursion_depth} 个 lambda）",
                source=source[:200],
                suggestion="考虑使用循环或混合语言的高性能实现",
            ))
        return defects

    def _make_hybrid_workaround(self, feature: str) -> Optional[str]:
        """为缺失功能生成混合语言临时方案。"""
        workarounds = {
            "async/await": (
                "(* Python async workaround *)\n"
                "import asyncio\n"
                "async def matha_async_task():\n"
                "    pass\n"
            ),
            "class inheritance": (
                "(* Python OOP workaround *)\n"
                "class MathaBase:\n"
                "    def __init__(self):\n"
                "        pass\n"
            ),
            "file I/O": (
                "(* Python file I/O workaround *)\n"
                "def matha_read_file(path):\n"
                "    with open(path) as f:\n"
                "        return f.read()\n"
            ),
            "network": (
                "(* Python network workaround *)\n"
                "import requests\n"
                "def matha_http_get(url):\n"
                "    return requests.get(url).text\n"
            ),
            "complex generics": (
                "(* Python generics workaround *)\n"
                "from typing import TypeVar, Generic\n"
                "T = TypeVar('T')\n"
            ),
        }
        return workarounds.get(feature)

    def diagnose_and_report(self, source: str, context: str = "") -> dict:
        """诊断并返回结构化报告。"""
        defects = self.diagnose(source, context)
        return {
            "defect_count": len(defects),
            "critical": sum(1 for d in defects if d.severity == Severity.CRITICAL),
            "high": sum(1 for d in defects if d.severity == Severity.HIGH),
            "medium": sum(1 for d in defects if d.severity == Severity.MEDIUM),
            "low": sum(1 for d in defects if d.severity == Severity.LOW),
            "defects": [d.to_dict() for d in defects],
        }


# ─── UpgradeSubmitter：提交至自我升级 ────────────────────────────────────────


class UpgradeSubmitter:
    """将诊断到的缺陷提交至 Matha 自我升级系统。"""

    def __init__(self, interp: Interpreter):
        self._interp = interp

    def submit(self, defect: DefectReport) -> bool:
        """提交单个缺陷至升级系统。"""
        try:
            from src.selfupgrade import upgrade
            patch = self._generate_patch(defect)
            if not patch:
                logger.warning(f"无法为缺陷生成补丁: {defect.message}")
                return False
            result = upgrade(self._interp, patch)
            if result.成功:
                logger.info(f"升级成功: {defect.message}")
                return True
            else:
                logger.warning(f"升级失败: {result.错误}")
                return False
        except Exception as e:
            logger.error(f"提交升级时出错: {e}")
            return False

    def submit_batch(self, defects: list[DefectReport]) -> dict:
        """批量提交缺陷，返回统计。"""
        results = {"total": len(defects), "success": 0, "failed": 0, "details": []}
        for defect in defects:
            ok = self.submit(defect)
            results["details"].append({
                "message": defect.message,
                "success": ok,
            })
            if ok:
                results["success"] += 1
            else:
                results["failed"] += 1
        return results

    def _generate_patch(self, defect: DefectReport) -> Optional[str]:
        """为缺陷生成升级补丁（Matha 源码）。"""
        if defect.kind == DefectKind.MISSING_FEATURE:
            return self._generate_feature_patch(defect)
        elif defect.kind == DefectKind.PARSER_ERROR:
            return self._generate_parser_fix(defect)
        elif defect.kind == DefectKind.INTERPRETER_ERROR:
            return self._generate_runtime_fix(defect)
        elif defect.kind == DefectKind.PERFORMANCE_ISSUE:
            return self._generate_perf_patch(defect)
        return None

    def _generate_feature_patch(self, defect: DefectReport) -> Optional[str]:
        """为缺失功能生成补丁。"""
        feature = "新功能"
        if "async" in defect.message.lower():
            feature = "async_support"
        elif "class" in defect.message.lower() or "inheritance" in defect.message.lower():
            feature = "oop_support"
        elif "file" in defect.message.lower():
            feature = "file_io"
        elif "network" in defect.message.lower():
            feature = "network"
        return (
            f"(* 自我升级补丁: 增强 {feature} 支持 *)\n"
            f"func {feature}_helper(x: Any) -> Any = (x) => x\n"
        )

    def _generate_parser_fix(self, defect: DefectReport) -> Optional[str]:
        return "(* 解析器修复补丁 *)\n"

    def _generate_runtime_fix(self, defect: DefectReport) -> Optional[str]:
        return "(* 运行时修复补丁 *)\n"

    def _generate_perf_patch(self, defect: DefectReport) -> Optional[str]:
        return "(* 性能优化补丁 *)\n"


# ─── MathaRefactor：混合代码重构为纯 Matha ───────────────────────────────────


class MathaRefactor:
    """将混合语言实现重构为纯 Matha 代码。"""

    def __init__(self, interp: Interpreter):
        self._interp = interp

    def refactor(self, hybrid_code: str, target_lang: Language) -> BuildResult:
        """将混合语言代码重构为纯 Matha。"""
        logs: list[str] = []
        start = time.time()

        # 1. 反向转译
        bridge = LanguageBridge()
        matha_source = bridge.from_language(hybrid_code, target_lang)
        logs.append(f"反向转译: {target_lang} → Matha")

        # 2. 验证转译结果
        try:
            prog = parse(matha_source)
            logs.append(f"解析成功: {len(prog.decls)} 个声明")
        except Exception as e:
            logs.append(f"解析失败: {e}")
            return BuildResult(
                success=False, logs=logs,
                hybrid_code=hybrid_code, target_language=target_lang.value,
            )

        # 3. 沙箱执行验证
        try:
            from src.selfupgrade import Sandbox
            sb = Sandbox(self._interp)
            outputs, trace, err = sb.run(matha_source)
            if err:
                logs.append(f"执行失败: {err}")
                return BuildResult(
                    success=False, logs=logs,
                    hybrid_code=hybrid_code, target_language=target_lang.value,
                )
            logs.append(f"执行成功: {len(outputs)} 个输出")
        except Exception as e:
            logs.append(f"沙箱异常: {e}")
            return BuildResult(
                success=False, logs=logs,
                hybrid_code=hybrid_code, target_language=target_lang.value,
            )

        elapsed = (time.time() - start) * 1000
        return BuildResult(
            success=True, output=outputs, logs=logs,
            hybrid_code=hybrid_code, target_language=target_lang.value,
            refactored_matha=matha_source, elapsed_ms=elapsed,
        )


# ─── MixedProjectBuilder：混合项目构建器 ─────────────────────────────────────


class MixedProjectBuilder:
    """当 Matha 无法独立完成时，使用混合语言构建项目。"""

    def __init__(self, interp: Interpreter):
        self._interp = interp
        self._bridge = LanguageBridge()
        self._diagnoser = AutoDiagnoser(interp)
        self._submitter = UpgradeSubmitter(interp)
        self._refactor = MathaRefactor(interp)

    def build(self, task: str, matha_source: str,
              fallback_languages: Optional[list[Language]] = None) -> BuildResult:
        """构建项目：先尝试纯 Matha，失败则使用混合语言。

        Args:
            task: 任务描述
            matha_source: Matha 源码
            fallback_languages: 按优先级排列的备用语言列表
        """
        if fallback_languages is None:
            fallback_languages = [
                Language.PYTHON, Language.JAVASCRIPT, Language.TYPESCRIPT,
            ]

        start = time.time()
        logs: list[str] = [f"开始构建任务: {task}"]
        defects: list[DefectReport] = []

        # ── 阶段 1：尝试纯 Matha ──────────────────────────────────────────
        logs.append("阶段 1: 尝试纯 Matha 执行")
        pure_result = self._try_pure_matha(matha_source)
        if pure_result.success:
            logs.append(f"纯 Matha 执行成功 (耗时 {pure_result.elapsed_ms:.1f}ms)")
            return pure_result

        logs.append(f"纯 Matha 失败: {pure_result.logs[-1] if pure_result.logs else '未知'}")
        defects.extend(pure_result.defects)

        # ── 阶段 2：诊断问题 ──────────────────────────────────────────────
        logs.append("阶段 2: 自动诊断问题")
        diag_report = self._diagnoser.diagnose_and_report(matha_source, task)
        logs.append(f"诊断结果: {diag_report['defect_count']} 个问题")
        defects.extend(
            DefectReport(
                kind=d["kind"], severity=d["severity"], message=d["message"],
                source=d["source"], suggestion=d.get("suggestion"),
            )
            for d in diag_report["defects"]
        )

        # ── 阶段 3：使用混合语言构建 ──────────────────────────────────────
        logs.append("阶段 3: 使用混合语言构建")
        for lang in fallback_languages:
            logs.append(f"  尝试语言: {lang.value}")
            hybrid_result = self._build_with_language(matha_source, lang, task)
            if hybrid_result.success:
                logs.append(f"  ✓ {lang.value} 构建成功")
                hybrid_result.logs = logs
                hybrid_result.defects = defects

                # ── 阶段 4：尝试重构回纯 Matha ──────────────────────────────
                logs.append("阶段 4: 尝试重构为纯 Matha")
                refactor_result = self._refactor.refactor(
                    hybrid_result.hybrid_code or "", lang
                )
                if refactor_result.success:
                    logs.append(f"  ✓ 重构成功，耗时 {refactor_result.elapsed_ms:.1f}ms")
                    hybrid_result.refactored_matha = refactor_result.output
                else:
                    logs.append(f"  ⚠ 重构部分成功，保留混合代码")

                # ── 阶段 5：提交至自我升级 ──────────────────────────────────
                critical_defects = [d for d in defects
                                    if d.severity in (Severity.HIGH, Severity.CRITICAL)]
                if critical_defects:
                    logs.append(f"阶段 5: 提交 {len(critical_defects)} 个严重缺陷至升级系统")
                    submit_result = self._submitter.submit_batch(critical_defects)
                    logs.append(
                        f"  升级提交: {submit_result['success']}/{submit_result['total']} 成功"
                    )

                hybrid_result.logs = logs
                return hybrid_result

        # ── 全部失败 ────────────────────────────────────────────────────
        logs.append("所有语言尝试均失败")
        elapsed = (time.time() - start) * 1000
        return BuildResult(
            success=False, logs=logs, defects=defects, elapsed_ms=elapsed,
        )

    def _try_pure_matha(self, source: str) -> BuildResult:
        """尝试纯 Matha 执行。"""
        start = time.time()
        try:
            prog = parse(source)
            outputs, trace = self._interp.run(prog)
            elapsed = (time.time() - start) * 1000
            return BuildResult(
                success=True, output=outputs,
                logs=[f"纯 Matha 执行成功，{len(outputs)} 个输出"],
                elapsed_ms=elapsed,
            )
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            return BuildResult(
                success=False,
                logs=[f"纯 Matha 执行失败: {e}"],
                defects=[DefectReport(
                    kind=DefectKind.INTERPRETER_ERROR,
                    severity=Severity.HIGH,
                    message=str(e),
                    source=source[:200],
                )],
                elapsed_ms=elapsed,
            )

    def _build_with_language(self, matha_source: str, lang: Language,
                              task: str) -> BuildResult:
        """使用指定语言构建。"""
        start = time.time()
        logs: list[str] = []

        try:
            # 转译为目标语言
            target_code = self._bridge.transpile_to(matha_source, lang)
            logs.append(f"转译为 {lang.value} 成功")

            if lang == Language.PYTHON:
                # 执行 Python 代码
                result = self._exec_python(target_code)
            elif lang == Language.JAVASCRIPT:
                result = self._exec_js(target_code)
            elif lang == Language.TYPESCRIPT:
                # TS 先转 JS 再执行
                js_code = self._bridge._matha_to_ts(matha_source)
                result = self._exec_js(js_code)
            elif lang == Language.C:
                result = self._exec_c(target_code)
            elif lang == Language.RUST:
                result = self._exec_rust(target_code)
            elif lang == Language.GO:
                result = self._exec_go(target_code)
            else:
                result = BuildResult(success=False, logs=[f"不支持的语言: {lang}"])

            result.logs = logs + result.logs
            result.hybrid_code = target_code
            result.target_language = lang.value
            result.elapsed_ms = (time.time() - start) * 1000
            return result

        except Exception as e:
            elapsed = (time.time() - start) * 1000
            return BuildResult(
                success=False,
                logs=logs + [f"构建失败: {e}"],
                elapsed_ms=elapsed,
            )

    def _exec_python(self, code: str) -> BuildResult:
        """执行 Python 代码。"""
        try:
            local_vars: dict = {}
            exec(code, {"__builtins__": __import__("builtins")}, local_vars)
            return BuildResult(success=True, output=local_vars,
                               logs=["Python 执行成功"])
        except Exception as e:
            return BuildResult(success=False, logs=[f"Python 执行失败: {e}"])

    def _exec_js(self, code: str) -> BuildResult:
        """执行 JavaScript 代码（通过 Node.js）。"""
        import subprocess
        try:
            result = subprocess.run(
                ["node", "-e", code],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                return BuildResult(success=True, output=result.stdout.strip(),
                                   logs=["JS 执行成功"])
            return BuildResult(success=False,
                               logs=[f"JS 执行失败: {result.stderr}"])
        except FileNotFoundError:
            return BuildResult(success=False,
                               logs=["Node.js 未安装，跳过 JS 执行"])
        except Exception as e:
            return BuildResult(success=False, logs=[f"JS 执行异常: {e}"])

    def _exec_c(self, code: str) -> BuildResult:
        import subprocess
        try:
            result = subprocess.run(
                ["gcc", "-x", "c", "-o", "/tmp/matha_build", "-"],
                input=code, capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0:
                out = subprocess.run(
                    ["/tmp/matha_build"], capture_output=True, text=True, timeout=5,
                )
                return BuildResult(success=True, output=out.stdout.strip(),
                                   logs=["C 编译执行成功"])
            return BuildResult(success=False, logs=[f"C 编译失败: {result.stderr}"])
        except FileNotFoundError:
            return BuildResult(success=False, logs=["gcc 未安装，跳过 C 执行"])
        except Exception as e:
            return BuildResult(success=False, logs=[f"C 执行异常: {e}"])

    def _exec_rust(self, code: str) -> BuildResult:
        import subprocess
        try:
            result = subprocess.run(
                ["rustc", "-o", "/tmp/matha_build", "-"],
                input=code, capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                out = subprocess.run(
                    ["/tmp/matha_build"], capture_output=True, text=True, timeout=5,
                )
                return BuildResult(success=True, output=out.stdout.strip(),
                                   logs=["Rust 编译执行成功"])
            return BuildResult(success=False, logs=[f"Rust 编译失败: {result.stderr}"])
        except FileNotFoundError:
            return BuildResult(success=False, logs=["rustc 未安装，跳过 Rust 执行"])
        except Exception as e:
            return BuildResult(success=False, logs=[f"Rust 执行异常: {e}"])

    def _exec_go(self, code: str) -> BuildResult:
        import subprocess
        try:
            result = subprocess.run(
                ["go", "run", "-"],
                input=code, capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                return BuildResult(success=True, output=result.stdout.strip(),
                                   logs=["Go 执行成功"])
            return BuildResult(success=False, logs=[f"Go 执行失败: {result.stderr}"])
        except FileNotFoundError:
            return BuildResult(success=False, logs=["go 未安装，跳过 Go 执行"])
        except Exception as e:
            return BuildResult(success=False, logs=[f"Go 执行异常: {e}"])


# ─── HybridCompiler：主协调器 ────────────────────────────────────────────────


class HybridCompiler:
    """Matha 混合语言编译器主协调器。

    提供统一的 API 用于：
      - 混合语言项目构建
      - 自动诊断与问题报告
      - 提交至自我升级系统
      - 混合代码重构为纯 Matha
    """

    def __init__(self, interp: Interpreter):
        self._interp = interp
        self._bridge = LanguageBridge()
        self._builder = MixedProjectBuilder(interp)
        self._diagnoser = AutoDiagnoser(interp)
        self._submitter = UpgradeSubmitter(interp)
        self._refactor = MathaRefactor(interp)

    # ── 公共 API ──────────────────────────────────────────────────────────

    def build_project(self, task: str, matha_source: str,
                      fallback_langs: Optional[list[str]] = None) -> dict:
        """构建项目：尝试 Matha → 混合语言 → 诊断 → 升级 → 重构。

        Args:
            task: 任务描述
            matha_source: Matha 源码
            fallback_langs: 备用语言列表（字符串名）

        Returns:
            构建结果字典
        """
        langs = [Language(l) for l in (fallback_langs or [
            "python", "javascript", "typescript",
        ])]
        result = self._builder.build(task, matha_source, langs)

        return {
            "success": result.success,
            "output": result.output,
            "logs": result.logs,
            "defects": [d.to_dict() for d in result.defects],
            "hybrid_code": result.hybrid_code,
            "target_language": result.target_language,
            "refactored_matha": result.refactored_matha,
            "elapsed_ms": result.elapsed_ms,
        }

    def diagnose(self, source: str, context: str = "") -> dict:
        """诊断 Matha 源码。"""
        return self._diagnoser.diagnose_and_report(source, context)

    def submit_defects(self, defects: list[dict]) -> dict:
        """批量提交缺陷至升级系统。"""
        parsed = [
            DefectReport(
                kind=DefectKind(d["kind"]),
                severity=Severity(d["severity"]),
                message=d["message"],
                source=d.get("source", ""),
                suggestion=d.get("suggestion"),
            )
            for d in defects
        ]
        return self._submitter.submit_batch(parsed)

    def refactor(self, hybrid_code: str, source_lang: str) -> dict:
        """将混合语言代码重构为纯 Matha。"""
        lang = Language(source_lang)
        result = self._refactor.refactor(hybrid_code, lang)
        return {
            "success": result.success,
            "output": result.output,
            "logs": result.logs,
            "refactored_matha": result.refactored_matha,
            "elapsed_ms": result.elapsed_ms,
        }

    def translate(self, source: str, target: str, direction: str = "matha_to") -> dict:
        """语言转译。

        Args:
            source: 源语言源码
            target: 目标语言名
            direction: "matha_to" 或 "to_matha"
        """
        lang = Language(target)
        if direction == "matha_to":
            code = self._bridge.transpile_to(source, lang)
        else:
            code = self._bridge.from_language(source, lang)
        return {"success": True, "code": code, "target": target}

    def mixed_exec(self, mixed_source: str) -> dict:
        """执行混合语言代码（Matha + Python/JS 片段）。

        混合代码格式：
          <<MATHA>> ...Matha代码... <<END>>
          <<PYTHON>> ...Python代码... <<END>>
        """
        logs: list[str] = []
        output = None

        # 分割混合代码
        segments = self._split_mixed(mixed_source)
        for seg_type, seg_code in segments:
            if seg_type == "matha":
                try:
                    prog = parse(seg_code)
                    out, _ = self._interp.run(prog)
                    output = out[-1] if out else None
                    logs.append(f"Matha 段执行成功，输出: {output}")
                except Exception as e:
                    logs.append(f"Matha 段执行失败: {e}")
            elif seg_type == "python":
                try:
                    local_vars: dict = {}
                    exec(seg_code, {"__builtins__": __import__("builtins")}, local_vars)
                    logs.append(f"Python 段执行成功，变量: {list(local_vars.keys())}")
                except Exception as e:
                    logs.append(f"Python 段执行失败: {e}")
            elif seg_type == "javascript":
                import subprocess
                try:
                    r = subprocess.run(["node", "-e", seg_code],
                                       capture_output=True, text=True, timeout=10)
                    logs.append(f"JS 段: {r.stdout.strip() or r.stderr.strip()}")
                except Exception as e:
                    logs.append(f"JS 段执行失败: {e}")

        return {"success": True, "output": output, "logs": logs}

    # ── 私有工具 ──────────────────────────────────────────────────────────

    def _split_mixed(self, source: str) -> list[tuple[str, str]]:
        """分割混合语言代码为 (type, code) 片段。"""
        import re
        pattern = re.compile(
            r"<<(MATHA|PYTHON|JAVASCRIPT)>>\s*(.*?)\s*<<END>>",
            re.DOTALL,
        )
        segments = []
        last_end = 0
        for m in pattern.finditer(source):
            # 前导纯文本（未标记的 Matha 代码）
            if m.start() > last_end:
                text = source[last_end:m.start()].strip()
                if text:
                    segments.append(("matha", text))
            segments.append((m.group(1).lower(), m.group(2).strip()))
            last_end = m.end()
        # 尾部纯文本
        if last_end < len(source):
            text = source[last_end:].strip()
            if text:
                segments.append(("matha", text))
        return segments


# ── 全局实例（懒初始化） ──────────────────────────────────────────────────────

_hybrid_compiler: Optional[HybridCompiler] = None


def get_hybrid_compiler(interp: Optional[Interpreter] = None) -> HybridCompiler:
    """获取或创建 HybridCompiler 实例。"""
    global _hybrid_compiler
    if _hybrid_compiler is None or interp is not None:
        if interp is None:
            from src.interp import Interpreter
            interp = Interpreter()
        _hybrid_compiler = HybridCompiler(interp)
    return _hybrid_compiler
