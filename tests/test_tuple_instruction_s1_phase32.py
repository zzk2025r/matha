# -*- coding: utf-8 -*-
"""32-②S1 BUILD_TUPLE 运行时指令面（0x65=101）——零发射直接指令锁。

用户拍板 ②「以维持登记为基础，以切片真化的方式进行中心工程推进，必须
拆分成可回滚受控切片，逐个验证与安全进行」：S1 = 元组指令在三执行体可
执行，零发射方（宿主/boot 编译器暂不发射、无语料触碰）——零行为变化
可证（金档/语料输出逐位不变）：

  ① VM 面（vm.py）：手构 MModule 直注 BUILD_TUPLE → 真元组落全局/输出
     （n=0 空元组 ()、嵌套列表混装、书写序核对、BUILD_LIST 回归恒列表）；
  ② vm.matha 面（stdlib+vm.matha joined VM，运行M3V 全链）：M3V dict
     直注操作码 101 → 输出承载真元组（_to_tuple 双面内建经 LOAD_GLOBAL
     命中——宿主 BUILTINS interp.py:1189 / VM defaults vm.py 同名同形；
     vm.matha 建元组臂镜像建列表臂取尾+换栈序）；
  ③ native 面：手构模块含 BUILD_TUPLE → emit_exe 纯 Python 零外部工具
     成功 + TYPE_TUPLE(13) 头标签字节在 .text（48 C7 00 0D000000 =
     mov [rax],TYPE_TUPLE）——S2 发射面切换前的发射能力取证；元组堆
     布局与列表同构 [type][len][elements...]，消费面（print/下标/迭代）
     随 S2 接管。

S1 边界锁：宿主编译器元组字面量 (1, 2) 仍按 31-②「元组按列表处理」
发射 BUILD_LIST——S1 不含发射方（S2 退役 29-② 时本锁翻转）。
"""
import os
import struct
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.set_int_max_str_digits(0)

from pathlib import Path

from src.parser import parse as py_parse
from src.mbc.compiler import Compiler, MModule
from src.mbc import opcodes as OP
from src.mbc.vm import VM
from src.mbc.native import emit_exe, TYPE_TUPLE
from src import ast_nodes as ast

_ROOT = Path(__file__).resolve().parent.parent


# ============================================================
# 0. 操作码码位耦合锁（vm.matha 数字 101 ↔ opcodes 0x65）
# ============================================================

def test_s1_opcode_slot_coupling():
    """0x65 码位三面同源：opcodes 常量 / name() / vm.matha 建元组()=101。"""
    assert OP.BUILD_TUPLE == 0x65 == 101, OP.BUILD_TUPLE
    assert OP.name(0x65) == "BUILD_TUPLE", OP.name(0x65)
    assert OP.STORE_SUBSCRIPT == 0x64 and OP.FORMULA_SCHEMA == 0x62
    from src.mbc.native import TYPE_LIST
    assert TYPE_TUPLE == 13 and TYPE_TUPLE != TYPE_LIST


# ============================================================
# ① VM 面（vm.py）：手构模块直注 BUILD_TUPLE
# ============================================================

def _vm_run(main_code, constants):
    mod = MModule(module_name="s1")
    mod.main_code = [tuple(i) for i in main_code]
    mod.constants = list(constants)
    vm = VM(mod)
    vm.run()
    return vm


def test_s1_vm_build_tuple_real_value():
    vm = _vm_run([(OP.PUSH_CONST, 0), (OP.PUSH_CONST, 1),
                  (OP.BUILD_TUPLE, 2), (OP.STORE_GLOBAL, 2), (OP.HALT,)],
                 [1, 2, "x"])
    x = vm.globals["x"]
    assert x == (1, 2) and type(x) is tuple, x


def test_s1_vm_build_tuple_empty_and_nested():
    # n=0 → 空元组
    vm = _vm_run([(OP.BUILD_TUPLE, 0), (OP.STORE_GLOBAL, 0), (OP.HALT,)], ["e"])
    assert vm.globals["e"] == () and type(vm.globals["e"]) is tuple
    # 嵌套：列表常量 + 整数混装（元素顺序 = 书写序）
    vm2 = _vm_run([(OP.PUSH_CONST, 0), (OP.PUSH_CONST, 1),
                   (OP.BUILD_TUPLE, 2), (OP.STORE_GLOBAL, 2), (OP.HALT,)],
                  [[9, 8], 2, "n"])
    n = vm2.globals["n"]
    assert n == ([9, 8], 2) and type(n) is tuple, n


def test_s1_vm_build_tuple_output_carries_tuple():
    """OUTPUT 通道承载真元组（_norm_output 原样透传）。"""
    vm = _vm_run([(OP.PUSH_CONST, 0), (OP.PUSH_CONST, 1),
                  (OP.BUILD_TUPLE, 2), (OP.OUTPUT,), (OP.HALT,)], [1, 2])
    assert vm.outputs == [(1, 2)], vm.outputs


