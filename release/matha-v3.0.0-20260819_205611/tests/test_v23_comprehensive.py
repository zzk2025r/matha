# -*- coding: utf-8 -*-
"""v2.3 异常处理系统 — 完整单元测试报告

覆盖范围：
  1. 6 种错误类型（ParseError, ClassifyError, ParamExtractError,
     CodeGenError, ExecError, CompositeError）
  2. 4 种恢复策略（classify, params, codegen, exec）
  3. 错误链传播（cause + children）
  4. ErrorAggregator 聚合报告
  5. IntentParseContext 上下文管理器
  6. REPL 集成兼容性
"""
import sys
import unittest
import threading
from typing import Any

sys.path.insert(0, r"D:\trae")

from src.errors import (
    MathaError, ErrorStage, ErrorSeverity,
    ParseError, ClassifyError, ParamExtractError,
    CodeGenError, ExecError, CompositeError,
    RecoveryStrategy, map_errors,
    classify_error, parse_error, param_error,
    codegen_error, exec_error, composite_error,
)
from src.enhanced_intent import (
    EnhancedIntentParser, IntentParseContext,
    ErrorAggregator, execute_intent,
)
from src.repl_v23 import MathaREPL
from src.result import Ok, Err
from src.intent_parser import IntentType


# ============================================================
# 1. ParseError 测试
# ============================================================

class TestParseError(unittest.TestCase):
    """ParseError 单元测试。"""

    def test_basic_init(self):
        e = parse_error("expected =", line=5, col=10, expected="=")
        self.assertEqual(e.stage, ErrorStage.PARSING)
        self.assertEqual(e.code, "PARSE:5:10")
        self.assertEqual(e.severity, ErrorSeverity.ERROR)

    def test_no_line_info(self):
        e = parse_error("unexpected token")
        self.assertEqual(e.code, "PARSE")
        self.assertNotIn(":", e.code)

    def test_suggestion_added(self):
        e = parse_error("missing =", expected="=")
        self.assertIn("期望: =", e.suggestions)

    def test_context_line_col(self):
        e = parse_error("err", line=3, col=7)
        self.assertEqual(e.context["line"], 3)
        self.assertEqual(e.context["col"], 7)

    def test_report_format(self):
        e = parse_error("syntax error", line=1, col=5)
        report = e.report()
        self.assertIn("[ERROR]", report)
        self.assertIn("PARSING", report)
        self.assertIn("syntax error", report)
        self.assertIn("PARSE:1:5", report)

    def test_to_result(self):
        e = parse_error("test")
        result = e.to_result()
        self.assertIsInstance(result, Err)

    def test_raise_and_catch(self):
        with self.assertRaises(ParseError):
            raise parse_error("raised error")

    def test_with_cause(self):
        cause = parse_error("root cause", line=1)
        e = parse_error("derived", line=2).with_cause(cause)
        self.assertEqual(e.cause, cause)
        self.assertIn("root cause", e.stack[0])


# ============================================================
# 2. ClassifyError 测试
# ============================================================

class TestClassifyError(unittest.TestCase):
    """ClassifyError 单元测试。"""

    def test_default_severity(self):
        e = classify_error("unknown intent")
        self.assertEqual(e.severity, ErrorSeverity.WARNING)
        self.assertEqual(e.stage, ErrorStage.CLASSIFYING)

    def test_candidates_suggestion(self):
        e = classify_error("no match", candidates=["算术", "字符串"])
        self.assertIn("算术", e.suggestions[0])
        self.assertIn("字符串", e.suggestions[0])

    def test_default_suggestion(self):
        e = classify_error("no match")
        self.assertTrue(any("关键词" in s for s in e.suggestions))

    def test_report(self):
        e = classify_error("unrecognized", candidates=["A", "B", "C"])
        report = e.report()
        self.assertIn("WARNING", report)
        self.assertIn("CLASSIFYING", report)

    def test_is_warning(self):
        e = classify_error("test")
        self.assertEqual(e.severity, ErrorSeverity.WARNING)


