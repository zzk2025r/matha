# -*- coding: utf-8 -*-
"""
Matha 多语言增强系统 — 单元测试

测试覆盖：
  1. multi_lang_codegen.py — C++/Rust/Go/Java 代码生成
  2. multi_lang_verifier.py — 多语言交叉验证
  3. csp_os_thread.py — OS 线程并发模型
  4. type_system_v2.py — 增强类型系统
  5. performance_benchmark.py — 性能基准测试
"""
from __future__ import annotations
import sys
import os
import unittest
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from multi_lang_codegen import (
    CppGenerator, RustGenerator, GoGenerator, JavaGenerator,
    MultiLangCodeGen, SymbolCompat,
    generate_cpp, generate_rust, generate_go, generate_java,
)
from multi_lang_verifier import (
    MultiLangVerifier, MultiLangCodeGenerator,
    CompareResult,
)
from csp_os_thread import (
    Channel, Goroutine, CSPRuntime, ProcessPool,
    go, channel, parallel_map,
)
from type_system_v2 import (
    Type, TypeKind, EnhancedTypeInferencer, SubtypeRegistry,
    RefinementChecker, TypeConstraint, TypeChecker,
)
from performance_benchmark import BenchmarkSuite, MultiLangBenchmark as BenchSuite


# ═══════════════════════════════════════════════════════════════════════════════
#  测试套件 1: 多语言代码生成
# ═══════════════════════════════════════════════════════════════════════════════

class TestMultiLangCodegen(unittest.TestCase):
    """多语言代码生成测试。"""

    def test_generate_cpp(self):
        """生成 C++ 代码。"""
        code = generate_cpp("polynomial", [("double", "x")], "x*x + 3*x - 5")
        self.assertIn("#include <cmath>", code)
        self.assertIn("double polynomial(double x)", code)
        self.assertIn("return x*x + 3*x - 5;", code)
        self.assertIn("int main()", code)

    def test_generate_rust(self):
        """生成 Rust 代码。"""
        code = generate_rust("polynomial", ["x"], "x*x + 3.0*x - 5.0")
        self.assertIn("fn polynomial(x: f64) -> f64", code)
        self.assertIn("println!", code)
        self.assertIn("test_polynomial", code)

    def test_generate_go(self):
        """生成 Go 代码。"""
        code = generate_go("polynomial", ["x"], "math.Pow(x, 2) + 3*x - 5")
        self.assertIn("func polynomial(x float64) float64", code)
        self.assertIn("package main", code)
        self.assertIn("import \"math\"", code)

    def test_generate_java(self):
        """生成 Java 代码。"""
        code = generate_java("polynomial", ["x"], "Math.pow(x, 2) + 3*x - 5")
        self.assertIn("public class PolynomialCompute", code)
        self.assertIn("public static double polynomial(double x)", code)
        self.assertIn("System.out.println", code)

    def test_multi_lang_codegen_all(self):
        """生成所有语言代码。"""
        gen = MultiLangCodeGen()
        results = gen.generate_all("test", [("double", "x")], "x+1")
        self.assertIn("python", results)
        self.assertIn("cpp", results)
        self.assertIn("rust", results)
        self.assertIn("go", results)
        self.assertIn("java", results)
        for lang, result in results.items():
            self.assertIn("code", result.__dict__)
            self.assertTrue(len(result.code) > 0)

    def test_symbol_compat_simplify(self):
        """符号简化测试。"""
        # 链式调用: a >> b → b(a)
        result = SymbolCompat.simplify("f >> x")
        self.assertEqual(result, "f(x)")
        # 属于判断: x >> S → x in S
        result = SymbolCompat.simplify("x >> S")
        self.assertIn("in", result)

    def test_cpp_class_generation(self):
        """生成 C++ 类。"""
        gen = CppGenerator("Calculator")
        methods = [
            {"name": "add", "params": [("double", "a"), ("double", "b")], "return": "double", "expr": "a + b"},
            {"name": "mul", "params": [("double", "a"), ("double", "b")], "return": "double", "expr": "a * b"},
        ]
        code = gen.generate_class("Calculator", methods)
        self.assertIn("class Calculator", code)
        self.assertIn("double add", code)
        self.assertIn("double mul", code)

    def test_rust_trait_generation(self):
        """生成 Rust Trait。"""
        gen = RustGenerator()
        methods = [
            {"name": "compute", "params": [("f64", "x")], "return": "f64"},
        ]
        code = gen.generate_trait("Compute", methods)
        self.assertIn("pub trait Compute", code)
        self.assertIn("fn compute", code)


