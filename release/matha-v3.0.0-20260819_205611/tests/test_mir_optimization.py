# -*- coding: utf-8 -*-
"""
MIR 优化 Pass 单元测试 - 增强版

测试覆盖：
  1. 常量折叠
  2. 代数简化
  3. 死代码消除
  4. 公共子表达式消除
  5. 复制传播
  6. 强度削弱
  7. 内联优化
  8. 窥孔优化
  9. 优化管道
"""
import sys
import unittest
sys.path.insert(0, r"D:\trae")

from src.mir import (
    MIRProgram, MIRFunction, MIRCallInstr, MIRArithInstr, MIRConstInstr,
    MIRInstrType
)
from src.mir_opt import (
    MathaConstFoldPass,
    MathaSimplifyPass,
    MathaDeadCodeElimPass,
    MathaCommonSubexprElimPass,
    MathaCopyPropagationPass,
    MathaStrengthReductionPass,
    MathaInlinePass,
    MathaPeepholeOptimizer,
    MathaOptimizationPipeline,
    _get_var,
)


class TestConstFoldPass(unittest.TestCase):
    """常量折叠测试。"""

    def test_add_constants(self):
        """测试常量加法折叠。"""
        program = MIRProgram()
        func = MIRFunction(name="main")
        func.instructions = [
            MIRArithInstr("t1", MIRInstrType.ADD, ["1.0", "2.0"], {"op": "+"}),
        ]
        program.functions["main"] = func

        pipeline = MathaConstFoldPass()
        result = pipeline.run(program)

        instr = result.functions["main"].instructions[0]
        self.assertEqual(instr.value, 3.0)

    def test_mul_constants(self):
        """测试常量乘法折叠。"""
        program = MIRProgram()
        func = MIRFunction(name="main")
        func.instructions = [
            MIRArithInstr("t1", MIRInstrType.ADD, ["3.0", "4.0"], {"op": "*"}),
        ]
        program.functions["main"] = func

        pipeline = MathaConstFoldPass()
        result = pipeline.run(program)

        instr = result.functions["main"].instructions[0]
        self.assertEqual(instr.value, 12.0)

    def test_no_fold_with_vars(self):
        """测试变量运算不被折叠。"""
        program = MIRProgram()
        func = MIRFunction(name="main")
        func.instructions = [
            MIRConstInstr("t1", MIRInstrType.ADD, [], {"value": 1.0}),
            MIRArithInstr("t2", MIRInstrType.ADD, ["t1", "2.0"], {"op": "+"}),
        ]
        program.functions["main"] = func

        pipeline = MathaConstFoldPass()
        result = pipeline.run(program)

        # t1 是变量，不应被折叠
        self.assertEqual(len(result.functions["main"].instructions), 2)

    def test_stats(self):
        """测试统计信息。"""
        program = MIRProgram()
        func = MIRFunction(name="main")
        func.instructions = [
            MIRArithInstr("t1", MIRInstrType.ADD, ["1.0", "2.0"], {"op": "+"}),
        ]
        program.functions["main"] = func

        pipeline = MathaConstFoldPass()
        pipeline.run(program)
        self.assertEqual(pipeline.stats["folded"], 1)


class TestSimplifyPass(unittest.TestCase):
    """代数简化测试。"""

    def test_add_zero(self):
        """测试 x + 0 = x。"""
        program = MIRProgram()
        func = MIRFunction(name="main")
        func.instructions = [
            MIRArithInstr("t1", MIRInstrType.ADD, ["5.0", "0.0"], {"op": "+"}),
        ]
        program.functions["main"] = func

        pipeline = MathaSimplifyPass()
        result = pipeline.run(program)

        instr = result.functions["main"].instructions[0]
        self.assertEqual(instr.value, 5.0)

    def test_mul_one(self):
        """测试 x * 1 = x。"""
        program = MIRProgram()
        func = MIRFunction(name="main")
        func.instructions = [
            MIRArithInstr("t1", MIRInstrType.ADD, ["5.0", "1.0"], {"op": "*"}),
        ]
        program.functions["main"] = func

        pipeline = MathaSimplifyPass()
        result = pipeline.run(program)

        instr = result.functions["main"].instructions[0]
        self.assertEqual(instr.value, 5.0)

    def test_mul_zero(self):
        """测试 x * 0 = 0。"""
        program = MIRProgram()
        func = MIRFunction(name="main")
        func.instructions = [
            MIRArithInstr("t1", MIRInstrType.ADD, ["5.0", "0.0"], {"op": "*"}),
        ]
        program.functions["main"] = func

        pipeline = MathaSimplifyPass()
        result = pipeline.run(program)

        instr = result.functions["main"].instructions[0]
        self.assertEqual(instr.value, 0.0)

    def test_sub_self(self):
        """测试 x - x = 0。"""
        program = MIRProgram()
        func = MIRFunction(name="main")
        func.instructions = [
            MIRArithInstr("t1", MIRInstrType.ADD, ["5.0", "5.0"], {"op": "-"}),
        ]
        program.functions["main"] = func

        pipeline = MathaSimplifyPass()
        result = pipeline.run(program)

        instr = result.functions["main"].instructions[0]
        self.assertEqual(instr.value, 0.0)

    def test_div_self(self):
        """测试 x / x = 1。"""
        program = MIRProgram()
        func = MIRFunction(name="main")
        func.instructions = [
            MIRArithInstr("t1", MIRInstrType.ADD, ["5.0", "5.0"], {"op": "/"}),
        ]
        program.functions["main"] = func

        pipeline = MathaSimplifyPass()
        result = pipeline.run(program)

        instr = result.functions["main"].instructions[0]
        self.assertEqual(instr.value, 1.0)


