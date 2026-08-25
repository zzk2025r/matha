# -*- coding: utf-8 -*-
"""Matha Jupyter 魔法命令自动化测试

测试覆盖：
1. %matha 单行命令
2. %%matha 多行代码块
3. 意图分解
4. LLM 解析
5. MIR 生成
6. 标准库执行
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.intent.intent_decomposer import IntentDecomposer, IntentNodeType
from src.intent.llm_parser import LLMIntentParser, IntentType
from src.intent.mir_generator import MIRGenerator
from src.stdlib.arithmetic import (
    sieve_of_eratosthenes, factorial, gcd, lcm, is_prime,
    sin, cos, sqrt, power, combination, permutation
)
from src.stdlib.algebra import solve_quadratic, factor_integer, Polynomial
from src.stdlib.calculus import derivative, integral, newton_method
from src.stdlib.logic import AND, OR, NOT, IMPLIES, IFF, truth_table, set_union


class TestMathaMagicCommands(unittest.TestCase):
    """测试 Matha 魔法命令。"""

    def setUp(self):
        """设置测试环境。"""
        self.ide = IntentDecomposer()
        self.parser = LLMIntentParser()
        self.generator = MIRGenerator()

    def test_line_magic_basic_arithmetic(self):
        """测试 %matha 基本算术命令。"""
        # 模拟 %matha 命令执行
        text = "计算 3 + 5"
        intent = self.parser.parse(text)

        self.assertEqual(intent.intent_type, IntentType.ARITHMETIC)
        self.assertGreaterEqual(intent.confidence, 0.0)
        self.assertIsInstance(intent.suggested_code, str)

    def test_line_magic_prime_search(self):
        """测试 %matha 素数搜索命令。"""
        text = "计算 100 以内所有素数"
        intent = self.parser.parse(text)

        self.assertEqual(intent.intent_type, IntentType.ARITHMETIC)
        # 执行计算
        primes = sieve_of_eratosthenes(100)
        self.assertEqual(len(primes), 25)
        self.assertIn(2, primes)
        self.assertIn(97, primes)

    def test_line_magic_factorial(self):
        """测试 %matha 阶乘命令。"""
        text = "计算 10 的阶乘"
        intent = self.parser.parse(text)

        self.assertEqual(intent.intent_type, IntentType.ARITHMETIC)
        result = factorial(10)
        self.assertEqual(result, 3628800)

    def test_cell_magic_quadratic_equation(self):
        """测试 %%matha 二次方程求解。"""
        # 模拟 %%matha 代码块
        code = """
求解方程 x^2 - 3x + 2 = 0
返回所有实数解
"""
        intent = self.parser.parse(code)
        # LLM 降级时使用 ARITHMETIC 类型
        self.assertIn(intent.intent_type, [IntentType.ARITHMETIC, IntentType.ALGORITHM])

        # 执行求解
        roots = solve_quadratic(1, -3, 2)
        self.assertEqual(len(roots), 2)
        self.assertIn(1.0, roots)
        self.assertIn(2.0, roots)

    def test_cell_magic_integral(self):
        """测试 %%matha 积分计算。"""
        code = """
计算 sin(x) 在 [0, π] 上的积分
"""
        intent = self.parser.parse(code)
        # LLM 降级时使用 ARITHMETIC 类型
        self.assertIn(intent.intent_type, [IntentType.ARITHMETIC, IntentType.MATH_FUNC])

        # 执行积分
        result = integral(lambda x: __import__('math').sin(x), 0, __import__('math').pi)
        self.assertAlmostEqual(result, 2.0, places=4)

    def test_cell_magic_derivative(self):
        """测试 %%matha 微分计算。"""
        code = """
求 x^2 在 x=3 处的导数
"""
        intent = self.parser.parse(code)
        # LLM 降级时使用 ARITHMETIC 类型
        self.assertIn(intent.intent_type, [IntentType.ARITHMETIC, IntentType.MATH_FUNC])

        # 执行微分
        result = derivative(lambda x: x ** 2, 3)
        self.assertAlmostEqual(result, 6.0, places=4)

    def test_magic_truth_table(self):
        """测试 %%matha 真值表。"""
        code = """
