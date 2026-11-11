# -*- coding: utf-8 -*-
"""阶段 9 · 假实现清算三锁（quantum / quantum_compute / unified_parser）。

背景：三个文件历史上是登记在案的假实现——
  · src/domains/quantum.py：apply_gate 恒 True、measure 恒 0、grover_search 恒 0、
    shor_factor 恒 [3,5]、run_algorithm 只记账不真算；注册层还是平面多参
    lambda（Matha f(a,b) 两侧均为 f(a)(b)，多参签名对 Matha 调用必碎）。
  · src/domains/quantum_compute.py：gate_decompose 无视输入返回固定 7 门；
    grover_iterate 无长度/归一化校验；shor_period_finding 周期起点漏 r=1。
  · src/unified_parser.py：matha_compile 返回不含真实信息的假编译摘要、
    matha_to_llvm / MathaLLVMGenerator.generate 返回假 IR 字符串。

本轮真化（三锁封死回退）：
  1. 手算对拍：Bell/GHZ 振幅、X/H/Z/S/T 门精确作用、CNOT/SWAP/CZ 真置换、
     Grover d=4 逐标记精确命中（振幅收敛为单位向量）、Shor 因子表
     （15/21/33/35/77/91/4/6/9）、乘法阶 ord 表、Toffoli→Clifford+T 15 门
     分解的矩阵乘积逐位验证；
  2. 闭环：种子化 Bell 测量关联 + 坍缩归一化、Grover d=8 统计命中率
     （理论 sin²(5θ)≈0.945）、QFT δ↔均匀往返、Matha 端到端（干净子进程
     exec_api 懒加载 quantum 领域，柯里化链真算 + 真拒绝）、matha_compile
     真计数与 parse+compile_program 独立复算对拍；
  3. 显式拒绝：未知门/RX·RY·RZ·TOFFOLI/素数 Shor/越界索引/两比特门缺目标/
     单比特门非法占位/oracle 长度不符/LLVM 假产物——一律如实抛错。
符号面：quantum 9 符号、quantum_compute 15 符号，manifest / registry /
symtab / 注册字典四方一致；柯里化注册形态逐一对拍（零参 f() 传 0 约定）。
"""
from __future__ import annotations

import cmath
import json
import math
import random
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.domains.quantum import (  # noqa: E402
    MAX_QUBITS,
    QuantumComputer,
    _quantum_symtab_names,
    _register_quantum,
)
from src.domains.quantum_compute import (  # noqa: E402
    _quantum_compute_symtab_names,
    _register_quantum_compute,
    circuit_depth,
    gate_decompose,
    grover_iterate,
    quantum_fourier_transform,
    shor_period_finding,
)
from src.unified_parser import (  # noqa: E402
    MathaLLVMGenerator,
    matha_compile,
    matha_run,
    matha_to_llvm,
)

MANIFEST = ROOT / "src" / "domains" / "manifest.json"

_INV_SQRT2 = 1.0 / math.sqrt(2.0)


def _amps(qc: QuantumComputer) -> list[complex]:
    return [complex(a) for a in qc.amplitudes()]


# ============================================================
# 1. 手算对拍（封死假值）
# ============================================================

