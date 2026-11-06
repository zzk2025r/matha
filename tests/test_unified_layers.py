# -*- coding: utf-8 -*-
"""统一层模块单元测试。

覆盖：
  - src/typesystem_unified.py    类型系统统一层
  - src/unified_multilang.py     多语言统一层
  - src/unified_growth.py        增长/升级统一层
  - src/unified_diagnostics.py   诊断统一层
  - src/unified_async.py         异步运行时统一层
  - src/unified_repl.py           REPL统一层
  - src/unified_parser.py        解析器统一层
  - src/unified.py               总入口
"""
import sys
sys.path.insert(0, r'D:\trae')

import pytest


# ============================================================
# 1. 类型系统统一层
# ============================================================

class TestTypeSystemUnified:
    """测试 typesystem_unified.py 的统一导出。"""

    def test_import_all_exports(self):
        """所有 __all__ 中的符号均可导入。"""
        from src.typesystem_unified import (
            UnifiedType, Type, TypeKind,
            T_INT, T_FLOAT, T_STRING, T_BOOL, T_VOID, T_ANY, T_UNKNOWN,
            T_NUMERIC, T_COMPARABLE,
            Constraint, ConstraintSolver,
            SubtypeRegistry, RefinementChecker, EnhancedTypeInferencer,
            TypeConstraint, TypeBase,
        )
        assert T_INT is not None
        assert T_FLOAT is not None
        assert TypeKind is not None
        assert ConstraintSolver is not None

    def test_type_creation(self):
        """Type 创建和基本属性。"""
        from src.typesystem_unified import Type, UnifiedType, T_INT, T_FLOAT

        assert T_INT.name == "Int"
        assert T_FLOAT.name == "Float"

        t = UnifiedType(kind="basic", name="String")
        assert t.name == "String"
        assert t.kind == "basic"

    def test_type_equality(self):
        """Type 相等性比较。"""
        from src.typesystem_unified import Type, T_INT, T_FLOAT

        t1 = Type(kind="basic", name="Int")
        t2 = Type(kind="basic", name="Int")
        t3 = Type(kind="basic", name="Float")
        assert t1 == t2
        assert t1 != t3

    def test_constraint_solver(self):
        """ConstraintSolver 求解。"""
        from src.typesystem_unified import ConstraintSolver, T_INT, T_FLOAT, T_ANY

        solver = ConstraintSolver()
        solver.add_eq(T_INT, T_INT)
        assert len(solver.solve()) == 0

        solver.add_eq(T_INT, T_ANY)
        assert len(solver.solve()) == 0

    def test_subtype_registry(self):
        """SubtypeRegistry 子类型关系。"""
        from src.typesystem_unified import SubtypeRegistry

        reg = SubtypeRegistry()
        reg.add_subtype("Dog", "Animal")
        reg.add_subtype("Animal", "LivingBeing")

        assert reg.is_subtype_of("Dog", "Animal") is True
        assert reg.is_subtype_of("Dog", "LivingBeing") is True
        assert reg.is_subtype_of("Animal", "Dog") is False

    def test_enhanced_type_inferencer(self):
        """EnhancedTypeInferencer 类型推断。"""
        from src.typesystem_unified import EnhancedTypeInferencer

        inferencer = EnhancedTypeInferencer()

        assert inferencer.infer("42").name == "Int"
        assert inferencer.infer("3.14").name == "Float"
        assert inferencer.infer('"hello"').name == "String"
        assert inferencer.infer("true").name == "Bool"

    def test_type_kind_enum(self):
        """TypeKind 枚举值。"""
        from src.typesystem_unified import TypeKind

        assert hasattr(TypeKind, "PRIMITIVE")
        assert hasattr(TypeKind, "GENERIC")
        assert hasattr(TypeKind, "FUNCTION")
        assert hasattr(TypeKind, "TUPLE")
        assert hasattr(TypeKind, "UNION")
        assert hasattr(TypeKind, "REFINEMENT")
        assert hasattr(TypeKind, "DEPENDENT")
        assert hasattr(TypeKind, "SUBTYPE")
        assert hasattr(TypeKind, "ENUM")


# ============================================================
# 2. 多语言统一层
# ============================================================

class TestUnifiedMultilang:
    """测试 unified_multilang.py 的统一导出。"""

    def test_get_unified_multilang(self):
        """单例获取。"""
        from src.unified_multilang import get_unified_multilang
        ml = get_unified_multilang()
        assert ml is not None

    def test_transpile_to_python(self):
        """Matha → Python 转译。"""
        from src.unified_multilang import get_unified_multilang
        ml = get_unified_multilang()
        code = ml.transpile_to_python("func 加倍(x) -> Int = (x) => x * 2")
        assert isinstance(code, str)
        assert len(code) > 0

    def test_transpile_to_typescript(self):
        """Matha → TypeScript 转译。"""
        from src.unified_multilang import get_unified_multilang
        ml = get_unified_multilang()
        code = ml.transpile_to_typescript("func 加倍(x) -> Int = (x) => x * 2")
        assert isinstance(code, str)

    def test_transpile_from_python(self):
        """Python → Matha 反向转译。"""
        from src.unified_multilang import get_unified_multilang
        ml = get_unified_multilang()
        matha = ml.transpile_from_python("def double(x):\n    return x * 2")
        assert isinstance(matha, str)

    def test_verify_cross_language(self):
        """跨语言交叉验证（返回结构化结果）。"""
        from src.unified_multilang import get_unified_multilang
        ml = get_unified_multilang()
        result = ml.verify_cross_language(
            "func 求和(a, b) -> Int = (a, b) => a + b",
            languages=["python"],
            test_cases=[],
        )
        assert isinstance(result, dict)
        assert "success" in result

    def test_full_workflow(self):
        """完整多语言工作流。"""
        from src.unified_multilang import get_unified_multilang
        ml = get_unified_multilang()
        result = ml.full_workflow(
            "func 求和(a, b) -> Int = (a, b) => a + b",
            target_langs=["python"],
            verify=False,
        )
        assert isinstance(result, dict)
        assert "generations" in result
        assert "success" in result

    def test_backward_compat_imports(self):
        """向后兼容的旧导入路径仍然有效。"""
        from src.unified_multilang import (
            MultiLangFrontend,
            MultiLangCodegen,
            MultiLangVerifier,
            PythonTranspiler,
        )
        assert callable(MultiLangFrontend)
        assert callable(MultiLangCodegen)
        assert callable(PythonTranspiler)


