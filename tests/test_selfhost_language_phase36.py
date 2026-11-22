# -*- coding: utf-8 -*-
"""阶段 36 语言收敛锁（mb/boot 面收口批——35-① + 34-②③⑤ 退役）。

36a 表达式位花括号 if（34-② 退役）：parser.matha 解析if表达式 补花括号
  臂（宿主 _parse_if_expr_impl 3880-3890 语句形式分支同构——块体经
  解析语句列表 产 程序节点，else 附着仅 否则，无则 假分支=null）；
  interp.matha 求值 补 程序 臂（VM² 镜像）。五形态 + 输出尾块值 +
  语句位 if 中性回归三面同判。

36b 块尾函数定义块值 null（34-③ 退役）：interp_matha 执行语句/执行声明
  函数定义臂 + interp.matha 执行函数定义 改返 (null, env2)（宿主
  _BLOCK_TAIL_STMT_NODES 块值模型对齐——函数仍绑定入 env，仅值面不
  回传）；boot 编译器 _发射块末条 _是语句类型 面既有 PUSH_NULL 零改动。

36c 字典裸键归一（34-⑤ 退役）：interp_matha/interp.matha 求值字典
  _字典键 臂（宿主 interp.py 2947-2951 键面同构）——Variable 键节点取
  名 字符串，其余键照常求值；boot 编译器 _发射字典 既有归一零改动。

36d 表达式位 let 元组绑定（35-① 退役）：interp_matha 求值/执行语句/
  执行声明 三臂 + 求值let元组/绑定求值let元组/_解构绑定元组（宿主
  _eval/_exec_stmt 镜像——闭包标记 4 元组错误文案归 function、表达式位
  三名绑定跳标记位 start=1 同判、语句位不跳标记长度面同判；块值 null）。
  VM² interp.matha 镜像面维持不对称（解构机族未进 interp.matha，
  35-② 登记口径承继——见 KNOWN_ISSUES 阶段 36）。

附带发现登记（登记不修，见 KNOWN_ISSUES 阶段 36）：
  vm 面 dict 字面量非字符串字面量键 str 归一（compiler.py _literal_key
  IntegerLit→str）→ d[2] 缺失键 null vs hi/mb int 键命中（vm 面
  d["2"] 反向命中）——语料约定引号键；boot 块值 Binding 尾
  { let x = 5 } 块值 5 vs vm/hi None（34-③ 同族 Binding 尾未真化）。
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.set_int_max_str_digits(0)

from pathlib import Path

from src.parser import parse as py_parse
from src.mbc.compiler import Compiler
from src.mbc.vm import VM
from src import ast_nodes as ast
from src.kernel import exec_api
from src.kernel.errors import MathaRuntimeError
from src import matha_bootstrap
from src import interp as host_interp

_ROOT = Path(__file__).resolve().parent.parent
_BOOT_FILES = ["matha/lexer.matha", "matha/stdlib.matha", "matha/parser.matha",
               "matha/runtime/matha_runtime.matha", "matha/interp_matha.matha"]
_CHAIN_NS_NAMES = ("词法器", "标准库", "语法器", "运行时引擎", "解释器")


def _strip_bom(src):
    return src.lstrip("\ufeff") if src and src[0] == "\ufeff" else src


def _hi_interp(src):
    try:
        outs, _ = host_interp.interpret(src)
        return outs, None
    except Exception as e:  # noqa: BLE001
        return None, e


def _boot_interp(src):
    """自举解释器面（matha_bootstrap：lexer/parser/stdlib/interp_matha 链）。

    strict=True：执行面异常如实上抛；解析面错误以输出行呈现（32 约定）。"""
    try:
        outs, _ = matha_bootstrap.interpret(src, strict=True)
        return outs, None
    except Exception as e:  # noqa: BLE001
        return None, e


def _three_faces(tag, src, want):
    outs, err = exec_api.run_checked(src)
    assert err is None and outs == want, (tag, "vm", outs, err)
    hi, hi_err = _hi_interp(src)
    assert hi_err is None and hi == want, (tag, "hi", hi, hi_err)
    mb, mb_err = _boot_interp(src)
    assert mb_err is None and mb == want, (tag, "mb", mb, mb_err)


def _three_err(tag, src, want):
    outs, err = exec_api.run_checked(src)
    assert err is not None and want in str(err), (tag, "vm", outs, err)
    hi, hi_err = _hi_interp(src)
    assert hi_err is not None and want in str(hi_err), (tag, "hi", hi, hi_err)
    mb, mb_err = _boot_interp(src)
    assert mb_err is not None and want in str(mb_err), (tag, "mb", mb, mb_err)


@pytest.fixture(scope="module")
def bootvm():
    """VM² 解释器面：宿主编译 interp_matha 链 → VM 运行（29d 同构）。"""
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
    r, env1 = bootvm.call("执行语句", prog, env0)
    return list(bootvm.call("输出快照")), r, env1


def _boot_err(bootvm, src):
    try:
        outs, _, _ = _boot_run(bootvm, src)
        return outs, None
    except Exception as e:  # noqa: BLE001
        return None, e


# ============================================================
# 36a 表达式位花括号 if（34-② 退役）
# ============================================================

_IF_BRACE_OK = [
    ("true",       "let x = if 1 { 2 } in 输出(x)", [2]),
    ("no_else",    "let x = if 0 { 2 } in 输出(x)", [None]),
    ("否则",       "let x = if 0 { 2 } 否则 { 3 } in 输出(x)", [3]),
    ("multi_stmt", "let x = if 1 { let a = 5\n a + 1 } in 输出(x)", [6]),
    ("func_body",  "func g() = if 1 { 2 }\n输出(g())", [2]),
    ("output_tail", "let x = if 1 { 输出(5)\n 6 } in 输出(x)", [5, 6]),
]


@pytest.mark.parametrize("tag,src,want", _IF_BRACE_OK, ids=[c[0] for c in _IF_BRACE_OK])
def test_36a_if_brace_expr_three_faces(tag, src, want):
    """表达式位花括号 if 六形态三面同判（34-② 解析拒绝退役）。"""
    _three_faces(tag, src, want)


def test_36a_stmt_if_brace_neutral():
    """语句位 if 花括号中性回归（解析if_stmt 既有路由不误伤）。"""
    _three_faces("stmt_if", 'if 1 { 输出("A") } else { 输出("B") }\n输出("尾")',
                 ["A", "尾"])


def test_36a_if_brace_vm_squared(bootvm):
    """VM² 解释器面（bootvm fixture）同判——正形态 + 无 else null 形态。"""
    for src, want in (("let x = if 1 { 2 } in 输出(x)\n", [2]),
                      ("let x = if 0 { 2 } in 输出(x)\n", [None]),
                      ("let x = if 0 { 2 } 否则 { 3 } in 输出(x)\n", [3])):
        outs, err = _boot_err(bootvm, src)
        assert err is None and outs == want, (src, outs, err)


# ============================================================
# 36b 块尾函数定义块值 null（34-③ 退役）
# ============================================================

def test_36b_block_tail_func_three_faces():
    """块尾 func 定义块值 null 三面同判（'<function>' 分歧退役）；
    块尾 func 后续调用正控（绑定不变）。"""
    _three_faces("let_blk", "let r = { func f() = 1 } in 输出(r)", [None])
    _three_faces("func_body", "func g() = {\n  func f() = 1\n}\n输出(g())", [None])
    _three_faces("blk_used", "let r = { func f() = 1\n f() } in 输出(r)", [1])


def test_36b_stmt_if_blk_func_neutral():
    """语句位 if 块内 func 定义中性回归（块值不浮现）。"""
    _three_faces("if_blk", 'if 1 {\n  func f() = 1\n}\n输出("尾")', ["尾"])


def test_36b_block_tail_func_vm_squared(bootvm):
    """VM² 解释器面同判——块尾 func 定义块值 null。"""
    for src, want in (("let r = { func f() = 1 } in 输出(r)\n", [None]),
                      ("func g() = {\n  func f() = 1\n}\n输出(g())\n", [None])):
        outs, err = _boot_err(bootvm, src)
        assert err is None and outs == want, (src, outs, err)


# ============================================================
# 36c 字典裸键归一（34-⑤ 退役）
# ============================================================

def test_36c_dict_bare_key_three_faces():
    """裸键析为键字符串三面同判（未定义变量 / 值键分歧退役）；
    引号键与已定义名正控。"""
    _three_faces("bare", "let d = {a: 1} in { 输出(d) }", [{"a": 1}])
    _three_faces("bare_shadow", "let a = 1 in 输出({a: 2})", [{"a": 2}])
    _three_faces("bare_lookup", 'let d = {x: 5} in 输出(d["x"])', [5])
    _three_faces("quoted", 'let d = {"a": 1} in { 输出(d) }', [{"a": 1}])


def test_36c_dict_bare_key_vm_squared(bootvm):
    """VM² 解释器面同判——裸键字符串化。"""
    outs, err = _boot_err(bootvm, "let d = {a: 1} in { 输出(d) }\n")
    assert err is None and outs == [{"a": 1}], (outs, err)


# ============================================================
# 36d 表达式位 let 元组绑定（35-① 退役）
# ============================================================

def test_36d_let_tuple_expr_three_faces():
    """表达式位 let 元组绑定三面同判（未知表达式类型退役）；
    语句位与块尾中性回归（绑定生效 / 块值 null）。"""
    _three_faces("expr", "let (a, b) = [1, 2] in 输出(a + b)", [3])
    _three_faces("no_body", "let r = (let (a, b) = [1, 2] in a) in 输出(r)", [1])
    _three_faces("stmt", "let (a, b) = [3, 4]\n输出(a + b)", [7])
    _three_faces("blk_tail", "let r = { let (a, b) = [1, 2] } in 输出(r)", [None])


@pytest.mark.parametrize("tag,src,want", [
    ("short", "输出(let (a, b) = [1] in a)", "解构失败：期望 2 个元素，实际 list"),
    ("long", "输出(let (a, b) = [1, 2, 3] in a)", "解构失败：期望 2 个元素，实际 list"),
    ("nonsseq", "输出(let (a, b) = 5 in a)", "解构失败：期望 2 个元素，实际 int"),
    ("str", "输出(let (a, b) = \"hi\" in a)", "解构失败：期望 2 个元素，实际 str"),
], ids=["short", "long", "nonsseq", "str"])
def test_36d_let_tuple_fail_three_faces(tag, src, want):
    """解构失败诚实报错三面同文案（vm err 对象 / hi·mb 异常）。"""
    _three_err(tag, src, want)


@pytest.mark.parametrize("tag,src", [
    ("func", "func f(x) = x\nlet (a, b) = f in 输出(a)"),
    ("lambda", "let (a, b) = (x) => x * 2 in 输出(a)"),
], ids=["func", "lambda"])
def test_36d_let_tuple_function_tname_three_faces(tag, src):
    """函数值解构 tname 归 "function" 三面同判（boot 闭包标记 List
    ["__closure__",…] 与 vm Closure / hi FuncDef·Lambda 同文案）。"""
    _three_err(tag, src, "解构失败：期望 2 个元素，实际 function")


def test_36d_let_tuple_vm_squared(bootvm):
    """VM² 解释器面同判——表达式位/语句位/错误文案。"""
    for src, want in (("let (a, b) = [1, 2] in 输出(a + b)\n", [3]),
                      ("let (a, b) = [3, 4]\n输出(a + b)\n", [7])):
        outs, err = _boot_err(bootvm, src)
        assert err is None and outs == want, (src, outs, err)
    outs, err = _boot_err(bootvm, "输出(let (a, b) = [1] in a)\n")
    assert err is not None and "解构失败：期望 2 个元素，实际 list" in str(err), \
        (outs, err)


# ============================================================
# 附带发现登记锁（登记不修）
# ============================================================

def test_36x_vm_dict_intkey_registration():
    """登记锁（维持）：vm 面 dict 字面量非字符串字面量键 str 归一
    （compiler.py _literal_key IntegerLit→str）→ d[2] 缺失键 null
    （29b-④ 语义）vs hi/mb int 键命中；vm 面 d["2"] 反向命中。
    语料约定引号键，登记不修。"""
    src = 'let d = {"k": 1, 2: "v"} in 输出(d["k"])\n输出(d[2])'
    outs, err = exec_api.run_checked(src)
    assert err is None and outs == [1, None], ("vm", outs, err)
    hi, hi_err = _hi_interp(src)
    assert hi_err is None and hi == [1, "v"], ("hi", hi, hi_err)
    mb, mb_err = _boot_interp(src)
    assert mb_err is None and mb == [1, "v"], ("mb", mb, mb_err)
    rev = 'let d = {2: "v"} in 输出(d["2"])'
    outs, err = exec_api.run_checked(rev)
    assert err is None and outs == ["v"], ("vm", outs, err)


def test_36x_blk_tail_binding_registration():
    """登记锁（维持）：boot 块值 Binding 尾 { let x = 5 } 块值 5
    vs vm/hi None（宿主 _BLOCK_TAIL_STMT_NODES 面）——34-③ 同族
    Binding 尾未真化，登记不修（let 元组尾已随 36d 真化对齐）。"""
    src = "let r = { let x = 5 } in 输出(r)"
    outs, err = exec_api.run_checked(src)
    assert err is None and outs == [None], ("vm", outs, err)
    hi, hi_err = _hi_interp(src)
    assert hi_err is None and hi == [None], ("hi", hi, hi_err)
    mb, mb_err = _boot_interp(src)
    assert mb_err is None and mb == [5], ("mb", mb, mb_err)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
