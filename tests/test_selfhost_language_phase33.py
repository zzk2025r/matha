# -*- coding: utf-8 -*-
"""阶段 33 语言收敛锁（mb 面六项分歧三面/VM² 收口 + in 四面同文案）。

33a（拍板「boot 诚实拒绝对齐宿主」）：单元素尾逗号 (1,) 吞没退役——
  boot 解析器 解析括号消解 逗号分支补右括号守卫，(1,) 诚实拒绝
  「期望表达式 (got PUNCT_RPAREN ')')」（宿主=SPEC 不动：同文案带
  L:C 前缀，vm 面经宿主编译器同判；boot 解析错误以输出行呈现不上
  抛——32 期同约定）。多元素尾逗号 (1, 2,) 与调用位尾逗号维持 boot
  通用文案「期望表达式，实际 )」（登记不修，33 只收单元素吞没位）。

33b（拍板「全族对齐 Bool」）：mb 比较族九臂 =/==/!=/</>/<=/>= 与 not
  返 真/假 Bool（宿主/VM 比较面 Python bool 同判；此前 mb 面 1.0/0.0
  浮点三面分歧——32 登记④退役）。mb 条件路由真值归一：求值if/执行
  语句 if/while 经 真值 helper（null/假/0/0.0/""/空容器 → 假）——
  空容器条件 while 零迭代、if else 分支三面+VM² 同判（32 登记⑦
  退役）；链代码裸 if 表达式宿主 Python 真值维持（_条件全真 不动）。

33c（拍板「四面同文案」）：`in` 成员判断四面真化（32 登记③退役）——
  vm._op_in 容器守卫（src/mbc/vm.py）/ native 容器守卫（raise_rt
  可捕获，tests/test_native.py 锁）/ mb _成员判断（interp_matha）/
  VM² 镜像（interp.matha）：List/Tuple/Dict/Str 命中→真 未中→假；
  非容器右侧诚实报错「in 右侧需为序列/集合/字典，实际 int」四面同
  文案。登记：字符串容器+非字符串左侧文案分歧——vm/hi Python
  TypeError 形态 vs mb/VM²「in 左侧需为字符串」vs native 静默返
  False（KNOWN_ISSUES 阶段 33 登记不修，本档锁现状防漂移）。

33d（拍板「顺手真修 hi」）：hi 面 if 无 else 条件假 → null
  （src/interp.py IfExpr/IfStmt else 缺失臂补 None；此前宿主解释器
  面崩 NoneType；VM 面 None 同判）——三面+VM² 同判。

33e：mb type_of/_to_tuple 注册真化（32 登记⑤退役）——注册内建尾部
  绑定 + 应用内建委托宿主 BUILTINS（裸名宿主解析，type_of 返
  Int/Float/… 大写面三面同判）；VM² 面 func_type_of/func_to_tuple
  包装注册。sum 累加器 0 起（32 登记⑥退役）：sum([])=0 Int、
  全整数和 Int、浮点和浮点——三面+VM² 同判（stdlib.matha list_sum）。

33h（收官探针踩中，顺手真修）：slice 内建字符串臂真化——mb 面
  应用内建实 slice 臂此前无条件走 标准库.list_slice，字符串实参产出
  字符列表（split 块变 ['a'] 形）；33b 比较族提速后 golden 38 语料
  600s 预算内首次真跑完成，timeout→differ 漂移显形此根因。String 实参
  改走 31f _切片值 字符串臂（负回绕/端钳 Python 语义）、List 维持
  list_slice、Tuple/其他诚实报错「slice() 需要字符串或列表」（宿主
  =SPEC 同文案）。登记：slice() 元组实参 vm 面宽松返元组 vs hi/mb
  报错（KNOWN_ISSUES 阶段 33）。
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
# 33b 比较族九臂 + not → 真/假 Bool
# ============================================================

_CMP_FAMILY = ('输出(1 < 2)\n输出(2 < 1)\n输出(2 > 1)\n输出(1 > 2)\n'
               '输出(1 <= 1)\n输出(2 <= 1)\n输出(1 >= 1)\n输出(1 >= 2)\n'
               '输出(1 == 1)\n输出(1 == 2)\n输出(1 != 2)\n输出(1 != 1)\n'
               '输出(1 = 1)\n输出(1 = 2)\n输出(真 == 真)\n输出("a" == "b")\n'
               '输出("a" < "b")\n输出("b" < "a")')
_CMP_WANT = [True, False, True, False, True, False, True, False,
             True, False, True, False, True, False, True, False,
             True, False]

_NOT_FAMILY = ('输出(not 0)\n输出(not 1)\n输出(not 0.0)\n输出(not "a")\n'
               '输出(not "")\n输出(not null)\n输出(not [1])\n输出(not [])\n'
               '输出(not {"a": 1})\n输出(not (1, 2))\n'
               '输出(not 真)\n输出(not 假)')
_NOT_WANT = [True, False, True, False, True, True, False, True,
             False, False, False, True]


def test_33b_compare_family_bool_three_faces():
    """比较族九臂三面 Bool（mb 面此前 1.0/0.0 浮点——32 登记④退役）。"""
    _three_faces("cmp_family", _CMP_FAMILY, _CMP_WANT)


def test_33b_compare_family_bool_vm2(bootvm):
    """VM² 解释器面同判（interp.matha 编译入 VM，应用运算镜像臂）。"""
    outs, err = _boot_err(bootvm, _CMP_FAMILY)
    assert err is None and outs == _CMP_WANT, ("cmp_vm2", outs, err)


def test_33b_not_family_bool_three_faces():
    """not 家族三面 Bool：0/0.0/""/空容器/null falsy，真值 helper 同判。"""
    _three_faces("not_family", _NOT_FAMILY, _NOT_WANT)


def test_33b_not_family_bool_vm2(bootvm):
    outs, err = _boot_err(bootvm, _NOT_FAMILY)
    assert err is None and outs == _NOT_WANT, ("not_vm2", outs, err)


# ============================================================
# 33b 条件路由真值归一（空容器/零/null falsy）
# ============================================================

# 条件用变量绑定：语句位 if 以 [ 开头的字面量条件会被宿主解析器析为
# 输出命令（IfStmt.cond=Output(...)，vm 面旁路输出条件值 vs hi 面不求值
# ——既有解析器形态分歧，KNOWN_ISSUES 阶段 33 登记，与真值语义无关）。
_TRUTH_PROG = ('t1 = []\nt2 = [1]\n'
               'if t1 { 输出("x") } else { 输出("y") }\n'
               'if t2 { 输出("x") } else { 输出("y") }\n'
               'if "" { 输出("x") } else { 输出("y") }\n'
               'if 0 { 输出("x") } else { 输出("y") }\n'
               'if null { 输出("x") } else { 输出("y") }\n'
               'while t1 { 输出("n") }\n'
               'while "" { 输出("n") }\n'
               '输出("尾")')
_TRUTH_WANT = ["y", "x", "y", "y", "y", "尾"]


def test_33b_truthiness_routing_three_faces():
    """if/while 条件真值归一三面：空容器零迭代/else 分支（32 登记⑦退役）。"""
    _three_faces("truth", _TRUTH_PROG, _TRUTH_WANT)


def test_33b_truthiness_routing_vm2(bootvm):
    outs, err = _boot_err(bootvm, _TRUTH_PROG)
    assert err is None and outs == _TRUTH_WANT, ("truth_vm2", outs, err)


# ============================================================
# 33c `in` 成员判断四面
# ============================================================

_IN_PROG = ('输出(3 in [1, 2, 3])\n输出(4 in [1, 2, 3])\n'
            '输出("ell" in "hello")\n输出("x" in "hello")\n'
            '输出("a" in {"a": 1})\n输出("b" in {"a": 1})\n'
            '输出(1 in (1, 2))\n输出(3 in (1, 2))')
_IN_WANT = [True, False, True, False, True, False, True, False]


def test_33c_in_membership_three_faces():
    """in List/Str/Dict/Tuple 命中/未中 三面（mb 面此前「未知运算符: in」
    ——32 登记③退役）。"""
    _three_faces("in_members", _IN_PROG, _IN_WANT)


def test_33c_in_membership_vm2(bootvm):
    """VM² 面同判（interp.matha _成员判断 镜像）。"""
    outs, err = _boot_err(bootvm, _IN_PROG)
    assert err is None and outs == _IN_WANT, ("in_vm2", outs, err)


def test_33c_in_noncontainer_error_text_three_faces():
    """非容器右侧诚实报错三面同文案（vm 面 TypeError 前缀外均含本文）。"""
    src = "输出(1 in 5)"
    want = "in 右侧需为序列/集合/字典，实际 int"
    outs, err = exec_api.run_checked(src)
    assert err is not None and want in str(err), ("vm", outs, err)
    hi, hi_err = _hi_interp(src)
    assert hi_err is not None and want in str(hi_err), ("hi", hi, hi_err)
    mb, mb_err = _boot_interp(src)
    assert mb_err is not None and want in str(mb_err), ("mb", mb, mb_err)


def test_33c_in_noncontainer_error_vm2(bootvm):
    """VM² 面同文案（raise 面 MathaRuntimeError）。"""
    outs, err = _boot_err(bootvm, "输出(1 in 5)")
    assert err is not None and "in 右侧需为序列/集合/字典，实际 int" in str(err), \
        ("vm2", outs, err)


def test_33c_in_string_left_registered_divergence():
    """登记锁（不修）：字符串容器+非字符串左侧文案分歧——vm/hi Python
    TypeError 形态 vs mb/VM²「in 左侧需为字符串」vs native 静默返 False。
    KNOWN_ISSUES 阶段 33 登记；本锁防现状漂移。"""
    want_hi = "requires string as left operand"
    want_mb = "in 左侧需为字符串"
    src = '输出(1 in "abc")'
    outs, err = exec_api.run_checked(src)
    assert err is not None and want_hi in str(err), ("vm", outs, err)
    hi, hi_err = _hi_interp(src)
    assert hi_err is not None and want_hi in str(hi_err), ("hi", hi, hi_err)
    mb, mb_err = _boot_interp(src)
    assert mb_err is not None and want_mb in str(mb_err), ("mb", mb, mb_err)


# ============================================================
# 33d hi 面 if 无 else → null（VM 面 None 同判）
# ============================================================

def test_33d_if_no_else_expr_three_faces():
    """if 表达式无 else：条件假 → null（hi 面此前崩 NoneType；VM 面 None
    同判）；条件真 → then 值。"""
    _three_faces("noelse_f", "输出(if 1 > 2 then 42)", [None])
    _three_faces("noelse_t", "输出(if 1 < 2 then 42)", [42])


def test_33d_if_no_else_expr_vm2(bootvm):
    outs, err = _boot_err(bootvm, "输出(if 1 > 2 then 42)")
    assert err is None and outs == [None], ("noelse_vm2", outs, err)


def test_33d_if_no_else_stmt_three_faces():
    """语句位 if 无 else：条件假跳过块体续行（hi 面此前崩）。"""
    _three_faces("noelse_stmt", 'if 1 > 2 { 输出("x") }\n输出("尾")', ["尾"])


# ============================================================
# 33e sum 累加器 0 起 + type_of/_to_tuple 注册真化
# ============================================================

_SUM_PROG = ('输出(sum([]))\n输出(sum([1, 2, 3]))\n输出(sum([1.5, 2.5]))\n'
             '输出(type_of(sum([])))\n输出(type_of(sum([1, 2, 3])))')
_SUM_WANT = [0, 6, 4.0, "Int", "Int"]


def test_33e_sum_semantics_three_faces():
    """sum 三面：空表 0、全整数和 Int、浮点和浮点（mb 面此前 0.0 起浮点化
    ——32 登记⑥退役）。"""
    _three_faces("sum", _SUM_PROG, _SUM_WANT)


def test_33e_sum_semantics_vm2(bootvm):
    outs, err = _boot_err(bootvm, _SUM_PROG)
    assert err is None and outs == _SUM_WANT, ("sum_vm2", outs, err)


_TYPE_PROG = ('输出(type_of(1))\n输出(type_of(1.5))\n输出(type_of(真))\n'
              '输出(type_of("s"))\n输出(type_of([1]))\n输出(type_of((1, 2)))\n'
              '输出(type_of({"a": 1}))\n输出(type_of(null))\n'
              '输出(_to_tuple([1, 2]))\n输出(type_of(_to_tuple([1, 2])))')
_TYPE_WANT = ["Int", "Float", "Bool", "String", "List", "Tuple", "Dict",
              "Null", (1, 2), "Tuple"]


def test_33e_type_of_to_tuple_three_faces():
    """mb 面 type_of/_to_tuple 注册真化（32 登记⑤退役）：应用内建委托宿主
    BUILTINS，大写类型名三面同判。"""
    _three_faces("type_of", _TYPE_PROG, _TYPE_WANT)


def test_33e_type_of_to_tuple_vm2(bootvm):
    """VM² 面 func_type_of/func_to_tuple 包装注册同判。"""
    outs, err = _boot_err(bootvm, _TYPE_PROG)
    assert err is None and outs == _TYPE_WANT, ("type_vm2", outs, err)


# ============================================================
# 33a 单元素尾逗号 (1,) 诚实拒绝对齐宿主
# ============================================================

def test_33a_single_trailing_comma_honest_reject():
    """(1,) 三面诚实拒绝（此前 boot 静默吞成分组 (1)——32 登记①退役）。

    宿主=SPEC：vm/hi 同文案带 L:C 前缀；boot 解析错误以输出行呈现
    （不上抛），文案与宿主逐字一致。"""
    src = "输出((1,))"
    want = "期望表达式 (got PUNCT_RPAREN ')')"
    outs, err = exec_api.run_checked(src)
    assert err is not None and want in str(err), ("vm", outs, err)
    hi, hi_err = _hi_interp(src)
    assert hi_err is not None and want in str(hi_err), ("hi", hi, hi_err)
    mb, mb_err = _boot_interp(src)
    assert mb_err is None and mb and "[语法分析错误]" in str(mb[0]) \
        and want in str(mb[0]), ("mb", mb, mb_err)


def test_33a_trailing_comma_registered_boundary():
    """登记锁（不修）：多元素尾逗号 (1, 2,) 与调用位 尾逗号——双面诚实
    拒绝（boot 维持通用文案「期望表达式，实际 )」，阶段 33 只收单元素
    吞没位）。"""
    for tag, src in [("trail2", "输出((1, 2,))"), ("call_trail", "输出(1,)")]:
        outs, err = exec_api.run_checked(src)
        assert err is not None, (tag, "vm", outs, err)
        mb, mb_err = _boot_interp(src)
        assert mb_err is not None or (mb and "语法分析错误" in str(mb[0])), \
            (tag, "mb", mb, mb_err)


# ============================================================
# 33h slice 内建字符串臂真化（Track B 38_basics_join_split differ 根因）
# ============================================================

# mb 面应用内建实 slice 臂此前无条件走 标准库.list_slice——字符串实参
# 产出字符列表（split 块变 ['a'] 形），与宿主 builtin_slice 字符串切片
# 分歧；golden 38 语料在 33b 比较族提速后 600s 预算内真跑完成，分歧
# 首次显形（timeout→differ 漂移根因）。33h：String 实参走 31f _切片值
# 字符串臂（负下标回绕/端钳制 Python 语义）、List 维持 list_slice、
# Tuple/其他 诚实报错「slice() 需要字符串或列表」（宿主=SPEC 同文案）。

_LIB = _strip_bom(
    (_ROOT / "matha" / "library" / "collections_core.matha")
    .read_text(encoding="utf-8"))

_SLICE_PROG = ('[slice("hello", 1, 3)]\n[slice("abc", -2, 3)]\n'
               '[slice("abc", 1, 99)]\n[slice("abc", 2, 1)]\n'
               "[slice([1, 2, 3, 4], 1, 3)]")
_SLICE_WANT = ["el", "bc", "bc", "", [2, 3]]

_ROUNDTRIP_PROG = ('[join(",", split("a,b,c", ","))]\n'
                   '[join("-", split("a,b,", ","))]\n'
                   '[len(split("a,,b", ","))]\n'
                   '[join(":", split("a::b::c", "::"))]')
_ROUNDTRIP_WANT = ["a,b,c", "a-b-", 3, "a:b:c"]


def test_33h_slice_builtin_string_three_faces():
    """slice 内建字符串/列表臂三面同判（mb 面此前字符串产出字符列表）。"""
    _three_faces("slice_str", _SLICE_PROG, _SLICE_WANT)


def test_33h_slice_builtin_string_vm2(bootvm):
    """VM² 面同判（应用内建实 slice 臂经宿主编译入 VM）。"""
    outs, err = _boot_err(bootvm, _SLICE_PROG)
    assert err is None and outs == _SLICE_WANT, ("slice_vm2", outs, err)


def test_33h_split_join_roundtrip_vm_hi_vm2(bootvm):
    """join∘split 往返锁（collections_core 拼接源，38 语料根因）：
    vm/hi 面 + VM² 链面（Track B boot 判据同构）。mb 面不进本锁——
    matha_bootstrap 面自举词法器递归深度上限（测试 harness 限制非产品
    分歧），库级源 boot 判据以 VM² 链面与 Track B sweep 为准。"""
    src = _LIB + "\n" + _ROUNDTRIP_PROG
    outs, err = exec_api.run_checked(src)
    assert err is None and outs == _ROUNDTRIP_WANT, ("vm", outs, err)
    hi, hi_err = _hi_interp(src)
    assert hi_err is None and hi == _ROUNDTRIP_WANT, ("hi", hi, hi_err)
    outs2, err2 = _boot_err(bootvm, src)
    assert err2 is None and outs2 == _ROUNDTRIP_WANT, ("vm2", outs2, err2)


def test_33h_slice_builtin_tuple_registered_divergence():
    """登记锁（不修）：slice() 内建元组实参——hi/mb 诚实报错
    「slice() 需要字符串或列表」（33h 对齐宿主），vm 面维持宽松
    c[s:e] 返元组形态（src/mbc/vm.py 内建表，native 走 build_slice
    共用路径）。KNOWN_ISSUES 阶段 33 登记；本锁防现状漂移。"""
    src = "输出(slice((1, 2, 3), 0, 2))"
    want = "slice() 需要字符串或列表"
    hi, hi_err = _hi_interp(src)
    assert hi_err is not None and want in str(hi_err), ("hi", hi, hi_err)
    mb, mb_err = _boot_interp(src)
    assert mb_err is not None and want in str(mb_err), ("mb", mb, mb_err)
    outs, err = exec_api.run_checked(src)
    assert err is None and outs == [(1, 2)], ("vm", outs, err)