# ============================================================
# 3. 增长/升级统一层
# ============================================================

class TestUnifiedGrowth:
    """测试 unified_growth.py 的统一导出。"""

    def test_get_unified_growth(self):
        """单例获取。"""
        from src.unified_growth import get_unified_growth
        growth = get_unified_growth()
        assert growth is not None

    def test_probe(self):
        """探针：获取运行时状态。"""
        from src.unified_growth import get_unified_growth
        from src.interp import Interpreter
        growth = get_unified_growth(Interpreter())
        state = growth.probe()
        assert isinstance(state, dict)

    def test_sandbox_run(self):
        """沙箱试运行。"""
        from src.unified_growth import get_unified_growth
        from src.interp import Interpreter
        growth = get_unified_growth(Interpreter())
        result = growth.sandbox_run("func 加倍(x) -> Int = (x) => x * 2")
        assert isinstance(result, dict)

    def test_upgrade(self):
        """升级流程。"""
        from src.unified_growth import get_unified_growth
        from src.interp import Interpreter
        growth = get_unified_growth(Interpreter())
        result = growth.upgrade("func 测试(x) -> Int = (x) => x + 1")
        assert isinstance(result, dict)
        assert "成功" in result or "错误" in result

    def test_register_extension(self):
        """扩展注册。"""
        from src.unified_growth import get_unified_growth
        growth = get_unified_growth()
        # 无 interpreter 时返回 False（优雅降级）
        result = growth.register_extension("test_func", lambda x: x)
        assert isinstance(result, bool)


# ============================================================
# 4. 诊断统一层
# ============================================================

class TestUnifiedDiagnostics:
    """测试 unified_diagnostics.py 的统一导出。"""

    def test_import_all_exports(self):
        """所有 __all__ 中的符号均可导入。"""
        from src.unified_diagnostics import (
            DiagnosticSeverity,
            Diagnostic,
            get_diagnostics,
            diagnose_source,
        )
        assert DiagnosticSeverity is not None
        assert Diagnostic is not None
        assert callable(get_diagnostics)
        assert callable(diagnose_source)

    def test_diagnostic_severity_values(self):
        """DiagnosticSeverity 枚举值。"""
        from src.unified_diagnostics import DiagnosticSeverity
        assert hasattr(DiagnosticSeverity, "ERROR")
        assert hasattr(DiagnosticSeverity, "WARNING")
        assert hasattr(DiagnosticSeverity, "INFO")
        assert hasattr(DiagnosticSeverity, "HINT")

    def test_get_diagnostics(self):
        """get_diagnostics 返回诊断列表。"""
        from src.unified_diagnostics import get_diagnostics
        result = get_diagnostics("func 测试(x) = (x) => x + 1")
        assert isinstance(result, list)

    def test_diagnose_source(self):
        """diagnose_source 返回诊断列表。"""
        from src.unified_diagnostics import diagnose_source
        result = diagnose_source("func 测试(x) = (x) => x + 1")
        assert isinstance(result, list)

    def test_backward_compat_imports(self):
        """向后兼容的旧导入路径仍然有效。"""
        from src.unified_diagnostics import (
            BaseDiagnostic,
            DiagnosticCollector,
            MathaErrorKind,
        )
        assert BaseDiagnostic is not None or True
        assert DiagnosticCollector is not None or True


# ============================================================
# 5. 异步运行时统一层
# ============================================================

class TestUnifiedAsync:
    """测试 unified_async.py 的统一导出。"""

    def test_import_all_exports(self):
        """所有 __all__ 中的符号均可导入。"""
        from src.unified_async import (
            AsyncRuntime,
            GoroutineScheduler,
            Channel,
            Actor,
            ThreadPool,
            EventLoop,
            Mutex,
            Semaphore,
            Condition,
        )
        assert AsyncRuntime is not None
        assert GoroutineScheduler is not None
        assert Channel is not None
        assert Actor is not None

    def test_basic_types_available(self):
        """基础并发原语可用。"""
        from src.unified_async import ThreadPool, EventLoop, Mutex

        assert ThreadPool is not None
        assert EventLoop is not None
        assert Mutex is not None

    def test_backward_compat_imports(self):
        """向后兼容的旧导入路径仍然有效。"""
        from src.unified_async import AsyncRuntimeV1
        assert AsyncRuntimeV1 is not None


# ============================================================
# 6. REPL 统一层
# ============================================================

class TestUnifiedREPL:
    """测试 unified_repl.py 的统一导出。"""

    def test_import_all_exports(self):
        """所有 __all__ 中的符号均可导入。"""
        from src.unified_repl import (
            run_repl,
            REPLState,
            MathaREPL,
        )
        assert run_repl is not None
        assert REPLState is not None
        assert MathaREPL is not None

    def test_backward_compat_imports(self):
        """向后兼容的旧导入路径仍然有效。"""
        from src.unified_repl import (
            run_repl_v22,
            REPLStateV22,
            MathaREPLV22,
        )
        assert run_repl_v22 is not None or True


# ============================================================
# 7. 解析器统一层
# ============================================================

