"""Matha Jupyter 集成

提供：
1. IPython 魔法命令（%matha, %%matha）
2. 自然语言意图 → Matha 代码 → 主链 exec_api 真算
3. MIR 预览（仅展示，不参与执行）

【定位 2026-11 · 阶段 2 AI 修复】历史链路把 MIRNode 对象传给只接受 str 的
execute_mir（必 AttributeError），回退 interpret 同样吃不下 MIRNode，%matha
从未算出过结果。现改为 intent.suggested_code 经 src.kernel.exec_api.run_checked
真算；错误下沉到展示层。口径见 docs/KNOWN_ISSUES.md §7c：编排契约已锁，
自然语言→代码的输出正确性不背书（正则兜底仅覆盖算术/平方根等窄路径；
分解器的裸 `#` 兜底标记被显式拒绝，不静默假成功）。

用法（仓库根目录）：
  %load_ext src.jupyter.matha_magic
  %matha 计算 3 加 5
  %%matha
  求 16 的平方根
"""
from __future__ import annotations

import re
import sys
from typing import Any

# 确保项目路径在 sys.path 中
sys.path.insert(0, '.')

_RESULT_BIND_RE = re.compile(r"^\s*result\s*=", re.M)
_OUTPUT_DIRECTIVE_RE = re.compile(r"^\s*#\d*：\[", re.M)
_MATHA_HASH_UNIT_RE = re.compile(r"^\s*#\d*：")


class MathaMagics:
    """Matha Jupyter 魔法命令。

    execute() 是可测试核心：IPython 未安装时魔法注册静默跳过，
    但 execute() 仍可用（展示降级为 print）。
    """

    def __init__(self, shell):
        self.shell = shell
        self._init_magics()

    def execute(self, code: str) -> Any:
        """自然语言 → 意图 → Matha 主链执行；返回末条输出，无输出/出错返回 None。"""
        try:
            from src.intent.llm_parser import LLMIntentParser
            from src.intent.mir_generator import MIRGenerator
            from src.kernel import exec_api

            intent = LLMIntentParser().parse(code)
            mir_node = MIRGenerator().generate(intent)

            source, skip_reason = self._prepare_source(intent.suggested_code)
            outputs: list[Any] = []
            error: BaseException | None = None
            if source:
                outputs, error = exec_api.run_checked(source)

            self._display_result(code, intent, mir_node, source, outputs, error, skip_reason)
            if error is not None:
                return None
            return outputs[-1] if outputs else None
        except Exception as e:
            print(f"[Matha] 执行失败: {e}")
            return None

    def _prepare_source(self, suggested: str) -> tuple[str, str]:
        """suggested_code → (可执行源码, 跳过原因)。

        分解器兜底标记（`# 无法映射: …`）以裸 `#` 开头：Matha 中这不是注释
        而是外来声明前缀，主链会静默 NOOP。在此显式拒绝，避免把「没算」
        伪装成「无输出」。
        """
        source = (suggested or "").strip()
        if not source:
            return "", "意图未产出代码"
        for line in source.splitlines():
            if line.lstrip().startswith("#") and not _MATHA_HASH_UNIT_RE.match(line):
                return "", f"含裸 `#` 行（非 Matha 注释/输出指令），未执行: {line.strip()}"
        if _RESULT_BIND_RE.search(source) and not _OUTPUT_DIRECTIVE_RE.search(source):
            source += "\n#1：[result]"
        return source, ""

    def _display_result(self, code, intent, mir_node, source, outputs, error, skip_reason):
        lines = [
            "## Matha 计算结果",
            "",
            f"**输入**: {code}",
            "",
            f"**意图类型**: {intent.intent_type.name}",
            f"**置信度**: {intent.confidence:.2f}",
        ]
        if intent.errors:
            lines.append("**解析说明**: " + "; ".join(str(e) for e in intent.errors))
        lines += [
            "",
            "**MIR 预览（仅展示，不参与执行）**:",
            "```matha",
            mir_node.to_math_code(),
            "```",
        ]
        if source:
            lines += ["", "**执行的 Matha 代码**:", "```matha", source, "```"]
        if skip_reason:
            lines.append(f"**未执行**: {skip_reason}")
        if error is not None:
            lines.append(f"**执行错误**: {type(error).__name__}: {error}")
        if outputs:
            lines.append(f"**输出**: {outputs}")
        elif error is None and not skip_reason:
            lines.append("**输出**: 无（主链未产生可观察输出）")
        text = "\n".join(lines)
        try:
            from IPython.display import Markdown, display
            display(Markdown(text))
        except ImportError:
            print(text)

    def _init_magics(self):
        """注册 IPython 魔法命令（可选导入，未安装时静默跳过注册）。"""
        try:
            from IPython.core.magic import (
                Magics,
                magics_class,
                register_cell_magic,
                register_line_magic,
            )
        except ImportError:
            return

        outer = self

        @magics_class
        class MathaMagicsClass(Magics):
            @register_line_magic
            def matha(self, line: str) -> Any:
                """单行自然语言：%matha 计算 3 加 5"""
                return outer.execute(line)

            @register_cell_magic
            def matha(self, line: str, cell: str) -> Any:  # noqa: F811
                """多行单元：%%matha（单元体为自然语言）"""
                return outer.execute(cell.strip())

        if hasattr(self.shell, "register_magics"):
            self.shell.register_magics(MathaMagicsClass)


def load_ipython_extension(ipython):
    """IPython 扩展加载入口。"""
    MathaMagics(ipython)
    print("[Matha] Jupyter 扩展已加载")
    print("  %matha <表达式>     — 执行单行 Matha 代码")
    print("  %%matha             — 执行多行 Matha 代码")


def unload_ipython_extension(ipython):
    """IPython 扩展卸载入口。"""
    print("[Matha] Jupyter 扩展已卸载")


# ============================================================
# 使用示例
# ============================================================

"""
# Notebook 使用示例（仓库根目录）

## 1. 加载扩展
%load_ext src.jupyter.matha_magic

## 2. 单行计算（正则兜底窄路径：四则运算 / 平方根等）
%matha 计算 3 加 5
%matha 求 16 的平方根

## 3. 多行单元
%%matha
计算 3 加 5

## 不支持的输入会显式拒绝/错误下沉，不静默假成功：
##   %matha 计算 100 以内所有素数   ← 范围语义，分解器无法映射
##   %matha 求解方程 x^2 - 3x + 2 = 0 ← 方程求解未接主链
"""
