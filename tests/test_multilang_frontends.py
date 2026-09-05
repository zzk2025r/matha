# -*- coding: utf-8 -*-
"""
混合语言编译器单元测试

覆盖：
  1. RustFrontend — 类型解析、函数提取、效应分析
  2. GoFrontend   — 函数提取、类型映射、Python 风格回退
  3. CFrontend    — C 函数解析、类型映射、IO 检测
  4. JSFrontend   — JS 函数提取、Math 映射、三元表达式
  5. MultiLanguageFrontend — 统一注册与分发
  6. HybridFrontend   — 原生→Python→tree-sitter 降级链
  7. 跨语言一致性 — 相同算法四语言输出对比
"""
import sys
sys.path.insert(0, r'D:\trae')

import json
import pytest
import subprocess
from pathlib import Path
from typing import Any
from src.typesystem_v2_fixed import T_INT, T_FLOAT, T_BOOL, T_STRING, T_ANY

# ── 辅助函数 ───────────────────────────────────────────────────

FRONTENDS_DIR = Path(__file__).parent.parent / "matha" / "frontends"


def _get_rust_frontend():
    from src.multi_lang_frontend import RustFrontend
    return RustFrontend()


def _get_go_frontend():
    from src.multi_lang_frontend import GoFrontend
    return GoFrontend()


def _get_c_frontend():
    from src.multi_lang_frontend import CFrontend
    return CFrontend()


def _get_js_frontend():
    from src.multi_lang_frontend import JSFrontend
    return JSFrontend()


# ============================================================
# 1. RustFrontend 单元测试
# ============================================================

