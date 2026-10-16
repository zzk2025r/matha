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
import math
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
        if src and src[0] == "﻿":
            src = src.lstrip("﻿")
        decls.extend(py_parse(src).decls)
    comp.compile_program(ast.Program(decls=decls))
    return comp


def _host_compile(source: str) -> MModule:
    """stage2：宿主 Python 编译器（src/mbc/compiler.py）的产物。"""
    return Compiler().compile_program(py_parse(source))


def _canon(mod):
    """把 MModule 或自举 dict 归一为可逐字段比较的纯 python 结构。

    自举产物用「函数」列表（按编译顺序），宿主用 dict（按名字）；
    归一后统一为 按名字排序的字典，从而 stage2 ≡ stage3 可直接断言。
    """
    if isinstance(mod, MModule):
        functions = {name: fn for name, fn in mod.functions.items()}
        module = mod.module_name
    else:
        functions = {}
        for entry in mod["函数"]:
            functions[entry[0]] = entry[1]
        module = mod.get("模块名", "主程序")
    return {
        "module": module,
        "constants": list(mod.constants if isinstance(mod, MModule)
                          else mod["常量"]),
        "main": [tuple(i) for i in (mod.main_code if isinstance(mod, MModule)
                                    else mod["主码"])],
        "functions": {
            name: (info.arity if isinstance(info, MFunction) else info["元数"],
                   info.nlocals if isinstance(info, MFunction) else info["局部数"],
                   list(info.params if isinstance(info, MFunction)
                        else info["参数"]),
                   [tuple(i) for i in (info.code if isinstance(info, MFunction)
                                       else info["码"])])
            for name, info in functions.items()
        },
    }


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


def test_interp_custom_op_eval(full_boot_vm):
    """自举解释器（interp.matha）求值自定义运算符：查具名实现并 f(l)(r) 两参调用。"""
    env = full_boot_vm.call("注册内建", full_boot_vm.call("空环境"))
    src = ("func 孪加(a: Int, b: Int) -> Int = (a, b) => a + b + 1\n"
           "@define_op: ∝ = 5 | left => 孪加\n"
           "2 ∝ 3\n")
    toks = full_boot_vm.call("tokenize", src)
    tree = full_boot_vm.call("parse", toks)
    result, _ = full_boot_vm.call("执行语句", tree, env)
    assert result == 6


def test_interp_custom_op_ast_has_impl(full_boot_vm):
    """自举解析器把自定义运算符产为「自定义二元」节点，携带「实现」函数名。"""
    _, tree = _parse_on_vm(full_boot_vm,
                           "@define_op: ∝ = 5 | left => 孪加\n2 ∝ 3\n")
    node = tree["声明"][-1]
    assert node["类型"] == "自定义二元"
    assert node["运算符"] == "∝"
    assert node["实现"] == "孪加"


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


# ---------- M4：集合构造 { }（自举 parser + compiler） ----------

def _set_case(compiler_boot_vm, src):
    """宿主 stage2 与自举 stage3 编译同一集合源码，比对规范化产物。"""
    host = _host_compile(src)
    self_ = dict_to_module(compiler_boot_vm.call("编译", src))
    return _canon(host) == _canon(self_)


def _set_outputs(compiler_boot_vm, src):
    """自举层编译并执行，返回 #1 输出。"""
    vm = VM(dict_to_module(compiler_boot_vm.call("编译", src)))
    vm.run()
    return vm.outputs


def test_set_empty(compiler_boot_vm):
    """{} 是空集合构造（不是空字典），与宿主 _parse_brace_dispatch 对齐。"""
    assert _set_case(compiler_boot_vm, "#1：[{}]")


def test_set_enumeration(compiler_boot_vm):
    """{1, 2, 3} 编译为 构造集合("enumeration", [], [1, 2, 3])。"""
    assert _set_case(compiler_boot_vm, "#1：[{1, 2, 3}]")


def test_set_dedup_and_order(compiler_boot_vm):
    """构造集合去重且保序，与宿主 VM 内建语义一致。"""
    assert _set_outputs(compiler_boot_vm, "#1：[{1, 2, 2, 3, 1}]") == [[1, 2, 3]]


def test_set_mixed_element_types(compiler_boot_vm):
    """数值 / 浮点 / 布尔 / 字符串元素与宿主逐字节一致。"""
    for src in ("#1：[{1, 2.5}]", "#1：[{真, 假}]", '#1：[{"a", 1}]'):
        assert _set_case(compiler_boot_vm, src), src


def test_set_expr_elements(compiler_boot_vm):
    """元素可以是任意表达式（首位须为字面量，标识符开头会走代码块消解）。"""
    assert _set_case(compiler_boot_vm, "a = 2\nb = 3\n#1：[{1, a + b}]")


def test_set_index_and_mutate(compiler_boot_vm):
    """集合构造结果可下标；下标赋值行为与宿主逐字节一致。

    注：`s[0] = 9` 在宿主与自举层当前都不改变已绑定值（两侧同为 no-op），
    此处锁定的是「两侧一致」这一契约，而非赋值语义本身。
    """
    src = "s = {3, 4}\ns[0] = 9\n#1：[[s, s[0]]]"
    assert _set_case(compiler_boot_vm, src)
    assert _set_outputs(compiler_boot_vm, src) == [[[3, 4], 3]]


def test_brace_still_dispatches_code_block_and_dict(compiler_boot_vm):
    """集合构造接入后，{ stmts } 代码块与 {k: v} 字典字面量消解不受影响。"""
    for src in (
        "#1：{ 1 + 1 }",
        "x = 9\n#1：{ x }",
        "#1：{ if 1 > 0 then 1 else 2 }",
        "#1：{ try { 1 } catch (e) { 2 } }",
        "#1：{ let y = 5 in y + 1 }",
        'd = {"a": 1}\n#1：[d["a"]]',
    ):
        assert _set_case(compiler_boot_vm, src), src


def test_set_rejects_identifier_leading_comma(compiler_boot_vm):
    """裸 {a, b} 在宿主报错：标识符开头的 `{` 会走代码块消解（与首位字面量的
    集合构造分支不同），块内 `a, b` 的逗号无法解析；并非「标识符开头需 `|`」
    （`|` 只是集合理解的另一条分支）。`#1：[{x, 2}]` 括号内宿主同样解析失败，
    走输出文本回退得 ['{x,2}']（非集合），自举层经同一回退与宿主一致。"""
    from src.parser import parse as py_parse

    with pytest.raises(Exception):
        py_parse("{a, b}")
    assert _set_outputs(compiler_boot_vm, "x = 1\n#1：[{x, 2}]") == ["{x,2}"]


def test_typed_lambda_in_let(compiler_boot_vm):
    """let g = (x: Int) => x + 1：带类型标注的 lambda 形参（括号消解）。"""
    assert _set_case(compiler_boot_vm, "let g = (x: Int) => x + 1\n#1：[g(41)]")


# ---------- M4：多值输出 / 属于判断 ∈ ----------

def test_output_multi_value_list(compiler_boot_vm):
    """#1：[a, b] 输出多个值——曾经遗留游离逗号，报「期望表达式，实际 ,」。"""
    assert _set_case(compiler_boot_vm, "a = 1\nb = 2\n#1：[a, b]")
    assert _set_outputs(compiler_boot_vm, "a = 1\nb = 2\n#1：[a, b]") == [[1, 2]]


def test_output_multi_value_literals(compiler_boot_vm):
    """输出内容为字面量列表。"""
    assert _set_case(compiler_boot_vm, "#1：[1, 2]")
    assert _set_outputs(compiler_boot_vm, "#1：[1, 2]") == [[1, 2]]


def test_output_single_value_unaffected(compiler_boot_vm):
    """单值输出与嵌套列表输出不被多值支持改坏。"""
    # `#1：[x]` 输出 x 本身；只有多值形态才整体是一个列表
    for src, want in (("#1：[1]", [1]),
                      ("#1：[[1, 2]]", [[1, 2]]),
                      ("#1：[]", [])):
        assert _set_case(compiler_boot_vm, src), src
        assert _set_outputs(compiler_boot_vm, src) == want, src


# ---------- M4：输出括号内的列表前瞻与集合运算符链 ----------
# 宿主 _parse_output 的 is_list_lookahead 除「紧跟逗号」外还用 _bracket_has_comma
# （括号内深度 1 的任意逗号）判定，列表分支在 ] 后另接集合运算符链（[a,b] ∪ [c,d]）。
# 自举 parser 此前仅看紧邻逗号、且不接集合链，故 #：[1 + 1, 2] 回退为文本、
# #：[[1], 2] 报错、#：[1, 2] ∪ [3] 把 ∪ 当变量名 + [3] 下标。
_M4_OUTPUT_LIST_CASES = [
    ("expr_then_comma", "#：[1 + 1, 2]\n", [[2, 2]]),
    ("nested_list_then_comma", "#：[[1], 2]\n", [[[1], 2]]),
    ("tuple_then_comma", "#：[(1, 2), 3]\n", [[[1, 2], 3]]),
    ("call_then_comma", "f = (x, y) => x + y\n#：[f(1, 2), 3]\n", [[3, 3]]),
    ("nested_lists", "#：[[1], [2]]\n", [[[1], [2]]]),
    ("three_values", "#：[1 + 1, 2, 3]\n", [[2, 2, 3]]),
    ("bracket_union", "#：[1, 2] ∪ [3]\n", [[1, 2, 3]]),
    ("bracket_union_trailing", "#：[1, 2] ∪ [3, 4]\n", [[1, 2, 3, 4]]),
    ("bracket_union_expr", "#：[1 + 1, 2] ∪ [3]\n", [[2, 3]]),
    ("bracket_union_order", "#：[3, 1] ∪ [2]\n", [[3, 1, 2]]),
    ("bracket_diff", "#：[1, 2, 3] ⊖ [2]\n", [[1, 3]]),
    ("bracket_inter", "#：[1, 2] ∩ [2, 3]\n", [[2]]),
    ("bracket_prod", "#：[1, 2] × [3, 4]\n", [[(1, 3), (1, 4), (2, 3), (2, 4)]]),
]

_M4_OUTPUT_LIST_IDS = [c[0] for c in _M4_OUTPUT_LIST_CASES]


@pytest.mark.parametrize("name,src,expect", _M4_OUTPUT_LIST_CASES, ids=_M4_OUTPUT_LIST_IDS)
def test_m4_output_list_host_runs(name, src, expect):
    """M4：宿主对 #：[…] 列表前瞻 + 集合运算符链的语义基准。"""
    assert VM(_host_compile(src)).run() == expect


@pytest.mark.parametrize("name,src,expect", _M4_OUTPUT_LIST_CASES, ids=_M4_OUTPUT_LIST_IDS)
def test_m4_output_list_stage2_equals_stage3(compiler_boot_vm, name, src, expect):
    """M4：stage2 ≡ stage3（输出括号列表前瞻 + 集合链逐字节一致）。"""
    stage3 = _canon(dict_to_module(compiler_boot_vm.call("编译", src)))
    stage2 = _canon(_host_compile(src))
    assert stage3 == stage2, f"stage2 ≡ stage3 不成立: {name}"


@pytest.mark.parametrize("name,src,expect", _M4_OUTPUT_LIST_CASES, ids=_M4_OUTPUT_LIST_IDS)
def test_m4_output_list_stage3_runs(compiler_boot_vm, name, src, expect):
    """M4：自举链路编译执行，输出与宿主一致。"""
    stage3_mod = dict_to_module(compiler_boot_vm.call("编译", src))
    assert VM(stage3_mod).run() == expect


def test_belongs_operator(compiler_boot_vm):
    """a ∈ b 成员判定：编译为 BINOP "in"，与宿主逐字节一致。"""
    cases = [
        ("a = [1, 2]\ny = 1 ∈ a\n#1：[y]", [True]),
        ("a = [1, 2]\ny = 3 ∈ a\n#1：[y]", [False]),
        ('d = {"a": 1}\ny = "a" ∈ d\n#1：[y]', [True]),
    ]
    for src, want in cases:
        assert _set_case(compiler_boot_vm, src), src
        assert _set_outputs(compiler_boot_vm, src) == want, src


def test_belongs_precedence(compiler_boot_vm):
    """∈ 比比较松、比 and 紧；且不破坏 and/or/比较既有语义。"""
    for src in (
        "a = [1, 2]\ny = 1 ∈ a and true\n#1：[y]",
        "a = 1\ny = a == 1\n#1：[y]",
        "a = true\nb = false\ny = a or b\n#1：[y]",
    ):
        assert _set_case(compiler_boot_vm, src), src