# ============================================================
# 3. ParamExtractError 测试
# ============================================================

class TestParamExtractError(unittest.TestCase):
    """ParamExtractError 单元测试。"""

    def test_type_mismatch(self):
        e = param_error("type mismatch", expected="int", actual="str")
        self.assertEqual(e.stage, ErrorStage.PARAM_EXTRACTING)
        self.assertEqual(e.context["actual_type"], "str")
        self.assertIn("期望类型: int", e.suggestions[0])

    def test_missing_param(self):
        e = param_error("missing required", expected="范围")
        self.assertIn("范围", e.suggestions[0])

    def test_severity(self):
        e = param_error("test")
        self.assertEqual(e.severity, ErrorSeverity.ERROR)


# ============================================================
# 4. CodeGenError 测试
# ============================================================

class TestCodeGenError(unittest.TestCase):
    """CodeGenError 单元测试。"""

    def test_default_lang(self):
        e = codegen_error("no params")
        self.assertEqual(e.stage, ErrorStage.CODE_GENERATING)
        self.assertIn("python", e.suggestions[0].lower())

    def test_custom_lang(self):
        e = codegen_error("missing args", lang="rust")
        self.assertIn("rust", e.suggestions[0].lower())

    def test_suggestions(self):
        e = codegen_error("test")
        self.assertGreaterEqual(len(e.suggestions), 2)


# ============================================================
# 5. ExecError 测试
# ============================================================

class TestExecError(unittest.TestCase):
    """ExecError 单元测试。"""

    def test_with_exception(self):
        exc = ZeroDivisionError("division by zero")
        e = exec_error("exec failed", exc)
        self.assertEqual(e.stage, ErrorStage.EXECUTING)
        self.assertGreater(len(e.stack), 0)
        # suggestion 包含通用建议
        self.assertGreaterEqual(len(e.suggestions), 2)

    def test_suggestions(self):
        e = exec_error("test")
        self.assertEqual(len(e.suggestions), 0)
        e2 = exec_error("test", Exception("dummy"))
        self.assertGreaterEqual(len(e2.suggestions), 2)


# ============================================================
# 6. CompositeError 测试
# ============================================================

class TestCompositeError(unittest.TestCase):
    """CompositeError 单元测试。"""

    def test_aggregate_errors(self):
        errs = [
            parse_error("err1"),
            classify_error("err2"),
            codegen_error("err3"),
        ]
        c = composite_error("multiple", errs)
        self.assertEqual(len(c.children), 3)
        self.assertEqual(c.severity, ErrorSeverity.ERROR)

    def test_severity_promotion(self):
        fatal = MathaError("fatal", ErrorStage.EXECUTING, severity=ErrorSeverity.FATAL)
        warn = MathaError("warn", ErrorStage.CLASSIFYING, severity=ErrorSeverity.WARNING)
        c = CompositeError("mixed", [fatal, warn])
        self.assertEqual(c.severity, ErrorSeverity.FATAL)

    def test_recover_finds_warning(self):
        c = composite_error("mixed", [
            classify_error("recoverable"),
            exec_error("fatal"),
        ])
        recovered = c.recover()
        self.assertIsNotNone(recovered)
        self.assertEqual(recovered.severity, ErrorSeverity.WARNING)

    def test_recover_no_warning(self):
        c = composite_error("all_fatal", [
            exec_error("fatal1"),
            exec_error("fatal2"),
        ])
        self.assertIsNone(c.recover())

    def test_empty_composite(self):
        c = composite_error("empty")
        self.assertEqual(len(c.children), 0)


# ============================================================
# 7. 恢复策略测试
# ============================================================

