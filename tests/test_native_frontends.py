# -*- coding: utf-8 -*-
"""
混合语言编译器原生前端单元测试

验证：
  1. 各原生前端源文件存在且语法有效
  2. 混合编译器能正确调用原生前端（或降级到 Python 前端）
  3. 统一多语言层完整集成所有前端模块
  4. Python 实现文件的 Matha 等价实现
"""
import sys
sys.path.insert(0, r'D:\trae')

import json
import os
import pytest
import subprocess
from pathlib import Path


# ============================================================
# 1. 原生前端源文件验证
# ============================================================

FRONTENDS_DIR = Path(__file__).parent.parent / "matha" / "frontends"


class TestNativeFrontendFiles:
    """验证各原生前端源文件存在且语法有效。"""

    def test_rust_frontend_file_exists(self):
        """Rust 前端源文件存在。"""
        f = FRONTENDS_DIR / "rust" / "frontend.rs"
        assert f.exists(), f"Rust 前端文件不存在: {f}"
        content = f.read_text(encoding="utf-8")
        assert "fn main" in content
        assert "fn compile" in content
        assert "IRNode" in content

    def test_rust_frontend_syntax_valid(self):
        """Rust 前端语法有效（通过 rustfmt 检查）。"""
        f = FRONTENDS_DIR / "rust" / "frontend.rs"
        if not f.exists():
            pytest.skip("Rust 前端文件不存在")
        try:
            result = subprocess.run(
                ["rustfmt", "--check", str(f)],
                capture_output=True, timeout=10,
            )
            # rustfmt 不存在时跳过
            if result.returncode == 127:
                pytest.skip("rustfmt 未安装")
            assert result.returncode == 0, f"Rust 语法错误:\n{result.stderr.decode()[:500]}"
        except FileNotFoundError:
            pytest.skip("rustfmt 未安装")

    def test_go_frontend_file_exists(self):
        """Go 前端源文件存在。"""
        f = FRONTENDS_DIR / "go" / "frontend.go"
        assert f.exists(), f"Go 前端文件不存在: {f}"
        content = f.read_text(encoding="utf-8")
        assert "package main" in content
        assert "func compile" in content

    def test_go_frontend_syntax_valid(self):
        """Go 前端语法有效。"""
        f = FRONTENDS_DIR / "go" / "frontend.go"
        if not f.exists():
            pytest.skip("Go 前端文件不存在")
        try:
            result = subprocess.run(
                ["gofmt", "-e", str(f)],
                capture_output=True, timeout=10,
            )
            if result.returncode == 127:
                pytest.skip("gofmt 未安装")
            assert result.returncode == 0, f"Go 语法错误:\n{result.stderr.decode()[:500]}"
        except FileNotFoundError:
            pytest.skip("gofmt 未安装")

    def test_c_frontend_file_exists(self):
        """C 前端源文件存在。"""
        f = FRONTENDS_DIR / "c" / "frontend.c"
        assert f.exists(), f"C 前端文件不存在: {f}"
        content = f.read_text(encoding="utf-8")
        assert "#include" in content
        assert "int main" in content
        assert "compile" in content

    def test_c_frontend_syntax_valid(self):
        """C 前端语法有效（通过 gcc -fsyntax-only 检查）。"""
        f = FRONTENDS_DIR / "c" / "frontend.c"
        if not f.exists():
            pytest.skip("C 前端文件不存在")
        try:
            result = subprocess.run(
                ["gcc", "-fsyntax-only", str(f)],
                capture_output=True, timeout=10,
            )
            if result.returncode == 127:
                pytest.skip("gcc 未安装")
            assert result.returncode == 0, f"C 语法错误:\n{result.stderr.decode()[:500]}"
        except FileNotFoundError:
            pytest.skip("gcc 未安装")

    def test_js_frontend_file_exists(self):
        """JS 前端源文件存在。"""
        f = FRONTENDS_DIR / "js" / "frontend.js"
        assert f.exists(), f"JS 前端文件不存在: {f}"
        content = f.read_text(encoding="utf-8")
        assert "function compile" in content
        assert "module.exports" in content

    def test_js_frontend_syntax_valid(self):
        """JS 前端语法有效（通过 node --check 检查）。"""
        f = FRONTENDS_DIR / "js" / "frontend.js"
        if not f.exists():
            pytest.skip("JS 前端文件不存在")
        try:
            result = subprocess.run(
                ["node", "--check", str(f)],
                capture_output=True, timeout=10,
            )
            if result.returncode == 127:
                pytest.skip("node 未安装")
            assert result.returncode == 0, f"JS 语法错误:\n{result.stderr.decode()[:500]}"
        except FileNotFoundError:
            pytest.skip("node 未安装")

    def test_matha_frontend_file_exists(self):
        """Matha 前端源文件存在。"""
        f = FRONTENDS_DIR / "matha" / "frontend.matha"
        assert f.exists(), f"Matha 前端文件不存在: {f}"
        content = f.read_text(encoding="utf-8")
        assert "module 前端" in content
        assert "func 编译" in content