def test_brace_dispatch_refactor_no_regression(compiler_boot_vm):
    """花括号三义消解重构后：集合 / 字典 / 代码块判定与重构前逐字节一致。"""
    for src in (
        "{}", "{1, 2}", '{"a": 1}', "x = 9\n#1：{ x }", "#1：{ 1 + 1 }",
        "#1：{ if 1 > 0 then 1 else 2 }", "#1：{ try { 1 } catch (e) { 2 } }",
        "#1：{ let y = 5 in y + 1 }",
    ):
        assert _set_case(compiler_boot_vm, src), src


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


# ---------- M5：自举 stdlib 的 dict 操作与文件 I/O ----------


def test_m5_dict_get_hit_and_fallback(compiler_boot_vm):
    """dict_get：有键返回值、无键返回 fallback（先 _dict_has 再 d[k]）。"""
    d = {"a": 1, "b": 2}
    assert compiler_boot_vm.call("dict_get", d, "a", -1) == 1
    assert compiler_boot_vm.call("dict_get", d, "zzz", -1) == -1
    # fallback 可以是 None / 列表 / 字典等任意值
    assert compiler_boot_vm.call("dict_get", d, "zzz", None) is None
    assert compiler_boot_vm.call("dict_get", d, "zzz", [0]) == [0]


def test_m5_dict_set_returns_new_dict(compiler_boot_vm):
    """dict_set：不可变设置——返回新字典，原字典不受影响。"""
    d = {"a": 1}
    d2 = compiler_boot_vm.call("dict_set", d, "b", 2)
    assert d2 == {"a": 1, "b": 2}
    assert d == {"a": 1}
    # 覆盖已有键
    assert compiler_boot_vm.call("dict_set", d, "a", 9) == {"a": 9}
    # 与 dict_put 同义（M5 计划的 dict_set 是对外别名）
    assert compiler_boot_vm.call("dict_put", d, "b", 2) == d2


def test_m5_keys_and_values(compiler_boot_vm):
    """keys / values：计划书短名入口，与 dict_keys / dict_values 等价。"""
    d = {"a": 1, "b": 2}
    assert compiler_boot_vm.call("keys", d) == compiler_boot_vm.call("dict_keys", d) == ["a", "b"]
    assert compiler_boot_vm.call("values", d) == compiler_boot_vm.call("dict_values", d) == [1, 2]
    assert compiler_boot_vm.call("keys", {}) == []
    assert compiler_boot_vm.call("values", {}) == []


def test_m5_dict_ops_exported_in_module_table(compiler_boot_vm):
    """M5 目标函数均注册进 stdlib 模块导出表，可被 Matha 代码按名取用。"""
    tbl = compiler_boot_vm.globals["内建"]
    for name in ("dict_get", "dict_set", "dict_put", "keys", "values",
                 "dict_keys", "dict_values", "read_file", "write_file"):
        assert name in tbl, f"stdlib 导出表缺 {name}"


def test_m5_file_io_roundtrip(compiler_boot_vm, tmp_path):
    """read_file / write_file：写后读回一致（append_file 追加）。"""
    p = str(tmp_path / "m5.txt")
    compiler_boot_vm.call("write_file", p, "你好 Matha\n")
    assert compiler_boot_vm.call("read_file", p) == "你好 Matha\n"
    compiler_boot_vm.call("append_file", p, "第二行\n")
    assert compiler_boot_vm.call("read_file", p) == "你好 Matha\n第二行\n"
    # write_file 覆盖而非追加
    compiler_boot_vm.call("write_file", p, "只剩这行")
    assert compiler_boot_vm.call("read_file", p) == "只剩这行"


def test_m5_dict_ops_usable_from_matha_source(compiler_boot_vm, tmp_path):
    """M5 函数在自举链路里可被 Matha 源码按名调用（含中文标识符链式调用）。"""
    p = str(tmp_path / "m5b.json")
    payload = '{"k": 1, "j": 2}'
    compiler_boot_vm.call("write_file", p, payload)
    back = compiler_boot_vm.call("read_file", p)
    assert back == payload
    # dict_get / keys / values 走 VM 装载的 stdlib 闭包
    assert compiler_boot_vm.call("dict_get", {"x": 7}, "x", 0) == 7
    assert sorted(compiler_boot_vm.call("keys", {"x": 7, "y": 8})) == ["x", "y"]


def _merge_with_stdlib(program: str) -> str:
    """把一段 Matha 程序拼到自举 stdlib.matha 之后，构成单一 Program 源码。

    stdlib 的 func/let 声明会被扁平化为全局（宿主 _compile_top_decl 与自举
    _编译声明 的「模块」分支一致），故测试程序里的 keys/dict_set/read_file 等
    调用在运行时按全局名解析到 stdlib 函数——这是 stdlib 能被 Matha 源码
    使用的唯一途径（自编译产物 VM 只有 VM 内建，不含 stdlib 包装层）。
    """
    std = (_ROOT / "matha/stdlib.matha").read_text(encoding="utf-8")
    if std and std[0] == "\ufeff":
        std = std.lstrip("\ufeff")
    return std + "\n\n" + program


def _m5_source(path: str) -> str:
    return """
d = { "a": 1, "b": 2 }
k2 = keys(d)
v2 = values(d)
g_hit = dict_get(d, "a", 0)
g_miss = dict_get(d, "zzz", -1)
d2 = dict_set(d, "c", 3)
p = "%s"
write_file(p, "你好 Matha")
r = read_file(p)
#：[g_hit]
#：[g_miss]
#：[r]
#：[dict_get(d2, "c", 0)]
""" % (path.replace("\\", "/"))


def test_m5_named_surface_selfhost_source(compiler_boot_vm, tmp_path):
    """M5 六函数在**单一 Program**（stdlib 合并测试程序）里自举编译并运行。

    验证 keys/values/dict_get/dict_set/read_file/write_file 经自举编译器
    （stage3）编译后、真实 VM 执行链路下全部可用。
    """
    path = str(tmp_path / "m5e2e.txt")
    src = _merge_with_stdlib(_m5_source(path))
    mod = dict_to_module(compiler_boot_vm.call("编译", src))
    assert VM(mod).run() == [1, -1, "你好 Matha", 3]


def test_m5_named_surface_stage2_equals_stage3(compiler_boot_vm, tmp_path):
    """M5：合并源码的自举产物与宿主产物逐字段等价（stage2 ≡ stage3）。"""
    path = str(tmp_path / "m5parity.txt")
    src = _merge_with_stdlib(_m5_source(path))
    assert _canon(dict_to_module(compiler_boot_vm.call("编译", src))) == _canon(_host_compile(src))


def test_m5_named_surface_host_runs(compiler_boot_vm, tmp_path):
    """M5：宿主编译同一合并源码，运行结果一致（对照）。"""
    path = str(tmp_path / "m5host.txt")
    src = _merge_with_stdlib(_m5_source(path))
    assert VM(_host_compile(src)).run() == [1, -1, "你好 Matha", 3]


def test_selfhost_compile_emits_module_dict(compiler_boot_vm):
    """自举编译器把 '3 + 5' 编译为模块 dict：常量池 + 主码（末条 HALT）。

    M2 起自举编译器与宿主编译器同为常量折叠：3+5 在编译期求值为 8。
    """
    d = compiler_boot_vm.call("编译", "3 + 5")
    assert isinstance(d, dict)
    assert set(["常量", "函数", "主码", "模块名"]).issubset(d.keys())
    assert d["模块名"] == "主程序"
    assert d["常量"] == [8]
    assert d["函数"] == []
    assert d["主码"][-1] == [0xFF]
    # 折叠后：PUSH_CONST 0(=8); POP; HALT
    assert d["主码"][0] == [0x01, 0]
    assert d["主码"][1] == [0x59]
    # 与宿主编译器逐字节一致（stage2 ≡ stage3）
    assert _canon(d) == _canon(_host_compile("3 + 5"))


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
    outs = vm.outputs[-22:]
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
    # M2 起自举编译器与宿主同为常量折叠：2*3 → 6，故池为 1, 6, '+'
    assert outs[13] == "主程序"
    assert outs[14] == 3                      # 常量：1, 6, '+'
    assert outs[15] == 1 and outs[16] == 6 and outs[17] == "+"
    assert outs[18] == 5                      # 4 条指令 + HALT
    assert outs[19] == 255                    # 末指令 HALT
    assert outs[20] == 64                     # BINOP
    assert outs[21] == 0                      # 无函数定义


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
    ("func f(a: List, i: Int) -> Int = (a, i) => a[i]", "f", ([10, 20, 30], 1), 20),
    ("func f(a: List) -> Int = (a) => a[len(a) - 1]", "f", ([9, 8, 7],), 7),
    ("func f() -> List = () => [1, 2, 3, 4][1:3]", "f", (), [2, 3]),
    ("func f() -> List = () => [1, 2, 3, 4][:2]", "f", (), [1, 2]),
    ("func f() -> List = () => [1, 2, 3, 4][1:]", "f", (), [2, 3, 4]),
    ("func f() -> Int = () => [1, 2, 3][1]", "f", (), 2),
    ("func g() -> List = () => [10, 20]\nfunc f() -> Int = () => g()[0]", "f", (), 10),
    ("func f(a: Int, b: Int) -> List = (a, b) => [a + b, len([1, 2])]", "f", (3, 4), [7, 2]),
    ("func f() -> List = () => [ [1, 2], [3, 4] ]", "f", (), [[1, 2], [3, 4]]),
])
def test_selfhost_list_literal_and_subscript(compiler_boot_vm, src, call, args, expected):
    """自举编译器编译含列表字面量/下标访问的源码 → VM 执行。

    M6 新增：parser.matha 解析 [a,b,c] 和 a[i]（含变量下标、表达式下标、
    切片、调用结果下标、嵌套/计算元素），
    compiler_matha.matha 已有 BUILD_LIST/INDEX_GET 生成路径。
    """
    results, _ = compile_and_run(compiler_boot_vm, src, [(call, args)])
    assert results[0] == expected


# M6 构造族 stage2 ≡ stage3 字节级 parity：不仅运行值一致，产物须逐字段等价。
_M6_PARITY_CASES = [
    ("list_lit_fn",      "func f() -> List = () => [1, 2, 3]"),
    ("empty_list_fn",    "func f() -> List = () => []"),
    ("trailing_comma",   "func f() -> List = () => [1, 2,]"),
    ("var_index",        "func f(a: List, i: Int) -> Int = (a, i) => a[i]"),
    ("expr_index",       "func f(a: List) -> Int = (a) => a[len(a) - 1]"),
    ("nested_sub",       "func f(a: List) -> Int = (a) => a[0][1]"),
    ("binop_elem",       "func f(a: List) -> Int = (a) => a[0] + a[1]"),
    ("slice_std",        "func f() -> List = () => [1, 2, 3, 4][1:3]"),
    ("slice_open_head",  "func f() -> List = () => [1, 2, 3, 4][:2]"),
    ("slice_open_tail",  "func f() -> List = () => [1, 2, 3, 4][1:]"),
    ("slice_all",        "func f() -> List = () => [1, 2, 3, 4][:]"),
    ("lit_subscript",    "func f() -> Int = () => [1, 2, 3][1]"),
    ("call_subscript",   "func g() -> List = () => [10, 20]\nfunc f() -> Int = () => g()[0]"),
    ("elem_expr",        "func f(a: Int, b: Int) -> List = (a, b) => [a, b, a + b]"),
    ("len_expr_elem",    "func f(a: Int, b: Int) -> List = (a, b) => [a + b, len([1, 2])]"),
    ("nested_list_lit",  "func f() -> List = () => [ [1, 2], [3, 4] ]"),
    ("empty_concat",     "func f() -> List = () => [] + [1, 2]"),
]


