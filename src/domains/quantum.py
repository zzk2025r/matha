"""Matha 量子计算模块：量子比特、量子门、量子电路、算法。

真实现（纯 Python 状态向量模拟）：
  1) 量子比特：n 比特态向量（2^n 振幅），上限 20 比特
  2) 量子门：H/X/Y/Z/S/T（单比特）+ CNOT/CZ/SWAP（两比特），矩阵真实作用于态向量
  3) 量子电路：门序列记录容器
  4) 量子算法：Bell/GHZ 态制备、QFT（委托 quantum_compute）、Grover/Shor 独立入口
  5) 量子纠缠：H + CNOT 真实制备纠缠对
  6) 量子测量：按 |振幅|² 概率采样并坍缩归一化

边界（如实登记）：本模块是经典模拟器，不背书量子加速；
量子比特数上限 20（2^20 振幅约 16MB）；Grover/Shor 为教科书式实现。
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

MAX_QUBITS = 20

_INV_SQRT2 = 1.0 / math.sqrt(2.0)

# 单比特门矩阵（真实酉矩阵）
_GATES_1Q: dict[str, list[list[complex]]] = {
    "H": [[_INV_SQRT2, _INV_SQRT2], [_INV_SQRT2, -_INV_SQRT2]],
    "X": [[0, 1], [1, 0]],
    "Y": [[0, -1j], [1j, 0]],
    "Z": [[1, 0], [0, -1]],
    "S": [[1, 0], [0, 1j]],
    "T": [[1, 0], [0, complex(math.cos(math.pi / 4), math.sin(math.pi / 4))]],
}
_GATES_2Q = ("CNOT", "CZ", "SWAP")

# 显式拒绝清单（此前为假实现占位，现如实拒绝而非假装成功）
_REJECTED_GATES = ("RX", "RY", "RZ", "TOFFOLI")


class QuantumGate(Enum):
    """量子门。"""
    H = "Hadamard"
    X = "Pauli-X"
    Y = "Pauli-Y"
    Z = "Pauli-Z"
    S = "S"
    T = "T"
    CNOT = "CNOT"
    CZ = "CZ"
    SWAP = "SWAP"


@dataclass
class Qubit:
    """量子比特（真态在整机态向量中，不在此存 state）。"""
    index: int = 0
    entangled: bool = False


@dataclass
class QuantumCircuit:
    """量子电路（门序列记录容器）。"""
    num_qubits: int = 2
    gates: list[Any] = field(default_factory=list)
    measurements: list[int] = field(default_factory=list)


@dataclass
class QuantumAlgorithm:
    """量子算法。"""
    name: str = ""
    qubits: int = 2
    depth: int = 0
    result: Any | None = None


def _as_int(value: Any, name: str) -> int:
    """整数归一化：接受 int 与整值 float，拒绝 bool。"""
    if isinstance(value, bool):
        raise TypeError(f"{name} 必须是整数，收到布尔值")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    raise TypeError(f"{name} 必须是整数，收到 {type(value).__name__}")


class QuantumComputer:
    """量子计算机：n 比特状态向量模拟器。

    位序约定：量子比特 q 对应振幅下标 i 的第 q 位（(i >> q) & 1）。
    新建量子比特追加为最高位，初态 |0>。
    """

    def __init__(self, num_qubits: int = 2):
        n = _as_int(num_qubits, "量子比特数")
        if n < 0 or n > MAX_QUBITS:
            raise ValueError(f"量子比特数须在 0..{MAX_QUBITS}，收到 {n}")
        self.num_qubits = n
        self._amps: list[complex] = [0.0 + 0.0j] * (2 ** n)
        self._amps[0] = 1.0 + 0.0j
        self._qubits: list[Qubit] = [Qubit(index=i) for i in range(n)]
        self._circuits: list[QuantumCircuit] = []
        self._algorithms: list[QuantumAlgorithm] = []

    def amplitudes(self) -> list[complex]:
        """返回当前态向量副本。"""
        return list(self._amps)

    def create_qubit(self, index: int = 0) -> Qubit:
        """创建量子比特：追加为最高位，整机态扩展并保持归一化。"""
        i = _as_int(index, "量子比特索引")
        if i != self.num_qubits:
            raise ValueError(
                f"新量子比特必须使用连续索引 {self.num_qubits}，收到 {i}")
        if self.num_qubits >= MAX_QUBITS:
            raise ValueError(f"已达量子比特上限 {MAX_QUBITS}")
        grown = [0.0 + 0.0j] * (2 ** (self.num_qubits + 1))
        for idx, amp in enumerate(self._amps):
            grown[idx] = amp  # 新位为 0：原索引处振幅不变
        self._amps = grown
        qubit = Qubit(index=i)
        self._qubits.append(qubit)
        self.num_qubits += 1
        return qubit

    def _require_qubit(self, q: Any, name: str) -> int:
        i = _as_int(q, name)
        if i < 0 or i >= self.num_qubits:
            raise ValueError(
                f"{name} 超界：有效范围 0..{self.num_qubits - 1}，收到 {i}")
        return i

    def apply_gate(self, gate: str, qubit_index: int,
                   target_index: int | None = None) -> bool:
        """应用量子门：真实矩阵作用到态向量。

        单比特门忽略 target_index（Matha 四参调用链需占位），
        但占位一旦提供必须落在有效比特范围内。
        """
        g = str(gate).upper()
        if g in _REJECTED_GATES:
            raise ValueError(
                f"量子门 {gate} 未实现（此前为假占位，现显式拒绝）；"
                f"支持：{', '.join(sorted(_GATES_1Q) + list(_GATES_2Q))}")
        q = self._require_qubit(qubit_index, "量子比特索引")
        if g in _GATES_1Q:
            if target_index is not None:
                self._require_qubit(target_index, "目标量子比特索引")
            self._apply_1q(_GATES_1Q[g], q)
            return True
        if g in _GATES_2Q:
            if target_index is None:
                raise ValueError(f"{g} 是两比特门，必须提供 target_index")
            t = self._require_qubit(target_index, "目标量子比特索引")
            if t == q:
                raise ValueError("两个量子比特索引必须不同")
            self._apply_2q(g, q, t)
            return True
        raise ValueError(
            f"未知量子门 {gate}；"
            f"支持：{', '.join(sorted(_GATES_1Q) + list(_GATES_2Q))}")

    def _apply_1q(self, m: list[list[complex]], q: int) -> None:
        for i in range(2 ** self.num_qubits):
            if (i >> q) & 1:
                continue
            j = i | (1 << q)
            a, b = self._amps[i], self._amps[j]
            self._amps[i] = m[0][0] * a + m[0][1] * b
            self._amps[j] = m[1][0] * a + m[1][1] * b

    def _apply_2q(self, g: str, c: int, t: int) -> None:
        for i in range(2 ** self.num_qubits):
            cb = (i >> c) & 1
            tb = (i >> t) & 1
            if g == "CNOT":
                if cb == 1:
                    j = i ^ (1 << t)
                    if i < j:
                        self._amps[i], self._amps[j] = self._amps[j], self._amps[i]
            elif g == "CZ":
                if cb == 1 and tb == 1:
                    self._amps[i] = -self._amps[i]
            elif g == "SWAP":
                if cb == 1 and tb == 0:
                    j = (i & ~(1 << c)) | (1 << t)
                    if i < j:
                        self._amps[i], self._amps[j] = self._amps[j], self._amps[i]

    def measure(self, qubit_index: int) -> int:
        """测量量子比特：按 |振幅|² 采样并坍缩归一化。"""
        q = self._require_qubit(qubit_index, "量子比特索引")
        p1 = 0.0
        for i, amp in enumerate(self._amps):
            if (i >> q) & 1:
                p1 += abs(amp) ** 2
        outcome = 1 if random.random() < p1 else 0
        norm = 0.0
        for i, amp in enumerate(self._amps):
            if ((i >> q) & 1) == outcome:
                norm += abs(amp) ** 2
        if norm <= 0.0:
            norm = 1.0
        for i in range(2 ** self.num_qubits):
            if ((i >> q) & 1) == outcome:
                self._amps[i] /= math.sqrt(norm)
            else:
                self._amps[i] = 0.0 + 0.0j
        self._qubits[q].entangled = False
        return outcome

    def entanglement(self, q1: int, q2: int) -> bool:
        """量子纠缠：H(q1) + CNOT(q1→q2) 真实制备 Bell 对。"""
        a = self._require_qubit(q1, "量子比特索引")
        b = self._require_qubit(q2, "目标量子比特索引")
        if a == b:
            raise ValueError("纠缠的两个量子比特必须不同")
        self._apply_1q(_GATES_1Q["H"], a)
        self._apply_2q("CNOT", a, b)
        self._qubits[a].entangled = True
        self._qubits[b].entangled = True
        return True

    def create_circuit(self, num_qubits: int = 2) -> QuantumCircuit:
        """创建量子电路（记录容器）。"""
        n = _as_int(num_qubits, "电路量子比特数")
        circuit = QuantumCircuit(num_qubits=n)
        self._circuits.append(circuit)
        return circuit

    def _grow_to(self, n: int) -> None:
        while self.num_qubits < n:
            self.create_qubit(self.num_qubits)

    def run_algorithm(self, name: str, qubits: int = 2) -> QuantumAlgorithm:
        """运行量子算法：Bell/GHZ 真实制备；QFT 委托 quantum_compute。"""
        algo = QuantumAlgorithm(name=str(name), qubits=qubits)
        n = str(name).lower()
        if n in ("bell", "bell_state", "bell态"):
            self._grow_to(2)
            self.entanglement(0, 1)
            algo.depth = 2
            algo.result = self.amplitudes()
        elif n in ("ghz", "ghz_state", "ghz态"):
            k = _as_int(qubits, "量子比特数")
            if k < 2 or k > MAX_QUBITS:
                raise ValueError(f"GHZ 量子比特数须在 2..{MAX_QUBITS}，收到 {k}")
            self._grow_to(k)
            self._apply_1q(_GATES_1Q["H"], 0)
            for q in range(1, k):
                self._apply_2q("CNOT", 0, q)
            for q in range(k):
                self._qubits[q].entangled = True
            algo.depth = k
            algo.result = self.amplitudes()
        elif n in ("qft", "quantum_fourier", "量子傅里叶变换"):
            from src.domains.quantum_compute import quantum_fourier_transform
            if _as_int(qubits, "量子比特数") != self.num_qubits:
                raise ValueError(
                    f"QFT 需要算法比特数与当前机器比特数一致（{self.num_qubits}），"
                    f"收到 {qubits}")
            algo.result = quantum_fourier_transform(self.amplitudes())
            algo.depth = self.num_qubits
        elif n in ("grover", "grover_search", "shor", "shor_factor"):
            raise ValueError(
                f"{name} 请使用独立入口（Grover搜索(数据库大小, 标记项) / "
                f"Shor分解(整数)），不通过 运行算法")
        else:
            raise ValueError(
                f"未知算法 {name}；支持：bell、ghz、qft（grover/shor 有独立入口）")
        self._algorithms.append(algo)
        return algo

    def grover_search(self, database_size: int, marked: int) -> int:
        """Grover 搜索：真实现，返回测量到的标记项索引。

        均匀叠加 → 相位 oracle（翻转标记项符号）→ 扩散算符
        D = 2|s><s| − I，迭代 floor(π/(4θ)) 次，θ = arcsin(1/√d)。
        d=4 时一次迭代精确命中（概率 1.0）。
        """
        d = _as_int(database_size, "数据库大小")
        m = _as_int(marked, "标记项")
        if d < 2:
            raise ValueError(f"数据库大小至少为 2，收到 {d}")
        if m < 0 or m >= d:
            raise ValueError(f"标记项须在 0..{d - 1}，收到 {m}")
        n = max(1, math.ceil(math.log2(d)))
        self._grow_to(n)
        size = 2 ** n
        norm_d = math.sqrt(d)
        self._amps = [complex(1.0 / norm_d, 0.0) if i < d else 0.0 + 0.0j
                      for i in range(size)]
        theta = math.asin(1.0 / norm_d)
        iterations = int(math.floor(math.pi / (4.0 * theta)))
        for _ in range(max(iterations, 1)):
            self._amps[m] = -self._amps[m]  # 相位 oracle
            proj = sum(self._amps[:d])  # D = 2|s><s| − I（d 维子空间）
            for i in range(d):
                self._amps[i] = 2.0 * proj / d - self._amps[i]
        return self._measure_register()

    def _measure_register(self) -> int:
        weights = [abs(a) ** 2 for a in self._amps]
        total = sum(weights)
        if total <= 0.0:
            return 0
        r = random.random() * total
        acc = 0.0
        for i, w in enumerate(weights):
            acc += w
            if r <= acc:
                return i
        return len(weights) - 1

    def shor_factor(self, n: int = 15) -> list[int]:
        """Shor 分解（经典部分真实现）：返回非平凡因子 [p, q]（p*q == n）。

        偶数直接 [2, n/2]；奇数用乘法阶 r = ord_a(n)，
        gcd(a^(r/2)±1, n) 提取因子；找不到非平凡因子则显式失败。
        """
        v = _as_int(n, "待分解整数")
        if v < 4:
            raise ValueError(f"待分解整数至少为 4，收到 {v}")
        if v % 2 == 0:
            return [2, v // 2]
        for a in range(2, v):
            g = math.gcd(a, v)
            if 1 < g < v:
                return [g, v // g]
            if g == 1:
                r = 1
                cur = a % v
                while cur != 1 and r <= v:
                    cur = (cur * a) % v
                    r += 1
                if cur != 1 or r % 2 != 0:
                    continue
                for p in (math.gcd(pow(a, r // 2, v) - 1, v),
                          math.gcd(pow(a, r // 2, v) + 1, v)):
                    if 1 < p < v:
                        return [p, v // p]
        raise ValueError(f"无法分解（可能为素数）：{v}")


def create_quantum_computer(num_qubits: int = 2) -> QuantumComputer:
    """创建量子计算机。"""
    return QuantumComputer(num_qubits)


def _register_quantum(builtins: dict) -> None:
    """注册量子计算内置函数（柯里化 lambda 链，匹配 Matha f(a,b) → f(a)(b)）。"""
    builtins["创建量子计算机"] = lambda n=2: create_quantum_computer(n)
    builtins["创建量子比特"] = lambda qc: lambda i: qc.create_qubit(i)
    builtins["应用量子门"] = lambda qc: lambda g: lambda q: lambda t: qc.apply_gate(g, q, t)
    builtins["创建量子电路"] = lambda qc: lambda n=2: qc.create_circuit(n)
    builtins["运行算法"] = lambda qc: lambda name: lambda qubits: qc.run_algorithm(name, qubits)
    builtins["测量"] = lambda qc: lambda q: qc.measure(q)
    builtins["量子纠缠"] = lambda qc: lambda q1: lambda q2: qc.entanglement(q1, q2)
    builtins["Grover搜索"] = lambda qc: lambda d: lambda m: qc.grover_search(d, m)
    builtins["Shor分解"] = lambda qc: lambda n: qc.shor_factor(n)


def _quantum_symtab_names() -> list[str]:
    return [
        "创建量子计算机", "创建量子比特", "应用量子门",
        "创建量子电路", "运行算法", "测量",
        "量子纠缠", "Grover搜索", "Shor分解",
    ]


__all__ = [
    "QuantumGate", "Qubit", "QuantumCircuit",
    "QuantumAlgorithm", "QuantumComputer",
    "create_quantum_computer", "_register_quantum",
    "_quantum_symtab_names",
]