# ═══════════════════════════════════════════════════════════════════════════════
#  测试套件 2: CSP OS 线程并发
# ═══════════════════════════════════════════════════════════════════════════════

class TestCSPThread(unittest.TestCase):
    """CSP OS 线程并发测试。"""

    def test_channel_send_recv(self):
        """Channel 发送接收。"""
        ch = Channel()
        ch.send(42)
        val = ch.recv()
        self.assertEqual(val, 42)

    def test_channel_stats(self):
        """Channel 统计。"""
        ch = Channel()
        ch.send(1)
        ch.send(2)
        stats = ch.stats()
        self.assertEqual(stats["sent"], 2)
        self.assertEqual(stats["recv"], 0)
        ch.recv()
        stats = ch.stats()
        self.assertEqual(stats["recv"], 1)

    def test_goroutine_start_join(self):
        """Goroutine 启动和等待。"""
        def compute(x):
            time.sleep(0.01)
            return x * x

        gor = Goroutine(compute, (5,))
        gor.start()
        result = gor.join()
        self.assertEqual(result, 25)

    def test_csp_runtime_go(self):
        """CSPRuntime go 启动。"""
        runtime = CSPRuntime()

        def square(x):
            return x * x

        gor1 = runtime.go(square, 3)
        gor2 = runtime.go(square, 5)
        results = runtime.wait_all()
        self.assertEqual(sorted(results), [9, 25])

    def test_process_pool_map(self):
        """ProcessPool map。"""
        pool = ProcessPool(2)

        def compute(x):
            return x * 2

        results = pool.map(compute, [1, 2, 3, 4])
        self.assertEqual(results, [2, 4, 6, 8])

    def test_concurrent_channel_communication(self):
        """并发 channel 通信。"""
        runtime = CSPRuntime()
        ch = runtime.new_channel()

        def producer():
            for i in range(5):
                ch.send(i)
            ch.close()

        def consumer():
            results = []
            for _ in range(5):
                try:
                    results.append(ch.recv(timeout=0.5))
                except TimeoutError:
                    break
            return results

        runtime.go(producer)
        runtime.go(consumer)
        results = runtime.wait_all()
        # 消费者结果应在 results 中
        self.assertTrue(any(isinstance(r, list) for r in results))


# ═══════════════════════════════════════════════════════════════════════════════
#  测试套件 3: 增强类型系统
# ═══════════════════════════════════════════════════════════════════════════════

class TestTypeSystemV2(unittest.TestCase):
    """增强类型系统测试。"""

    def setUp(self):
        self.inferencer = EnhancedTypeInferencer()

    def test_primitive_inference(self):
        """基本类型推断。"""
        self.assertEqual(self.inferencer.infer("42"), Type.INT)
        self.assertEqual(self.inferencer.infer("3.14"), Type.FLOAT)
        self.assertEqual(self.inferencer.infer('"hello"'), Type.STRING)
        self.assertEqual(self.inferencer.infer("true"), Type.BOOL)

    def test_generic_inference(self):
        """泛型类型推断。"""
        t = self.inferencer.infer("[1, 2, 3]")
        self.assertEqual(t.kind, TypeKind.GENERIC)
        self.assertEqual(t.name, "List")

    def test_refinement_type(self):
        """精炼类型推断。"""
        t = self.inferencer.infer("{x: Int | x > 0}")
        self.assertEqual(t.kind, TypeKind.REFINEMENT)
        self.assertEqual(t.predicate, "x > 0")

    def test_dependent_type(self):
        """依赖类型推断。"""
        t = self.inferencer.infer("(n: Nat) -> Vec n")
        self.assertEqual(t.kind, TypeKind.DEPENDENT)

    def test_subtype_check(self):
        """子类型检查。"""
        self.inferencer.add_subtype("Dog", "Animal")
        self.inferencer.add_subtype("Animal", "LivingBeing")
        self.assertTrue(self.inferencer.subtype_registry.is_subtype_of("Dog", "Animal"))
        self.assertTrue(self.inferencer.subtype_registry.is_subtype_of("Dog", "LivingBeing"))
        self.assertFalse(self.inferencer.subtype_registry.is_subtype_of("Animal", "Dog"))

    def test_refinement_check(self):
        """精炼类型检查。"""
        checker = RefinementChecker()
        self.assertTrue(checker.check(5, "x > 0"))
        self.assertFalse(checker.check(-1, "x > 0"))
        self.assertTrue(checker.check("hello", "len(s) > 0"))
        self.assertFalse(checker.check("", "len(s) > 0"))

    def test_type_alias(self):
        """类型别名。"""
        self.inferencer.define_alias("PositiveInt",
                                     Type.refinement("x", "x > 0"))
        t = self.inferencer.infer("PositiveInt")
        self.assertEqual(t.kind, TypeKind.ALIAS)

    def test_enum_type(self):
        """枚举类型。"""
        self.inferencer.define_enum("Color", ["RED", "GREEN", "BLUE"])
        t = self.inferencer.infer("Color")
        self.assertEqual(t.kind, TypeKind.ENUM)
        self.assertEqual(t.name, "Color")

    def test_function_type_inference(self):
        """函数类型推断。"""
        t = self.inferencer.infer("sin(1.5)")
        self.assertEqual(t, Type.FLOAT)

    def test_subtype_hierarchy_chain(self):
        """子类型层次链。"""
        self.inferencer.add_subtype("Dog", "Animal")
        self.inferencer.add_subtype("Animal", "LivingBeing")
        chain = self.inferencer.subtype_registry.get_hierarchy("Dog")
        self.assertEqual(chain, ["Dog", "Animal", "LivingBeing"])