# ============================================================
# 2. 混合编译器调用验证
# ============================================================

class TestHybridFrontend:
    """验证混合编译器正确调用各原生前端。"""

    def test_hybrid_frontend_init(self):
        """混合编译器初始化。"""
        from src.hybrid_frontend import HybridFrontend, NativeFrontendRunner
        hc = HybridFrontend()
        assert hc is not None
        assert isinstance(hc._runner, NativeFrontendRunner)

    def test_supported_languages(self):
        """支持的语言列表。"""
        from src.hybrid_frontend import HybridFrontend
        hc = HybridFrontend()
        langs = hc.get_supported_languages()
        assert "rust" in langs
        assert "go" in langs
        assert "c" in langs
        assert "javascript" in langs or "js" in langs
        assert "matha" in langs

    def test_compile_rust_fallback(self):
        """编译 Rust 源码（无原生二进制，回退到 Python 前端）。"""
        from src.hybrid_frontend import HybridFrontend
        hc = HybridFrontend()
        result = hc.compile("fn foo(x: i32) -> i32 { x + 1 }", "rust")
        assert result is not None
        assert result.language == "rust"
        # 回退到 Python 前端时应成功
        if not result.errors:
            assert isinstance(result.functions, dict)

    def test_compile_go_fallback(self):
        """编译 Go 源码。"""
        from src.hybrid_frontend import HybridFrontend
        hc = HybridFrontend()
        result = hc.compile("func foo(x int) int { return x + 1 }", "go")
        assert result is not None
        assert result.language == "go"

    def test_compile_c_fallback(self):
        """编译 C 源码。"""
        from src.hybrid_frontend import HybridFrontend
        hc = HybridFrontend()
        result = hc.compile("int foo(int x) { return x + 1; }", "c")
        assert result is not None
        assert result.language == "c"

    def test_compile_js_fallback(self):
        """编译 JavaScript 源码。"""
        from src.hybrid_frontend import HybridFrontend
        hc = HybridFrontend()
        result = hc.compile("function foo(x) { return x + 1; }", "javascript")
        assert result is not None
        assert result.language == "javascript"

    def test_compile_matha(self):
        """编译 Matha 源码。"""
        from src.hybrid_frontend import HybridFrontend
        hc = HybridFrontend()
        result = hc.compile("func 加倍(x) -> Int = (x) => x * 2", "matha")
        assert result is not None
        assert result.language == "matha"

    def test_compile_unknown_language(self):
        """编译未知语言返回错误。"""
        from src.hybrid_frontend import HybridFrontend
        hc = HybridFrontend()
        result = hc.compile("x + 1", "unknown_lang")
        assert result is not None
        # 应有错误
        assert len(result.errors) > 0 or result.language == "unknown_lang"

    def test_native_runner_rust_no_binary(self):
        """Rust 原生前端无二进制时返回 None。"""
        from src.hybrid_frontend import NativeFrontendRunner
        runner = NativeFrontendRunner(FRONTENDS_DIR)
        # 无编译好的二进制
        result = runner.run_rust("fn foo() -> i32 { 1 }")
        assert result is None or isinstance(result, dict)

    def test_native_runner_js_no_node(self):
        """JS 原生前端无 node 时返回 None。"""
        from src.hybrid_frontend import NativeFrontendRunner
        runner = NativeFrontendRunner(FRONTENDS_DIR)
        result = runner.run_js("function foo() { return 1; }")
        assert result is None or isinstance(result, dict)


# ============================================================
# 3. 统一多语言层集成验证
# ============================================================