class TestQuantumHandComputed:

    def test_bell_amplitudes_exact(self):
        qc = QuantumComputer(2)
        assert qc.entanglement(0, 1) is True
        a = _amps(qc)
        assert a[0] == pytest.approx(_INV_SQRT2)
        assert a[1] == pytest.approx(0.0)
        assert a[2] == pytest.approx(0.0)
        assert a[3] == pytest.approx(_INV_SQRT2)

    def test_x_gate_flips_basis_state(self):
        qc = QuantumComputer(1)
        assert qc.apply_gate("X", 0) is True
        a = _amps(qc)
        assert a[0] == pytest.approx(0.0) and a[1] == pytest.approx(1.0)

    def test_h_then_z_exact(self):
        qc = QuantumComputer(1)
        qc.apply_gate("H", 0)
        a = _amps(qc)
        assert a[0] == pytest.approx(_INV_SQRT2)
        assert a[1] == pytest.approx(_INV_SQRT2)
        qc.apply_gate("Z", 0)
        a = _amps(qc)
        assert a[0] == pytest.approx(_INV_SQRT2)
        assert a[1] == pytest.approx(-_INV_SQRT2)

    def test_s_and_t_phases_exact(self):
        qc = QuantumComputer(1)
        qc.apply_gate("X", 0)
        qc.apply_gate("S", 0)
        amp = _amps(qc)[1]
        assert abs(amp) == pytest.approx(1.0)
        assert cmath.phase(amp) == pytest.approx(math.pi / 2)
        qc.apply_gate("T", 0)
        amp = _amps(qc)[1]
        assert cmath.phase(amp) == pytest.approx(math.pi / 2 + math.pi / 4)

    def test_cnot_controlled_flip_exact(self):
        qc = QuantumComputer(2)
        qc.apply_gate("X", 1)          # |10>（q0 为低位）
        qc.apply_gate("CNOT", 1, 0)    # 控制 q1 → 翻转 q0：|11>
        a = _amps(qc)
        assert a[3] == pytest.approx(1.0) and a[2] == pytest.approx(0.0)
        qc2 = QuantumComputer(2)
        qc2.apply_gate("X", 1)
        qc2.apply_gate("CNOT", 0, 1)   # 控制 q0=0 → 不翻转
        assert _amps(qc2)[2] == pytest.approx(1.0)

    def test_swap_exact(self):
        qc = QuantumComputer(2)
        qc.apply_gate("X", 0)          # |01>
        qc.apply_gate("SWAP", 0, 1)    # → |10>
        a = _amps(qc)
        assert a[2] == pytest.approx(1.0) and a[1] == pytest.approx(0.0)

    def test_cz_sign_flip_exact(self):
        qc = QuantumComputer(2)
        qc.apply_gate("X", 0)
        qc.apply_gate("X", 1)          # |11>
        qc.apply_gate("CZ", 0, 1)
        assert _amps(qc)[3] == pytest.approx(-1.0)
        qc.apply_gate("CZ", 0, 1)      # 自逆
        assert _amps(qc)[3] == pytest.approx(1.0)

    def test_ghz3_amplitudes_exact(self):
        qc = QuantumComputer(1)
        algo = qc.run_algorithm("ghz", 3)
        a = _amps(qc)
        assert a[0] == pytest.approx(_INV_SQRT2)
        assert a[7] == pytest.approx(_INV_SQRT2)
        assert all(a[i] == pytest.approx(0.0) for i in range(1, 7))
        assert algo.result == qc.amplitudes()

    def test_qft_delta_to_uniform(self):
        out = quantum_fourier_transform([1, 0, 0, 0])
        assert all(abs(v - 0.5) < 1e-12 for v in out)

    @pytest.mark.parametrize("marked", [0, 1, 2, 3])
    def test_grover_d4_exact_all_marked(self, marked):
        random.seed(9)
        qc = QuantumComputer(0)
        assert qc.grover_search(4, marked) == marked
        a = _amps(qc)
        for i in range(4):
            assert a[i] == pytest.approx(1.0 if i == marked else 0.0)

    def test_grover_d2_half_probability(self):
        # N=2 退化案例：sin²((2k+1)π/4) ≡ 0.5，理论命中率恰为 50%
        # （旧假实现恒返回 0，marked=1 时命中率必为 0，此锁封死回退）
        random.seed(13)
        hits = 0
        trials = 400
        for _ in range(trials):
            qc = QuantumComputer(0)
            if qc.grover_search(2, 1) == 1:
                hits += 1
        assert 0.35 < hits / trials < 0.65

    def test_grover_padding_stays_zero(self):
        random.seed(9)
        qc = QuantumComputer(0)
        qc.grover_search(5, 3)   # d=5 → 3 比特寄存器，索引 5..7 为填充
        a = _amps(qc)
        assert all(a[i] == pytest.approx(0.0) for i in range(5, 8))
        assert sum(abs(x) ** 2 for x in a) == pytest.approx(1.0)

    def test_shor_factor_table(self):
        table = {15: (3, 5), 21: (3, 7), 33: (3, 11), 35: (5, 7),
                 77: (7, 11), 91: (7, 13), 4: (2, 2), 6: (2, 3), 9: (3, 3)}
        qc = QuantumComputer(2)
        for n, expected in table.items():
            got = qc.shor_factor(n)
            assert sorted(got) == sorted(expected), f"{n} -> {got}"
            assert got[0] * got[1] == n
            assert 1 < got[0] < n and 1 < got[1] < n

    def test_shor_period_finding_orders(self):
        assert shor_period_finding(2, 15) == 4
        assert shor_period_finding(1, 15) == 1   # 周期起点修复前恒 None
        assert shor_period_finding(8, 9) == 2
        assert shor_period_finding(5, 12) == 2
        assert shor_period_finding(3, 15) is None  # gcd != 1

    def test_circuit_depth_convention(self):
        assert circuit_depth(["H", "CNOT", "TOFFOLI"], 3) == 6
        assert circuit_depth(["SWAP", "T"], 2) == 3
        assert circuit_depth([], 2) == 0