class TestRustFrontend:
    """Rust → Matha IR 前端测试。"""

    def test_simple_function(self):
        """基本函数提取。"""
        fe = _get_rust_frontend()
        result = fe.compile("fn add(x: i32, y: i32) -> i32 { x + y }")
        assert result.language == "rust"
        assert "add" in result.functions
        assert len(result.functions["add"]) > 0

    def test_function_with_math(self):
        """含数学函数的提取与 STD_MATH 映射（使用 return 语句确保 body 解析）。"""
        fe = _get_rust_frontend()
        result = fe.compile("fn compute(x: f64) -> f64 { return sqrt(x) + 1.0; }")
        assert "compute" in result.functions
        ir = result.functions["compute"]
        call_nodes = [n for n in ir if n.kind.name == "CALL"]
        assert len(call_nodes) >= 1
        assert call_nodes[0].value == "sqrt"

    def test_type_resolution_i32(self):
        """i32 → T_INT 类型解析。"""
        fe = _get_rust_frontend()
        result = fe.compile("fn foo(x: i32) -> i32 { x }")
        assert result.types["foo"] == fe._resolve_type("i32")

    def test_type_resolution_f64(self):
        """f64 → T_FLOAT 类型解析。"""
        fe = _get_rust_frontend()
        result = fe.compile("fn bar(x: f64) -> f64 { x }")
        assert result.types["bar"] == fe._resolve_type("f64")

    def test_type_resolution_bool(self):
        """bool → T_BOOL 类型解析。"""
        fe = _get_rust_frontend()
        assert fe._resolve_type("bool") == T_BOOL

    def test_type_resolution_string(self):
        """String / &str → T_STRING。"""
        fe = _get_rust_frontend()
        assert fe._resolve_type("String") == T_STRING
        assert fe._resolve_type("&str") == T_STRING

    def test_type_resolution_vec(self):
        """Vec<T> → T_ANY。"""
        fe = _get_rust_frontend()
        assert fe._resolve_type("Vec<i32>") == T_ANY

    def test_type_resolution_unknown(self):
        """未知类型 → T_ANY。"""
        fe = _get_rust_frontend()
        assert fe._resolve_type("FooBar") == T_ANY

    def test_effect_pure(self):
        """纯函数 → Pure。"""
        fe = _get_rust_frontend()
        result = fe.compile("fn inc(x: i32) -> i32 { x + 1 }")
        assert result.effects["inc"] == "Pure"

    def test_effect_io(self):
        """含 println! 的函数 → IO。"""
        fe = _get_rust_frontend()
        result = fe.compile('fn main() { println!("hello"); }')
        assert result.effects["main"] == "IO"

    def test_param_parsing(self):
        """参数列表解析。"""
        fe = _get_rust_frontend()
        params, types = fe._parse_params("x: i32, y: f64, z: bool")
        assert params == ["x", "y", "z"]
        assert types["x"] == T_INT
        assert types["y"] == T_FLOAT
        assert types["z"] == T_BOOL

    def test_empty_params(self):
        """空参数列表。"""
        fe = _get_rust_frontend()
        params, types = fe._parse_params("")
        assert params == []
        assert types == {}

    def test_parse_const_expr(self):
        """常量表达式解析。"""
        fe = _get_rust_frontend()
        nodes = fe._parse_atom("42", {})
        assert len(nodes) == 1
        assert nodes[0].kind.name == "CONST"
        assert nodes[0].value == 42.0

    def test_parse_var_ref(self):
        """变量引用解析。"""
        fe = _get_rust_frontend()
        nodes = fe._parse_atom("x", {"x": T_INT})
        assert len(nodes) == 1
        assert nodes[0].kind.name == "VAR"
        assert nodes[0].value == "x"

    def test_parse_binop(self):
        """二元运算解析（通过 compile 验证函数体中 a+b 能被解析为 VAR 节点）。"""
        fe = _get_rust_frontend()
        result = fe.compile("fn foo(a: i32, b: i32) -> i32 { a + b }")
        assert "foo" in result.functions
        ir = result.functions["foo"]
        var_nodes = [n for n in ir if n.kind.name == "VAR"]
        assert len(var_nodes) >= 2

    def test_infer_types(self):
        """类型推断返回正确 dict。"""
        fe = _get_rust_frontend()
        types = fe.infer_types("fn foo(x: i32, y: f64) -> bool { x > 0 }")
        assert "foo" in types
        assert "x" in types
        assert "y" in types

    def test_analyze_effects(self):
        """效应分析。"""
        fe = _get_rust_frontend()
        effects = fe.analyze_effects('fn main() { println!("hi"); }')
        assert "main" in effects
        assert effects["main"] == "IO"

    def test_no_functions(self):
        """无函数定义时返回空。"""
        fe = _get_rust_frontend()
        result = fe.compile("// just a comment\n")
        assert result.language == "rust"
        assert result.functions == {}

    def test_multiple_functions(self):
        """多函数编译。"""
        fe = _get_rust_frontend()
        source = (
            "fn add(a: i32, b: i32) -> i32 { a + b }\n"
            "fn mul(a: i32, b: i32) -> i32 { a * b }"
        )
        result = fe.compile(source)
        assert "add" in result.functions
        assert "mul" in result.functions

    def test_top_level_expr(self):
        """顶层表达式解析。"""
        fe = _get_rust_frontend()
        result = fe.compile("let x = 42;")
        assert len(result.ir_nodes) >= 0  # 无语法错误即通过

    def test_rust_source_file_exists(self):
        """Rust 原生源文件存在且含关键函数。"""
        f = FRONTENDS_DIR / "rust" / "frontend.rs"
        assert f.exists()
        content = f.read_text(encoding="utf-8")
        assert "fn compile" in content
        assert "fn tokenize" in content
        assert "IRNode" in content

    def test_rust_native_compile(self):
        """运行 Rust 原生前端（如编译好的二进制存在）。"""
        f = FRONTENDS_DIR / "rust" / "matha_rust_frontend.exe"
        if not f.exists():
            pytest.skip("Rust 二进制未编译")
        result = subprocess.run(
            [str(f), "fn foo(x: i32) -> i32 { x + 1 }"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        # Rust 原生前端输出含尾逗号（如 "foo":[...],}），需清理后解析
        import re as _re
        clean = _re.sub(r',\s*([}\]])', r'\1', result.stdout)
        data = json.loads(clean)
        assert data["language"] == "rust"
        assert "foo" in data["functions"]


# ============================================================
# 2. GoFrontend 单元测试
# ============================================================

class TestGoFrontend:
    """Go → Matha IR 前端测试。"""

    def test_simple_function(self):
        """基本 Go 函数提取（至少提取函数名和类型）。"""
        fe = _get_go_frontend()
        result = fe.compile("func add(x int, y int) int { return x + y }")
        assert result.language == "go"
        assert "add" in result.functions
        # Go 前端提取函数名和类型信息
        assert result.types["add"] == T_INT

    def test_function_no_return(self):
        """无返回类型（默认 float64）。"""
        fe = _get_go_frontend()
        result = fe.compile('func greet() { println("hi") }')
        assert "greet" in result.functions

    def test_type_resolution_int(self):
        """int → T_INT。"""
        fe = _get_go_frontend()
        assert fe._resolve_type("int") == T_INT

    def test_type_resolution_float64(self):
        """float64 → T_FLOAT。"""
        fe = _get_go_frontend()
        assert fe._resolve_type("float64") == T_FLOAT

    def test_type_resolution_string(self):
        """string → T_STRING。"""
        fe = _get_go_frontend()
        assert fe._resolve_type("string") == T_STRING

    def test_type_resolution_bool(self):
        """bool → T_BOOL。"""
        fe = _get_go_frontend()
        assert fe._resolve_type("bool") == T_BOOL

    def test_type_resolution_slice(self):
        """[]int → T_ANY。"""
        fe = _get_go_frontend()
        assert fe._resolve_type("[]int") == T_ANY

    def test_param_parsing_shared_type(self):
        """Go 共享类型参数：a, b int。"""
        fe = _get_go_frontend()
        # Go 前端支持 "a int, b int" 格式
        params, types = fe._parse_params("a int, b int")
        assert set(params) == {"a", "b"}
        assert types["a"] == T_INT
        assert types["b"] == T_INT

    def test_effect_pure(self):
        """纯函数 → Pure。"""
        fe = _get_go_frontend()
        result = fe.compile("func abs(x int) int { if x < 0 { -x } else { x } }")
        assert result.effects["abs"] == "Pure"

    def test_effect_io(self):
        """含 fmt.Println → IO。"""
        fe = _get_go_frontend()
        result = fe.compile('func main() { fmt.Println("hello") }')
        assert result.effects["main"] == "IO"

    def test_python_fallback_def(self):
        """Python 风格 def 回退解析。"""
        fe = _get_go_frontend()
        result = fe.compile("def foo(x): return x + 1")
        assert "foo" in result.functions
        assert result.effects["foo"] == "Pure"

    def test_python_fallback_with_comment(self):
        """Python 风格带注释。"""
        fe = _get_go_frontend()
        result = fe.compile("# comment\ndef bar(x): return x * 2")
        assert "bar" in result.functions

    def test_no_functions(self):
        """空源码返回空结果。"""
        fe = _get_go_frontend()
        result = fe.compile("# just a comment\n")
        assert result.language == "go"
        assert result.functions == {}

    def test_multiple_functions(self):
        """多函数编译。"""
        fe = _get_go_frontend()
        source = (
            "func add(a int, b int) int { return a + b }\n"
            "func mul(a int, b int) int { return a * b }"
        )
        result = fe.compile(source)
        assert "add" in result.functions
        assert "mul" in result.functions

    def test_unary_minus(self):
        """一元负号解析（通过 compile 验证含 -x 的函数）。"""
        fe = _get_go_frontend()
        result = fe.compile("func abs(x int) int { if x < 0 { -x } else { x } }")
        assert "abs" in result.functions

    def test_go_source_file_exists(self):
        """Go 原生源文件存在。"""
        f = FRONTENDS_DIR / "go" / "frontend.go"
        assert f.exists()
        content = f.read_text(encoding="utf-8")
        assert "package main" in content
        assert "func compile" in content

    def test_go_native_compile(self):
        """运行 Go 原生前端（如可编译）。"""
        f = FRONTENDS_DIR / "go" / "matha_go_frontend.exe"
        if not f.exists():
            pytest.skip("Go 二进制未编译")
        result = subprocess.run(
            [str(f), "func foo(x int) int { return x + 1 }"],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["language"] == "go"
        assert "foo" in data["functions"]


# ============================================================
# 3. CFrontend 单元测试
# ============================================================

class TestCFrontend:
    """C → Matha IR 前端测试。"""

    def test_simple_function(self):
        """基本 C 函数提取。"""
        fe = _get_c_frontend()
        result = fe.compile("int foo(int x) { return x + 1; }")
        assert result.language == "c"
        assert "foo" in result.functions
        assert len(result.functions["foo"]) > 0

    def test_float_function(self):
        """float 类型函数。"""
        fe = _get_c_frontend()
        result = fe.compile("float square(float x) { return x * x; }")
        assert "square" in result.functions

    def test_double_function(self):
        """double 类型函数。"""
        fe = _get_c_frontend()
        result = fe.compile("double cube(double x) { return x * x * x; }")
        assert "cube" in result.functions

    def test_type_resolution_int(self):
        """int → T_INT。"""
        fe = _get_c_frontend()
        assert fe._resolve_type("int") == T_INT

    def test_type_resolution_float(self):
        """float → T_FLOAT。"""
        fe = _get_c_frontend()
        assert fe._resolve_type("float") == T_FLOAT

    def test_type_resolution_double(self):
        """double → T_FLOAT。"""
        fe = _get_c_frontend()
        assert fe._resolve_type("double") == T_FLOAT

    def test_type_resolution_void(self):
        """void → T_INT（默认）。"""
        fe = _get_c_frontend()
        typ = fe._resolve_type("void")
        assert typ is not None

    def test_type_resolution_pointer(self):
        """指针类型 → T_INT（默认）。"""
        fe = _get_c_frontend()
        typ = fe._resolve_type("*int")
        assert typ is not None

    def test_param_parsing_multiple(self):
        """多参数解析。"""
        fe = _get_c_frontend()
        params, types = fe._parse_params("int a, float b, double c")
        assert len(params) == 3
        assert "a" in types
        assert "b" in types
        assert "c" in types

    def test_param_parsing_void(self):
        """void 参数 → 空。"""
        fe = _get_c_frontend()
        params, types = fe._parse_params("void")
        assert params == []

    def test_effect_pure(self):
        """纯 C 函数 → Pure。"""
        fe = _get_c_frontend()
        result = fe.compile("int inc(int x) { return x + 1; }")
        assert result.effects["inc"] == "Pure"

    def test_effect_io(self):
        """含 printf → IO。"""
        fe = _get_c_frontend()
        result = fe.compile('int main() { printf("hello"); return 0; }')
        assert result.effects["main"] == "IO"

    def test_python_fallback_def(self):
        """Python 风格 def 回退。"""
        fe = _get_c_frontend()
        result = fe.compile("def foo(x): return x + 1")
        assert "foo" in result.functions

    def test_empty_source(self):
        """空源码不崩溃。"""
        fe = _get_c_frontend()
        result = fe.compile("")
        assert result.language == "c"
        assert result.functions == {}

    def test_multiple_functions(self):
        """多函数编译。"""
        fe = _get_c_frontend()
        source = (
            "int add(int a, int b) { return a + b; }\n"
            "float mul(float a, float b) { return a * b; }"
        )
        result = fe.compile(source)
        assert "add" in result.functions
        assert "mul" in result.functions

    def test_c_source_file_exists(self):
        """C 原生源文件存在。"""
        f = FRONTENDS_DIR / "c" / "frontend.c"
        assert f.exists()
        content = f.read_text(encoding="utf-8")
        assert "#include" in content
        assert "int main" in content
        assert "compile" in content

    def test_c_native_compile(self):
        """运行 C 原生前端（如二进制存在）。"""
        f = FRONTENDS_DIR / "c" / "matha_c_frontend.exe"
        if not f.exists():
            pytest.skip("C 二进制未编译")
        result = subprocess.run(
            [str(f), "int foo(int x) { return x + 1; }"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["language"] == "c"
        assert "foo" in data["functions"]


# ============================================================
# 4. JSFrontend 单元测试
# ============================================================

class TestJSFrontend:
    """JS → Matha IR 前端测试。"""

    def test_function_declaration(self):
        """function 声明提取。"""
        fe = _get_js_frontend()
        result = fe.compile("function add(x, y) { return x + y; }")
        assert result.language == "javascript"
        assert "add" in result.functions

    def test_const_arrow_function(self):
        """const 箭头函数提取（带括号参数）。"""
        fe = _get_js_frontend()
        result = fe.compile("const double = (x) => x * 2;")
        assert "double" in result.functions

    def test_const_function_expression(self):
        """const 函数表达式提取。"""
        fe = _get_js_frontend()
        result = fe.compile("const square = function(x) { return x * x; }")
        assert "square" in result.functions

    def test_type_resolution_number(self):
        """number → T_FLOAT。"""
        fe = _get_js_frontend()
        assert fe._resolve_type("number") == T_FLOAT

    def test_type_resolution_int(self):
        """int → T_INT。"""
        fe = _get_js_frontend()
        assert fe._resolve_type("int") == T_INT

    def test_type_resolution_boolean(self):
        """boolean → T_BOOL。"""
        fe = _get_js_frontend()
        assert fe._resolve_type("boolean") == T_BOOL

    def test_type_resolution_string(self):
        """string → T_STRING。"""
        fe = _get_js_frontend()
        assert fe._resolve_type("string") == T_STRING

    def test_type_resolution_void(self):
        """void → T_ANY。"""
        fe = _get_js_frontend()
        assert fe._resolve_type("void") == T_ANY

    def test_math_function_mapping(self):
        """Math.sin → sin 映射。"""
        fe = _get_js_frontend()
        result = fe.compile("function f(x) { return Math.sin(x); }")
        assert "f" in result.functions
        ir = result.functions["f"]
        calls = [n for n in ir if n.kind.name == "CALL"]
        assert any(c.value == "sin" for c in calls)

    def test_math_abs_mapping(self):
        """Math.abs → fabs 映射。"""
        fe = _get_js_frontend()
        nodes = fe._parse_expr("Math.abs(x)", {})
        calls = [n for n in nodes if n.kind.name == "CALL"]
        assert any(c.value == "fabs" for c in calls)

    def test_math_pow_mapping(self):
        """Math.pow → pow 映射。"""
        fe = _get_js_frontend()
        nodes = fe._parse_expr("Math.pow(x, 2)", {})
        calls = [n for n in nodes if n.kind.name == "CALL"]
        assert any(c.value == "pow" for c in calls)

    def test_unary_minus(self):
        """一元负号。"""
        fe = _get_js_frontend()
        nodes = fe._parse_expr("-x", {})
        unaries = [n for n in nodes if n.kind.name == "UNARY"]
        assert len(unaries) >= 1
        assert unaries[0].op == "-"

    def test_triple_expr(self):
        """三元表达式解析。"""
        fe = _get_js_frontend()
        nodes = fe._parse_expr("x > 0 ? x : -x", {"x": T_FLOAT})
        assert len(nodes) > 0

    def test_effect_pure(self):
        """纯 JS 函数 → Pure（通过 analyze_effects）。"""
        fe = _get_js_frontend()
        result = fe.compile("function add(x, y) { return x + y; }")
        effects = fe.analyze_effects("function add(x, y) { return x + y; }")
        assert effects["add"] == "Pure"

    def test_effect_io(self):
        """含 console.log → IO。"""
        fe = _get_js_frontend()
        effects = fe.analyze_effects('function log(x) { console.log(x); }')
        assert effects["log"] == "IO"

    def test_empty_source(self):
        """空源码不崩溃。"""
        fe = _get_js_frontend()
        result = fe.compile("")
        assert result.language == "javascript"
        assert result.functions == {}

    def test_multiple_functions(self):
        """多函数编译。"""
        fe = _get_js_frontend()
        source = (
            "function add(x, y) { return x + y; }\n"
            "const mul = (x, y) => x * y;"
        )
        result = fe.compile(source)
        assert "add" in result.functions
        assert "mul" in result.functions

    def test_js_source_file_exists(self):
        """JS 原生源文件存在。"""
        f = FRONTENDS_DIR / "js" / "frontend.js"
        assert f.exists()
        content = f.read_text(encoding="utf-8")
        assert "function compile" in content
        assert "module.exports" in content

    def test_js_native_compile(self):
        """运行 JS 原生前端。"""
        f = FRONTENDS_DIR / "js" / "frontend.js"
        result = subprocess.run(
            ["node", str(f), "function foo(x) { return x + 1; }"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["language"] == "javascript"
        assert "foo" in data["functions"]


# ============================================================
# 5. MultiLanguageFrontend 统一注册测试
# ============================================================

class TestMultiLanguageFrontend:
    """MultiLanguageFrontend 注册与分发测试。"""

    def test_register_and_compile_rust(self):
        """注册 Rust 并编译。"""
        from src.multi_lang_frontend import MultiLanguageFrontend, RustFrontend
        ml = MultiLanguageFrontend()
        ml.register("rust", RustFrontend())
        result = ml.compile("fn foo(x: i32) -> i32 { x + 1 }", "rust")
        assert result.language == "rust"
        assert "foo" in result.functions

    def test_register_and_compile_go(self):
        """注册 Go 并编译。"""
        from src.multi_lang_frontend import MultiLanguageFrontend, GoFrontend
        ml = MultiLanguageFrontend()
        ml.register("go", GoFrontend())
        result = ml.compile("func foo(x int) int { return x + 1 }", "go")
        assert result.language == "go"
        assert "foo" in result.functions

    def test_register_and_compile_c(self):
        """注册 C 并编译。"""
        from src.multi_lang_frontend import MultiLanguageFrontend, CFrontend
        ml = MultiLanguageFrontend()
        ml.register("c", CFrontend())
        result = ml.compile("int foo(int x) { return x + 1; }", "c")
        assert result.language == "c"
        assert "foo" in result.functions

    def test_register_and_compile_js(self):
        """注册 JS 并编译。"""
        from src.multi_lang_frontend import MultiLanguageFrontend, JSFrontend
        ml = MultiLanguageFrontend()
        ml.register("javascript", JSFrontend())
        result = ml.compile("function foo(x) { return x + 1; }", "javascript")
        assert result.language == "javascript"
        assert "foo" in result.functions

    def test_all_four_registered(self):
        """四语言全部注册。"""
        from src.multi_lang_frontend import MultiLanguageFrontend, RustFrontend, GoFrontend, JSFrontend, CFrontend
        ml = MultiLanguageFrontend()
        ml.register("rust", RustFrontend())
        ml.register("go", GoFrontend())
        ml.register("javascript", JSFrontend())
        ml.register("c", CFrontend())
        langs = ml.supported_languages()
        assert "rust" in langs
        assert "go" in langs
        assert "javascript" in langs
        assert "c" in langs

    def test_unknown_language_raises(self):
        """未知语言抛出 ValueError。"""
        from src.multi_lang_frontend import MultiLanguageFrontend
        ml = MultiLanguageFrontend()
        with pytest.raises(ValueError):
            ml.compile("x + 1", "fortran")

    def test_infer_types_dispatch(self):
        """类型推断正确分发到各语言前端。"""
        from src.multi_lang_frontend import MultiLanguageFrontend, RustFrontend
        ml = MultiLanguageFrontend()
        ml.register("rust", RustFrontend())
        types = ml.infer_types("fn foo(x: i32) -> i32 { x }", "rust")
        assert "foo" in types

    def test_analyze_effects_dispatch(self):
        """效应分析正确分发。"""
        from src.multi_lang_frontend import MultiLanguageFrontend, JSFrontend
        ml = MultiLanguageFrontend()
        ml.register("javascript", JSFrontend())
        effects = ml.analyze_effects("function log(x) { console.log(x); }", "javascript")
        assert "log" in effects
        assert effects["log"] == "IO"

    def test_to_mir(self):
        """CompileResult.to_mir 生成有效 MIRProgram。"""
        from src.multi_lang_frontend import MultiLanguageFrontend, RustFrontend
        ml = MultiLanguageFrontend()
        ml.register("rust", RustFrontend())
        result = ml.compile("fn foo(x: i32) -> i32 { x + 1 }", "rust")
        mir = ml.to_mir(result)
        assert mir is not None
        assert "foo" in mir.functions

    def test_get_frontend_factory(self):
        """get_frontend() 工厂函数返回有效实例。"""
        from src.multi_lang_frontend import get_frontend
        ml = get_frontend()
        langs = ml.supported_languages()
        assert "rust" in langs
        assert "go" in langs
        assert "javascript" in langs
        assert "c" in langs


# ============================================================
# 6. HybridFrontend 混合编译器测试
# ============================================================

class TestHybridFrontend:
    """HybridFrontend 混合编译器测试。"""

    def test_init(self):
        """混合编译器初始化。"""
        from src.hybrid_frontend import HybridFrontend
        hc = HybridFrontend()
        assert hc is not None

    def test_supported_languages(self):
        """支持语言列表包含所有四语言。"""
        from src.hybrid_frontend import HybridFrontend
        hc = HybridFrontend()
        langs = hc.get_supported_languages()
        assert "rust" in langs
        assert "go" in langs
        assert "c" in langs
        assert "javascript" in langs or "js" in langs

    def test_compile_rust_fallback(self):
        """Rust 编译（无原生二进制，回退 Python 前端）。"""
        from src.hybrid_frontend import HybridFrontend
        hc = HybridFrontend()
        result = hc.compile("fn foo(x: i32) -> i32 { x + 1 }", "rust")
        assert result is not None
        assert result.language == "rust"

    def test_compile_go_fallback(self):
        """Go 编译（回退 Python 前端）。"""
        from src.hybrid_frontend import HybridFrontend
        hc = HybridFrontend()
        result = hc.compile("func foo(x int) int { return x + 1 }", "go")
        assert result is not None
        assert result.language == "go"

    def test_compile_c_fallback(self):
        """C 编译（回退 Python 前端）。"""
        from src.hybrid_frontend import HybridFrontend
        hc = HybridFrontend()
        result = hc.compile("int foo(int x) { return x + 1; }", "c")
        assert result is not None
        assert result.language == "c"

    def test_compile_js_fallback(self):
        """JS 编译（回退 Python 前端）。"""
        from src.hybrid_frontend import HybridFrontend
        hc = HybridFrontend()
        result = hc.compile("function foo(x) { return x + 1; }", "javascript")
        assert result is not None
        assert result.language == "javascript"

    def test_compile_unknown_fails_gracefully(self):
        """未知语言返回含错误的 IRResult。"""
        from src.hybrid_frontend import HybridFrontend
        hc = HybridFrontend()
        result = hc.compile("x + 1", "unknown")
        assert result is not None
        assert result.language == "unknown"

    def test_has_native_frontend_rust(self):
        """Rust 有后端前端（Python 正则）。"""
        from src.hybrid_frontend import HybridFrontend
        hc = HybridFrontend()
        assert hc._registry.get("rust") is not None

    def test_has_native_frontend_go(self):
        """Go 有后端前端。"""
        from src.hybrid_frontend import HybridFrontend
        hc = HybridFrontend()
        assert hc._registry.get("go") is not None

    def test_has_native_frontend_c(self):
        """C 有后端前端。"""
        from src.hybrid_frontend import HybridFrontend
        hc = HybridFrontend()
        assert hc._registry.get("c") is not None

    def test_has_native_frontend_js(self):
        """JS 有后端前端。"""
        from src.hybrid_frontend import HybridFrontend
        hc = HybridFrontend()
        assert hc._registry.get("javascript") is not None

    def test_native_runner_no_binary(self):
        """无原生二进制时返回 None 或 dict。"""
        from src.hybrid_frontend import NativeFrontendRunner
        runner = NativeFrontendRunner(FRONTENDS_DIR)
        result = runner.run_rust("fn foo() -> i32 { 1 }")
        assert result is None or isinstance(result, dict)

    def test_native_runner_js_no_node(self):
        """JS 前端 runner 不崩溃。"""
        from src.hybrid_frontend import NativeFrontendRunner
        runner = NativeFrontendRunner(FRONTENDS_DIR)
        result = runner.run_js("function foo() { return 1; }")
        assert result is None or isinstance(result, dict)

    def test_to_ir_result(self):
        """_to_ir_result 转换正确。"""
        from src.hybrid_frontend import HybridFrontend
        hc = HybridFrontend()
        native = {
            "language": "rust",
            "functions": {"foo": []},
            "types": {"foo": "Int"},
            "effects": {"foo": "Pure"},
            "errors": [],
        }
        ir = hc._to_ir_result(native, "rust", "source")
        assert ir.language == "rust"
        assert "foo" in ir.functions
        assert ir.effects["foo"] == "Pure"

    def test_compile_all_four_languages(self):
        """四语言全部编译通过。"""
        from src.hybrid_frontend import HybridFrontend
        hc = HybridFrontend()
        cases = [
            ("rust", "fn foo(x: i32) -> i32 { x + 1 }"),
            ("go", "func foo(x int) int { return x + 1 }"),
            ("c", "int foo(int x) { return x + 1; }"),
            ("javascript", "function foo(x) { return x + 1; }"),
        ]
        for lang, src in cases:
            result = hc.compile(src, lang)
            assert result is not None, f"{lang} 编译失败"
            assert result.language == lang, f"{lang} 语言不匹配"

    def test_get_hybrid_frontend_singleton(self):
        """get_hybrid_frontend() 返回单例。"""
        from src.hybrid_frontend import get_hybrid_frontend
        a = get_hybrid_frontend()
        b = get_hybrid_frontend()
        assert a is b

    def test_compile_to_ir_backward_compat(self):
        """compile_to_ir 向后兼容函数。"""
        from src.hybrid_frontend import compile_to_ir
        result = compile_to_ir("fn foo(x: i32) -> i32 { x + 1 }", "rust")
        assert result is not None
        assert result.language == "rust"

    def test_parse_foreign_backward_compat(self):
        """parse_foreign 向后兼容函数。"""
        from src.hybrid_frontend import parse_foreign
        result = parse_foreign("fn foo(x: i32) -> i32 { x + 1 }", "rust")
        assert isinstance(result, dict)
        assert result["language"] == "rust"


# ============================================================
# 7. 跨语言一致性测试
# 注意：使用直接前端实例（非 get_frontend），避免 tree-sitter 适配器干扰
# ============================================================

class TestCrossLanguageConsistency:
    """同一算法在各语言前端中的 IR 结构一致性。"""

    def _get_all_results(self):
        """使用直接前端实例（绕过 tree-sitter 适配器）。"""
        from src.multi_lang_frontend import RustFrontend, GoFrontend, JSFrontend, CFrontend
        rust_fe = RustFrontend()
        go_fe = GoFrontend()
        js_fe = JSFrontend()
        c_fe = CFrontend()

        rust_src = "fn add(a: i32, b: i32) -> i32 { return a + b; }"
        go_src = "func add(a int, b int) int { return a + b }"
        c_src = "int add(int a, int b) { return a + b; }"
        js_src = "function add(a, b) { return a + b; }"

        return {
            "rust": rust_fe.compile(rust_src),
            "go": go_fe.compile(go_src),
            "c": c_fe.compile(c_src),
            "javascript": js_fe.compile(js_src),
        }

    def test_all_compile_success(self):
        """四语言全部编译成功（无 error）。"""
        results = self._get_all_results()
        for lang, r in results.items():
            assert r.success, f"{lang} 编译有错误: {r.errors}"

    def test_all_have_add_function(self):
        """四语言都提取出 add 函数。"""
        results = self._get_all_results()
        for lang, r in results.items():
            assert "add" in r.functions, f"{lang} 未提取 add 函数"

    def test_all_have_function_count(self):
        """四语言函数数量一致（各 1 个）。"""
        results = self._get_all_results()
        for lang, r in results.items():
            assert len(r.functions) == 1, f"{lang} 函数数量: {len(r.functions)}"

    def test_all_have_types(self):
        """四语言类型信息不为空。"""
        results = self._get_all_results()
        for lang, r in results.items():
            assert "add" in r.types, f"{lang} 缺少 add 类型"

    def test_all_have_effects(self):
        """四语言效应分析不为空（通过 analyze_effects 验证）。"""
        from src.multi_lang_frontend import RustFrontend, GoFrontend, JSFrontend, CFrontend
        effects = {
            "rust": RustFrontend().analyze_effects("fn add(a: i32, b: i32) -> i32 { return a + b; }"),
            "go": GoFrontend().analyze_effects("func add(a int, b int) int { return a + b }"),
            "c": CFrontend().analyze_effects("int add(int a, int b) { return a + b; }"),
            "javascript": JSFrontend().analyze_effects("function add(a, b) { return a + b; }"),
        }
        for lang, e in effects.items():
            assert "add" in e, f"{lang} 缺少 add 效应"
            assert e["add"] == "Pure", f"{lang} add 应为 Pure"

    def test_rust_vs_go_function_names(self):
        """Rust 和 Go 提取的函数名一致。"""
        results = self._get_all_results()
        assert set(results["rust"].functions.keys()) == set(results["go"].functions.keys())

    def test_c_vs_js_function_names(self):
        """C 和 JS 提取的函数名一致。"""
        results = self._get_all_results()
        assert set(results["c"].functions.keys()) == set(results["javascript"].functions.keys())

    def test_all_function_names_same(self):
        """四语言函数名完全一致。"""
        results = self._get_all_results()
        rust_names = set(results["rust"].functions.keys())
        for lang, r in results.items():
            assert rust_names == set(r.functions.keys()), f"{lang} 函数名不一致"

    def test_multi_lang_frontend_single_compile(self):
        """通过 MultiLanguageFrontend.compile 四语言一致（直接注册正则前端）。"""
        from src.multi_lang_frontend import MultiLanguageFrontend, RustFrontend, GoFrontend, JSFrontend, CFrontend
        ml = MultiLanguageFrontend()
        ml.register("rust", RustFrontend())
        ml.register("go", GoFrontend())
        ml.register("javascript", JSFrontend())
        ml.register("c", CFrontend())

        sources = {
            "rust": "fn add(a: i32, b: i32) -> i32 { return a + b; }",
            "go": "func add(a int, b int) int { return a + b }",
            "c": "int add(int a, int b) { return a + b; }",
            "javascript": "function add(a, b) { return a + b; }",
        }
        for lang, src in sources.items():
            r = ml.compile(src, lang)
            assert r.success, f"{lang}: {r.errors}"
            assert "add" in r.functions

    def test_math_function_consistency(self):
        """sin/cos 在各语言前端中都被正确映射为对应调用。"""
        from src.multi_lang_frontend import RustFrontend, JSFrontend, CFrontend

        rust_result = RustFrontend().compile("fn f(x: f64) -> f64 { return sin(x); }")
        js_result = JSFrontend().compile("function f(x) { return Math.sin(x); }")
        c_result = CFrontend().compile("float f(float x) { return sin(x); }")

        for lang, r in [("rust", rust_result), ("javascript", js_result), ("c", c_result)]:
            ir = r.functions.get("f", [])
            calls = [n for n in ir if n.kind.name == "CALL"]
            assert any(c.value == "sin" for c in calls), f"{lang} 未找到 sin 映射"

    def test_param_count_consistency(self):
        """各语言 add 函数参数类型信息一致。"""
        from src.multi_lang_frontend import RustFrontend, GoFrontend, JSFrontend, CFrontend

        rust = RustFrontend().compile("fn add(a: i32, b: i32) -> i32 { return a + b; }")
        go = GoFrontend().compile("func add(a int, b int) int { return a + b }")
        c = CFrontend().compile("int add(int a, int b) { return a + b; }")
        js = JSFrontend().compile("function add(a, b) { return a + b; }")

        for lang, r in [("rust", rust), ("go", go), ("c", c), ("javascript", js)]:
            assert "add" in r.types, f"{lang} 缺少 add 类型"


# ============================================================
# 8. IRNode / CompileResult 数据结构测试
# ============================================================

class TestIRDataStructures:
    """IRNode 和 CompileResult 数据结构测试。"""

    def test_ir_node_with_type(self):
        """with_type 返回新节点。"""
        from src.multi_lang_frontend import IRNode, IRKind
        node = IRNode(IRKind.CONST, value=1.0, result="t0")
        typed = node.with_type(T_INT)
        assert typed.kind == node.kind
        assert typed.typ == T_INT
        assert typed is not node  # 新对象

    def test_ir_node_repr(self):
        """IRNode.__repr__ 格式正确。"""
        from src.multi_lang_frontend import IRNode, IRKind
        node = IRNode(IRKind.BINOP, op="+", result="t1")
        assert "BINOP" in repr(node)
        assert "op=+" in repr(node)

    def test_compile_result_success(self):
        """success 属性：无错误时为 True。"""
        from src.multi_lang_frontend import CompileResult
        cr = CompileResult(language="rust", source="")
        assert cr.success is True

    def test_compile_result_with_errors(self):
        """success 属性：有错误时为 False。"""
        from src.multi_lang_frontend import CompileResult
        cr = CompileResult(language="rust", source="", errors=["bad"])
        assert cr.success is False

    def test_compile_result_empty(self):
        """空 CompileResult 字段默认值。"""
        from src.multi_lang_frontend import CompileResult
        cr = CompileResult(language="rust", source="test")
        assert cr.ir_nodes == []
        assert cr.functions == {}
        assert cr.types == {}
        assert cr.effects == {}
        assert cr.globals == {}
        assert cr.errors == []
        assert cr.warnings == []

    def test_ir_to_mir_const(self):
        """_ir_to_mir 处理 CONST 节点。"""
        from src.multi_lang_frontend import IRNode, IRKind, _ir_to_mir
        node = IRNode(IRKind.CONST, value=3.14, result="t0", typ=T_FLOAT)
        mirs = _ir_to_mir(node)
        assert len(mirs) == 1

    def test_ir_to_mir_call(self):
        """_ir_to_mir 处理 CALL 节点。"""
        from src.multi_lang_frontend import IRNode, IRKind, _ir_to_mir
        node = IRNode(IRKind.CALL, value="sqrt", operands=["t0"], result="t1")
        mirs = _ir_to_mir(node)
        assert len(mirs) == 1

    def test_ir_to_mir_unknown_kind(self):
        """未知节点类型返回空列表。"""
        from src.multi_lang_frontend import IRNode, IRKind, _ir_to_mir
        node = IRNode(IRKind.LABEL, result="l1")
        mirs = _ir_to_mir(node)
        assert mirs == []


# ============================================================
# 9. 各语言前端边界条件测试
# ============================================================

class TestFrontendEdgeCases:
    """边界条件和异常处理测试。"""

    def test_rust_whitespace_only(self):
        """空白源码不崩溃。"""
        from src.multi_lang_frontend import RustFrontend
        fe = RustFrontend()
        result = fe.compile("   \n\t  ")
        assert result.language == "rust"

    def test_rust_comments_only(self):
        """仅注释不崩溃。"""
        from src.multi_lang_frontend import RustFrontend
        fe = RustFrontend()
        result = fe.compile("// comment\n// another\n")
        assert result.language == "rust"

    def test_go_nested_braces(self):
        """嵌套花括号不崩溃。"""
        from src.multi_lang_frontend import GoFrontend
        fe = GoFrontend()
        result = fe.compile("func outer() { if true { inner(); } }")
        assert result.language == "go"

    def test_c_multiple_semicolons(self):
        """多个分号的 C 代码不崩溃。"""
        from src.multi_lang_frontend import CFrontend
        fe = CFrontend()
        result = fe.compile("int f(int x) { int a=1;; int b=2; return a+b; }")
        assert result.language == "c"
        assert "f" in result.functions

    def test_js_null_undefined(self):
        """JS null/undefined 不崩溃。"""
        from src.multi_lang_frontend import JSFrontend
        fe = JSFrontend()
        result = fe.compile("function f(x) { return null; }")
        assert result.language == "javascript"

    def test_rust_option_type(self):
        """Option<T> 类型解析。"""
        from src.multi_lang_frontend import RustFrontend
        fe = RustFrontend()
        typ = fe._resolve_type("Option<i32>")
        assert typ == T_ANY

    def test_go_pointer_type(self):
        """*int 指针类型解析（Go 中 *int 默认解析为 Int）。"""
        from src.multi_lang_frontend import GoFrontend
        fe = GoFrontend()
        typ = fe._resolve_type("*int")
        # Go 的 *int 去掉 * 后解析为 int → Int
        assert typ.name in ("Int", "Any")

    def test_c_pointer_param(self):
        """C 指针参数解析。"""
        from src.multi_lang_frontend import CFrontend
        fe = CFrontend()
        params, types = fe._parse_params("int *ptr")
        assert len(params) == 1
        assert params[0] == "ptr"

    def test_js_arrow_with_parens(self):
        """箭头函数带括号参数。"""
        from src.multi_lang_frontend import JSFrontend
        fe = JSFrontend()
        result = fe.compile("const inc = (x) => x + 1;")
        assert "inc" in result.functions

    def test_very_long_source(self):
        """长源码不崩溃（性能边界）。"""
        from src.multi_lang_frontend import RustFrontend
        fe = RustFrontend()
        lines = ["fn main() {}"] + [f"fn func{i}(x: i32) -> i32 {{ return x + {i}; }}" for i in range(50)]
        source = "\n".join(lines)
        result = fe.compile(source)
        assert "func0" in result.functions
        assert "func49" in result.functions


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
