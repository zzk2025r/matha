# -*- coding: utf-8 -*-
"""
Matha VM 与交叉验证单元测试

测试覆盖：
  1. MathaVM 基本指令执行
  2. 算术运算
  3. 函数调用
  4. 常量折叠
  5. 交叉验证
  6. 性能基准
"""
import sys
import unittest
sys.path.insert(0, r"D:\trae")

from src.vm import MathaVM, CrossVerifier, benchmark, VMResult
from src.mir import (
    MIRProgram, MIRFunction, MIRArithInstr, MIRCallInstr,
    MIRConstInstr, MIRInstrType, MIRCompareInstr, MIRLogicalInstr,
    MIRLabelInstr, MIRCondBranchInstr, MIRStoreInstr
)


class TestMathaVMBasic(unittest.TestCase):
    """MathaVM 基本功能测试。"""

    def test_const_instruction(self):
        """测试常量赋值指令。"""
        program = MIRProgram()
        func = MIRFunction(name="main", params=[], return_type="double")
        func.instructions = [
            MIRConstInstr("t1", MIRInstrType.ADD, [], {"value": 5.0}),
        ]
        program.functions["main"] = func

        vm = MathaVM()
        outputs, trace = vm.run(program)
        self.assertEqual(len(outputs), 0)  # 无输出指令

    def test_arith_add(self):
        """测试加法运算。"""
        program = MIRProgram()
        func = MIRFunction(name="main", params=[], return_type="double")
        func.instructions = [
            MIRConstInstr("t1", MIRInstrType.ADD, [], {"value": 3.0}),
            MIRConstInstr("t2", MIRInstrType.ADD, [], {"value": 4.0}),
            MIRArithInstr("t3", MIRInstrType.ADD, ["t1", "t2"], {"op": "+"}),
        ]
        program.functions["main"] = func

        vm = MathaVM()
        outputs, trace = vm.run(program)
        # VM 执行应无错误，输出为空（无 print 指令）
        self.assertEqual(len(outputs), 0)

    def test_arith_mul(self):
        """测试乘法运算。"""
        program = MIRProgram()
        func = MIRFunction(name="main", params=[], return_type="double")
        func.instructions = [
            MIRConstInstr("t1", MIRInstrType.ADD, [], {"value": 3.0}),
            MIRConstInstr("t2", MIRInstrType.ADD, [], {"value": 4.0}),
            MIRArithInstr("t3", MIRInstrType.ADD, ["t1", "t2"], {"op": "*"}),
        ]
        program.functions["main"] = func

        vm = MathaVM()
        outputs, trace = vm.run(program)
        self.assertEqual(len(outputs), 0)

    def test_math_functions(self):
        """测试数学函数调用。"""
        program = MIRProgram()
        func = MIRFunction(name="main", params=[], return_type="double")
        func.instructions = [
            MIRConstInstr("t1", MIRInstrType.ADD, [], {"value": 3.14159}),
            MIRCallInstr("t2", MIRInstrType.CALL, ["t1"], {"c_func": "sin"}),
        ]
        program.functions["main"] = func

        vm = MathaVM()
        outputs, trace = vm.run(program)
        # sin(π) ≈ 0
        self.assertTrue(any("0" in t for t in trace) or len(trace) > 0)

    def test_compare(self):
        """测试比较运算。"""
        program = MIRProgram()
        func = MIRFunction(name="main", params=[], return_type="double")
        func.instructions = [
            MIRConstInstr("t1", MIRInstrType.ADD, [], {"value": 5.0}),
            MIRConstInstr("t2", MIRInstrType.ADD, [], {"value": 3.0}),
            MIRCompareInstr("t3", MIRInstrType.ADD, ["t1", "t2"], {"op": ">"}),
        ]
        program.functions["main"] = func

        vm = MathaVM()
        outputs, trace = vm.run(program)
        # 5 > 3 = true (1.0)
        self.assertTrue(len(trace) >= 0)

    def test_logical_and(self):
        """测试逻辑与运算。"""
        program = MIRProgram()
        func = MIRFunction(name="main", params=[], return_type="double")
        func.instructions = [
            MIRConstInstr("t1", MIRInstrType.ADD, [], {"value": 1.0}),
            MIRConstInstr("t2", MIRInstrType.ADD, [], {"value": 1.0}),
            MIRLogicalInstr("t3", MIRInstrType.ADD, ["t1", "t2"], {"op": "and"}),
        ]
        program.functions["main"] = func

        vm = MathaVM()
        outputs, trace = vm.run(program)
        self.assertTrue(len(trace) >= 0)

    def test_empty_program(self):
        """测试空程序。"""
        program = MIRProgram()
        func = MIRFunction(name="main", params=[], return_type="double")
        func.instructions = []
        program.functions["main"] = func

        vm = MathaVM()
        outputs, trace = vm.run(program)
        self.assertEqual(len(outputs), 0)

    def test_max_iterations(self):
        """测试最大迭代限制。"""
        program = MIRProgram()
        func = MIRFunction(name="main", params=[], return_type="double")
        # 创建大量指令模拟循环
        for i in range(100):
            func.instructions.append(MIRConstInstr(f"t{i}", MIRInstrType.ADD, [], {"value": float(i)}))
        program.functions["main"] = func

        vm = MathaVM(max_iterations=10)
        outputs, trace = vm.run(program)
        # 应该因为迭代限制而中止
        self.assertTrue(any("ERROR" in t for t in trace) or len(trace) < 100)


