# -*- coding: utf-8 -*-
"""阶段 34 语言收敛锁（六项登记分歧全族真化——33-①②③④ + 32-⑨⑪ 退役）。

34a 尾逗号全族（33-① 退役）：33a 单元素 (1,) 真化扩展到全族——多元素
  (1, 2,) 与调用位 f(1, 2,) boot 面改发宿主精确文案「期望表达式
  (got PUNCT_RPAREN ')')」（此前通用「期望表达式，实际 ）」），解析
  错误以输出行呈现不上抛（32 约定）；列表尾逗号 [1, 2,] 三面合法。

34b 语句位 if `[` 路由（28-⑦/33-② 退役）：宿主 _parse_if/_parse_while
  条件位加 _in_cond_value 值语境旗标（27f 同款先例）——`if [1] { … }`
  条件析为列表字面量而非输出命令（boot 面此前已正确，零改动）。
  vm 面此前漏出条件值 outs=[1,'x'] vs hi/mb ['x'] 三面分歧退役。

34c in 左侧四面同文案（33-③ 退役）：字符串容器+非字符串左侧——
  vm._op_in / hi（interp.py 二元运算 in 臂）/ mb _成员判断 /
  VM² 镜像（interp.matha _类型名）四面统一 boot 中文文案
  「in 左侧需为字符串，实际 int/list/NoneType」；native 面诚实报错
  （非零退出 + stderr 同文案）+ try/catch 可捕获形态锁在
  tests/test_native.py（test_in_str_left_nonstr_registered_divergence
  / test_in_string_left_error_text_matches_vm）。

34d slice 元组 vm 收敛对齐宿主（33-④ 退役）：vm _builtin_slice 容器
  守卫（仅 str/list 透传，其余诚实报错「slice() 需要字符串或列表」）
  + native fn:slice 容器守卫（try/catch 可捕获，tests/test_native.py
  test_slice_builtin_tuple_error_matches_vm）；str/list 透传形态不变，
  下标切片 xs[a:b] 共用路径不受守卫影响（元组切片返元组维持）。

34e boot for (k,v) 多变量目标真化（32-⑨ 退役）：boot parser.matha
  解析for_stmt 括号解构目标（"变量" String=单变量 | List=名单）+
  interp_matha 执行for循环 _解构绑定（宿主 _exec_for_stmt 镜像：
  Tuple/List 且长度匹配逐位绑定，否则「解构失败：期望 N 个元素，
  实际 <类型名>」）；字典源 (k,v) 对产出三面+VM² 同判。boot 编译器
  发射面（_分配循环变量）List 目标诚实拒绝「boot 编译器 for 解构
  目标暂未支持」——UNPACK_SEQ 镜像未做，登记维持。

34f hi 面 func 值求值真化（32-⑪ 退役）：块尾 func 定义块值 → None
  （src/interp.py _eval 补 FuncDef 臂；vm 面同判 None）。mb 面
  表达式位 if-then 缺失与 func 体块尾 '<function>' 两登记由阶段 36
  真化退役（parser.matha 花括号臂 + boot 函数定义块值 null）。

附带发现（登记不修，见 KNOWN_ISSUES 阶段 34；34-⑤ 已由阶段 36
  真化退役——boot 求值字典 _字典键 臂）：boot 字典字面量裸键
  {a: 1} 析为变量引用（未定义变量 'a'）vs hi 面字符串键；引号键
  {"a": 1} 三面一致。vm 面编译路径 UNPACK_SEQ 长度不匹配宽松补 null
  登记（34e 收官时）已由 35a S1 真化退役——UNPACK_SEQ 长度守卫 +
  native unpack 严格化 + vm.matha 解包守卫三执行体同判（本档
  test_34e_for_pair_fail_vm_true 真化退役锁；见
  tests/test_selfhost_language_phase35.py）。
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
_COMP_FILES = ["matha/lexer.matha", "matha/stdlib.matha", "matha/parser.matha",
               "matha/interp.matha", "matha/compiler_matha.matha"]
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
# 34a 尾逗号全族（33-① 退役）
# ============================================================

_WANT_TAIL = "期望表达式 (got PUNCT_RPAREN ')')"


def _tail_reject(tag, src):
    outs, err = exec_api.run_checked(src)
    assert err is not None and _WANT_TAIL in str(err), (tag, "vm", outs, err)
    hi, hi_err = _hi_interp(src)
    assert hi_err is not None and _WANT_TAIL in str(hi_err), (tag, "hi", hi, hi_err)
    mb, mb_err = _boot_interp(src)
    assert mb_err is None and any(_WANT_TAIL in str(o) for o in (mb or [])), \
        (tag, "mb", mb, mb_err)


def test_34a_multi_tail_comma_three_faces():
    """多元素尾逗号 (1, 2,) 三面诚实拒绝同文案（vm/hi 带 L:C 前缀，
    mb 输出行呈现无前缀——boot 解析错误通道约定）。"""
    _tail_reject("multi_tail", "输出((1, 2,))\n")


def test_34a_call_tail_comma_three_faces():
    """调用位尾逗号 f(1, 2,) 三面诚实拒绝同文案。"""
    _tail_reject("call_tail", "func f(a, b) = a + b\n输出(f(1, 2,))\n")


def test_34a_single_tail_consistency():
    """单元素尾逗号 (1,) 与 33a 锁同文案（全族一致性冒烟）。"""
    _tail_reject("single_tail", "输出((1,))\n")


def test_34a_list_tail_comma_three_faces():
    """列表尾逗号 [1, 2,] 三面合法（尾逗号真化不误伤列表族）。"""
    _three_faces("list_tail", "输出([1, 2,])\n", [[1, 2]])


# ============================================================
# 34b 语句位 if `[` 路由（28-⑦/33-② 退役）
# ============================================================

def test_34b_if_list_cond_three_faces():
    """if [1] { … } else { … }：条件析为列表字面量，三面 ['x']
    （vm 面此前漏出条件值 [1,'x'] 分歧退役；宿主 _in_cond_value
    旗标，boot 面既有正确行为零改动）。"""
    _three_faces("if_list_t", 'if [1] { 输出("x") } else { 输出("y") }\n', ["x"])
    _three_faces("if_list_f", 'if [] { 输出("x") } else { 输出("y") }\n', ["y"])


def test_34b_while_list_cond_three_faces():
    """while [] { … }：空列表条件零迭代三面同判（真值归一 33b 承继）。"""
    _three_faces("while_empty", 'while [] { 输出("n") }\n输出("尾")\n', ["尾"])


def test_34b_if_list_cond_vm2(bootvm):
    """VM² 解释器面同判（boot 解析器面既有行为镜像）。"""
    outs, err = _boot_err(
        bootvm, 'if [1] { 输出("x") } else { 输出("y") }\n')
    assert err is None and outs == ["x"], ("if_list_vm2", outs, err)


# ============================================================
# 34c in 左侧四面同文案（33-③ 退役；native 面 test_native.py）
# ============================================================

_IN_LEFT_CASES = [
    ("int_left", '输出(1 in "abc")', "in 左侧需为字符串，实际 int"),
    ("list_left", '输出([1] in "abc")', "in 左侧需为字符串，实际 list"),
    ("null_left", '输出(null in "abc")', "in 左侧需为字符串，实际 NoneType"),
]


def test_34c_in_str_left_error_three_faces():
    """字符串容器+非字符串左侧：vm/hi/mb 三面同 boot 中文文案。"""
    for tag, src, want in _IN_LEFT_CASES:
        outs, err = exec_api.run_checked(src)
        assert err is not None and want in str(err), (tag, "vm", outs, err)
        hi, hi_err = _hi_interp(src)
        assert hi_err is not None and want in str(hi_err), (tag, "hi", hi, hi_err)
        mb, mb_err = _boot_interp(src)
        assert mb_err is not None and want in str(mb_err), (tag, "mb", mb, mb_err)


def test_34c_in_str_left_error_vm2(bootvm):
    """VM² 解释器面同文案（interp.matha _类型名 小写面镜像）。"""
    for tag, src, want in _IN_LEFT_CASES:
        outs, err = _boot_err(bootvm, src)
        assert err is not None and want in str(err), (tag, "vm2", outs, err)


def test_34c_in_str_left_positive_control():
    """正控：字符串左侧成员判断不受守卫影响（三面 命中/未中）。"""
    _three_faces("in_pos", '输出("ell" in "hello")\n输出("x" in "hello")\n',
                 [True, False])


# ============================================================
# 34d slice 元组四面（33-④ 退役；native 面 test_native.py）
# ============================================================

_WANT_SLICE = "slice() 需要字符串或列表"


def test_34d_slice_tuple_error_three_faces():
    """slice((1,2,3), 0, 2)：vm/hi/mb 三面诚实报错同文案
    （vm 此前宽松返元组分歧退役）。"""
    src = "输出(slice((1, 2, 3), 0, 2))"
    outs, err = exec_api.run_checked(src)
    assert err is not None and _WANT_SLICE in str(err), ("vm", outs, err)
    hi, hi_err = _hi_interp(src)
    assert hi_err is not None and _WANT_SLICE in str(hi_err), ("hi", hi, hi_err)
    mb, mb_err = _boot_interp(src)
    assert mb_err is not None and _WANT_SLICE in str(mb_err), ("mb", mb, mb_err)


def test_34d_slice_tuple_error_vm2(bootvm):
    """VM² 解释器面同文案（应用内建 slice 臂 _切片值 Tuple 诚实拒绝）。"""
    outs, err = _boot_err(bootvm, "输出(slice((1, 2, 3), 0, 2))")
    assert err is not None and _WANT_SLICE in str(err), ("vm2", outs, err)


def test_34d_slice_passthrough_three_faces():
    """正控：str/list 透传形态不变（三面）。"""
    _three_faces("slice_str", '输出(slice("abcdef", 1, 3))', ["bc"])
    _three_faces("slice_list", "输出(slice([1, 2, 3, 4], 1, 3))", [[2, 3]])


def test_34d_subscript_tuple_slice_intact():
    """下标切片共用路径不受守卫影响：元组 (1, 2, 3)[1:3] 返 (2, 3)。"""
    _three_faces("sub_tuple", "输出((1, 2, 3)[1:3])", [(2, 3)])


# ============================================================
# 34e boot for (k,v) 多变量目标（32-⑨ 退役）
# ============================================================

_PAIR = ('let xs = [[1, "a"], [2, "b"]] in {\n'
         "  for (k, v) in xs {\n"
         "    输出(k)\n"
         "    输出(v)\n"
         "  }\n"
         "}\n")
_TUPLES = ('let xs = [(1, 2), (3, 4)] in {\n'
           "  for (a, b) in xs {\n"
           "    输出(a + b)\n"
           "  }\n"
           "}\n")
_DICT = ('let d = {"a": 1, "b": 2} in {\n'
         "  for (k, v) in d {\n"
         "    输出(k)\n"
         "    输出(v)\n"
         "  }\n"
         "}\n")
_FAIL = ('let xs = [[1, 2], [3]] in {\n'
         "  try {\n"
         "    for (k, v) in xs {\n"
         "      输出(k)\n"
         "    }\n"
         "  } catch (e) {\n"
         "    输出(e)\n"
         "  }\n"
         "}\n")
_SINGLE = "let xs = [1, 2, 3] in {\n  for i in xs {\n    输出(i)\n  }\n}\n"
_WANT_DESTRUCT = "解构失败：期望 2 个元素，实际 list"


def test_34e_for_pair_list_three_faces():
    """列表对源解构逐位绑定：hi/mb/VM² 同判 [1, 'a', 2, 'b']。"""
    _three_faces("pair_list", _PAIR, [1, "a", 2, "b"])


def test_34e_for_pair_tuple_three_faces():
    """元组对源解构：hi/mb 三面 [3, 7]。"""
    _three_faces("pair_tuple", _TUPLES, [3, 7])


def test_34e_for_pair_dict_three_faces():
    """字典源 (k, v) 对解构：hi/mb/VM² 同判 ['a', 1, 'b', 2]
    （_for迭代源 Dict → ('k', v) 对，31d 语义承继）。"""
    _three_faces("pair_dict", _DICT, ["a", 1, "b", 2])


def test_34e_for_pair_fail_hi_mb():
    """长度不匹配诚实报错「解构失败：期望 2 个元素，实际 list」hi/mb 同文案
    （宿主 _exec_for_stmt 文案镜像，try/catch 可捕获）。"""
    hi, hi_err = _hi_interp(_FAIL)
    assert hi_err is None and hi == [1, _WANT_DESTRUCT], ("hi", hi, hi_err)
    mb, mb_err = _boot_interp(_FAIL)
    assert mb_err is None and mb == [1, _WANT_DESTRUCT], ("mb", mb, mb_err)


def test_34e_for_pair_fail_vm_true():
    """vm 面长度不匹配诚实报错同文案（35a S1 真化退役锁——34e 旧登记锁
    「vm 宽松补 null」退役：UNPACK_SEQ 长度守卫三执行体真化，vm/hi/mb
    三面同判 [1, 解构失败文案]）。"""
    _three_faces("pair_fail", _FAIL, [1, _WANT_DESTRUCT])


def test_34e_for_single_regression():
    """单变量 for 不受解构形态分派影响（String 形态直绑回归锁）。"""
    _three_faces("single", _SINGLE, [1, 2, 3])


def test_34e_for_pair_vm2(bootvm):
    """VM² 解释器面四形态同判（解析 + 执行解构绑定镜像）。"""
    for tag, src, want in [("pair", _PAIR, [1, "a", 2, "b"]),
                           ("tuple", _TUPLES, [3, 7]),
                           ("dict", _DICT, ["a", 1, "b", 2]),
                           ("fail", _FAIL, [1, _WANT_DESTRUCT]),
                           ("single", _SINGLE, [1, 2, 3])]:
        outs, err = _boot_err(bootvm, src)
        assert err is None and outs == want, (tag, "vm2", outs, err)


def test_34e_boot_compiler_pair_emits_unpack_seq(bvm):
    """真化退役锁（35b S2——34-①「boot 编译器 for 解构目标暂未支持」退役）：
    boot 编译器 for 解构目标发射真 UNPACK_SEQ（87）+ 逆序存储，不再诚实
    拒绝；stage2↔stage3 逐位一致与 M3V 运行面真跑锁归
    tests/test_selfhost_language_phase35.py（对拍/运行基础设施所在）。"""
    src = 'd = {"a": 1}\ns = ""\nfor (k, v) in d {\n  s = s + k\n}\n输出(s)\n'
    d = bvm.call("编译", _strip_bom(src))
    ops = [x[0] for x in d["主码"]]
    i87 = ops.index(87)
    stores = [x for x in d["主码"][i87 + 1:] if x[0] == 24][:2]
    v_idx = d["常量"].index("v")
    k_idx = d["常量"].index("k")
    assert [x[1] for x in stores] == [v_idx, k_idx], \
        ([x[1] for x in stores], v_idx, k_idx)


# ============================================================
# 34f hi 面 func 值求值真化（32-⑪ 退役）
# ============================================================

def test_34f_block_tail_funcdef_vm_hi():
    """块尾 func 定义块值 → None：vm/hi 同判（hi 此前崩
    「暂不支持求值: FuncDef」分歧退役）。"""
    src = "输出(if 1 { func g(x) = x })\n"
    outs, err = exec_api.run_checked(src)
    assert err is None and outs == [None], ("vm", outs, err)
    hi, hi_err = _hi_interp(src)
    assert hi_err is None and hi == [None], ("hi", hi, hi_err)


def test_34f_block_tail_funcdef_mb_true():
    """真化改锁（34-② 退役）：mb 面表达式位 if 无 then 花括号形态解析
    真化（parser.matha 解析if表达式 花括号臂，宿主 _parse_if_expr_impl
    3880-3890 同构）——块尾 func 定义块值 null（36b 同批真化）三面同判。"""
    src = "输出(if 1 { func g(x) = x })\n"
    outs, err = exec_api.run_checked(src)
    assert err is None and outs == [None], ("vm", outs, err)
    hi, hi_err = _hi_interp(src)
    assert hi_err is None and hi == [None], ("hi", hi, hi_err)
    mb, mb_err = _boot_interp(src)
    assert mb_err is None and mb == [None], ("mb", mb, mb_err)


def test_34f_funcbody_tail_funcdef_true():
    """真化改锁（34-③ 退役）：func 体块尾 func 定义块值 null 三面同判
    ——boot 面 执行语句/执行声明 函数定义臂改返 null（宿主
    _BLOCK_TAIL_STMT_NODES 块值模型对齐，函数仍绑定入 env）。"""
    src = "func g() = {\n  func f() = 1\n}\n输出(g())\n"
    _three_faces("funcbody_tail", src, [None])
    blk = "let r = { func f() = 1 } in 输出(r)\n"
    _three_faces("let_blk_tail", blk, [None])
    used = "let r = { func f() = 1\n f() } in 输出(r)\n"
    _three_faces("blk_tail_used", used, [1])


def test_34f_statement_block_funcdef_neutral():
    """语句位 if 块内 func 定义三面中性（块值不浮现，零扰动回归）。"""
    _three_faces("if_blk", 'if 1 {\n  func f() = 1\n}\n输出("尾")\n', ["尾"])


# ============================================================
# 附带发现登记锁：boot 字典字面量裸键（登记不修）
# ============================================================

def test_34x_dict_bare_key_true():
    """真化改锁（34-⑤ 退役）：boot 字典字面量裸键 {a: 1} 析为键字符串
    "a"（interp_matha/interp.matha 求值字典 _字典键 臂，宿主 interp.py
    2947-2951 键面同构）——未定义变量分歧退役三面同判；引号键维持。
    vm 面非字符串字面量键分歧已随 37d 自然键真化退役，
    见 test_selfhost_language_phase36.test_36x_vm_dict_intkey_true。"""
    bare = "let d = {a: 1} in { 输出(d) }\n"
    _three_faces("dict_bare", bare, [{"a": 1}])
    quoted = 'let d = {"a": 1} in { 输出(d) }\n'
    _three_faces("dict_quoted", quoted, [{"a": 1}])


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
