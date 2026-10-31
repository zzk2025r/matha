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