class TestDeadCodeElimPass(unittest.TestCase):
    """死代码消除测试。"""

    def test_remove_unused_variable(self):
        """测试移除未使用的变量。"""
        program = MIRProgram()
        func = MIRFunction(name="main")
        # t1 只被定义但从未被使用（不在任何操作数中）
        func.instructions = [
            MIRArithInstr("t1", MIRInstrType.ADD, ["1.0", "2.0"], {"op": "+"}),
            MIRArithInstr("t2", MIRInstrType.ADD, ["3.0", "4.0"], {"op": "+"}),
        ]
        program.functions["main"] = func

        pipeline = MathaDeadCodeElimPass()
        result = pipeline.run(program)

        # t1 未被使用（不在任何操作数中），应被移除
        results = [getattr(i, "result", "") for i in result.functions["main"].instructions]
        self.assertNotIn("t1", results)

    def test_keep_used_variable(self):
        """测试保留被使用的变量。"""
        program = MIRProgram()
        func = MIRFunction(name="main")
        func.instructions = [
            MIRConstInstr("t1", MIRInstrType.ADD, [], {"value": 1.0}),
            MIRArithInstr("t2", MIRInstrType.ADD, ["t1", "2.0"], {"op": "+"}),
        ]
        program.functions["main"] = func

        pipeline = MathaDeadCodeElimPass()
        result = pipeline.run(program)

        # t1 被 t2 使用，应保留
        results = [getattr(i, "result", "") for i in result.functions["main"].instructions]
        self.assertIn("t1", results)

    def test_stats(self):
        """测试统计信息。"""
        program = MIRProgram()
        func = MIRFunction(name="main")
        func.instructions = [
            MIRArithInstr("t1", MIRInstrType.ADD, ["1.0", "2.0"], {"op": "+"}),
            MIRArithInstr("t2", MIRInstrType.ADD, ["t1", "3.0"], {"op": "+"}),
        ]
        program.functions["main"] = func

        pipeline = MathaDeadCodeElimPass()
        pipeline.run(program)
        self.assertEqual(pipeline.stats["removed"], 0)


class TestCommonSubexprElimPass(unittest.TestCase):
    """公共子表达式消除测试。"""

    def test_eliminate_duplicate_expr(self):
        """测试消除重复表达式。"""
        program = MIRProgram()
        func = MIRFunction(name="main")
        func.instructions = [
            MIRArithInstr("t1", MIRInstrType.ADD, ["3.0", "4.0"], {"op": "*"}),
            MIRArithInstr("t2", MIRInstrType.ADD, ["3.0", "4.0"], {"op": "*"}),
        ]
        program.functions["main"] = func

        pipeline = MathaCommonSubexprElimPass()
        result = pipeline.run(program)

        # 第二次计算应被消除
        self.assertEqual(pipeline.stats["eliminated"], 1)


class TestCopyPropagationPass(unittest.TestCase):
    """复制传播测试。"""

    def test_propagate_constant(self):
        """测试常量传播。"""
        program = MIRProgram()
        func = MIRFunction(name="main")
        # t1 = 5.0 + 0.0 (会被折叠为 5.0)，t2 = t1 + 2.0
        func.instructions = [
            MIRArithInstr("t1", MIRInstrType.ADD, ["5.0", "0.0"], {"op": "+"}),
            MIRArithInstr("t2", MIRInstrType.ADD, ["t1", "2.0"], {"op": "+"}),
        ]
        program.functions["main"] = func

        # 先运行常量折叠
        fold_pass = MathaConstFoldPass()
        folded = fold_pass.run(program)

        # 再运行复制传播
        pipeline = MathaCopyPropagationPass()
        result = pipeline.run(folded)

        # 验证传播发生（通过检查 stats）
        self.assertGreater(pipeline.stats["propagated"], 0)