class TestRecoveryStrategies(unittest.TestCase):
    """4 种恢复策略单元测试。"""

    def test_recover_classify(self):
        e = classify_error("未知意图")
        recovered = RecoveryStrategy.try_recover(e)
        self.assertIsNone(recovered)  # classify 返回 None
        self.assertTrue(any("关键词" in s for s in e.suggestions))

    def test_recover_params(self):
        e = param_error("类型不匹配")
        recovered = RecoveryStrategy.try_recover(e)
        self.assertIsNone(recovered)
        self.assertTrue(any("阿拉伯数字" in s for s in e.suggestions))

    def test_recover_params_missing(self):
        e = param_error("缺少必要参数")
        recovered = RecoveryStrategy.try_recover(e)
        self.assertIsNone(recovered)
        self.assertTrue(any("补充" in s for s in e.suggestions))

    def test_recover_codegen(self):
        e = codegen_error("参数不足")
        recovered = RecoveryStrategy.try_recover(e)
        self.assertIsNone(recovered)
        self.assertTrue(any("默认参数" in s for s in e.suggestions))

    def test_recover_exec_nameerror(self):
        e = exec_error("NameError: name 'x' is not defined")
        recovered = RecoveryStrategy.try_recover(e)
        self.assertIsNone(recovered)
        self.assertTrue(any("变量名" in s for s in e.suggestions))

    def test_recover_exec_typeerror(self):
        e = exec_error("TypeError: expected int")
        recovered = RecoveryStrategy.try_recover(e)
        self.assertIsNone(recovered)
        self.assertTrue(any("类型" in s for s in e.suggestions))

    def test_recover_exec_zerodiv(self):
        e = exec_error("ZeroDivisionError: division by zero")
        recovered = RecoveryStrategy.try_recover(e)
        self.assertIsNone(recovered)
        self.assertTrue(any("除零" in s for s in e.suggestions))

    def test_no_registered_strategy(self):
        e = MathaError("unknown stage", ErrorStage.VALIDATING)
        recovered = RecoveryStrategy.try_recover(e)
        self.assertIsNone(recovered)

    def test_strategy_exception_handled(self):
        """策略内部异常不应影响恢复流程。"""
        class BadStrategy:
            def __call__(self, error):
                raise RuntimeError("strategy crash")
        RecoveryStrategy._strategies[ErrorStage.VALIDATING] = [BadStrategy()]
        e = MathaError("test", ErrorStage.VALIDATING)
        recovered = RecoveryStrategy.try_recover(e)
        self.assertIsNone(recovered)
        RecoveryStrategy._strategies.pop(ErrorStage.VALIDATING, None)


# ============================================================
# 8. map_errors 测试
# ============================================================

class TestMapErrors(unittest.TestCase):
    """map_errors 工具函数测试。"""

    def test_ok_result(self):
        result = map_errors(lambda: 42, stage=ErrorStage.EXECUTING)
        self.assertTrue(result.is_ok())
        self.assertEqual(result.unwrap(), 42)

    def test_exception_mapped(self):
        result = map_errors(lambda: 1 / 0, stage=ErrorStage.EXECUTING)
        self.assertTrue(result.is_err())
        error = result.err()
        self.assertEqual(error.stage, ErrorStage.EXECUTING)
        self.assertIn("ZeroDivisionError", error.message)

    def test_matha_error_mapped(self):
        result = map_errors(
            lambda: (_ for _ in []).throw(parse_error("custom")),
            stage=ErrorStage.PARSING,
        )
        self.assertTrue(result.is_err())
        self.assertIsInstance(result.err(), ParseError)

    def test_default_stage(self):
        result = map_errors(lambda: None)
        self.assertTrue(result.is_ok())


# ============================================================
# 9. 错误链测试
# ============================================================

class TestErrorChain(unittest.TestCase):
    """错误链（cause + children）测试。"""

    def test_cause_chain_report(self):
        root = parse_error("root: syntax error", line=1)
        mid = classify_error("classified wrong").with_cause(root)
        top = MathaError("top level").with_cause(mid)
        report = top.report()
        self.assertIn("root: syntax error", report)
        self.assertIn("classified wrong", report)
        self.assertIn("top level", report)

    def test_nested_children_report(self):
        c1 = param_error("missing param")
        c2 = codegen_error("bad code")
        parent = CompositeError("multi", [c1, c2])
        report = parent.report()
        self.assertIn("missing param", report)
        self.assertIn("bad code", report)

    def test_severity_from_max_child(self):
        fatal = MathaError("fatal", ErrorStage.EXECUTING, severity=ErrorSeverity.FATAL)
        info = MathaError("info", ErrorStage.VALIDATING, severity=ErrorSeverity.INFO)
        c = CompositeError("mixed", [fatal, info])
        self.assertEqual(c.severity, ErrorSeverity.FATAL)

    def test_add_child_chaining(self):
        parent = MathaError("parent")
        child = parse_error("child")
        result = parent.add_child(child)
        self.assertIs(result, parent)
        self.assertEqual(len(parent.children), 1)