def test_s1_vm_build_list_regression():
    """BUILD_LIST 回归锁：同栈序恒列表（S1 零行为变化）。"""
    vm = _vm_run([(OP.PUSH_CONST, 0), (OP.PUSH_CONST, 1),
                  (OP.BUILD_LIST, 2), (OP.STORE_GLOBAL, 2), (OP.HALT,)],
                 [1, 2, "x"])
    x = vm.globals["x"]
    assert x == [1, 2] and type(x) is list, x


# ============================================================
# ② vm.matha 面：joined VM + 运行M3V 全链（操作码 101）
# ============================================================

@pytest.fixture(scope="module")
def vvm():
    """stdlib + vm.matha joined VM（phase29 vvm 同构）。"""
    comp = Compiler()
    src = ((_ROOT / "matha/stdlib.matha").read_text(encoding="utf-8") + "\n"
           + (_ROOT / "matha/vm.matha").read_text(encoding="utf-8"))
    comp.compile_program(ast.Program(decls=py_parse(src.lstrip("\ufeff")).decls))
    vm = VM(comp.mod)
    vm.run()
    return vm


def _m3v(main, constants):
    return {"模块名": "主", "常量": list(constants),
            "主码": [list(i) for i in main], "函数": []}


def _ins(*ops):
    """指令行归一：标量（无操作数指令如 停机）→ [op]，元组 → [op, ...]。"""
    return [[op] if isinstance(op, int) else list(op) for op in ops]


def test_s1_vmmath_build_tuple_runm3v(vvm):
    """M3V dict 直注 101 → 输出承载真元组（vm.matha 建元组臂真执行）。"""
    outs = vvm.call("运行M3V", _m3v(_ins((1, 0), (1, 1), (101, 2), (96, 0), 255), [1, 2]))
    assert outs == [(1, 2)], outs


def test_s1_vmmath_build_tuple_empty_nested(vvm):
    # 空元组
    assert vvm.call("运行M3V", _m3v(_ins((101, 0), (96, 0), 255), [])) == [()]
    # 嵌套混装（列表常量 + 整数）
    outs = vvm.call("运行M3V",
                    _m3v(_ins((1, 0), (1, 1), (101, 2), (96, 0), 255), [[9, 8], 2]))
    assert outs == [([9, 8], 2)], outs


def test_s1_vmmath_opcode_name_and_list_regression(vvm):
    """操作码名 101 → "0x65"（未知操作码诊断面）；建列表恒列表回归。"""
    assert vvm.call("操作码名", 101) == "0x65", vvm.call("操作码名", 101)
    outs = vvm.call("运行M3V", _m3v(_ins((1, 0), (1, 1), (80, 2), (96, 0), 255), [1, 2]))
    assert outs == [[1, 2]], outs


# ============================================================
# ③ native 面：emit_exe 纯 Python 发射能力取证（TYPE_TUPLE 头标签）
# ============================================================

def _native_mod(main_code, constants):
    mod = MModule(module_name="s1n")
    mod.main_code = [tuple(i) for i in main_code]
    mod.constants = list(constants)
    return mod


def test_s1_native_emit_build_tuple():
    """BUILD_TUPLE 发射臂接线取证：emit_exe 成功（不抛 NativeNotSupported）
    且 .text 含 mov [rax],TYPE_TUPLE（48 C7 00 0D000000）。"""
    mod = _native_mod([(OP.PUSH_CONST, 0), (OP.PUSH_CONST, 1),
                       (OP.BUILD_TUPLE, 2), (OP.HALT,)], [1, 2])
    exe = emit_exe(mod)
    assert b"\x48\xC7\x00" + struct.pack("<I", TYPE_TUPLE) in exe


def test_s1_native_emit_build_list_regression():
    """BUILD_LIST 发射回归锁：头标签 TYPE_LIST(2) 不受 S1 扰动。"""
    from src.mbc.native import TYPE_LIST
    mod = _native_mod([(OP.PUSH_CONST, 0), (OP.PUSH_CONST, 1),
                       (OP.BUILD_LIST, 2), (OP.HALT,)], [1, 2])
    exe = emit_exe(mod)
    assert b"\x48\xC7\x00" + struct.pack("<I", TYPE_LIST) in exe


# ============================================================
# S1 边界锁（S2 翻转）：宿主编译器元组字面量发射 BUILD_TUPLE
# ============================================================

def test_s1_no_emitter_host_tuple_literal_is_list():
    """S2 发射面切换后翻转（31-②「元组按列表处理」退役）：宿主编译器
    (1, 2) → BUILD_TUPLE 0x65，真元组发射；全模块零 BUILD_LIST 替身。"""
    mod = Compiler().compile_program(py_parse("x = (1, 2)"))
    assert any(i[0] == OP.BUILD_TUPLE for i in mod.main_code), mod.main_code
    assert not any(i[0] == OP.BUILD_LIST for i in mod.main_code), mod.main_code
