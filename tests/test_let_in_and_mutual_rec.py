# -*- coding: utf-8 -*-
"""`let … in` 体边界 与 顶层同级多个 `let rec` 的回归测试。

覆盖两处前端/编译器缺陷：

1. `_parse_let` 在解析完绑定值后把 `_in_let_value` 无条件置 False，
   嵌套 let 会清掉外层的「in 是边界」标记，导致
   `let f = (x) => let y = 1 in x + y in 输出(f(5))` 中的外层 `in`
   被当作 Python 成员运算符，生成 `BINOP 'in'` 并把 `输出(f(5))`
   错误编进 lambda 内部（main 只剩 HALT）。
   同构问题另见 `func` / `and` 顶层 lambda 体分支（漏设 _in_let_value）
   与 `_parse_let_tuple`。

2. `_emit_let` 的 `let rec` 分支无条件申请局部槽并发射
   MAKE_BOX/STORE_BOX，但 main 帧没有局部槽数组，越界抛 IndexError。
   同级第二个及后续 `let rec` 必然触发（互递归场景）。
"""
import pytest

from src import ast_nodes as ast
from src.mbc.compiler import compile_source
from src.mbc.vm import run_source

输出 = chr(0x8F93) + chr(0x51FA)


def _vm(src: str) -> list:
    return [str(v) for v in run_source(src)]


def _parse(src: str) -> ast.Program:
    from src.parser import parse
    return parse(src)


# ---------- 1. let 体边界：外层 in 不得被当作二元运算符 ----------

def test_outer_in_terminates_lambda_body_with_inner_let():
    """`let f = lambda(let y = … in …) in REST`：外层 in 是 let 边界。

    回归时外层 in 被解析成 BinaryOp('in', x+y, 输出(f(5)))，
    且输出调用被编进 __lam_1 内部，main_code 近乎为空。
    """
    prog = _parse(f"let f = (x) => let y = 10 in x + y in\n{输出}(f(5))\n")
    outer = prog.decls[0]
    assert isinstance(outer, ast.LetBinding)
    # 外层 let 必须有 body（承接 in 之后的表达式）
    assert outer.body is not None, "外层 let 的 body（in 之后部分）丢失"
    # 绑定值内不得出现 op='in' 的二元运算
    assert not _has_in_binop(outer.value), \
        f"lambda 体把 in 误当成员运算符：{outer.value!r}"
    # 顶层 body 应为对 f 的调用
    assert _is_call(outer.body), \
        f"外层 body 应为输出调用，实际 {type(outer.body).__name__}: {outer.body!r}"


def _has_in_binop(node) -> bool:
    """递归查找 op == 'in' 的 BinaryOp（项目 AST 非 stdlib 子类，用 vars 遍历）。"""
    if isinstance(node, ast.BinaryOp) and getattr(node, "op", None) == "in":
        return True
    for val in vars(node).values():
        if isinstance(val, (list, tuple)):
            for item in val:
                if hasattr(item, "__dict__") and _has_in_binop(item):
                    return True
        elif hasattr(val, "__dict__") and _has_in_binop(val):
            return True
    return False


def _is_call(node) -> bool:
    return isinstance(node, ast.FuncApp)


def test_lambda_body_keeps_no_in_binop_letrec():
    """`let rec` 形态同样正确。"""
    prog = _parse(f"let rec f = (x) => let y = 10 in x + y in\n{输出}(f(5))\n")
    outer = prog.decls[0]
    assert isinstance(outer, ast.LetBinding)
    assert outer.body is not None
    assert not _has_in_binop(outer.value)


def test_func_lambda_body_terminates_at_in():
    """`func` 顶层 lambda 体后跟 in：体不得吞掉 in 之后部分。

    回归时 func 的 lambda 体未设 _in_let_value，in 被吞成
    BinaryOp('in', x+y, 输出(f(5)))，main 只剩 HALT。
    """
    src = f"func f(x: Int) -> Int = (x) => let y = 10 in x + y in\n{输出}(f(5))\n"
    mm = compile_source(src)
    for name, fn in mm.functions.items():
        assert not any(ins[0] == 0x40 and mm.constants[ins[1]] == "in"
                       for ins in fn.code if len(ins) > 1 and isinstance(ins[1], int)), \
            f"函数 {name} 中残留 BINOP 'in'"


