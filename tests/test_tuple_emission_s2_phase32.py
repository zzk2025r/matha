# -*- coding: utf-8 -*-
"""阶段 32-②S2 元组发射面切换锁（BUILD_TUPLE 0x65 双编译器发射 + 消费面全链）。

用户拍板 ②「以维持登记为基础，以切片真化的方式进行中心工程推进，必须
拆分成可回滚受控切片，逐个验证与安全进行」：S1 = 运行时指令面（零发射，
test_tuple_instruction_s1_phase32）；S2 = 发射面切换（本文件）——

  ① 发射面：宿主编译器 TupleExpr → BUILD_TUPLE（compiler.py 元组臂）；
     boot 编译器 _发射元组 镜像（OP_BUILD_TUPLE = 0x65，28c parity 逐位
     一致）。31-②「元组按列表处理（发射 BUILD_LIST）」就此退役。
  ② 消费面值语义：VM 面（vm.py 语义权威）+ hi 面（interp.py）+ mb 面
     （interp_matha 经宿主运行时委托）——输出/下标/负下标/切片/拼接/
     重复/len/max/str/迭代/字典对 全对拍。hi 面 `*` 序列重复臂、`-`
     容器守卫与 VM _op_mul/_op_sub 对齐；stdlib.matha str / vm.matha
     函数str 补元组渲染臂（CPython str(tuple) 形态：() / (a,) 尾逗号 /
     (a, b)，容器内 repr 转义）。
  ③ native 面：真实编译链 compile_to_exe（发射 BUILD_TUPLE）→ exe →
     stdout 逐行——print/print_tuple、seq_repeat、list_concat（标签保持）、
     _emit_getitem/_emit_slice/iter_source/len/type_of/str 容器路由、
     真值（truthy）、val_eq。
  ④ 诚实错误面：设值 tuple[i]=v（索引操作不支持）、越界（tuple index
     out of range）、`-` 容器（四执行体同文案）。native 跨型 `+` 返回
     null 为本后端既有约定（list+dict 同形，非 ② 新引入）——登记。

登记不修（32f）：尾逗号单元素 `(1,)` / 空括号 `()` 解析分歧（vm/hi
ParseError vs mb 静默误析 1/0）；mb 面用户域 type_of/_to_tuple 未定义
（30e carve-out）；mb 面 `in` 未知运算符；mb 面 `==` 返回 1.0/0.0；
mb 面空元组真值为真（真值模型仅数值/字符串）；mb 面 sum 返回浮点；
native 跨型 `+`/`*` 返回 null 约定。三面正锁全部避开尾逗号形态
（单元素/空元组经切片 t[0:1] / t[0:0] 构造）。
"""
import os
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.set_int_max_str_digits(0)

from src.parser import parse as py_parse
from src.mbc.compiler import Compiler, MModule, MFunction
from src.mbc.vm import VM
from src.mbc import opcodes as OP
from src.mbc.native import compile_to_exe, emit_exe, TYPE_TUPLE, TYPE_LIST
from src.kernel import exec_api
from src import ast_nodes as ast
from src import matha_bootstrap
from src import interp as host_interp

_ROOT = Path(__file__).resolve().parent.parent
_COMP_FILES = ["matha/lexer.matha", "matha/stdlib.matha", "matha/parser.matha",
               "matha/interp.matha", "matha/compiler_matha.matha"]


def _strip_bom(src):
    return src.lstrip("\ufeff") if src and src[0] == "\ufeff" else src


def dict_to_module(d):
    mod = MModule(module_name=d.get("模块名", "主程序"))
    mod.constants = list(d["常量"])
    mod.main_code = [tuple(x) for x in d["主码"]]
    for entry in d["函数"]:
        name, info = entry[0], entry[1]
        mod.functions[name] = MFunction(
            name, info["元数"], info["局部数"],
            [tuple(x) for x in info["码"]], list(info["参数"]))
    return mod


