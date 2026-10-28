# -*- coding: utf-8 -*-
"""A3：三元 / or 语境里 == / != 的优先级回归锁。

历史缺口（docs/ast_vm_gap.md 第九节）：语句位的比较运算符 == / !=
右操作数误用 _parse_expr，会贪心吞掉后续三元，使

    r = 3 == 3 ? 100 : 200

被解析成 r = 3 == (3 ? 100 : 200)（运行得 False），而非
    r = (3 == 3) ? 100 : 200（应得 100）。

> < >= <= 与 lambda 体内的比较本就正确（右操作数用 _parse_set_expr），
本测试锁定 == / != 也与之同口径，防止重新引入。
"""
from __future__ import annotations

import src.ast_nodes as ast
from src.kernel import exec_api
from src.parser import parse


def _outputs(src: str) -> list:
    outs, err = exec_api.run_checked(src, mode="vm")
    assert err is None, f"VM 运行报错：{err}"
    return list(outs)


def _binding_value(src: str):
    tree = parse(src)
    binds = [d for d in tree.decls if isinstance(d, ast.Binding)]
    assert binds, "未解析出 Binding"
    return binds[0].value


# ---- AST 结构：== 的比较对象是 cond，而非被三元吞进右操作数 ----

def test_eq_thenary_parses_comparison_as_cond():
    val = _binding_value("r = 3 == 3 ? 100 : 200")
    assert isinstance(val, ast.IfExpr), f"应为 IfExpr，实得 {type(val).__name__}"
    assert isinstance(val.cond, ast.BinaryOp) and val.cond.op == "==", \
        "IfExpr.cond 应为 == 比较"
    assert isinstance(val.then, ast.IntegerLit) and val.then.value == 100
    assert isinstance(val.else_, ast.IntegerLit) and val.else_.value == 200


def test_neq_ternary_parses_comparison_as_cond():
    val = _binding_value("r = 3 != 5 ? 100 : 200")
    assert isinstance(val, ast.IfExpr), f"应为 IfExpr，实得 {type(val).__name__}"
    assert isinstance(val.cond, ast.BinaryOp) and val.cond.op == "!=", \
        "IfExpr.cond 应为 != 比较"


# ---- 运行值：与解释器（遗留后端）同口径 ----

def test_eq_ternary_true_branch():
    assert _outputs("r = 3 == 3 ? 100 : 200\n[r]") == [100]


def test_eq_ternary_false_branch():
    assert _outputs("r = 3 == 5 ? 100 : 200\n[r]") == [200]


def test_neq_ternary():
    assert _outputs("r = 4 != 3 ? 7 : 9\n[r]") == [7]


def test_eq_ternary_inside_or_context():
    # or 左假 → 取右侧三元；右侧 (2 == 2) ? 5 : 6 应得 5，而非 2 == (2 ? 5 : 6)
    assert _outputs("r = 0 or (2 == 2 ? 5 : 6)\n[r]") == [5]


def test_assignment_rhs_ternary_still_works():
    # 单等号赋值：右值仍应能整体纳入三元（回归保护，不得被改坏）
    assert _outputs("m = 3 > 2 ? 100 : 200\n[m]") == [100]
