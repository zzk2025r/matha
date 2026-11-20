# -*- coding: utf-8 -*-
"""阶段 30d 语法缺口真化锁（列表推导 boot 面 + 内建偏应用 + 机械单元列表体）。

30d 三片：
  ① 列表推导 [e for t in it if c...] boot parser + interp 真化——
     boot parser 二义分派（解析列表元素返节点）+ 解析推导尾/目标/条件 +
     求值列表推导（宿主 ListComp 镜像：List/Tuple/String/Dict 迭代源、
     多条件、影子绑定不外泄）；28b conv 面 列表推导→ast.ListComp
     （test_parser_parity_phase28 _PARITY_FILES golden 35 全文件对拍）。
  ② 内建偏应用协议——柯里化 AST（嵌套单参 FuncApp）下多参内建首参调用
     记 ["__内建部分__", 名, 已积参数]，续参经 应用函数/应用多参数函数
     补全臂重入 应用内建（宿主 _curry_module 同构）；此前 range(1, 4)
     等多参内建 boot 面一律 IndexError（stdlib_symbols/golden 35 根因）。
  ③ 执行机械单元 列表体修复——type_of(stmt["body"]) = "列表" 误比
     （type_of 返回 "List"），列表体落入 执行语句列表(list) 报
     「索引操作不支持: list[类型]」（bootstrap_test_v2 根因）。
判据：boot 面输出快照 == 宿主面输出 == 期望值；boot 解析节点形状锁；
双 for 推导锁已随 31b 真化退役（原 boot 诚实报错分歧条目）。
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.set_int_max_str_digits(0)

from pathlib import Path

from src.parser import parse as py_parse
from src import ast_nodes as ast
from src.mbc.compiler import Compiler
from src.mbc.vm import VM
from src.kernel.errors import MathaRuntimeError
from src import interp as host_interp

_ROOT = Path(__file__).resolve().parent.parent
_BOOT_FILES = ["matha/lexer.matha", "matha/stdlib.matha", "matha/parser.matha",
               "matha/runtime/matha_runtime.matha", "matha/interp_matha.matha"]

_CHAIN_NS_NAMES = ("词法器", "标准库", "语法器", "运行时引擎", "解释器")


def _strip_bom(src):
    return src.lstrip("\ufeff") if src and src[0] == "\ufeff" else src


@pytest.fixture(scope="module")
def bootvm():
    comp = Compiler()
    decls = []
    for rel in _BOOT_FILES:
        decls.extend(py_parse(_strip_bom(
            (_ROOT / rel).read_text(encoding="utf-8"))).decls)
    comp.compile_program(ast.Program(decls=decls))
    vm = VM(comp.mod)
    vm.run()
    vm.globals["MathaRuntimeError"] = MathaRuntimeError
    vm._chain_nss = {nm: vm.globals[nm] for nm in _CHAIN_NS_NAMES
                     if isinstance(vm.globals.get(nm), dict)}
    return vm


def _boot_run(bootvm, src):
    bootvm.call("输出清空")
    toks = bootvm.call("扫描", src, 0, 1, 1, [])
    prog = bootvm.call("parse", toks)
    env0 = bootvm.call("注册内建", bootvm.call("空环境"))
    for nm, ns in bootvm._chain_nss.items():
        env0 = bootvm.call("绑定环境", env0, nm, ns)
    bootvm.call("执行语句", prog, env0)
    return list(bootvm.call("输出快照"))


def _host_run(src):
    outs, _trace = host_interp.interpret(src)
    return outs


# (名, 源码, 期望输出) —— 输出快照形态（一次 输出 一条目）
_COMP_CASES = [
    ("golden35_sq", "nums = [1, 2, 3, 4]\n输出([x * x for x in nums])",
     [[1, 4, 9, 16]]),
    ("golden35_filter", "big = [1, 2, 3, 4, 5]\n输出([x for x in big if x > 3])",
     [[4, 5]]),
    ("multi_cond", "mid = [1, 2, 3, 4, 5]\n输出([x for x in mid if x > 2 if x < 5])",
     [[3, 4]]),
    ("empty_src", "输出([x * x for x in []])", [[]]),
    ("range_src", "输出([x * 10 for x in range(1, 4)])", [[10, 20, 30]]),
    ("nested_comp", "m = [[1, 2], [3, 4]]\n输出([[y * 2 for y in row] for row in m])",
     [[[2, 4], [6, 8]]]),
    ("string_iter", '输出([c for c in "abc"])', [["a", "b", "c"]]),
    ("tuple_iter", "输出([x + 1 for x in (1, 2)])", [[2, 3]]),
    ("dict_iter_index", 'd = {"a": 1, "b": 2}\n输出([x[0] for x in d])',
     [["a", "b"]]),
    ("shadow_restore", "x = 99\n输出([x for x in [1, 2]])\n输出(x)",
     [[1, 2], 99]),
    ("mod_cond", "输出([n for n in [1, 2, 3, 4] if n % 2 = 0])", [[2, 4]]),
    # 内建偏应用（30d-②）：柯里化 AST 下多参内建首参记部分、续参补全
    ("builtin_partial_range", "输出(range(1, 4))", [[1, 2, 3]]),
    ("builtin_partial_in_comp",
     "输出([s for s in range(0, 5) if s > 1])", [[2, 3, 4]]),
]


@pytest.mark.parametrize("name,src,expected", _COMP_CASES, ids=[c[0] for c in _COMP_CASES])
def test_list_comp_boot_equals_host(bootvm, name, src, expected):
    assert _boot_run(bootvm, src) == expected
    assert _host_run(src) == expected


_UNIT_SRC = """module 单元列表体测 {
#1：【块】
{
  a = 2
  [a]
}
}
"""


def test_mech_unit_list_body_boot_equals_host(bootvm):
    """30d-③：机械单元 列表体（宿主合并体 [生成语句, 块]）经 _执行单元列表
    逐条执行；此前 type_of(body) = "列表" 误比落入 执行语句列表(list)
    报「索引操作不支持: list[类型]」（bootstrap_test_v2 全文件同根因）。
    裸 [a] 输出语句打印 a 的值（输出追踪包 输出），双面快照均 [2]。"""
    assert _boot_run(bootvm, _UNIT_SRC) == [2]
    assert _host_run(_UNIT_SRC) == [2]


def test_boot_parse_comp_node_shape(bootvm):
    """boot 解析节点形状：列表推导 四字段（表达式/目标/迭代/条件），
    目标裸变量（in 成员运算不被吞），条件列表保序。"""
    bootvm.call("输出清空")
    toks = bootvm.call("扫描",
                       "b = [x * x for x in nums if x > 1]\n", 0, 1, 1, [])
    prog = bootvm.call("parse", toks)
    decl = prog["声明"][0]
    node = decl["值"]
    assert node["类型"] == "列表推导"
    # boot 做Variable 节点带 是占位 字段，锁字段级形状而非全字典相等
    assert node["目标"]["类型"] == "变量" and node["目标"]["名"] == "x"
    assert node["迭代"]["类型"] == "变量" and node["迭代"]["名"] == "nums"
    assert len(node["条件"]) == 1
    assert node["条件"][0]["类型"] == "二元运算"


def test_host_parse_list_comp_mirror():
    """宿主面同源：ast.ListComp 四字段镜像（boot conv 面
    列表推导→ListComp 由 test_parser_parity_phase28 golden 35 全文件锁）。"""
    prog = py_parse("b = [x * x for x in nums if x > 1]\n")
    decl = prog.decls[0]
    node = decl.value
    assert isinstance(node, ast.ListComp)
    assert isinstance(node.target, ast.Variable) and node.target.name == "x"
    assert isinstance(node.iter, ast.Variable) and node.iter.name == "nums"
    assert len(node.ifs) == 1


def test_double_for_boot_truthified(bootvm):
    """双 for 推导：双面求值一致（31b 真化退役原 30d 诚实报错分歧登记——
    原 boot MathaRuntimeError「推导式期望列表右括号 ]」vs 宿主 ParseError
    两形态均不复存在）。VM 面同值由 test_selfhost_language_phase31
    test_31b_multi_comp_three_faces 锁。"""
    src = "输出([a + b for a in [1, 2] if a > 0 for b in [10]])"
    assert _boot_run(bootvm, src) == [[11, 12]]
    assert _host_run(src) == [[11, 12]]