class TestToffoliDecompositionHandComputed:
    """gate_decompose 从「固定 7 门假产物」真化为矩阵级验证的精确分解。"""

    def test_exact_sequence_lock(self):
        seq = gate_decompose(6)
        assert len(seq) == 15
        assert seq.count("CNOT") == 6
        assert seq[0] == "H" and seq[-1] == "H"
        assert seq == ["H", "Tdg", "Tdg", "Tdg", "CNOT", "T", "CNOT", "Tdg",
                       "CNOT", "T", "CNOT", "CNOT", "T", "CNOT", "H"]

    def test_matrix_product_equals_toffoli(self):
        # 位序约定：q0 = 最高位（c1）、q1 = c2、q2 = 最低位（t），
        # Toffoli 交换 |110> ↔ |111>，即矩阵下标 6 ↔ 7。
        s2 = 1.0 / math.sqrt(2.0)
        H = [[s2, s2], [s2, -s2]]
        T = [[1, 0], [0, complex(s2, s2)]]
        Tdg = [[1, 0], [0, complex(s2, -s2)]]
        I2 = [[1, 0], [0, 1]]
        G = {"H": H, "T": T, "Tdg": Tdg}
        POS = {"c1": 0, "c2": 1, "t": 2}

        def kron(a, b):
            ra, ca, rb, cb = len(a), len(a[0]), len(b), len(b[0])
            return [[a[r // rb][c // cb] * b[r % rb][c % cb]
                     for c in range(ca * cb)] for r in range(ra * rb)]

        def mm(a, b):
            return [[sum(a[r][k] * b[k][c] for k in range(len(b)))
                     for c in range(len(b[0]))] for r in range(len(a))]

        def gate1(m, q):
            ops = [[1]]
            for k in range(3):
                ops = kron(ops, m if k == q else I2)
            return ops

        def cnot3(c, t):
            out = [[1 if r == c2 else 0 for c2 in range(8)] for r in range(8)]
            for col in range(8):
                if (col >> (2 - c)) & 1:
                    row = col ^ (1 << (2 - t))
                    out[row][col] = 1
                    out[row][row] = 0
                    out[col][col] = 0
            return out

        roles = ["t", "c1", "c2", "t", "c2:t", "t", "c1:t", "t", "c2:t",
                 "t", "c1:t", "c1:c2", "c2", "c1:c2", "t"]
        mat = [[1 if i == j else 0 for j in range(8)] for i in range(8)]
        for name, role in zip(gate_decompose(6), roles):
            if ":" in role:
                c, t = role.split(":")
                g = cnot3(POS[c], POS[t])
            else:
                g = gate1(G[name], POS[role])
            mat = mm(g, mat)  # 电路序：新门在左

        toffoli = [[1 if i == j else 0 for j in range(8)] for i in range(8)]
        toffoli[6][7] = 1
        toffoli[7][6] = 1
        toffoli[6][6] = 0
        toffoli[7][7] = 0
        for r in range(8):
            for c in range(8):
                assert abs(mat[r][c] - toffoli[r][c]) < 1e-9


# ============================================================
# 2. 闭环（种子化统计 + 端到端 + 独立复算）
# ============================================================

class TestQuantumClosedLoop:

    def test_bell_correlation_collapse_and_renormalization(self):
        random.seed(42)
        for _ in range(20):
            qc = QuantumComputer(2)
            qc.entanglement(0, 1)
            m0 = qc.measure(0)
            m1 = qc.measure(1)
            assert m0 == m1                       # Bell 关联
            amps = _amps(qc)
            assert sum(abs(a) ** 2 for a in amps) == pytest.approx(1.0)
            assert qc.measure(0) == m0            # 坍缩后复测不变

    def test_grover_d8_statistical_hit_rate(self):
        # θ = arcsin(1/√8)，k = floor(π/(4θ)) = 2，p = sin²(5θ) ≈ 0.945
        random.seed(7)
        hits = 0
        trials = 300
        for _ in range(trials):
            qc = QuantumComputer(0)
            if qc.grover_search(8, 5) == 5:
                hits += 1
        assert hits / trials > 0.85
        assert hits / trials <= 1.0

    def test_qft_uniform_to_delta_roundtrip(self):
        out = quantum_fourier_transform([0.5, 0.5, 0.5, 0.5])
        assert abs(out[0] - 1.0) < 1e-12
        assert all(abs(v) < 1e-12 for v in out[1:])

    def test_grow_and_amplitude_continuity(self):
        qc = QuantumComputer(1)
        qc.apply_gate("X", 0)
        qc.create_qubit(1)   # 追加最高位 |0>，原振幅不动
        a = _amps(qc)
        assert a[1] == pytest.approx(1.0)   # |q1=0, q0=1> → 下标 1
        assert a[3] == pytest.approx(0.0)

    def test_matha_compile_counts_independently_recomputed(self):
        from src.mbc.compiler import compile_program
        from src.parser import parse

        src = "func 加倍(x) -> Int = (x) => x * 2"
        got = matha_compile(src, "test")
        prog = parse(src)
        mod = compile_program(prog)
        expected = (f"# Compiled {len(prog.decls)} declarations to test: "
                    f"{len(mod.functions)} functions, {len(mod.main_code)} ops")
        assert got == expected
        assert got == "# Compiled 1 declarations to test: 1 functions, 1 ops"

    def test_matha_run_still_real(self):
        outputs, trace = matha_run("[1 + 2]")
        assert outputs == [3]
        assert isinstance(trace, list)


# ============================================================
# 3. 显式拒绝（不再假装成功）
# ============================================================

class TestQuantumExplicitRejection:

    @pytest.mark.parametrize("gate", ["RX", "RY", "RZ", "TOFFOLI"])
    def test_placeholder_gates_rejected(self, gate):
        qc = QuantumComputer(1)
        with pytest.raises(ValueError, match="显式拒绝"):
            qc.apply_gate(gate, 0)

    def test_unknown_gate_rejected(self):
        qc = QuantumComputer(1)
        with pytest.raises(ValueError, match="未知量子门"):
            qc.apply_gate("BOGUS", 0)

    def test_cnot_requires_target(self):
        qc = QuantumComputer(2)
        with pytest.raises(ValueError, match="必须提供 target_index"):
            qc.apply_gate("CNOT", 0)

    @pytest.mark.parametrize("gate", ["CNOT", "CZ", "SWAP"])
    def test_same_index_two_qubit_rejected(self, gate):
        qc = QuantumComputer(2)
        with pytest.raises(ValueError, match="必须不同"):
            qc.apply_gate(gate, 1, 1)

    def test_apply_gate_index_out_of_bounds(self):
        qc = QuantumComputer(1)
        with pytest.raises(ValueError, match="超界"):
            qc.apply_gate("X", 5)

    def test_measure_index_out_of_bounds(self):
        qc = QuantumComputer(1)
        with pytest.raises(ValueError, match="超界"):
            qc.measure(3)

    def test_one_qubit_gate_placeholder_target_still_validated(self):
        qc = QuantumComputer(1)
        qc.apply_gate("X", 0, 0)      # 合法占位（同一比特）→ 放行
        with pytest.raises(ValueError, match="超界"):
            qc.apply_gate("X", 0, 9)  # 越界占位 → 拒绝

    def test_create_qubit_nonsequential_rejected(self):
        qc = QuantumComputer(1)
        with pytest.raises(ValueError, match="连续索引"):
            qc.create_qubit(0)

    def test_max_qubits_enforced(self):
        with pytest.raises(ValueError, match="量子比特数须在"):
            QuantumComputer(MAX_QUBITS + 1)
        qc = QuantumComputer(MAX_QUBITS)
        with pytest.raises(ValueError, match="上限"):
            qc.create_qubit(MAX_QUBITS)

    def test_grover_bounds_rejected(self):
        qc = QuantumComputer(2)
        with pytest.raises(ValueError, match="至少为 2"):
            qc.grover_search(1, 0)
        with pytest.raises(ValueError, match="标记项须在"):
            qc.grover_search(4, 4)
        with pytest.raises(ValueError, match="标记项须在"):
            qc.grover_search(4, -1)

    def test_shor_small_and_prime_rejected(self):
        qc = QuantumComputer(2)
        with pytest.raises(ValueError, match="至少为 4"):
            qc.shor_factor(3)
        with pytest.raises(ValueError, match="可能为素数"):
            qc.shor_factor(17)
        with pytest.raises(ValueError, match="可能为素数"):
            qc.shor_factor(23)

    def test_ghz_size_bounds_rejected(self):
        qc = QuantumComputer(1)
        with pytest.raises(ValueError, match="GHZ"):
            qc.run_algorithm("ghz", 1)

    def test_unknown_algorithm_rejected(self):
        qc = QuantumComputer(2)
        with pytest.raises(ValueError, match="未知算法"):
            qc.run_algorithm("占卜", 2)

    def test_algorithm_redirect_rejected(self):
        qc = QuantumComputer(2)
        with pytest.raises(ValueError, match="独立入口"):
            qc.run_algorithm("grover", 2)
        with pytest.raises(ValueError, match="独立入口"):
            qc.run_algorithm("shor", 2)

    def test_entanglement_same_index_rejected(self):
        qc = QuantumComputer(2)
        with pytest.raises(ValueError, match="必须不同"):
            qc.entanglement(1, 1)

    def test_qft_arity_mismatch_rejected(self):
        qc = QuantumComputer(2)
        with pytest.raises(ValueError, match="一致"):
            qc.run_algorithm("qft", 3)

    def test_bool_as_index_rejected(self):
        qc = QuantumComputer(2)
        with pytest.raises(TypeError, match="布尔"):
            qc.measure(True)


class TestQuantumComputeExplicitRejection:

    def test_grover_iterate_oracle_length_mismatch(self):
        state = [0.5, 0.5, 0.5, 0.5]
        with pytest.raises(ValueError, match="不一致"):
            grover_iterate(state, lambda s: s[:2], 1)

    def test_grover_iterate_zero_vector_rejected(self):
        with pytest.raises(ValueError, match="零向量"):
            grover_iterate([0.0, 0.0], lambda s: [0.0, 0.0], 1)

    def test_grover_iterate_negative_iterations(self):
        with pytest.raises(ValueError, match="非负"):
            grover_iterate([1.0, 0.0], lambda s: s, -1)

    def test_grover_iterate_empty_state(self):
        with pytest.raises(ValueError, match="不能为空"):
            grover_iterate([], lambda s: s, 1)

    @pytest.mark.parametrize("count", [0, 4, 7, -6])
    def test_gate_decompose_rejects_other_cnot_counts(self, count):
        with pytest.raises(ValueError, match="6 个 CNOT"):
            gate_decompose(count)


class TestUnifiedParserExplicitRejection:

    def test_matha_to_llvm_rejected(self):
        with pytest.raises(NotImplementedError, match="显式拒绝"):
            matha_to_llvm("func 测试(x) -> Int = (x) => x + 1")

    def test_llvm_generator_rejected(self):
        gen = MathaLLVMGenerator()
        with pytest.raises(NotImplementedError, match="显式拒绝"):
            gen.generate(None)


# ============================================================
# 4. 符号面（四方一致）+ 柯里化注册形态
# ============================================================

class TestSymbolFace:

    QUANTUM_NAMES = [
        "创建量子计算机", "创建量子比特", "应用量子门",
        "创建量子电路", "运行算法", "测量",
        "量子纠缠", "Grover搜索", "Shor分解",
    ]

    def test_quantum_symtab_is_nine_names(self):
        names = _quantum_symtab_names()
        assert names == self.QUANTUM_NAMES
        b: dict = {}
        _register_quantum(b)
        assert set(names) == set(b)

    def test_quantum_compute_symtab_is_fifteen_names(self):
        names = _quantum_compute_symtab_names()
        assert len(names) == 15
        expected = {"hadamard", "pauli_x", "pauli_y", "pauli_z", "cnot",
                    "swap", "toffoli", "bell_state", "ghz_state",
                    "qubit_state", "grover_iterate", "shor_period",
                    "量子傅里叶变换", "电路深度", "门分解"}
        assert set(names) == expected
        b: dict = {}
        _register_quantum_compute(b)
        assert set(names) == set(b)

    def test_manifest_symbols_match_symtab(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        for plugin_name, symtab in (("quantum", _quantum_symtab_names),
                                    ("quantum_compute",
                                     _quantum_compute_symtab_names)):
            entry = next(p for p in manifest["plugins"]
                         if p["name"] == plugin_name)
            assert set(entry["symbols"]) == set(symtab()), plugin_name

    def test_registry_templates_match_symtab(self):
        from src.domains.registry import DomainRegistry
        templates = DomainRegistry._DOMAIN_TEMPLATES
        quantum = templates["Quantum"]["functions"]
        quantum_compute = templates["QuantumComputing"]["functions"]
        assert set(quantum) == set(_quantum_symtab_names())
        assert set(quantum_compute) == set(_quantum_compute_symtab_names())
        # 幻影符号清算锁：quantum_fourier / grover_iter / quantum_teleport
        # 此前登记在 registry 但模块中根本不存在
        for phantom in ("quantum_fourier", "grover_iter", "quantum_teleport"):
            assert phantom not in quantum_compute

    def test_curried_chain_arity(self):
        b: dict = {}
        _register_quantum(b)
        qc = b["创建量子计算机"](2)
        assert isinstance(qc, QuantumComputer)
        # 零参 f() 传常量 0 约定：创建量子计算机() → 0 比特机器
        assert b["创建量子计算机"](0).num_qubits == 0
        assert callable(b["创建量子比特"](qc))
        assert callable(b["应用量子门"](qc))
        assert callable(b["应用量子门"](qc)("X"))
        assert callable(b["应用量子门"](qc)("X")(0))
        assert b["应用量子门"](qc)("X")(0)(1) is True
        assert callable(b["量子纠缠"](qc)(0))
        assert b["量子纠缠"](qc)(0)(1) is True
        assert callable(b["运行算法"](qc))
        assert callable(b["运行算法"](qc)("ghz"))
        ghz = b["运行算法"](qc)("ghz")(3)
        assert ghz.result == qc.amplitudes()
        assert callable(b["Grover搜索"](qc)(4))
        random.seed(9)
        assert b["Grover搜索"](qc)(4)(2) == 2
        assert b["Shor分解"](qc)(15) == [3, 5]
        assert callable(b["创建量子电路"](qc))


# ============================================================
# 5. matha_system 量子门面（假 dict / 恒 0 / 恒 [1,n] → 真委托 + 显式拒绝）
# ============================================================

class TestMathaSystemQuantumFacade:

    def _system(self):
        from src.matha_system import MathaSystem
        s = MathaSystem()
        s._init_quantum()
        return s

    def test_uninitialized_system_rejected_not_fake(self):
        from src.matha_system import MathaSystem
        s = MathaSystem()   # 未走 _init_quantum：门面如实拒绝，不再假值兜底
        with pytest.raises(RuntimeError):
            s.create_quantum_computer(2)
        with pytest.raises(RuntimeError, match="未初始化"):
            s.quantum_measure(0)
        with pytest.raises(RuntimeError, match="初始化失败"):
            s.shor_factor(15)

    def test_create_and_track_machines(self):
        s = self._system()
        m1 = s.create_quantum_computer(2)
        m2 = s.create_quantum_computer(1)
        assert s._quantum_machines == [m1, m2]
        assert s._require_quantum_machine() is m2

    def test_gate_and_measure_real(self):
        random.seed(3)
        s = self._system()
        s.create_quantum_computer(2)
        assert s.apply_quantum_gate("X", 0) is True
        assert s.quantum_measure(0) == 1   # X|0> 确定为 1（旧假实现恒 0）
        assert s.quantum_measure(1) == 0

    def test_bell_correlation_via_facade(self):
        random.seed(11)
        s = self._system()
        s.create_quantum_computer(2)
        s.apply_quantum_gate("H", 0)
        s.apply_quantum_gate("CNOT", 0, 1)
        assert s.quantum_measure(0) == s.quantum_measure(1)

    def test_circuit_and_algorithm_real(self):
        s = self._system()
        s.create_quantum_computer(1)
        circuit = s.create_quantum_circuit(2)
        assert circuit.num_qubits == 2
        algo = s.run_quantum_algorithm("ghz", 3)
        assert algo.name == "ghz"
        amps = algo.result
        assert abs(amps[0]) == pytest.approx(_INV_SQRT2)
        assert abs(amps[7]) == pytest.approx(_INV_SQRT2)

    def test_grover_shor_real(self):
        random.seed(9)
        s = self._system()
        s.create_quantum_computer(2)
        assert s.grover_search(4, 2) == 2
        assert s.shor_factor(15) == [3, 5]
        assert sorted(s.shor_factor(91)) == [7, 13]

    def test_no_machine_rejected(self):
        s = self._system()
        for fn in (lambda: s.apply_quantum_gate("X", 0),
                   lambda: s.quantum_measure(0),
                   lambda: s.create_quantum_circuit(2),
                   lambda: s.run_quantum_algorithm("bell", 2),
                   lambda: s.grover_search(4, 0)):
            with pytest.raises(RuntimeError, match="尚无量子计算机"):
                fn()

    def test_grover_without_marked_rejected(self):
        s = self._system()
        s.create_quantum_computer(2)
        with pytest.raises(ValueError, match="marked"):
            s.grover_search(4)

    def test_prime_shor_rejected_via_facade(self):
        s = self._system()
        with pytest.raises(ValueError, match="可能为素数"):
            s.shor_factor(17)


# ============================================================
# 6. 主执行链端到端（干净子进程，懒加载真算/真拒绝）
# ============================================================

_E2E_SNIPPET = """
import json, sys
sys.path.insert(0, %r)
from src.kernel import exec_api
from src.plugin_api import get_resolver
src = '''@：【加载领域】，quantum
机 = 创建量子计算机(2)
量子纠缠(机, 0, 1)
甲 = 测量(机, 0)
乙 = 测量(机, 1)
输出(甲)
输出(乙)
机2 = 创建量子计算机(2)
输出(Grover搜索(机2, 4, 2))
输出(Shor分解(机2, 15))
'''
out = exec_api.run(src)
assert len(out) == 4, out
assert out[0] == out[1], ("Bell 关联破裂", out)      # 纠缠对测量强关联
assert out[2] == 2, ("Grover d=4 未精确命中", out)   # sin²(3θ)=1
assert out[3] == [3, 5], ("Shor 15 分解错误", out)
assert "quantum" in get_resolver().loaded()
print(json.dumps({"bell": out[0], "grover": out[2], "shor": out[3]}))
""" % str(ROOT)


def test_main_chain_lazy_loads_and_computes_for_real():
    proc = subprocess.run([sys.executable, "-c", _E2E_SNIPPET],
                          cwd=str(ROOT), capture_output=True, text=True,
                          timeout=180)
    assert proc.returncode == 0, proc.stderr[-800:]
    payload = json.loads(proc.stdout.strip().splitlines()[-1])
    assert payload["grover"] == 2
    assert payload["shor"] == [3, 5]


_E2E_REJECT_SNIPPET = """
import sys
sys.path.insert(0, %r)
from src.kernel import exec_api
src = '''@：【加载领域】，quantum
机 = 创建量子计算机(1)
应用量子门(机, "TOFFOLI", 0, 1)
'''
try:
    exec_api.run(src)
except ValueError as e:
    assert "显式拒绝" in str(e)
    print("REJECTED-GATE")
else:
    raise AssertionError("TOFFOLI 假占位复活：未抛 ValueError")
src2 = '''@：【加载领域】，quantum
机 = 创建量子计算机(2)
输出(Shor分解(机, 17))
'''
try:
    exec_api.run(src2)
except ValueError as e:
    assert "可能为素数" in str(e)
    print("REJECTED-PRIME")
else:
    raise AssertionError("素数 Shor 假 [3,5] 复活：未抛 ValueError")
""" % str(ROOT)


def test_main_chain_surfaces_honest_rejection():
    proc = subprocess.run([sys.executable, "-c", _E2E_REJECT_SNIPPET],
                          cwd=str(ROOT), capture_output=True, text=True,
                          timeout=180)
    assert proc.returncode == 0, proc.stderr[-800:]
    assert "REJECTED-GATE" in proc.stdout
    assert "REJECTED-PRIME" in proc.stdout
