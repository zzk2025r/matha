# -*- coding: utf-8 -*-
"""插件化隔离风险门禁：代数数精确打印（opt-in）与动态语义空壳预埋。

覆盖三件事（对应「内核只依赖接口 / 核心保持纯净 / 外部插件实现 / 动态加载」）：

1. **无损**：代数数插件默认不加载时，门面 ``to_str`` 发射逐字节不变；加载后仅
   把可证精确命中的 double 系数还原为根式；能力之外诚实回退。
2. **诚实预埋**：动态语义骨架加载后不认领任何指令（``supports`` 恒 False），
   被显式要求执行未接线语义时抛 ``DynamicSemanticsNotWired``，绝不伪造成功。
3. **隔离红线**：纯内核 / 执行器不得 import 插件契约层；契约层不得顶层依赖
   sympy / numpy / scipy（保持核心极简、零第三方成本）。
"""
from __future__ import annotations

import importlib.util
import math
from fractions import Fraction
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

from src.algebra import interface as alg  # noqa: E402
from src.algebra.algebra_plugin import PLUGIN as ALG_PLUGIN  # noqa: E402
from src.dynamics import dynamic_semantics_plugin as dsp  # noqa: E402
from src.dynamics import interface as dyn  # noqa: E402
from src.dynamics import rv32_executor_pilot as pilot  # noqa: E402
from src.dynamics.interface import DynamicSemanticsNotWired  # noqa: E402


def _sq(n: int):
    return alg.UnaryOp("sqrt", alg.Const(n))


def _c(n):
    return alg.Const(Fraction(n))


def _add(a, b):
    return alg.BinOp("+", a, b)


def _sub(a, b):
    return alg.BinOp("-", a, b)


def _mul(a, b):
    return alg.BinOp("*", a, b)


def _div(a, b):
    return alg.BinOp("/", a, b)


def _root(d, n):
    return alg.BinOp("^", alg.Const(Fraction(d)), alg.Const(Fraction(1, n)))


def _canon_to_sympy(s: str):
    """把插件规范串（sqrt(n)/root(n,d)/分数/+-*）解析回 sympy 精确表达式。"""
    import re

    import sympy as sp
    s2 = re.sub(r"root\((\d+),(\d+)\)", r"root(\2,\1)", s)
    return sp.sympify(s2)


def _tree_to_sympy(t):
    """独立地用 sympy 精确求值中性项树（与插件完全无关的第二实现，作对拍基准）。"""
    import sympy as sp
    if isinstance(t, alg.Const):
        return sp.Rational(t.value)
    if isinstance(t, alg.Symbol):
        return sp.Symbol(t.name)
    if isinstance(t, alg.UnaryOp):
        inner = _tree_to_sympy(t.operand)
        if t.op == "sqrt":
            return sp.sqrt(inner)
        if t.op == "-":
            return -inner
        if t.op == "+":
            return inner
    if isinstance(t, alg.BinOp):
        L = _tree_to_sympy(t.left)
        R = _tree_to_sympy(t.right)
        return {"+": L + R, "-": L - R, "*": L * R, "/": L / R, "^": sp.Pow(L, R)}[t.op]
    raise TypeError(f"未知项类型：{type(t).__name__}")


# ============================================================
# 1. 代数数打印：无损 + 精确 + 诚实边界
# ============================================================


def test_algebra_default_inactive_facade_is_lossless():
    """未加载插件时门面输出必须等于内核 to_str 原样（含 double 系数）。"""
    from src.stdlib import calculus_symbolic as cs
    cs.use_kernel_printing()  # 确保关
    assert cs.exact_algebra_enabled() is False
    out = cs.symbolic_integral("1/(x**2+2)", "x")
    # 默认路径应保留 double 打印，绝不出现根式
    assert "sqrt" not in out
    assert "0.70" in out or "1.41" in out


def test_algebra_optin_renders_exact_and_restores():
    """同一条积分：关→开→关，关闭后必须与初始默认输出逐字节相同（无损）。"""
    from src.stdlib import calculus_symbolic as cs
    cs.use_kernel_printing()
    default_out = cs.symbolic_integral("1/(x**2+2)", "x")
    assert "sqrt" not in default_out
    try:
        cs.enable_exact_algebra()
        assert cs.exact_algebra_enabled() is True
        exact = cs.symbolic_integral("1/(x**2+2)", "x")
        assert "sqrt(2)" in exact          # 0.7071… → 1/2*sqrt(2)，1.4142… → sqrt(2)
        assert "0.70" not in exact
    finally:
        cs.use_kernel_printing()
    assert cs.symbolic_integral("1/(x**2+2)", "x") == default_out


@pytest.mark.parametrize("value,expect", [
    (math.sqrt(2), "sqrt(2)"),
    (Fraction(5, 7), "5/7"),
    (7, "7"),
    (-math.sqrt(3), "-sqrt(3)"),
    (0.5 + 3 * math.sqrt(2), "1/2 + 3*sqrt(2)"),
    (2 ** 0.5 * 2, "2*sqrt(2)"),          # sqrt(8) 化简
])
def test_algebra_recognizer_exact_forms(value, expect):
    got = ALG_PLUGIN.render(alg.Const(Fraction(value)) if not isinstance(value, Fraction) else alg.Const(value))
    assert got == expect


def test_algebra_honesty_defers_unknown():
    """能力边界诚实回退：无结构线索的扁平浮点 / 超越数 / 嵌套根 / 混合高次 → render 回 None。"""
    # 扁平 double（来自门面 decorate 路径）：√2+√3 无数树形线索 → 不过度猜测，回 None
    assert ALG_PLUGIN.render(alg.Const(Fraction(math.sqrt(2) + math.sqrt(3)))) is None
    # 超越数 π
    assert ALG_PLUGIN.render(alg.Const(Fraction(math.pi))) is None
    # 嵌套根式 √(√2)：本框架不做 denest → None
    assert ALG_PLUGIN.render(alg.UnaryOp("sqrt", _sq(2))) is None
    # 多根式 + 高次混合 √2 + ∛2：超出 ℚ(√…) 且非纯根 → None
    assert ALG_PLUGIN.render(_add(_sq(2), _root(2, 3))) is None
    # 含符号：不可作为常数精确还原 → None
    assert ALG_PLUGIN.render(_add(_sq(2), alg.Symbol("x"))) is None
    # 非实：√(-1) → None（不伪造）
    assert ALG_PLUGIN.render(_sq(-1)) is None


@pytest.mark.parametrize("tree,expect", [
    (_add(_sq(2), _sq(3)), "sqrt(2) + sqrt(3)"),
    (_sub(_sq(5), _sq(2)), "-sqrt(2) + sqrt(5)"),
    (_mul(_add(_c(1), _sq(2)), _add(_c(1), _sq(3))), "1 + sqrt(2) + sqrt(3) + sqrt(6)"),
    (_div(_c(1), _sq(2)), "1/2*sqrt(2)"),
    (_add(_sq(2), _add(_sq(3), _sq(5))), "sqrt(2) + sqrt(3) + sqrt(5)"),
    (_sub(_mul(_c(3), _sq(2)), _sq(3)), "3*sqrt(2) - sqrt(3)"),
    (_mul(_sq(2), _sq(3)), "sqrt(6)"),
    (_add(_c(1), _sq(2)), "1 + sqrt(2)"),
])
def test_algebra_multiquadratic_exact(tree, expect):
    """多根式域 ℚ(√d1,…,√dk) 结构还原：与既有 double 塌缩不重合的高次代数数现在可精确打印。"""
    got = ALG_PLUGIN.render(tree)
    assert got == expect