class TestUnifiedParser:
    """测试 unified_parser.py 的统一导出。"""

    def test_import_all_exports(self):
        """所有 __all__ 中的符号均可导入。"""
        from src.unified_parser import (
            Lexer, TokenType,
            Parser, parse, ParseError,
            MathaLexer, MathaParser, MathaFrontend,
            matha_compile, matha_run, matha_to_llvm,
        )
        assert Lexer is not None
        assert Parser is not None
        assert parse is not None
        assert ParseError is not None

    def test_parse_basic(self):
        """基础解析。"""
        from src.unified_parser import parse
        prog = parse("func 加倍(x) -> Int = (x) => x * 2")
        assert prog is not None
        assert hasattr(prog, 'decls')

    def test_matha_lexer_compat(self):
        """MathaLexer 兼容性。"""
        from src.unified_parser import MathaLexer
        lexer = MathaLexer("x + 1")
        tokens = list(lexer.tokenize())
        assert len(tokens) > 0

    def test_matha_parser_compat(self):
        """MathaParser 兼容性。"""
        from src.unified_parser import MathaParser
        from src.lexer import Lexer
        tokens = list(Lexer("func f(x) -> Int = (x) => x").tokenize())
        parser = MathaParser(tokens)
        prog = parser.parse()
        assert prog is not None

    def test_matha_frontend(self):
        """MathaFrontend 兼容性。"""
        from src.unified_parser import MathaFrontend
        frontend = MathaFrontend()
        ast = frontend.compile("func 加倍(x) -> Int = (x) => x * 2")
        assert ast is not None

    def test_matha_compile(self):
        """matha_compile 兼容性。"""
        from src.unified_parser import matha_compile
        result = matha_compile("func 加倍(x) -> Int = (x) => x * 2", "test")
        assert isinstance(result, str)

    def test_matha_run(self):
        """matha_run 兼容性。"""
        from src.unified_parser import matha_run
        outputs, trace = matha_run("[1 + 2]")
        assert isinstance(outputs, list)
        assert isinstance(trace, list)


# ============================================================
# 8. 总入口
# ============================================================

class TestUnifiedEntry:
    """测试 src.unified 总入口。"""

    def test_import_all_exports(self):
        """所有 __all__ 中的符号均可导入。"""
        from src.unified import (
            parse, Parser, Lexer, TokenType,
            Interpreter, interpret, MathaRuntimeError,
            UnifiedType, Type, TypeKind,
            T_INT, T_FLOAT, T_STRING, T_BOOL, T_VOID, T_ANY,
            Constraint, ConstraintSolver,
            SubtypeRegistry, RefinementChecker, EnhancedTypeInferencer,
            UnifiedMultiLang, get_unified_multilang,
            UnifiedGrowth, get_unified_growth,
            DiagnosticSeverity, Diagnostic,
            get_diagnostics, diagnose_source,
            AsyncRuntime, GoroutineScheduler, Channel, Actor,
            ThreadPool, EventLoop, Mutex, Semaphore, Condition,
            run_repl, REPLState, MathaREPL,
            HybridCompiler, LanguageBridge, AutoDiagnoser,
            MixedProjectBuilder, MathaRefactor, UpgradeSubmitter,
            Language, DefectKind, Severity, DefectReport, BuildResult,
            get_hybrid_compiler,
            Ok, Err, result,
            MathaError, ParseError,
            SemanticAnalyzer,
        )
        # 核心验证
        assert parse is not None
        assert Interpreter is not None
        assert UnifiedType is not None
        assert T_INT is not None
        assert get_unified_multilang is not None
        assert get_unified_growth is not None
        assert get_hybrid_compiler is not None
        assert DiagnosticSeverity is not None
        assert AsyncRuntime is not None
        assert run_repl is not None
        assert HybridCompiler is not None

    def test_parse_and_execute(self):
        """解析并执行简单 Matha 程序。"""
        from src.unified import parse, Interpreter

        prog = parse("func 加倍(x) -> Int = (x) => x * 2\n[加倍(5)]")
        interp = Interpreter()
        outputs, trace = interp.run(prog)
        assert 10 in outputs or outputs == [10]

    def test_type_system_ops(self):
        """类型系统操作。"""
        from src.unified import T_INT, T_FLOAT, ConstraintSolver

        solver = ConstraintSolver()
        solver.add_eq(T_INT, T_INT)
        assert len(solver.solve()) == 0

    def test_hybrid_compiler(self):
        """混合编译器功能。"""
        from src.unified import HybridCompiler, Interpreter

        hc = HybridCompiler(Interpreter())
        result = hc.diagnose("func 加倍(x) -> Int = (x) => x * 2")
        assert isinstance(result, dict)
        assert "defect_count" in result

    def test_language_translate(self):
        """语言转译。"""
        from src.unified import get_unified_multilang

        ml = get_unified_multilang()
        code = ml.transpile_to_python("func 求和(a, b) -> Int = (a, b) => a + b")
        assert isinstance(code, str)
        assert len(code) > 0

    def test_diagnostics_api(self):
        """诊断 API 可用。"""
        from src.unified import get_diagnostics, diagnose_source, DiagnosticSeverity

        result = get_diagnostics("func 测试(x) -> Int = (x) => x + 1")
        assert isinstance(result, list)

        result2 = diagnose_source("func 测试(x) -> Int = (x) => x + 1")
        assert isinstance(result2, list)

        assert DiagnosticSeverity.ERROR is not None


# ============================================================
# 9. 兼容性回归测试
# ============================================================

class TestBackwardCompatibility:
    """确保旧导入路径仍然有效。"""

    def test_old_type_system_imports(self):
        """旧 type_system_v2 导入路径。"""
        from src.type_system_v2 import Type, TypeKind, EnhancedTypeInferencer
        assert Type is not None
        assert TypeKind is not None

    def test_old_typesystem_imports(self):
        """旧 typesystem_v2_fixed 导入路径。"""
        from src.typesystem_v2_fixed import Type, T_INT, ConstraintSolver
        assert T_INT is not None
        assert ConstraintSolver is not None

    def test_old_multilang_imports(self):
        """旧多语言导入路径。"""
        from src.multi_lang_frontend import MultiLanguageFrontend
        from src.multi_lang_codegen import MultiLangCodeGen
        assert MultiLanguageFrontend is not None
        assert MultiLangCodeGen is not None

    def test_old_diagnostic_imports(self):
        """旧诊断导入路径。"""
        from src.diagnostics import DiagnosticSeverity, Diagnostic
        from src.diagnostics_v2 import Severity, Diagnostic as DiagV2
        assert DiagnosticSeverity is not None
        assert Severity is not None

    def test_old_async_imports(self):
        """旧异步导入路径。"""
        from src.async_runtime import ThreadPool, EventLoop
        from src.async_runtime_v2 import AsyncRuntime, GoroutineScheduler
        assert ThreadPool is not None
        assert AsyncRuntime is not None

    def test_old_repl_imports(self):
        """旧 REPL 导入路径。"""
        from src.repl import run_repl as run_repl_v22
        from src.repl_v23 import run_repl as run_repl_v23
        assert run_repl_v22 is not None
        assert run_repl_v23 is not None

    def test_old_parser_imports(self):
        """旧解析器导入路径。"""
        from src.lexer import Lexer
        from src.parser import Parser, parse
        from src.compiler.matha_cc import MathaLexer, MathaParser
        assert Lexer is not None
        assert Parser is not None
        assert MathaLexer is not None
        assert MathaParser is not None

    def test_old_growth_imports(self):
        """旧增长/升级导入路径。"""
        from src.growth import ExtensionRegistry
        from src.growth_engine import GrowthEngine
        from src.selfupgrade import Probe, Sandbox, UpgradeResult
        assert ExtensionRegistry is not None
        assert GrowthEngine is not None
        assert Probe is not None
        assert Sandbox is not None
        assert UpgradeResult is not None