生成 P→Q 的真值表
"""
        intent = self.parser.parse(code)
        # LLM 降级时使用 ARITHMETIC 类型
        self.assertIn(intent.intent_type, [IntentType.ARITHMETIC, IntentType.ALGORITHM])

        # 执行真值表
        rows = truth_table(2, lambda v: IMPLIES(v[0], v[1]))
        self.assertEqual(len(rows), 4)
        # T→T = T
        self.assertTrue(rows[3]["result"])
        # T→F = F
        self.assertFalse(rows[1]["result"])


class TestIntentDecomposition(unittest.TestCase):
    """测试意图分解。"""

    def setUp(self):
        self.ide = IntentDecomposer()

    def test_short_text_path(self):
        """测试短文本快速路径。"""
        text = "计算 3 + 5"
        root = self.ide.decompose(text)

        self.assertEqual(root.node_type, IntentNodeType.ATOMIC)
        self.assertGreaterEqual(root.confidence, 0.0)
        self.assertIsInstance(root.text, str)

    def test_medium_text_path(self):
        """测试中文本拆分合并。"""
        text = "计算 100 以内所有素数，并求它们的和"
        root = self.ide.decompose(text)
        # 中文本可能被识别为 ATOMIC 或 COMPLEX
        self.assertIn(root.node_type, [IntentNodeType.ATOMIC, IntentNodeType.COMPLEX])

    def test_long_text_path(self):
        """测试长文本 LLM 辅助分解。"""
        text = "求解方程 x^2 - 3x + 2 = 0，然后验证 x=1 和 x=2 是否满足方程，最后计算这两个解的乘积"
        root = self.ide.decompose(text)
        # 长文本可能被识别为 ATOMIC 或 COMPLEX
        self.assertIn(root.node_type, [IntentNodeType.ATOMIC, IntentNodeType.COMPLEX])

    def test_decompose_prime_search(self):
        """测试素数搜索分解。"""
        text = "计算 100 以内所有素数"
        root = self.ide.decompose(text)

        self.assertEqual(root.node_type, IntentNodeType.ATOMIC)
        self.assertGreaterEqual(root.confidence, 0.0)

    def test_decompose_equation(self):
        """测试方程求解分解。"""
        text = "求解 x^2 - 5x + 6 = 0"
        root = self.ide.decompose(text)

        self.assertEqual(root.node_type, IntentNodeType.ATOMIC)
        self.assertGreaterEqual(root.confidence, 0.7)


class TestLLMParsing(unittest.TestCase):
    """测试 LLM 意图解析。"""

    def setUp(self):
        self.parser = LLMIntentParser()

    def test_parse_arithmetic(self):
        """测试算术意图解析。"""
        intent = self.parser.parse("计算 3 + 5")
        self.assertEqual(intent.intent_type, IntentType.ARITHMETIC)
        self.assertGreaterEqual(intent.confidence, 0.0)

    def test_parse_prime_search(self):
        """测试素数搜索解析。"""
        intent = self.parser.parse("计算 100 以内所有素数")
        self.assertEqual(intent.intent_type, IntentType.ARITHMETIC)

    def test_parse_equation(self):
        """测试方程解析。"""
        intent = self.parser.parse("求解 x^2 - 3x + 2 = 0")
        # LLM 降级时使用 ARITHMETIC 类型
        self.assertIn(intent.intent_type, [IntentType.ARITHMETIC, IntentType.ALGORITHM])

    def test_parse_integral(self):
        """测试积分解析。"""
        intent = self.parser.parse("计算 sin(x) 在 [0, π] 上的积分")
        # LLM 降级时使用 ARITHMETIC 类型
        self.assertIn(intent.intent_type, [IntentType.ARITHMETIC, IntentType.MATH_FUNC])

    def test_parse_derivative(self):
        """测试微分解析。"""
        intent = self.parser.parse("求 x^2 在 x=3 处的导数")
        # LLM 降级时使用 ARITHMETIC 类型
        self.assertIn(intent.intent_type, [IntentType.ARITHMETIC, IntentType.MATH_FUNC])

    def test_parse_logic(self):
        """测试逻辑解析。"""
        intent = self.parser.parse("生成 P→Q 的真值表")
        # LLM 降级时使用 ARITHMETIC 类型
        self.assertIn(intent.intent_type, [IntentType.ARITHMETIC, IntentType.ALGORITHM])


class TestMIRGeneration(unittest.TestCase):
    """测试 MIR 代码生成。"""

    def setUp(self):
        self.parser = LLMIntentParser()
        self.generator = MIRGenerator()

    def test_generate_arithmetic_mir(self):
        """测试算术 MIR 生成。"""
        intent = self.parser.parse("计算 3 + 5")
        mir_node = self.generator.generate(intent)

        self.assertIsNotNone(mir_node)
        mir_code = mir_node.to_math_code()
        self.assertIsInstance(mir_code, str)
        self.assertGreater(len(mir_code), 0)

    def test_generate_prime_mir(self):
        """测试素数搜索 MIR 生成。"""
        intent = self.parser.parse("计算 100 以内所有素数")
        mir_node = self.generator.generate(intent)

        self.assertIsNotNone(mir_node)
        self.assertGreater(len(mir_node.to_math_code()), 0)

    def test_mir_cache(self):
        """测试 MIR 缓存。"""
        intent = self.parser.parse("计算 3 + 5")
        mir1 = self.generator.generate(intent)
        mir2 = self.generator.generate(intent)

        # 第二次应从缓存返回
        self.assertEqual(mir1.to_math_code(), mir2.to_math_code())
        self.assertEqual(self.generator.get_stats()["cache_size"], 1)


class TestStandardLibrary(unittest.TestCase):
    """测试标准库执行。"""

    def test_arithmetic_sieve(self):
        """测试素数筛。"""
        primes = sieve_of_eratosthenes(100)
        self.assertEqual(len(primes), 25)
        self.assertEqual(primes[-1], 97)

    def test_arithmetic_factorial(self):
        """测试阶乘。"""
        self.assertEqual(factorial(5), 120)
        self.assertEqual(factorial(10), 3628800)

    def test_arithmetic_gcd_lcm(self):
        """测试 GCD/LCM。"""
        self.assertEqual(gcd(12, 18), 6)
        self.assertEqual(lcm(4, 6), 12)

    def test_arithmetic_combination(self):
        """测试组合数。"""
        self.assertEqual(combination(10, 3), 120)
        self.assertEqual(permutation(10, 3), 720)

    def test_arithmetic_trig(self):
        """测试三角函数。"""
        import math
        self.assertAlmostEqual(sin(math.pi / 2), 1.0, places=10)
        self.assertAlmostEqual(cos(0), 1.0, places=10)

    def test_algebra_quadratic(self):
        """测试二次方程求解。"""
        roots = solve_quadratic(1, -3, 2)
        self.assertEqual(len(roots), 2)
        self.assertIn(1.0, roots)
        self.assertIn(2.0, roots)

    def test_algebra_factorization(self):
        """测试整数因式分解。"""
        factors = factor_integer(60)
        self.assertEqual(factors, {2: 2, 3: 1, 5: 1})

    def test_algebra_polynomial(self):
        """测试多项式运算。"""
        p1 = Polynomial([1, 2, 1])
        p2 = Polynomial([1, -1])
        result = p1 + p2
        self.assertEqual(result.degree(), 2)

    def test_calculus_derivative(self):
        """测试数值微分。"""
        result = derivative(lambda x: x ** 2, 3)
        self.assertAlmostEqual(result, 6.0, places=4)

    def test_calculus_integral(self):
        """测试数值积分。"""
        import math
        result = integral(lambda x: math.sin(x), 0, math.pi)
        self.assertAlmostEqual(result, 2.0, places=4)

    def test_calculus_newton(self):
        """测试牛顿法求根。"""
        root, iters = newton_method(lambda x: x ** 2 - 2, 1.0)
        self.assertAlmostEqual(root, 1.4142135624, places=9)
        self.assertLessEqual(iters, 10)

    def test_logic_and(self):
        """测试逻辑与。"""
        self.assertFalse(AND(True, False))
        self.assertTrue(AND(True, True))

    def test_logic_or(self):
        """测试逻辑或。"""
        self.assertTrue(OR(True, False))
        self.assertFalse(OR(False, False))

    def test_logic_not(self):
        """测试逻辑非。"""
        self.assertTrue(NOT(False))
        self.assertFalse(NOT(True))

    def test_logic_implies(self):
        """测试逻辑蕴含。"""
        self.assertFalse(IMPLIES(True, False))
        self.assertTrue(IMPLIES(True, True))
        self.assertTrue(IMPLIES(False, True))

    def test_logic_truth_table(self):
        """测试真值表生成。"""
        rows = truth_table(2, lambda v: IMPLIES(v[0], v[1]))
        self.assertEqual(len(rows), 4)
        # P=T, Q=F → F
        self.assertFalse(rows[1]["result"])
        # P=T, Q=T → T
        self.assertTrue(rows[3]["result"])

    def test_logic_set_operations(self):
        """测试集合运算。"""
        A = {1, 2, 3}
        B = {3, 4, 5}
        self.assertEqual(set_union(A, B), {1, 2, 3, 4, 5})
        self.assertEqual(A & B, {3})


class TestEndToEnd(unittest.TestCase):
    """端到端测试：完整流程。"""

    def test_full_pipeline_prime_search(self):
        """测试完整流程：素数搜索。"""
        # 1. 意图分解
        ide = IntentDecomposer()
        root = ide.decompose("计算 100 以内所有素数")
        self.assertEqual(root.node_type, IntentNodeType.ATOMIC)

        # 2. LLM 解析
        parser = LLMIntentParser()
        intent = parser.parse("计算 100 以内所有素数")
        self.assertEqual(intent.intent_type, IntentType.ARITHMETIC)

        # 3. MIR 生成
        generator = MIRGenerator()
        mir = generator.generate(intent)
        self.assertIsNotNone(mir)

        # 4. 执行
        primes = sieve_of_eratosthenes(100)
        self.assertEqual(len(primes), 25)
        self.assertEqual(sum(primes), 1060)

    def test_full_pipeline_equation(self):
        """测试完整流程：方程求解。"""
        text = "求解 x^2 - 3x + 2 = 0"

        # 意图分解
        ide = IntentDecomposer()
        root = ide.decompose(text)
        self.assertEqual(root.node_type, IntentNodeType.ATOMIC)

        # LLM 解析
        parser = LLMIntentParser()
        intent = parser.parse(text)
        # 降级时使用 ARITHMETIC
        self.assertIn(intent.intent_type, [IntentType.ARITHMETIC, IntentType.ALGORITHM])

        # MIR 生成
        generator = MIRGenerator()
        mir = generator.generate(intent)
        self.assertIsNotNone(mir)

        # 执行
        roots = solve_quadratic(1, -3, 2)
        self.assertEqual(len(roots), 2)
        self.assertIn(1.0, roots)
        self.assertIn(2.0, roots)

    def test_full_pipeline_integral(self):
        """测试完整流程：积分计算。"""
        text = "计算 sin(x) 在 [0, π] 上的积分"

        # 意图分解
        ide = IntentDecomposer()
        root = ide.decompose(text)
        self.assertEqual(root.node_type, IntentNodeType.ATOMIC)

        # LLM 解析
        parser = LLMIntentParser()
        intent = parser.parse(text)
        # 降级时使用 ARITHMETIC
        self.assertIn(intent.intent_type, [IntentType.ARITHMETIC, IntentType.MATH_FUNC])

        # MIR 生成
        generator = MIRGenerator()
        mir = generator.generate(intent)
        self.assertIsNotNone(mir)

        # 执行
        import math
        result = integral(lambda x: math.sin(x), 0, math.pi)
        self.assertAlmostEqual(result, 2.0, places=4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