@pytest.mark.parametrize("tree", [
    _add(_sq(2), _sq(3)),
    _sub(_sq(5), _sq(2)),
    _mul(_add(_c(1), _sq(2)), _add(_c(1), _sq(3))),
    _div(_c(1), _sq(2)),
    _add(_sq(2), _add(_sq(3), _sq(5))),
    _sub(_mul(_c(3), _sq(2)), _sq(3)),
])
def test_algebra_multiquadratic_differential_vs_sympy(tree):
    """对拍 sympy：插件输出的规范串解析回 sympy 后，与树的独立 sympy 精确求值符号相等。"""
    import sympy as sp
    got = ALG_PLUGIN.render(tree)
    assert got is not None
    diff = sp.simplify(_canon_to_sympy(got) - _tree_to_sympy(tree))
    assert diff == 0, f"{got!r} vs sympy 不吻合: {diff}"


@pytest.mark.parametrize("tree,expect", [
    (_root(2, 3), "root(3,2)"),
    (_root(16, 3), "2*root(3,2)"),
    (_root(4, 3), "root(3,4)"),
    (_root(3, 4), "root(4,3)"),
    (_root(7, 5), "root(5,7)"),
    (_root(32, 5), "2"),                 # 纯整数次根 → 有理路径
])
def test_algebra_nthroot_exact(tree, expect):
    """高次纯根 base^(1/n)（n>=3）化简为 k·ⁿ√r，规范串 root(n,r)。"""
    assert ALG_PLUGIN.render(tree) == expect


@pytest.mark.parametrize("tree", [
    _root(2, 3), _root(16, 3), _root(4, 3), _root(3, 4),
])
def test_algebra_nthroot_differential_vs_sympy(tree):
    """对拍 sympy：纯高次根的插件输出与 sympy 实根数值、符号均吻合。"""
    import sympy as sp
    got = ALG_PLUGIN.render(tree)
    assert got is not None
    assert sp.simplify(_canon_to_sympy(got) - _tree_to_sympy(tree)) == 0
    assert abs(float(_canon_to_sympy(got)) - ALG_PLUGIN._eval_float(tree)) < 1e-9


def test_algebra_flat_float_regression_still_quadratic_only():
    """回归锁：扁平浮点（无树形）仍仅走二次/有理识别，不得因扩面而误命中高次。"""
    assert ALG_PLUGIN.render(alg.Const(Fraction(2 ** 0.5))) == "sqrt(2)"   # 二次仍精确
    assert ALG_PLUGIN.render(alg.Const(Fraction(2 ** (1 / 3)))) is None     # 扁平 ∛2 无结构→诚实 None


# ============================================================
# 2. 动态语义：加载契约 + 未接线诚实 + 对 SPIKE 逐指令 对拍
# ============================================================


def test_dynamics_default_inactive():
    dyn.set_active(None)
    assert dyn.active_backend() is None


def test_dynamics_loaded_executes_and_unloaded_falls_back():
    """未加载插件时 execute_or_default 必须回退 native；加载后按契约真实执行。"""
    dyn.set_active(None)
    m0 = RefMachine(0x1000)
    m0.write_reg(2, 10)
    m0.write_reg(3, 32)
    calls: list[str] = []
    handled = dyn.execute_or_default(
        dyn.DecodedInstr("add", rd=1, rs1=2, rs2=3), m0,
        lambda i, mm: calls.append(i.op))
    assert handled is False and calls == ["add"]        # 未加载 → 走原生，插件不碰机器
    assert m0.read_reg(1) == 0                          # 插件未执行，x1 保持
    try:
        backend = dyn.load_plugin("dynamic")
        assert backend.supports(dyn.DecodedInstr("add", rd=1, rs1=2, rs2=3)) is True
        m1 = RefMachine(0x1000)
        m1.write_reg(2, 10)
        m1.write_reg(3, 32)
        handled = dyn.execute_or_default(
            dyn.DecodedInstr("add", rd=1, rs1=2, rs2=3), m1,
            lambda i, mm: pytest.fail("已加载且认领的指令不应走原生"))
        assert handled is True and m1.read_reg(1) == 42
    finally:
        dyn.set_active(None)


def test_dynamics_honest_on_unwired_op():
    """未落地语义（mret/wfi 等系统指令）：supports=False、回退原生、直接 execute 抛显式失败。"""
    unwired = dyn.DecodedInstr("mret", rd=1, rs1=2, rs2=3, imm=0)
    try:
        backend = dyn.load_plugin("dynamic")
        assert backend.supports(unwired) is False           # 不认领未接线的
        assert "mret" not in backend.wired_ops()
        calls: list[str] = []
        handled = dyn.execute_or_default(
            unwired, object(), lambda i, mm: calls.append(i.op))
        assert handled is False and calls == ["mret"]       # 回退执行器原生
        with pytest.raises(DynamicSemanticsNotWired):       # 显式失败，不伪造成功
            backend.execute(unwired, object())
    finally:
        dyn.set_active(None)


def test_dynamics_wired_ops_cover_rv32im_core():
    ops = set(dsp.PLUGIN.wired_ops())
    for need in ("add", "sub", "and", "or", "xor", "sll", "srl", "sra", "slt", "sltu",
                 "addi", "slti", "xori", "ori", "andi", "slli", "srli", "srai",
                 "lui", "auipc", "jal", "jalr", "beq", "bne", "blt", "bge", "bltu", "bgeu",
                 "lw", "lh", "lb", "sw", "sh", "sb", "mul", "div", "divu", "rem", "remu"):
        assert need in ops, need


