# -*- coding: utf-8 -*-
"""M3V 自举闭环测试：Matha 词法器 + 语法器 + 解释器（编译为字节码）在 VM 上运行，
完成「Matha 源码 → token → AST → 求值」全流程——编译基础设施自举的关键里程碑。

验证要点：
  - lexer.matha / stdlib.matha / parser.matha / interp.matha 可共同编译为字节码
  - VM 上 Matha tokenize 产出正确 token（类型/文本/行列）
  - VM 上 Matha parse 产出正确 AST（运算符优先级、带类型标注函数定义等）
  - VM 上 Matha 求值 能正确求值算术/三元/变量/Lambda/函数应用
  - and/or 短路语义在字节码层正确（数字/空白判定依赖）
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.set_int_max_str_digits(0)
# 注意：不要在此提高 sys.setrecursionlimit——VM 使用显式帧栈，深递归不占
# Python C 栈；过高的递归限制会把其他模块的 RecursionError 放大成 C 栈崩溃。

from pathlib import Path

from src.parser import parse as py_parse
from src.mbc.compiler import Compiler, MModule, MFunction
from src.mbc.vm import VM
from src import ast_nodes as ast

_ROOT = Path(__file__).resolve().parent.parent
_BOOT_FILES = ["matha/lexer.matha", "matha/stdlib.matha", "matha/parser.matha"]
_FULL_BOOT_FILES = _BOOT_FILES + ["matha/interp.matha"]
_COMPILER_BOOT_FILES = _FULL_BOOT_FILES + ["matha/compiler_matha.matha"]


def dict_to_module(d):
    """自举编译器产物 dict → 宿主 MModule（指令 list 转 tuple，结构等价）。"""
    mod = MModule(module_name=d.get("模块名", "主程序"))
    mod.constants = list(d["常量"])
    mod.main_code = [tuple(x) for x in d["主码"]]
    for entry in d["函数"]:
        name, info = entry[0], entry[1]
        mod.functions[name] = MFunction(
            name, info["元数"], info["局部数"],
            [tuple(x) for x in info["码"]], list(info["参数"]))
    return mod


def compile_and_run(compiler_boot_vm, src, calls=()):
    """自举编译 src → dict → 真实宿主 VM 执行；calls 为 (函数名, 参数元组) 序列。"""
    d = compiler_boot_vm.call("编译", src)
    vm = VM(dict_to_module(d))
    vm.run()
    return [vm.call(name, *args) for name, args in calls], vm


def _compile_files(rels):
    """多文件自举编译：合并所有文件的顶层声明为单一 Program 再编译。

    关键：不能逐文件 compile_program——每次调用都会追加一条 HALT，
    vm.run() 在第一条 HALT 处即停止，后续文件的模块级 let 永不执行。
    """
    comp = Compiler()
    decls = []
    for rel in rels:
        src = (_ROOT / rel).read_text(encoding="utf-8")
        if src and src[0] == "\ufeff":
            src = src.lstrip("\ufeff")
        decls.extend(py_parse(src).decls)
    comp.compile_program(ast.Program(decls=decls))
    return comp


@pytest.fixture(scope="module")
def boot_vm():
    comp = _compile_files(_BOOT_FILES)
    vm = VM(comp.mod)
    vm.run()
    return vm


@pytest.fixture(scope="module")
def full_boot_vm():
    """加载全部自举模块（lexer + stdlib + parser + interp），验证可编译为字节码并在 VM 上运行。"""
    comp = _compile_files(_FULL_BOOT_FILES)
    vm = VM(comp.mod)
    vm.run()
    return vm


@pytest.fixture(scope="module")
def compiler_boot_vm():
    """全量自举（含 compiler_matha）：lexer + stdlib + parser + interp + 编译器。"""
    comp = _compile_files(_COMPILER_BOOT_FILES)
    vm = VM(comp.mod)
    vm.run()
    return vm


def _parse_on_vm(vm, code):
    toks = vm.call("tokenize", code)
    tree = vm.call("parse", toks)
    return toks, tree


# ---------- 词法器 ----------

def test_lexer_tokens(boot_vm):
    toks = boot_vm.call("tokenize", "1 + 2 * 3")
    pairs = [(t["类型"], t["文本"]) for t in toks]
    assert pairs == [
        ("整数", "1"), ("加", "+"), ("整数", "2"),
        ("乘", "*"), ("整数", "3"), ("结束", ""),
    ]


def test_lexer_skips_whitespace_and_classifies_identifiers(boot_vm):
    toks = boot_vm.call("tokenize", "func add(a: Int) -> Int")
    types = [t["类型"] for t in toks]
    assert types[0] == "关键字" and types[0] is not None
    assert types[1] == "标识符"
    assert types[-1] == "结束"
    # 空白不得产出 token
    assert all(t["文本"] != " " for t in toks)


# ---------- 语法器：表达式与优先级 ----------

def test_parse_arith_precedence(boot_vm):
    _, tree = _parse_on_vm(boot_vm, "1 + 2 * 3")
    assert tree["类型"] == "程序"
    decls = tree["声明"]
    assert len(decls) == 1
    expr = decls[0]
    assert expr["类型"] == "二元运算"
    assert expr["运算符"] == "+"
    # 乘法应绑定更紧：右孩子是 2 * 3
    assert expr["右"]["类型"] == "二元运算"
    assert expr["右"]["运算符"] == "*"
    assert expr["左"]["值"] == 1


def test_parse_let_binding(boot_vm):
    _, tree = _parse_on_vm(boot_vm, "let x = 42")
    decls = tree["声明"]
    assert len(decls) == 1


# ---------- 语法器：带参数类型标注的函数定义 ----------

def test_parse_func_def_with_typed_params(boot_vm):
    _, tree = _parse_on_vm(
        boot_vm, "func add(a: Int, b: Int) -> Int = (a, b) => a + b"
    )
    decls = tree["声明"]
    assert len(decls) == 1
    fn = decls[0]
    assert fn["类型"] == "函数定义"
    assert fn.get("名") == "add" or fn.get("名称") == "add"


def test_parse_func_def_with_if_expr_body(boot_vm):
    _, tree = _parse_on_vm(
        boot_vm, "func f(x: Int) -> Int = (x) => if x > 0 then x else 0 - x"
    )
    decls = tree["声明"]
    assert len(decls) == 1
    assert decls[0]["类型"] == "函数定义"


# ---------- 字节码语义：and/or 短路 ----------

def test_short_circuit_and_or():
    from src.mbc import compile_source, run_module
    # 若 and/or 不短路，右侧 get("x")(99) 越界取值会直接抛 IndexError
    outs = run_module(compile_source(
        'result = (1 > 2) and (get("x")(99) = "y")\n#1：[result]'))
    assert outs[-1] is False

    outs = run_module(compile_source(
        'result = (1 < 2) or (get("x")(99) = "y")\n#1：[result]'))
    assert outs[-1] is True


# ---------- 解释器自举：VM 上 Matha 求值 ----------

def test_interp_arith(full_boot_vm):
    """VM 上 Matha 解释器正确求值算术表达式。"""
    env = full_boot_vm.call("注册内建", full_boot_vm.call("空环境"))
    expr = full_boot_vm.call("做BinaryOp", "+",
                             full_boot_vm.call("做IntLit", 3),
                             full_boot_vm.call("做IntLit", 5))
    assert full_boot_vm.call("求值", expr, env) == 8

    inner = full_boot_vm.call("做BinaryOp", "+",
                              full_boot_vm.call("做IntLit", 3),
                              full_boot_vm.call("做IntLit", 4))
    expr2 = full_boot_vm.call("做BinaryOp", "*",
                              full_boot_vm.call("做IntLit", 2), inner)
    assert full_boot_vm.call("求值", expr2, env) == 14


def test_interp_ternary(full_boot_vm):
    """VM 上 Matha 解释器正确求值三元条件表达式。"""
    env = full_boot_vm.call("注册内建", full_boot_vm.call("空环境"))
    cond = full_boot_vm.call("做BinaryOp", ">",
                             full_boot_vm.call("做IntLit", 1),
                             full_boot_vm.call("做IntLit", 2))
    expr = full_boot_vm.call("做If", cond,
                             full_boot_vm.call("做IntLit", 100),
                             full_boot_vm.call("做IntLit", 200))
    assert full_boot_vm.call("求值", expr, env) == 200


def test_interp_variable(full_boot_vm):
    """VM 上 Matha 解释器正确处理变量绑定与查找。"""
    env = full_boot_vm.call("注册内建", full_boot_vm.call("空环境"))
    env2 = full_boot_vm.call("绑定环境", env, "x", 10)
    expr = full_boot_vm.call("做Variable", "x")
    assert full_boot_vm.call("求值", expr, env2) == 10


def test_interp_lambda(full_boot_vm):
    """VM 上 Matha 解释器正确处理 Lambda 闭包与函数应用。"""
    env = full_boot_vm.call("注册内建", full_boot_vm.call("空环境"))
    lam = full_boot_vm.call("做Lambda",
                            [full_boot_vm.call("做Variable", "x")],
                            full_boot_vm.call("做BinaryOp", "+",
                                              full_boot_vm.call("做Variable", "x"),
                                              full_boot_vm.call("做IntLit", 1)))
    closure = full_boot_vm.call("求值", lam, env)
    env2 = full_boot_vm.call("绑定环境", env, "加一", closure)
    expr = full_boot_vm.call("做FuncApp",
                             full_boot_vm.call("做Variable", "加一"),
                             full_boot_vm.call("做IntLit", 5))
    assert full_boot_vm.call("求值", expr, env2) == 6


# ---------- M3：try/catch/raise（自举层） ----------

def _run_interp_src(vm, src):
    """VM 上 tokenize → parse → 执行语句列表，返回 (值, 环境)。"""
    env = vm.call("注册内建", vm.call("空环境"))
    toks = vm.call("tokenize", src)
    tree = vm.call("parse", toks)
    return vm.call("执行语句列表", tree, env)


def test_interp_try_normal(full_boot_vm):
    """自举层 try 体正常完成：值为 try 体尾表达式。"""
    v, _ = _run_interp_src(full_boot_vm, "try { 40 + 2 } catch (e) { 0 }")
    assert v == 42


def test_interp_try_catch_raise(full_boot_vm):
    """自举层 raise 抛出的消息被 catch 变量捕获。"""
    v, _ = _run_interp_src(full_boot_vm, 'try { raise "boom" } catch (e) { e }')
    assert v == "boom"


def test_interp_try_catch_runtime_error(full_boot_vm):
    """自举层内建运行时错误（get 非列表）同样被捕获。"""
    v, _ = _run_interp_src(full_boot_vm, "try { get(5)(0) } catch (e) { 7 }")
    assert v == 7


def test_interp_try_catch_no_var(full_boot_vm):
    """自举层 catch 可不带变量。"""
    v, _ = _run_interp_src(full_boot_vm, 'try { raise "x" } catch { 3 }')
    assert v == 3


def test_interp_try_finally(full_boot_vm):
    """自举层 finally 执行但不覆盖 try/catch 的值。"""
    v, _ = _run_interp_src(full_boot_vm, 'try { raise "x" } catch (e) { 5 } finally { 99 }')
    assert v == 5
    v2, _ = _run_interp_src(full_boot_vm, "try { 8 } catch (e) { 0 } finally { 1 }")
    assert v2 == 8


# ---------- parser 嵌套 let 修复回归 ----------

def test_nested_let_in_ternary():
    """验证 parser 修复：嵌套 let 在三元表达式内不再将 in 误认为二元运算符。"""
    from src.parser import parse
    code = 'func f(x: Int) -> Int = (x) => (x > 0) ? (let y = x in y) : 0'
    tree = parse(code)
    fn = tree.decls[0]
    lam = fn.body
    # lambda body 应为 IfExpr，其 then 分支为 LetBinding（非 BinaryOp ' in '）
    from src.ast_nodes import IfExpr, LetBinding
    assert isinstance(lam.body, IfExpr)
    assert isinstance(lam.body.then, LetBinding)
    assert lam.body.then.name == "y"


# ---------- 自举编译器：VM 上 Matha 编译 Matha ----------

def test_selfhost_type_of(compiler_boot_vm):
    """VM 内建 type_of 经 stdlib.matha_type_of 透传，各类型判定正确。"""
    assert compiler_boot_vm.call("matha_type_of", 3) == "Int"
    assert compiler_boot_vm.call("matha_type_of", 3.5) == "Float"
    assert compiler_boot_vm.call("matha_type_of", "hi") == "String"
    assert compiler_boot_vm.call("matha_type_of", [1, 2]) == "List"
    assert compiler_boot_vm.call("matha_type_of", {"a": 1}) == "Dict"
    assert compiler_boot_vm.call("matha_type_of", True) == "Bool"
    assert compiler_boot_vm.call("matha_type_of", None) == "Null"


def test_selfhost_compile_emits_module_dict(compiler_boot_vm):
    """自举编译器把 '3 + 5' 编译为模块 dict：常量池 + 主码（末条 HALT）。"""
    d = compiler_boot_vm.call("编译", "3 + 5")
    assert isinstance(d, dict)
    assert set(["常量", "函数", "主码", "模块名"]).issubset(d.keys())
    assert d["模块名"] == "主程序"
    assert d["常量"] == [3, 5, "+"]
    assert d["函数"] == []
    assert d["主码"][-1] == [0xFF]
    # PUSH_CONST 0; PUSH_CONST 1; BINOP(+ 常量索引 2); POP; HALT
    assert d["主码"][0] == [0x01, 0]
    assert d["主码"][2] == [0x40, 2]


def test_selfhost_compile_func_def(compiler_boot_vm):
    """自举编译器产出函数表条目；顶层 x = add(2, 3) 在真实 VM 执行得 5。"""
    src = "func add(a: Int, b: Int) -> Int = (a, b) => a + b\nx = add(2, 3)"
    d = compiler_boot_vm.call("编译", src)
    assert isinstance(d, dict) and len(d["函数"]) == 1
    name, info = d["函数"][0]
    assert name == "add"
    assert info["元数"] == 2 and info["参数"] == ["a", "b"]
    assert info["码"][-1] == [0x22]          # RET
    _, vm = compile_and_run(compiler_boot_vm, src)
    assert vm.globals["x"] == 5


def test_selfhost_module_constants_registered(compiler_boot_vm):
    """compiler_matha 的模块级 let 操作码常量已在 VM 全局注册（多文件合并初始化）。"""
    g = compiler_boot_vm.globals
    assert g["OP_PUSH_CONST"] == 0x01
    assert g["OP_HALT"] == 0xFF


_ARITH = "func f(a: Int, b: Int) -> Int = (a, b) => a * b + 3"
_RECUR = "func fact(n: Int) -> Int = (n) => n <= 1 ? 1 : n * fact(n - 1)"
_CURRY = "func 加c(a: Int) -> Int = (a) => (b) => a + b"
_CLOSURE = "func 造计数器(n: Int) -> Int = (n) => () => n + 1"
_WHILE = """
func 求和(n: Int) -> Int = (n) => {
  s = 0
  i = 1
  while i <= n {
    s = s + i
    i = i + 1
  }
  s
}
"""
_FOR = """
func 求和(xs: List) -> Int = (xs) => {
  s = 0
  for x in xs {
    s = s + x
  }
  s
}
"""
_TRY_OK = """
func 试() -> Int = () => {
  try {
    42
  } catch (e) {
    7
  }
}
"""
_TRY_RAISE = """
func 试() -> Int = () => {
  try {
    raise "炸"
  } catch (e) {
    99
  }
}
"""


@pytest.mark.parametrize("src,call,args,expected", [
    (_ARITH, "f", (4, 5), 23),
    (_RECUR, "fact", (5,), 120),
    (_WHILE, "求和", (10,), 55),
    (_FOR, "求和", ([1, 2, 3, 4, 5],), 15),
    (_TRY_OK, "试", (), 42),
    (_TRY_RAISE, "试", (), 99),
])
def test_selfhost_compiled_module_runs(compiler_boot_vm, src, call, args, expected):
    """自举产物 dict → MModule → 真实宿主 VM 端到端执行。"""
    results, _ = compile_and_run(compiler_boot_vm, src, [(call, args)])
    assert results[0] == expected


def test_selfhost_curried_closure_runs(compiler_boot_vm):
    """柯里化：加c(2)(3) = 5（逐参偏应用）。"""
    d = compiler_boot_vm.call("编译", _CURRY)
    vm = VM(dict_to_module(d))
    vm.run()
    inner = vm.call("加c", 2)
    assert vm.invoke_value(inner, [3]) == 5


def test_selfhost_zero_arg_closure_runs(compiler_boot_vm):
    """零参闭包：造计数器(10)() = 11（覆盖 () => 解析与 MAKE_CLOSURE 捕获）。"""
    d = compiler_boot_vm.call("编译", _CLOSURE)
    vm = VM(dict_to_module(d))
    vm.run()
    thunk = vm.call("造计数器", 10)
    assert vm.invoke_value(thunk, []) == 11


# ---------- S5：bootstrap_full_test.matha 全链路自测 ----------

def test_bootstrap_full_test_pipeline():
    """运行 matha/bootstrap_full_test.matha：lexer→parser→interp→compiler 全链路。

    该文件的自测块依次输出词法/语法/解释/编译四阶段的断言值，
    在合并编译后的 VM 上执行，验证全链路在字节码层闭环。
    """
    comp = _compile_files(_COMPILER_BOOT_FILES + ["matha/bootstrap_full_test.matha"])
    vm = VM(comp.mod)
    vm.run()
    # 合并编译时 lexer/stdlib/parser/interp 的自测块也会输出，取本文件自测段的尾部
    outs = vm.outputs[-21:]
    # 词法：6 tokens（5 + 结束），首 token 整数"1"，次为加，第4为乘，末为结束
    assert outs[0] == 6
    assert outs[1] == "整数" and outs[2] == "1"
    assert outs[3] == "加" and outs[4] == "乘" and outs[5] == "结束"
    # 语法：程序 → 顶层二元运算"+"，右孩子二元运算"*"（乘法绑定更紧），左值为 1
    assert outs[6] == "程序"
    assert outs[7] == "二元运算" and outs[8] == "+"
    assert outs[9] == "二元运算" and outs[10] == "*" and outs[11] == 1
    # 解释：求值结果 7
    assert outs[12] == 7
    # 编译：模块 dict（常量池 / 主码 / 函数表）
    assert outs[13] == "主程序"
    assert outs[14] == 5                      # 常量：1, 2, 3, *, +
    assert outs[15] == 1 and outs[16] == "+"
    assert outs[17] == 7                      # 6 条指令 + HALT
    assert outs[18] == 255                    # 末指令 HALT
    assert outs[19] == 64                     # 乘法先发射为 BINOP
    assert outs[20] == 0                      # 无函数定义


# ---------- M5：stdlib dict 操作 / 文件 I/O ----------

def test_stdlib_dict_keys(boot_vm):
    """dict_keys(d) → 键列表（stdlib 薄包装委托 VM 原语）。"""
    result = boot_vm.call("dict_keys", {"a": 1, "b": 2})
    assert sorted(result) == ["a", "b"]


def test_stdlib_dict_values(boot_vm):
    """dict_values(d) → 值列表。"""
    result = boot_vm.call("dict_values", {"a": 1, "b": 2})
    assert sorted(result) == [1, 2]


def test_stdlib_dict_has(boot_vm):
    """dict_has(d, k) → 是否含键。"""
    assert boot_vm.call("dict_has", {"a": 1}, "a") is True
    assert boot_vm.call("dict_has", {"a": 1}, "b") is False


def test_stdlib_dict_size(boot_vm):
    """dict_size(d) → 键数量（纯 Matha：len(_dict_keys(d))）。"""
    assert boot_vm.call("dict_size", {"a": 1, "b": 2, "c": 3}) == 3
    assert boot_vm.call("dict_size", {}) == 0


def test_stdlib_dict_get(boot_vm):
    """dict_get(d, k, default) → 有键取值，无键返回默认（纯 Matha）。"""
    assert boot_vm.call("dict_get", {"a": 1, "b": 2}, "a", 0) == 1
    assert boot_vm.call("dict_get", {"a": 1}, "x", 99) == 99


def test_stdlib_dict_put(boot_vm):
    """dict_put(d, k, v) → 不可变设置，返回新字典。"""
    d = boot_vm.call("dict_put", {"a": 1}, "b", 2)
    assert d == {"a": 1, "b": 2}
    # 原字典不受影响
    assert boot_vm.call("dict_has", {"a": 1}, "b") is False


def test_stdlib_dict_remove(boot_vm):
    """dict_remove(d, k) → 不可变删除，返回新字典。"""
    d = boot_vm.call("dict_remove", {"a": 1, "b": 2}, "a")
    assert "a" not in d
    assert d.get("b") == 2


def test_stdlib_dict_to_list(boot_vm):
    """dict_to_list(d) → [[键, 值], ...]（纯 Matha：拉链合并）。"""
    result = boot_vm.call("dict_to_list", {"a": 1})
    assert result == [["a", 1]]


def test_stdlib_dict_update(boot_vm):
    """dict_update(base, overrides) → 合并字典（纯 Matha：折叠 _dict_put）。"""
    d = boot_vm.call("dict_update", {"a": 1}, {"b": 2})
    assert d == {"a": 1, "b": 2}
    # overrides 覆盖同键
    d2 = boot_vm.call("dict_update", {"a": 1}, {"a": 99})
    assert d2 == {"a": 99}


def test_stdlib_dict_from_pairs(boot_vm):
    """dict_from_pairs(pairs) → 字典（纯 Matha：折叠 _dict_put + 空字典字面量）。"""
    d = boot_vm.call("dict_from_pairs", [("a", 1), ("b", 2)])
    assert d == {"a": 1, "b": 2}
    # 空列表 → 空字典
    assert boot_vm.call("dict_from_pairs", []) == {}


def test_stdlib_file_io(boot_vm, tmp_path):
    """read_file / write_file / append_file 端到端。"""
    p = str(tmp_path / "m5_test.txt")
    boot_vm.call("write_file", p, "hello")
    assert boot_vm.call("read_file", p) == "hello"
    boot_vm.call("append_file", p, " world")
    assert boot_vm.call("read_file", p) == "hello world"


# ---------- M5：自举编译器端到端 dict / file ----------

_DICT_KEYS_SRC = "func f(d: Dict) -> List = (d) => _dict_keys(d)"
_DICT_HAS_SRC = "func f(d: Dict, k: String) -> Bool = (d, k) => _dict_has(d, k)"
_DICT_PUT_SRC = "func f(d: Dict, k: String, v: Int) -> Dict = (d, k, v) => _dict_put(d, k, v)"


@pytest.mark.parametrize("src,call,args,check", [
    (_DICT_KEYS_SRC, "f", ({"a": 1, "b": 2},),
     lambda r: sorted(r) == ["a", "b"]),
    (_DICT_HAS_SRC, "f", ({"a": 1}, "a"),
     lambda r: r is True),
    (_DICT_HAS_SRC, "f", ({"a": 1}, "z"),
     lambda r: r is False),
    (_DICT_PUT_SRC, "f", ({"a": 1}, "b", 2),
     lambda r: r == {"a": 1, "b": 2}),
])
def test_selfhost_dict_vm_builtins(compiler_boot_vm, src, call, args, check):
    """自举编译器编译调用 VM 内建 dict 原语的源码 → VM 执行。

    编译产物 VM 有 _default_builtins()（含 _dict_keys/_dict_has/_dict_put 等），
    但无 stdlib 函数。此处验证编译器正确编译 Dict 类型标注 + 全局函数调用。
    """
    results, _ = compile_and_run(compiler_boot_vm, src, [(call, args)])
    assert check(results[0])


# ---------- M6：自举解析器列表字面量 / 下标访问 ----------

_LIST_LIT_SRC = "func f() -> List = () => [1, 2, 3]"
_SUBSCRIPT_SRC = "func f(lst: List) -> Int = (lst) => lst[0]"
_EMPTY_LIST_SRC = "func f() -> List = () => []"
_NESTED_SUB_SRC = "func f(lst: List) -> Int = (lst) => lst[0][1]"
_TRAILING_COMMA_SRC = "func f() -> List = () => [1, 2,]"
_BINOP_SUB_SRC = "func f(lst: List) -> Int = (lst) => lst[0] + lst[1]"
_LIST_ELEM_EXPR_SRC = "func f(a: Int, b: Int) -> List = (a, b) => [a, b, a + b]"


@pytest.mark.parametrize("src,call,args,expected", [
    (_LIST_LIT_SRC, "f", (), [1, 2, 3]),
    (_SUBSCRIPT_SRC, "f", ([10, 20, 30],), 10),
    (_EMPTY_LIST_SRC, "f", (), []),
    (_NESTED_SUB_SRC, "f", ([[10, 20, 30], 40, 50],), 20),
    (_TRAILING_COMMA_SRC, "f", (), [1, 2]),
    (_BINOP_SUB_SRC, "f", ([10, 20],), 30),
    (_LIST_ELEM_EXPR_SRC, "f", (3, 4), [3, 4, 7]),
])
def test_selfhost_list_literal_and_subscript(compiler_boot_vm, src, call, args, expected):
    """自举编译器编译含列表字面量/下标访问的源码 → VM 执行。

    M6 新增：parser.matha 解析 [a,b,c] 和 a[i]，
    compiler_matha.matha 已有 BUILD_LIST/INDEX_GET 生成路径。
    """
    results, _ = compile_and_run(compiler_boot_vm, src, [(call, args)])
    assert results[0] == expected


# ---------- M7：自举闭环验证 ----------

def test_m7_compiler_compiles_own_sources(compiler_boot_vm):
    """自举编译器编译自身全部源文件（lexer/stdlib/parser/interp/compiler_matha）。"""
    files = [
        ("matha/lexer.matha", 24),
        ("matha/stdlib.matha", 103),
        ("matha/parser.matha", 128),
        ("matha/interp.matha", 65),
        ("matha/compiler_matha.matha", 70),
    ]
    for rel, _min_funcs in files:
        src = (_ROOT / rel).read_text(encoding="utf-8")
        if src and src[0] == "\ufeff":
            src = src.lstrip("\ufeff")
        d = compiler_boot_vm.call("编译", src)
        assert isinstance(d, dict), f"{rel}: 编译未返回 dict"
        assert "函数" in d, f"{rel}: 产物无函数表"
        assert len(d["函数"]) >= 1, f"{rel}: 函数表为空"


def test_m7_compiled_lexer_matches_host(compiler_boot_vm):
    """自举 lexer.tokenize 产出的 token 值与宿主 lexer 一致。"""
    from src.lexer import Lexer as HostLexer
    cases = [
        "x = 1 + 2",
        "func f(a: Int) -> Int = (a) => a * b",
        "if x >= 3 then y else z",
        'let s = "hello" in s',
        "a >= b",
        "x != y",
        "a // b",
        "x ** 2",
    ]
    for src in cases:
        host_vals = [t.value for t in HostLexer(src).tokenize()]
        sh_toks = compiler_boot_vm.call("tokenize", src)
        sh_vals = [t["文本"] for t in sh_toks]
        assert host_vals == sh_vals, f"token 值不匹配: {src!r}\n  host={host_vals}\n  self={sh_vals}"


def test_m7_compiled_parser_runs(compiler_boot_vm):
    """自举 lexer → 自举 parser 产出 AST（声明数验证）。"""
    cases = [
        ("1 + 2 * 3", 1),
        ("x = 1", 1),
        ("(a) => a + 1", 1),
        ("if x then 1 else 2", 1),
    ]
    for src, expected_decls in cases:
        toks = compiler_boot_vm.call("tokenize", src)
        tree = compiler_boot_vm.call("parse", toks)
        assert tree["类型"] == "程序", f"{src!r}: AST 根节点非程序"
        assert len(tree["声明"]) == expected_decls, f"{src!r}: 声明数={len(tree['声明'])}, 期望={expected_decls}"


def test_m7_code_block_in_function(compiler_boot_vm):
    """自举编译器编译含代码块 { ... } 的函数体 → VM 执行。"""
    src = (
        "func f(n: Int) -> Int = (n) => {\n"
        "  s = 0\n"
        "  i = 1\n"
        "  while i <= n {\n"
        "    s = s + i\n"
        "    i = i + 1\n"
        "  }\n"
        "  s\n"
        "}\n"
    )
    results, _ = compile_and_run(compiler_boot_vm, src, [("f", (5,))])
    assert results[0] == 15  # 1+2+3+4+5 = 15


def test_m7_if_then_else_stmt(compiler_boot_vm):
    """自举解析器支持 if cond then expr else expr 语句形式。"""
    src = "func f(n: Int) -> Int = (n) => if n >= 0 then 1 else -1"
    results, _ = compile_and_run(compiler_boot_vm, src, [("f", (3,)), ("f", (-2,))])
    assert results[0] == 1
    assert results[1] == -1

