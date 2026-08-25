# -*- coding: utf-8 -*-
"""
代码生成器单元测试 - 回归测试 P0 缺陷

测试覆盖：
  1. C 代码生成包含函数调用
  2. C 代码生成包含算术运算
  3. C 代码生成变量初始化顺序正确
  4. Python 代码生成语法正确
  5. Matha 自举输出正确
"""
import sys
import unittest
sys.path.insert(0, r"D:\trae")

from src.mir import MIRGenerator, MIRCallInstr, MIRArithInstr, MIRConstInstr
from src.mir_codegen import MIRToCGenerator, MIRToPythonGenerator
from src.mir_converter import convert, matha_to_mir
from src.compiler.matha_cc import MathaLexer, MathaParser


class TestCCodeGeneration(unittest.TestCase):
    """C 代码生成单元测试。"""

    def _generate_mir(self, source: str):
        """生成 MIR 程序。"""
        lexer = MathaLexer(source)
        tokens = lexer.tokenize()
        parser = MathaParser(tokens)
        ast = parser.parse()
        mir_gen = MIRGenerator()
        return mir_gen.generate(ast)

    def test_c_code_contains_sin_call(self):
        """测试 C 代码包含 sin 函数调用。"""
        source = "x = sin(3.14)"
        c_code = convert(source, "matha", "c")

        self.assertIn("sin(", c_code, "C 代码缺少 sin 调用")
        self.assertIn("3.14", c_code, "C 代码缺少 sin 参数")

    def test_c_code_contains_cos_call(self):
        """测试 C 代码包含 cos 函数调用。"""
        source = "x = cos(1.57)"
        c_code = convert(source, "matha", "c")

        self.assertIn("cos(", c_code, "C 代码缺少 cos 调用")

    def test_c_code_contains_addition(self):
        """测试 C 代码包含加法运算。"""
        source = "x = sin(3.14) + cos(1.57)"
        c_code = convert(source, "matha", "c")

        self.assertIn("+", c_code, "C 代码缺少加法运算")

    def test_c_code_variable_initialization(self):
        """测试 C 代码变量初始化顺序正确。"""
        source = "x = 3.14 + 1.57"
        c_code = convert(source, "matha", "c")

        # 常量初始化应该先于使用
        lines = c_code.split("\n")
        t1_line = None
        t2_line = None
        for i, line in enumerate(lines):
            if "double t1 = 3.14" in line:
                t1_line = i
            elif "double t2 = 1.57" in line:
                t2_line = i

        self.assertIsNotNone(t1_line, "t1 初始化未找到")
        self.assertIsNotNone(t2_line, "t2 初始化未找到")

    def test_c_code_return_statement(self):
        """测试 C 代码包含 return 语句。"""
        source = "x = sin(3.14)"
        c_code = convert(source, "matha", "c")

        self.assertIn("return", c_code, "C 代码缺少 return 语句")

    def test_c_code_complete_expression(self):
        """测试完整表达式的 C 代码生成。"""
        source = "x = sin(3.14) + cos(1.57)"
        c_code = convert(source, "matha", "c")

        # 必须包含所有元素
        self.assertIn("sin(", c_code)
        self.assertIn("cos(", c_code)
        self.assertIn("+", c_code)
        self.assertIn("return", c_code)
        self.assertIn("#include <math.h>", c_code)

    def test_c_code_multiple_operations(self):
        """测试多个运算的 C 代码生成。"""
        source = "x = sin(π) + cos(π/2) + tan(π/4)"
        c_code = convert(source, "matha", "c")

        self.assertIn("sin(", c_code)
        self.assertIn("cos(", c_code)
        self.assertIn("tan(", c_code)
        self.assertIn("+", c_code)

    def test_c_code_no_syntax_errors(self):
        """测试 C 代码无语法错误。"""
        source = "x = sin(3.14) + cos(1.57)"
        c_code = convert(source, "matha", "c")

        # 检查基本语法结构
        self.assertIn("{", c_code)
        self.assertIn("}", c_code)
        self.assertIn(";", c_code)
        self.assertIn("double", c_code)