@pytest.mark.parametrize("name,src", _M6_PARITY_CASES, ids=[c[0] for c in _M6_PARITY_CASES])
def test_selfhost_list_subscript_parity(compiler_boot_vm, name, src):
    """M6 构造族（列表字面量/下标/切片/嵌套/调用链）stage2 ≡ stage3。"""
    stage3 = _canon(dict_to_module(compiler_boot_vm.call("编译", src)))
    stage2 = _canon(_host_compile(src))
    assert stage3 == stage2, "stage2 ≡ stage3 不成立: M6.%s" % name


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
        # ---- 字符串转义：自举 lexer 的 解转义 必须与宿主 _decode_escape 同构 ----
        # 此前自举版只认 \n/\t 且丢弃其余反斜杠，宿主支持 \r 等而自举仍产出
        # " \t\nr"，自举定点（stage2 ≡ stage3）因此失败。
        r'x = "a\nb"',
        r'x = "a\rb"',
        r'x = "a\tb"',
        r'x = "a\bb"',
        r'x = "a\fb"',
        r'x = "a\vb"',
        r'x = "a\ab"',
        r'x = "a\"b"',
        "x = \"a\\'b\"",
        r'x = "a\\b"',
        r'x = "\x41\x7e"',
        r'x = "\u4f60\U0001F600"',
        r'x = "\101\102\0"',
        r'x = "\1011"',
        r'x = "a\qb"',
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


# M7 双重自举闭环：再用**自举编译器**（compiler_boot_vm，即跑在 VM 里的
# compiler_matha.matha 本身）编译自举源文件，产出的模块放进全新 VM 仍要能
# 工作。
# 
# 分级投入：
#   - lexer.matha 独占自举：约 10s（tokenize 闭环）
#   - lexer + parser 自举：约 2.5 分钟（tokenize→parse 闭环）
#   - 全链（含 compiler_matha）自举 + 二级编译：约 9 分钟，不进常规套件
#     （已在一次性探针中验证：自举链产物仍能 tokenize/parse，且二级「编译」
#      产出的模块在全新 VM 里可运行）。
def _boot_src(rels):
    parts = []
    for rel in rels:
        src = (_ROOT / rel).read_text(encoding="utf-8")
        if src and src[0] == "\ufeff":
            src = src.lstrip("\ufeff")
        parts.append(src)
    return "\n\n".join(parts)


def test_m7_double_bootstrap_lexer_chain(compiler_boot_vm):
    """双重自举：自举编译器编译 lexer.matha → 新 VM 中的自产 lexer.tokenize 与宿主一致。"""
    from src.lexer import Lexer as HostLexer
    src = _boot_src(["matha/lexer.matha"])
    mod = dict_to_module(compiler_boot_vm.call("编译", src))
    vm = VM(mod)
    vm.run()
    cases = [
        "x = 1 + 2",
        "func f(a: Int) -> Int = (a) => a * b",
        "if x >= 3 then y else z",
        'let s = "hello" in s',
        "a >= b",
        "x != y",
        "a // b",
        "x ** 2",
        # ---- 字符串转义：matha/lexer.matha 的 解转义 必须与宿主 _decode_escape 同构 ----
        # 此前自举版只认 \n/\t 且丢弃其余反斜杠，导致宿主已支持 \r 等而
        # 自举编译器仍产出 " \t\nr"，自举定点（stage2 ≡ stage3）失败。
        r'x = "a\nb"',
        r'x = "a\rb"',
        r'x = "a\tb"',
        r'x = "a\bb"',
        r'x = "a\fb"',
        r'x = "a\vb"',
        r'x = "a\ab"',
        r'x = "a\"b"',
        "x = \"a\\'b\"",
        r'x = "a\\b"',
        r'x = "\x41\x7e"',
        r'x = "\u4f60\U0001F600"',
        r'x = "\101\102\0"',
        r'x = "\1011"',
        r'x = "a\qb"',
    ]
    for sample in cases:
        host_vals = [t.value for t in HostLexer(sample).tokenize()]
        sh_vals = [t["文本"] for t in vm.call("tokenize", sample)]
        assert host_vals == sh_vals, f"双重自举 lexer token 不匹配: {sample!r}\n  host={host_vals}\n  self={sh_vals}"


def test_m7_double_bootstrap_parser_chain(compiler_boot_vm):
    """双重自举：自举编译器编译 lexer+parser → 新 VM 中的自产解析器照常工作。"""
    src = _boot_src(["matha/lexer.matha", "matha/parser.matha"])
    mod = dict_to_module(compiler_boot_vm.call("编译", src))
    vm = VM(mod)
    vm.run()
    cases = [
        ("1 + 2 * 3", 1),
        ("x = 1", 1),
        ("(a) => a + 1", 1),
        ("if x then 1 else 2", 1),
    ]
    for sample, expected_decls in cases:
        toks = vm.call("tokenize", sample)
        tree = vm.call("parse", toks)
        assert tree["类型"] == "程序", f"{sample!r}: AST 根节点非程序"
        assert len(tree["声明"]) == expected_decls, f"{sample!r}: 声明数={len(tree['声明'])}, 期望={expected_decls}"


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


# ==================== M2 定点：stage2 ≡ stage3 ====================
# 宿主 Python 编译器（stage2）与纯 Matha 编译器（stage3）对同一源码必须
# 产出完全一致的模块：常量池、主码、函数表（按名归一）。
#
# 已知例外（宿主侧限制，非 M2 缺陷），故不纳入断言：
#   - struct 字段赋值 `p.x = 7`：宿主无 SET_ATTR 指令，会退化为
#     存到名为 PathExpr(...) 的全局键；M3V 同样没有 SET_ATTR。
#   - match 语句：宿主编译器直接报「暂不支持的节点 MatchStmt」。

_M2_CASES = [
    ("arith", "x = 1 + 2 * 3\n输出(x)\n"),
    ("str_escape", 's = "a\\nb"\n输出(s)\n'),
    ("null_name", "x = null\n输出(x)\n"),
    ("list_index", "y = [1, 2, 3]\n输出(y[0])\n"),
    ("slice", "y = [1, 2, 3, 4]\n输出(y[1:3])\n"),
    ("dict_ident_keys", "x = { a: 1, b: 2 }\n输出(x)\n"),
    ("struct_ctor", "struct P { x: Int }\np = P(7)\n输出(p)\n"),
    ("let_local", "func f() -> Int = () => let y = 2 in y + 1\n输出(f())\n"),
    ("for_loop", "t = 0\nfor i in [1, 2, 3] {\n  t = t + i\n}\n输出(t)\n"),
    ("while_loop", "i = 0\nwhile i < 3 {\n  i = i + 1\n}\n输出(i)\n"),
    ("try_catch", "try {\n  x = 1\n} catch (e) {\n  x = 2\n}\n输出(x)\n"),
    ("import", "use stdlib\nx = len([1, 2])\n输出(x)\n"),
    ("module_name", "module M {\n  输出(1)\n}\n"),
    ("tuple_return", "func two() -> (Int, Int) = () => (1, 2)\nlet (a, b) = two()\n输出(a + b)\n"),
    ("closure", "func mk() -> Int = () => () => 7\n输出(mk()())\n"),
    ("mech_output", "#1：[42]\n"),
    ("mech_output_expr", "#：[1 + 1]\n"),
    ("output_stmt_list", "[1, 2]\n"),
    ("output_stmt_empty", "[]\n"),
    ("const_fold", "x = 3 + 5\n输出(x)\n"),
    ("lambda_multi_call", "func add3(a: Int, b: Int, c: Int) -> Int = (a, b, c) => a + b + c\n输出(add3(1, 2, 3))\n"),
]


@pytest.mark.parametrize("name,src", _M2_CASES, ids=[c[0] for c in _M2_CASES])
def test_m2_stage2_equals_stage3(compiler_boot_vm, name, src):
    """M2 定点：代表性源码上 stage2 与 stage3 产物逐字段一致。"""
    stage3 = _canon(dict_to_module(compiler_boot_vm.call("编译", src)))
    stage2 = _canon(_host_compile(src))
    assert stage3 == stage2, "stage2 ≡ stage3 不成立: %s" % name


# M2 定点：五个自举源全部 stage2 ≡ stage3，此表已清空（保持结构以便回归定位）。
_M2_BOOT_PENDING: dict[str, str] = {}


@pytest.mark.parametrize("path", _COMPILER_BOOT_FILES, ids=_COMPILER_BOOT_FILES)
def test_m2_boot_source_stage2_equals_stage3(compiler_boot_vm, path):
    """M2 定点：五个自举源文件自身 stage2 ≡ stage3。"""
    src = Path(path).read_text(encoding="utf-8")
    stage3 = _canon(dict_to_module(compiler_boot_vm.call("编译", src)))
    stage2 = _canon(_host_compile(src))
    if path in _M2_BOOT_PENDING:
        pytest.xfail("已知差异（待修）: %s —— %s" % (path, _M2_BOOT_PENDING[path]))
    assert stage3 == stage2, "自举源定点失败: %s" % path


# M4 宿主可达性修复回归：以下每类曾因 lexer/parser/compiler 缺口而不可用。
# 三元组 = (用例名, 源码, 宿主 VM 期望输出)。
_M4_HOST_FIX_CASES = [
    # 1. typeof 缺表达式 primary（parser 不认 typeof）
    ("typeof_int", 'x = typeof(1)\n#：[x]\n', ["整数"]),
    ("typeof_str", 'x = typeof("a")\n#：[x]\n', ["文本"]),
    # 2. 安全属性访问：parser 已能产 SafePathExpr，compiler 曾对裸 str 属性名漏发 PUSH_CONST
    ("safe_attr_hit", 'd = {"a": 1}\n#：[d?.a]\n', [1]),
    ("safe_attr_miss", 'd = {}\n#：[d?.a]\n', [None]),
    ("safe_chain", 'd = {"a": {"b": 2}}\n#：[d?.a?.b]\n', [2]),
    # 3. 安全下标访问（回归护栏，修复前已可用；注意语法是 a?.[i] 而非 a.?[i]）
    ("safe_index_hit", 'd = [1, 2]\n#：[d?.[0]]\n', [1]),
    ("safe_index_miss", 'd = [1, 2]\n#：[d?.[9]]\n', [None]),
    # 4. AngleExpr：⟨ 此前未映射成 OP_ANGLE，且 _identifier() 不前进导致无限循环
    ("angle", '#：[⟨1 + 2⟩]\n', [3]),
    # 5. IsExpr：parser 曾把 is 构造成 BinaryOp("is")，MBC 查表 KeyError
    ("is_expr", 'a = 1\nb = 1\n#：[a is b]\n', [True]),
    # 6. ChanExpr / SendExpr：KW_CHAN 无解析入口、`<-` 无 postfix 分支
    ("chan_send", 'c = chan Int\nc <- 7\nc <- 8\n#：[c?.缓冲]\n', [[7, 8]]),
    # 7. 位移：1 >> a 走的是位运算（∈ 才是 Belongs），此前 compiler/VM 均缺 << >>
    ("shift_left", '#：[1 << 3]\n', [8]),
    ("shift_right", '#：[16 >> 2]\n', [4]),
    # 8. 属于判断 ∈（BINOP "in"，注意不是 " in "）
    ("belongs", '#：[1 ∈ [1, 2]]\n', [True]),
    # 9. throw 与 raise 同义：KW_THROW 曾无解析入口；且 raise 在 try 体末句需补 PUSH_NULL
    ("throw_in_try", '#1：{ try { throw 1 } catch (e) { 2 } }\n', []),
]

_M4_HOST_FIX_IDS = [c[0] for c in _M4_HOST_FIX_CASES]

# stage3 补齐 ChanExpr / SendExpr 后，M4 全部节点已有 stage2≡stage3 覆盖，
# 无待办 xfail。保留本字典作为「新增节点须在此登记」的清单（空 = 全覆盖）。
_M4_STAGE3_PENDING: dict[str, str] = {}

# M4-2：@define_op。宿主/自举 _parse_define_op 均返回 NOOP 声明节点（编译期不产
# 码），并把绑定登记进运算符表；声明可绑定具名实现 `=> fn`。绑定后该运算符即可在
# 表达式中使用——两侧编译器均发 `LOAD_GLOBAL fn; left; right; CALL 2`。
_M4_DEFINE_OP_CASES = [
    ("dop_symbol", "@define_op : ∝ = 5 | left\n#：[1]\n", [1]),
    ("dop_halfcolon", "@define_op: ≈ = 5 | left\n#：[1 + 1]\n", [2]),
    ("dop_right_assoc", "@define_op : ≡ = 3 | right\n#：[2]\n", [2]),
    ("dop_two_decls", "@define_op : ∝ = 5 | left\n@define_op : ≡ = 3 | right\n#：[3]\n", [3]),
    ("dop_use_left",
     "func 孪加(a: Int, b: Int) -> Int = (a, b) => a + b + 1\n"
     "@define_op: ∝ = 5 | left => 孪加\n#：[2 ∝ 3]\n", [6]),
]

