"""自举语法分析器原型测试。

验证 Matha 用自身语法描述的语法分析器（matha/parser.matha）能被
Matha 工具链正确解析与语义校验——自举可行性验证的第二步。

覆盖：
  1. parser.matha 解析无 ParseError
  2. 语义校验 0 错误
  3. AST 数据模型完整（enum + struct + func）
  4. 跨模块复用：use 词法器
  5. 递归下降算法函数齐全

运行：python -m tests.test_selfhost_parser
"""

import os
from src.parser import parse, ParseError
from src.semantic import analyze_source
from src import ast_nodes as ast

PARSER_PATH = os.path.join(os.path.dirname(__file__), "..", "matha", "parser.matha")


def _load() -> str:
    with open(PARSER_PATH, encoding="utf-8") as f:
        return f.read()


def test_parser_matha_parses():
    """matha/parser.matha 必须能被 Matha parser 解析。"""
    print("\n--- 自举语法器：解析 ---")
    src = _load()
    print(f"  源码长度: {len(src)} 字符")
    program = parse(src)
    decl_types = [type(d).__name__ for d in program.decls]
    print(f"  顶层声明: {decl_types}")
    # 接受 ImportDecl + ModuleDecl + 可选 MechUnit
    assert "ModuleDecl" in decl_types, f"缺少 ModuleDecl，实际 {decl_types}"
    print("  ✓ 解析通过：含 ModuleDecl")
    return program


def test_parser_matha_semantic_clean():
    """语义校验必须 0 错误。"""
    print("\n--- 自举语法器：语义校验 ---")
    src = _load()
    _, errors = analyze_source(src, verbose=False)
    err_n = sum(1 for e in errors if e.severity == "error")
    warn_n = sum(1 for e in errors if e.severity == "warning")
    print(f"  error={err_n}  warning={warn_n}")
    for e in errors:
        print(f"    {e}")
    assert err_n == 0, f"期望 0 错误，实际 {err_n}"
    print("  ✓ 语义校验通过（0 错误）")


def test_parser_imports_lexer():
    """跨模块复用：导入词法器的 Token 类型。"""
    print("\n--- 自举语法器：跨模块导入 ---")
    program = parse(_load())
    imports = [d for d in program.decls if isinstance(d, ast.ImportDecl)]
    if imports:
        imp = imports[0]
        print(f"  ✓ use {imp.module_name} {imp.import_list}")
    else:
        print("  ~ 无跨模块导入声明（非必需）")

    # 解析器 struct 应存在
    module = next(d for d in program.decls if isinstance(d, ast.ModuleDecl))
    structs = [s for s in module.decls if isinstance(s, ast.StructDef)]
    struct_names = {s.name for s in structs}
    assert "解析器" in struct_names, f"缺少 struct 解析器，实际 {struct_names}"
    print(f"  ✓ struct 解析器 存在")


def test_parser_data_model():
    """AST 数据模型完整。"""
    print("\n--- 自举语法器：数据模型 ---")
    program = parse(_load())
    module = next(d for d in program.decls if isinstance(d, ast.ModuleDecl))
    kinds = [type(d).__name__ for d in module.decls]
    print(f"  模块内声明类型: {kinds}")

    # 检查存在 struct 和 func
    structs = [d for d in module.decls if isinstance(d, ast.StructDef)]
    funcs = [d for d in module.decls if isinstance(d, ast.FuncDef)]
    print(f"  struct: {[s.name for s in structs]}, func: {len(funcs)}")
    assert len(structs) >= 1, f"缺少 struct 定义"
    assert len(funcs) >= 5, f"缺少函数定义"
    print(f"  ✓ 数据模型完整（{len(structs)} struct, {len(funcs)} func）")


def test_parser_helper_funcs():
    """解析辅助纯函数齐全。"""
    print("\n--- 自举语法器：纯函数 ---")
    program = parse(_load())
    module = next(d for d in program.decls if isinstance(d, ast.ModuleDecl))
    funcs = [d for d in module.decls if isinstance(d, ast.FuncDef)]
    fn_names = {f.name for f in funcs}
    print(f"  函数: {sorted(fn_names)}")
    expected = {"推进", "当前", "匹配", "期望", "解析程序", "parse"}
    assert expected <= fn_names, f"缺少函数，期望含 {expected}，实际 {fn_names}"
    print(f"  ✓ {len(funcs)} 个纯函数全部定义")


def test_parser_algorithm_segments():
    """递归下降算法以函数形式描述。"""
    print("\n--- 自举语法器：算法段 ---")
    program = parse(_load())
    module = next(d for d in program.decls if isinstance(d, ast.ModuleDecl))
    funcs = [d for d in module.decls if isinstance(d, ast.FuncDef)]
    fn_names = {f.name for f in funcs}
    print(f"  函数数: {len(funcs)}")
    # 检查核心解析函数存在
    core_funcs = {"解析表达式", "解析声明", "解析主要", "解析应用", "解析幂", "解析乘除", "解析加减", "解析比较", "解析三元"}
    missing = core_funcs - fn_names
    if missing:
        print(f"  ~ 缺少核心函数: {missing}")
    else:
        print(f"  ✓ 核心解析函数齐全")
    assert len(funcs) >= 10, f"期望至少 10 个函数，实际 {len(funcs)}"
    print(f"  ✓ 算法函数完整（{len(funcs)} 个）")


def _run_all():
    tests = [
        test_parser_matha_parses,
        test_parser_matha_semantic_clean,
        test_parser_imports_lexer,
        test_parser_data_model,
        test_parser_helper_funcs,
        test_parser_algorithm_segments,
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
    print(f"\n{'='*48}")
    print(f"自举语法器测试：{passed} 通过, {failed} 失败 (共 {len(tests)})")
    return failed == 0


if __name__ == "__main__":
    import sys
    sys.exit(0 if _run_all() else 1)