# ============================================================
# 10. ErrorAggregator 测试
# ============================================================

class TestErrorAggregator(unittest.TestCase):
    """ErrorAggregator 测试。"""

    def test_empty_aggregate(self):
        agg = ErrorAggregator()
        self.assertIn("成功", agg.report())

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
        agg.add_result(Err(parse_error("from_result")))
        report = agg.report()
        self.assertIn("from_result", report)

    def test_aggregate_composite(self):
        agg = ErrorAggregator()
        composite = composite_error("multi", [
            parse_error("p1"),
            classify_error("c1"),
        ])
        agg.add(composite)
        report = agg.report()
        self.assertIn("multi", report)


# ============================================================
# 11. EnhancedIntentParser 集成测试
# ============================================================

class TestEnhancedParserIntegration(unittest.TestCase):
    """EnhancedIntentParser 集成测试。"""

    def setUp(self):
        self.parser = EnhancedIntentParser()

    def test_success_arithmetic(self):
        result = self.parser.parse("计算 3 加 5")
        self.assertTrue(result.is_ok())
        intent = result.unwrap()
        self.assertEqual(intent.intent_type, IntentType.ARITHMETIC)
        self.assertGreater(intent.confidence, 0.3)

    def test_success_array_op(self):
        result = self.parser.parse("对数组 [3,1,2] 排序")
        self.assertTrue(result.is_ok())
        intent = result.unwrap()
        self.assertEqual(intent.intent_type, IntentType.ARRAY_OP)

    def test_classify_failure(self):
        result = self.parser.parse("xyz abc notreal")
        self.assertTrue(result.is_err())
        error = result.err()
        self.assertEqual(error.stage, ErrorStage.CLASSIFYING)
        # 建议内容是"可能的意图"或"关键词"均可
        self.assertTrue(any("意图" in s or "关键词" in s for s in error.suggestions))

    def test_param_warning_not_blocking(self):
        result = self.parser.parse("求正弦值")
        # 参数缺失是 WARNING，不阻断
        self.assertTrue(result.is_ok())

    def test_execute_and_verify(self):
        intent = self.parser.parse("计算 3 加 5").unwrap()
        result = self.parser.execute_and_verify(intent)
        self.assertTrue(result.is_ok())
        self.assertEqual(result.unwrap(), 8.0)

    def test_explain_with_errors(self):
        report = self.parser.explain_with_errors("xyz")
        self.assertIn("失败", report)
        self.assertIn("建议", report)

    def test_long_chain(self):
        """长文本多步操作。"""
        result = self.parser.parse("找出 1 到 100 之间所有素数")
        self.assertTrue(result.is_ok())
        intent = result.unwrap()
        self.assertEqual(intent.intent_type, IntentType.MATH_FUNC)


# ============================================================
# 12. IntentParseContext 测试
# ============================================================