_M4_DEFINE_OP_IDS = [c[0] for c in _M4_DEFINE_OP_CASES]


@pytest.mark.parametrize("name,src,expect", _M4_DEFINE_OP_CASES, ids=_M4_DEFINE_OP_IDS)
def test_m4_define_op_host_runs(name, src, expect):
    """M4 @define_op：声明为编译期 NOOP，不影响程序输出。"""
    assert VM(_host_compile(src)).run() == expect


@pytest.mark.parametrize("name,src,expect", _M4_DEFINE_OP_CASES, ids=_M4_DEFINE_OP_IDS)
def test_m4_define_op_stage2_equals_stage3(compiler_boot_vm, name, src, expect):
    """M4 @define_op：stage2 ≡ stage3（消费序列一致、均不产码）。"""
    assert _canon(dict_to_module(compiler_boot_vm.call("编译", src))) == _canon(_host_compile(src))


@pytest.mark.parametrize("name,src,expect", _M4_DEFINE_OP_CASES, ids=_M4_DEFINE_OP_IDS)
def test_m4_define_op_stage3_runs(compiler_boot_vm, name, src, expect):
    assert VM(dict_to_module(compiler_boot_vm.call("编译", src))).run() == expect


def test_m4_define_op_unbound_use_raises():
    """使用**未绑定实现**的自定义运算符 → 编译期报错（宿主）。

    宿主 _parse_define_op 注册（handler=None）后返回 NOOP；使用该符号时具名
    实现为空，宿主编译器在编译期即拒绝（`未绑定实现`），故断言抛异常。
    绑定实现（`=> fn`）后的可用性由 dop_use_left 用例覆盖。
    """
    src = "@define_op : ∝ = 5 | left\nx = 1 ∝ 2\n#：[x]\n"
    with pytest.raises(Exception):
        VM(_host_compile(src)).run()

# M4-3：通道 ChanExpr / SendExpr。宿主降级为 {"缓冲": [], "容量": 0, "关闭": False}；
# `ch <- v` 追加到 缓冲 并求值为 true。注意 append 返回**新列表**，故须经
# _dict_put 写回通道变量（stage3 对应 _存储名 原语）。
_M4_CHAN_CASES = [
    ("chan_make", 'ch = chan Int\n#：[ch?.缓冲]\n', [[]]),
    ("chan_send", 'ch = chan Int\nch <- 1\nch <- 2\n#：[ch?.缓冲]\n', [[1, 2]]),
    # 发送本身求值为 true
    ("chan_send_value", 'ch = chan Int\nch <- 1\nr = ch <- 2\n#：[r]\n', [True]),
    ("chan_fields", 'ch = chan Int\n#：[ch?.容量]\n#：[ch?.关闭]\n', [0, False]),
    # chan T 的类型名支持泛型文本（Dict[String, Int] 等）
    ("chan_generic", 'ch = chan Int[3]\n#：[ch?.容量]\n', [0]),
    # 非变量通道：SendExpr 无法按名回写，宿主退化为求值后丢弃（POP）
    ("chan_noname", 'f = () => (chan Int) <- 1\n#：[1]\n', [1]),
]

_M4_CHAN_IDS = [c[0] for c in _M4_CHAN_CASES]


@pytest.mark.parametrize("name,src,expect", _M4_CHAN_CASES, ids=_M4_CHAN_IDS)
def test_m4_chan_host_runs(name, src, expect):
    """M4 通道：宿主构造/发送/字段。"""
    assert VM(_host_compile(src)).run() == expect


@pytest.mark.parametrize("name,src,expect", _M4_CHAN_CASES, ids=_M4_CHAN_IDS)
def test_m4_chan_stage2_equals_stage3(compiler_boot_vm, name, src, expect):
    """M4 通道：stage2 ≡ stage3。

    顶层两条 `ch <- v` 必须复用同一组临时槽名（__send_ch_0_1 /
    __send_buf_0_2）：宿主对每个顶层声明新建 main 作用域，临时槽计数
    从 0 起算——stage3 以 _重置主作用域计数 对齐。
    """
    assert _canon(dict_to_module(compiler_boot_vm.call("编译", src))) == _canon(_host_compile(src))


@pytest.mark.parametrize("name,src,expect", _M4_CHAN_CASES, ids=_M4_CHAN_IDS)
def test_m4_chan_stage3_runs(compiler_boot_vm, name, src, expect):
    assert VM(dict_to_module(compiler_boot_vm.call("编译", src))).run() == expect


def test_m4_top_level_temp_slots_restart_per_decl(compiler_boot_vm):
    """护栏：每条顶层语句的临时槽从 1 重新起算（与宿主 new main 作用域一致）。"""
    src = 'ch = chan Int\nch <- 1\nch <- 2\n#：[ch?.缓冲]\n'
    consts = dict_to_module(compiler_boot_vm.call("编译", src)).constants
    assert "__send_ch_0_1" in consts and "__send_buf_0_2" in consts
    assert "__send_ch_0_3" not in consts and "__send_buf_0_4" not in consts

# M4 自然语言块 / 标注块：宿主 NLBlock、ReadBlock 均为编译期 NOOP；
# stage3 需自建「自然语言块」节点并按同一语义（不产码、块末补 PUSH_NULL）。
_M4_NL_CASES = [
    ("nl_plain", "【求 1 加 1】\n#：[1]\n", [1]),
    ("nl_annot_1", "【*/多参数函数边界测试/*】\n#1：[1 + 1]\n", [2]),
    # 标注是自由文本：多词 + 全角冒号（宿主 _parse_annotation 曾只取单 token）
    ("nl_annot_multi", "【*/自主成长：从源码学习新能力、沙箱验证、注册/*】\n#：[1 + 1]\n", [2]),
    # 标注内允许 *（不应被误当公式起点）
    ("nl_annot_star", "【*/计算 2*3 的和/*】\n#：[1]\n", [1]),
    ("nl_then_block", "【*/模板 读取资源库构建计算流程/*】\n#：{ x = 1 + 2\n[x] }\n", [3]),
    ("nl_two_units", "【*/甲/*】\n#1：[1]\n【*/乙/*】\n#1：[2]\n", [1, 2]),
    # 函数体整体是文档块 → 宿主发 PUSH_NULL，函数值为 None
    ("nl_in_func", "func f() -> Int = () =>\n  【*/说明/*】\n  7\n#：[f()]\n", [None]),
    # 块末是文档块 → 走 _emit_block leave_last 收尾补 PUSH_NULL
    ("nl_end_of_func", "func g() -> Int = () =>\n  7\n  【*/尾部说明/*】\n#：[g()]\n", [7]),
]

_M4_NL_IDS = [c[0] for c in _M4_NL_CASES]


@pytest.mark.parametrize("name,src,expect", _M4_NL_CASES, ids=_M4_NL_IDS)
def test_m4_nl_block_host_runs(name, src, expect):
    """M4 自然语言块：宿主可解析、编译、运行（NLBlock/ReadBlock 皆 NOOP）。"""
    assert VM(_host_compile(src)).run() == expect


@pytest.mark.parametrize("name,src,expect", _M4_NL_CASES, ids=_M4_NL_IDS)
def test_m4_nl_block_stage2_equals_stage3(compiler_boot_vm, name, src, expect):
    """M4 自然语言块：stage2 ≡ stage3。"""
    assert _canon(dict_to_module(compiler_boot_vm.call("编译", src))) == _canon(_host_compile(src))


@pytest.mark.parametrize("name,src,expect", _M4_NL_CASES, ids=_M4_NL_IDS)
def test_m4_nl_block_stage3_runs(compiler_boot_vm, name, src, expect):
    """M4 自然语言块：自举链路运行结果与宿主一致。"""
    assert VM(dict_to_module(compiler_boot_vm.call("编译", src))).run() == expect


def test_m4_annotation_is_free_text():
    """标注体是自由文本：多词/含冒号/含 * 都能解析（宿主 _parse_annotation 回归）。"""
    for text in ("自主成长：从源码学习新能力", "多参数函数边界测试", "计算 2*3 的和"):
        py_parse("【*/%s/*】\n#：[1]\n" % text)


@pytest.mark.parametrize("name,src,expect", _M4_HOST_FIX_CASES, ids=_M4_HOST_FIX_IDS)
def test_m4_host_fix_runs(name, src, expect):
    """M4 修复项：宿主可解析、编译并运行，且语义正确。"""
    assert VM(_host_compile(src)).run() == expect


@pytest.mark.parametrize("name,src,expect", _M4_HOST_FIX_CASES, ids=_M4_HOST_FIX_IDS)
def test_m4_host_fix_stage2_equals_stage3(compiler_boot_vm, name, src, expect):
    """M4 修复项：stage2 与 stage3 产物逐字段一致（防回归）。"""
    if name in _M4_STAGE3_PENDING:
        pytest.xfail("stage3 已知差异（待补）: %s —— %s" % (name, _M4_STAGE3_PENDING[name]))
    stage3 = _canon(dict_to_module(compiler_boot_vm.call("编译", src)))
    stage2 = _canon(_host_compile(src))
    assert stage3 == stage2, "M4 修复项 stage2 ≡ stage3 不成立: %s" % name


@pytest.mark.parametrize("name,src,expect", _M4_HOST_FIX_CASES, ids=_M4_HOST_FIX_IDS)
def test_m4_host_fix_stage3_runs(compiler_boot_vm, name, src, expect):
    """M4 修复项：自举链路能编译并运行出与宿主相同的结果。"""
    if name in _M4_STAGE3_PENDING:
        pytest.xfail("stage3 已知差异（待补）: %s —— %s" % (name, _M4_STAGE3_PENDING[name]))
    stage3_mod = dict_to_module(compiler_boot_vm.call("编译", src))
    assert VM(stage3_mod).run() == expect


# ==================== M8：三元分支单元素列表字面量 ====================
# 宿主 _parse_primary 曾按「前一个 token」判定 [ 是列表还是输出，但漏了
# 三元 ? / :——导致 `cond ? [x] : [y]`（单元素）被误当 Output：宿主产出
# `[x, x]`（两分支各输出一次），而多元素 `[x, y]` 与自举解析器都按列表，
# 宿主自身语义即不一致。修复：新增 _in_ternary_branch 语境标记。
_M8_TERNARY_LIST_CASES = [
    ("ternary_then_single",
     "x = 1\n#：[x > 0 ? [1] : [0]]\n", [[1]]),
    ("ternary_else_single",
     "x = 0\n#：[x > 0 ? [1] : [2]]\n", [[2]]),
    ("ternary_var_single",
     "a = 1\nb = 2\n#：[a > b ? [a] : [b]]\n", [[2]]),
    ("ternary_bool_single",
     "x = true\n#：[x ? [42] : []]\n", [[42]]),
    ("ternary_multi_unaffected",
     "x = 1\n#：[x > 0 ? [1, 2] : [3, 4]]\n", [[1, 2]]),
    ("ternary_recursive_null",
     "func 补空(n: Int) -> List = (n) => n <= 0 ? [] : [null] + 补空(n - 1)\n"
     "#：[补空(3)]\n", [[None, None, None]]),
    ("ternary_paren_site",
     "x = 1\n#：[(x > 0) ? [7] : [8]]\n", [[7]]),
    ("ternary_nested_single",
     "x = 2\n#：[x > 1 ? x > 2 ? [1] : [2] : [3]]\n", [[2]]),
]

_M8_TERNARY_IDS = [c[0] for c in _M8_TERNARY_LIST_CASES]


@pytest.mark.parametrize("name,src,expect", _M8_TERNARY_LIST_CASES, ids=_M8_TERNARY_IDS)
def test_m8_ternary_list_host_runs(name, src, expect):
    """M8：宿主编译运行三元分支中的单元素列表字面量，语义为列表。"""
    assert VM(_host_compile(src)).run() == expect


@pytest.mark.parametrize("name,src,expect", _M8_TERNARY_LIST_CASES, ids=_M8_TERNARY_IDS)
def test_m8_ternary_list_stage2_equals_stage3(compiler_boot_vm, name, src, expect):
    """M8：三元分支列表字面量 stage2 ≡ stage3（宿主与自举解析一致）。"""
    stage3 = _canon(dict_to_module(compiler_boot_vm.call("编译", src)))
    stage2 = _canon(_host_compile(src))
    assert stage3 == stage2, f"stage2 ≡ stage3 不成立: {name}"


