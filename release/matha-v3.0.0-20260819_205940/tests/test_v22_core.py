# -*- coding: utf-8 -*-
"""Matha v2.2 测试套件：标准库 + Result + REPL + 意图解析器。"""
import sys
import unittest
from typing import Any

sys.path.insert(0, r"D:\trae")

from src.stdlib.core import register_core_builtins, MathaType
from src.result import Ok, Err, Some, None_, result, try_unwrap_or, MathaResultError
from src.intent_parser import IntentParser, IntentType, parse_intent, explain_intent
from src.repl import MathaREPL


# ============================================================
# 标准库 Core 测试
# ============================================================

class TestCoreStdlib(unittest.TestCase):
    """标准库 Core 模块测试。"""

    def setUp(self):
        self.builtins: dict[str, Any] = {}
        register_core_builtins(self.builtins)

    # ── Int ──────────────────────────────────────────────────────
    def test_int_basic(self):
        self.assertEqual(self.builtins["Int"](3.7), 3)
        self.assertEqual(self.builtins["Int"]("5"), 5)

    def test_int_max_min(self):
        self.assertEqual(self.builtins["IntMax"](3, 7), 7)
        self.assertEqual(self.builtins["IntMin"](3, 7), 3)

    def test_int_gcd_lcm(self):
        self.assertEqual(self.builtins["IntGCD"](12, 8), 4)
        self.assertEqual(self.builtins["IntLCM"](4, 6), 12)

    def test_int_prime(self):
        self.assertTrue(self.builtins["IntIsPrime"](7))
        self.assertFalse(self.builtins["IntIsPrime"](4))

    def test_int_factors(self):
        self.assertEqual(self.builtins["IntFactors"](12), [1, 2, 3, 4, 6, 12])

    def test_int_roman(self):
        self.assertEqual(self.builtins["IntFromStr"]("2025"), 2025)
        self.assertEqual(self.builtins["RomanToInt"]("XIV"), 14)

    # ── String ───────────────────────────────────────────────────
    def test_str_basic(self):
        self.assertEqual(self.builtins["Str"](42), "42")
        self.assertEqual(self.builtins["StrLen"]("hello"), 5)

    def test_str_upper_lower(self):
        self.assertEqual(self.builtins["StrUpper"]("hello"), "HELLO")
        self.assertEqual(self.builtins["StrLower"]("HELLO"), "hello")

    def test_str_split_join(self):
        self.assertEqual(self.builtins["StrSplit"]("a,b,c", ","), ["a", "b", "c"])
        self.assertEqual(self.builtins["StrJoin"]("-", ["a", "b", "c"]), "a-b-c")

    def test_str_contains(self):
        self.assertTrue(self.builtins["StrContains"]("ell", "hello"))
        self.assertFalse(self.builtins["StrContains"]("xyz", "hello"))

    def test_str_replace(self):
        self.assertEqual(self.builtins["StrReplace"]("world", "Matha", "hello world"), "hello Matha")

    def test_str_slice(self):
        self.assertEqual(self.builtins["StrSlice"]("hello", 1, 4), "ell")

    def test_str_reverse(self):
        self.assertEqual(self.builtins["StrReverse"]("abc"), "cba")

    def test_str_repeat(self):
        self.assertEqual(self.builtins["StrRepeat"]("ab", 3), "ababab")

    def test_str_word_count(self):
        self.assertEqual(self.builtins["StrWordCount"]("hello world foo"), 3)

    # ── Bool ─────────────────────────────────────────────────────
    def test_bool_basic(self):
        self.assertTrue(self.builtins["Bool"](1))
        self.assertFalse(self.builtins["Bool"](0))

    def test_bool_not(self):
        self.assertFalse(self.builtins["BoolNot"](True))
        self.assertTrue(self.builtins["BoolNot"](False))

    def test_bool_and_or(self):
        self.assertTrue(self.builtins["BoolAnd"](True, True))
        self.assertFalse(self.builtins["BoolAnd"](True, False))
        self.assertTrue(self.builtins["BoolOr"](False, True))
        self.assertFalse(self.builtins["BoolOr"](False, False))

    def test_bool_xor(self):
        self.assertTrue(self.builtins["BoolXor"](True, False))
        self.assertFalse(self.builtins["BoolXor"](True, True))

    # ── Array ────────────────────────────────────────────────────
    def test_array_basic(self):
        arr = self.builtins["Array"](1, 2, 3)
        self.assertEqual(arr, [1, 2, 3])

    def test_array_new(self):
        arr = self.builtins["ArrayNew"](5, 0)
        self.assertEqual(arr, [0, 0, 0, 0, 0])

    def test_array_len(self):
        self.assertEqual(self.builtins["ArrayLen"]([1, 2, 3]), 3)

    def test_array_append_push(self):
        arr = [1, 2]
        self.assertEqual(self.builtins["ArrayAppend"](arr, 3), [1, 2, 3])

    def test_array_get_set(self):
        arr = [10, 20, 30]
        self.assertEqual(self.builtins["ArrayGet"](arr, 1), 20)
        self.builtins["ArraySet"](arr, 1, 99)
        self.assertEqual(arr[1], 99)

    def test_array_contains_index(self):
        arr = [1, 2, 3]
        self.assertTrue(self.builtins["ArrayContains"](arr, 2))
        self.assertEqual(self.builtins["ArrayIndex"](arr, 3), 2)

    def test_array_sort_reverse(self):
        self.assertEqual(self.builtins["ArraySort"]([3, 1, 2]), [1, 2, 3])
        self.assertEqual(self.builtins["ArrayReverse"]([1, 2, 3]), [3, 2, 1])

    def test_array_sum_avg(self):
        self.assertEqual(self.builtins["ArraySum"]([1, 2, 3, 4]), 10)
        self.assertEqual(self.builtins["ArrayAvg"]([1, 2, 3, 4]), 2.5)

    def test_array_min_max(self):
        self.assertEqual(self.builtins["ArrayMin"]([3, 1, 4]), 1)
        self.assertEqual(self.builtins["ArrayMax"]([3, 1, 4]), 4)

    def test_array_slice(self):
        arr = [0, 1, 2, 3, 4]
        self.assertEqual(self.builtins["ArraySlice"](arr, 1, 4), [1, 2, 3])

    def test_array_range(self):
        self.assertEqual(self.builtins["ArrayRange"](0, 5), [0, 1, 2, 3, 4])

    def test_array_unique(self):
        self.assertEqual(self.builtins["ArrayUnique"]([1, 2, 2, 3, 3]), [1, 2, 3])

    def test_array_chunk(self):
        self.assertEqual(self.builtins["ArrayChunk"]([1, 2, 3, 4, 5], 2), [[1, 2], [3, 4], [5]])


