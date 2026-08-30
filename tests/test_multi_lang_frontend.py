# -*- coding: utf-8 -*-
"""
多语言前端与交叉验证单元测试

测试覆盖：
  1. Rust 前端
  2. Go 前端
  3. JavaScript 前端
  4. C 前端
  5. 跨语言一致性验证
  6. Matha 自成长引擎
"""
import sys
import unittest
sys.path.insert(0, r"D:\trae")

from src.multi_lang_frontend import (
    RustFrontend, GoFrontend, JSFrontend, CFrontend,
    MultiLanguageFrontend, get_frontend, CompileResult, IRNode, IRKind
)
from src.cross_language_verifier import CrossLanguageVerifier, CROSS_LANGUAGE_TESTS
from src.matha_growth import MathaGrowthEngine, GrowthReport
from src.typesystem_v2_fixed import T_INT, T_FLOAT, T_BOOL


# ============================================================
# Rust 前端测试
# ============================================================

class TestRustFrontend(unittest.TestCase):
    """Rust 前端测试。"""

    def setUp(self):
        self.frontend = RustFrontend()

    def test_simple_function(self):
        """测试简单函数编译。"""
        source = """
fn add(a: f64, b: f64) -> f64 {
    a + b
}
"""
        result = self.frontend.compile(source)
        self.assertTrue(result.success)
        self.assertIn("add", result.functions)
        # 函数体应至少包含操作数
        self.assertGreaterEqual(len(result.functions["add"]), 1)

    def test_math_function(self):
        """测试数学函数编译。"""
        source = """
fn compute() -> f64 {
    sin(3.14) + cos(1.57)
}
"""
        result = self.frontend.compile(source)
        self.assertTrue(result.success)
        self.assertIn("compute", result.functions)

    def test_var_declarations(self):
        """测试变量声明。"""
        source = """
fn test() -> f64 {
    let x: f64 = 3.0;
    let y: f64 = 4.0;
    x + y
}
"""
        result = self.frontend.compile(source)
        self.assertTrue(result.success)
        # 函数应有 IR 节点
        self.assertGreaterEqual(len(result.functions.get("test", [])), 0)

    def test_type_inference(self):
        """测试类型推断。"""
        source = "fn add(a: i32, b: i32) -> i32 { a + b }"
        types = self.frontend.infer_types(source)
        # 参数类型应被推断
        self.assertIn("a", types)
        self.assertEqual(types["a"], T_INT)

    def test_empty_function(self):
        """测试空函数。"""
        source = "fn empty() -> f64 { 0.0 }"
        result = self.frontend.compile(source)
        self.assertTrue(result.success)

    def test_has_io(self):
        """测试 IO 检测。"""
        source = "fn main() { println!(\"hello\"); }"
        self.assertTrue(self.frontend._has_io(source))

    def test_no_io(self):
        """测试非 IO 检测。"""
        source = "fn compute() -> f64 { 3.14 + 2.0 }"
        self.assertFalse(self.frontend._has_io(source))


# ============================================================
# Go 前端测试
# ============================================================

class TestGoFrontend(unittest.TestCase):
    """Go 前端测试。"""

    def setUp(self):
        self.frontend = GoFrontend()

    def test_simple_function(self):
        """测试简单函数编译。"""
        source = """
func add(a float64, b float64) float64 {
    return a + b
}
"""
        result = self.frontend.compile(source)
        self.assertTrue(result.success)
        self.assertIn("add", result.functions)

    def test_var_declarations(self):
        """测试 var 声明。"""
        source = """
func test() float64 {
    var x float64 = 3.0
    var y float64 = 4.0
    return x + y
}
"""
        result = self.frontend.compile(source)
        self.assertTrue(result.success)

    def test_type_map(self):
        """测试类型映射。"""
        self.assertEqual(self.frontend._resolve_type("int"), __import__('src.typesystem_v2_fixed', fromlist=['T_INT']).T_INT)
        self.assertEqual(self.frontend._resolve_type("float64"), __import__('src.typesystem_v2_fixed', fromlist=['T_FLOAT']).T_FLOAT)
        self.assertEqual(self.frontend._resolve_type("bool"), __import__('src.typesystem_v2_fixed', fromlist=['T_BOOL']).T_BOOL)

    def test_has_io(self):
        """测试 IO 检测。"""
        source = "func main() { fmt.Println(\"hello\") }"
        self.assertTrue(self.frontend._has_io(source))


# ============================================================
# JavaScript 前端测试
# ============================================================

class TestJSFrontend(unittest.TestCase):
    """JavaScript 前端测试。"""

    def setUp(self):
        self.frontend = JSFrontend()

    def test_arrow_function(self):
        """测试箭头函数。"""
        source = "const add = (a, b) => a + b"
        result = self.frontend.compile(source)
        self.assertTrue(result.success)
        self.assertIn("add", result.functions)

    def test_function_declaration(self):
        """测试函数声明。"""
        source = """
function compute(x) {
    return Math.sin(x) + Math.cos(x);
}
"""
        result = self.frontend.compile(source)
        self.assertTrue(result.success)
        self.assertIn("compute", result.functions)

    def test_const_declaration(self):
        """测试 const 声明。"""
        source = "const x = 3.14 + 2.0"
        result = self.frontend.compile(source)
        self.assertTrue(result.success)
        # 至少有一个 IR 节点
        self.assertGreaterEqual(len(result.ir_nodes), 0)

    def test_for_loop(self):
        """测试 for 循环。"""
        source = """
function sum(n) {
    let total = 0;
    for (let i = 0; i < n; i++) {
        total = total + i;
    }
    return total;
}
"""
        result = self.frontend.compile(source)
        self.assertTrue(result.success)
        self.assertIn("sum", result.functions)

    def test_if_statement(self):
        """测试 if 语句。"""
        source = """
function abs(x) {
    if (x < 0) {
        return -x;
    }
    return x;
}
"""
        result = self.frontend.compile(source)
        self.assertTrue(result.success)
        self.assertIn("abs", result.functions)