@pytest.mark.parametrize("name,src,expect", _M8_TERNARY_LIST_CASES, ids=_M8_TERNARY_IDS)
def test_m8_ternary_list_stage3_runs(compiler_boot_vm, name, src, expect):
    """M8：自举链路编译三元分支列表字面量，运行结果与宿主一致。"""
    stage3_mod = dict_to_module(compiler_boot_vm.call("编译", src))
    assert VM(stage3_mod).run() == expect


# ==================== M9：let 函数绑定显式 lambda + 顶层常量次序 ====================
# 1) 自举 parser 曾把 `let [rec] f(params) -> T = (params) => body` 里的显式
#    lambda 再包一层签名参数，形成双层 lambda（值变成「返回函数的函数」），
#    `let rec f ... = (n) => ...` 因而产出闭包而非计算结果。修复：与
#    解析函数定义 一致，`=` 后若为显式 lambda 则直接采用之。
# 2) 自举 compiler 曾先「一遍编译全部函数定义」再编译主码，导致「顶层 let
#    （带常量）出现在 func 之前」时常量池次序与宿主不同。修复：与宿主
#    compile_program 一致，顶层声明按源码顺序单遍编译。
_M9_LET_LAMBDA_CASES = [
    ("letrec_explicit_lambda",
     "let rec f(n: Int) -> Int = (n) => n <= 0 ? 1 : g(n - 1)\n"
     "and g(n: Int) -> Int = (n) => n <= 0 ? 2 : f(n - 1)\n"
     "#：[f(3)]\n", [2]),
    ("let_func_explicit_lambda",
     "let f(n: Int) -> Int = (n) => n * 2\n#：[f(4)]\n", [8]),
    ("let_before_func_order",
     "let f = (n) => n + 1\n"
     "func g(x: Int) -> Int = (x) => x * 2\n"
     "#：[f(1) + g(2)]\n", [6]),
    ("rec_simple_explicit",
     "let rec fact(n: Int) -> Int = (n) => n <= 1 ? 1 : n * fact(n - 1)\n"
     "#：[fact(5)]\n", [120]),
]

_M9_LET_LAMBDA_IDS = [c[0] for c in _M9_LET_LAMBDA_CASES]


@pytest.mark.parametrize("name,src,expect", _M9_LET_LAMBDA_CASES, ids=_M9_LET_LAMBDA_IDS)
def test_m9_let_lambda_host_runs(name, src, expect):
    """M9：宿主解析 let 函数绑定显式 lambda 与 let/func 次序，语义正确。"""
    assert VM(_host_compile(src)).run() == expect


@pytest.mark.parametrize("name,src,expect", _M9_LET_LAMBDA_CASES, ids=_M9_LET_LAMBDA_IDS)
def test_m9_let_lambda_stage2_equals_stage3(compiler_boot_vm, name, src, expect):
    """M9：stage2 ≡ stage3（含常量池次序逐位一致）。"""
    stage3 = _canon(dict_to_module(compiler_boot_vm.call("编译", src)))
    stage2 = _canon(_host_compile(src))
    assert stage3 == stage2, f"stage2 ≡ stage3 不成立: {name}"


@pytest.mark.parametrize("name,src,expect", _M9_LET_LAMBDA_CASES, ids=_M9_LET_LAMBDA_IDS)
def test_m9_let_lambda_stage3_runs(compiler_boot_vm, name, src, expect):
    """M9：自举链路编译 let 函数绑定显式 lambda 与 let/func 次序，运行一致。"""
    stage3_mod = dict_to_module(compiler_boot_vm.call("编译", src))
    assert VM(stage3_mod).run() == expect


# ==================== M10：位运算符 & | ⊕（含集合语境守卫）====================
# 1) 自举 parser 的 解析移位_续 曾缺 `&`/`|`/`⊕`，宿主可运行而自举崩
#    （VM：不可调用的值 None）。修复：与宿主 _parse_bit_expr 同层左结合，
#    按记号文本区分 `&`/`＆`（位与）、`|`/`｜`（位或）、`⊕`（异或）。
# 2) 自举 compiler 的 二元运算表 亦缺此三算子，一并补上（不参与常量折叠，
#    与宿主 _fold_bin 仅折叠 + - * ** 一致）。
# 3) `|` 与集合语境：宿主在集合理解头部把 `|` 当子句分隔符；自举 parser 不支持
#    理解形式，故引入 是理解头/有顶层理解管道 守卫，命中即报错，避免 `{x | cond}`
#    被静默误解析为位或枚举；`{1 | 2}`（非理解头）仍按位或，与宿主 [3] 一致。
_M10_BITOPS_CASES = [
    ("bit_and", "#：[6 & 3]\n", [2]),
    ("bit_or", "#：[6 | 3]\n", [7]),
    ("bit_xor", "#：[6 ⊕ 3]\n", [5]),
    ("bit_and_fullwidth", "#：[6 ＆ 3]\n", [2]),
    ("bit_or_fullwidth", "#：[6 ｜ 3]\n", [7]),
    ("bit_mixed", "#：[6 & 3 | 1]\n", [3]),
    ("set_bit_or", "#：[{1 | 2}]\n", [[3]]),
    ("set_bit_and", "#：[{1 & 2}]\n", [[0]]),
    ("set_bit_xor", "#：[{1 ⊕ 2}]\n", [[3]]),
    ("set_enum_bit", "#：[{1, 2 | 3}]\n", [[1, 3]]),
]

_M10_BITOPS_IDS = [c[0] for c in _M10_BITOPS_CASES]


@pytest.mark.parametrize("name,src,expect", _M10_BITOPS_CASES, ids=_M10_BITOPS_IDS)
def test_m10_bitops_host_runs(name, src, expect):
    """M10：宿主解析位运算符（含集合语境），语义正确。"""
    assert VM(_host_compile(src)).run() == expect


@pytest.mark.parametrize("name,src,expect", _M10_BITOPS_CASES, ids=_M10_BITOPS_IDS)
def test_m10_bitops_stage2_equals_stage3(compiler_boot_vm, name, src, expect):
    """M10：stage2 ≡ stage3（位运算符逐位一致）。"""
    stage3 = _canon(dict_to_module(compiler_boot_vm.call("编译", src)))
    stage2 = _canon(_host_compile(src))
    assert stage3 == stage2, f"stage2 ≡ stage3 不成立: {name}"


@pytest.mark.parametrize("name,src,expect", _M10_BITOPS_CASES, ids=_M10_BITOPS_IDS)
def test_m10_bitops_stage3_runs(compiler_boot_vm, name, src, expect):
    """M10：自举链路编译位运算符，运行一致。"""
    stage3_mod = dict_to_module(compiler_boot_vm.call("编译", src))
    assert VM(stage3_mod).run() == expect


@pytest.mark.parametrize("name,src,expect", [
    ("gen_clause", "s = [1, 2]\n#：[{x | x >> s}]\n", [[1, 2]]),
    ("ident_head", "s = [1, 2]\n#：[{a | b}]\n", ['{a|b}']),
    ("top_pipe_gen", "s = [1, 2, 3]\n#：[{1 + 1 | x >> s}]\n", [[2]]),
    ("bounded", "#：[{x | 1 <= x <= 5}]\n", [[1, 2, 3, 4, 5]]),
], ids=["gen_clause", "ident_head", "top_pipe_gen", "bounded"])
def test_m10_comprehension_host_runs(name, src, expect):
    """M10：宿主解析集合理解 `{输出 | v >> S | 条件}`，语义正确。"""
    assert VM(_host_compile(src)).run() == expect


@pytest.mark.parametrize("name,src,expect", [
    ("gen_clause", "s = [1, 2]\n#：[{x | x >> s}]\n", [[1, 2]]),
    ("ident_head", "s = [1, 2]\n#：[{a | b}]\n", ['{a|b}']),
    ("top_pipe_gen", "s = [1, 2, 3]\n#：[{1 + 1 | x >> s}]\n", [[2]]),
    ("bounded", "#：[{x | 1 <= x <= 5}]\n", [[1, 2, 3, 4, 5]]),
], ids=["gen_clause", "ident_head", "top_pipe_gen", "bounded"])
def test_m10_comprehension(compiler_boot_vm, name, src, expect):
    """M10：自举链路编译集合理解并运行，产物与宿主逐项一致。

    自举 parser 产出 comprehension 节点（`|` 分隔、`v >> S` 生成子句、可由
    `1 <= v <= n` 推断整数域），自举 compiler 降级为嵌套循环 + 过滤 + append，
    末尾 构造集合("enumeration", [], acc) 去重保序；不再回退为输出文本。"""
    assert _set_outputs(compiler_boot_vm, src) == expect


# ==================== M11：前缀一元运算符 ~ ^ ** << ++ -- ====================
# 1) 自举 parser 的 解析一元 曾缺 `~`（位取反）、`^`/`**`（前缀开方）、`<<`（前缀
#    角度）、`++`/`--`（前缀自增/自减）：宿主可运行而自举崩（KeyError '^' /
#    VM：不可调用的值 None），`--3` 更因 `--` 被拆成两个 减 记号而误算为 3。
#    修复：与宿主 src/parser.py:_parse_unary 对齐——新增 解析一元操作数
#    （对应 _parse_unary_operand，覆盖 << - ~ ^ ** 的任意层前缀组合），
#    解析一元 补齐 左移/加加/减减 分支；not/typeof 的操作数退回 解析应用。
# 2) 自举 lexer 曾把 `++`/`--` 拆成两个 加/减 记号；修复：enum 增 加加/减减，
#    检测多符 增 `++`/`--` 分支（对应宿主 tokens.py OP_INCR/OP_DECR）。
# 3) 自举 compiler 的 一元运算表 补 sqrt/~/angle/++/--；_折叠一元 补 sqrt
#    （整数字面量完全平方 → 整型，如 ^9 → 3，与宿主 _fold_unary 一致）、
#    ++/--（v±1）；~ / angle 不折叠，与宿主一致。
_M11_PREFIX_CASES = [
    ("bit_not", "#：[~5]\n", [-6]),
    ("bit_not_zero", "#：[~0]\n", [-1]),
    ("bit_not_chain", "#：[~~~5]\n", [-6]),
    ("sqrt_int_square", "#：[^9]\n", [3]),
    ("sqrt_int_nonsquare", "#：[^2]\n", [1.4142135623730951]),
    ("sqrt_float", "#：[^9.0]\n", [3.0]),
    ("sqrt_starstar", "#：[**9]\n", [3]),
    ("sqrt_in_expr", "#：[1 + ^9]\n", [4]),
    ("angle", "#：[<<90]\n", [1.5707963267948966]),
    ("angle_neg", "#：[<<-90]\n", [-1.5707963267948966]),
    ("neg_angle", "#：[-<<90]\n", [-1.5707963267948966]),
    ("incr", "#：[++3]\n", [4]),
    ("decr", "#：[--3]\n", [2]),
    ("incr_float", "#：[++3.5]\n", [4.5]),
    ("incr_var", "x = 5\n#：[++x]\n#：[x]\n", [6, 5]),
    ("decr_var", "x = 5\n#：[--x]\n#：[x]\n", [4, 5]),
]

_M11_PREFIX_IDS = [c[0] for c in _M11_PREFIX_CASES]


@pytest.mark.parametrize("name,src,expect", _M11_PREFIX_CASES, ids=_M11_PREFIX_IDS)
def test_m11_prefix_host_runs(name, src, expect):
    """M11：宿主解析前缀一元运算符，语义正确。"""
    assert VM(_host_compile(src)).run() == expect


@pytest.mark.parametrize("name,src,expect", _M11_PREFIX_CASES, ids=_M11_PREFIX_IDS)
def test_m11_prefix_stage2_equals_stage3(compiler_boot_vm, name, src, expect):
    """M11：stage2 ≡ stage3（前缀一元运算符逐位一致）。"""
    stage3 = _canon(dict_to_module(compiler_boot_vm.call("编译", src)))
    stage2 = _canon(_host_compile(src))
    assert stage3 == stage2, f"stage2 ≡ stage3 不成立: {name}"


@pytest.mark.parametrize("name,src,expect", _M11_PREFIX_CASES, ids=_M11_PREFIX_IDS)
def test_m11_prefix_stage3_runs(compiler_boot_vm, name, src, expect):
    """M11：自举链路编译前缀一元运算符，运行一致。"""
    stage3_mod = dict_to_module(compiler_boot_vm.call("编译", src))
    assert VM(stage3_mod).run() == expect