# ============================================================
# Result 类型测试
# ============================================================

class TestResult(unittest.TestCase):
    """Result 类型测试。"""

    def test_ok_basic(self):
        r = Ok(42)
        self.assertTrue(r.is_ok())
        self.assertFalse(r.is_err())
        self.assertEqual(r.unwrap(), 42)

    def test_err_basic(self):
        r = Err("failed")
        self.assertFalse(r.is_ok())
        self.assertTrue(r.is_err())

    def test_ok_map(self):
        r = Ok(5).map(lambda x: x * 2)
        self.assertEqual(r.unwrap(), 10)

    def test_err_map(self):
        r = Err("e").map(lambda x: x * 2)
        self.assertIsInstance(r, Err)

    def test_err_map_err(self):
        r = Err("e").map_err(lambda x: f"wrapped: {x}")
        self.assertEqual(r.error, "wrapped: e")

    def test_ok_and_then(self):
        r = Ok(3).and_then(lambda x: Ok(x * 2))
        self.assertEqual(r.unwrap(), 6)

    def test_err_and_then(self):
        r = Err("e").and_then(lambda x: Ok(x * 2))
        self.assertIsInstance(r, Err)

    def test_ok_or_else(self):
        r = Ok(3).or_else(lambda e: Ok(99))
        self.assertEqual(r.unwrap(), 3)

    def test_err_or_else(self):
        r = Err("e").or_else(lambda e: Ok(99))
        self.assertEqual(r.unwrap(), 99)

    def test_ok_unwrap_or(self):
        self.assertEqual(Ok(5).unwrap_or(0), 5)

    def test_err_unwrap_or(self):
        self.assertEqual(Err("e").unwrap_or(42), 42)

    def test_err_unwrap_raises(self):
        with self.assertRaises(MathaResultError):
            Err("e").unwrap()

    def test_err_expect_raises(self):
        with self.assertRaises(MathaResultError):
            Err("e").expect("custom message")

    def test_result_helper(self):
        r = result(lambda: 1 / 0)
        self.assertIsInstance(r, Err)
        r2 = result(lambda: 42)
        self.assertIsInstance(r2, Ok)
        self.assertEqual(r2.unwrap(), 42)

    def test_try_unwrap_or(self):
        self.assertEqual(try_unwrap_or(Ok(10), 0), 10)
        self.assertEqual(try_unwrap_or(Err("e"), 99), 99)

    def test_err_context(self):
        r = Err("base").context("extra").context("more")
        self.assertIn("extra", r.trace)
        self.assertIn("more", r.trace)


# ============================================================
# Option 类型测试
# ================================================= ============

