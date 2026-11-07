"""
Matha 自然语言 → 公式代码 统一管线（NL Pipeline）

整合全流程：
  NL输入
    ↓
  [nl_semantic.py]  时代语义词典 — 理解每个词的语义
    ↓
  [nl_definition.py] 定义构建器 — 列明条目 + 赋予当前时代定义
    ↓
  [nl_to_formula.py] 公式转换器 — 定义 → 公式代码（预览形态）
    ↓
  [阶段4：本模块]    执行段 — 纯算术公式 → 可执行 Matha（func 定义 + 单位探针）
    ↓
  [kernel/exec_api]  主链执行（lexer → parser → mbc.compiler → mbc.vm）

阶段4 的诚实边界：nl_to_formula 的预览源码（`let …`、`^`、`#` 注释）不是
可执行 Matha（Matha 唯一注释形式为 `(* … *)`，`^` 是异或）；执行段只把
**纯算术等式**保守翻译为 `func 名(自由参数) -> Float = 右式`（`^`→`**`），
并附全参数=1.0 的探针调用验证可执行性——探针不是用户语义的答案。
集合运算/含函数调用/仅声明/非 ASCII 符号一律跳过并如实记入 execution_notes；
执行错误不吞，沉入 execution_error。口径见 docs/KNOWN_ISSUES.md §7c。

同时提供：
  - 多时代对比（同一文本在不同时代的定义差异）
  - 歧义检测与报告
  - 公式代码预览
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.kernel import exec_api
from src.nl_definition import DefinitionBuilder, DefinitionItem, DefinitionResult
from src.nl_semantic import NLDictionary
from src.nl_to_formula import (
    DefinitionToFormulaConverter,
    FormulaCode,
    FormulaTranslation,
)

# ============================================================
#  管线结果
# ============================================================

@dataclass
class PipelineResult:
    """统一管线的最终输出。"""
    # 原始输入
    original_text: str
    era: str

    # 阶段1：语义理解
    semantic_map: dict[str, str]  # {词: 当前时代语义}

    # 阶段2：定义构建
    definition_result: DefinitionResult | None = None

    # 阶段3：公式转换
    formula_translation: FormulaTranslation | None = None

    # 阶段4：执行段（纯算术公式 → 可执行 Matha；空串 = 无可执行公式）
    executable_code: str = ""
    # 探针输出（全参数=1.0 的验证调用，非用户语义答案）
    outputs: list = field(default_factory=list)
    # 执行错误（不抛出，如实下沉；None = 无错误或未执行）
    execution_error: str | None = None
    # 跳过/降级说明
    execution_notes: list[str] = field(default_factory=list)

    # 歧义报告
    ambiguities: list[dict] = field(default_factory=list)

    # 整体摘要
    summary: str = ""

    def is_complete(self) -> bool:
        """管线是否成功完成。"""
        return (
            self.definition_result is not None
            and self.formula_translation is not None
            and bool(self.formula_translation.formula_codes)
        )

    def has_ambiguities(self) -> bool:
        """是否存在歧义。"""
        return len(self.ambiguities) > 0


# ============================================================
#  统一管线
# ============================================================

class NLPipeline:
    """
    自然语言 → 公式代码 统一管线。

    用法：
      pipeline = NLPipeline()
      result = pipeline.run("速度的定义是位移除以时间")
      print(result.formula_translation.matha_source)
    """

    def __init__(self):
        self._dict = NLDictionary()
        self._builder = DefinitionBuilder(self._dict)
        self._converter = DefinitionToFormulaConverter()

    def run(self, text: str, era: str = "当代") -> PipelineResult:
        """
        执行完整管线。

        Args:
            text: 自然语言输入
            era: 目标时代（默认"当代"）

        Returns:
            PipelineResult
        """
        # ── 阶段1：语义理解 ──────────────────────────────────────
        semantic_map = self._dict.build_semantic_map(text, era=era)
        semantic_desc = {word: entry.meaning for word, entry in semantic_map.items()}

        # ── 阶段2：定义构建 ──────────────────────────────────────
        def_result = self._builder.build(text, era=era)

        # ── 阶段3：公式转换 ──────────────────────────────────────
        formula_trans = self._converter.convert(def_result)

        # ── 歧义检测 ─────────────────────────────────────────────
        ambiguities = self._detect_ambiguities(def_result.items)

        # ── 阶段4：执行段（主链 exec_api，错误不吞） ─────────────
        executable_code, exec_notes = self._build_executable(formula_trans)
        outputs: list = []
        execution_error: str | None = None
        if executable_code:
            out, err = exec_api.run_checked(executable_code)
            outputs = out
            if err is not None:
                execution_error = f"{type(err).__name__}: {err}"

        # ── 生成摘要 ─────────────────────────────────────────────
        summary = self._build_summary(text, era, def_result, formula_trans, ambiguities)

        return PipelineResult(
            original_text=text,
            era=era,
            semantic_map=semantic_desc,
            definition_result=def_result,
            formula_translation=formula_trans,
            executable_code=executable_code,
            outputs=outputs,
            execution_error=execution_error,
            execution_notes=exec_notes,
            ambiguities=ambiguities,
            summary=summary,
        )

    def run_multi_era(self, text: str, eras: list[str] | None = None) -> dict[str, PipelineResult]:
        """
        多时代对比：同一文本在不同时代的定义差异。

        Args:
            text: 自然语言输入
            eras: 要对比的时代列表（默认全部）

        Returns:
            {era: PipelineResult}
        """
        if eras is None:
            eras = ["先秦", "汉唐", "宋元", "明清", "近代", "现代", "当代"]

        results = {}
        for era in eras:
            results[era] = self.run(text, era=era)
        return results

    def format_report(self, result: PipelineResult) -> str:
        """
        将管线结果格式化为可读报告。

        输出格式：
          ╔══════════════════════════════════════════════════╗
          │  自然语言 → 公式代码 转换报告                     │
          ╠══════════════════════════════════════════════════╣
          │  原文：...                                       │
          │  时代：...                                       │
          ╠══════════════════════════════════════════════════╣
          │  【阶段1：语义理解】                              │
          │    速度 → 位移对时间的变化率                      │
          │    时间 → ...                                    │
          ╠══════════════════════════════════════════════════╣
          │  【阶段2：定义构建】                              │
          │    [1] 速度                                      │
          │      各时代语义：                                 │
          │        [近代] 位移对时间的变化率 (v = ds/dt)      │
          │      当前定义：位移对时间的变化率                  │
          │      符号：v                                     │
          ╠══════════════════════════════════════════════════╣
          │  【阶段3：公式转换】                              │
          │    let 速度 = v = s / t                          │
          ╠══════════════════════════════════════════════════╣
          │  【阶段4：执行段（主链）】                        │
          │    func 速度(s, t) -> Float = s / t              │
          │    探针输出：[1.0]                               │
          ╠══════════════════════════════════════════════════╣
          │  【歧义报告】                                     │
          │    无歧义                                        │
          ╚══════════════════════════════════════════════════╝
        """
        lines = []
        lines.append("╔════════════════════════════════════════════════════════════╗")
        lines.append("║  自然语言 → 公式代码 转换报告                               ║")
        lines.append("╠════════════════════════════════════════════════════════════╣")
        lines.append(f"║  原文：{result.original_text:<48}║")
        lines.append(f"║  时代：{result.era:<48}║")
        lines.append("╠════════════════════════════════════════════════════════════╣")

        # 阶段1：语义理解
        lines.append("║  【阶段1：语义理解】                                        ║")
        for word, meaning in result.semantic_map.items():
            lines.append(f"║    {word:<6} → {meaning:<40}║")
        lines.append("╠════════════════════════════════════════════════════════════╣")

        # 阶段2：定义构建
        lines.append("║  【阶段2：定义构建】                                        ║")
        if result.definition_result:
            for i, item in enumerate(result.definition_result.items, 1):
                flag = " ★歧义" if item.is_ambiguous else ""
                lines.append(f"║    [{i}] {item.raw_word}{flag}{' '*(38-len(item.raw_word)-len(flag))}║")
                lines.append(f"║        定义：{item.definition:<45}║")
                lines.append(f"║        符号：{item.math_symbol:<45}║")
                lines.append(f"║        公式：{item.math_expr:<45}║")
        else:
            lines.append("║    （无定义条目）                                            ║")
        lines.append("╠════════════════════════════════════════════════════════════╣")

        # 阶段3：公式转换
        lines.append("║  【阶段3：公式转换】                                        ║")
        if result.formula_translation:
            if result.formula_translation.formula_codes:
                for code in result.formula_translation.formula_codes:
                    lines.append(f"║    {code.matha_code:<48}║")
                if result.formula_translation.param_equivalences:
                    lines.append("║    参数等价：")
                    for lhs, rhs in result.formula_translation.param_equivalences:
                        lines.append(f"║      {lhs} = {rhs}")
            else:
                lines.append("║    （未生成公式，可能无可识别的数学词汇）                      ║")
            if result.formula_translation.notes:
                for note in result.formula_translation.notes:
                    lines.append(f"║    注：{note:<44}║")
        lines.append("╠════════════════════════════════════════════════════════════╣")

        # 阶段4：执行段
        lines.append("║  【阶段4：执行段（主链）】                                    ║")
        if result.executable_code:
            for line in result.executable_code.split("\n"):
                lines.append(f"║    {line}")
            if result.execution_error:
                lines.append(f"║    执行错误：{result.execution_error}")
            else:
                lines.append(f"║    探针输出：{result.outputs}")
        else:
            lines.append("║    （无可执行公式）                                          ║")
        for note in result.execution_notes:
            lines.append(f"║    注：{note}")
        lines.append("╠════════════════════════════════════════════════════════════╣")

        # 歧义报告
        lines.append("║  【歧义报告】                                               ║")
        if result.ambiguities:
            for amb in result.ambiguities:
                lines.append(f"║    ⚠ {amb['word']}: {amb['note']}")
        else:
            lines.append("║    无歧义                                                    ║")
        lines.append("╠════════════════════════════════════════════════════════════╣")

        # 完整源码
        lines.append("║  【Matha 源码】                                             ║")
        if result.formula_translation:
            for line in result.formula_translation.matha_source.split("\n"):
                lines.append(f"║    {line:<48}║")
        else:
            lines.append("║    （暂无源码）                                              ║")
        lines.append("╚════════════════════════════════════════════════════════════╝")

        return "\n".join(lines)

    # ── 辅助方法 ──────────────────────────────────────────────────

    #: 执行段只接纯算术类别；set_op/stat/prob/nn/optim/declaration 一律跳过
    _EXEC_CATEGORIES = frozenset({"linear", "area", "perimeter", "volume", "general"})
    _EXEC_RHS_RE = re.compile(r"[A-Za-z0-9_.+\-*/() \t]+")
    _EXEC_CALL_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\s*\(")
    _EXEC_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
    _EXEC_CONSTANTS = frozenset({"pi", "e", "tau", "phi"})

    def _translate_formula(self, code: FormulaCode) -> tuple[str, str] | None:
        """纯算术等式 → (func 定义行, 单位探针行)；不可译则 None。"""
        if code.category not in self._EXEC_CATEGORIES:
            return None
        if any(c in code.name for c in " ()=+-*/^,") or not code.name:
            return None
        text = code.expr_text
        if "=" not in text:
            return None
        lhs, rhs = (s.strip() for s in text.split("=", 1))
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", lhs):
            return None
        rhs = rhs.replace("^", "**")
        if not self._EXEC_RHS_RE.fullmatch(rhs) or self._EXEC_CALL_RE.search(rhs):
            return None
        params = list(dict.fromkeys(
            i for i in self._EXEC_IDENT_RE.findall(rhs)
            if i != lhs and i not in self._EXEC_CONSTANTS))
        if not params:
            return None
        # func 直expr体以 `(` 开头会被解析为 lambda 参数列（`(c) => …` 语法）；
        # 前置乘法单位元 1.0 * 保持浮点语义逐值不变（含 -0.0/inf/NaN）
        if rhs.startswith("("):
            rhs = "1.0 * " + rhs
        func_line = f"func {code.name}({', '.join(params)}) -> Float = {rhs}"
        probe_args = ", ".join(["1.0"] * len(params))
        probe_line = f"#1：[{code.name}({probe_args})]"
        return func_line, probe_line

    def _build_executable(self, trans: FormulaTranslation) -> tuple[str, list[str]]:
        """阶段4：把可译公式拼成可执行源码；跳过项如实记注。"""
        notes: list[str] = []
        blocks: list[str] = []
        for code in trans.formula_codes:
            translated = self._translate_formula(code)
            if translated is None:
                notes.append(
                    f"跳过 {code.name}（{code.category}）：非纯算术等式，执行段不背书")
                continue
            blocks.extend(translated)
        if not blocks:
            return "", notes
        header = ("(* 由自然语言管线阶段4生成：func 定义 + 单位探针"
                  "（全参数=1.0，仅验证可执行性，非用户语义答案） *)")
        return "\n".join([header] + blocks), notes

    def _detect_ambiguities(self, items: list[DefinitionItem]) -> list[dict]:
        """检测定义条目中的歧义。"""
        ambiguities = []
        for item in items:
            if item.is_ambiguous:
                eras = [e.era for e in item.era_semantics]
                ambiguities.append({
                    "word": item.raw_word,
                    "eras": eras,
                    "note": f"在{len(eras)}个时代有不同语义，当前选用[{item.current_entry.era}]",
                })
        return ambiguities

    def _build_summary(
        self,
        text: str,
        era: str,
        def_result: DefinitionResult,
        formula_trans: FormulaTranslation,
        ambiguities: list[dict],
    ) -> str:
        """生成管线摘要。"""
        n_formulas = len(formula_trans.formula_codes)
        n_ambiguities = len(ambiguities)
        status = "成功" if n_formulas > 0 else "无公式生成"
        amb_str = f"，{n_ambiguities}个歧义" if n_ambiguities > 0 else ""
        return f"'{text}' → {era}时代 → {n_formulas}个公式{amb_str} → [{status}]"


# ============================================================
#  便捷函数
# ============================================================

_pipeline: NLPipeline | None = None


def run(text: str, era: str = "当代") -> PipelineResult:
    """便捷入口：执行自然语言→公式代码管线。"""
    global _pipeline
    if _pipeline is None:
        _pipeline = NLPipeline()
    return _pipeline.run(text, era=era)


def report(text: str, era: str = "当代") -> str:
    """便捷入口：格式化输出转换报告。"""
    global _pipeline
    if _pipeline is None:
        _pipeline = NLPipeline()
    result = _pipeline.run(text, era=era)
    return _pipeline.format_report(result)


def multi_era_compare(text: str, eras: list[str] | None = None) -> dict[str, PipelineResult]:
    """多时代对比。"""
    global _pipeline
    if _pipeline is None:
        _pipeline = NLPipeline()
    return _pipeline.run_multi_era(text, eras)
