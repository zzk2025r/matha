# -*- coding: utf-8 -*-
"""缺口修复轮：阶段 8a 登记的五项预先存在缺口真实修复的行为级三锁。

对 docs/KNOWN_ISSUES.md「阶段 8a 收官」条目登记的五缺口逐一修复并背书：
  ① interp_matha 顶层 let 绑定 env 丢失（执行声明 else 丢弃新 env）；
  ② 两自举链列表/字典字面量求值缺失（「未知表达式类型: 列表/字典」）；
  ③ mb 链内建元组形态分发缺失（注册内建 绑 ("__builtin__",名) 元组，
     应用函数/应用多参数函数 只认 Dict 形态 → parse_JSON 等「不可调用的值」）；
  ④ 构造子匹配不支持元组形态 scrutinee（type_of 无 "Tuple" 判别）；
  ⑤ match 守卫真值口径（自举 if 非0.0且非假 vs 宿主 Python truthiness）。

另修复验证中发现的同源缺陷（一并入门禁）：
  ⑥ fresh 链 func 定义参数为字符串而 应用函数 只认 Variable.名 → 用户 func
     全崩；对齐 mb 链双形态口径。mb 链闭包统一为列表形态（与 fresh 链对齐）。
  后端原语补齐：宿主/VM 增 _dict_keys/_dict_values/_dict_has/_dict_put/
  _dict_remove/_to_tuple，type_of 增 "Tuple"（原生端无元组类型，自举解释器
  不以原生为目标，登记为边界）。

三锁口径：手算对拍（宿主 ↔ mb/fresh/VM 逐值一致）/ 闭环（let→字面量→match→
func 组合）/ 显式拒绝（_to_tuple 非列表、match 无匹配、未定义变量）。
 fixture 模块级只建一次（真实加载/编译 Matha 核心模块，约数十秒）。
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.matha_bootstrap as mb
from src.interp import Interpreter, MathaRuntimeError, MathaUndefinedNameError
from src.parser import parse as py_parse
from src.mbc.compiler import Compiler
from src.mbc.vm import VM
import src.ast_nodes as ast

ROOT = Path(__file__).resolve().parents[1]


def _read_matha(rel):
    src = (ROOT / rel).read_text(encoding="utf-8")
    return src.lstrip("\ufeff") if src.startswith("\ufeff") else src


@pytest.fixture(scope="module")
def mb_boot():
    interp = mb._get_interp()
    if not getattr(interp, "_matha_loaded", False):
        pytest.skip("Matha 核心模块不可用（缺少 matha/*.matha 源文件）")
    return interp


@pytest.fixture(scope="module")
def fresh_boot():
    interp = Interpreter()
    assert interp.load_matha_module("解释器")
    assert "预绑定函数" in interp.modules["解释器"], "应为 interp.matha 版"
    return interp


@pytest.fixture(scope="module")
def interp_vm():
    comp = Compiler()
    decls = []
    for rel in ("matha/lexer.matha", "matha/stdlib.matha",
                "matha/parser.matha", "matha/interp.matha"):
        decls.extend(py_parse(_read_matha(rel)).decls)
    comp.compile_program(ast.Program(decls=decls))
    vm = VM(comp.mod)
    vm.run()
    return vm


def _run_source(interp, src):
    toks = interp.call("扫描", src, 0, 1, 1, [])
    ast_d = interp.call("parse", toks)
    mod = interp.modules["解释器"]
    env = interp._call_func_or_closure(mod["注册内建"], [[]])
    result, _ = interp._call_func_or_closure(mod["执行语句"], [ast_d, env])
    return result


def _host_value(expr_src):
    interp = Interpreter()
    interp.run(py_parse("输出(" + expr_src + ")"))
    return interp.outputs[0] if interp.outputs else None


def _call3(interp, mod, fn, *args):
    return interp._call_func_or_closure(mod[fn], list(args))


# ---------- ① 顶层 let 绑定 env 保留（手算对拍 + 闭环） ----------

_LET_CASES = [
    ("let n = 5\nn + 1", 6),
    ("let a = 2\nlet b = a + 3\nb * 2", 10),
    ("let x = 5 in x + 1", 6),
    ("let x = 3\nlet y = x * x\nlet z = y + 1\nz", 10),
]


@pytest.mark.parametrize("src,want", _LET_CASES)
def test_top_let_mb(mb_boot, src, want):
    assert _run_source(mb_boot, src) == want, src


@pytest.mark.parametrize("src,want", _LET_CASES)
def test_top_let_fresh(fresh_boot, src, want):
    assert _run_source(fresh_boot, src) == want, src


@pytest.mark.parametrize("src,want", _LET_CASES)
def test_top_let_host_parity(src, want):
    # 多行 let 是程序形态：末行表达式用 输出 取值（宿主不支持 输出(let ... 多行)）。
    if "\n" in src:
        lines = src.split("\n")
        program = "\n".join(lines[:-1] + ["输出(" + lines[-1] + ")"])
        interp = Interpreter()
        interp.run(py_parse(program))
        assert interp.outputs and interp.outputs[0] == want, src
    else:
        assert _host_value(src) == want, src


def test_top_let_undefined_still_rejected_mb(mb_boot):
    """显式拒绝：未绑定变量仍抛错（env 修复不引入静默 null）；
    39b 真化后与宿主同载体 MathaUndefinedNameError。"""
    with pytest.raises(MathaUndefinedNameError, match="未定义变量 'n'"):
        _run_source(mb_boot, "n + 1")


# ---------- ② 列表/字典字面量求值（对拍 + 闭环 + 真实类型） ----------

_LIT_CASES = [
    ("[1, 2, 3]", [1, 2, 3]),
    ("[1 + 1, 2 * 3]", [2, 6]),
    ("[[1, 2], [3]]", [[1, 2], [3]]),
    ('{"a": 1, "b": 2}', {"a": 1, "b": 2}),
    ('{"x": 2 + 3}', {"x": 5}),
    ("len([1, 2, 3])", 3),
]


@pytest.mark.parametrize("src,want", _LIT_CASES)
def test_literals_mb(mb_boot, src, want):
    assert _run_source(mb_boot, src) == want, src


@pytest.mark.parametrize("src,want", _LIT_CASES)
def test_literals_fresh(fresh_boot, src, want):
    assert _run_source(fresh_boot, src) == want, src


@pytest.mark.parametrize("src,want", _LIT_CASES)
def test_literals_host_parity(src, want):
    assert _host_value(src) == want, src


def test_dict_literal_is_real_dict_mb(mb_boot):
    """字典字面量产真实 dict，非键值对列表占位。

    mb 链未注册 type_of 内建，用等值判别：真实 dict ≠ 键值对列表，
    同内容两 dict 相等（mb 的 = 产 1.0/0.0）。
    """
    assert _run_source(mb_boot, '{"a": 1} = [["a", 1]]') == 0.0
    assert _run_source(mb_boot, '{"a": 1} = {"a": 1}') == 1.0


def test_list_literal_closed_loop_mb(mb_boot):
    """闭环：let 绑列表 → len → 与标量运算组合。"""
    assert _run_source(mb_boot, "let xs = [10, 20, 30]\nlen(xs) + 1") == 4


def test_literals_vm(interp_vm):
    """M3V VM：做ListLit/做DictLit 经 求值列表/求值字典 产真实值。"""
    env = interp_vm.call("注册内建", interp_vm.call("空环境"))
    lst = interp_vm.call("做ListLit", [interp_vm.call("做IntLit", 1),
                                       interp_vm.call("做IntLit", 2)])
    assert interp_vm.call("求值", lst, env) == [1, 2]
    dct = interp_vm.call("做DictLit", [interp_vm.call("做StringLit", "a")],
                         [interp_vm.call("做IntLit", 1)])
    assert interp_vm.call("求值", dct, env) == {"a": 1}


# ---------- ③ mb 链内建元组分发 / parse_JSON（对拍 + 显式拒绝） ----------

_BUILTIN_CASES = [
    ('ord("中")', 20013),
    ('str(42)', "42"),
    ('strip("  hi  ")', "hi"),
    ('int("7")', 7),
    ('parse_JSON("[1, 2, 3]")', [1, 2, 3]),
    # stdlib parse_JSON 为紧凑 JSON 口径（冒号后不跳空白，登记为边界）。
    ('parse_JSON("{\\"a\\":1}")', [["a", 1]]),
]


@pytest.mark.parametrize("src,want", _BUILTIN_CASES)
def test_builtin_dispatch_mb(mb_boot, src, want):
    assert _run_source(mb_boot, src) == want, src


def test_parse_json_invalid_rejected_mb(mb_boot):
    """显式拒绝：非法 JSON 不静默（stdlib parse_JSON 真实抛错）。"""
    with pytest.raises(Exception):
        _run_source(mb_boot, 'parse_JSON("{bad")')


def test_non_callable_rejected_mb(mb_boot):
    """显式拒绝：不可调用的值仍抛错（分发修复不吞错）。"""
    with pytest.raises(Exception):
        _run_source(mb_boot, "let x = 5\nx(1)")


# ---------- ④ 元组形态 scrutinee（对拍 + type_of + 显式拒绝） ----------

_TUPLE_MATCH_CASES = [
    ('match ("Some", 5) {\n| Some(x) => x + 1\n| _ => 99\n}', 6),
    ('match ("Other", 5) {\n| Some(x) => x + 1\n| _ => 99\n}', 99),
    ('match ("Some", 5, 6) {\n| Some(x) => x + 1\n| _ => 99\n}', 99),
]


@pytest.mark.parametrize("src,want", _TUPLE_MATCH_CASES)
def test_tuple_match_mb(mb_boot, src, want):
    assert _run_source(mb_boot, src) == want, src


@pytest.mark.parametrize("src,want", _TUPLE_MATCH_CASES)
def test_tuple_match_fresh(fresh_boot, src, want):
    assert _run_source(fresh_boot, src) == want, src


@pytest.mark.parametrize("src,want", _TUPLE_MATCH_CASES)
def test_tuple_match_host_parity(src, want):
    assert _host_value(src) == want, src


def test_type_of_tuple_host():
    assert _host_value("type_of((1, 2))") == "Tuple"


def test_type_of_tuple_vm(interp_vm):
    assert interp_vm.call("type_of", (1, 2)) == "Tuple"


def test_to_tuple_host():
    assert _host_value("_to_tuple([1, 2])") == (1, 2)


def test_to_tuple_rejects_non_list_host():
    with pytest.raises(MathaRuntimeError, match="需要列表"):
        _host_value("_to_tuple(5)")


def test_tuple_constructor_vm(interp_vm):
    """M3V VM：元组 scrutinee 与元组字典参数均命中构造子。"""
    env = interp_vm.call("注册内建", interp_vm.call("空环境"))
    body = interp_vm.call("做BinaryOp", "+", interp_vm.call("做Variable", "x"),
                          interp_vm.call("做IntLit", 1))
    pat = interp_vm.call("做构造子模式", "Some", [interp_vm.call("做Variable", "x")])
    branches = [[pat, None, body],
                [interp_vm.call("做Variable", "_"), None, interp_vm.call("做IntLit", 99)]]
    for value, want in ((("Some", 5), 6), ({"Some": (5,)}, 6), (("Other", 5), 99)):
        env_v = interp_vm.call("绑定环境", env, "v", value)
        m = interp_vm.call("做Match", interp_vm.call("做Variable", "v"), branches)
        assert interp_vm.call("求值", m, env_v) == want, value


def test_tuple_literal_eval_vm(interp_vm):
    """M3V VM：做元组 经 _to_tuple 产真实元组。"""
    env = interp_vm.call("注册内建", interp_vm.call("空环境"))
    t = interp_vm.call("做元组", [interp_vm.call("做IntLit", 1),
                                  interp_vm.call("做IntLit", 2)])
    assert interp_vm.call("求值", t, env) == (1, 2)


# ---------- ⑤ match 守卫真值对齐宿主（对拍） ----------

_GUARD_CASES = [
    ('match 1 {\n| _ if "" => 10\n| _ => 20\n}', 20),
    ('match 1 {\n| _ if "0" => 10\n| _ => 20\n}', 10),
    ('match 1 {\n| _ if 0 => 10\n| _ => 20\n}', 20),
    ('match 1 {\n| _ if 假 => 10\n| _ => 20\n}', 20),
    ('match 1 {\n| _ if null => 10\n| _ => 20\n}', 20),
    ('match 1 {\n| _ if 真 => 10\n| _ => 20\n}', 10),
]


@pytest.mark.parametrize("src,want", _GUARD_CASES)
def test_guard_truthiness_mb(mb_boot, src, want):
    assert _run_source(mb_boot, src) == want, src


@pytest.mark.parametrize("src,want", _GUARD_CASES)
def test_guard_truthiness_fresh(fresh_boot, src, want):
    assert _run_source(fresh_boot, src) == want, src


@pytest.mark.parametrize("src,want", _GUARD_CASES)
def test_guard_truthiness_host_parity(src, want):
    assert _host_value(src) == want, src


def test_guard_empty_container_vm(interp_vm):
    """M3V VM：空列表守卫为假（跳过），非空列表守卫为真（命中）。"""
    env = interp_vm.call("注册内建", interp_vm.call("空环境"))
    for elems, want in (([], 20), ([1], 10)):
        g = interp_vm.call("做ListLit", [interp_vm.call("做IntLit", x) for x in elems])
        brs = [[interp_vm.call("做Variable", "_"), g, interp_vm.call("做IntLit", 10)],
               [interp_vm.call("做Variable", "_"), None, interp_vm.call("做IntLit", 20)]]
        m = interp_vm.call("做Match", interp_vm.call("做IntLit", 1), brs)
        assert interp_vm.call("求值", m, env) == want, elems


def test_match_no_match_still_rejected_mb(mb_boot):
    """回归显式拒绝：无匹配分支仍抛错。"""
    with pytest.raises(MathaRuntimeError, match="match 无匹配分支"):
        _run_source(mb_boot, 'match 7 {\n| 1 => 10\n}')


# ---------- ⑥ func 参数双形态 / 柯里化闭包（对拍 + 闭环） ----------

_FUNC_CASES = [
    ("func add(x, y) -> Int = x + y\nadd(3, 4)", 7),
    ("func inc(x) -> Int = x + 1\ninc(5)", 6),
    ("let f = (x) => (y) => x + y in f(3)(4)", 7),
    ("func fact(n) -> Int = if n <= 1 then 1 else n * fact(n - 1)\nfact(5)", 120),
]


@pytest.mark.parametrize("src,want", _FUNC_CASES)
def test_func_defs_mb(mb_boot, src, want):
    assert _run_source(mb_boot, src) == want, src


@pytest.mark.parametrize("src,want", _FUNC_CASES)
def test_func_defs_fresh(fresh_boot, src, want):
    assert _run_source(fresh_boot, src) == want, src


def test_func_literal_match_closed_loop_mb(mb_boot):
    """闭环：func + 列表字面量 + match 元组构造子组合（端到端）。"""
    src = ("func unwrap(v) -> Int = match v {\n"
           "  | Some(x) => x + 1\n"
           "  | _ => 0\n"
           "}\n"
           'unwrap(("Some", 41))')
    assert _run_source(mb_boot, src) == 42


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "-s"]))