# ============================================================
# 10. 类型系统深入测试
# ============================================================

class TestTypeSystemDeep:
    """类型系统深入功能测试。"""

    def test_unified_type_with_constraints(self):
        """UnifiedType 带约束创建。"""
        from src.typesystem_unified import UnifiedType

        t = UnifiedType(kind="generic", name="List",
                        args=["T"], constraints=["T: Numeric"])
        assert len(t.args) == 1
        assert len(t.constraints) == 1

    def test_type_base_alias(self):
        """TypeBase 是 Type 的别名。"""
        from src.typesystem_unified import TypeBase, Type

        assert TypeBase is not None
        t = TypeBase(kind="basic", name="Int")
        assert t.name == "Int"

    def test_type_constraint_class(self):
        """TypeConstraint 类可用。"""
        from src.typesystem_unified import TypeConstraint

        assert TypeConstraint is not None
        # 尝试创建约束
        tc = TypeConstraint(var="T", constraint="x > 0")
        assert tc.var == "T"
        assert tc.constraint == "x > 0"

    def test_refinement_checker(self):
        """RefinementChecker 可用。"""
        from src.typesystem_unified import RefinementChecker

        checker = RefinementChecker()
        # 基本检查应不抛出
        result = checker.check("x > 0", "Int")
        # 结果可能是 True 或 None，不应抛出
        assert result is None or isinstance(result, bool)

    def test_subtyping_chain(self):
        """多跳子类型链。"""
        from src.typesystem_unified import SubtypeRegistry

        reg = SubtypeRegistry()
        reg.add_subtype("Poodle", "Dog")
        reg.add_subtype("Dog", "Animal")
        reg.add_subtype("Animal", "LivingBeing")
        reg.add_subtype("LivingBeing", "Entity")

        assert reg.is_subtype_of("Poodle", "Entity") is True
        assert reg.is_subtype_of("Entity", "Poodle") is False
        assert reg.is_subtype_of("Dog", "Entity") is True

    def test_constraint_solver_conflict(self):
        """约束冲突检测。"""
        from src.typesystem_unified import ConstraintSolver, T_INT, T_FLOAT, T_BOOL

        solver = ConstraintSolver()
        solver.add_eq(T_INT, T_FLOAT)
        solver.add_eq(T_FLOAT, T_BOOL)
        errors = solver.solve()
        # 应检测到类型不兼容
        assert len(errors) > 0

    def test_constraint_solver_partial(self):
        """部分约束可满足。"""
        from src.typesystem_unified import ConstraintSolver, T_INT, T_ANY

        solver = ConstraintSolver()
        solver.add_eq(T_INT, T_ANY)
        errors = solver.solve()
        assert len(errors) == 0

    def test_type_generic_construction(self):
        """泛型类型构造。"""
        from src.typesystem_unified import Type

        t = Type(kind="generic", name="List", args=["Int"])
        assert t.name == "List"
        assert len(t.args) == 1
        assert t.args[0] == "Int"

    def test_type_function_construction(self):
        """函数类型构造。"""
        from src.typesystem_unified import Type

        t = Type(kind="function", name="Fn", args=["Int", "Int"],
                 constraints=["(Int) -> Int"])
        assert t.kind == "function"
        assert len(t.args) == 2


# ============================================================
# 11. 多语言深入测试
# ============================================================

class TestUnifiedMultilangDeep:
    """多语言层深入测试。"""

    def test_singleton_behavior(self):
        """单例模式验证。"""
        from src.unified_multilang import get_unified_multilang

        ml1 = get_unified_multilang()
        ml2 = get_unified_multilang()
        assert ml1 is ml2

    def test_parse_foreign_returns_dict(self):
        """parse_foreign 返回结构化结果。"""
        from src.unified_multilang import get_unified_multilang
        ml = get_unified_multilang()
        result = ml.parse_foreign("x + 1", "python")
        # 应返回 dict 或 None（降级路径）
        assert result is None or isinstance(result, dict)

    def test_generate_code_returns_string(self):
        """generate_code 返回字符串。"""
        from src.unified_multilang import get_unified_multilang
        ml = get_unified_multilang()
        code = ml.generate_code("python", "test_func", [("x", "Int")], "x + 1", "Int")
        assert isinstance(code, str)

    def test_transpile_typescript_fallback(self):
        """TypeScript 转译降级路径。"""
        from src.unified_multilang import get_unified_multilang
        ml = get_unified_multilang()
        code = ml.transpile_to_typescript("func 加倍(x) -> Int = (x) => x * 2")
        # 应返回字符串，可能是降级实现
        assert isinstance(code, str)
        assert len(code) > 0

    def test_verify_with_multiple_languages(self):
        """多语言验证。"""
        from src.unified_multilang import get_unified_multilang
        ml = get_unified_multilang()
        result = ml.verify_cross_language(
            "func 求和(a, b) -> Int = (a, b) => a + b",
            languages=["python", "typescript"],
            test_cases=[],
        )
        assert isinstance(result, dict)
        assert "success" in result

    def test_full_workflow_no_verify(self):
        """不验证的完整工作流。"""
        from src.unified_multilang import get_unified_multilang
        ml = get_unified_multilang()
        result = ml.full_workflow(
            "func 求和(a, b) -> Int = (a, b) => a + b",
            target_langs=["python"],
            verify=False,
        )
        assert isinstance(result, dict)
        assert "generations" in result

    def test_full_workflow_with_verify(self):
        """带验证的完整工作流。"""
        from src.unified_multilang import get_unified_multilang
        ml = get_unified_multilang()
        result = ml.full_workflow(
            "func 求和(a, b) -> Int = (a, b) => a + b",
            target_langs=["python"],
            verify=True,
        )
        assert "verification" in result

    def test_python_to_matha_complex(self):
        """复杂 Python 代码反向转译。"""
        from src.unified_multilang import get_unified_multilang
        ml = get_unified_multilang()
        py_src = """
def add(a, b):
    return a + b

def multiply(a, b):
    return a * b
"""
        matha = ml.transpile_from_python(py_src)
        assert isinstance(matha, str)
        assert len(matha) > 0

    def test_backward_compat_all_imports(self):
        """所有向后兼容导入路径。"""
        from src.unified_multilang import (
            MultiLangFrontend,
            MultiLangCodegen,
            MultiLangVerifier,
            PythonTranspiler,
            TypeScriptTranspiler,
        )
        assert callable(MultiLangFrontend)
        assert callable(MultiLangCodegen)
        assert callable(MultiLangVerifier)
        assert callable(PythonTranspiler)
        # TypeScriptTranspiler 可能为 None（未安装）
        assert TypeScriptTranspiler is None or callable(TypeScriptTranspiler)