def _canon_code(mod):
    if isinstance(mod, MModule):
        return {"main": [tuple(i) for i in mod.main_code],
                "fns": {n: [tuple(i) for i in f.code]
                        for n, f in mod.functions.items()}}
    return {"main": [tuple(i) for i in mod["主码"]],
            "fns": {e[0]: [tuple(i) for i in e[1]["码"]] for e in mod["函数"]}}


@pytest.fixture(scope="module")
def bvm():
    comp = Compiler()
    decls = []
    for rel in _COMP_FILES:
        decls.extend(py_parse(_strip_bom(
            (_ROOT / rel).read_text(encoding="utf-8"))).decls)
    comp.compile_program(ast.Program(decls=decls))
    vm = VM(comp.mod)
    vm.run()
    return vm


def _stage2(src):
    return Compiler().compile_program(py_parse(_strip_bom(src)))


def _stage3(bvm, src):
    return dict_to_module(bvm.call("编译", _strip_bom(src)))


def _assert_parity(bvm, src):
    assert _canon_code(_stage3(bvm, src)) == _canon_code(_stage2(src)), src


def _boot_interp(src):
    try:
        outs, trace = matha_bootstrap.interpret(src, strict=True)
        return outs, None
    except Exception as e:  # noqa: BLE001
        return None, e


def _hi_interp(src):
    try:
        outs, trace = host_interp.interpret(src)
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


def _aot(src: str) -> list:
    exe = os.path.join(tempfile.gettempdir(), "test_tuple_s2.exe")
    Path(exe).write_bytes(compile_to_exe(src))
    r = subprocess.run([exe], capture_output=True, timeout=30)
    assert r.returncode == 0, (r.returncode, r.stderr)
    return r.stdout.decode("utf-8", "replace").splitlines()


def _aot_err(src: str, msg: str):
    exe = os.path.join(tempfile.gettempdir(), "test_tuple_s2.exe")
    Path(exe).write_bytes(compile_to_exe(src))
    r = subprocess.run([exe], capture_output=True, timeout=30)
    assert (r.returncode & 0xFFFFFFFF) == 1, (r.returncode, r.stderr)
    assert msg in r.stderr.decode("utf-8", "replace"), r.stderr


# ============================================================
# ① 发射面：宿主编译器 BUILD_TUPLE 形状 + 零 BUILD_LIST 替身
# ============================================================

def test_s2_host_emission_shapes():
    """n=2 / n=0 边界（空元组经切片）与嵌套发射形状：TupleExpr →
    BUILD_TUPLE，全模块零 BUILD_LIST 替身。"""
    mod = _stage2("x = (1, 2)")
    codes = [i[0] for i in mod.main_code]
    assert codes.count(OP.BUILD_TUPLE) == 1, codes
    assert OP.BUILD_LIST not in codes, codes

    mod2 = _stage2("t = (1, 2)\nu = (3, 4)\nx = (t, u)")
    codes2 = [i[0] for i in mod2.main_code]
    assert codes2.count(OP.BUILD_TUPLE) == 3, codes2
    assert OP.BUILD_LIST not in codes2, codes2


def test_s2_host_list_literal_regression():
    """列表字面量恒 BUILD_LIST（发射面切换不扰动列表）。"""
    mod = _stage2("x = [1, 2]")
    codes = [i[0] for i in mod.main_code]
    assert OP.BUILD_LIST in codes and OP.BUILD_TUPLE not in codes, codes


def test_s2_for_target_unpack_not_tuple_emission():
    """for 目标解构走 UNPACK_SEQ（多变量目标 names 列表），不受元组发射
    切换扰动；单变量目标直 STORE_GLOBAL（无 UNPACK_SEQ）。"""
    mod = _stage2("s = 0\nfor x in (10, 20, 30) {\n  s = s + x\n}\n输出(s)")
    codes = [i[0] for i in mod.main_code]
    assert OP.BUILD_TUPLE in codes, codes
    assert OP.UNPACK_SEQ not in codes, codes

    mod2 = _stage2('s = ""\nfor (k, v) in {"a": 1} {\n  s = s + k\n}\n输出(s)')
    codes2 = [i[0] for i in mod2.main_code]
    assert OP.UNPACK_SEQ in codes2, codes2


