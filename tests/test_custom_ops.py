"""用户自定义运算符（@define_op）测试。

语法：`@define_op: <符号> = <优先级> | <结合性>  [ => <函数名> ]`
运算符绑定到具名函数；求值 `a <符号> b` 时调用该函数。
覆盖：解析注册、解释器求值、字节码/VM 求值、原生求值、优先级、未绑定/缺实现报错。
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from src import custom_ops
from src.interp import MathaRuntimeError, interpret
from src.mbc import compile_source
from src.mbc.native import compile_to_exe
from src.mbc.vm import VM
from src.parser import parse


@pytest.fixture(autouse=True)
def _fresh_registry():
    custom_ops.clear()
    yield
    custom_ops.clear()


def _interp(src):
    out, _ = interpret(src)
    return out


def _vm(src):
    m = compile_source(src)
    vm = VM(m)
    vm.run()
    return vm.outputs


# ─── 注册 ────────────────────────────────────────────────────────────────────

def test_define_op_registers_precedence_assoc_handler():
    prog = parse("@define_op: ≈ = 5 | left => 约等于\n")
    assert prog is not None
    op = custom_ops.get("≈")
    assert op is not None
    assert op.precedence == 5
    assert op.assoc == "left"
    assert op.handler == "约等于"


def test_define_op_without_handler_has_none():
    parse("@define_op: ≈ = 3 | right\n")
    op = custom_ops.get("≈")
    assert op.handler is None


# ─── 解释器求值 ──────────────────────────────────────────────────────────────

_APPROX = (
    "@define_op: ≈ = 5 | left => 约等于\n"
    "func 约等于(a: Int, b: Int) -> Bool = abs(a - b) <= 1\n"
)


def test_interp_custom_op_true():
    out = _interp(_APPROX + "x = 3\ny = 4\n#：[x ≈ y]\n")
    assert out[-1] is True


def test_interp_custom_op_false():
    out = _interp(_APPROX + "x = 3\ny = 9\n#：[x ≈ y]\n")
    assert out[-1] is False


def test_interp_custom_op_precedence_over_add():
    # 2 + 3 ≈ 4 + 1  →  (2+3) ≈ (4+1)  → True
    out = _interp(_APPROX + "#：[2 + 3 ≈ 4 + 1]\n")
    assert out[-1] is True


def test_interp_custom_op_left_associative():
    src = (
        "@define_op: ⊙ = 4 | left => 连加\n"
        "func 连加(a: Int, b: Int) -> Int = a + b\n"
        "#：[1 ⊙ 2 ⊙ 3]\n"
    )
    # left 结合：(1 ⊙ 2) ⊙ 3 = (1+2)+3 = 6
    assert _interp(src)[-1] == 6


def test_interp_custom_op_right_associative():
    src = (
        "@define_op: ⊙ = 4 | right => 连加\n"
        "func 连加(a: Int, b: Int) -> Int = a * 10 + b\n"
        "#：[1 ⊙ 2 ⊙ 3]\n"
    )
    # right 结合：1 ⊙ (2 ⊙ 3) = (1*10) + (2*10 + 3) = 33
    assert _interp(src)[-1] == 33


def test_interp_custom_op_binds_looser_than_higher_precedence():
    src = (
        "@define_op: ⋈ = 4 | left => 加\n"
        "@define_op: ⊛ = 6 | right => 乘\n"
        "func 加(a: Int, b: Int) -> Int = a + b\n"
        "func 乘(a: Int, b: Int) -> Int = a * b\n"
        "#：[1 ⋈ 2 ⊛ 3]\n"
    )
    # ⊛ 优先级 6 高于 ⋈ 的 4 → 1 ⋈ (2 ⊛ 3) = 1 + 6 = 7
    assert _interp(src)[-1] == 7


# ─── 报错 ────────────────────────────────────────────────────────────────────

def test_interp_unbound_custom_op_raises():
    with pytest.raises(MathaRuntimeError) as e:
        _interp("@define_op: ≈ = 5 | left\n#：[1 ≈ 2]\n")
    assert "未绑定实现" in str(e.value)


def test_interp_missing_handler_function_raises():
    with pytest.raises(MathaRuntimeError) as e:
        _interp("@define_op: ≈ = 5 | left => 不存在的函数\n#：[1 ≈ 2]\n")
    assert "实现函数未定义" in str(e.value)


def test_compile_unbound_custom_op_raises():
    with pytest.raises(RuntimeError) as e:
        compile_source("@define_op: ≈ = 5 | left\n#：[1 ≈ 2]\n")
    assert "未绑定实现" in str(e.value)


# ─── 字节码 / VM ─────────────────────────────────────────────────────────────

def test_vm_custom_op_true():
    assert _vm(_APPROX + "x = 3\ny = 4\n#：[x ≈ y]\n")[-1] is True


def test_vm_custom_op_false():
    assert _vm(_APPROX + "x = 3\ny = 9\n#：[x ≈ y]\n")[-1] is False


def test_vm_matches_interp():
    src = _APPROX + "a = 5\nb = 6\nc = 20\n#：[a ≈ b]\n#：[a ≈ c]\n"
    assert _vm(src) == _interp(src)


# ─── 原生（x86-64 PE64）─────────────────────────────────────────────────────
# 编译器对自定义运算符发射 LOAD_GLOBAL handler + CALL 2，原生端复用既有闭包
# 调用路径，无需改 native.py；此处仅端到端锁定行为。

def _native(src):
    """编译为 exe 并运行，返回 stdout 文本（原生 OUTPUT 打印整数/布尔）。"""
    exe = os.path.join(tempfile.gettempdir(), "test_custom_ops_native.exe")
    Path(exe).write_bytes(compile_to_exe(src))
    r = subprocess.run([exe], capture_output=True, timeout=30)
    assert r.returncode & 0xFFFFFFFF == 0, r.stderr.decode("utf-8", "replace")
    return r.stdout.decode("utf-8", "replace").strip()


_NAT_ADD = (
    "@define_op: ≈ = 5 | left => 加\n"
    "func 加(a: Int, b: Int) -> Int = a + b\n"
)


def test_native_custom_op_add():
    assert _native(_NAT_ADD + "#1：[2 ≈ 3]\n") == "5"


def test_native_custom_op_vars():
    assert _native(_NAT_ADD + "x = 10\ny = 20\n#1：[x ≈ y]\n") == "30"


def test_native_matches_vm():
    src = _NAT_ADD + "a = 5\nb = 6\n#1：[a ≈ b]\n"
    assert _native(src) == str(_vm(src)[-1])


# ─── 注册表工具 ──────────────────────────────────────────────────────────────

def test_registry_clear_and_get():
    custom_ops.register("≈", 5, "left", "f")
    assert custom_ops.is_custom_op("≈")
    custom_ops.clear()
    assert not custom_ops.is_custom_op("≈")
    assert custom_ops.get("≈") is None


def test_register_rejects_bad_assoc():
    with pytest.raises(ValueError):
        custom_ops.register("≈", 5, "sideways", "f")