# ==================== M12：`#：` 输出括号内文本回退 ====================
# 宿主 `_parse_output`（src/parser.py:2524）在括号内容无法解析为「恰好填满到 ]
# 的单个表达式」时回退：把 ] 之前的原始记号文本（含换行 "\n"、不跳空白）拼成
# 字符串字面量。自举 parser 曾无此回退，遇 `#：[Hello world]` 等即报错。
# 修复：`解析器` 增 `禁止并列` 字段并在 `解析应用链` 间禁用并列应用（宿主无并列，
# 否则 `[Hello world]` 被吞成 FuncApp）；`解析括号内输出` 经 `调用捕获` 受保护地
# 尝试解析，成功且停在 ] 用其结果，否则 `收集原始文本` 逐记号码拼文本回退。
# 关键：不引入 `try` 节点与块内裸 `let`——自举编译器尚不支持 try 的字节码生成，
# 且对块内裸 `let` 会把局部名泄漏进常量池，二者都会破坏 stage2 ≡ stage3。
_M12_FALLBACK_CASES = [
    ("func_comma_fullwidth", "#：[你好，世界]\n", ["你好，世界"]),
    ("juxtaposition", "#：[Hello world]\n", ["Helloworld"]),
    ("fullwidth_comma", "#：[1，2]\n", ["1，2"]),
    ("ascii_comma_list", "#：[1, 2]\n", [[1, 2]]),
    ("prefix_plus", "#：[1 + +2]\n", ["1++2"]),
    ("octal", "#：[0o17]\n", ["0o17"]),
    ("underscore_num", "#：[1_000]\n", ["1_000"]),
    ("quad_minus", "#：[----3]\n", ["----3"]),
    ("not_incr", "#：[~++3]\n", ["~++3"]),
    ("extra_spaces", "#：[  Hello   world  ]\n", ["Helloworld"]),
    ("empty", "#：[]\n", []),
    ("call_text", "#：[f 5]\n", ["f5"]),
    ("abc_text", "#：[a b c]\n", ["abc"]),
    ("single_expr", "x = 7\n#：[x]\n", [7]),
    ("single_expr_calc", "#：[1 + 2]\n", [3]),
]

_M12_FALLBACK_IDS = [c[0] for c in _M12_FALLBACK_CASES]


@pytest.mark.parametrize("name,src,expect", _M12_FALLBACK_CASES, ids=_M12_FALLBACK_IDS)
def test_m12_fallback_host_runs(name, src, expect):
    """M12：宿主 `#：` 文本回退，语义正确。"""
    assert VM(_host_compile(src)).run() == expect


@pytest.mark.parametrize("name,src,expect", _M12_FALLBACK_CASES, ids=_M12_FALLBACK_IDS)
def test_m12_fallback_stage2_equals_stage3(compiler_boot_vm, name, src, expect):
    """M12：stage2 ≡ stage3（`#：` 文本回退逐位一致）。"""
    stage3 = _canon(dict_to_module(compiler_boot_vm.call("编译", src)))
    stage2 = _canon(_host_compile(src))
    assert stage3 == stage2, f"stage2 ≡ stage3 不成立: {name}"


@pytest.mark.parametrize("name,src,expect", _M12_FALLBACK_CASES, ids=_M12_FALLBACK_IDS)
def test_m12_fallback_stage3_runs(compiler_boot_vm, name, src, expect):
    """M12：自举链路编译 `#：` 文本回退，运行一致。"""
    stage3_mod = dict_to_module(compiler_boot_vm.call("编译", src))
    assert VM(stage3_mod).run() == expect


# ==================== M13：集合运算符 ∪ ∩ ⊖ × ⊆ ~（自举 chain）====================
# 宿主 src/lexer.py 把 ∪∩×⊆ 及别名 ⊖/＼（差）、～/〜/¬（补）、＄（积）分别归为
# OP_SET_UNION/INTER/PROD/SUBSET/DIFF/COMP；ASCII `~` 归 OP_BIT_NOT（一元位取反，
# 与 _SINGLE_CHAR_MAP 同键胜出于 _SINGLE_SET_OPS，故 `~` 不作二元补集）。宿主
# src/parser.py 的 _parse_set_expr 夹在 _parse_rel_expr 与 _parse_add_expr 之间
# （rel → set → add），compiler 的 _BIN_OPS 与 vm 的 _BINOPS 增补六个运算符。
# 自举侧：lexer.matha 不设专属类型，集合符号落入「符号」（按文本判定即可，无 lexer
# 改动）；parser.matha 新增 解析集合/解析集合_续 层插在 解析比较 与 解析加减 之间，
# 集合运算文本 把上述字形归一为 ∪∩⊖×⊆~；compiler_matha.matha 的 二元运算表 增补；
# vm.matha 的 应用运算 委托宿主原语 _set_*（有序去重列表），避免自引用。
# 语义：结果一律为有序去重 list（对齐集合字面量，非内建 sorted）；补集 A ~ B = B \ A
# （右操作数作全集，对齐 docs/06 与 api_reference set_complement）。ASCII `~` 仍是
# 前缀位取反，故补集用例只用全角 ～/〜/¬。
_M13_SETOP_CASES = [
    ("union", "s = [1,2,3] ∪ [3,4]\n#：[s]\n", [[1, 2, 3, 4]]),
    ("union_order", "s = [3,1] ∪ [2]\n#：[s]\n", [[3, 1, 2]]),
    ("union_scalar_r", "s = [1,2] ∪ [5]\n#：[s]\n", [[1, 2, 5]]),
    ("union_dedup", "s = [1,2,2] ∪ [2]\n#：[s]\n", [[1, 2]]),
    ("inter", "s = [1,2,3] ∩ [3,4]\n#：[s]\n", [[3]]),
    ("diff", "s = [1,2,3] ⊖ [3]\n#：[s]\n", [[1, 2]]),
    ("diff_alias", "s = [1,2,3] ＼ [2]\n#：[s]\n", [[1, 3]]),
    ("prod", "s = [1,2] × [3,4]\n#：[s]\n", [[(1, 3), (1, 4), (2, 3), (2, 4)]]),
    ("prod_alias", "s = [1,2] ＄ [3]\n#：[s]\n", [[(1, 3), (2, 3)]]),
    ("subset_true", "s = [1,2] ⊆ [1,2,3]\n#：[s]\n", [True]),
    ("subset_false", "s = [1,2] ⊆ [1,3]\n#：[s]\n", [False]),
    ("comp", "s = [2,3] ～ [1,2,3]\n#：[s]\n", [[1]]),
    ("comp_neg", "s = [1] ¬ [1,2,3]\n#：[s]\n", [[2, 3]]),
    ("comp_wave", "s = [1,2] 〜 [1,2,3]\n#：[s]\n", [[3]]),
    ("chained_left_assoc", "s = [1,2,3] ⊖ [3] ⊖ [1]\n#：[s]\n", [[2]]),
]

_M13_SETOP_IDS = [c[0] for c in _M13_SETOP_CASES]


@pytest.mark.parametrize("name,src,expect", _M13_SETOP_CASES, ids=_M13_SETOP_IDS)
def test_m13_setop_host_runs(name, src, expect):
    """M13：宿主编译执行集合运算符，语义正确（有序去重；补集 B\\A）。"""
    assert VM(_host_compile(src)).run() == expect


@pytest.mark.parametrize("name,src,expect", _M13_SETOP_CASES, ids=_M13_SETOP_IDS)
def test_m13_setop_stage2_equals_stage3(compiler_boot_vm, name, src, expect):
    """M13：stage2 ≡ stage3（集合运算符逐字节一致）。"""
    stage3 = _canon(dict_to_module(compiler_boot_vm.call("编译", src)))
    stage2 = _canon(_host_compile(src))
    assert stage3 == stage2, f"stage2 ≡ stage3 不成立: {name}"


@pytest.mark.parametrize("name,src,expect", _M13_SETOP_CASES, ids=_M13_SETOP_IDS)
def test_m13_setop_stage3_runs(compiler_boot_vm, name, src, expect):
    """M13：自举链路编译集合运算符，运行一致。"""
    stage3_mod = dict_to_module(compiler_boot_vm.call("编译", src))
    assert VM(stage3_mod).run() == expect


def test_m13_setop_ascii_tilde_is_unary_bitnot(boot_vm):
    """ASCII `~` 仍是前缀位取反（OP_BIT_NOT），不作二元补集；自举 parser 同判。

    宿主 `_SINGLE_CHAR_MAP["~"] = OP_BIT_NOT` 先于 `_SINGLE_SET_OPS` 命中；自举
    parser 的 是位取反（类型.符号 且 文本 "~"）同理，集合层不将 `~` 视为运算符。
    """
    _, tree = _parse_on_vm(boot_vm, "~1")
    # 前缀解析为一元位取反节点
    assert isinstance(tree, dict) and tree["类型"] == "程序"
    # 宿主侧重：~5 = -6（位取反）；#：[~5] 输出列表 [~5]
    assert VM(_host_compile("#：[~5]\n")).run() == [-6]


# ==================== M14：符号常量/前缀/单位（Phase ②，自举 chain）====================
# Phase ②：符号常量 π τ φ ∞、空集字面量 ∅、前缀 √/∛、中缀 ÷、单位后缀 ° ℃ ℉。
# 宿主：mathlib CONSTANTS 增 π τ φ ∞；lexer 把 ÷ 归 OP_SLASH、单位 °℃℉ 折入数字
# 字面量；parser 把前缀 √/∛ 建成 UnaryOp(sqrt/cbrt)、∅ 建成空列表字面量；compiler
# _UNARY_OPS/_fold_unary 增 cbrt。自举：lexer.matha ÷→除、单位码折入数字文本；
# parser.matha 增 是开方号/是立方根号、解析主要 增 符号分支（∅→空列表，余→变量）；
# compiler_matha 一元运算表/折叠 增 cbrt；vm.matha 应用一元 增 cbrt、引导 注册
# π τ φ ∞（∞ 用 _to_float("inf")，因自举 float 实现不解析 "inf"）。
# 语义：单位纯字符串标签（运行期丢弃，仅取值）；√/∛ 整数完全平方/立方回退整型。
_M14_SYMBOL_CASES = [
    ("pi", "#：[π]\n", [math.pi]),
    ("tau", "#：[τ]\n", [math.tau]),
    ("phi", "#：[φ]\n", [(1 + 5 ** 0.5) / 2]),
    ("inf", "#：[∞]\n", [math.inf]),
    ("empty_set", "#：[∅]\n", [[]]),
    ("empty_set_len", "#：[len(∅)]\n", [0]),
    ("sqrt_int", "#：[√9]\n", [3]),
    ("sqrt_int2", "#：[√16]\n", [4]),
    ("sqrt_float", "#：[√2]\n", [2 ** 0.5]),
    ("sqrt_in_expr", "#：[√9 + 1]\n", [4]),
    ("cbrt_perfect", "#：[∛27]\n", [3]),
    ("cbrt_perfect2", "#：[∛8]\n", [2]),
    ("cbrt_perfect3", "#：[∛64]\n", [4]),
    ("cbrt_neg", "#：[∛-8]\n", [-2]),
    ("cbrt_float", "#：[∛2]\n", [2 ** (1 / 3)]),
    ("div_symbol", "#：[6 ÷ 2]\n", [3.0]),
    ("div_symbol2", "#：[2 ÷ 4]\n", [0.5]),
    ("div_chained", "#：[12 ÷ 2 ÷ 3]\n", [2.0]),
    ("unit_deg", "#：[90°]\n", [90]),
    ("unit_celsius", "#：[30℃]\n", [30]),
    ("unit_fahrenheit", "#：[98℉]\n", [98]),
    ("unit_cjk", "#：[100米]\n", [100]),
    ("unit_in_expr", "#：[90° + 10]\n", [100]),
]

_M14_SYMBOL_IDS = [c[0] for c in _M14_SYMBOL_CASES]


@pytest.mark.parametrize("name,src,expect", _M14_SYMBOL_CASES, ids=_M14_SYMBOL_IDS)
def test_m14_symbol_host_runs(name, src, expect):
    """M14：宿主编译执行符号常量/前缀/单位，语义正确。"""
    assert VM(_host_compile(src)).run() == expect