_PARITY_SRCS = [
    "x = (1, 2)\n输出(x)",
    "t = (1, 2)\n输出(t * 3)",
    "输出(3 * (1, 0))",
    "t = (1, 2)\n输出(t + t[1:2])",
    "t = (1, 2)\n输出((t, (3, 4)))",
    "输出([(1, 2), (3, 4)])",
    '输出({"k": (1, 2)})',
    "输出((10, 20, 30)[1])",
    "输出((10, 20, 30)[-1])",
    "输出((1, 2, 3, 4)[1:3])",
    "t = (1, 2)\n输出(t[0:1])",
    "t = (1, 2)\n输出(t[0:0])",
    "输出(len((1, 2)))",
    "输出(str((1, 2)))",
    "s = 0\nfor x in (10, 20, 30) {\n  s = s + x\n}\n输出(s)",
    'd = {"a": 1}\nfor p in d {\n  输出(p)\n}',
]


def test_s2_boot_parity_tuple_sources(bvm):
    """S2a 自举编译器 _发射元组 镜像：16 语料 stage2↔stage3 逐位一致。"""
    for src in _PARITY_SRCS:
        _assert_parity(bvm, src)


# ============================================================
# ② 消费面值语义：三面对拍（全部避开尾逗号解析缺口）
# ============================================================

_THREE_FACE_CASES = [
    ("out2", "输出((1, 2))", [(1, 2)]),
    ("repeat", "输出((1, 0) * 3)", [(1, 0, 1, 0, 1, 0)]),
    ("rswap", "输出(3 * (1, 0))", [(1, 0, 1, 0, 1, 0)]),
    ("concat_slice", "t = (1, 2)\n输出(t + t[1:2])", [(1, 2, 2)]),
    ("nested", "t = (1, 2)\nu = (3, 4)\n输出((t, u))", [((1, 2), (3, 4))]),
    ("tuplist", "输出([(1, 2), (3, 4)])", [[(1, 2), (3, 4)]]),
    ("tupdict", '输出({"k": (1, 2)})', [{"k": (1, 2)}]),
    ("index", "输出((10, 20, 30)[1])", [20]),
    ("negidx", "输出((10, 20, 30)[-1])", [30]),
    ("slice", "输出((1, 2, 3, 4)[1:3])", [(2, 3)]),
    ("slice_head", "输出((1, 2, 3)[:2])", [(1, 2)]),
    ("single", "t = (1, 2)\n输出(t[0:1])", [(1,)]),
    ("single_lit", "输出((7, 8)[1:2])", [(8,)]),
    ("empty", "t = (1, 2)\n输出(t[0:0])", [()]),
    ("repeat_empty", "t = (1, 2)[0:0]\n输出(t * 3)", [()]),
    ("len", "输出(len((1, 2)))", [2]),
    ("max", "输出(max((3, 1, 2)))", [3]),
    ("str2", "输出(str((1, 2)))", ["(1, 2)"]),
    ("str_single", "输出(str((1, 2)[0:1]))", ["(1,)"]),
    ("str_empty", "输出(str((1, 2)[0:0]))", ["()"]),
    ("str_nested", "输出(str(((1, 2), (3, 4))))", ["((1, 2), (3, 4))"]),
    ("str_tuplist", "输出(str([(1, 2), (3, 4)]))", ["[(1, 2), (3, 4)]"]),
    ("str_tupdict", '输出(str({"k": (1, 2)}))', ["{'k': (1, 2)}"]),
    ("foriter", "s = 0\nfor x in (10, 20, 30) {\n  s = s + x\n}\n输出(s)", [60]),
    ("dictfor", 'd = {"a": 1}\nfor p in d {\n  输出(p)\n}', [("a", 1)]),
    ("truthy", "t = (0, 1)\nif t {\n  输出(1)\n} else {\n  输出(0)\n}", [1]),
]