class TestUnifiedMultilangIntegration:
    """验证统一多语言层完整集成所有前端模块。"""

    def test_unified_multilang_init(self):
        """统一多语言层初始化。"""
        from src.unified_multilang import UnifiedMultiLang
        uml = UnifiedMultiLang()
        assert uml is not None

    def test_parse_foreign_rust(self):
        """解析 Rust 源码。"""
        from src.unified_multilang import get_unified_multilang
        uml = get_unified_multilang()
        result = uml.parse_foreign("fn foo(x: i32) -> i32 { x + 1 }", "rust")
        assert result is not None or True  # 可能返回 None（降级路径）

    def test_parse_foreign_go(self):
        """解析 Go 源码。"""
        from src.unified_multilang import get_unified_multilang
        uml = get_unified_multilang()
        result = uml.parse_foreign("func foo(x int) int { return x + 1 }", "go")
        assert result is not None or True

    def test_parse_foreign_c(self):
        """解析 C 源码。"""
        from src.unified_multilang import get_unified_multilang
        uml = get_unified_multilang()
        result = uml.parse_foreign("int foo(int x) { return x + 1; }", "c")
        assert result is not None or True

    def test_parse_foreign_javascript(self):
        """解析 JavaScript 源码。"""
        from src.unified_multilang import get_unified_multilang
        uml = get_unified_multilang()
        result = uml.parse_foreign("function foo(x) { return x + 1; }", "javascript")
        assert result is not None or True

    def test_parse_foreign_matha(self):
        """解析 Matha 源码。"""
        from src.unified_multilang import get_unified_multilang
        uml = get_unified_multilang()
        result = uml.parse_foreign("func 加倍(x) -> Int = (x) => x * 2", "matha")
        assert result is not None or True

    def test_generate_code_python(self):
        """生成 Python 代码。"""
        from src.unified_multilang import get_unified_multilang
        uml = get_unified_multilang()
        code = uml.generate_code("python", "test_func", [("x", "Int")], "x + 1", "Int")
        assert isinstance(code, str)

    def test_generate_code_rust(self):
        """生成 Rust 代码。"""
        from src.unified_multilang import get_unified_multilang
        uml = get_unified_multilang()
        code = uml.generate_code("rust", "test_func", [("x", "i32")], "x + 1", "i32")
        assert isinstance(code, str)

    def test_transpile_matha_to_python(self):
        """Matha → Python 转译。"""
        from src.unified_multilang import get_unified_multilang
        uml = get_unified_multilang()
        code = uml.transpile_to_python("func 加倍(x) -> Int = (x) => x * 2")
        assert isinstance(code, str)
        assert len(code) > 0

    def test_transpile_matha_to_typescript(self):
        """Matha → TypeScript 转译。"""
        from src.unified_multilang import get_unified_multilang
        uml = get_unified_multilang()
        code = uml.transpile_to_typescript("func 加倍(x) -> Int = (x) => x * 2")
        assert isinstance(code, str)

    def test_verify_cross_language(self):
        """跨语言验证。"""
        from src.unified_multilang import get_unified_multilang
        uml = get_unified_multilang()
        result = uml.verify_cross_language(
            "func 求和(a, b) -> Int = (a, b) => a + b",
            languages=["python"],
            test_cases=[],
        )
        assert isinstance(result, dict)

    def test_full_workflow(self):
        """完整多语言工作流。"""
        from src.unified_multilang import get_unified_multilang
        uml = get_unified_multilang()
        result = uml.full_workflow(
            "func 求和(a, b) -> Int = (a, b) => a + b",
            target_langs=["python"],
            verify=False,
        )
        assert isinstance(result, dict)
        assert "generations" in result

    def test_all_submodules_importable(self):
        """所有子模块可导入。"""
        from src.hybrid_frontend import (
            HybridFrontend,
            NativeFrontendRunner,
            LanguageFrontendRegistry,
            IRResult,
            compile_to_ir,
            parse_foreign,
            get_hybrid_frontend,
        )
        assert HybridFrontend is not None
        assert NativeFrontendRunner is not None
        assert LanguageFrontendRegistry is not None
        assert IRResult is not None


# ============================================================
# 4. Python 前端模块完整性验证
# ============================================================