# ═══════════════════════════════════════════════════════════════════════════════
#  测试套件 4: 多语言验证器
# ═══════════════════════════════════════════════════════════════════════════════

class TestMultiLangVerifier(unittest.TestCase):
    """多语言验证器测试。"""

    def setUp(self):
        self.verifier = MultiLangVerifier()

    def test_verify_polynomial(self):
        """验证多项式函数。"""
        verification = self.verifier.verify(
            func_name="polynomial",
            params=["x"],
            expr="x*x + 3*x - 5",
            test_cases=[
                ([2.0], 3.0),
                ([0.0], -5.0),
                ([1.0], -1.0),
            ]
        )
        self.assertEqual(verification.func_name, "polynomial")
        self.assertEqual(len(verification.test_cases), 3)

    def test_code_generation(self):
        """代码生成测试。"""
        codegen = MultiLangCodeGenerator()
        python_code = codegen.gen_python("test", ["x"], "x+1")
        self.assertIn("def test", python_code)
        self.assertIn("return x+1", python_code)

        cpp_code = codegen.gen_cpp("test", ["x"], "x+1")
        self.assertIn("#include", cpp_code)
        self.assertIn("double test", cpp_code)

    def test_benchmark_result(self):
        """基准测试结果。"""
        suite = BenchmarkSuite()
        result = suite.run_benchmark(
            "test_compute",
            lambda: time.sleep(0.001),
            (),
            iterations=10,
            language="matha"
        )
        self.assertEqual(result.test_name, "test_compute")
        self.assertEqual(result.language, "matha")
        self.assertGreater(result.avg_ms, 0)


# ═══════════════════════════════════════════════════════════════════════════════
#  测试套件 5: 性能基准
# ═══════════════════════════════════════════════════════════════════════════════

class TestPerformanceBenchmark(unittest.TestCase):
    """性能基准测试。"""

    def test_sort_benchmark(self):
        """排序基准测试。"""
        suite = BenchmarkSuite()
        import random
        data = [random.random() for _ in range(1000)]
        result = suite.run_benchmark(
            "Sort_1000",
            lambda d: sorted(d),
            (data,),
            iterations=100,
            language="matha"
        )
        self.assertEqual(result.language, "matha")
        self.assertGreater(result.avg_ms, 0)
        self.assertIsNotNone(result.result_value)
        self.assertEqual(len(result.result_value), 1000)

    def test_parallel_benchmark(self):
        """并行计算基准测试。"""
        pool = ProcessPool(2)

        def compute(x):
            return x * 2

        results = pool.map(compute, [1, 2, 3, 4])
        self.assertEqual(results, [2, 4, 6, 8])


# ═══════════════════════════════════════════════════════════════════════════════
#  测试运行入口
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 70)
    print("  Matha 多语言增强系统 — 单元测试")
    print("=" * 70)
    print()
    unittest.main(verbosity=2)
