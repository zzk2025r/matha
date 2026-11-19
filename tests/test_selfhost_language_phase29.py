# -*- coding: utf-8 -*-
"""阶段 29b 自举链语言级缺陷真化锁（七项双面/三面判定）。

29b 七项自举链语言级缺陷的真化与宿主对齐，逐项最小源锁（探针移植）：

  ① 语句位下标赋值（0x64 STORE_SUBSCRIPT）：容器/下标/右值栈序原位写入，
     双编译器字节码对拍 + 双执行面语义（变量容器/字典键/嵌套下标）；
  ② lambda 立即调用/链式（宿主 parser 语句位 Binding 消解特例）：
     六形态双执行面 + 分组非 lambda 诚实报错；
  ③ 函数式 let `->` 可选（宿主 3472 简写分支双端同源；显式 lambda 特例仅限
     带箭头形态，参数走 _parse_lambda_param 类型标注可选）：A-H 八形态三面；
  ④ MBC VM 字典缺失键 → null（对齐 host dict.get / native dict_get，
     vm.py INDEX_GET 29b-④；vm.matha 取下标经宿主解释器基底传递对齐）；
  ⑤ vm.matha 查全局 文案对齐宿主 MathaUndefinedNameError「未定义变量 '<名>'」
     （宿主 VM 面 / stdlib+vm.matha joined 直调面 / 运行M3V 全链面）；
  ⑥ lambda/func 块体语句位 `name = <右值>` 回退式歧义消解——右值（解析集合层）
     后紧跟关系运算符时回退按赋值全量解析（原双端「期望表达式 (got OP_GT)」）；
     右值后为 `?` 的语料惯用式（desktop.matha `动 = "启动" ? … : …`）保持
     比较语义零扰动。新合法形态暴露预存自举编译器分歧：块尾 输出/输出追踪
     是宿主 _VALUE_STMTS（_emit_if_try_value → expr+DUP+OUTPUT，块值=输出值），
     自举原走语句+PUSH_NULL（块值=null）——_发射块末条 特例 _发射块末输出
     真化（空输出仍语句+PUSH_NULL），C1-C7 双执行面 + 双编译器字节码对齐；
  ⑦ break/continue 自举编译器发射（JMP 收口）：九形态字节码对拍 + 双执行面
     语义 + 循环外诚实报错。

登记不修（27c 勘误候选，29f 登记）：lambda 表达式体 `op = "+" ? a : b` 折损
形态双端分歧（host is_assign → BinaryOp("=", op, IfExpr)；自举比较链 →
IfExpr(cond=BinaryOp("=", op, "+"))）——语料零命中，本文件不锁。
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.set_int_max_str_digits(0)

from pathlib import Path

from src.parser import parse as py_parse
from src.mbc.compiler import Compiler, MModule, MFunction
from src.mbc.vm import VM
from src import ast_nodes as ast
from src.kernel import exec_api
from src import matha_bootstrap
from src import interp as host_interp

_ROOT = Path(__file__).resolve().parent.parent
_COMP_FILES = ["matha/lexer.matha", "matha/stdlib.matha", "matha/parser.matha",
               "matha/interp.matha", "matha/compiler_matha.matha"]


def _strip_bom(src):
    return src.lstrip("\ufeff") if src and src[0] == "\ufeff" else src


def dict_to_module(d):
    mod = MModule(module_name=d.get("模块名", "主程序"))
    mod.constants = list(d["常量"])
    mod.main_code = [tuple(x) for x in d["主码"]]
    for entry in d["函数"]:
        name, info = entry[0], entry[1]
        mod.functions[name] = MFunction(
            name, info["元数"], info["局部数"],
            [tuple(x) for x in info["码"]], list(info["参数"]))
    return mod


def _canon_code(mod):
    """指令码逐位（28c _canon 的码子集：main + 全函数码）。"""
    if isinstance(mod, MModule):
        return {"main": [tuple(i) for i in mod.main_code],
                "fns": {n: [tuple(i) for i in f.code]
                        for n, f in mod.functions.items()}}
    return {"main": [tuple(i) for i in mod["主码"]],
            "fns": {e[0]: [tuple(i) for i in e[1]["码"]] for e in mod["函数"]}}


@pytest.fixture(scope="module")
def bvm():
    """五文件自举编译器 VM（lexer+stdlib+parser+interp+compiler_matha）。"""
    comp = Compiler()
    decls = []
    for rel in _COMP_FILES:
        decls.extend(py_parse(_strip_bom(
            (_ROOT / rel).read_text(encoding="utf-8"))).decls)
    comp.compile_program(ast.Program(decls=decls))
    vm = VM(comp.mod)
    vm.run()
    return vm


@pytest.fixture(scope="module")
def vvm():
    """stdlib + vm.matha joined VM（stage4 _JOINED_VM_FILES 同构，⑤ 专用）。"""
    comp = Compiler()
    src = ((_ROOT / "matha/stdlib.matha").read_text(encoding="utf-8") + "\n"
           + (_ROOT / "matha/vm.matha").read_text(encoding="utf-8"))
    comp.compile_program(ast.Program(decls=py_parse(_strip_bom(src)).decls))
    vm = VM(comp.mod)
    vm.run()
    return vm


def _stage2(src):
    return Compiler().compile_program(py_parse(_strip_bom(src)))


def _stage3(bvm, src):
    return dict_to_module(bvm.call("编译", _strip_bom(src)))


def _vm_outputs(mod):
    m = VM(mod)
    m.run()
    return m.outputs


def _boot_interp(src):
    """自举解释器面：返回 (outs, trace, exc)——预期报错形态需查 exc。

    strict=True：boot 面异常如实上抛，不静默降级 Python 解释器
    （29d 假成功通道关闭——此前 boot 缺陷被宿主面成功掩盖可致假绿）。"""
    try:
        outs, trace = matha_bootstrap.interpret(src, strict=True)
        return outs, trace, None
    except Exception as e:  # noqa: BLE001
        return [], [], e


def _assert_parity(bvm, src):
    assert _canon_code(_stage3(bvm, src)) == _canon_code(_stage2(src)), src


# ============================================================
# ① 语句位下标赋值（0x64 STORE_SUBSCRIPT）
# ============================================================

_SUB_CASES = [
    ("var_list", "甲 = [1, 2, 3]\n甲[0] = 9\n输出(甲)", [[9, 2, 3]]),
    ("dict_key", 'm = {"a": 1}\nm["b"] = 2\n输出(m["b"])', [2]),
    ("nested", "g = [[1]]\ng[0][0] = 5\n输出(g[0][0])", [5]),
]


def test_29b01_subscript_assign_semantics():
    for tag, src, want in _SUB_CASES:
        outs, err = exec_api.run_checked(src)
        assert err is None and outs == want, (tag, outs, err)
        b_outs, b_trace, b_exc = _boot_interp(src)
        assert b_exc is None and b_outs == want, (tag, b_outs, b_exc)


def test_29b01_subscript_assign_parity(bvm):
    for tag, src, _ in _SUB_CASES:
        _assert_parity(bvm, src)


# ============================================================
# ② lambda 立即调用/链式
# ============================================================

_IMM_CALL_CASES = [
    ("imm", "输出(((x) => x * 2)(21))", [42]),
    ("chain", "输出(((x) => (y) => x + y)(1)(2))", [3]),
    ("local_chain", "输出(((a, b) => a + b)(1)(2))", [3]),
    ("named_chain", "f = (a) => (b) => a + b\n输出(f(1)(2))", [3]),
    ("subscript_call", "表 = [(x) => x + 21]\n输出(表[0](21))", [42]),
    ("curry_first_lambda", "应用 = (f) => (x) => f(x)\n输出(应用((v) => v * 3)(5))", [15]),
]


def test_29b02_lambda_immediate_call():
    for tag, src, want in _IMM_CALL_CASES:
        outs, err = exec_api.run_checked(src)
        assert err is None and outs == want, (tag, outs, err)
        b_outs, b_trace, b_exc = _boot_interp(src)
        assert b_exc is None and b_outs == want, (tag, b_outs, b_exc)


def test_29b02_grouped_nonlambda_honest_error():
    """分组非 lambda：`(1 + 2)(3)` 双执行面均诚实报错，不假成功。"""
    outs, err = exec_api.run_checked("输出((1 + 2)(3))")
    assert err is not None, outs
    b_outs, b_trace, b_exc = _boot_interp("输出((1 + 2)(3))")
    assert b_exc is not None, b_outs


# ============================================================
# ③ 函数式 let `->` 可选
# ============================================================

_LET_ARROW_CASES = [
    # A: 带 -> 完整形态（回归：修复前后都应绿）
    ("A_with_arrow", "let rec f(n: Int) -> Int = if n <= 1 then 1 else n * f(n - 1) in 输出(f(5))", ["120"]),
    # B: 无 -> rec 简写（宿主 3471 简写分支）
    ("B_no_arrow_rec", "let rec f(n: Int) = if n <= 1 then 1 else n * f(n - 1) in 输出(f(5))", ["120"]),
    # C: 无 -> 带类型非递归简写
    ("C_no_arrow_typed", "let g(x: Int) = x * 2 in 输出(g(21))", ["42"]),
    # D: 无 -> 无类型标注简写
    ("D_no_type", "let h(x) = x + 1 in 输出(h(41))", ["42"]),
    # E: 无 -> 显式 lambda 体（宿主 params 保留 → 柯里化）
    ("E_no_arrow_lambda", "let f(x) = (y) => x + y in 输出(f(1)(2))", ["3"]),
    # G: 无 -> 带类型显式 lambda 体（宿主显式 lambda 参数位走 _parse_lambda_param）
    ("G_typed_lambda", "let f(x: Int) = (y: Int) => x + y in 输出(f(1)(2))", ["3"]),
]
_LET_ARROW_ERR_CASES = [
    # F/H: 带 -> 显式 lambda 体（特例仅带箭头形态；双端一致报 x 未定义——
    # 显式 lambda 体不捕获签名参数，值侧 lambda 只有自己的参数）
    ("F_arrow_lambda", "let f(x: Int) -> Int = (y) => x + y in 输出(f(1)(2))", "未定义变量 'x'"),
    ("H_arrow_typed_lambda", "let f(x: Int) -> Int = (y: Int) => x + y in 输出(f(1)(2))", "未定义变量 'x'"),
]


def test_29b03_let_arrow_valid():
    for tag, src, want in _LET_ARROW_CASES:
        outs, err = exec_api.run_checked(src)
        assert err is None and [str(o) for o in outs] == want, (tag, outs, err)
        b_outs, b_trace, b_exc = _boot_interp(src)
        assert b_exc is None and [str(o) for o in b_outs] == want, (tag, b_outs, b_exc)


def test_29b03_let_arrow_error_both_faces():
    for tag, src, msg in _LET_ARROW_ERR_CASES:
        outs, err = exec_api.run_checked(src)
        assert err is not None and msg in str(err), (tag, err)
        b_outs, b_trace, b_exc = _boot_interp(src)
        joined = " ".join(str(o) for o in b_outs) + " " + str(b_exc)
        assert b_exc is not None or any(msg in str(t) for t in b_outs), (tag, b_outs, b_exc)
        assert msg in joined or b_exc is not None, (tag, b_outs, b_exc)


def test_29b03_let_arrow_parity(bvm):
    for tag, src, _ in _LET_ARROW_CASES + _LET_ARROW_ERR_CASES:
        _assert_parity(bvm, src)


# ============================================================
# ④ MBC VM 字典缺失键 → null
# ============================================================

def test_29b04_vm_missing_dict_key_null():
    """VM INDEX_GET 字典缺失键 → null（对齐 host interp dict.get 同语义）。"""
    src = 'd = {"a": 1}\n输出(d["缺键"])'
    outs, err = exec_api.run_checked(src)
    assert err is None and outs == [None], (outs, err)
    i_outs, i_trace = host_interp.interpret(src)
    assert i_outs == [None], (i_outs, i_trace)
    # 已存在键不受影响；列表越界维持原诚实报错面（不在本锁范围）
    outs2, err2 = exec_api.run_checked('d = {"a": 1}\n输出(d["a"])')
    assert err2 is None and outs2 == [1], (outs2, err2)


# ============================================================
# ⑤ vm.matha 查全局 文案对齐
# ============================================================

def test_29b05_undef_host_face():
    outs, err = exec_api.run_checked("输出(不存在)")
    assert err is not None and "未定义变量 '不存在'" in str(err), (outs, err)


def test_29b05_undef_vmmath_faces(vvm):
    assert vvm.call("查全局", [["a", 1]], "a") == 1
    with pytest.raises(Exception) as ei:
        vvm.call("查全局", [], "x")
    assert "未定义变量 'x'" in str(ei.value)
    # 运行M3V 全链面：读全局=23，常量 0 = "x"，首条即抛
    d = {"模块名": "主", "常量": ["x"], "主码": [[23, 0]], "函数": []}
    with pytest.raises(Exception) as ei2:
        vvm.call("运行M3V", d)
    assert "未定义变量 'x'" in str(ei2.value)


# ============================================================
# ⑥ 块体语句位条件赋值（回退式歧义消解）
# ============================================================

_BLOCK_CASES = [
    ("C1_func_block_ternary",
     "func f() -> Int =\n{\n  r = 1 > 0 ? 10 : 20\n  [r]\n}\n输出(f())\n", ["10", "10"]),
    ("C2_func_block_else",
     "func f(n: Int) -> Int =\n{\n  r = n > 5 ? 100 : 200\n  [r]\n}\n输出(f(1))\n输出(f(9))\n",
     ["200", "200", "100", "100"]),
    ("C3_nested_if_block",
     "func f(n: Int) -> Int =\n{\n  r = 0\n  if n > 0 {\n    r = n > 5 ? 1 : 2\n  }\n  [r]\n}\n输出(f(9))\n输出(f(1))\n",
     ["1", "1", "2", "2"]),
    ("C4_lambda_block",
     "g = (n) => { r = n > 0 ? 7 : 8\n[r] }\n输出(g(1))\n输出(g(0))\n", ["7", "7", "8", "8"]),
    ("C5_block_eqcmp",
     "func f(n: Int) -> Int =\n{\n  r = 0\n  if n == 5 {\n    r = 1\n  }\n  [r]\n}\n输出(f(5))\n输出(f(4))\n",
     ["1", "1", "0", "0"]),
    ("C6_block_plain",
     "func f() -> Int =\n{\n  r = 42\n  [r]\n}\n输出(f())\n", ["42", "42"]),
    ("C7_while_block",
     "func f() -> Int =\n{\n  i = 0\n  acc = 0\n  while i < 3 {\n    acc = acc + (i > 1 ? 10 : 1)\n    i = i + 1\n  }\n  [acc]\n}\n输出(f())\n",
     ["12", "12"]),
]


def test_29b06_block_ternary_semantics():
    for tag, src, want in _BLOCK_CASES:
        outs, err = exec_api.run_checked(src)
        assert err is None and [str(o) for o in outs] == want, (tag, outs, err)
        b_outs, b_trace, b_exc = _boot_interp(src)
        assert b_exc is None and [str(o) for o in b_outs] == want, (tag, b_outs, b_exc)


def test_29b06_block_ternary_parity(bvm):
    for tag, src, _ in _BLOCK_CASES:
        _assert_parity(bvm, src)


# ============================================================
# ⑦ break/continue 自举发射
# ============================================================

_BREAK_CASES = {
    "while_break": ('while 真 {\n  break\n}\n#1：["after"]', ["after"]),
    "while_continue": ('i = 0\nacc = []\nwhile i < 5 {\n  i = i + 1\n'
                       '  if i % 2 == 0 {\n    continue\n  }\n'
                       '  acc = acc + [i]\n}\n#1：[acc]', [[1, 3, 5]]),
    "for_break": ('acc = []\nfor x in [1, 2, 3, 4] {\n  if x == 3 {\n    break\n  }\n'
                  '  acc = acc + [x]\n}\n#1：[acc]', [[1, 2]]),
    "for_continue": ('acc = []\nfor x in [1, 2, 3, 4, 5] {\n  if x % 2 == 0 {\n    continue\n  }\n'
                     '  acc = acc + [x]\n}\n#1：[acc]', [[1, 3, 5]]),
    "nested_break_inner": ('acc = []\ni = 0\nwhile i < 3 {\n  i = i + 1\n  j = 0\n'
                           '  while j < 5 {\n    j = j + 1\n    if j == 2 {\n      break\n    }\n'
                           '    acc = acc + [j]\n  }\n}\n#1：[acc]', [[1, 1, 1]]),
    "for_mixed": ('acc = []\nfor x in [1, 2, 3, 4, 5] {\n  if x == 2 {\n    continue\n  }\n'
                  '  if x == 4 {\n    break\n  }\n  acc = acc + [x]\n}\n#1：[acc]', [[1, 3]]),
    "fn_while_break": ('func 计数(n: Int) -> Int = (n) => {\n  i = 0\n  while 真 {\n'
                       '    i = i + 1\n    if i >= n {\n      break\n    }\n  }\n  i\n}\n'
                       '#1：[计数(5)]', [5]),
    "fn_for_break": ('func 首奇(xs: List) -> Int = (xs) => {\n  r = -1\n  for x in xs {\n'
                     '    if x % 2 == 1 {\n      r = x\n      break\n    }\n  }\n  r\n}\n'
                     '#1：[首奇([2, 4, 7, 9])]', [7]),
    "break_fn_last_stmt": ('func 摸底(xs: List) -> Int = (xs) => {\n  i = 0\n'
                           '  while i < len(xs) {\n    if xs[i] == 9 {\n      break\n    }\n'
                           '    i = i + 1\n  }\n  i\n}\n#1：[摸底([1, 9, 3])]', [1]),
}


def test_29b07_break_continue_parity_and_semantics(bvm):
    for tag, (src, want) in _BREAK_CASES.items():
        _assert_parity(bvm, src)
        o3 = _vm_outputs(_stage3(bvm, src))
        o2 = _vm_outputs(_stage2(src))
        assert o3 == o2 == want, (tag, o3, o2, want)


def test_29b07_break_outside_loop_honest_error(bvm):
    """循环外 break：双端编译器均诚实报错，不假成功。"""
    with pytest.raises(Exception):
        bvm.call("编译", "break")
    with pytest.raises(Exception):
        _stage2("break")