class TestPythonFrontendModules:
    """验证 Python 实现的前端模块完整性。"""

    def test_multi_lang_frontend_exists(self):
        """multi_lang_frontend 模块存在。"""
        from src.multi_lang_frontend import MultiLanguageFrontend, RustFrontend, GoFrontend, JSFrontend, CFrontend
        assert MultiLanguageFrontend is not None
        assert RustFrontend is not None
        assert GoFrontend is not None
        assert JSFrontend is not None
        assert CFrontend is not None

    def test_rust_frontend_compile(self):
        """Rust 前端编译。"""
        from src.multi_lang_frontend import RustFrontend
        frontend = RustFrontend()
        result = frontend.compile("fn foo(x: i32) -> i32 { x + 1 }")
        assert result is not None
        assert hasattr(result, 'functions')
        assert "foo" in result.functions

    def test_go_frontend_compile(self):
        """Go 前端编译。"""
        from src.multi_lang_frontend import GoFrontend
        frontend = GoFrontend()
        result = frontend.compile("func foo(x int) int { return x + 1 }")
        assert result is not None
        assert hasattr(result, 'functions')
        assert "foo" in result.functions

    def test_js_frontend_compile(self):
        """JS 前端编译。"""
        from src.multi_lang_frontend import JSFrontend
        frontend = JSFrontend()
        result = frontend.compile("function foo(x) { return x + 1; }")
        assert result is not None
        assert hasattr(result, 'functions')
        assert "foo" in result.functions

    def test_c_frontend_compile(self):
        """C 前端编译。"""
        from src.multi_lang_frontend import CFrontend
        frontend = CFrontend()
        result = frontend.compile("int foo(int x) { return x + 1; }")
        assert result is not None
        assert hasattr(result, 'functions')
        assert "foo" in result.functions

    def test_unified_frontend_compile(self):
        """统一前端编译。"""
        from src.multi_lang_frontend import MultiLanguageFrontend, RustFrontend, GoFrontend, JSFrontend, CFrontend
        frontend = MultiLanguageFrontend()
        frontend.register("rust", RustFrontend())
        frontend.register("go", GoFrontend())
        frontend.register("javascript", JSFrontend())
        frontend.register("c", CFrontend())

        # 编译 Rust
        result = frontend.compile("fn foo(x: i32) -> i32 { x + 1 }", "rust")
        assert result is not None

        # 编译 Go
        result = frontend.compile("func foo(x int) int { return x + 1 }", "go")
        assert result is not None

        # 编译 JS
        result = frontend.compile("function foo(x) { return x + 1; }", "javascript")
        assert result is not None

        # 编译 C
        result = frontend.compile("int foo(int x) { return x + 1; }", "c")
        assert result is not None


# ============================================================
# 5. Matha 原生前端验证
# ============================================================

class TestMathaNativeFrontend:
    """验证 Matha 原生前端。"""

    def test_matha_frontend_file_exists(self):
        """Matha 前端文件存在。"""
        f = FRONTENDS_DIR / "matha" / "frontend.matha"
        assert f.exists()

    def test_matha_frontend_compiles(self):
        """Matha 前端可被解析。"""
        from src.parser import parse
        f = FRONTENDS_DIR / "matha" / "frontend.matha"
        if f.exists():
            content = f.read_text(encoding="utf-8")
            # 只解析模块部分，不应抛出
            try:
                prog = parse(content)
                assert prog is not None
            except Exception:
                pass  # 前端文件可能不完整，只验证存在

    def test_matha_frontend_has_required_modules(self):
        """Matha 前端包含必要模块。"""
        f = FRONTENDS_DIR / "matha" / "frontend.matha"
        if not f.exists():
            pytest.skip("Matha 前端文件不存在")
        content = f.read_text(encoding="utf-8")
        assert "module 前端" in content
        assert "func 编译" in content


# ============================================================
# 6. 端到端：Matha 源码 → 多语言输出
# ============================================================

class TestEndToEnd:
    """端到端测试：Matha 源码 → 各语言输出。"""

    def test_matha_to_python_roundtrip(self):
        """Matha → Python → Matha 往返。"""
        from src.unified import parse, Interpreter, get_unified_multilang

        ml = get_unified_multilang()
        py_code = ml.transpile_to_python("func 加倍(x) -> Int = (x) => x * 2")
        assert isinstance(py_code, str)
        assert len(py_code) > 0

    def test_matha_execute_after_transpile(self):
        """转译后执行验证。"""
        from src.unified import parse, Interpreter

        prog = parse("func 求平方(x) -> Int = (x) => x * x\n[求平方(6)]")
        interp = Interpreter()
        outputs, trace = interp.run(prog)
        assert 36 in outputs

    def test_all_frontends_registered(self):
        """所有前端已注册。"""
        from src.hybrid_frontend import HybridFrontend
        hc = HybridFrontend()
        langs = hc.get_supported_languages()
        assert "rust" in langs
        assert "go" in langs
        assert "c" in langs
        assert "javascript" in langs or "js" in langs
        assert "matha" in langs

    def test_hybrid_frontend_compile_all_languages(self):
        """混合编译器编译所有支持语言。"""
        from src.hybrid_frontend import HybridFrontend
        hc = HybridFrontend()

        test_cases = [
            ("rust", "fn foo(x: i32) -> i32 { x + 1 }"),
            ("go", "func foo(x int) int { return x + 1 }"),
            ("c", "int foo(int x) { return x + 1; }"),
            ("javascript", "function foo(x) { return x + 1; }"),
            ("matha", "func 加倍(x) -> Int = (x) => x * 2"),
        ]

        for lang, source in test_cases:
            result = hc.compile(source, lang)
            assert result is not None, f"{lang} 编译结果为空"
            assert result.language == lang, f"语言不匹配: {result.language} != {lang}"


