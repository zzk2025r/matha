"""生态能力测试：验证 Matha 构建专属生态所需的四大语言支柱。

覆盖：
  1. 模块系统（module / use）
  2. 类型定义（struct / enum / type）
  3. 函数定义（func ... -> Type = (params) => body）
  4. 并发原语（go）

运行：python -m tests.test_ecosystem
"""

from src.parser import parse, ParseError
from src.semantic import analyze_source
from src import ast_nodes as ast


def _check(label: str, source: str, expect_decls=None, expect_errors=0):
    """解析 + 语义分析，断言声明类型与错误数。"""
    print(f"\n--- {label} ---")
    program = parse(source)
    decl_types = [type(d).__name__ for d in program.decls]
    _, errors = analyze_source(source, verbose=False)
    err_n = sum(1 for e in errors if e.severity == "error")
    print(f"  声明: {decl_types}  error={err_n}")
    assert err_n == expect_errors, f"{label}: 期望 {expect_errors} 个错误，实际 {err_n}"
    if expect_decls is not None:
        assert decl_types == expect_decls, f"{label}: 期望 {expect_decls}，实际 {decl_types}"
    print(f"  ✓ {label} 通过")
    return program


def test_module_decl():
    """模块声明：module Name { ... }"""
    _check(
        "模块声明",
        "module 生态 {\n  #1：[1]\n}",
        expect_decls=["ModuleDecl"],
    )


def test_import_decl():
    """导入声明：use Module { member | member }"""
    _check(
        "导入声明",
        "use 生态 { add | 显示器 }",
    )


def test_func_def():
    """函数定义：func add(x: Int, y: Int) -> Int = (x, y) => x + y"""
    prog = _check(
        "函数定义",
        "func add(x: Int, y: Int) -> Int = (x, y) => x + y",
        expect_decls=["FuncDef"],
    )
    fn = prog.decls[0]
    assert fn.name == "add"
    print(f"  ✓ 函数名={fn.name}, 参数数={len(fn.body.params)}")


def test_struct_def():
    """结构体定义：struct 显示器 { 字段... }"""
    prog = _check(
        "结构体定义",
        "struct 显示器 {\n  尺寸: Int\n  分辨率: String\n}",
        expect_decls=["StructDef"],
    )
    st = prog.decls[0]
    assert st.name == "显示器"
    assert len(st.fields) == 2
    print(f"  ✓ 结构体={st.name}, 字段数={len(st.fields)}")


def test_enum_def():
    """枚举定义：enum 颜色 { 红 | 绿 | 蓝 }"""
    prog = _check(
        "枚举定义",
        "enum 颜色 { 红 | 绿 | 蓝 }",
        expect_decls=["EnumDef"],
    )
    assert prog.decls[0].name == "颜色"
    print(f"  ✓ 枚举={prog.decls[0].name}")


def test_type_alias():
    """类型别名：type ID = Int"""
    _check(
        "类型别名",
        "type ID = Int",
        expect_decls=["AliasDef"],
    )


def test_module_func_call():
    """综合：模块 + 函数 + 导入 + 调用"""
    _check(
        "模块+函数+调用",
        "module 数学 {\n  func double(n: Int) -> Int = (n) => n * 2\n}\n"
        "use 数学 { double }\n#1：[double(5)]",
    )


def test_concurrency_go():
    """并发原语：#1：go 任务"""
    prog = _check(
        "并发 go",
        "#1：go 任务",
        expect_decls=["MechUnit"],
    )
    unit = prog.decls[0]
    assert isinstance(unit.body, ast.GenStmt)
    assert isinstance(unit.body.content, ast.GoStmt)
    print(f"  ✓ GoStmt.expr={type(unit.body.content.expr).__name__}")


def test_go_in_code_block():
    """代码块内裸 go 语句"""
    _check(
        "代码块内 go",
        "#：{\n  go 任务\n}",
    )


def test_go_func_call():
    """go 启动函数调用：go doWork(args)"""
    _check(
        "go 函数调用",
        "func doWork(n: Int) -> Int = (n) => n\n#1：go doWork(5)",
    )


def _run_all():
    tests = [
        test_module_decl,
        test_import_decl,
        test_func_def,
        test_struct_def,
        test_enum_def,
        test_type_alias,
        test_module_func_call,
        test_concurrency_go,
        test_go_in_code_block,
        test_go_func_call,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except (AssertionError, ParseError, Exception) as ex:
            failed += 1
            print(f"  ✗ {t.__name__} 失败: {type(ex).__name__}: {ex}")
    print(f"\n{'='*40}")
    print(f"生态能力测试：{passed} 通过, {failed} 失败 (共 {len(tests)})")
    return failed == 0


if __name__ == "__main__":
    import sys
    sys.exit(0 if _run_all() else 1)