class TestOption(unittest.TestCase):
    """Option 类型测试。"""

    def test_some_basic(self):
        o = Some(42)
        self.assertTrue(o.is_some())
        self.assertFalse(o.is_none())
        self.assertEqual(o.unwrap(), 42)

    def test_none_basic(self):
        o = None_()
        self.assertFalse(o.is_some())
        self.assertTrue(o.is_none())

    def test_some_map(self):
        o = Some(5).map(lambda x: x * 2)
        self.assertEqual(o.unwrap(), 10)

    def test_none_map(self):
        o = None_().map(lambda x: x * 2)
        self.assertIsInstance(o, None_)

    def test_some_and_then(self):
        o = Some(3).and_then(lambda x: Some(x * 2))
        self.assertEqual(o.unwrap(), 6)

    def test_none_and_then(self):
        o = None_().and_then(lambda x: Some(x * 2))
        self.assertIsInstance(o, None_)

    def test_some_unwrap_or(self):
        self.assertEqual(Some(5).unwrap_or(0), 5)

    def test_none_unwrap_or(self):
        self.assertEqual(None_().unwrap_or(42), 42)

    def test_none_unwrap_raises(self):
        with self.assertRaises(MathaResultError):
            None_().unwrap()

    def test_some_ok_or(self):
        o = Some(10).ok_or("missing")
        self.assertEqual(o.unwrap(), 10)

    def test_none_ok_or(self):
        o = None_().ok_or("missing")
        self.assertEqual(o.error, "missing")


# ============================================================
# 意图解析器测试
# ================================================= ============

class TestIntentParser(unittest.TestCase):
    """意图解析器测试。"""

    def setUp(self):
        self.parser = IntentParser()

    def test_arithmetic_intent(self):
        intent = self.parser.parse("计算 3 加 5")
        self.assertEqual(intent.intent_type, IntentType.ARITHMETIC)
        self.assertGreaterEqual(intent.confidence, 0.5)

    def test_string_intent(self):
        intent = self.parser.parse("将字符串 hello 反转")
        self.assertEqual(intent.intent_type, IntentType.STRING_OP)
        self.assertGreaterEqual(intent.confidence, 0.5)

    def test_array_intent(self):
        intent = self.parser.parse("对数组 [1,3,2] 排序")
        self.assertEqual(intent.intent_type, IntentType.ARRAY_OP)
        self.assertGreaterEqual(intent.confidence, 0.5)

    def test_math_intent(self):
        intent = self.parser.parse("计算 100 以内所有素数")
        self.assertEqual(intent.intent_type, IntentType.MATH_FUNC)
        self.assertGreaterEqual(intent.confidence, 0.5)

    def test_loop_intent(self):
        intent = self.parser.parse("循环处理 1 到 10 的数")
        self.assertEqual(intent.intent_type, IntentType.LOOP)

    def test_unknown_intent(self):
        intent = self.parser.parse("blah blah xyz")
        self.assertEqual(intent.intent_type, IntentType.UNKNOWN)
        self.assertLess(intent.confidence, 0.3)

    def test_params_extraction(self):
        intent = self.parser.parse("求 1 到 100 的和")
        self.assertIn("numbers", intent.params)
        self.assertIn("range", intent.params)
        self.assertEqual(intent.params["range"], (1, 100))

    def test_code_generation(self):
        intent = self.parser.parse("计算 10 的平方根")
        self.assertGreaterEqual(intent.confidence, 0.5)
        self.assertTrue(len(intent.suggested_code) > 0)

    def test_explain(self):
        text = "找出 1 到 50 之间所有偶数"
        explanation = explain_intent(text)
        self.assertIsInstance(explanation, str)
        self.assertGreater(len(explanation), 0)

    def test_confidence_threshold(self):
        intent = self.parser.parse("你好")
        self.assertLess(intent.confidence, 0.3)
        self.assertFalse(intent.is_valid())


# ============================================================
# 运行时类型测试
# ================================================= ============

class TestMathaType(unittest.TestCase):
    """MathaType 运行时类型测试。"""

    def test_to_int(self):
        self.assertEqual(MathaType.to_int(3.7), 3)
        self.assertEqual(MathaType.to_int("5"), 5)
        self.assertEqual(MathaType.to_int(None), 0)

    def test_to_float(self):
        self.assertEqual(MathaType.to_float(5), 5.0)
        self.assertEqual(MathaType.to_float("3.14"), 3.14)

    def test_to_str(self):
        self.assertEqual(MathaType.to_str(42), "42")
        self.assertEqual(MathaType.to_str(True), "true")
        self.assertEqual(MathaType.to_str(False), "false")

    def test_to_bool(self):
        self.assertTrue(MathaType.to_bool(1))
        self.assertFalse(MathaType.to_bool(0))
        self.assertTrue(MathaType.to_bool("true"))
        self.assertFalse(MathaType.to_bool("false"))

    def test_to_array(self):
        self.assertEqual(MathaType.to_array([1, 2]), [1, 2])
        self.assertEqual(MathaType.to_array(5), [5])
        self.assertEqual(MathaType.to_array("abc"), ["abc"])

    def test_coalesce(self):
        self.assertEqual(MathaType.coalesce(None, None, 3), 3)
        self.assertEqual(MathaType.coalesce(1, 2), 1)
        self.assertIsNone(MathaType.coalesce(None, None))


# ============================================================
# 入口
# ================================================= ============

if __name__ == "__main__":
    unittest.main(verbosity=2)