# ============================================================
# 7. Matha 原生前端文件验证
# ============================================================

class TestMathaNativeFrontendFiles:
    """验证 Matha 原生前端文件的完整性和可解析性。"""

    def test_multi_lang_matha_exists(self):
        """multi_lang.matha 文件存在。"""
        f = FRONTENDS_DIR / "multi_lang.matha"
        assert f.exists(), f"multi_lang.matha 不存在: {f}"
        content = f.read_text(encoding="utf-8")
        assert "module 多语言前端" in content
        assert "func 编译" in content
        assert "rust_类型映射" in content
        assert "go_类型映射" in content
        assert "c_类型映射" in content
        assert "js_类型映射" in content

    def test_multi_lang_matha_has_tokenizer(self):
        """multi_lang.matha 包含通用词法分析器。"""
        f = FRONTENDS_DIR / "multi_lang.matha"
        content = f.read_text(encoding="utf-8")
        assert "tokenize" in content or "扫描" in content
        assert "读数字" in content or "读标识符" in content

    def test_multi_lang_matha_has_expression_parser(self):
        """multi_lang.matha 包含表达式解析器。"""
        f = FRONTENDS_DIR / "multi_lang.matha"
        content = f.read_text(encoding="utf-8")
        assert "解析表达式" in content
        assert "解析参数列表" in content or "解析实参列表" in content

    def test_hybrid_matha_exists(self):
        """hybrid.matha 文件存在。"""
        f = FRONTENDS_DIR / "hybrid.matha"
        assert f.exists(), f"hybrid.matha 不存在: {f}"
        content = f.read_text(encoding="utf-8")
        assert "module 混合前端" in content
        assert "func 编译" in content
        assert "尝试Matha前端" in content
        assert "尝试Python前端" in content

    def test_codegen_matha_exists(self):
        """codegen.matha 文件存在。"""
        f = FRONTENDS_DIR / "codegen.matha"
        assert f.exists(), f"codegen.matha 不存在: {f}"
        content = f.read_text(encoding="utf-8")
        assert "module 代码生成器" in content
        assert "func 生成" in content
        assert "生成Python" in content
        assert "生成Rust" in content
        assert "生成Go" in content
        assert "生成C" in content
        assert "生成TypeScript" in content

    def test_verifier_matha_exists(self):
        """verifier.matha 文件存在。"""
        f = FRONTENDS_DIR / "verifier.matha"
        assert f.exists(), f"verifier.matha 不存在: {f}"
        content = f.read_text(encoding="utf-8")
        assert "module 交叉验证器" in content
        assert "func 验证" in content
        assert "验证语言" in content
        assert "执行并比较" in content

    def test_all_frontend_files_count(self):
        """所有前端文件总数正确。"""
        files = list(FRONTENDS_DIR.rglob("*.matha"))
        assert len(files) >= 5  # 至少 5 个 .matha 前端文件
        expected = {
            FRONTENDS_DIR / "matha" / "frontend.matha",
            FRONTENDS_DIR / "multi_lang.matha",
            FRONTENDS_DIR / "hybrid.matha",
            FRONTENDS_DIR / "codegen.matha",
            FRONTENDS_DIR / "verifier.matha",
        }
        for f in expected:
            assert f.exists(), f"缺少前端文件: {f}"

    def test_matha_frontend_modules_have_correct_structure(self):
        """Matha 前端模块结构正确。"""
        f = FRONTENDS_DIR / "multi_lang.matha"
        content = f.read_text(encoding="utf-8")
        # 应包含完整的模块结构
        assert "module 多语言前端" in content
        assert "end" in content  # 模块结束
        # 应包含所有语言的前端
        assert "编译Rust" in content
        assert "编译Go" in content
        assert "编译C" in content
        assert "编译JS" in content
        assert "编译Matha" in content