@pytest.mark.parametrize("name,src,expect", _M14_SYMBOL_CASES, ids=_M14_SYMBOL_IDS)
def test_m14_symbol_stage2_equals_stage3(compiler_boot_vm, name, src, expect):
    """M14：stage2 ≡ stage3（符号常量/前缀/单位逐字节一致）。"""
    stage3 = _canon(dict_to_module(compiler_boot_vm.call("编译", src)))
    stage2 = _canon(_host_compile(src))
    assert stage3 == stage2, f"stage2 ≡ stage3 不成立: {name}"


@pytest.mark.parametrize("name,src,expect", _M14_SYMBOL_CASES, ids=_M14_SYMBOL_IDS)
def test_m14_symbol_stage3_runs(compiler_boot_vm, name, src, expect):
    """M14：自举链路编译符号常量/前缀/单位，运行一致。"""
    stage3_mod = dict_to_module(compiler_boot_vm.call("编译", src))
    assert VM(stage3_mod).run() == expect


# ==================== M15：聚合前缀 ∑/∏（Phase ②，自举 chain）====================
# 聚合前缀 ∑（列表求和，空表→0）/ ∏（列表求积，空表→1）；操作数须为列表，
# 非列表抛可捕获异常（对齐解释器 builtin_列表求和/求积）。
# 宿主：parser _parse_unary/_parse_unary_operand 增 ∑/∏ → UnaryOp(sum/prod)；
# compiler _UNARY_OPS 增 sum/prod；vm _UNARYOPS 增 → _builtin_list_sum/prod。
# 自举：parser.matha 增 是求和号/是求积号、解析一元(_操作数) 增分支；
# compiler_matha 一元运算表 增 sum/prod；vm.matha 应用一元 委托宿主
# _list_sum/_list_prod（在 src/mbc/vm.py 默认内建注册）。
_M15_AGG_CASES = [
    ("sum_int", "#：[∑[1,2,3,4]]\n", [10]),
    ("sum_empty", "#：[∑[]]\n", [0]),
    ("sum_single", "#：[∑[7,]]\n", [7]),
    ("prod_int", "#：[∏[1,2,3,4]]\n", [24]),
    ("prod_empty", "#：[∏[]]\n", [1]),
    ("prod_single", "#：[∏[7,]]\n", [7]),
    ("sum_float", "#：[∑[1, 2.5, 3]]\n", [6.5]),
    ("sum_float2", "#：[∑[1.5, 2.5]]\n", [4.0]),
    ("prod_float", "#：[∏[1.5, 2]]\n", [3.0]),
    ("sum_in_expr", "#：[∑[1,2,3] + 10]\n", [16]),
    ("sum_with_sqrt", "#：[∑[√9, √16]]\n", [7]),
    ("sum_of_prod", "#：[∑[∏[1,2], ∏[3,4]]]\n", [14]),
]


_M15_AGG_IDS = [c[0] for c in _M15_AGG_CASES]


@pytest.mark.parametrize("name,src,expect", _M15_AGG_CASES, ids=_M15_AGG_IDS)
def test_m15_agg_host_runs(name, src, expect):
    """M15：宿主编译执行聚合前缀 ∑/∏，语义正确。"""
    assert VM(_host_compile(src)).run() == expect


@pytest.mark.parametrize("name,src,expect", _M15_AGG_CASES, ids=_M15_AGG_IDS)
def test_m15_agg_stage2_equals_stage3(compiler_boot_vm, name, src, expect):
    """M15：stage2 ≡ stage3（聚合前缀 ∑/∏ 逐字节一致）。"""
    stage3 = _canon(dict_to_module(compiler_boot_vm.call("编译", src)))
    stage2 = _canon(_host_compile(src))
    assert stage3 == stage2, f"stage2 ≡ stage3 不成立: {name}"


@pytest.mark.parametrize("name,src,expect", _M15_AGG_CASES, ids=_M15_AGG_IDS)
def test_m15_agg_stage3_runs(compiler_boot_vm, name, src, expect):
    """M15：自举链路编译聚合前缀 ∑/∏，运行一致。"""
    stage3_mod = dict_to_module(compiler_boot_vm.call("编译", src))
    assert VM(stage3_mod).run() == expect


# ==================== M16：try/catch/finally ====================
# 自托管编译器新增 try/catch/finally 支持（_发射try/catch、块末尾机械单元修正）。
# 覆盖基础、catch 变量绑定、finally、嵌套、函数体内 try、catch-only、finally-only。
_M16_TRY_CASES = [
    ("basic",        "try { #：[1] } catch (e) { #：[2] }\n", [1]),
    ("catch_msg",    'try { throw "boom" } catch (e) { #：[e] }\n', ["boom"]),
    ("catch_int",    "try { throw 1 } catch (e) { #：[e] }\n", ["1"]),
    ("finally",      "try { #：[7] } catch (e) { #：[8] } finally { #：[9] }\n", [7, 9]),
    ("all",          "try { #：[1] } catch (e) { #：[2] } finally { #：[3] }\n", [1, 3]),
    ("finally_only", "try { #：[1] } finally { #：[2] }\n", [1, 2]),
    ("val_tail",     "try { #：[1] 2 } catch (e) { 3 }\n", [1]),
    ("nested",       "try { try { #：[1] } catch (e) { #：[2] } } catch (e) { #：[3] }\n", [1]),
    ("multi_units",  "try { #：[1] #：[2] } catch (e) { #：[3] }\n", [1, 2]),
    ("assign_in_try","x = 0\ntry { x = 5 } catch (e) { x = 9 }\n#：[x]\n", [0]),
    ("assign_catch", "x = 0\ntry { throw 1 } catch (e) { x = 9 }\n#：[x]\n", [0]),
    ("catch_runs",   "try { throw 5 } catch (e) { #：[10] }\n", [10]),
    ("fn_body_try",  "f = () => { try { throw 1 } catch (e) { 42 } }\n#：[f()]\n", [42]),
    ("fn_try_out",   "f = (n) => { try { n + 1 } catch (e) { 0 } }\n#：[f(3)]\n", [4]),
    ("try_then_out", "try { #：[1] } catch (e) { #：[2] }\n#：[99]\n", [1, 99]),
    ("throw_recover","try { throw 1 } catch (e) { #：[e] }\n#：[100]\n", ["1", 100]),
    ("nested_fin",   "try { try { #：[1] } finally { #：[2] } } catch (e) { #：[3] }\n", [1, 2]),
]


_M16_TRY_IDS = [c[0] for c in _M16_TRY_CASES]


@pytest.mark.parametrize("name,src,expect", _M16_TRY_CASES, ids=_M16_TRY_IDS)
def test_m16_try_host_runs(name, src, expect):
    """M16：宿主 try/catch/finally 语义基准。"""
    assert VM(_host_compile(src)).run() == expect


@pytest.mark.parametrize("name,src,expect", _M16_TRY_CASES, ids=_M16_TRY_IDS)
def test_m16_try_stage2_equals_stage3(compiler_boot_vm, name, src, expect):
    """M16：stage2 ≡ stage3（try/catch/finally 字节级一致）。"""
    stage3 = _canon(dict_to_module(compiler_boot_vm.call("编译", src)))
    stage2 = _canon(_host_compile(src))
    assert stage3 == stage2, f"stage2 ≡ stage3 不成立: {name}"


@pytest.mark.parametrize("name,src,expect", _M16_TRY_CASES, ids=_M16_TRY_IDS)
def test_m16_try_stage3_runs(compiler_boot_vm, name, src, expect):
    """M16：自举链路编译执行 try/catch/finally，输出与宿主一致。"""
    stage3_mod = dict_to_module(compiler_boot_vm.call("编译", src))
    assert VM(stage3_mod).run() == expect


# ==================== M17：块内裸 let 与分号语句分隔符 ====================
# 块内裸 let（{ let x = … }）此前总按顶层语义 STORE_GLOBAL + 常量池登记，
# 使局部名泄漏进常量池、破坏 stage2≡stage3 定点。现 _编译顶层let /
# _编译顶层let元组 按 is_main 分支：非 main 作用域走 STORE_LOCAL（元组则
# UNPACK_SEQ + 逆序 STORE_LOCAL），常量池不登记局部名。同时自托管 parser
# 补齐 `;` 语句分隔符（对应宿主 _skip_semicolon），支持 { let x = 1; x + 1 }
# 与顶层 `a = 1; b = 2`。
_M17_BLOCK_LET_CASES = [
    ("bare_let_chain",  "f = (x) => { let a = 1\n let b = a + x\n a + b }\n#：[f(1)]\n", [3]),
    ("bare_let_tuple",  "f = (x) => { let (a, b) = (x, x + 1)\n a + b }\n#：[f(2)]\n", [5]),
    ("bare_let_nested", "f = (x) => { let a = 1\n if true then { let b = a + x\n b * 2 } else { 0 } }\n#：[f(5)]\n", [12]),
    ("semi_block",      "f = (x) => { let y = x + 1; y * 2 }\n#：[f(3)]\n", [8]),
    ("semi_chain",      "f = (x) => { let a = 1; let b = a + x; a + b }\n#：[f(1)]\n", [3]),
    ("semi_top",        "a = 1; b = 2\n#：[a + b]\n", [3]),
    ("semi_mixed",      "f = (x) => { let a = 1\n let b = 2; a + b + x }\n#：[f(10)]\n", [13]),
]


_M17_BLOCK_LET_IDS = [c[0] for c in _M17_BLOCK_LET_CASES]


@pytest.mark.parametrize("name,src,expect", _M17_BLOCK_LET_CASES, ids=_M17_BLOCK_LET_IDS)
def test_m17_block_let_host_runs(name, src, expect):
    """M17：宿主块内裸 let / 分号分隔语义基准。"""
    assert VM(_host_compile(src)).run() == expect


@pytest.mark.parametrize("name,src,expect", _M17_BLOCK_LET_CASES, ids=_M17_BLOCK_LET_IDS)
def test_m17_block_let_stage2_equals_stage3(compiler_boot_vm, name, src, expect):
    """M17：stage2 ≡ stage3（块内裸 let / 分号分隔逐字节一致）。"""
    stage3 = _canon(dict_to_module(compiler_boot_vm.call("编译", src)))
    stage2 = _canon(_host_compile(src))
    assert stage3 == stage2, f"stage2 ≡ stage3 不成立: {name}"


@pytest.mark.parametrize("name,src,expect", _M17_BLOCK_LET_CASES, ids=_M17_BLOCK_LET_IDS)
def test_m17_block_let_stage3_runs(compiler_boot_vm, name, src, expect):
    """M17：自举链路编译执行块内裸 let / 分号分隔，输出与宿主一致。"""
    stage3_mod = dict_to_module(compiler_boot_vm.call("编译", src))
    assert VM(stage3_mod).run() == expect


# ==================== M18：match / switch 语句 ====================
# 自托管链路此前完全不支持 match/switch：parser 无 switch 分派、match 分支
# 不消费收尾 `}`、`_` 通配误用占位符类型、无守卫/构造子模式；compiler 无
# match/switch 发射。现补齐：parser 的 做Match 键名修正、解析match_stmt 消费
# `}`、解析match分支 支持守卫并置「在理解头」抑制 `|` 作位或、解析match模式
# 支持 下划线/字符串/布尔/浮点/构造子；新增 解析switch；lexer 关键字补
# switch/case/default；compiler 新增 _发射match/_发射switch 与模式发射，按
# 宿主 _emit_match/_emit_switch 逐字节对齐（scrutinee 临时槽 + 逐分支 JZ/JMP）。
_M18_MATCH_CASES = [
    ("lit_chain", 'func 分类(n: Int) -> String = (n) => {\n  match n {\n    | 0 => "零"\n    | 1 => "一"\n    | _ => "多"\n  }\n}\n#1：[分类(0)]\n#1：[分类(1)]\n#1：[分类(7)]\n', ["零", "一", "多"]),
    ("var_bind",  'func 加一(n: Int) -> Int = (n) => {\n  match n {\n    | x => x + 1\n  }\n}\n#1：[加一(9)]\n', [10]),
    ("guard",     'func 档(n: Int) -> String = (n) => {\n  match n {\n    | x if x > 10 => "大"\n    | x if x > 3 => "中"\n    | _ => "小"\n  }\n}\n#1：[档(20)]\n#1：[档(5)]\n#1：[档(1)]\n', ["大", "中", "小"]),
    ("ctor",      'func 解(o: Any) -> String = (o) => {\n  match o {\n    | Some(x) => "有" + str(x)\n    | None => "无"\n  }\n}\n#1：[解({"Some": 5})]\n#1：[解({"None": 1})]\n', ["有5", "无"]),
    ("two_ctors", 'func 解(o: Any) -> String = (o) => {\n  match o {\n    | Some(x) => "s" + str(x)\n    | Err(y) => "e" + str(y)\n    | _ => "?"\n  }\n}\n#1：[解({"Some": 1})]\n#1：[解({"Err": 2})]\n#1：[解({"Other": 3})]\n', ["s1", "e2", "?"]),
    ("str_pat",   'func 应(s: String) -> Int = (s) => {\n  match s {\n    | "a" => 1\n    | "b" => 2\n    | _ => 0\n  }\n}\n#1：[应("a")]\n#1：[应("b")]\n#1：[应("z")]\n', [1, 2, 0]),
    ("bool_pat",  'func 判(b: Bool) -> Int = (b) => {\n  match b {\n    | true => 1\n    | _ => 0\n  }\n}\n#1：[判(true)]\n#1：[判(false)]\n', [1, 0]),
    ("float_pat", 'func 判(x: Float) -> Int = (x) => {\n  match x {\n    | 1.5 => 1\n    | _ => 0\n  }\n}\n#1：[判(1.5)]\n#1：[判(2.0)]\n', [1, 0]),
    ("stmt_pos",  'func f(n: Int) -> String = (n) => {\n  match n {\n    | 1 => "a"\n    | _ => "b"\n  }\n  "done"\n}\n#1：[f(1)]\n#1：[f(2)]\n', ["done", "done"]),
]