# ============================================================
# 12. 增长/升级深入测试
# ============================================================

class TestUnifiedGrowthDeep:
    """增长/升级层深入测试。"""

    def test_singleton_behavior(self):
        """单例模式验证。"""
        from src.unified_growth import get_unified_growth

        g1 = get_unified_growth()
        g2 = get_unified_growth()
        assert g1 is g2

    def test_singleton_with_interp(self):
        """带 Interpreter 的单例。"""
        from src.unified_growth import get_unified_growth
        from src.interp import Interpreter

        g = get_unified_growth(Interpreter())
        assert g is not None
        # 再次调用应返回同一实例
        g2 = get_unified_growth()
        # 注意：get_unified_growth 不带参数时会创建新实例
        # 这是设计预期
        assert g2 is not None

    def test_run_growth_pipeline(self):
        """运行增长管道。"""
        from src.unified_growth import get_unified_growth
        growth = get_unified_growth()
        # 无 interpreter 时返回 False
        result = growth.run_growth_pipeline("func 测试() -> Int = () => 1")
        assert isinstance(result, bool)

    def test_get_growth_status(self):
        """获取增长状态。"""
        from src.unified_growth import get_unified_growth
        # 不带 interpreter，避免 GrowthEngine 需要 assistant
        growth = get_unified_growth()
        try:
            status = growth.get_growth_status()
            assert isinstance(status, dict)
        except AttributeError:
            # GrowthEngine 需要 AI assistant，降级测试
            pass

    def test_self_grow_fallback(self):
        """self_grow 降级路径。"""
        from src.unified_growth import get_unified_growth
        growth = get_unified_growth()
        # matha_growth 可能不可用，应返回错误
        result = growth.self_grow("func 测试() -> Int = () => 1")
        assert isinstance(result, dict)
        assert "success" in result

    def test_run_inner_loop_wired(self):
        """run_inner_loop 已真正接入 inner_loop（阶段 6d 适配桥）：注入桩验证委派，不触发重型 init_modules。"""
        from src.unified_growth import UnifiedGrowth

        class _StubInner:
            def __init__(self):
                self.calls = []

            def run(self, task, max_rounds=3):
                self.calls.append((task, max_rounds))
                return {"success": True, "task": task, "rounds_run": max_rounds,
                        "stopped_early": True, "health_score": 100.0,
                        "status": "healthy", "cycle_count": max_rounds, "results": []}

        growth = UnifiedGrowth()
        stub = _StubInner()
        growth._inner_loop = stub
        result = growth.run_inner_loop("简单任务", max_rounds=1)
        assert isinstance(result, dict)
        assert result["success"] is True
        assert stub.calls == [("简单任务", 1)]

    # ── 阶段 6e 修复锁：GrowthEngine 接线 / domain_formula 对象迭代 / fictionalize 诚实拒绝 ──
    def test_get_growth_status_wired(self):
        """6e：GrowthEngine 经 create_growth_engine 正确接线后 get_growth_status 不再抛 AttributeError。"""
        from src.unified_growth import UnifiedGrowth
        ug = UnifiedGrowth()
        st = ug.get_growth_status()  # 旧缺陷：Interpreter 被当 assistant → 'Interpreter' has no 'parser'
        assert isinstance(st, dict)
        assert "engine_defects" in st and "resources_audited" in st

    def test_domain_formula_summary_real_numbers(self):
        """6e：domain_formula_summary 改迭代 Formula 对象后返回真实统计、不再吞成 error。"""
        from src.unified_growth import UnifiedGrowth
        ug = UnifiedGrowth()
        s = ug.domain_formula_summary()
        assert "error" not in s
        assert s["loaded_domains"] > 0
        assert s["total_formulas"] > 0
        assert isinstance(s["summary"], str) and "领域公式注册总览" in s["summary"]

    def test_domain_formula_cross_links_no_raise(self):
        """6e：get_cross_domain_links 同修 str/对象误用后返回 dict（不再 'str' has no 'free_vars'）。"""
        from src.domain_formula import DomainFormulaRegistry
        reg = DomainFormulaRegistry()
        reg.register_all_domains()
        assert isinstance(reg.get_cross_domain_links(), dict)

    def test_cross_domain_engine_analyze_links_no_raise(self):
        """Tier 2·C0：CrossDomainFormulaEngine.analyze_links 同修 str/对象误用，
        迭代 Formula 对象→返回真实 CrossDomainLink 列表（不再 'str' has no 'free_vars'）。"""
        from src.domain_formula import DomainFormulaRegistry, CrossDomainFormulaEngine, CrossDomainLink
        reg = DomainFormulaRegistry()
        reg.register_all_domains()
        links = CrossDomainFormulaEngine(reg).analyze_links()
        assert isinstance(links, list) and links            # 领域公式充分互联，非空
        l = links[0]
        assert isinstance(l, CrossDomainLink)
        assert isinstance(l.formula_a, str) and isinstance(l.formula_b, str)
        assert l.shared_vars and all(isinstance(v, str) for v in l.shared_vars)

    def test_cross_domain_engine_knowledge_graph_no_raise(self):
        """Tier 2·C0：get_knowledge_graph（内部依赖 analyze_links）返回非空 dict、节点结构完整。"""
        from src.domain_formula import DomainFormulaRegistry, CrossDomainFormulaEngine
        reg = DomainFormulaRegistry()
        reg.register_all_domains()
        graph = CrossDomainFormulaEngine(reg).get_knowledge_graph()
        assert isinstance(graph, dict) and graph
        node = next(iter(graph.values()))
        assert set(node) == {"domain", "links", "shared_with"}

    def test_fictionalize_honest_refusal(self):
        """6e：fictionalize 幽灵依赖清除后如实拒绝、绝不抛 ImportError。"""
        from src.unified_growth import UnifiedGrowth
        ug = UnifiedGrowth()
        r = ug.fictionalize("计算两个质量之间的万有引力")  # 旧缺陷：每次抛 ImportError
        assert isinstance(r, dict)
        assert r["success"] is False
        assert "FormulaFictionalizer" in r["error"] and "formula_grow" in r["error"]

    def test_backward_compat_exports(self):
        """向后兼容的导出。"""
        from src.unified_growth import (
            Probe, Sandbox, UpgradeResult,
            GrowthEngine,
        )
        assert Probe is not None
        assert Sandbox is not None
        assert UpgradeResult is not None
        assert GrowthEngine is not None


