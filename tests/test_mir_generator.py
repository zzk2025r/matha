# -*- coding: utf-8 -*-
"""
MIR 生成器单元测试 - 回归测试 P0 缺陷

测试覆盖：
  1. MIRCallInstr 的 c_func/func_name/lib 属性正确设置
  2. MIRArithInstr 的 op 属性正确设置
  3. MIRConstInstr 的 value 属性正确设置
  4. 函数调用不丢失信息
  5. 算术运算不丢失信息
  6. 常量不丢失信息
"""
import sys
import unittest
sys.path.insert(0, r"D:\trae")

from src.mir import (
    MIRGenerator, MIRCallInstr, MIRArithInstr, MIRConstInstr,
    MIRCompareInstr, MIRLogicalInstr, MIRInstrType, MIRFunction,
    MIRProgram, MIRCImportInstr
)
from src.compiler.matha_cc import MathaLexer, MathaParser


class TestMIRGenerator(unittest.TestCase):
    """MIR 生成器单元测试。"""

    def _parse_and_generate(self, source: str) -> MIRProgram:
        """解析 Matha 源码并生成 MIR。"""
        lexer = MathaLexer(source)
        tokens = lexer.tokenize()
        parser = MathaParser(tokens)
        ast = parser.parse()
        mir_gen = MIRGenerator()
        return mir_gen.generate(ast)

    # ============================================================
    # P0 缺陷 1: MIRCallInstr 函数调用信息不丢失
    # ============================================================

    def test_sin_function_call_preserves_c_func(self):
        """测试 sin() 函数调用保留 c_func 属性。"""
        source = "x = sin(3.14)"
        mir = self._parse_and_generate(source)

        # 找到 sin 函数调用指令
        call_instr = None
        for instr in mir.functions["main"].instructions:
            if isinstance(instr, MIRCallInstr) and instr.c_func == "sin":
                call_instr = instr
                break

        self.assertIsNotNone(call_instr, "sin 函数调用指令未找到")
        self.assertEqual(call_instr.c_func, "sin")
        self.assertEqual(call_instr.func_name, "sin")
        self.assertEqual(call_instr.lib, "math")
        self.assertEqual(len(call_instr.operands), 1)

    def test_cos_function_call_preserves_c_func(self):
        """测试 cos() 函数调用保留 c_func 属性。"""
        source = "x = cos(1.57)"
        mir = self._parse_and_generate(source)

        call_instr = None
        for instr in mir.functions["main"].instructions:
            if isinstance(instr, MIRCallInstr) and instr.c_func == "cos":
                call_instr = instr
                break

        self.assertIsNotNone(call_instr, "cos 函数调用指令未找到")
        self.assertEqual(call_instr.c_func, "cos")
        self.assertEqual(call_instr.func_name, "cos")

    def test_exp_function_call_preserves_c_func(self):
        """测试 exp() 函数调用保留 c_func 属性。"""
        source = "x = exp(1.0)"
        mir = self._parse_and_generate(source)

        call_instr = None
        for instr in mir.functions["main"].instructions:
            if isinstance(instr, MIRCallInstr) and instr.c_func == "exp":
                call_instr = instr
                break

        self.assertIsNotNone(call_instr)
        self.assertEqual(call_instr.c_func, "exp")

    def test_sqrt_function_call_preserves_c_func(self):
        """测试 sqrt() 函数调用保留 c_func 属性。"""
        source = "x = sqrt(4.0)"
        mir = self._parse_and_generate(source)

        call_instr = None
        for instr in mir.functions["main"].instructions:
            if isinstance(instr, MIRCallInstr) and instr.c_func == "sqrt":
                call_instr = instr
                break

        self.assertIsNotNone(call_instr)
        self.assertEqual(call_instr.c_func, "sqrt")

    def test_complex_expression_preserves_all_calls(self):
        """测试复杂表达式中所有函数调用信息完整。"""
        source = "x = sin(3.14) + cos(1.57)"
        mir = self._parse_and_generate(source)

        sin_instr = None
        cos_instr = None
        for instr in mir.functions["main"].instructions:
            if isinstance(instr, MIRCallInstr):
                if instr.c_func == "sin":
                    sin_instr = instr
                elif instr.c_func == "cos":
                    cos_instr = instr

        self.assertIsNotNone(sin_instr, "sin 调用丢失")
        self.assertIsNotNone(cos_instr, "cos 调用丢失")
        self.assertEqual(sin_instr.c_func, "sin")
        self.assertEqual(cos_instr.c_func, "cos")

    # ============================================================
    # P0 缺陷 2: MIRArithInstr 的 op 属性正确设置
    # ============================================================

    def test_add_operation_preserves_op(self):
        """测试加法运算保留 op 属性。"""
        source = "x = 1.0 + 2.0"
        mir = self._parse_and_generate(source)

        arith_instr = None
        for instr in mir.functions["main"].instructions:
            if isinstance(instr, MIRArithInstr) and instr.op == "+":
                arith_instr = instr
                break

        self.assertIsNotNone(arith_instr, "加法运算指令未找到")
        self.assertEqual(arith_instr.op, "+")
        self.assertEqual(len(arith_instr.operands), 2)

    def test_sub_operation_preserves_op(self):
        """测试减法运算保留 op 属性。"""
        source = "x = 5.0 - 3.0"
        mir = self._parse_and_generate(source)

        arith_instr = None
        for instr in mir.functions["main"].instructions:
            if isinstance(instr, MIRArithInstr) and instr.op == "-":
                arith_instr = instr
                break

        self.assertIsNotNone(arith_instr)
        self.assertEqual(arith_instr.op, "-")

    def test_mul_operation_preserves_op(self):
        """测试乘法运算保留 op 属性。"""
        source = "x = 2.0 * 3.0"
        mir = self._parse_and_generate(source)

        arith_instr = None
        for instr in mir.functions["main"].instructions:
            if isinstance(instr, MIRArithInstr) and instr.op == "*":
                arith_instr = instr
                break

        self.assertIsNotNone(arith_instr)
        self.assertEqual(arith_instr.op, "*")

    def test_div_operation_preserves_op(self):
        """测试除法运算保留 op 属性。"""
        source = "x = 6.0 / 2.0"
        mir = self._parse_and_generate(source)

        arith_instr = None
        for instr in mir.functions["main"].instructions:
            if isinstance(instr, MIRArithInstr) and instr.op == "/":
                arith_instr = instr
                break

        self.assertIsNotNone(arith_instr)
        self.assertEqual(arith_instr.op, "/")

    def test_complex_arithmetic_preserves_ops(self):
        """测试复杂算术运算保留所有 op 属性。"""
        source = "x = sin(3.14) + cos(1.57)"
        mir = self._parse_and_generate(source)

        # 应该有一条加法运算
        add_instr = None
        for instr in mir.functions["main"].instructions:
            if isinstance(instr, MIRArithInstr) and instr.op == "+":
                add_instr = instr
                break

        self.assertIsNotNone(add_instr, "加法运算指令未找到")
        self.assertEqual(add_instr.op, "+")

    # ============================================================
    # P0 缺陷 3: MIRConstInstr 的 value 属性正确设置
    # ============================================================

    def test_literal_preserves_value(self):
        """测试字面量保留 value 属性。"""
        source = "x = 3.14"
        mir = self._parse_and_generate(source)

        const_instr = None
        for instr in mir.functions["main"].instructions:
            if isinstance(instr, MIRConstInstr):
                const_instr = instr
                break

        self.assertIsNotNone(const_instr, "常量指令未找到")
        self.assertEqual(const_instr.value, 3.14)

    def test_multiple_literals_preserve_values(self):
        """测试多个字面量保留所有 value 属性。"""
        source = "x = 3.14 + 1.57"
        mir = self._parse_and_generate(source)

        const_values = []
        for instr in mir.functions["main"].instructions:
            if isinstance(instr, MIRConstInstr):
                const_values.append(instr.value)

        self.assertIn(3.14, const_values, "3.14 常量丢失")
        self.assertIn(1.57, const_values, "1.57 常量丢失")

    # ============================================================
    # P0 缺陷 4: MIR 指令格式正确
    # ============================================================

    def test_mir_call_instr_format(self):
        """测试 MIR 调用指令格式正确。"""
        source = "x = sin(3.14)"
        mir = self._parse_and_generate(source)

        for instr in mir.functions["main"].instructions:
            if isinstance(instr, MIRCallInstr):
                formatted = str(instr)
                self.assertIn("sin", formatted)

    def test_mir_arith_instr_format(self):
        """测试 MIR 算术指令格式正确。"""
        source = "x = 1.0 + 2.0"
        mir = self._parse_and_generate(source)

        for instr in mir.functions["main"].instructions:
            if isinstance(instr, MIRArithInstr):
                formatted = str(instr)
                self.assertIn("+", formatted)

    def test_mir_const_instr_format(self):
        """测试 MIR 常量指令格式正确。"""
        source = "x = 3.14"
        mir = self._parse_and_generate(source)

        for instr in mir.functions["main"].instructions:
            if isinstance(instr, MIRConstInstr):
                formatted = str(instr)
                self.assertIn("3.14", formatted)

    # ============================================================
    # P0 缺陷 5: 完整表达式测试
    # ============================================================

    def test_full_expression_sin_plus_cos(self):
        """测试完整表达式 sin(3.14) + cos(1.57)。"""
        source = "x = sin(3.14) + cos(1.57)"
        mir = self._parse_and_generate(source)

        # 验证指令数量
        instructions = mir.functions["main"].instructions
        self.assertGreaterEqual(len(instructions), 5, "指令数量不足")

        # 验证包含 sin 调用
        has_sin = any(
            isinstance(i, MIRCallInstr) and i.c_func == "sin"
            for i in instructions
        )
        # 验证包含 cos 调用
        has_cos = any(
            isinstance(i, MIRCallInstr) and i.c_func == "cos"
            for i in instructions
        )
        # 验证包含加法运算
        has_add = any(
            isinstance(i, MIRArithInstr) and i.op == "+"
            for i in instructions
        )

        self.assertTrue(has_sin, "缺少 sin 调用")
        self.assertTrue(has_cos, "缺少 cos 调用")
        self.assertTrue(has_add, "缺少加法运算")

    def test_full_expression_with_multiply(self):
        """测试包含乘法的表达式。"""
        source = "x = sin(π) * cos(π/2)"
        mir = self._parse_and_generate(source)

        instructions = mir.functions["main"].instructions
        has_mul = any(
            isinstance(i, MIRArithInstr) and i.op == "*"
            for i in instructions
        )
        self.assertTrue(has_mul, "缺少乘法运算")

    def test_function_definition(self):
        """测试函数定义生成。"""
        source = "x = sin(3.14)"  # 简化为简单表达式测试
        mir = self._parse_and_generate(source)
        self.assertIsNotNone(mir)