@pytest.mark.parametrize("tag,src,want", _THREE_FACE_CASES)
def test_s2_value_three_faces(tag, src, want):
    """元组消费面 27 形态三面同判：vm（语义权威）/ hi（宿主解释器）/
    mb（自举解释器经宿主运行时委托）。"""
    _three_faces(tag, src, want)


def test_s2_output_carries_real_tuple_type():
    """输出通道承载真元组对象（vm 面 outputs 元素 type is tuple）。"""
    outs, err = exec_api.run_checked("输出((1, 2))")
    assert err is None and type(outs[0]) is tuple, outs


# ============================================================
# ③ vm/hi 双面锁（mb 面 type_of/_to_tuple/in/== 为登记缺口）
# ============================================================

def test_s2_type_of_tuple_vm_hi_faces():
    outs, err = exec_api.run_checked("输出(type_of((1, 2)))")
    assert err is None and outs == ["Tuple"], (outs, err)
    hi, hi_err = _hi_interp("输出(type_of((1, 2)))")
    assert hi_err is None and hi == ["Tuple"], (hi, hi_err)


def test_s2_eq_and_in_vm_hi_faces():
    for tag, src, want in [
        ("eq_t", "输出((1, 2) == (1, 2))", [True]),
        ("eq_x", "输出((1, 2) == [1, 2])", [False]),
        ("in_t", "输出(1 in (1, 2))", [True]),
        ("in_f", "输出(3 in (1, 2))", [False]),
    ]:
        outs, err = exec_api.run_checked(src)
        assert err is None and outs == want, (tag, "vm", outs, err)
        hi, hi_err = _hi_interp(src)
        assert hi_err is None and hi == want, (tag, "hi", hi, hi_err)


def test_s2_falsy_empty_tuple_vm_hi_faces():
    """空元组假值（vm/hi 面）：真值路由 TYPE_TUPLE → len。mb 面空元组
    真值为真（真值模型登记 32f）。"""
    src = "t = (1, 2)[0:0]\nif t {\n  输出(1)\n} else {\n  输出(0)\n}"
    outs, err = exec_api.run_checked(src)
    assert err is None and outs == [0], (outs, err)
    hi, hi_err = _hi_interp(src)
    assert hi_err is None and hi == [0], (hi, hi_err)


# ============================================================
# ④ 诚实错误面：四执行体同文案
# ============================================================

_ERR_CASES = [
    ("setitem", "x = (1, 2)\nx[0] = 9", "索引操作不支持: tuple[0]"),
    ("oob", "输出((10, 20, 30)[5])", "tuple index out of range"),
    ("sub", "t = (1, 2)\n输出(t - 1)", "- 不适用于字符串/列表"),
]


@pytest.mark.parametrize("tag,src,msg", _ERR_CASES)
def test_s2_error_messages_three_faces(tag, src, msg):
    """错误文案三面同判（越界 IndexError 透传 29b 语义、其余
    MathaRuntimeError——消息文本逐字一致）。"""
    outs, err = exec_api.run_checked(src)
    assert err is not None and str(err) == msg, (tag, outs, err)
    hi, hi_err = _hi_interp(src)
    assert hi is None and hi_err is not None and str(hi_err) == msg, (tag, hi, hi_err)
    mb, mb_err = _boot_interp(src)
    assert mb is None and mb_err is not None and str(mb_err) == msg, (tag, mb, mb_err)


def test_s2_trailing_comma_honest_parse_reject_vm_hi():
    """登记缺口诚实锁：尾逗号 `(1,)` vm/hi 面解析器诚实拒绝（ParseError）；
    mb 面静默误析为 1（登记 32f，不锁其误析结果）。"""
    src = "输出((1,))"
    outs, err = exec_api.run_checked(src)
    assert err is not None and "ParseError" in type(err).__name__, (outs, err)
    hi, hi_err = _hi_interp(src)
    assert hi is None and hi_err is not None, (hi, hi_err)


# ============================================================
# ⑤ native 面：真实编译链 → exe → stdout（S2b 消费面运行时取证）
# ============================================================