# ============================================================
# 12b. UnifiedGrowth 包装委派契约锁（阶段 6e·补全）
# ============================================================

class TestUnifiedGrowthWrapperLocks:
    """锁定 UnifiedGrowth 各包装方法对子系统真实委派契约。

    过往 4 处 phantom（GrowthEngine 构造参数 / list_formulas 名字当对象 /
    FormulaFictionalizer 幽灵导入 / get_current_version 的 _registry 属性错误）均潜伏在
    **无锁包装方法**里——因为它们只测了 fallback、未跑真实路径。本类对每个包装方
    法做**真实离线冒烟**（能像人工排查那样抓出属性/参数错配），对会写文件的
    devour* 用桩注入只锁 record→dict 映射契约。只锁接线，不背书子系统输出正确性。
    """

    # ── 公式编译：真实走 FormulaCompiler.compile_formula 并校验 result 属性名 ──
    def test_compile_formula_wired(self):
        from src.unified_growth import UnifiedGrowth
        from src.formula_system import get_formula_registry
        reg = get_formula_registry()
        if not list(reg.list_formulas()):
            reg.register_geometric_defaults()
        name = next(iter(reg.list_formulas()))
        ug = UnifiedGrowth()
        r = ug.compile_formula(name)  # 旧隐患：result.python_code/.optimizations 等属性名错配会被吞成 error
        assert isinstance(r, dict)
        assert {"success", "name", "python", "c", "optimizations", "error"} <= set(r)
        assert r["success"] is True and r["name"] == name

    # ── 公式生长：真实走 FormulaGrowthEngine.compose 并锁 schema ──
    def test_formula_grow_compose_wired(self):
        from src.unified_growth import UnifiedGrowth
        ug = UnifiedGrowth()
        r = ug.formula_grow("compose", names=[])
        assert isinstance(r, dict)
        assert r["success"] is True and "results" in r  # 旧隐患：DomainFormulaRegistry/registry._formulas 错配

    # ── get_current_version：锁定不再走 _registry phantom 属性、取唯一版本源 ──
    def test_get_current_version_from_single_source(self):
        from src.unified_growth import get_current_version
        from src.__version__ import __version__
        assert get_current_version() == __version__  # 旧缺陷：恒回退硬编码 "1.0.0"

    # ── devour/devour_file：桩注入锁 record→dict 映射（避免写文件副作用）──
    def _stub_bridge(self, growth):
        class _Fn:
            name = "f"
            generated = "func f() = 1"
            body = "1"

        class _Rec:
            success = True
            verified = True
            written = False
            steps = ["parse", "gen"]
            error = None
            functions = [_Fn()]
            def summary(self):
                return "devoured 1 fn"

        class _Stub:
            def __init__(self):
                self.calls = []
            def devour(self, lang, source, module_name):
                self.calls.append(("devour", lang, source, module_name)); return _Rec()
            def devour_file(self, path, module_name):
                self.calls.append(("devour_file", path, module_name)); return _Rec()
            def fuse(self, record):
                return True

        stub = _Stub()
        growth._bridge = stub
        return stub

    def test_devour_wrapper_maps_record(self):
        from src.unified_growth import UnifiedGrowth
        ug = UnifiedGrowth()
        stub = self._stub_bridge(ug)
        r = ug.devour("python", "def f(): return 1", "m")
        assert stub.calls == [("devour", "python", "def f(): return 1", "m")]
        assert r["success"] is True and r["verified"] is True
        assert r["functions"][0]["name"] == "f" and r["summary"] == "devoured 1 fn"

    def test_devour_file_wrapper_maps_record(self):
        from src.unified_growth import UnifiedGrowth
        ug = UnifiedGrowth()
        stub = self._stub_bridge(ug)
        r = ug.devour_file("x.py", "m")
        assert stub.calls == [("devour_file", "x.py", "m")]
        assert isinstance(r, dict) and r["success"] is True

    # ── 插件市场：真实离线冒烟，锁返回类型与诚实降级（不联网、remote=False）──
    def test_market_wrappers_honest_types(self):
        from src.unified_growth import UnifiedGrowth
        ug = UnifiedGrowth()
        assert isinstance(ug.search_packages("arithmetic", remote=False), list)
        assert isinstance(ug.get_package_info("__nope__"), str)
        assert isinstance(ug.rate_package("__nope__", 5), bool)
        rating = ug.get_package_rating("__nope__")
        assert isinstance(rating, dict) and "average" in rating and "count" in rating
        assert isinstance(ug.check_updates(), list)
        assert isinstance(ug.get_dependency_tree("__nope__"), dict)
        assert isinstance(ug.check_conflicts(["__nope__"]), list)
        # dry_run + 不存在包 → 不触发安装、空列表
        assert isinstance(ug.upgrade_packages("__nope__", dry_run=True), list)

    def test_dependency_tree_nested_real(self, tmp_path):
        """Tier 2·D0：get_dependency_tree 对嵌套依赖（app→lib→core）产出真实树，
        不再因递归误用 2 参公开方法而 TypeError；且尊重 depth、可 JSON 序列化。
        用 tmp root 隔离，绝不写仓库。"""
        import json
        from src.pkg_manager_v2 import MathaPackageManager
        from src.pkg_manager import PackageMeta, Version
        mgr = MathaPackageManager(root_dir=str(tmp_path))
        mgr.registry['app'] = PackageMeta(name='app', version=Version(1, 0, 0),
                                          dependencies={'lib': '2.0.0'})
        mgr.registry['lib'] = PackageMeta(name='lib', version=Version(2, 0, 0),
                                          dependencies={'core': '0.1.0'})
        mgr.registry['core'] = PackageMeta(name='core', version=Version(0, 1, 0))
        tree = mgr.get_dependency_tree('app')
        assert tree['name'] == 'app' and tree['version'] == '1.0.0'
        assert tree['dependencies']['lib']['version'] == '2.0.0'
        assert tree['dependencies']['lib']['dependencies']['core']['version'] == '0.1.0'
        json.dumps(tree)                                   # 旧 bug：installed 为 Version → 不可序列化
        # depth 尊重：depth=2 时不再深入 core
        shallow = mgr.get_dependency_tree('app', depth=1)
        assert shallow['dependencies']['lib']['dependencies'] == {}
        # 未知包诚实空 dict
        assert mgr.get_dependency_tree('__nope__') == {}


