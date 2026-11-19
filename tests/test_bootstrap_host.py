# -*- coding: utf-8 -*-
"""Matha 宿主自举路径测试（src/matha_bootstrap.py）。

覆盖历史遗留缺陷：
  - 加载 `interp_matha.matha` 时的 `未定义函数 'MathaRuntimeError'`：
    自举解释器以 `raise MathaRuntimeError(msg)` 抛错，宿主须注册同名内建。
  - 宿主加载模块时误执行顶层 `#：{ }` 自测块（递归运行自举解释器 → 报错/挂死）：
    加载只应执行 ModuleDecl，跳过自测 MechUnit。
  - `run_ast` 是 Matha 闭包元组（不可直接调用）：
    宿主须经 `_call_func_or_closure` 应用，否则静默回退 Python 解释器。

注：本文件会真实加载全部 Matha 核心模块（约数秒），故用模块级 fixture 只加载一次。
"""
import sys
import os

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.matha_bootstrap as mb
from src.interp import MathaRuntimeError, Interpreter


@pytest.fixture(scope="module")
def boot():
    interp = mb._get_interp()
    if not getattr(interp, "_matha_loaded", False):
        pytest.skip("Matha 核心模块不可用（缺少 matha/*.matha 源文件）")
    return interp


def test_bootstrap_loads_core_modules(boot):
    """自举模块可完整加载（含 interp_matha + bootstrap_matha）。"""
    assert boot._matha_loaded is True
    for mod in ("词法器", "语法器", "标准库", "解释器", "自举加载器"):
        assert mod in boot.modules, f"缺少模块 {mod}"
    print("  ✓ 核心模块全部加载")


def test_bootstrap_run_ast_is_callable_closure(boot):
    """run_ast 是闭包元组，须可经 _call_func_or_closure 应用。"""
    run_ast = boot.modules["自举加载器"]["run_ast"]
    assert isinstance(run_ast, tuple) and run_ast[0] == "__closure__", run_ast
    print("  ✓ run_ast 为闭包元组")


def test_bootstrap_interpret_arithmetic(boot):
    """自举解释器执行算术表达式（29d 输出列表语义统一）。

    mb.interpret 返回 输出 语句行（与宿主/VM 面同口径）——顶层裸表达式
    不再回显；算术能力经 输出() 通道断言，strict=True 关闭静默回退，
    证明由自举解释器真实执行。
    """
    out, _ = mb.interpret("输出(3 + 5)", strict=True)
    assert out == [8], out
    out, _ = mb.interpret("输出(2 * (3 + 4))", strict=True)
    assert out == [14], out
    print("  ✓ 自举解释 输出(3+5)→[8] / 输出(2*(3+4))→[14]")


def test_bootstrap_interpret_custom_op(boot):
    """自举解释器执行自定义运算符（@define_op 绑定具名函数，f(l)(r) 两参调用）。

    自举面可执行用户函数与自定义算子（@define_op 求值分支早已落地，见
    CHANGELOG「用户自定义运算符：原生端 + 自托管端可用」节）；旧 docstring
    「无法执行用户函数 / 静默回退产生 [6]」为过时措辞，本轮勘误。29d 输出
    列表语义统一——经 输出() 通道断言取值，strict=True 不静默回退。
    """
    out, _ = mb.interpret(
        "func 孪加(a: Int, b: Int) -> Int = (a, b) => a + b + 1\n"
        "@define_op: ∝ = 5 | left => 孪加\n"
        "输出(2 ∝ 3)\n", strict=True)
    assert out == [6], out
    print("  ✓ 自举解释自定义运算符 输出(2 ∝ 3) → [6]")


def test_bootstrap_interpret_empty(boot):
    """空输入：无 输出 语句 → 诚实空列表（29d 输出列表语义统一）。

    旧 [None] 末语句值回显随输出列表口径退役（宿主/VM/自举三面同形）。
    """
    out, _ = mb.interpret("", strict=True)
    assert out == [], out
    print("  ✓ 空输入 → 诚实 []")


def test_bootstrap_syntax_error_is_reported(boot):
    """语法错误以消息返回，不崩溃、不挂死。"""
    out, trace = mb.interpret("1 +")
    assert out and isinstance(out[0], str) and "语法" in out[0], out
    print("  ✓ 语法错误优雅返回")


def test_bootstrap_undefined_variable_raises(boot):
    """未定义变量经自举求值抛 MathaRuntimeError（宿主/自举语义对齐）。"""
    with pytest.raises(MathaRuntimeError):
        mb.interpret("x + 1")
    print("  ✓ 未定义变量 → MathaRuntimeError")


def test_matha_runtime_error_builtin_registered():
    """宿主内建表含 MathaRuntimeError，调用即抛同名异常。"""
    b = Interpreter().builtins
    assert "MathaRuntimeError" in b
    with pytest.raises(MathaRuntimeError):
        b["MathaRuntimeError"]("测试消息")
    print("  ✓ MathaRuntimeError 内建注册且抛出")


def test_bootstrap_test_matha_parses_losslessly():
    """`matha/bootstrap_test.matha` 须被宿主 parser **无损**解析。

    历史缺陷：多语句 then/else 分支会被静默丢弃（`else` 分支整体丢失），
    使该文件"解析通过"但 AST 严重残缺。此处守护 `断言` 函数体含完整
    `else` 分支且分支为 let-in 结构（惯用式重写后的形态）。
    """
    from src.parser import parse
    from src import ast_nodes as ast

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "matha", "bootstrap_test.matha")
    if not os.path.exists(path):
        pytest.skip("缺少 matha/bootstrap_test.matha")
    with open(path, encoding="utf-8") as f:
        prog = parse(f.read())
    md = prog.decls[0]
    assert isinstance(md, ast.ModuleDecl), type(md)
    fds = [d for d in md.decls if isinstance(d, ast.FuncDef)]
    assert_fd = next(f for f in fds if f.name == "断言")
    body = assert_fd.body.body
    assert isinstance(body, ast.IfExpr), type(body)
    assert body.else_ is not None, "断言 else 分支被丢弃"
    assert isinstance(body.then, ast.LetBinding), type(body.then)
    assert isinstance(body.else_, ast.LetBinding), type(body.else_)
    print("  ✓ bootstrap_test.matha 无损解析（含 else 分支）")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "-s"]))