def test_nested_let_chain_terminates_each_level():
    """多层 let 各自正确消费自己的 in。"""
    src = (f"let g = 1 in let f = (x) => let y = 2 in x+y in"
           f" let h = 3 in {输出}(f(5) + g + h)\n")
    assert _vm(src) == ["11"]


def test_three_level_lambda_let_chain():
    """lambda 体内连续 let 绑定。"""
    src = f"let f = (x) => let y = 1 in let z = 2 in x+y+z in {输出}(f(10))\n"
    assert _vm(src) == ["13"]


# ---------- in 作为成员运算符的语义不得回归 ----------

@pytest.mark.parametrize("src,want", [
    ("let a = 3 in %s(a in [1,2,3])\n" % 输出, ["True"]),
    ("let s = [1,2,3] in %s(2 in s)\n" % 输出, ["True"]),
    ("let c = 1 in let d = 2 in %s(c + d)\n" % 输出, ["3"]),
    ("let x = 41 in %s(x + 1)\n" % 输出, ["42"]),
])
def test_in_still_works_as_membership_operator(src, want):
    """`in` 作为二元运算符仍然生效（修复只改边界判定，不改运算符语义）。"""
    assert _vm(src) == want


def test_in_still_usable_as_parameter_name():
    """`in` 作为参数名（关键字白名单）不受影响。"""
    src = f"func f(in: Int) -> Int = in * 2\n{输出}(f(21))\n"
    assert _vm(src) == ["42"]


def test_let_body_in_operator_precedence_preserved():
    """let body 内的成员运算保持优先级：`(a in b) and c`。"""
    src = f"let a = 2 in let s = [1,2,3] in {输出}((a in s) and (3 in s))\n"
    assert _vm(src) == ["True"]


# ---------- 2. 顶层同级多个 let rec ----------

def test_two_sibling_let_rec_no_index_error():
    """同级两个 let rec 不再越界访问 locals。"""
    src = f"let rec a = (n) => n in\nlet rec b = (n) => n in\n{输出}(a(1) + b(2))\n"
    assert _vm(src) == ["3"]


def test_mutual_recursion_even_odd():
    src = (f"let rec even = (n) => if n == 0 then true else odd(n-1) in\n"
           f"let rec odd = (n) => if n == 0 then false else even(n-1) in\n"
           f"{输出}(even(4))\n{输出}(odd(4))\n{输出}(even(5))\n")
    assert _vm(src) == ["True", "False", "False"]


def test_mutual_recursion_pair():
    src = (f"let rec e = (n) => if n <= 1 then n else o(n-1) in\n"
           f"let rec o = (n) => if n <= 1 then n else e(n-1) in\n"
           f"{输出}(e(6))\n{输出}(o(7))\n")
    assert _vm(src) == ["1", "1"]


def test_three_sibling_let_rec():
    src = (f"let rec a = (n) => if n == 0 then 1 else b(n-1) in\n"
           f"let rec b = (n) => if n == 0 then 2 else a(n-1) in\n"
           f"let rec c = (n) => if n == 0 then 3 else a(n) in\n"
           f"{输出}(a(4))\n{输出}(b(4))\n{输出}(c(0))\n")
    assert _vm(src) == ["1", "2", "3"]


def test_single_let_rec_still_uses_box_in_nested_scope():
    """非 main 作用域内的 let rec 仍用 Box（共享可变状态语义不变）。"""
    src = (f"func outer(k: Int) -> Int = (k) =>\n"
           f"    let rec f = (n) => if n <= 0 then 0 else f(n-1) in\n"
           f"    f(k)\n{输出}(outer(3))\n")
    assert _vm(src) == ["0"]


def test_main_let_rec_emits_store_global_not_make_box():
    """main 作用域的 let rec 退化为 STORE_GLOBAL，不再发 MAKE_BOX。"""
    mm = compile_source(f"let rec f = (n) => if n <= 1 then 1 else n * f(n-1) in\n"
                        f"{输出}(f(5))\n")
    main = mm.main_code
    assert (0x13, 0) not in main and (0x13, 1) not in main, \
        f"main 中不应出现 MAKE_BOX：{main}"
    assert any(ins[0] == 0x18 for ins in main), \
        f"main 中应出现 STORE_GLOBAL(0x18)：{main}"