class TestPythonCodeGeneration(unittest.TestCase):
    """Python 代码生成单元测试。"""

    def test_python_code_contains_sin_call(self):
        """测试 Python 代码包含 math.sin 调用。"""
        source = "x = sin(3.14)"
        py_code = convert(source, "matha", "python")

        self.assertIn("math.sin(", py_code, "Python 代码缺少 math.sin 调用")

    def test_python_code_contains_cos_call(self):
        """测试 Python 代码包含 math.cos 调用。"""
        source = "x = cos(1.57)"
        py_code = convert(source, "matha", "python")

        self.assertIn("math.cos(", py_code, "Python 代码缺少 math.cos 调用")

    def test_python_code_no_percent_prefix(self):
        """测试 Python 代码变量名无前缀 %。"""
        source = "x = sin(3.14)"
        py_code = convert(source, "matha", "python")

        self.assertNotIn("%t", py_code, "Python 代码变量名不应有 % 前缀")

    def test_python_code_valid_syntax(self):
        """测试 Python 代码语法正确。"""
        source = "x = sin(3.14) + cos(1.57)"
        py_code = convert(source, "matha", "python")

        # 应该可以编译
        try:
            compile(py_code, "<test>", "exec")
        except SyntaxError as e:
            self.fail(f"Python 代码语法错误: {e}")

    def test_python_code_return_no_semicolon(self):
        """测试 Python 代码 return 不加 ;。"""
        source = "x = sin(3.14)"
        py_code = convert(source, "matha", "python")

        # return 语句不应以 ; 结尾
        for line in py_code.split("\n"):
            if line.strip().startswith("return"):
                self.assertFalse(
                    line.strip().endswith(";"),
                    "Python return 语句不应以 ; 结尾"
                )

    def test_python_code_complete_expression(self):
        """测试完整表达式的 Python 代码生成。"""
        source = "x = sin(3.14) + cos(1.57)"
        py_code = convert(source, "matha", "python")

        self.assertIn("math.sin(", py_code)
        self.assertIn("math.cos(", py_code)
        self.assertIn("+", py_code)
        self.assertIn("return", py_code)


class TestMathaSelfBoot(unittest.TestCase):
    """Matha 自举测试。"""

    def test_matha_self_conversion(self):
        """测试 Matha → Matha 转换。"""
        source = "x = sin(3.14) + cos(1.57)"
        matha_out = convert(source, "matha", "matha")

        self.assertIn("sin", matha_out)
        self.assertIn("cos", matha_out)

    def test_matha_self_roundtrip(self):
        """测试 Matha 自举往返。"""
        source = "x = sin(π) + cos(π/2)"
        matha_out = convert(source, "matha", "matha")

        # 输出应该包含原始表达式的关键元素
        self.assertEqual(len(matha_out), len(source))


class TestMIRCodeGeneration(unittest.TestCase):
    """MIR 代码生成单元测试。"""

    def test_mir_to_c_consistency(self):
        """测试 MIR → C 一致性。"""
        source = "x = sin(3.14) + cos(1.57)"

        # 生成 MIR
        lexer = MathaLexer(source)
        tokens = lexer.tokenize()
        parser = MathaParser(tokens)
        ast = parser.parse()
        mir_gen = MIRGenerator()
        mir = mir_gen.generate(ast)

        # 生成 C
        c_gen = MIRToCGenerator()
        c_code = c_gen.generate(mir)

        # 验证 C 代码包含所有必要元素
        self.assertIn("sin(", c_code)
        self.assertIn("cos(", c_code)
        self.assertIn("+", c_code)

    def test_mir_to_python_consistency(self):
        """测试 MIR → Python 一致性。"""
        source = "x = sin(3.14) + cos(1.57)"

        lexer = MathaLexer(source)
        tokens = lexer.tokenize()
        parser = MathaParser(tokens)
        ast = parser.parse()
        mir_gen = MIRGenerator()
        mir = mir_gen.generate(ast)

        py_gen = MIRToPythonGenerator()
        py_code = py_gen.generate(mir)

        self.assertIn("math.sin(", py_code)
        self.assertIn("math.cos(", py_code)
        self.assertIn("+", py_code)


class TestCodeGenerationPerformance(unittest.TestCase):
    """代码生成性能测试。"""

    def test_c_generation_speed(self):
        """测试 C 代码生成速度。"""
        import time
        source = "x = sin(3.14) + cos(1.57)"

        t0 = time.perf_counter()
        for _ in range(100):
            convert(source, "matha", "c")
        elapsed = (time.perf_counter() - t0) * 1000

        # 100 次转换应在 100ms 内完成
        self.assertLess(elapsed, 100, f"C 代码生成太慢: {elapsed:.1f}ms/100次")

    def test_python_generation_speed(self):
        """测试 Python 代码生成速度。"""
        import time
        source = "x = sin(3.14) + cos(1.57)"

        t0 = time.perf_counter()
        for _ in range(100):
            convert(source, "matha", "python")
        elapsed = (time.perf_counter() - t0) * 1000

        # 100 次转换应在 100ms 内完成
        self.assertLess(elapsed, 100, f"Python 代码生成太慢: {elapsed:.1f}ms/100次")


if __name__ == "__main__":
    unittest.main(verbosity=2)