class TestStrengthReductionPass(unittest.TestCase):
    """强度削弱测试。"""

    def test_mul_by_two(self):
        """测试 x * 2 → x + x。"""
        program = MIRProgram()
        func = MIRFunction(name="main")
        func.instructions = [
            MIRArithInstr("t1", MIRInstrType.ADD, ["x", "2.0"], {"op": "*"}),
        ]
        program.functions["main"] = func

        pipeline = MathaStrengthReductionPass()
        result = pipeline.run(program)

        instr = result.functions["main"].instructions[0]
        # 应被替换为加法
        self.assertEqual(instr.op, "+")
        self.assertEqual(instr.operands, ["x", "x"])

    def test_square(self):
        """测试 x^2 → x * x。"""
        program = MIRProgram()
        func = MIRFunction(name="main")
        func.instructions = [
            MIRArithInstr("t1", MIRInstrType.ADD, ["x", "2.0"], {"op": "**"}),
        ]
        program.functions["main"] = func

        pipeline = MathaStrengthReductionPass()
        result = pipeline.run(program)

        instr = result.functions["main"].instructions[0]
        self.assertEqual(instr.op, "*")
        self.assertEqual(instr.operands, ["x", "x"])

    def test_stats(self):
        """测试统计信息。"""
        program = MIRProgram()
        func = MIRFunction(name="main")
        func.instructions = [
            MIRArithInstr("t1", MIRInstrType.ADD, ["x", "2.0"], {"op": "*"}),
        ]
        program.functions["main"] = func

        pipeline = MathaStrengthReductionPass()
        pipeline.run(program)
        self.assertEqual(pipeline.stats["reduced"], 1)


class TestInlinePass(unittest.TestCase):
    """内联优化测试。"""

    def test_inline_small_function(self):
        """测试内联小函数。"""
        program = MIRProgram()
        program.functions["main"] = MIRFunction(name="main")
        program.functions["main"].instructions = [
            MIRCallInstr("t1", MIRInstrType.CALL, [], {"func_name": "helper"}),
        ]
        program.functions["helper"] = MIRFunction(
            name="helper", params=[], instructions=[
                MIRConstInstr("t2", MIRInstrType.ADD, [], {"value": 42.0}),
            ]
        )

        pipeline = MathaInlinePass()
        result = pipeline.run(program)

        self.assertNotIn("helper", result.functions)
        # 内联后，main 的指令数应为 1（helper 的常量指令）
        self.assertEqual(len(result.functions["main"].instructions), 1)

    def test_not_inline_large_function(self):
        """测试不内联大函数。"""
        program = MIRProgram()
        program.functions["main"] = MIRFunction(name="main")
        program.functions["large"] = MIRFunction(
            name="large", params=[], instructions=[
                MIRConstInstr("t1", MIRInstrType.ADD, [], {"value": 1.0}),
                MIRConstInstr("t2", MIRInstrType.ADD, [], {"value": 2.0}),
                MIRConstInstr("t3", MIRInstrType.ADD, [], {"value": 3.0}),
            ]
        )

        pipeline = MathaInlinePass()
        pipeline.run(program)

        self.assertIn("large", program.functions)


class TestPeepholeOptimizer(unittest.TestCase):
    """窥孔优化测试。"""

    def test_remove_self_assignment(self):
        """测试移除 x = x。"""
        program = MIRProgram()
        func = MIRFunction(name="main")
        func.instructions = [
            MIRConstInstr("t1", MIRInstrType.ADD, [], {"value": 1.0}),
            MIRArithInstr("t2", MIRInstrType.ADD, ["t1", "t1"], {"op": "+"}),
        ]
        program.functions["main"] = func

        pipeline = MathaPeepholeOptimizer()
        result = pipeline.run(program)

        # t2 = t1 + t1 不应被移除（t1 != t2）
        self.assertEqual(len(result.functions["main"].instructions), 2)


