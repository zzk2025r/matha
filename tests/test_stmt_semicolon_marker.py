# -*- coding: utf-8 -*-
"""语句终止（分号）与文件尾标记修复测试。

覆盖（均为历史遗留缺陷的回归）：
  - 同行 `;` 分隔的多条绑定须解析为多条独立语句，而非「表达式序列取末段」：
      `x = 1; y = 2` 曾解析为 `x = (y = 2)`（丢弃 `x = 1`），运行时报 `未定义变量 'y'`。
  - `#：【文件】`（文件尾标记）是结构性标记，求值须为空操作，
      曾抛 `MathaRuntimeError: 暂不支持求值: FileMarker`。
  - if/then/else 分支的「分号表达式序列取末段」语义（_parse_semicolon_exprs）须保留。
"""
import sys
sys.path.insert(0, r'D:\trae')

from src.parser import parse
from src.interp import interpret
from src import ast_nodes as ast


def _get_out(src: str):
    out, _ = interpret(src)
    return out[-1] if out else None


# ─── 分号：同行语句分隔 ──────────────────────────────────────────────────────

def test_parser_splits_semicolon_bindings():
    """解析层：`x = 1; y = 2` → 两条 Binding（而非一条 x = y = 2）。"""
    prog = parse('x = 1; y = 2')
    assert len(prog.decls) == 2, [type(d).__name__ for d in prog.decls]
    assert all(isinstance(d, ast.Binding) for d in prog.decls)
    assert prog.decls[0].target.name == 'x'
    assert prog.decls[1].target.name == 'y'
    assert isinstance(prog.decls[0].value, ast.IntegerLit)
    assert prog.decls[0].value.value == 1
    assert isinstance(prog.decls[1].value, ast.IntegerLit)
    assert prog.decls[1].value.value == 2
    print('  ✓ x = 1; y = 2 → 两条 Binding')


def test_semicolon_bindings_execute_independently():
    """运行层：同行绑定各自生效，可相互引用。"""
    assert _get_out('x = 1; y = 2\n输出({ x + y })') == 3
    print('  ✓ 同行绑定运行时各自生效 → 3')


def test_semicolon_string_bindings():
    """原始用例：name/rootUri 同行绑定（旧版报 未定义变量 'rootUri'）。"""
    out, _ = interpret('#：{ name = "a"; rootUri = "b"\n [name, rootUri] }')
    assert out == [['a', 'b']], out
    print('  ✓ #：{ name=..; rootUri=.. } → [["a", "b"]]')


def test_semicolon_three_bindings_and_expr():
    """多段分号：绑定 + 末尾表达式。"""
    assert _get_out('a = 1; b = 2; c = a + b\n输出({ c })') == 3
    print('  ✓ a=1; b=2; c=a+b → 3')


def test_if_branch_semicolon_sequence_preserved():
    """回归保护：if/then/else 分支的分号序列取末段语义不得被破坏。"""
    assert _get_out('输出({ if true then 10; 20 else 30 })') == 20
    assert _get_out('输出({ if false then 10; 20 else 30 })') == 30
    print('  ✓ if/then/else 分号序列取末段（→20 / →30）')


# ─── 文件尾标记：#：【文件】 ─────────────────────────────────────────────────

def test_file_marker_toplevel_is_noop():
    """顶层 `#：【文件】` 求值不得抛错。"""
    out, _ = interpret('#：【文件】')
    assert out == [], out
    print('  ✓ 顶层 #：【文件】 空操作')


def test_file_marker_in_code_block_is_noop():
    """代码块内 `#：【文件】` 不得中断求值。"""
    out, _ = interpret('#：{\n x = 1\n #：【文件】\n [x]\n}')
    assert out == [1], out
    print('  ✓ 代码块内 #：【文件】 空操作')


def test_file_marker_with_semicolon_bindings():
    """文件尾标记与同行绑定共存。"""
    out, _ = interpret('#：{\n name = "a"; rootUri = "b"\n #：【文件】\n [name, rootUri]\n}')
    assert out == [['a', 'b']], out
    print('  ✓ 文件尾标记 + 同行绑定共存')


def test_file_marker_parse_type():
    """解析层：代码块内 `#：【文件】` → FileMarker（is_end_marker=True）。"""
    prog = parse('#：{ x = 1\n #：【文件】\n [x] }')
    mech = prog.decls[0]
    body = getattr(mech, 'body', None)
    assert isinstance(body, ast.CodeBlock), type(body).__name__
    markers = [s for s in body.stmts if isinstance(s, ast.FileMarker)]
    assert len(markers) == 1, [type(s).__name__ for s in body.stmts]
    assert markers[0].is_end_marker is True
    print('  ✓ 解析为 FileMarker')


if __name__ == '__main__':
    for _name, _fn in sorted(globals().items()):
        if _name.startswith('test_') and callable(_fn):
            _fn()
    print('全部通过')