def test_s2_native_print_tuple():
    """print_value → print_tuple：编译链发射 BUILD_TUPLE，exe 输出
    CPython 形态 "(1, 2)"。"""
    assert _aot("x = (1, 2)\n输出(x)") == ["(1, 2)"]


def test_s2_native_tuple_ops():
    """重复（双向）/拼接（标签保持）/下标/切片/len/迭代/str/type_of/eq/in/
    真值——S2b 消费臂逐臂运行时取证。"""
    assert _aot("输出((1, 0) * 3)") == ["(1, 0, 1, 0, 1, 0)"]
    assert _aot("输出(3 * (1, 0))") == ["(1, 0, 1, 0, 1, 0)"]
    assert _aot("t = (1, 2)\n输出(t + t[1:2])") == ["(1, 2, 2)"]
    assert _aot("t = (1, 2)\n输出(t[1])") == ["2"]
    assert _aot("输出((10, 20, 30)[-1])") == ["30"]
    assert _aot("输出((1, 2, 3, 4)[1:3])") == ["(2, 3)"]
    assert _aot("t = (1, 2)\n输出(t[0:0])") == ["()"]
    assert _aot("输出(len((1, 2)))") == ["2"]
    assert _aot("s = 0\nfor x in (10, 20, 30) {\n  s = s + x\n}\n输出(s)") == ["60"]
    assert _aot('d = {"a": 1}\nfor p in d {\n  输出(p)\n}') == ["('a', 1)"]
    assert _aot("输出(str((1, 2)))") == ["(1, 2)"]
    assert _aot("输出(type_of((1, 2)))") == ["Tuple"]
    assert _aot("输出((1, 2) == (1, 2))") == ["True"]
    assert _aot("输出(1 in (1, 2))") == ["True"]
    assert _aot("t = (0, 1)\nif t {\n  输出(1)\n} else {\n  输出(0)\n}") == ["1"]
    assert _aot("t = (1, 2)[0:0]\nif t {\n  输出(1)\n} else {\n  输出(0)\n}") == ["0"]


def test_s2_native_list_regression():
    """列表消费面回归：S2b 标签保持改造不扰动既有列表行为。"""
    assert _aot("x = [1, 2]\n输出(x)") == ["[1, 2]"]
    assert _aot("输出([1, 2] + [3])") == ["[1, 2, 3]"]
    assert _aot("输出([1, 0] * 2)") == ["[1, 0, 1, 0]"]


def test_s2_native_error_messages():
    """native 诚实错误：越界 / 设值 / 容器减法（err_index_tuple /
    si_tname_tuple / err_sub_type 路由）。"""
    _aot_err("输出((10, 20, 30)[5])", "tuple index out of range")
    _aot_err("x = (1, 2)\nx[0] = 9", "索引操作不支持: tuple[0]")
    _aot_err("t = (1, 2)\n输出(t - 1)", "- 不适用于字符串/列表")


def test_s2_native_emit_forensics():
    """发射取证：编译链产物 .text 含 TYPE_TUPLE 头标签存储
    （48 C7 00 0D000000 = mov [rax],TYPE_TUPLE）——S2a 发射面切换已
    供给 native BUILD_TUPLE 发射臂（零 BUILD_LIST 替身由发射形状锁
    test_s2_host_emission_shapes 在字节码层证明——机器码层同字节序列
    会与其他立即数存储碰撞，不可字节级断言缺席）。"""
    exe = emit_exe(_stage2("x = (1, 2)"))
    assert b"\x48\xC7\x00" + struct.pack("<I", TYPE_TUPLE) in exe


def test_s2_opcode_slot_coupling():
    """码位三面同源（承 S1）：0x65 = 101 = BUILD_TUPLE。"""
    assert OP.BUILD_TUPLE == 0x65 == 101, OP.BUILD_TUPLE
    assert OP.name(0x65) == "BUILD_TUPLE", OP.name(0x65)
    assert TYPE_TUPLE == 13 and TYPE_TUPLE != TYPE_LIST