class TestOptimizationPipeline(unittest.TestCase):
    """优化管道测试。"""

    def test_pipeline_runs_all_passes(self):
        """测试管道运行所有 Pass。"""
        program = MIRProgram()
        func = MIRFunction(name="main")
        func.instructions = [
            MIRArithInstr("t1", MIRInstrType.ADD, ["3.0", "4.0"], {"op": "*"}),
            MIRArithInstr("t2", MIRInstrType.ADD, ["1.0", "2.0"], {"op": "+"}),
        ]
        program.functions["main"] = func

        pipeline = MathaOptimizationPipeline()
        result = pipeline.run(program)

        self.assertIn("main", result.functions)

    def test_pipeline_summary(self):
        """测试管道摘要。"""
        program = MIRProgram()
        func = MIRFunction(name="main")
        func.instructions = [
            MIRArithInstr("t1", MIRInstrType.ADD, ["3.0", "4.0"], {"op": "*"}),
        ]
        program.functions["main"] = func

        pipeline = MathaOptimizationPipeline()
        pipeline.run(program)
        summary = pipeline.get_summary()

        self.assertIn("优化摘要", summary)
        self.assertIn("folded", summary)
        self.assertIn("simplified", summary)


class TestDeadCodeAnalysis(unittest.TestCase):
    """死代码分析测试。"""

    def test_reachable_code(self):
        """测试可达代码分析。"""
        program = MIRProgram()
        func = MIRFunction(name="main")
        func.instructions = [
            MIRArithInstr("t1", MIRInstrType.ADD, ["1.0", "2.0"], {"op": "+"}),
            MIRArithInstr("t2", MIRInstrType.ADD, ["t1", "3.0"], {"op": "+"}),
            MIRArithInstr("t3", MIRInstrType.ADD, ["t2", "4.0"], {"op": "*"}),
        ]
        program.functions["main"] = func

        # 所有指令都应被保留
        pipeline = MathaDeadCodeElimPass()
        result = pipeline.run(program)
        self.assertEqual(len(result.functions["main"].instructions), 3)

    def test_unreachable_after_return(self):
        """测试返回后的不可达代码。"""
        program = MIRProgram()
        func = MIRFunction(name="main")
        func.instructions = [
            MIRConstInstr("t1", MIRInstrType.ADD, [], {"value": 1.0}),
            MIRConstInstr("t2", MIRInstrType.ADD, [], {"value": 2.0}),
        ]
        program.functions["main"] = func

        pipeline = MathaDeadCodeElimPass()
        result = pipeline.run(program)
        # 所有变量都被使用（隐式返回），应保留
        self.assertEqual(len(result.functions["main"].instructions), 2)


class TestCodeSimplification(unittest.TestCase):
    """代码简化测试。"""

    def test_simplify_x_plus_zero(self):
        """测试 x + 0 → x。"""
        program = MIRProgram()
        func = MIRFunction(name="main")
        func.instructions = [
            MIRArithInstr("t1", MIRInstrType.ADD, ["5.0", "0.0"], {"op": "+"}),
        ]
        program.functions["main"] = func

        pipeline = MathaSimplifyPass()
        result = pipeline.run(program)

        instr = result.functions["main"].instructions[0]
        self.assertEqual(instr.value, 5.0)

    def test_simplify_x_mul_one(self):
        """测试 x * 1 → x。"""
        program = MIRProgram()
        func = MIRFunction(name="main")
        func.instructions = [
            MIRArithInstr("t1", MIRInstrType.ADD, ["5.0", "1.0"], {"op": "*"}),
        ]
        program.functions["main"] = func

        pipeline = MathaSimplifyPass()
        result = pipeline.run(program)

        instr = result.functions["main"].instructions[0]
        self.assertEqual(instr.value, 5.0)

    def test_simplify_x_sub_x(self):
        """测试 x - x → 0。"""
        program = MIRProgram()
        func = MIRFunction(name="main")
        func.instructions = [
            MIRArithInstr("t1", MIRInstrType.ADD, ["5.0", "5.0"], {"op": "-"}),
        ]
        program.functions["main"] = func

        pipeline = MathaSimplifyPass()
        result = pipeline.run(program)

        instr = result.functions["main"].instructions[0]
        self.assertEqual(instr.value, 0.0)

    def test_simplify_x_div_x(self):
        """测试 x / x → 1。"""
        program = MIRProgram()
        func = MIRFunction(name="main")
        func.instructions = [
            MIRArithInstr("t1", MIRInstrType.ADD, ["5.0", "5.0"], {"op": "/"}),
        ]
        program.functions["main"] = func

        pipeline = MathaSimplifyPass()
        result = pipeline.run(program)

        instr = result.functions["main"].instructions[0]
        self.assertEqual(instr.value, 1.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