class TestIntentParseContext(unittest.TestCase):
    """IntentParseContext 上下文管理器测试。"""

    def test_successful_parse(self):
        with IntentParseContext("计算 3 + 5") as ctx:
            result = ctx.parse()
            self.assertTrue(result.is_ok())
            self.assertEqual(len(ctx.errors), 0)

    def test_classify_failure_collected(self):
        with IntentParseContext("xyz") as ctx:
            result = ctx.parse()
            self.assertTrue(result.is_err())
            self.assertEqual(len(ctx.warnings), 1)

    def test_exception_caught(self):
        ctx = IntentParseContext("test")
        try:
            with ctx:
                raise ValueError("unexpected")
        except ValueError:
            pass
        self.assertEqual(len(ctx.errors), 1)
        self.assertEqual(ctx.errors[0].stage, ErrorStage.EXECUTING)

    def test_report_contains_all(self):
        with IntentParseContext("xyz") as ctx:
            ctx.parse()
            report = ctx.report()
            self.assertGreater(len(report), 0)

    def test_recover_method(self):
        with IntentParseContext("xyz") as ctx:
            ctx.parse()
            recovered = ctx.recover()
            self.assertIsNone(recovered)


# ============================================================
# 13. 并发安全测试
# ============================================================

class TestConcurrency(unittest.TestCase):
    """并发场景下的异常处理测试。"""

    def test_concurrent_parse(self):
        """多线程并发解析不同输入。"""
        results = []
        errors = []

        def parse_one(text, idx):
            try:
                parser = EnhancedIntentParser()
                result = parser.parse(text)
                results.append((idx, result))
            except Exception as e:
                errors.append((idx, e))

        threads = []
        inputs = [
            "计算 3 加 5",
            "反转字符串 abc",
            "对数组 [3,1,2] 排序",
            "xyz abc",
            "求 100 以内素数",
        ]
        for i, inp in enumerate(inputs):
            t = threading.Thread(target=parse_one, args=(inp, i))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=5)

        self.assertEqual(len(results), 5)
        self.assertEqual(len(errors), 0)

    def test_concurrent_error_types(self):
        """并发创建不同错误类型。"""
        errors_created = []
        lock = threading.Lock()

        def create_errors(stage, err_class, count):
            for _ in range(count):
                e = err_class("test")
                with lock:
                    errors_created.append((stage.name, type(e).__name__))

        tasks = [
            (ErrorStage.PARSING, ParseError, 10),
            (ErrorStage.CLASSIFYING, ClassifyError, 10),
            (ErrorStage.PARAM_EXTRACTING, ParamExtractError, 10),
            (ErrorStage.CODE_GENERATING, CodeGenError, 10),
            (ErrorStage.EXECUTING, ExecError, 10),
        ]

        threads = []
        for stage, err_cls, count in tasks:
            t = threading.Thread(target=create_errors, args=(stage, err_cls, count))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=5)

        self.assertEqual(len(errors_created), 50)

    def test_recovery_strategy_thread_safety(self):
        """恢复策略注册在多线程环境下安全。"""
        def register_and_use(idx):
            @RecoveryStrategy.register(ErrorStage.VALIDATING)
            def _strategy(error):
                error.add_suggestion(f"strategy_{idx}")
                return None
            e = MathaError("test", ErrorStage.VALIDATING)
            RecoveryStrategy.try_recover(e)

        threads = [threading.Thread(target=register_and_use, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)


# ============================================================
# 14. REPL 集成兼容性测试
# ============================================================

class TestREPLIntegration(unittest.TestCase):
    """REPL 与 v2.3 异常系统的兼容性测试。"""

    def test_repl_handles_error_gracefully(self):
        """REPL 处理自然语言错误时不崩溃。"""
        from src.repl_v23 import MathaREPL
        repl = MathaREPL(debug=False)
        # 模拟错误输入，不应抛出未捕获异常
        repl.state.intent_parser = EnhancedIntentParser()
        try:
            repl._process_natural_language("xyz abc notreal")
        except Exception:
            self.fail("REPL should handle error gracefully")

    def test_repl_handles_success(self):
        repl = MathaREPL(debug=False)
        repl.state.intent_parser = EnhancedIntentParser()
        try:
            repl._process_natural_language("计算 3 加 5")
        except Exception:
            self.fail("REPL should handle success case")

    def test_repl_process_matha_expr_with_error(self):
        repl = MathaREPL(debug=False)
        try:
            repl._process_matha_expr("this is not valid matha >>>")
        except Exception:
            self.fail("REPL should catch and display Matha parse errors")


# ============================================================
# 运行测试
# ============================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
