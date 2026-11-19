# -*- coding: utf-8 -*-
"""阶段 29d Track A：自举执行面轻中档锁（boot 面 5 文件链 + 宿主面对拍）。

bootvm = lexer+stdlib+parser+runtime+interp_matha 五文件链（host 编译单模块 VM），
逐用例 输出清空 → 扫描 → parse → 注册内建 → 执行语句 → 输出快照；
宿主面 host_interp.interpret 同源码对拍。判据：

  ① 输出语义矩阵（P1-P13）：双面输出归一相等；P4/P6a/P6b 为双面一致
     的遗留语义实测值（空输出记 0 / 输出追踪双记），P5 顶层 match 逗号
     形态双面解析器同拒绝（解析层分歧非执行面，锁双面同拒）；
  ② 模块/use 导入（29d 模块面）：双模块 use 标准库 多名导入（len 走
     内建回退——stdlib ns 无 len，宿主 _exec_use 第三回退镜像）+ VM 闭包
     经语言级动态调用 + 兄弟模块导入 + 严格隔离 ns 键（本地名表：函数/
     绑定/let 绑定，不含 use 导入名）+ 纯语料 球体积.matha 双面 []；
  ③ 诚实报错文案对拍：缺名（模块 'X' 中未找到 'Y'）/ 缺模块（未找到
     模块 'X'）与宿主 _exec_use 同文案；跨文件 use 内核（链外模块）boot
     面诚实拒绝——宿主面自动从 matha/os/kernel.matha 装载成功（24a 双面
     可达），sweep 驱动链扩展为后续工作（登记面）；
  ④ 环境包含 自包含锁（29d：此前仅 interp.matha 定义、29d 链无该文件，
     语句位二元运算赋值 LOAD_GLOBAL 潜伏崩溃）；下标求值分支（求值 此前
     无 "下标"——任何含 a[i]/d["k"] 语料 boot 面未知表达式类型）；
  ⑤ 复位协议（输出清空→快照==[]）+ 公式库登记（__公式库__ 单条目）+
     宿主装载（matha_bootstrap._get_interp 链上 输出快照 可达）；
  ⑥ 轻中档语料子集：matha/library/core 7 文件双面输出对拍。
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


def _strip_bom(src):
    return src.lstrip("\ufeff") if src and src[0] == "\ufeff" else src


_CHAIN_NS_NAMES = ("词法器", "标准库", "语法器", "运行时引擎", "解释器")


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
    # 链模块 ns 预绑定（driver 面）：链装载时 VM globals 持有各模块命名空间
    # dict（宿主编译 ModuleDecl 产物），逐文件绑入 env0 供 use 导入查表。
    # 只绑定在场的链模块名——链缺文件时该名不可用，use 诚实报未找到模块。
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
    r, env1 = bootvm.call("执行语句", prog, env0)
    return list(bootvm.call("输出快照")), r, env1


def _host_run(src):
    outs, trace = host_interp.interpret(src)
    return outs


def _norm(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, (list, tuple)):
        return [_norm(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _norm(x) for k, x in v.items()}
    return v


def _both(bootvm, src):
    b_err = h_err = None
    b_outs = h_outs = None
    try:
        b_outs = _boot_run(bootvm, src)[0]
    except Exception as e:
        b_err = f"{type(e).__name__}: {e}"
    try:
        h_outs = _host_run(src)
    except Exception as e:
        h_err = f"{type(e).__name__}: {e}"
    return b_outs, b_err, h_outs, h_err


# ① 输出语义矩阵（P5 双面同拒单独锁）
_OUTPUT_MATRIX = [
    ("P1 输出语句", "输出(41)", [41]),
    ("P2 内建链式", "let a = 输出(5) + 1 in 输出(a)", [5, 6]),
    ("P3 print", "print(7)", [7]),
    ("P4 空输出（双面遗留语义一致值）", "输出()", [0]),
    ("P6a GenTrail（双面双记一致）", "#：[输出(3)]", [3, 3]),
    ("P6b 裸Trail（双面双记一致）", "[输出(3)]", [3, 3]),
    ("P7 GenOut", "#：输出(9)", [9]),
    ("P8 公式并存", "#1：？单价 * ？数量 = ？总价\n输出(41)", [41]),
    ("P10 for循环", "for x in [1, 2, 3] {\n  输出(x)\n}", [1, 2, 3]),
    ("P11 while循环", "i = 0\nwhile i < 3 {\n  输出(i)\n  i = i + 1\n}", [0, 1, 2]),
    ("P12 函数值归一", "f = (x) => x + 1\n输出(f)", ["<function>"]),
    ("P13 嵌套内建", "输出(输出(1) + 输出(2))", [1, 2, 3]),
]


@pytest.mark.parametrize(("name", "src", "expect"), _OUTPUT_MATRIX,
                         ids=[c[0] for c in _OUTPUT_MATRIX])
def test_output_matrix(bootvm, name, src, expect):
    b_outs, b_err, h_outs, h_err = _both(bootvm, src)
    assert b_err is None, f"boot 面: {b_err}"
    assert h_err is None, f"宿主面: {h_err}"
    assert _norm(b_outs) == _norm(expect), f"boot 输出 {b_outs!r} != {expect!r}"
    assert _norm(h_outs) == _norm(expect), f"宿主输出 {h_outs!r} != {expect!r}"


def test_top_level_match_both_refuse(bootvm):
    src = "match 2 { 1 => 10, _ => 20 }"
    b_outs, b_err, h_outs, h_err = _both(bootvm, src)
    assert b_err is not None and h_err is not None
    assert "期望 }" in b_err, f"boot 拒绝文案: {b_err}"
    assert "期望 }" in h_err, f"宿主拒绝文案: {h_err}"


# ② 模块/use 导入面
_M1 = """module 试区 {
  use 标准库 { len | str | 原地设置 }
  func 加一(x) -> Int = len([x]) + x
  输出(加一(41))
  输出(str(7))
  let 盒 = [1, 2]
  let 忽略 = 原地设置(盒, 0, 99)
  输出(盒[0])
}
module 试区二 {
  use 试区 { 加一 }
  输出(加一(100))
}
"""


def test_module_use_import_dual_face(bootvm):
    b_outs, b_err, h_outs, h_err = _both(bootvm, _M1)
    assert b_err is None, f"boot 面: {b_err}"
    assert h_err is None, f"宿主面: {h_err}"
    assert _norm(b_outs) == [42.0, "7", 99.0, 101.0], f"boot 输出 {b_outs!r}"
    assert _norm(h_outs) == [42.0, "7", 99.0, 101.0], f"宿主输出 {h_outs!r}"


def test_module_ns_strict_isolation(bootvm):
    _, _, env1 = _boot_run(bootvm, _M1)
    ns = next((p[1] for p in env1 if p[0] == "试区"), None)
    assert isinstance(ns, dict), f"试区 ns 未登记: {type(ns).__name__}"
    assert sorted(ns.keys()) == ["加一", "忽略", "盒"], f"ns 键 {sorted(ns.keys())}"
    assert "len" not in ns and "str" not in ns, "use 导入名不得进 ns（严格隔离）"


def test_pure_module_corpus(bootvm):
    src = (_ROOT / "matha/library/core/球体积.matha").read_text(encoding="utf-8")
    b_outs, b_err, h_outs, h_err = _both(bootvm, src)
    assert b_err is None, f"boot 面: {b_err}"
    assert h_err is None, f"宿主面: {h_err}"
    assert _norm(b_outs) == [] and _norm(h_outs) == []


# ③ ④ 诚实报错 + 自包含 + 下标
def test_use_missing_name_error_text(bootvm):
    src = "module 试错 {\n  use 标准库 { 不存在 }\n}\n"
    b_outs, b_err, h_outs, h_err = _both(bootvm, src)
    assert b_err is not None and h_err is not None
    assert "模块 '标准库' 中未找到 '不存在'" in b_err, f"boot 文案: {b_err}"
    assert "模块 '标准库' 中未找到 '不存在'" in h_err, f"宿主文案: {h_err}"


def test_use_missing_module_error_text(bootvm):
    src = "module 试错 {\n  use 幻影模块\n}\n"
    b_outs, b_err, h_outs, h_err = _both(bootvm, src)
    assert b_err is not None and h_err is not None
    assert "未找到模块 '幻影模块'" in b_err, f"boot 文案: {b_err}"
    assert "未找到模块 '幻影模块'" in h_err, f"宿主文案: {h_err}"


def test_cross_file_use_boot_refusal(bootvm):
    """跨文件 use（链外模块）：boot 面诚实拒绝；宿主面自动装载（信息面）。"""
    src = (_ROOT / "matha/library/os/进程管理.matha").read_text(encoding="utf-8")
    b_outs, b_err, h_outs, h_err = _both(bootvm, src)
    assert b_err is not None and "未找到模块 '内核'" in b_err, f"boot: {b_err}"
    assert h_err is None, "宿主面应自动装载 kernel.matha 成功"


def test_env_contains_self_contained(bootvm):
    stmt = {"类型": "二元运算", "运算符": "=",
            "左": {"类型": "变量", "名": "q"}, "右": {"类型": "整数", "值": 5}}
    env0 = bootvm.call("注册内建", bootvm.call("空环境"))
    v, env2 = bootvm.call("语句位赋值或表达式", stmt, env0)
    got = [p for p in env2 if p[0] == "q"]
    assert got, f"q 未绑定（v={v!r}）"
    assert float(got[0][1]) == 5.0


def test_subscript_eval_branch(bootvm):
    src = "let 盒 = [1, 2, 3] in 输出(盒[1])\n输出({\"键\": \"值\"}[\"键\"])"
    b_outs, b_err, h_outs, h_err = _both(bootvm, src)
    assert b_err is None, f"boot 面: {b_err}"
    assert h_err is None, f"宿主面: {h_err}"
    assert _norm(b_outs) == [2.0, "值"], f"boot 输出 {b_outs!r}"
    assert _norm(h_outs) == [2.0, "值"], f"宿主输出 {h_outs!r}"


# ⑤ 复位 / 登记 / 宿主装载
def test_reset_protocol(bootvm):
    bootvm.call("输出清空")
    snap = list(bootvm.call("输出快照"))
    assert snap == []


def test_formula_library_registered(bootvm):
    src = "#1：？单价 * ？数量 = ？总价\n输出(41)"
    _, _, env1 = _boot_run(bootvm, src)
    lib = next((p[1] for p in env1 if p[0] == "__公式库__"), None)
    assert lib is not None and len(lib) == 1, f"__公式库__ {lib!r}"


def test_host_bootstrap_load():
    from src import matha_bootstrap
    it = matha_bootstrap._get_interp()
    snap = list(it.call("输出快照"))
    assert snap == [], f"宿主装载链 输出快照 {snap!r}"


# ⑥ 轻中档语料子集（library/core 7 文件双面输出对拍）
_CORE_FILES = sorted((_ROOT / "matha" / "library" / "core").glob("*.matha"))


@pytest.mark.parametrize("path", _CORE_FILES, ids=[p.name for p in _CORE_FILES])
def test_corpus_core_subset(bootvm, path):
    src = path.read_text(encoding="utf-8")
    b_outs, b_err, h_outs, h_err = _both(bootvm, src)
    assert b_err is None, f"{path.name} boot 面: {b_err}"
    assert h_err is None, f"{path.name} 宿主面: {h_err}"
    assert _norm(b_outs) == _norm(h_outs), \
        f"{path.name} 输出分歧: boot={b_outs!r} host={h_outs!r}"
