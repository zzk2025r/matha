"""自举词法器原型测试。

验证 Matha 用自身语法描述的词法器（matha/lexer.matha）能被
Matha 工具链（parser + semantic）正确解析与语义校验——
这是「Matha 能否自举」可行性验证的第一步。

运行：python -m tests.test_selfhost_lexer
"""

import os
from src.parser import parse, ParseError
from src.semantic import analyze_source
from src import ast_nodes as ast

LEXER_PATH = os.path.join(os.path.dirname(__file__), "..", "matha", "lexer.matha")


def _load() -> str:
    with open(LEXER_PATH, encoding="utf-8") as f:
        return f.read()


def test_lexer_matha_parses():
    """matha/lexer.matha 必须能被 Matha parser 解析（无 ParseError）。"""
    print("\n--- 自举词法器：解析 ---")
    src = _load()
    print(f"  源码长度: {len(src)} 字符")
    program = parse(src)
    decl_types = [type(d).__name__ for d in program.decls]
    print(f"  顶层声明: {decl_types}")
    # 接受 ModuleDecl + 可选 MechUnit（自测块）
    assert "ModuleDecl" in decl_types, f"缺少 ModuleDecl，实际 {decl_types}"
    print("  ✓ 解析通过，含 ModuleDecl")
    return program


def test_lexer_matha_semantic_clean():
    """matha/lexer.matha 语义校验必须 0 错误。"""
    print("\n--- 自举词法器：语义校验 ---")
    src = _load()
    _, errors = analyze_source(src, verbose=False)
    err_n = sum(1 for e in errors if e.severity == "error")
    warn_n = sum(1 for e in errors if e.severity == "warning")
    print(f"  error={err_n}  warning={warn_n}")
    for e in errors:
        print(f"    {e}")
    assert err_n == 0, f"期望 0 错误，实际 {err_n}"
    print("  ✓ 语义校验通过（0 错误）")


def test_lexer_data_model():
    """词法器数据模型完整：enum 类型 + struct Token + struct 游标。"""
    print("\n--- 自举词法器：数据模型 ---")
    program = parse(_load())
    module = next(d for d in program.decls if isinstance(d, ast.ModuleDecl))
    kinds = [type(d).__name__ for d in module.decls]
    print(f"  模块内声明类型: {kinds}")

    # enum 类型
    enums = [d for d in module.decls if isinstance(d, ast.EnumDef)]
    assert len(enums) >= 1, f"缺少 enum，实际 {kinds}"
    enum_types = [e.name for e in enums]
    print(f"  ✓ enum: {enum_types}")

    # struct Token / 游标
    structs = [d for d in module.decls if isinstance(d, ast.StructDef)]
    struct_names = {s.name for s in structs}
    assert "Token" in struct_names, f"缺少 struct Token，实际 {struct_names}"
    token = next(s for s in structs if s.name == "Token")
    assert len(token.fields) == 4, f"struct Token 期望 4 字段，实际 {len(token.fields)}"
    print(f"  ✓ struct Token ({len(token.fields)} 字段)")
    if "游标" in struct_names:
        print(f"  ✓ struct 游标")


def test_lexer_helper_funcs():
    """词法器核心函数齐全。"""
    print("\n--- 自举词法器：纯函数 ---")
    program = parse(_load())
    module = next(d for d in program.decls if isinstance(d, ast.ModuleDecl))
    funcs = [d for d in module.decls if isinstance(d, ast.FuncDef)]
    fn_names = {f.name for f in funcs}
    print(f"  函数: {sorted(fn_names)}")
    expected = {"扫描", "tokenize", "做Token", "是字母码", "是数字码", "是换行码", "是空白码", "是标识符续"}
    assert expected <= fn_names, f"缺少函数，期望含 {expected}，实际 {fn_names}"
    print(f"  ✓ {len(funcs)} 个纯函数全部定义")


def test_lexer_algorithm_segments():
    """词法算法包含必要的纯函数实现。"""
    print("\n--- 自举词法器：算法段 ---")
    program = parse(_load())
    module = next(d for d in program.decls if isinstance(d, ast.ModuleDecl))
    mechs = [d for d in module.decls if isinstance(d, ast.MechUnit)]
    funcs = [d for d in module.decls if isinstance(d, ast.FuncDef)]
    print(f"  机械段数: {len(mechs)}, 函数数: {len(funcs)}")
    assert len(funcs) >= 10, f"期望至少 10 个函数，实际 {len(funcs)}"
    print(f"  ✓ 函数实现完整（{len(funcs)} 个）")


def _run_all():
    tests = [
        test_lexer_matha_parses,
        test_lexer_matha_semantic_clean,
        test_lexer_data_model,
        test_lexer_helper_funcs,
        test_lexer_algorithm_segments,
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
    print(f"自举词法器测试：{passed} 通过, {failed} 失败 (共 {len(tests)})")
    return failed == 0


if __name__ == "__main__":
    import sys
    sys.exit(0 if _run_all() else 1)