def _load_spike():
    """按需加载 SPIKE 权威解释器 rv32sim 作为逐指令黄金参照（非内核、非插件依赖）。"""
    global _SPIKE
    if _SPIKE is None:
        path = ROOT / "baremetal" / "tools" / "rv32_spike" / "rv32sim.py"
        spec = importlib.util.spec_from_file_location("rv32sim_golden", str(path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _SPIKE = mod
    return _SPIKE


_SPIKE = None


# ---- 对拍机器：仅经 MachineView 动作面（寄存器 / 小端访存 / pc / halt）----
class RefMachine:
    def __init__(self, pc=0):
        self.regs = [0] * 32
        self.mem: dict[int, int] = {}      # 绝对地址 -> 字节
        self.csrs: dict[int, int] = {}     # CSR 地址 -> 32 位值（独立地址空间）
        self._pc = pc & 0xFFFFFFFF
        self.exit = None

    def read_reg(self, idx):
        return self.regs[idx] if idx else 0

    def write_reg(self, idx, value):
        if idx:
            self.regs[idx] = value & 0xFFFFFFFF

    def load(self, addr, width):
        v = 0
        for k in range(width):
            v |= (self.mem.get((addr + k) & 0xFFFFFFFF, 0) & 0xFF) << (8 * k)
        return v

    def store(self, addr, value, width):
        for k in range(width):
            self.mem[(addr + k) & 0xFFFFFFFF] = (value >> (8 * k)) & 0xFF

    def pc(self):
        return self._pc

    def set_pc(self, value):
        self._pc = value & 0xFFFFFFFF

    def halt(self, exit_code):
        self.exit = exit_code

    # ---- CSR 动作面（插件经鸭子类型可选探测；仅本参照机器建模）----
    def csr_read(self, addr):
        return self.csrs.get(addr, 0) & 0xFFFFFFFF

    def csr_write(self, addr, value):
        self.csrs[addr] = value & 0xFFFFFFFF


def _s32(x):
    x &= 0xFFFFFFFF
    return x - 0x100000000 if x >= 0x80000000 else x


def _u32(x):
    return x & 0xFFFFFFFF


# ---- 把 32 位指令字解码成 DecodedInstr（模拟执行器的解码步）----
def _decode(w, pc):
    op = w & 0x7F
    rd = (w >> 7) & 0x1F
    f3 = (w >> 12) & 0x7
    rs1 = (w >> 15) & 0x1F
    rs2 = (w >> 20) & 0x1F
    f7 = (w >> 25) & 0x7F

    def imm_i():
        v = (w >> 20) & 0xFFF
        return v - 0x1000 if v >= 0x800 else v

    def imm_s():
        v = ((f7 << 5) | ((w >> 7) & 0x1F)) & 0xFFF
        return v - 0x1000 if v >= 0x800 else v

    def imm_b():
        v = (((w >> 31) & 1) << 12) | (((w >> 7) & 1) << 11) | \
            (((w >> 25) & 0x3F) << 5) | (((w >> 8) & 0xF) << 1)
        return _s32(v << 19) >> 19 if v & 0x1000 else v

    def imm_j():
        v = (((w >> 31) & 1) << 20) | (((w >> 12) & 0xFF) << 12) | \
            (((w >> 20) & 1) << 11) | (((w >> 21) & 0x3FF) << 1)
        return _s32(v << 11) >> 11 if v & 0x100000 else v

    if op == 0x37:
        return dyn.DecodedInstr("lui", rd, imm=_s32(w & 0xFFFFF000), pc=pc)
    if op == 0x17:
        return dyn.DecodedInstr("auipc", rd, imm=_s32(w & 0xFFFFF000), pc=pc)
    if op == 0x6F:
        return dyn.DecodedInstr("jal", rd, imm=imm_j(), pc=pc)
    if op == 0x67:
        return dyn.DecodedInstr("jalr", rd, rs1, imm=imm_i(), pc=pc)
    if op == 0x63:
        name = {0: "beq", 1: "bne", 4: "blt", 5: "bge", 6: "bltu", 7: "bgeu"}[f3]
        return dyn.DecodedInstr(name, 0, rs1, rs2, imm=imm_b(), pc=pc)
    if op == 0x03:
        name = {0: "lb", 1: "lh", 2: "lw", 4: "lbu", 5: "lhu", 6: "lwu"}[f3]
        return dyn.DecodedInstr(name, rd, rs1, imm=imm_i(), pc=pc)
    if op == 0x23:
        name = {0: "sb", 1: "sh", 2: "sw"}[f3]
        return dyn.DecodedInstr(name, 0, rs1, rs2, imm=imm_s(), pc=pc)
    if op == 0x13:
        raw = (w >> 20) & 0xFFF
        if f3 == 5:
            sub = raw >> 6
            name = "srli" if sub == 0 else ("srai" if sub == 0x10 else None)
            if name is None:
                raise AssertionError(f"未知 funct6=0x{sub:02X}")
        else:
            name = {0: "addi", 1: "slli", 2: "slti", 3: "sltiu",
                    4: "xori", 6: "ori", 7: "andi"}[f3]
        return dyn.DecodedInstr(name, rd, rs1, imm=imm_i(), pc=pc)
    if op == 0x33:
        if f7 == 0x00:
            name = ["add", "sll", "slt", "sltu", "xor", "srl", "or", "and"][f3]
        elif f7 == 0x20:
            name = {0: "sub", 5: "sra"}[f3]
        elif f7 == 0x01:
            name = ["mul", "mulh", "mulhsu", "mulhu", "div", "divu", "rem", "remu"][f3]
        else:
            raise AssertionError(f"未知 funct7=0x{f7:02X}")
        return dyn.DecodedInstr(name, rd, rs1, rs2, pc=pc)
    if op == 0x73:                                       # SYSTEM: ecall/ebreak/CSR
        csr = (w >> 20) & 0xFFF                          # imm[11:0] = CSR 地址 / funct12
        if f3 == 0:
            name = {0: "ecall", 1: "ebreak"}.get(csr)
            if name is None:
                raise AssertionError(f"未知 SYSTEM funct12=0x{csr:03X}")
            return dyn.DecodedInstr(name, 0, 0, 0, imm=csr, pc=pc)
        if f3 == 4:
            raise AssertionError("非法 CSR 编码 funct3=4")
        name = {1: "csrrw", 2: "csrrs", 3: "csrrc",
                5: "csrrwi", 6: "csrrsi", 7: "csrrci"}[f3]
        return dyn.DecodedInstr(name, rd, rs1, imm=csr, pc=pc)
    if op == 0x0F:                                       # MISC-MEM: fence / fence.i
        name = {0: "fence", 1: "fence.i"}[f3]
        return dyn.DecodedInstr(name, 0, 0, 0, imm=0, pc=pc)
    raise AssertionError(f"未知 opcode 0x{op:02X}")


def encR(f7, rs2, rs1, f3, rd):
    return ((f7 & 0x7F) << 25) | ((rs2 & 0x1F) << 20) | ((rs1 & 0x1F) << 15) | \
        ((f3 & 7) << 12) | ((rd & 0x1F) << 7) | 0x33


def encI(imm, rs1, f3, rd, op=0x13):
    return ((imm & 0xFFF) << 20) | ((rs1 & 0x1F) << 15) | ((f3 & 7) << 12) | \
        ((rd & 0x1F) << 7) | op


def encS(imm, rs2, rs1, f3):
    i = imm & 0xFFF
    return ((i >> 5) << 25) | ((rs2 & 0x1F) << 20) | ((rs1 & 0x1F) << 15) | \
        ((f3 & 7) << 12) | ((i & 0x1F) << 7) | 0x23


def encB(imm, rs2, rs1, f3):
    u = imm & 0x1FFF
    return (((u >> 12) & 1) << 31) | (((u >> 5) & 0x3F) << 25) | ((rs2 & 0x1F) << 20) | \
        ((rs1 & 0x1F) << 15) | ((f3 & 7) << 12) | (((u >> 1) & 0xF) << 8) | \
        (((u >> 11) & 1) << 7) | 0x63


def encU(imm20, rd, op=0x37):
    return ((imm20 & 0xFFFFF) << 12) | ((rd & 0x1F) << 7) | op


def encJ(imm, rd):
    u = imm & 0x1FFFFF
    return (((u >> 20) & 1) << 31) | (((u >> 1) & 0x3FF) << 21) | \
        (((u >> 11) & 1) << 20) | (((u >> 12) & 0xFF) << 12) | ((rd & 0x1F) << 7) | 0x6F


_AR_PAIRS = [(0, 0), (5, 3), (0xFFFFFFFF, 1), (0x80000000, 0xFFFFFFFF),
             (0x7FFFFFFF, 1), (100, 7), (1, 32)]
_A_VALS = [0, 5, 0xFFFFFFFF, 0x80000000, 0x7FFFFFFF]
_IMM_VALS = [0, 1, -1, 5, -0x800]

_RALU = {"add": (0x00, 0x0), "sub": (0x20, 0x0), "and": (0x00, 0x7), "or": (0x00, 0x6),
         "xor": (0x00, 0x4), "sll": (0x00, 0x1), "srl": (0x00, 0x5), "sra": (0x20, 0x5),
         "slt": (0x00, 0x2), "sltu": (0x00, 0x3), "mul": (0x01, 0x0), "div": (0x01, 0x4),
         "divu": (0x01, 0x5), "rem": (0x01, 0x6), "remu": (0x01, 0x7)}

_CORPUS: list[tuple[str, int, dict]] = []
for _n, (_f7, _f3) in _RALU.items():
    for _a, _b in _AR_PAIRS:
        _CORPUS.append((_n, encR(_f7, 6, 5, _f3, 7), {5: _a, 6: _b}))
for _n, _f3 in (("addi", 0), ("slti", 2), ("sltiu", 3), ("xori", 4), ("ori", 6), ("andi", 7)):
    for _a in _A_VALS:
        for _im in _IMM_VALS:
            _CORPUS.append((_n, encI(_im, 5, _f3, 7), {5: _a}))
for _n, (_f3, _fn) in (("slli", (1, lambda s: s)), ("srli", (5, lambda s: s)),
                       ("srai", (5, lambda s: (1 << 10) | s))):
    for _a in _A_VALS:
        for _sh in (0, 1, 5, 15, 31):
            _CORPUS.append((_n, encI(_fn(_sh), 5, _f3, 7), {5: _a}))
for _n, _f3 in (("beq", 0), ("bne", 1), ("blt", 4), ("bge", 5), ("bltu", 6), ("bgeu", 7)):
    for _a, _b in _AR_PAIRS:
        for _off in (0x10, -0x10):
            _CORPUS.append((_n, encB(_off, 6, 5, _f3), {5: _a, 6: _b}))
for _off in (0, 0x10, -0x10, 0x100):
    _CORPUS.append(("jal", encJ(_off, 7), {}))
for _a in _A_VALS:
    for _im in (0, 1, 4, -4):
        _CORPUS.append(("jalr", encI(_im, 5, 0, 7, op=0x67), {5: _a}))
for _imm20 in (0, 1, 0x80000, 0xFFFFF, 0x7FFFF):
    _CORPUS.append(("lui", encU(_imm20, 7, 0x37), {}))
    _CORPUS.append(("auipc", encU(_imm20, 7, 0x17), {}))


def _plugin_run(instr, seed, pc_addr):
    m = RefMachine(pc_addr + 4)
    for idx, val in seed.items():
        m.write_reg(idx, val)
    dsp.PLUGIN.execute(instr, m)
    return m


def _spike_new(seed, memseed=None):
    sim_mod = _load_spike()
    sim = sim_mod.RV32Sim.__new__(sim_mod.RV32Sim)
    sim.ram = bytearray(0x4000)
    sim.out = []
    sim.done = False
    sim.exit_code = 0
    sim.x = [0] * 32
    for idx, val in seed.items():
        sim.x[idx] = _s32(val)
    for a, b in (memseed or {}).items():
        sim.ram[a - sim_mod.BASE] = b
    return sim


def _spike_run(word, seed, pc_addr):
    sim = _spike_new(seed)
    ret = sim._step(word, _u32(pc_addr + 4))
    return sim, ret


@pytest.mark.parametrize(
    "name,word,seed", _CORPUS,
    ids=[f"{c[0]}#{i}" for i, c in enumerate(_CORPUS)])
def test_dynamics_rv32im_spike_parity(name, word, seed):
    """逐指令 对拍：同一指令字分别喂给 SPIKE 与插件，寄存器文件 / pc 必须逐位相同。"""
    instr = _decode(word, 0x1000)
    assert instr.op == name                                   # 解码助记符须与编码一致
    assert instr.op in dsp.PLUGIN.wired_ops()
    sim, ret = _spike_run(word, seed, 0x1000)
    m = _plugin_run(instr, seed, 0x1000)
    for idx in range(32):
        assert _u32(m.read_reg(idx)) == _u32(sim.x[idx]), \
            (name, idx, hex(m.read_reg(idx)), hex(sim.x[idx]))
    assert _u32(m.pc()) == _u32(ret), (name, hex(m.pc()), hex(ret))


# ---- 访存 对拍（仅取 SPIKE 实现的 lw/lb/lbu/lwu/sw/sb）----
_ADDR = 0x80000000 + 0x100
_MEM_CORPUS = [
    ("sw", encS(0, 6, 5, 2), {5: _ADDR, 6: 0xDEADBEEF}, {}, _ADDR, _ADDR + 4),
    ("sb", encS(0, 6, 5, 0), {5: _ADDR, 6: 0x11223344}, {}, _ADDR, _ADDR + 1),
    ("lw", encI(0, 5, 2, 7, op=0x03), {5: _ADDR}, {_ADDR: 0xEF, _ADDR + 1: 0xBE, _ADDR + 2: 0xAD, _ADDR + 3: 0xDE}, _ADDR, _ADDR + 4),
    ("lb", encI(0, 5, 0, 7, op=0x03), {5: _ADDR}, {_ADDR: 0x80}, _ADDR, _ADDR + 1),
    ("lbu", encI(0, 5, 4, 7, op=0x03), {5: _ADDR}, {_ADDR: 0x80}, _ADDR, _ADDR + 1),
    ("lwu", encI(0, 5, 6, 7, op=0x03), {5: _ADDR}, {_ADDR: 0xFF, _ADDR + 1: 0xFF, _ADDR + 2: 0xFF, _ADDR + 3: 0xFF}, _ADDR, _ADDR + 4),
]


@pytest.mark.parametrize("name,word,seed,memseed,lo,hi", _MEM_CORPUS, ids=[c[0] for c in _MEM_CORPUS])
def test_dynamics_rv32im_spike_parity_mem(name, word, seed, memseed, lo, hi):
    instr = _decode(word, 0x1000)
    assert instr.op == name and instr.op in dsp.PLUGIN.wired_ops()
    sim_mod = _load_spike()
    m = RefMachine(0x1004)
    for idx, val in seed.items():
        m.write_reg(idx, val)
    for a, b in memseed.items():
        m.mem[a] = b
    sim = _spike_new(seed, memseed)
    ret = sim._step(word, 0x1004)
    dsp.PLUGIN.execute(instr, m)
    for idx in range(32):
        assert _u32(m.read_reg(idx)) == _u32(sim.x[idx]), (name, idx)
    for a in range(lo, hi):
        assert m.mem.get(a, 0) == sim.ram[a - sim_mod.BASE], (name, hex(a))


# ---- 规格黄金锁：SPIKE 未覆盖(半字访问 / mulh 族)与关键边界，手写期望值直锁 ----
def _exec(op, rd=7, rs1=5, rs2=6, imm=0, pc=0x1000, regs=None, mem=None, csrs=None):
    m = RefMachine(pc + 4)
    for idx, val in (regs or {}).items():
        m.write_reg(idx, val)
    for a, b in (mem or {}).items():
        m.mem[a] = b
    for a, v in (csrs or {}).items():
        m.csrs[a] = v
    assert dsp.PLUGIN.execute(dyn.DecodedInstr(op, rd, rs1, rs2, imm, pc), m) is True
    return m


def test_golden_mulh_family():
    assert _exec("mulh", regs={5: 0x80000000, 6: 0xFFFFFFFF}).read_reg(7) == 0
    assert _exec("mulhsu", regs={5: 0xFFFFFFFF, 6: 2}).read_reg(7) == 0xFFFFFFFF
    assert _exec("mulhu", regs={5: 0xFFFFFFFF, 6: 0xFFFFFFFF}).read_reg(7) == 0xFFFFFFFE
    assert _exec("mulh", regs={5: 0x7FFFFFFF, 6: 0x7FFFFFFF}).read_reg(7) == 0x3FFFFFFF


def test_golden_halfword_access():
    assert _exec("lh", regs={5: _ADDR}, mem={_ADDR: 0x00, _ADDR + 1: 0x80}).read_reg(7) == 0xFFFF8000
    assert _exec("lhu", regs={5: _ADDR}, mem={_ADDR: 0x00, _ADDR + 1: 0x80}).read_reg(7) == 0x8000
    m = _exec("sh", regs={5: _ADDR, 6: 0xABCD1234})
    assert m.mem[_ADDR] == 0x34 and m.mem[_ADDR + 1] == 0x12


def test_golden_srai_negative():
    assert _exec("srai", regs={5: 0x80000000}, imm=4).read_reg(7) == 0xF8000000


def test_golden_div_rem_edge():
    assert _exec("div", regs={5: 0x80000000, 6: 0xFFFFFFFF}).read_reg(7) == 0x80000000  # INT_MIN/-1
    assert _exec("div", regs={5: 0x12345678, 6: 0}).read_reg(7) == 0xFFFFFFFF          # 除零 => -1
    assert _exec("rem", regs={5: 0x80000000, 6: 0xFFFFFFFF}).read_reg(7) == 0            # INT_MIN%-1
    assert _exec("rem", regs={5: 0x12345678, 6: 0}).read_reg(7) == 0x12345678           # 除零 => 被除数
    assert _exec("divu", regs={5: 0xFFFFFFFF, 6: 0}).read_reg(7) == 0xFFFFFFFF
    assert _exec("remu", regs={5: 0x12345678, 6: 0}).read_reg(7) == 0x12345678


def test_golden_jalr_clears_lsb():
    m = _exec("jalr", regs={5: 0x10000003}, imm=1, pc=0x1000)
    assert m.pc() == 0x10000004 and m.read_reg(7) == 0x1004


def test_golden_branch_taken_vs_not():
    assert _exec("beq", regs={5: 5, 6: 5}, imm=0x10, pc=0x1000).pc() == 0x1010
    assert _exec("beq", regs={5: 5, 6: 6}, imm=0x10, pc=0x1000).pc() == 0x1004   # 未转移
    assert _exec("blt", regs={5: 0xFFFFFFFF, 6: 1}, imm=-0x10, pc=0x1000).pc() == 0xFF0
    assert _exec("bgeu", regs={5: 0xFFFFFFFF, 6: 1}, imm=0x10, pc=0x1000).pc() == 0x1010   # 无符号转移


# ---- SYSTEM 规格黄金锁：CSR 读改写 / fence nop / ecall（SPIKE 未建模 CSR/FENCE，按规格直锁）----
def test_dynamics_system_ops_wired():
    ops = set(dsp.PLUGIN.wired_ops())
    for need in ("fence", "fence.i", "ecall",
                 "csrrw", "csrrs", "csrrc", "csrrwi", "csrrsi", "csrrci"):
        assert need in ops, need


def test_golden_csrrw_rmw():
    m = _exec("csrrw", rd=7, rs1=5, imm=0x300, regs={5: 0xABCD}, csrs={0x300: 0x1111})
    assert m.read_reg(7) == 0x1111          # rd = 旧值
    assert m.csrs[0x300] == 0xABCD          # csr = rs1
    m = _exec("csrrw", rd=7, rs1=0, imm=0x300, csrs={0x300: 0x9})   # rs1==x0 仍无条件写 0
    assert m.csrs[0x300] == 0


def test_golden_csrrs_csrrc_set_clear():
    m = _exec("csrrs", rd=7, rs1=5, imm=0x300, regs={5: 0x0F}, csrs={0x300: 0xF0})
    assert m.read_reg(7) == 0xF0 and m.csrs[0x300] == 0xFF
    m = _exec("csrrc", rd=7, rs1=5, imm=0x300, regs={5: 0x0F}, csrs={0x300: 0xFF})
    assert m.read_reg(7) == 0xFF and m.csrs[0x300] == 0xF0


def test_golden_csrr_pure_read():
    m = _exec("csrrs", rd=7, rs1=0, imm=0x300, csrs={0x300: 0x123})   # csrrs rd,csr,x0 == csrr
    assert m.read_reg(7) == 0x123 and m.csrs[0x300] == 0x123         # 只读不写回


def test_golden_csr_immediate_forms():
    m = _exec("csrrwi", rd=7, rs1=5, imm=0x300, csrs={0x300: 0xEE})   # uimm=5
    assert m.read_reg(7) == 0xEE and m.csrs[0x300] == 5
    m = _exec("csrrsi", rd=7, rs1=0x1, imm=0x300, csrs={0x300: 0xF0})
    assert m.csrs[0x300] == 0xF1
    m = _exec("csrrci", rd=7, rs1=0x1, imm=0x300, csrs={0x300: 0xFF})
    assert m.csrs[0x300] == 0xFE
    m = _exec("csrrsi", rd=7, rs1=0, imm=0x300, csrs={0x300: 0xF0})   # uimm==0 不写
    assert m.csrs[0x300] == 0xF0


def test_golden_fence_is_noop():
    for nm in ("fence", "fence.i"):
        m = _exec(nm, regs={5: 0x99}, mem={_ADDR: 0x77})
        assert m.read_reg(5) == 0x99 and m.read_reg(7) == 0
        assert m.mem[_ADDR] == 0x77 and m.pc() == 0x1004            # 不改寄存器/内存/pc


def test_golden_ecall_defers_unknown_abi():
    m = RefMachine(0x1004)
    m.write_reg(17, 0x1234)                                          # 非 system_reset
    assert dsp.PLUGIN.execute(dyn.DecodedInstr("ecall", pc=0x1000), m) is False
    assert m.exit is None                                            # 不静默 halt


def test_csr_without_machine_capability_defers():
    # 机器不提供 csr_read/csr_write → CSR 指令返回 False 回退原生，绝不崩溃/伪造
    for nm in ("csrrw", "csrrs", "csrrc", "csrrwi", "csrrsi", "csrrci"):
        assert dsp.PLUGIN.execute(
            dyn.DecodedInstr(nm, rd=7, rs1=5, imm=0x300), object()) is False


def test_dynamics_ecall_spike_parity():
    """ecall system_reset：SPIKE（done=True）与插件（halt）均在收到 a7==0x6758 时停机。"""
    word = 0x00000073                                                # ecall
    instr = _decode(word, 0x1000)
    assert instr.op == "ecall" and instr.op in dsp.PLUGIN.wired_ops()
    seed = {17: 0x6758, 10: 0x7}
    sim, _ret = _spike_run(word, seed, 0x1000)
    m = RefMachine(0x1004)
    for idx, val in seed.items():
        m.write_reg(idx, val)
    assert dsp.PLUGIN.execute(instr, m) is True
    assert sim.done is True and m.exit == 0x7                        # 二者均停机
    assert m.read_reg(17) == _u32(sim.x[17])                         # a7 保持


# ============================================================
# 2b. 执行器试点闭环（端到端）：插件逐条驱动真实 RV32I 程序 vs SPIKE 原生
# ============================================================

class SpikeMachine:
    """把真实权威解释器 :class:`RV32Sim` 适配到 :class:`MachineView` 最小动作面。

    寄存器 / 内存 / MMIO / 停机约定全部代理给 SPIKE 实例本体（含 UART / sifive_test），
    故“插件驱动的整程序跑”与“SPIKE 原生跑”只隔离**指令语义**一处变量。
    """

    def __init__(self, sim, pc):
        self.sim = sim
        self._pc = pc
        self._next = None

    def read_reg(self, idx):
        return self.sim.x[idx]

    def write_reg(self, idx, value):
        if idx:                                  # x0 恒零（与 SPIKE setrd 同）
            self.sim.x[idx] = _s32(value)

    def load(self, addr, width):
        if width == 4:
            return self.sim._r32(addr)
        if width == 1:
            return self.sim._r8(addr)
        raise AssertionError(f"试点：width {width} 超出 SPIKE 建模（lh/lhu/sh 未实现）")

    def store(self, addr, value, width):
        if width == 4:
            self.sim._w32(addr, value)
        elif width == 1:
            self.sim._w8(addr, value)
        else:
            raise AssertionError(f"试点：width {width} 超出 SPIKE 建模")

    def pc(self):
        return self._pc

    def set_pc(self, value):
        self._next = _u32(value)                 # 仅跳转 / 分支改写；否则驱动顺序 +4

    def next_pc(self):
        """可选能力探测点：回报跳转 / 分支后的下一地址（None = 顺序执行）。

        生产集成入口 :func:`drive_program` 经此约定推进 PC，替代原先写死在
        测试里的 ``view._next`` 私有读取，使适配器与驱动器之间的缝保持中性。
        """
        return self._next

    def halt(self, exit_code):
        self.sim.done = True


def _mk_sim(words, data=None):
    """用指令字序列在 SPIKE 稀疏 RAM 的 BASE 处搭一段可原生执行的 RV32I 程序。"""
    sim_mod = _load_spike()
    sim = sim_mod.RV32Sim.__new__(sim_mod.RV32Sim)
    sim.ram = bytearray(0x4000)
    sim.out = []
    sim.done = False
    sim.exit_code = 0
    sim.max_steps = 100_000
    sim.x = [0] * 32
    sim.entry = sim_mod.BASE
    for i, w in enumerate(words):
        sim.ram[4 * i:4 * i + 4] = (w & 0xFFFFFFFF).to_bytes(4, "little")
    for off, v in (data or {}).items():
        sim.ram[off:off + 4] = (v & 0xFFFFFFFF).to_bytes(4, "little")
    return sim


_HALP = [encU(0x100, 1, 0x37), encU(0x5, 2, 0x37), encI(0x555, 2, 6, 2), encS(0, 2, 1, 2)]


def _prog_arith():
    w = [encI(20, 0, 0, 5), encI(7, 0, 0, 6),
         encR(0x00, 6, 5, 0x0, 7), encR(0x20, 6, 5, 0x0, 8),   # add sub
         encR(0x00, 6, 5, 0x7, 9), encR(0x00, 6, 5, 0x6, 10),   # and or
         encR(0x00, 6, 5, 0x4, 11), encR(0x00, 6, 5, 0x1, 12),  # xor sll
         encR(0x00, 6, 5, 0x5, 13), encR(0x20, 6, 5, 0x5, 14),  # srl sra
         encR(0x00, 6, 5, 0x2, 15), encR(0x00, 6, 5, 0x3, 16),  # slt sltu
         encU(0x80000, 28, 0x37), encI(1000, 0, 0, 17),         # lui BASE; data
         encS(0x400, 17, 28, 2), encI(0x400, 28, 2, 18)]        # sw / lw
    return w + _HALP


def _prog_loop():
    w = [encI(0, 0, 0, 5), encI(1, 0, 0, 6), encI(11, 0, 0, 7),      # acc i limit
         encR(0x00, 6, 5, 0x0, 5), encI(1, 6, 0, 6),                 # +12 LOOP add; +16 i+=1
         encB(-8, 7, 6, 4)]                                          # +20 blt x6,x7 -> +12
    return w + _HALP


def _prog_call():
    # +0 jal→FUNC(+20)；+4..+16 为 halt 序（返回落点，jal 已跳过）；FUNC 尾 jalr 回 +4
    w = [encJ(20, 1)]                            # +0  jal x1, +20 -> FUNC, x1=+4
    w += _HALP                                    # +4/+8/+12/+16 halt（返回至此）
    w += [encI(42, 0, 0, 6),                      # +20 FUNC addi x6,x0,42
          encI(0, 1, 0, 0, op=0x67)]              # +24 jalr x0, 0(x1) -> 返回 +4
    return w


def _prog_uart():
    w = [encU(0x10000, 5, 0x37),      # lui x5, 0x10000 -> UART 0x10000000
         encI(0x48, 0, 0, 6), encS(0, 6, 5, 0),   # sb 'H'
         encI(0x69, 0, 0, 6), encS(0, 6, 5, 0)]   # sb 'i'
    return w + _HALP


def _run_native(sim):
    sim.x[2] = 0
    sim.x[1] = 0
    sim.run()
    return sim


def _run_plugin(sim):
    """经生产集成入口 :func:`drive_program` 逐条驱动真 SPIKE 机器到停机。"""
    rep = pilot.drive_program(
        entry_pc=sim.entry,
        fetch=sim._r32,
        decode=_decode,
        view_factory=lambda pc: SpikeMachine(sim, pc),
        is_halted=lambda: sim.done,
        max_steps=sim.max_steps + 1,
    )
    assert rep.halted and rep.fully_plugin_driven   # 全程插件语义，无一例回退原生
    return sim, rep.steps


_PILOT_PROGRAMS = {
    "arith": _prog_arith,
    "loop": _prog_loop,
    "call": _prog_call,
    "uart": _prog_uart,
}


@pytest.mark.parametrize("name", list(_PILOT_PROGRAMS), ids=list(_PILOT_PROGRAMS))
def test_dynamics_executor_pilot_end_to_end(name):
    """RV32I 端到端语义闭环：同一段程序，“插件逐条驱动”与“SPIKE 原生”最终态逐位相同。"""
    words = _PILOT_PROGRAMS[name]()
    n = _run_native(_mk_sim(words))
    p, _steps = _run_plugin(_mk_sim(words))
    assert p.done and n.done
    assert _u32(p.exit_code) == _u32(n.exit_code), (name, p.exit_code, n.exit_code)
    assert "".join(p.out) == "".join(n.out), (name, "".join(p.out), "".join(n.out))
    for idx in range(32):
        assert _u32(p.x[idx]) == _u32(n.x[idx]), (name, idx, _u32(p.x[idx]), _u32(n.x[idx]))


def test_dynamics_executor_pilot_loop_reaches_expected_sum():
    """控制流程序（blt 循环）插件驱动跑完：acc = 1+2+…+10 = 55，且确实走了转移。"""
    _p, steps = _run_plugin(_mk_sim(_prog_loop()))
    assert _p.x[5] == 55
    assert steps > 8                       # 循环多轮，非一次线性到底


# ============================================================
# 2c. 生产集成入口本体：只依赖中性契约，不依赖任何具体执行器
# ============================================================


class _FakeMachine:
    """最小 MachineView 实现（纯内存 register/ram）——证明入口与执行器解耦。"""

    def __init__(self, text, data, start_pc=0):
        self.text = list(text)
        self.data = {k: v for k, v in data.items()}
        self.x = [0] * 32
        self._pc = start_pc
        self._next = None
        self.halted_with = None

    def read_reg(self, idx):
        return self.x[idx]

    def write_reg(self, idx, value):
        if idx:
            self.x[idx] = _s32(value)

    def load(self, addr, width):
        return self.data.get(addr, 0)

    def store(self, addr, value, width):
        self.data[addr] = _u32(value)

    def pc(self):
        return self._pc

    def set_pc(self, value):
        self._next = _u32(value)

    def next_pc(self):
        """一次性报告下一地址：读后复位，避免陈旧跳转目标污染后续顺序步。"""
        value, self._next = self._next, None
        return value

    def halt(self, exit_code):
        self.halted_with = exit_code


class _OpSubsetBackend:
    """按 op 子集认领的后端：用于验证覆盖护栏与原生回退记账。"""

    def __init__(self, name, ops, fn=None):
        self._name = name
        self.ops = set(ops)
        self.fn = fn

    @property
    def name(self):
        return self._name

    def supports(self, instr):
        return instr.op in self.ops

    def execute(self, instr, machine):
        return self.fn(instr, machine) if self.fn else instr.op in self.ops


def _drive_fake(machine, **kw):
    """以纯假机器调用生产入口；默认走真 ``"dynamic"`` 插件语义。

    取指越界回 0（RV 的 ``addi x0,x0,0`` = nop），使无 halt 程序的 PC 自由跑到
    步数预算，从而由 :class:`PilotRunaway` 显式报错而非依赖执行器内存模型。
    """
    kw.setdefault("ensure_backend", "dynamic")
    return pilot.drive_program(
        entry_pc=0,
        fetch=lambda pc: machine.text[pc // 4] if pc // 4 < len(machine.text) else 0,
        decode=_decode,
        view_factory=lambda pc: machine,
        is_halted=lambda: machine.halted_with is not None,
        **kw,
    )


def _EXIT(code=0):
    """假机器上的停机序列：``li a7,0x6758``（lui+addi）/ ``li a0,code`` / ``ecall``。

    与 SPIKE 的 ``sifive_test`` 写 MMIO 停机不同路：这里走执行器已建模的
    system_reset ABI（插件 ``ecall`` 分支 → ``halt(a0)``），不依赖任何访存布局。
    a7 = 0x6758 超 12 位立即数，故按 RV 惯例拆成 lui + addi（addi 立即数取
    12 位有符号编码，与 SPIKE ``li`` 展开同形）。
    """
    return [encU(0x6, 17), encI(0x758, 17, 0, 17),
            encI(code & 0xFFF, 0, 0, 10), encI(0, 0, 0, 0, op=0x73)]


def _mini_decode(op, pc, rd=0, rs1=0, rs2=0, imm=0):
    """直接造中性指令（不走 RV 编码）：只给本入口自检用，避免编码细节抢戏。"""
    return dyn.DecodedInstr(op, rd, rs1, rs2, imm, pc)


def test_drive_program_backend_agnostic_on_fake_machine():
    """驱动器只认中性契约：在不依赖 SPIKE / baremetal 的假机器上跑通插件语义。"""
    dyn.set_active(None)          # 只清激活态（登记表保持），避免跳用例泄漏被当成结果
    m = _FakeMachine([encI(5, 0, 0, 5), encI(37, 0, 0, 6),
                      encR(0x00, 6, 5, 0x0, 7)] + _EXIT(), {})
    rep = _drive_fake(m)
    assert m.x[7] == 42 and m.halted_with == 0
    assert rep.steps == 6 and rep.end_pc == 6 * 4   # end_pc = halt 现场（ecall）
    assert rep.halted and rep.fully_plugin_driven and rep.native_fallback_ops == ()
    assert dyn.active_backend() is None          # 插件激活生命周期不外溢


def test_drive_program_reports_native_fallback_honestly():
    """显式关闭全覆盖护栏时，未认领指令走原生兜底并被记入报告（绝不隐没）。"""
    dyn.set_active(None)
    # 子集后端只认 add / ecall（两者均在其动作面内真正落地）；
    # addi 不认领 → 必须逐条回退到原生，并且可审计。
    m = _FakeMachine([0] * 4, {})
    prog = [_mini_decode("addi", 0, rd=17, imm=0x6758),    # 0  预置 system_reset ABI
            _mini_decode("add", 4, rd=7, rs1=5, rs2=6),    # 1  未认领 → 兜底
            _mini_decode("add", 8, rd=8, rs1=5, rs2=6),    # 2  认领
            _mini_decode("ecall", 12),                      # 3  停机（认领）
            _mini_decode("addi", 16, rd=9, imm=7)]         # 4  不应被取到
    seen: list[str] = []

    def _decode_at(w, pc):
        return prog[pc // 4]

    def _native(instr, view):
        """极简“原生”兜底：只补子集后端不认领的 addi。"""
        seen.append(instr.op)
        view.write_reg(instr.rd, _u32(instr.imm))

    def _subset_execute(instr, machine):
        if instr.op == "add":
            machine.write_reg(instr.rd,
                              _u32(machine.read_reg(instr.rs1) + machine.read_reg(instr.rs2)))
            return True
        if instr.op == "ecall":
            machine.halt(machine.read_reg(10))
            return True
        return False

    backend = _OpSubsetBackend("pilot-subset", {"add", "ecall"}, fn=_subset_execute)
    dyn.register_backend(backend, activate=True)
    try:
        rep = pilot.drive_program(
            entry_pc=0,
            fetch=lambda pc: m.text[pc // 4] if pc // 4 < len(m.text) else 0,
            decode=_decode_at,
            view_factory=lambda pc: m,
            is_halted=lambda: m.halted_with is not None,
            ensure_backend=None, require_plugin_coverage=False, native=_native)
    finally:
        dyn.unregister_backend("pilot-subset")
        dyn.set_active(None)                              # 不受跳用例遗留的登记影响
    assert rep.native_fallback_ops == ("addi",)          # 回退指令逐个记账
    assert seen == ["addi"] and m.x[17] == 0x6758
    assert not rep.fully_plugin_driven
    assert m.x[7] == 0 and m.x[8] == 0                   # add 由子集后端落地
    assert m.halted_with == 0 and rep.halted and rep.steps == 3
    assert rep.end_pc == 12                              # 停在 halt 现场，不多取一条
    assert prog[4].rd == 9 and m.x[9] == 0               # 停机后不再取下一条


def test_drive_program_rejects_unwired_instruction():
    """默认要求全覆盖：取到后端不认领的指令时显式失败，不静默当 nop 放过。"""
    m = _FakeMachine([0] * 4, {})
    prog = [_mini_decode("addi", 0, rd=5, imm=1),
            _mini_decode("sub", 4, rd=7, rs1=5, rs2=6),
            _mini_decode("ecall", 8)]
    dyn.set_active(None)
    dyn.register_backend(
        _OpSubsetBackend("pilot-narrow", {"addi", "ecall"}), activate=True)

    def _decode_at(w, pc):
        return prog[pc // 4]

    try:
        with pytest.raises(pilot.PilotUnsupported, match="sub"):
            pilot.drive_program(
                entry_pc=0, fetch=lambda pc: 0,
                decode=_decode_at, view_factory=lambda pc: m,
                is_halted=lambda: m.halted_with is not None,
                ensure_backend=None)
    finally:
        dyn.unregister_backend("pilot-narrow")
        dyn.set_active(None)
    assert m.x[7] == 0                              # 失败前未产生任何副作用
    assert m.halted_with is None


def test_drive_program_rejects_claimed_but_unexecuted():
    """后端认领（supports 真）却未落地（execute 假）时同样显式失败，不静默当 nop。

    对应真实插件行为：CSR 若机器未提供 csr_read/csr_write、非复位 ecall 都会
    supports=True 而 execute=False。旧实现丢弃 execute_or_default 返回值会将其静默跳过。
    """
    m = _FakeMachine([0] * 4, {})
    prog = [_mini_decode("csrrw", 0, rd=5, imm=0x300),   # 认领但执行为假
            _mini_decode("ecall", 4)]
    dyn.set_active(None)
    # 认领 csrrw 但 execute 恒返回 False（模拟无 CSR 动作面的机器）
    dyn.register_backend(
        _OpSubsetBackend("pilot-claim", {"csrrw", "ecall"},
                         fn=lambda i, machine: i.op == "ecall"),
        activate=True)

    def _decode_at(w, pc):
        return prog[pc // 4]

    try:
        with pytest.raises(pilot.PilotUnsupported, match="csrrw"):
            pilot.drive_program(
                entry_pc=0, fetch=lambda pc: 0, decode=_decode_at,
                view_factory=lambda pc: m,
                is_halted=lambda: m.halted_with is not None,
                ensure_backend=None)
    finally:
        dyn.unregister_backend("pilot-claim")
        dyn.set_active(None)
    assert m.halted_with is None                    # 认领未落地即在当时报错，不往后跑


def test_drive_program_guard_rails_runaway_and_no_backend():
    """护栏：死循环超预算报 PilotRunaway；无后端且未交 ensure_backend 时显式报错。"""
    dyn.set_active(None)
    # +0 addi x5,x5,1 / +4 nop / +8 nop / +12 bge x5,x0,-12（恒真，跳回 +0）
    loop = [_mini_decode("addi", 0, rd=5, rs1=5, imm=1),
            _mini_decode("nop", 4), _mini_decode("nop", 8),
            _mini_decode("bge", 12, rs1=5, rs2=0, imm=-12)]

    def _decode_loop(w, pc):
        return loop[(pc >> 2) & 3]

    def _native(instr, view):                      # 无插件认领，语义全靠原生推进
        if instr.op == "addi":
            view.write_reg(instr.rd, _u32(view.read_reg(instr.rs1) + instr.imm))
        elif instr.op == "bge":
            if view.read_reg(instr.rs1) >= view.read_reg(instr.rs2):
                view.set_pc(instr.pc + instr.imm)
        elif instr.op == "ecall":
            view.halt(view.read_reg(10))

    m = _FakeMachine([0] * 4, {})
    with pytest.raises(pilot.PilotRunaway):
        pilot.drive_program(                       # 纯原生跑法：无插件也须受预算约束
            entry_pc=0, fetch=lambda pc: 0, decode=_decode_loop,
            view_factory=lambda pc: m, is_halted=lambda: m.halted_with is not None,
            ensure_backend=None, require_plugin_coverage=False,
            native=_native, max_steps=10)
    assert m.x[5] == 3                             # 10 步内走了 3 遍 addi（预算截断于第 3 轮）

    # 预算边界：刚达到 max_steps 前一步若已停机则不算 runaway
    m3 = _FakeMachine([0] * 2, {})
    rep3 = pilot.drive_program(
        entry_pc=0, fetch=lambda pc: 0,
        decode=lambda w, pc: _mini_decode("ecall", pc),
        view_factory=lambda pc: m3, is_halted=lambda: m3.halted_with is not None,
        ensure_backend=None, require_plugin_coverage=False,
        native=_native, max_steps=1)
    assert rep3.steps == 0 and rep3.halted and rep3.native_fallback_ops == ("ecall",)

    m2 = _FakeMachine(_EXIT(), {})
    with pytest.raises(ValueError, match="ensure_backend"):
        _drive_fake(m2, ensure_backend=None)        # 默认仍要求全覆盖 → 无后端即报错
    assert m2.halted_with is None                  # 报错发生在取指之前

    with pytest.raises(ValueError, match="native"):
        _drive_fake(m2, ensure_backend=None, require_plugin_coverage=False)


def test_executor_pilot_entry_has_no_reverse_coupling():
    """生产入口只依赖 interface + 标准库：不反向耦合执行器 / 内核 / 裸机。"""
    mods = _imported_full(ROOT / "src" / "dynamics" / "rv32_executor_pilot.py")
    bad = [m for m in mods if m.startswith(
        ("baremetal", "rv32sim", "src.kernel", "src.algebra", "src.mbc", "src.domains"))]
    assert not bad, f"生产入口反向耦合：{bad}"
    assert [m for m in mods if m.startswith("src.dynamics")] == ["src.dynamics.interface"]
    assert not _imported_roots(ROOT / "src" / "dynamics" / "rv32_executor_pilot.py") & {
        "sympy", "numpy", "scipy"}


# ---- 界定内核 / 执行器 / 插件 边界：原生执行器不感知插件（耦合单向：试点适配器→两边）----
def test_native_executor_is_plugin_agnostic():
    """权威解释器 rv32sim 源码不得 import src.dynamics / src.algebra / src.kernel：
    执行器对插件事务无知，集成缝单向存在于试点适配器（它同时 import 两边）。"""
    mods = _imported_full(ROOT / "baremetal" / "tools" / "rv32_spike" / "rv32sim.py")
    bad = [m for m in mods if m.startswith(("src.dynamics", "src.algebra", "src.kernel"))]
    assert not bad, f"执行器反向耦合插件/内核：{bad}"


# ============================================================
# 3. 隔离红线：内核不依赖插件层；插件层零重型依赖
# ============================================================

_CORE_DIRS = ("src/kernel", "src/mbc")
_CORE_FILES = ("src/lexer.py", "src/parser.py", "src/ast_nodes.py")


def _core_sources() -> list[Path]:
    files: list[Path] = []
    for d in _CORE_DIRS:
        files += sorted((ROOT / d).rglob("*.py"))
    files += [ROOT / f for f in _CORE_FILES]
    return files


def _imported_roots(path: Path) -> set[str]:
    """静态解析模块真实 import 到的顶层名（避开注释/docstring 里的散文误判）。"""
    import ast
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                roots.add(a.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                roots.add(node.module.split(".", 1)[0])
    return roots


def _imported_full(path: Path) -> list[str]:
    import ast
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    mods: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.append(node.module)
    return mods


@pytest.mark.parametrize("path", _core_sources(), ids=lambda p: str(p.relative_to(ROOT)))
def test_core_never_imports_plugin_contracts(path: Path):
    """纯内核 / 执行器不得 import 代数数或动态语义契约层（核心只依赖接口，接口在插件侧）。"""
    bad = [m for m in _imported_full(path)
           if m.startswith(("src.algebra", "src.dynamics"))]
    assert not bad, f"{path} 反向依赖插件契约层：{bad}"


@pytest.mark.parametrize("path", [
    ROOT / "src/algebra/interface.py",
    ROOT / "src/algebra/algebra_plugin.py",
    ROOT / "src/dynamics/interface.py",
    ROOT / "src/dynamics/dynamic_semantics_plugin.py",
], ids=lambda p: str(p.relative_to(ROOT)))
def test_plugin_contract_has_no_heavy_or_kernel_top_level_import(path: Path):
    """契约层只用标准库：不得 import sympy/numpy/scipy，也不得耦合内核内部。"""
    roots = _imported_roots(path)
    heavy = roots & {"sympy", "numpy", "scipy"}
    assert not heavy, f"{path.name} 引入重型依赖：{sorted(heavy)}"
    kernel = [m for m in _imported_full(path) if m.startswith("src.kernel")]
    assert not kernel, f"{path.name} 耦合内核内部：{kernel}"
