# -*- coding: utf-8 -*-
"""Matha 增强意图解析器 — v2.3

在 v2.2 基础上集成结构化异常系统，支持：
  1. 精确错误定位（阶段 + 行号 + 列号）
  2. 错误链传播（cause + children）
  3. 自动恢复策略
  4. 用户友好错误报告
  5. Result 类型错误传播（? 运算符语义）
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Any, Optional
from src.intent_parser import IntentParser as IntentParserBase, Intent, IntentType
from src.errors import (
    MathaError, ErrorStage, ErrorSeverity,
    ParseError, ClassifyError, ParamExtractError,
    CodeGenError, ExecError, CompositeError,
    RecoveryStrategy, err_with_stage, map_errors,
    classify_error, parse_error, param_error,
    codegen_error, exec_error, composite_error,
    ok_with_context,
)
from src.result import Ok, Err
Result = type


# ============================================================
# 增强意图解析器
# ============================================================

class EnhancedIntentParser(IntentParserBase):
    """增强意图解析器 — 带结构化异常处理。"""

    def parse(self, text: str, target_lang: str = "python") -> Result:
        """解析自然语言，返回 Result[Intent, MathaError]。"""
        if not text or not text.strip():
            return Err(classify_error("输入为空", ["请提供非空文本"]))

        intent = Intent(
            intent_type=IntentType.UNKNOWN,
            description=text.strip(),
            target_lang=target_lang,
            confidence=0.0,
        )

        # Step 1: 意图分类（带错误处理）
        classify_result = self._classify_with_recovery(text, intent)
        if classify_result.is_err():
            return classify_result

        # Step 2: 参数提取（带错误处理）
        param_result = self._extract_params_with_recovery(text, intent)
        if param_result.is_err():
            # 参数提取失败不阻断，降级为 WARNING
            intent.errors.append(param_result.err())
            intent.confidence = max(0.0, intent.confidence - 0.1)

        # Step 3: 置信度评估
        intent.confidence = self._calc_confidence(intent, text)
        if intent.confidence < 0.3:
            return Err(classify_error(
                f"置信度太低 ({intent.confidence:.0%})，无法识别意图",
                candidates=self._get_candidates(text)
            ))

        # Step 4: 代码生成
        code_result = self._generate_code(intent)
        if code_result.is_err():
            return code_result

        return Ok(intent)

    def _classify_with_recovery(
        self, text: str, intent: Intent
    ) -> Result:
        """意图分类，带自动恢复。"""
        def do_classify():
            itype = self.classifier.classify(text)
            if itype == IntentType.UNKNOWN:
                raise classify_error(
                    "无法识别意图类型",
                    candidates=self._get_candidates(text)
                )
            intent.intent_type = itype
            intent.description = self._describe_intent(itype, text)
            return intent

        result = map_errors(do_classify, stage=ErrorStage.CLASSIFYING)
        if result.is_err():
            error = result.err()
            # 尝试恢复
            recovered = RecoveryStrategy.try_recover(error)
            if recovered:
                return Ok(intent)
        return result

    def _extract_params_with_recovery(
        self, text: str, intent: Intent
    ) -> Result:
        """参数提取，带自动恢复。"""
        def do_extract():
            nums = self.extractor.extract_numbers(text)
            vars_found = self.extractor.extract_variables(text)
            rng = self.extractor.extract_range(text)

            # 验证必需参数
            if intent.intent_type == IntentType.MATH_FUNC and not nums:
                raise param_error(
                    "数学函数需要数值参数，但未找到数字",
                    expected="数字",
                    actual="无"
                )
            if intent.intent_type == IntentType.LOOP:
                if not rng and len(nums) < 2:
                    raise param_error(
                        "循环需要范围参数（如'1到100'）或起始/结束值",
                        expected="范围(起始, 结束)",
                        actual=f"数字: {nums}"
                    )

            intent.params = {
                "numbers": nums,
                "variables": vars_found,
                "range": rng,
                "raw_text": text,
            }
            return intent

        return map_errors(do_extract, stage=ErrorStage.PARAM_EXTRACTING)

    def _generate_code(self, intent: Intent) -> Result:
        """代码生成，带错误处理。"""
        def do_generate():
            # 先生成代码（如果还没有）
            if not intent.suggested_code:
                intent.suggested_code = self.generator.generate(intent, intent.target_lang)
            return intent.suggested_code

        return map_errors(do_generate, stage=ErrorStage.CODE_GENERATING)

    def _get_candidates(self, text: str) -> list[str]:
        """获取可能的意图候选。"""
        text_lower = text.lower()
        candidates = []
        if any(kw in text_lower for kw in ['计算', '算', '求', '加减', '乘除']):
            candidates.append("算术运算")
        if any(kw in text_lower for kw in ['字符串', '文字', '文本', '反转', '拼接']):
            candidates.append("字符串操作")
        if any(kw in text_lower for kw in ['数组', '列表', '排序', '过滤']):
            candidates.append("数组操作")
        if any(kw in text_lower for kw in ['素数', '质数', '因数', '阶乘']):
            candidates.append("数学函数")
        if any(kw in text_lower for kw in ['如果', '判断', '是否']):
            candidates.append("条件判断")
        if any(kw in text_lower for kw in ['循环', '遍历', '迭代']):
            candidates.append("循环迭代")
        if any(kw in text_lower for kw in ['转换', '转化', '罗马']):
            candidates.append("类型转换")
        return candidates[:5] or ["请尝试更明确的描述"]

    def execute_and_verify(self, intent: Intent) -> Result:
        """执行意图并验证结果。"""
        def do_execute():
            if not intent.suggested_code:
                raise codegen_error("无生成代码", lang=intent.target_lang)
            # 执行代码
            local_vars = {}
            exec(intent.suggested_code, {"__builtins__": __builtins__}, local_vars)
            result = local_vars.get('result')
            if result is None:
                raise ExecError("代码执行后结果为空", Exception("result is None"))
            return result

        result = map_errors(do_execute, stage=ErrorStage.EXECUTING)
        if result.is_err():
            error = result.err()
            # 尝试恢复：使用备用执行方式
            recovered = RecoveryStrategy.try_recover(error)
            if recovered:
                return Err(recovered)
        return result

    def explain_with_errors(self, text: str) -> str:
        """解析并生成带错误信息的自然语言解释。"""
        result = self.parse(text)
        if result.is_ok():
            intent = result.unwrap()
            return self.explain(intent)
        else:
            error = result.err()
            return self._format_error_report(error, text)

    def _format_error_report(self, error: MathaError, original_text: str) -> str:
        """格式化错误报告。"""
        lines = [
            "=" * 50,
            "意图解析失败报告",
            "=" * 50,
            f"输入: {original_text!r}",
            "",
            error.report(),
            "",
            error.suggestions_text(),
            "=" * 50,
        ]
        return "\n".join(lines)


# ============================================================
# 错误聚合器
# ============================================================

class ErrorAggregator:
    """聚合多个解析错误，生成综合报告。"""

    def __init__(self):
        self.errors: list[MathaError] = []

    def add(self, error: MathaError) -> "ErrorAggregator":
        self.errors.append(error)
        return self

    def add_result(self, result: Result) -> "ErrorAggregator":
        """从 Result 中提取错误并添加。"""
        if result.is_err():
            self.add(result.err())
        return self

    def aggregate(self) -> CompositeError:
        """聚合所有错误为 CompositeError。"""
        if not self.errors:
            return composite_error("无错误")
        messages = [e.message for e in self.errors]
        return composite_error(
            f"解析过程中发生 {len(self.errors)} 个错误",
            errors=self.errors
        )

    def report(self) -> str:
        """生成聚合报告。"""
        if not self.errors:
            return "所有解析步骤成功。"
        lines = [f"共 {len(self.errors)} 个错误:"]
        for i, e in enumerate(self.errors, 1):
            lines.append(f"\n--- 错误 {i} ---")
            lines.append(e.report(indent=2))
            if e.suggestions:
                lines.append("建议:")
                for s in e.suggestions:
                    lines.append(f"  • {s}")
        return "\n".join(lines)


# ============================================================
# 上下文管理器：带自动错误恢复的解析
# ============================================================

class IntentParseContext:
    """意图解析上下文，提供链式错误处理。"""

    def __init__(self, text: str):
        self.text = text
        self.parser = EnhancedIntentParser()
        self.errors: list[MathaError] = []
        self.warnings: list[MathaError] = []

    def parse(self) -> Result:
        """执行解析，收集所有错误。"""
        result = self.parser.parse(self.text)
        if result.is_err():
            error = result.err()
            if error.severity == ErrorSeverity.WARNING:
                self.warnings.append(error)
            else:
                self.errors.append(error)
        return result

    def recover(self) -> Optional[MathaError]:
        """尝试自动恢复。"""
        if self.errors:
            first = self.errors[0]
            recovered = RecoveryStrategy.try_recover(first)
            if recovered:
                self.errors.pop(0)
                return recovered
        return None

    def report(self) -> str:
        """生成完整报告。"""
        agg = ErrorAggregator()
        for e in self.errors:
            agg.add(e)
        for w in self.warnings:
            agg.add(w)
        return agg.report()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.errors.append(MathaError(
                message=f"{exc_type.__name__}: {exc_val}",
                stage=ErrorStage.EXECUTING,
            ))
        return False


# ============================================================
# 便捷函数
# ============================================================

def parse_intent_safe(text: str, target_lang: str = "python") -> Result:
    """安全解析：返回 Result[Intent, MathaError]。"""
    parser = EnhancedIntentParser()
    return parser.parse(text, target_lang)


def explain_intent_safe(text: str, target_lang: str = "python") -> str:
    """安全解释：返回自然语言报告（含错误信息）。"""
    parser = EnhancedIntentParser()
    return parser.explain_with_errors(text)


def execute_intent(text: str, target_lang: str = "python") -> Result:
    """解析 + 执行 + 返回结果。"""
    parser = EnhancedIntentParser()
    parse_result = parser.parse(text, target_lang)
    if parse_result.is_err():
        return Err(parse_result.err())
    intent = parse_result.unwrap()
    exec_result = parser.execute_and_verify(intent)
    return exec_result


# ============================================================
# 类型别名（方便导入）
# ============================================================

IntentResult = Result
IntentError = MathaError