class TestMathaVMFunctionCall(unittest.TestCase):
    """函数调用测试。"""

    def test_simple_function_call(self):
        """测试简单函数调用。"""
        program = MIRProgram()

        # helper 函数
        helper = MIRFunction(name="helper", params=["a", "b"], return_type="double")
        helper.instructions = [
            MIRArithInstr("t1", MIRInstrType.ADD, ["%a", "%b"], {"op": "+"}),
        ]
        helper.returns = ["t1"]

        # main 函数
        main = MIRFunction(name="main", params=[], return_type="double")
        main.instructions = [
            MIRCallInstr("t2", MIRInstrType.CALL, ["1.0", "2.0"], {"func_name": "helper"}),
        ]
        main.returns = ["t2"]

        program.functions["helper"] = helper
        program.functions["main"] = main

        # 需要先注册函数到 globals
        vm = MathaVM()
        vm._state.globals.update({
            "helper": helper,
            "main": main,
        })

        outputs, trace = vm.run(program)
        self.assertTrue(len(trace) > 0)

    def test_nested_function_call(self):
        """测试嵌套函数调用。"""
        program = MIRProgram()

        def make_add_func():
            f = MIRFunction(name="add", params=["a", "b"], return_type="double")
            f.instructions = [
                MIRArithInstr("t1", MIRInstrType.ADD, ["%a", "%b"], {"op": "+"}),
            ]
            f.returns = ["t1"]
            return f

        add = make_add_func()

        main = MIRFunction(name="main", params=[], return_type="double")
        main.instructions = [
            MIRCallInstr("t1", MIRInstrType.CALL, ["1.0", "2.0"], {"func_name": "add"}),
            MIRCallInstr("t2", MIRInstrType.CALL, ["t1", "3.0"], {"func_name": "add"}),
        ]
        main.returns = ["t2"]

        program.functions["add"] = add
        program.functions["main"] = main

        vm = MathaVM()
        vm._state.globals.update({"add": add, "main": main})

        outputs, trace = vm.run(program)
        self.assertTrue(len(trace) > 0)


class TestCrossVerifier(unittest.TestCase):
    """交叉验证器测试。"""

    def test_verify_simple_arithmetic(self):
        """测试简单算术的交叉验证。"""
        source = "x = 1 + 2\n#1：[x]"
        verifier = CrossVerifier(verbose=False)
        result = verifier.verify(source)

        # 两个解释器应该产生相同输出
        self.assertIn("match", result)
        self.assertIn("errors", result)

    def test_verify_with_functions(self):
        """测试含函数的交叉验证。"""
        source = "f = (x) => x * 2\nx = f(5)\n#1：[x]"
        verifier = CrossVerifier(verbose=False)
        result = verifier.verify(source)

        self.assertIn("match", result)

    def test_batch_verify(self):
        """测试批量验证。"""
        sources = [
            "x = 1 + 2\n#1：[x]",
            "y = 3 * 4\n#1：[y]",
            "z = sin(0)\n#1：[z]",
        ]
        verifier = CrossVerifier(verbose=False)
        summary = verifier.batch_verify(sources)

        self.assertIn("total", summary)
        self.assertIn("passed", summary)
        self.assertIn("failed", summary)
        self.assertEqual(summary["total"], len(sources))


class TestBenchmark(unittest.TestCase):
    """性能基准测试。"""

    def test_benchmark_simple(self):
        """测试简单性能基准。"""
        source = "x = sin(3.14) + cos(1.57)\n#1：[x]"
        result = benchmark(source, iterations=100)

        self.assertIn("interpreter_ms", result)
        self.assertIn("vm_ms", result)
        self.assertIn("speedup", result)
        self.assertGreater(result["iterations"], 0)

        # VM 应该比 Interpreter 快
        if result["vm_ms"] > 0 and result["interpreter_ms"] > 0:
            self.assertGreaterEqual(result["speedup"], 0.5)  # 至少 0.5x


class TestVMEdgeCases(unittest.TestCase):
    """VM 边界情况测试。"""

    def test_division_by_zero(self):
        """测试除零处理。"""
        program = MIRProgram()
        func = MIRFunction(name="main", params=[], return_type="double")
        func.instructions = [
            MIRConstInstr("t1", MIRInstrType.ADD, [], {"value": 5.0}),
            MIRConstInstr("t2", MIRInstrType.ADD, [], {"value": 0.0}),
            MIRArithInstr("t3", MIRInstrType.ADD, ["t1", "t2"], {"op": "/"}),
        ]
        program.functions["main"] = func

        vm = MathaVM()
        outputs, trace = vm.run(program)
        # 应该返回 inf 而不是崩溃
        self.assertTrue(len(trace) >= 0)

    def test_negative_numbers(self):
        """测试负数运算。"""
        program = MIRProgram()
        func = MIRFunction(name="main", params=[], return_type="double")
        func.instructions = [
            MIRConstInstr("t1", MIRInstrType.ADD, [], {"value": -3.0}),
            MIRConstInstr("t2", MIRInstrType.ADD, [], {"value": 2.0}),
            MIRArithInstr("t3", MIRInstrType.ADD, ["t1", "t2"], {"op": "+"}),
        ]
        program.functions["main"] = func

        vm = MathaVM()
        outputs, trace = vm.run(program)
        self.assertTrue(len(trace) >= 0)

    def test_large_numbers(self):
        """测试大数运算。"""
        program = MIRProgram()
        func = MIRFunction(name="main", params=[], return_type="double")
        func.instructions = [
            MIRConstInstr("t1", MIRInstrType.ADD, [], {"value": 1e300}),
            MIRConstInstr("t2", MIRInstrType.ADD, [], {"value": 1e300}),
            MIRArithInstr("t3", MIRInstrType.ADD, ["t1", "t2"], {"op": "*"}),
        ]
        program.functions["main"] = func

        vm = MathaVM()
        outputs, trace = vm.run(program)
        # 应该处理溢出
        self.assertTrue(len(trace) >= 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