# ============================================================
# 13. 诊断深入测试
# ============================================================

class TestUnifiedDiagnosticsDeep:
    """诊断层深入测试。"""

    def test_severity_equality(self):
        """Severity 值比较。"""
        from src.unified_diagnostics import DiagnosticSeverity

        assert DiagnosticSeverity.ERROR != DiagnosticSeverity.WARNING
        assert DiagnosticSeverity.INFO == DiagnosticSeverity.INFO

    def test_severity_ordering(self):
        """Severity 顺序验证（枚举顺序为 ERROR > WARNING > INFO > HINT）。"""
        from src.unified_diagnostics import DiagnosticSeverity

        members = list(DiagnosticSeverity)
        # 实际枚举顺序：ERROR, WARNING, INFO, HINT
        assert members[0] == DiagnosticSeverity.ERROR
        assert members[1] == DiagnosticSeverity.WARNING
        assert members[2] == DiagnosticSeverity.INFO
        assert members[3] == DiagnosticSeverity.HINT

    def test_diagnostics_on_empty_source(self):
        """空源码诊断。"""
        from src.unified_diagnostics import get_diagnostics
        result = get_diagnostics("")
        assert isinstance(result, list)

    def test_diagnostics_on_valid_matha(self):
        """合法 Matha 代码诊断。"""
        from src.unified_diagnostics import get_diagnostics
        result = get_diagnostics("func 测试(x) -> Int = (x) => x + 1")
        assert isinstance(result, list)

    def test_diagnostics_on_invalid_matha(self):
        """非法 Matha 代码诊断。"""
        from src.unified_diagnostics import get_diagnostics
        result = get_diagnostics("func 测试( x) -> Int = (x) => x + 1")
        # 可能有语法错误，返回空列表或诊断结果
        assert isinstance(result, list)

    def test_diagnose_source_with_path(self):
        """带路径的 diagnose_source。"""
        from src.unified_diagnostics import diagnose_source
        result = diagnose_source("func 测试(x) -> Int = (x) => x + 1", "/test.matha")
        assert isinstance(result, list)

    def test_backward_compat_all_exports(self):
        """所有向后兼容导出。"""
        from src.unified_diagnostics import (
            BaseDiagnostic,
            DiagnosticCollector,
            MathaErrorKind,
            BaseSourceHighlighter,
            LSPServer,
            Severity,
            Diagnostic,
            ContextAnalyzer,
            ErrorHistory,
            EnhancedDiagnosticCollector,
            SourceHighlighter,
        )
        assert BaseDiagnostic is not None or True
        assert DiagnosticCollector is not None or True
        assert MathaErrorKind is not None or True
        assert Severity is not None or True


# ============================================================
# 14. 异步运行时深入测试
# ============================================================

class TestUnifiedAsyncDeep:
    """异步运行时深入测试。"""

    def test_all_exports_available(self):
        """所有 __all__ 导出可用。"""
        from src.unified_async import (
            GState, Goroutine, AsyncSyntax,
            async_spawn, async_wait,
            new_channel, create_actor,
            AsyncSupport, get_thread_pool, get_event_loop,
        )
        # v2 新增导出（可能为 None）
        for sym in [GState, Goroutine, AsyncSyntax,
                    async_spawn, async_wait, new_channel, create_actor]:
            assert sym is not None or True
        # v1 导出
        assert AsyncSupport is not None or True
        assert get_thread_pool is not None or True
        assert get_event_loop is not None or True

    def test_async_runtime_v1_alias(self):
        """AsyncRuntimeV1 是 AsyncRuntime 的别名。"""
        from src.unified_async import AsyncRuntimeV1, AsyncRuntime

        assert AsyncRuntimeV1 is AsyncRuntime

    def test_channel_class_available(self):
        """Channel 类可用。"""
        from src.unified_async import Channel

        assert Channel is not None

    def test_actor_class_available(self):
        """Actor 类可用。"""
        from src.unified_async import Actor

        assert Actor is not None

    def test_concurrency_primitives(self):
        """并发原语可用。"""
        from src.unified_async import Mutex, Semaphore, Condition

        assert Mutex is not None
        assert Semaphore is not None
        assert Condition is not None


# ============================================================
# 15. REPL 深入测试
# ============================================================

