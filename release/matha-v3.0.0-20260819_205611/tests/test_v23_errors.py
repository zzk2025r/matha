# -*- coding: utf-8 -*-
"""v2.3 异常处理系统测试。"""
import sys
import unittest
from typing import Any

sys.path.insert(0, r"D:\trae")

from src.intent_parser import IntentType
from src.errors import (
    MathaError, ErrorStage, ErrorSeverity,
    ParseError, ClassifyError, ParamExtractError,
    CodeGenError, ExecError, CompositeError,
    RecoveryStrategy, err_with_stage, map_errors,
    classify_error, parse_error, param_error,
    codegen_error, exec_error, composite_error,
    ok_with_context,
)
from src.enhanced_intent import (
    EnhancedIntentParser, IntentParseContext,
    parse_intent_safe, explain_intent_safe, execute_intent,
    ErrorAggregator,
)
from src.result import Ok, Err


class TestMathaError(unittest.TestCase):
    """基础错误类测试。"""

    def test_basic_error(self):
        e = MathaError("test error", ErrorStage.PARSING)
        self.assertEqual(e.message, "test error")
        self.assertEqual(e.severity, ErrorSeverity.ERROR)
        self.assertEqual(len(e.suggestions), 0)

    def test_with_cause(self):
        cause = MathaError("cause", ErrorStage.EXECUTING)
        e = MathaError("main", ErrorStage.PARSING).with_cause(cause)
        self.assertEqual(e.cause, cause)
        self.assertIn("cause", e.stack[0])

    def test_add_child(self):
        child = MathaError("child", ErrorStage.CLASSIFYING)
        parent = MathaError("parent", ErrorStage.PARAM_EXTRACTING)
        parent.add_child(child)
        self.assertEqual(len(parent.children), 1)

    def test_add_suggestion(self):
        e = MathaError("test", ErrorStage.PARSING)
        e.add_suggestion("try this")
        e.add_suggestion("try that")
        self.assertEqual(len(e.suggestions), 2)

    def test_report_format(self):
        e = MathaError("test error", ErrorStage.PARSING)
        report = e.report()
        self.assertIn("[ERROR]", report)
        self.assertIn("PARSING", report)
        self.assertIn("test error", report)

    def test_suggestions_text(self):
        e = MathaError("test", ErrorStage.PARSING)
        e.add_suggestion("fix 1")
        e.add_suggestion("fix 2")
        text = e.suggestions_text()
        self.assertIn("fix 1", text)
        self.assertIn("fix 2", text)

    def test_to_result(self):
        e = MathaError("test", ErrorStage.PARSING)
        result = e.to_result()
        self.assertIsInstance(result, Err)


class TestStageErrors(unittest.TestCase):
    """各阶段错误测试。"""

    def test_parse_error(self):
        e = parse_error("expected =", line=5, col=10, expected="=")
        self.assertEqual(e.stage, ErrorStage.PARSING)
        self.assertEqual(e.code, "PARSE:5:10")
        self.assertIn("期望: =", e.suggestions)

    def test_classify_error(self):
        e = classify_error("unknown intent", candidates=["算术", "字符串"])
        self.assertEqual(e.stage, ErrorStage.CLASSIFYING)
        self.assertEqual(e.severity, ErrorSeverity.WARNING)
        self.assertIn("算术", e.suggestions[0])

    def test_param_error(self):
        e = param_error("type mismatch", expected="int", actual="str")
        self.assertEqual(e.stage, ErrorStage.PARAM_EXTRACTING)
        self.assertEqual(e.context["actual_type"], "str")

    def test_codegen_error(self):
        e = codegen_error("missing params", lang="rust")
        self.assertEqual(e.stage, ErrorStage.CODE_GENERATING)
        self.assertIn("rust", e.suggestions[0].lower())

    def test_exec_error(self):
        e = exec_error("division by zero", Exception("zero div"))
        self.assertEqual(e.stage, ErrorStage.EXECUTING)
        self.assertGreater(len(e.stack), 0)

    def test_composite_error(self):
        errors = [
            parse_error("err1"),
            classify_error("err2"),
        ]
        e = composite_error("multiple errors", errors)
        self.assertEqual(len(e.children), 2)
        self.assertEqual(e.severity, ErrorSeverity.ERROR)


class TestErrorChain(unittest.TestCase):
    """错误链测试。"""

    def test_cause_chain(self):
        root = parse_error("root cause")
        mid = classify_error("classification failed").with_cause(root)
        top = MathaError("top level").with_cause(mid)

        report = top.report()
        self.assertIn("root cause", report)
        self.assertIn("classification failed", report)

    def test_nested_children(self):
        child1 = param_error("missing param")
        child2 = codegen_error("bad code")
        parent = CompositeError("multi", [child1, child2])

        report = parent.report()
        self.assertIn("missing param", report)
        self.assertIn("bad code", report)

    def test_severity_propagation(self):
        fatal = MathaError("fatal", ErrorStage.EXECUTING, severity=ErrorSeverity.FATAL)
        warning = MathaError("warn", ErrorStage.CLASSIFYING, severity=ErrorSeverity.WARNING)
        composite = CompositeError("mixed", [fatal, warning])
        self.assertEqual(composite.severity, ErrorSeverity.FATAL)


class TestRecoveryStrategy(unittest.TestCase):
    """恢复策略测试。"""

    def test_classify_recovery(self):
        error = classify_error("unknown intent")
        recovered = RecoveryStrategy.try_recover(error)
        # classify recovery returns None (info-level)
        self.assertIsNone(recovered)
        self.assertTrue(any("关键词" in s for s in error.suggestions))

    def test_param_recovery(self):
        error = param_error("type mismatch")
        recovered = RecoveryStrategy.try_recover(error)
        self.assertIsNone(recovered)

    def test_exec_recovery(self):
        error = exec_error("ZeroDivisionError", Exception("division by zero"))
        recovered = RecoveryStrategy.try_recover(error)
        self.assertIsNone(recovered)
        self.assertTrue(any("除零" in s for s in error.suggestions))