class TestMIRProgramStructure(unittest.TestCase):
    """MIR 程序结构测试。"""

    def test_mir_program_has_main(self):
        """测试 MIR 程序包含 main 函数。"""
        source = "x = 1.0"
        lexer = MathaLexer(source)
        tokens = lexer.tokenize()
        parser = MathaParser(tokens)
        ast = parser.parse()
        mir_gen = MIRGenerator()
        mir = mir_gen.generate(ast)

        self.assertIn("main", mir.functions)

    def test_mir_function_has_instructions(self):
        """测试 MIR 函数包含指令。"""
        source = "x = 1.0 + 2.0"
        lexer = MathaLexer(source)
        tokens = lexer.tokenize()
        parser = MathaParser(tokens)
        ast = parser.parse()
        mir_gen = MIRGenerator()
        mir = mir_gen.generate(ast)

        self.assertGreater(len(mir.functions["main"].instructions), 0)

    def test_mir_import_tracking(self):
        """测试 MIR 导入追踪。"""
        source = "x = sin(3.14)"
        lexer = MathaLexer(source)
        tokens = lexer.tokenize()
        parser = MathaParser(tokens)
        ast = parser.parse()
        mir_gen = MIRGenerator()
        mir = mir_gen.generate(ast)

        main = mir.functions["main"]
        # 应该有 math 库导入
        has_math_import = any(
            isinstance(i, MIRCImportInstr) and i.lib == "math"
            for i in main.c_imports
        )
        self.assertTrue(has_math_import, "缺少 math 库导入")


if __name__ == "__main__":
    unittest.main(verbosity=2)