_M18_SWITCH_CASES = [
    ("sw_default",   'func 分支(n: Int) -> String = (n) => {\n  switch n {\n    case 1: "一"\n    case 2: "二"\n    default: "其它"\n  }\n}\n#1：[分支(1)]\n#1：[分支(2)]\n#1：[分支(9)]\n', ["一", "二", "其它"]),
    ("sw_nodefault", 'func 分支(n: Int) -> Int = (n) => {\n  switch n {\n    case 10: 100\n    case 20: 200\n  }\n}\n#1：[分支(10)]\n#1：[分支(20)]\n#1：[分支(30)]\n', [100, 200, None]),
    ("sw_stmt",      'func f(n: Int) -> String = (n) => {\n  switch n {\n    case 0: "zero"\n    default: "nonzero"\n  }\n  "tail"\n}\n#1：[f(0)]\n', ["tail"]),
    ("sw_str",       'func f(s: String) -> Int = (s) => {\n  switch s {\n    case "x": 1\n    case "y": 2\n    default: 3\n  }\n}\n#1：[f("x")]\n#1：[f("z")]\n', [1, 3]),
]


_M18_MATCH_IDS = [c[0] for c in _M18_MATCH_CASES]
_M18_SWITCH_IDS = [c[0] for c in _M18_SWITCH_CASES]


@pytest.mark.parametrize("name,src,expect", _M18_MATCH_CASES, ids=_M18_MATCH_IDS)
def test_m18_match_host_runs(name, src, expect):
    """M18：宿主 match 语义基准。"""
    assert VM(_host_compile(src)).run() == expect


@pytest.mark.parametrize("name,src,expect", _M18_MATCH_CASES, ids=_M18_MATCH_IDS)
def test_m18_match_stage2_equals_stage3(compiler_boot_vm, name, src, expect):
    """M18：stage2 ≡ stage3（match 字节级一致）。"""
    stage3 = _canon(dict_to_module(compiler_boot_vm.call("编译", src)))
    stage2 = _canon(_host_compile(src))
    assert stage3 == stage2, f"stage2 ≡ stage3 不成立: {name}"


@pytest.mark.parametrize("name,src,expect", _M18_MATCH_CASES, ids=_M18_MATCH_IDS)
def test_m18_match_stage3_runs(compiler_boot_vm, name, src, expect):
    """M18：自举链路编译执行 match，输出与宿主一致。"""
    stage3_mod = dict_to_module(compiler_boot_vm.call("编译", src))
    assert VM(stage3_mod).run() == expect


@pytest.mark.parametrize("name,src,expect", _M18_SWITCH_CASES, ids=_M18_SWITCH_IDS)
def test_m18_switch_host_runs(name, src, expect):
    """M18：宿主 switch 语义基准。"""
    assert VM(_host_compile(src)).run() == expect


@pytest.mark.parametrize("name,src,expect", _M18_SWITCH_CASES, ids=_M18_SWITCH_IDS)
def test_m18_switch_stage2_equals_stage3(compiler_boot_vm, name, src, expect):
    """M18：stage2 ≡ stage3（switch 字节级一致）。"""
    stage3 = _canon(dict_to_module(compiler_boot_vm.call("编译", src)))
    stage2 = _canon(_host_compile(src))
    assert stage3 == stage2, f"stage2 ≡ stage3 不成立: {name}"


@pytest.mark.parametrize("name,src,expect", _M18_SWITCH_CASES, ids=_M18_SWITCH_IDS)
def test_m18_switch_stage3_runs(compiler_boot_vm, name, src, expect):
    """M18：自举链路编译执行 switch，输出与宿主一致。"""
    stage3_mod = dict_to_module(compiler_boot_vm.call("编译", src))
    assert VM(stage3_mod).run() == expect


# ==================== M19：go 语句 ====================
# 自托管链路此前不支持 `go <expr>`：宿主 parser 在**块内**把 `go` 解析为
# ast.GoStmt（_parse_statement 的 KW_GO 分支；顶层 _parse_decl 无此分支），
# compiler 降级为「立即求值 + POP」（VM 无抢占式调度）；自举 parser 无 go
# 分派（落到 解析表达式 报错）。现补齐：
#   - parser：新增 做Go + 解析go语句；解析声明 增 go 分派。
#   - compiler：_编译声明 增 `go` 分支（_发射表达式 + OP_POP）；并登记进
#     _是语句类型（宿主 GoStmt ∈ _STMT_NODES：块末留值时走语句路径，再由
#     _emit_block 的 leave_last 尾巴补 PUSH_NULL）。
_M19_GO_CASES = [
    ("after_ret",  'func g(x: Int) -> Int = (x) => x + 1\nfunc f() -> Int = () => {\n  go g(1)\n  42\n}\n#1：[f()]\n', [42]),
    ("tail_null",  'func g(x: Int) -> Int = (x) => x + 1\nfunc f() -> Int = () => {\n  go g(1)\n}\n#1：[f()]\n', [None]),
    ("call_value", 'func g(x: Int) -> Int = (x) => x\nfunc f() -> Int = () => {\n  go g(5)\n  7\n}\n#1：[f()]\n', [7]),
    ("in_while",   'func g(x: Int) -> Int = (x) => x\nfunc f(n: Int) -> Int = (n) => {\n  i = 0\n  while i < n {\n    go g(i)\n    i = i + 1\n  }\n  i\n}\n#1：[f(3)]\n', [3]),
    ("in_if",      'func g(x: Int) -> Int = (x) => x\nfunc f(n: Int) -> Int = (n) => {\n  if n > 0 {\n    go g(n)\n  }\n  n\n}\n#1：[f(2)]\n', [2]),
    ("in_if_more", 'func g(x: Int) -> Int = (x) => x\nfunc f(n: Int) -> Int = (n) => {\n  if n > 0 {\n    go g(n)\n    0\n  }\n  n\n}\n#1：[f(2)]\n', [2]),
    ("var_expr",   'func f() -> Int = () => {\n  x = 5\n  go x\n  9\n}\n#1：[f()]\n', [9]),
    ("arith_expr", 'func f() -> Int = () => {\n  go 1 + 2\n  9\n}\n#1：[f()]\n', [9]),
]

_M19_GO_IDS = [c[0] for c in _M19_GO_CASES]


@pytest.mark.parametrize("name,src,expect", _M19_GO_CASES, ids=_M19_GO_IDS)
def test_m19_go_host_runs(name, src, expect):
    """M19：宿主 go 语句语义基准。"""
    assert VM(_host_compile(src)).run() == expect


@pytest.mark.parametrize("name,src,expect", _M19_GO_CASES, ids=_M19_GO_IDS)
def test_m19_go_stage2_equals_stage3(compiler_boot_vm, name, src, expect):
    """M19：stage2 ≡ stage3（go 字节级一致）。"""
    stage3 = _canon(dict_to_module(compiler_boot_vm.call("编译", src)))
    stage2 = _canon(_host_compile(src))
    assert stage3 == stage2, f"stage2 ≡ stage3 不成立: {name}"


@pytest.mark.parametrize("name,src,expect", _M19_GO_CASES, ids=_M19_GO_IDS)
def test_m19_go_stage3_runs(compiler_boot_vm, name, src, expect):
    """M19：自举链路编译执行 go，输出与宿主一致。"""
    stage3_mod = dict_to_module(compiler_boot_vm.call("编译", src))
    assert VM(stage3_mod).run() == expect


# ==================== M20：语句位置 if 的形态对齐 ====================
# 缺陷：自举 _编译平衡（语句位置 if）恒以「值形态 + POP」发射（_发射if 恒
# 留值，再 OP_POP），而宿主对**块形态** if（IfStmt/IfElseStmt）用语句形态
# _emit_if_stmt(leave_value=False)：各分支块 leave_last=假、无 else 不补
# PUSH_NULL、整体无 POP；仅对 then/else **表达式形态**（IfExpr）才用
# 「值形态 + POP」。故语句位置块形态 if 的字节码两侧不一致（执行结果相同，
# 隐藏已久：自举源自身不含语句位置 if，M2 定点未暴露）。
# 修复：_发射if 增 留值 参数；_编译平衡 按真分支是否为 Program 区分形态：
#   块形态 → _发射if(…, 假)（语句形态）；表达式形态 → _发射if(…, 真) + OP_POP。
_M20_IF_STMT_CASES = [
    ("top_block",    'x = 0\nif x > 0 {\n  x = 1\n}\n#：[x]\n', [0]),
    ("block_else",   'func f(n: Int) -> Int = (n) => {\n  if n > 0 {\n    1\n  } else {\n    2\n  }\n  n\n}\n#1：[f(1)]\n', [1]),
    ("block_noelse", 'func f(n: Int) -> Int = (n) => {\n  if n > 0 {\n    n\n  }\n  n\n}\n#1：[f(2)]\n', [2]),
    ("tail_block",   'func f(n: Int) -> Int = (n) => {\n  if n > 0 {\n    n\n  }\n}\n#1：[f(2)]\n', [2]),
    ("two_blocks",   'func f(n: Int) -> Int = (n) => {\n  if n > 0 {\n    1\n  }\n  if n > 1 {\n    2\n  }\n  n\n}\n#1：[f(5)]\n', [5]),
    ("expr_stmt",    'func f(n: Int) -> Int = (n) => {\n  if n > 0 then 1 else 2\n  n\n}\n#1：[f(1)]\n', [1]),
    ("expr_tail",    'func f(n: Int) -> Int = (n) => {\n  if n > 0 then 1 else 2\n}\n#1：[f(1)]\n', [1]),
    ("mech_block",   '#1：{ if 1 > 0 { 5 } else { 6 } }\n', []),
]

_M20_IF_STMT_IDS = [c[0] for c in _M20_IF_STMT_CASES]


@pytest.mark.parametrize("name,src,expect", _M20_IF_STMT_CASES, ids=_M20_IF_STMT_IDS)
def test_m20_if_stmt_host_runs(name, src, expect):
    """M20：宿主语句位置 if 语义基准。"""
    assert VM(_host_compile(src)).run() == expect


@pytest.mark.parametrize("name,src,expect", _M20_IF_STMT_CASES, ids=_M20_IF_STMT_IDS)
def test_m20_if_stmt_stage2_equals_stage3(compiler_boot_vm, name, src, expect):
    """M20：stage2 ≡ stage3（语句位置 if 字节级一致）。"""
    stage3 = _canon(dict_to_module(compiler_boot_vm.call("编译", src)))
    stage2 = _canon(_host_compile(src))
    assert stage3 == stage2, f"stage2 ≡ stage3 不成立: {name}"


@pytest.mark.parametrize("name,src,expect", _M20_IF_STMT_CASES, ids=_M20_IF_STMT_IDS)
def test_m20_if_stmt_stage3_runs(compiler_boot_vm, name, src, expect):
    """M20：自举链路编译执行语句位置 if，输出与宿主一致。"""
    stage3_mod = dict_to_module(compiler_boot_vm.call("编译", src))
    assert VM(stage3_mod).run() == expect