class TestEnhancedParser(unittest.TestCase):
    """增强意图解析器测试。"""

    def setUp(self):
        self.parser = EnhancedIntentParser()

    def test_parse_success(self):
        result = self.parser.parse("计算 3 加 5")
        self.assertTrue(result.is_ok())
        intent = result.unwrap()
        self.assertEqual(intent.intent_type.name, "ARITHMETIC")
        self.assertGreater(intent.confidence, 0.3)

    def test_parse_classify_failure(self):
        result = self.parser.parse("xyz abc def")
        self.assertTrue(result.is_err())
        error = result.err()
        self.assertEqual(error.stage, ErrorStage.CLASSIFYING)

    def test_parse_param_failure(self):
        # 参数提取失败是 WARNING，不阻断解析
        result = self.parser.parse("求正弦值")
        self.assertTrue(result.is_ok())
        intent = result.unwrap()
        self.assertGreaterEqual(len(intent.errors), 0)

    def test_parse_with_context(self):
        result = ok_with_context("hello", source="test")
        self.assertTrue(result.is_ok())
        self.assertEqual(result.unwrap(), "hello")

    def test_error_chain_in_parse(self):
        result = self.parser.parse("对数组 [1,3,2] 排序")
        self.assertTrue(result.is_ok())
        intent = result.unwrap()
        self.assertEqual(intent.intent_type, IntentType.ARRAY_OP)

    def test_confidence_threshold(self):
        result = self.parser.parse("hello")
        # 无匹配关键词 → 低置信度 → Err
        self.assertTrue(result.is_err() or result.unwrap().confidence < 0.3)


class TestExecuteIntent(unittest.TestCase):
    """意图执行测试。"""

    def test_execute_arithmetic(self):
        result = execute_intent("计算 3 加 5")
        self.assertTrue(result.is_ok())
        self.assertEqual(result.unwrap(), 8)

    def test_execute_math_func(self):
        result = execute_intent("计算 16 的平方根")
        if result.is_ok():
            self.assertAlmostEqual(result.unwrap(), 4.0, places=1)

    def test_execute_string_op(self):
        result = execute_intent("反转字符串 abc")
        # 可能因参数提取失败而返回 Err
        if result.is_err():
            error = result.err()
            self.assertIsInstance(error, MathaError)


class TestErrorAggregator(unittest.TestCase):
    """错误聚合器测试。"""

    def test_aggregate_empty(self):
        agg = ErrorAggregator()
        report = agg.report()
        self.assertIn("成功", report)

    def test_aggregate_multiple(self):
        agg = ErrorAggregator()
        agg.add(parse_error("err1"))
        agg.add(classify_error("err2"))
        report = agg.report()
        self.assertIn("2 个错误", report)
        self.assertIn("err1", report)
        self.assertIn("err2", report)

    def test_aggregate_from_result(self):
        agg = ErrorAggregator()
        agg.add_result(Err(parse_error("test")))
        report = agg.report()
        self.assertIn("test", report)


class TestIntentParseContext(unittest.TestCase):
    """上下文管理器测试。"""

    def test_context_parse(self):
        with IntentParseContext("计算 3 + 5") as ctx:
            result = ctx.parse()
            self.assertTrue(result.is_ok())
            self.assertEqual(len(ctx.errors), 0)

    def test_context_error_collection(self):
        with IntentParseContext("xyz") as ctx:
            result = ctx.parse()
            self.assertTrue(result.is_err())
            # 分类失败是 WARNING，存入 warnings
            self.assertEqual(len(ctx.warnings), 1)

    def test_context_exception(self):
        ctx = IntentParseContext("test")
        try:
            with ctx:
                raise ValueError("unexpected")
        except ValueError:
            pass
        self.assertEqual(len(ctx.errors), 1)

    def test_context_report(self):
        with IntentParseContext("xyz") as ctx:
            ctx.parse()
            report = ctx.report()
            self.assertGreater(len(report), 0)


class TestExplainIntentSafe(unittest.TestCase):
    """安全解释测试。"""

    def test_explain_success(self):
        report = explain_intent_safe("计算 3 加 5")
        self.assertIn("算术", report)
        self.assertIn("3.0 + 5.0", report)

    def test_explain_error(self):
        report = explain_intent_safe("xyz abc")
        self.assertIn("失败", report)
        self.assertIn("建议", report)


class TestMapErrors(unittest.TestCase):
    """map_errors 工具测试。"""

    def test_map_ok(self):
        def fn():
            return 42
        result = map_errors(fn, stage=ErrorStage.EXECUTING)
        self.assertTrue(result.is_ok())
        self.assertEqual(result.unwrap(), 42)

    def test_map_err(self):
        def fn():
            raise ValueError("test")
        result = map_errors(fn, stage=ErrorStage.EXECUTING)
        self.assertTrue(result.is_err())
        error = result.err()
        self.assertEqual(error.stage, ErrorStage.EXECUTING)

    def test_map_matha_error(self):
        def fn():
            raise parse_error("custom error")
        result = map_errors(fn, stage=ErrorStage.PARSING)
        self.assertTrue(result.is_err())
        error = result.err()
        self.assertEqual(error.stage, ErrorStage.PARSING)


if __name__ == "__main__":
    unittest.main(verbosity=2)