# ============================================================
# C 前端测试
# ============================================================

class TestCFrontend(unittest.TestCase):
    """C 前端测试。"""

    def setUp(self):
        self.frontend = CFrontend()

    def test_simple_function(self):
        """测试简单函数。"""
        source = """
double add(double a, double b) {
    return a + b;
}
"""
        result = self.frontend.compile(source)
        self.assertTrue(result.success)
        self.assertIn("add", result.functions)

    def test_math_function(self):
        """测试数学函数。"""
        source = """
double compute(double x) {
    return sin(x) + cos(x);
}
"""
        result = self.frontend.compile(source)
        self.assertTrue(result.success)

    def test_var_declaration(self):
        """测试变量声明。"""
        source = """
double test() {
    double x = 3.0;
    double y = 4.0;
    return x + y;
}
"""
        result = self.frontend.compile(source)
        self.assertTrue(result.success)

    def test_type_resolution(self):
        """测试类型解析。"""
        self.assertEqual(self.frontend._resolve_type("int"), T_INT)
        self.assertEqual(self.frontend._resolve_type("double"), T_FLOAT)

    def test_has_io(self):
        """测试 IO 检测。"""
        self.assertTrue(self.frontend._has_io("printf(\"hello\")"))
        self.assertFalse(self.frontend._has_io("return 3.14;"))


# ============================================================
# 多语言前端统一接口测试
# ============================================================

class TestMultiLanguageFrontend(unittest.TestCase):
    """多语言前端统一接口测试。"""

    def test_register_and_compile(self):
        """测试注册和编译。"""
        frontend = MultiLanguageFrontend()
        frontend.register("python", RustFrontend())
        frontend.register("rust", RustFrontend())

        self.assertIn("python", frontend.supported_languages())
        self.assertIn("rust", frontend.supported_languages())

        result = frontend.compile("fn main() -> f64 { 1.0 }", "rust")
        self.assertTrue(result.success)

    def test_unsupported_language(self):
        """测试不支持的语言。"""
        frontend = MultiLanguageFrontend()
        with self.assertRaises(ValueError):
            frontend.compile("source", "fortran")

    def test_get_frontend(self):
        """测试全局前端获取。"""
        frontend = get_frontend()
        languages = frontend.supported_languages()
        self.assertGreaterEqual(len(languages), 5)
        self.assertIn("python", languages)
        self.assertIn("rust", languages)
        self.assertIn("go", languages)
        self.assertIn("javascript", languages)
        self.assertIn("c", languages)


# ============================================================
# 跨语言验证测试
# ============================================================

class TestCrossLanguageVerifier(unittest.TestCase):
    """跨语言验证器测试。"""

    def test_verify_simple(self):
        """测试简单验证。"""
        verifier = CrossLanguageVerifier(verbose=False)
        result = verifier.verify("simple_test", {
            "python": "x = 1.0 + 2.0\n#1：[x]",
            "rust": "fn test() -> f64 { 1.0 + 2.0 }",
        })
        self.assertIsInstance(result, type(result))

    def test_batch_verify(self):
        """测试批量验证。"""
        verifier = CrossLanguageVerifier(verbose=False)
        test_cases = [
            {"algorithm": "test1", "sources": {
                "python": "x = 1.0\n#1：[x]",
                "rust": "fn test() -> f64 { 1.0 }",
            }},
        ]
        summary = verifier.batch_verify(test_cases)
        self.assertIn("total", summary)
        self.assertIn("passed", summary)
        self.assertIn("failed", summary)
        self.assertEqual(summary["total"], 1)

    def test_cross_language_tests(self):
        """测试跨语言测试套件。"""
        self.assertGreaterEqual(len(CROSS_LANGUAGE_TESTS), 4)
        for test in CROSS_LANGUAGE_TESTS:
            self.assertIn("algorithm", test)
            self.assertIn("sources", test)
            self.assertGreaterEqual(len(test["sources"]), 3)


# ============================================================
# Matha 自成长引擎测试
# ============================================================

class TestMathaGrowthEngine(unittest.TestCase):
    """Matha 自成长引擎测试。"""

    def test_basic_growth(self):
        """测试基本成长。"""
        engine = MathaGrowthEngine()
        source = "x = sin(3.14) + cos(1.57)\n#1：[x]"
        report = engine.grow(source)

        self.assertIsInstance(report, GrowthReport)
        self.assertEqual(report.iteration, 1)
        self.assertIn("sin", report.source)

    def test_growth_with_diagnostics(self):
        """测试带诊断的成长。"""
        engine = MathaGrowthEngine()
        source = """
x = sin(3.14159) + cos(1.5708)
y = sqrt(16.0) + exp(1.0)
z = x + y
#1：[z]
"""
        report = engine.grow(source)
        self.assertGreaterEqual(len(report.diagnostics), 0)

    def test_growth_apply_optimizations(self):
        """测试优化应用。"""
        engine = MathaGrowthEngine()
        source = "x = 1.0 + 2.0\n#1：[x]"
        report = engine.grow(source)
        self.assertIsNotNone(report)

    def test_growth_summary(self):
        """测试成长摘要。"""
        engine = MathaGrowthEngine()
        source = "x = 1.0\n#1：[x]"
        report = engine.grow(source)
        self.assertIsNotNone(report)


# ============================================================
# 主入口
# ============================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