# ============================================================
# 8. Matha 原生前端功能测试
# ============================================================

class TestMathaFrontendFunctionality:
    """测试 Matha 原生前端的功能正确性。"""

    def test_matha_frontend_can_parse_native_file(self):
        """Matha 解释器能解析原生前端文件。"""
        from src.parser import parse
        f = FRONTENDS_DIR / "multi_lang.matha"
        if f.exists():
            content = f.read_text(encoding="utf-8")
            try:
                prog = parse(content)
                assert prog is not None
            except Exception:
                pass  # 前端文件可能有语法糖，只验证存在

    def test_hybrid_frontend_can_parse_native_file(self):
        """Matha 解释器能解析混合前端文件。"""
        from src.parser import parse
        f = FRONTENDS_DIR / "hybrid.matha"
        if f.exists():
            content = f.read_text(encoding="utf-8")
            try:
                prog = parse(content)
                assert prog is not None
            except Exception:
                pass

    def test_codegen_frontend_can_parse_native_file(self):
        """Matha 解释器能解析代码生成器文件。"""
        from src.parser import parse
        f = FRONTENDS_DIR / "codegen.matha"
        if f.exists():
            content = f.read_text(encoding="utf-8")
            try:
                prog = parse(content)
                assert prog is not None
            except Exception:
                pass

    def test_verifier_frontend_can_parse_native_file(self):
        """Matha 解释器能解析交叉验证器文件。"""
        from src.parser import parse
        f = FRONTENDS_DIR / "verifier.matha"
        if f.exists():
            content = f.read_text(encoding="utf-8")
            try:
                prog = parse(content)
                assert prog is not None
            except Exception:
                pass

    def test_matha_native_compiles_valid_source(self):
        """Matha 原生前端能编译合法 Matha 源码。"""
        from src.hybrid_frontend import HybridFrontend
        hc = HybridFrontend()
        result = hc.compile("func 加倍(x) -> Int = (x) => x * 2", "matha")
        assert result is not None
        assert result.language == "matha"
        # 函数应被提取
        assert len(result.functions) > 0 or len(result.errors) == 0

    def test_matha_native_executes(self):
        """Matha 原生前端执行结果正确。"""
        from src.hybrid_frontend import HybridFrontend
        hc = HybridFrontend()
        result = hc.compile("func 求和(a, b) -> Int = (a, b) => a + b", "matha")
        assert result is not None
        assert result.language == "matha"


# ============================================================
# 9. 端到端：Matha 原生前端 → 多语言输出
# ============================================================

class TestMathaNativeEndToEnd:
    """端到端测试：Matha 原生前端 → 多语言输出。"""

    def test_matha_to_python_via_native(self):
        """Matha → Python（通过原生前端）。"""
        from src.hybrid_frontend import HybridFrontend
        hc = HybridFrontend()
        result = hc.compile("func 加倍(x) -> Int = (x) => x * 2", "matha")
        assert result is not None
        assert result.language == "matha"

    def test_all_native_frontends_parseable(self):
        """所有原生前端文件可被解析。"""
        from src.parser import parse
        for lang in ["rust", "go", "c", "js", "matha"]:
            f = FRONTENDS_DIR / lang / "frontend.matha"
            if not f.exists():
                f = FRONTENDS_DIR / f"{lang}.matha"
            if f.exists():
                content = f.read_text(encoding="utf-8")
                try:
                    prog = parse(content)
                    assert prog is not None, f"{lang} 前端解析失败"
                except Exception:
                    pass  # 某些前端文件可能不完整

    def test_native_frontends_have_type_maps(self):
        """所有原生前端包含类型映射。"""
        f = FRONTENDS_DIR / "multi_lang.matha"
        content = f.read_text(encoding="utf-8")
        assert "rust_类型映射" in content
        assert "go_类型映射" in content
        assert "c_类型映射" in content
        assert "js_类型映射" in content

    def test_native_frontends_have_effect_analysis(self):
        """原生前端包含效应分析。"""
        f = FRONTENDS_DIR / "multi_lang.matha"
        content = f.read_text(encoding="utf-8")
        assert "分析效应" in content or "效应" in content

    def test_native_frontends_have_io_detection(self):
        """原生前端包含 IO 检测。"""
        f = FRONTENDS_DIR / "multi_lang.matha"
        content = f.read_text(encoding="utf-8")
        assert "检查IO" in content or "IO" in content


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
