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
    """{a, b} 在宿主即非法（标识符开头需 `|`），自举层同样拒绝而非误判为集合。"""
    from src.parser import parse as py_parse

    with pytest.raises(Exception):
        py_parse("{a, b}")
    with pytest.raises(Exception):
        compiler_boot_vm.call("编译", "x = 1\n#1：[{x, 2}]")


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

# M4-2：@define_op。宿主 _parse_define_op 注册 GLOBAL_CUSTOM_OPS 后返回
# ast.DefineOp（编译期 NOOP）；宿主自身尚不支持**使用**自定义运算符
# （写 `1 ∝ 2` 报未知运算符），故 stage3 只需按同一次序消费、不产码。
_M4_DEFINE_OP_CASES = [
    ("dop_symbol", "@define_op : ∝ = 5 | left\n#：[1]\n", [1]),
    ("dop_halfcolon", "@define_op: ≈ = 5 | left\n#：[1 + 1]\n", [2]),
    ("dop_right_assoc", "@define_op : ≡ = 3 | right\n#：[2]\n", [2]),
    ("dop_two_decls", "@define_op : ∝ = 5 | left\n@define_op : ≡ = 3 | right\n#：[3]\n", [3]),
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


def test_m4_define_op_symbol_not_usable_either_side():
    """自定义运算符**使用**在宿主与自举侧同样不支持。

    解析与编译都通过（`1 ∝ 2` 落到未知 BINOP），VM 求值时才因未知运算符
    报错——故这里断言运行期失败，而非解析期失败。
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