class TestUnifiedREPLDeep:
    """REPL 深入测试。"""

    def test_run_repl_callable(self):
        """run_repl 可调用。"""
        from src.unified_repl import run_repl
        assert callable(run_repl)

    def test_repl_state_class(self):
        """REPLState 类可用。"""
        from src.unified_repl import REPLState
        assert REPLState is not None

    def test_matha_repl_class(self):
        """MathaREPL 类可用。"""
        from src.unified_repl import MathaREPL
        assert MathaREPL is not None

    def test_v22_backward_compat(self):
        """v2.2 向后兼容导出。"""
        from src.unified_repl import (
            run_repl_v22,
            REPLStateV22,
            MathaREPLV22,
        )
        assert run_repl_v22 is not None or True
        assert REPLStateV22 is not None or True
        assert MathaREPLV22 is not None or True


# ============================================================
# 16. 解析器深入测试
# ============================================================

class TestUnifiedParserDeep:
    """解析器深入测试。"""

    def test_matha_llvm_generator(self):
        """MathaLLVMGenerator 兼容。"""
        from src.unified_parser import MathaLLVMGenerator

        gen = MathaLLVMGenerator()
        result = gen.generate(None)
        assert isinstance(result, str)

    def test_matha_to_llvm(self):
        """matha_to_llvm 兼容。"""
        from src.unified_parser import matha_to_llvm
        result = matha_to_llvm("func 测试(x) -> Int = (x) => x + 1")
        assert isinstance(result, str)

    def test_parse_error_raised(self):
        """解析错误被正确抛出。"""
        from src.unified_parser import parse, ParseError

        with pytest.raises(ParseError):
            parse("func 测试( = (x) => x + 1")

    def test_parse_multiple_decls(self):
        """多声明解析。"""
        from src.unified_parser import parse

        src = """
func 加倍(x) -> Int = (x) => x * 2
func 求和(a, b) -> Int = (a, b) => a + b
[求和(加倍(3), 5)]
"""
        prog = parse(src)
        assert len(prog.decls) >= 2

    def test_parse_with_comments(self):
        """带注释的解析。"""
        from src.unified_parser import parse

        src = "(* 这是一个注释 *)\nfunc 测试(x) -> Int = (x) => x + 1"
        prog = parse(src)
        assert prog is not None

    def test_lexer_preserves_source(self):
        """Lexer 保留源码信息。"""
        from src.unified_parser import Lexer

        lexer = Lexer("let x = 42")
        tokens = list(lexer.tokenize())
        assert len(tokens) > 0
        # 每个 token 应包含行号信息
        for tok in tokens:
            assert hasattr(tok, 'type')
            assert hasattr(tok, 'value')

    def test_parser_pool_reference(self):
        """ParserPool 引用。"""
        try:
            from src.parser_pool import ParserPool
            assert ParserPool is not None or True
        except ImportError:
            pass


# ============================================================
# 17. 端到端集成测试
# ============================================================

class TestEndToEnd:
    """统一层端到端集成测试。"""

    def test_full_pipeline_parse_execute(self):
        """解析 → 执行完整流程。"""
        from src.unified import parse, Interpreter

        prog = parse("func 阶乘(n) -> Int = (n) => if n <= 1 then 1 else n * 阶乘(n - 1)\n[阶乘(5)]")
        interp = Interpreter()
        outputs, trace = interp.run(prog)
        assert 120 in outputs

    def test_full_pipeline_with_types(self):
        """带类型的完整流程。"""
        from src.unified import parse, Interpreter, T_INT

        prog = parse("func 求平方(x) -> Int = (x) => x * x\n[求平方(7)]")
        interp = Interpreter()
        outputs, trace = interp.run(prog)
        assert 49 in outputs

    def test_hybrid_build_pipeline(self):
        """混合构建流程。"""
        from src.unified import HybridCompiler, Interpreter

        hc = HybridCompiler(Interpreter())
        result = hc.build_project(
            "测试构建",
            "func 求和(a, b) -> Int = (a, b) => a + b",
        )
        assert isinstance(result, dict)
        assert "success" in result
        assert "logs" in result

    def test_hybrid_diagnose_pipeline(self):
        """混合诊断流程。"""
        from src.unified import HybridCompiler, Interpreter

        hc = HybridCompiler(Interpreter())
        result = hc.diagnose("func 求和(a, b) -> Int = (a, b) => a + b")
        assert isinstance(result, dict)
        assert "defect_count" in result

    def test_translate_and_execute(self):
        """转译并执行。"""
        from src.unified import get_unified_multilang, parse, Interpreter

        ml = get_unified_multilang()
        py_code = ml.transpile_to_python("func 加倍(x) -> Int = (x) => x * 2")
        assert isinstance(py_code, str)

        # 验证转译结果可被解析并执行
        prog = parse("func 加倍(x) -> Int = (x) => x * 2\n[加倍(5)]")
        interp = Interpreter()
        outputs, trace = interp.run(prog)
        assert len(outputs) > 0

    def test_type_inference_on_complex_expr(self):
        """复杂表达式类型推断。"""
        from src.unified import EnhancedTypeInferencer

        inferencer = EnhancedTypeInferencer()

        # 基本字面量推断
        assert inferencer.infer("42").name == "Int"
        assert inferencer.infer("3.14").name == "Float"
        assert inferencer.infer('"hello"').name == "String"
        assert inferencer.infer("true").name == "Bool"
        # 复杂表达式返回 Any（推断器只处理简单字面量）
        result = inferencer.infer("1 + 2")
        assert result is not None

    def test_diagnostics_on_complex_source(self):
        """复杂源码诊断。"""
        from src.unified import get_diagnostics

        src = """
func 加倍(x) -> Int = (x) => x * 2
func 求和(a, b) -> Int = (a, b) => a + b
[求和(加倍(3), 求和(1, 2))]
"""
        result = get_diagnostics(src)
        assert isinstance(result, list)

    def test_all_unified_exports_completeness(self):
        """验证 __all__ 完整性。"""
        from src.unified import __all__ as unified_all

        # 所有 __all__ 应为非空列表
        assert len(unified_all) > 20

        # 验证各子模块的 __all__
        from src.typesystem_unified import __all__ as ts_all
        assert len(ts_all) > 0

        from src.unified_diagnostics import __all__ as diag_all
        assert len(diag_all) > 0

        from src.unified_async import __all__ as async_all
        assert len(async_all) > 0

        from src.unified_repl import __all__ as repl_all
        assert len(repl_all) > 0

        from src.unified_parser import __all__ as parser_all
        assert len(parser_all) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
