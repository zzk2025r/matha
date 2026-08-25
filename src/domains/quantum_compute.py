# -*- coding: utf-8 -*-
"""
Matha 量子计算领域模块。

覆盖：
  1) 量子门：H, X, Y, Z, CNOT, Toffoli, SWAP
  2) 量子电路：Bell态, GHZ态, QFT
  3) 量子算法：Grover, Shor简化版
  4) 量子态操作

注意：不依赖 numpy，使用纯 Python 实现以避免依赖问题。
"""
from __future__ import annotations
import cmath
import math
from typing import Optional, Callable


# ============================================================
# 基本量子门（纯 Python 矩阵）
# ============================================================

I  = [[1+0j, 0+0j], [0+0j, 1+0j]]
H  = [[1/math.sqrt(2), 1/math.sqrt(2)], [1/math.sqrt(2), -1/math.sqrt(2)]]
X  = [[0+0j, 1+0j], [1+0j, 0+0j]]
Y  = [[0+0j, -1j], [1j, 0+0j]]
Z  = [[1+0j, 0+0j], [0+0j, -1+0j]]
S  = [[1+0j, 0+0j], [0+0j, 1j]]
T  = [[1+0j, 0+0j], [0+0j, cmath.exp(1j * math.pi / 4)]]

CNOT = [[1+0j, 0, 0, 0],
        [0, 1+0j, 0, 0],
        [0, 0, 0+0j, 1+0j],
        [0, 0, 1+0j, 0+0j]]

SWAP = [[1+0j, 0, 0, 0],
        [0, 0+0j, 1+0j, 0],
        [0, 1+0j, 0+0j, 0],
        [0, 0, 0, 1+0j]]


# ============================================================
# 量子门
# ============================================================

def hadamard():
    """Hadamard 门。"""
    return H

def pauli_x():
    """Pauli-X 门（量子非门）。"""
    return X

def pauli_y():
    """Pauli-Y 门。"""
    return Y

def pauli_z():
    """Pauli-Z 门。"""
    return Z

def cnot():
    """CNOT 门。"""
    return CNOT

def swap_gate():
    """SWAP 门。"""
    return SWAP

def toffoli():
    """Toffoli（CCNOT）门（8x8矩阵）。"""
    mat = [[1+0j if i==j else 0+0j for j in range(8)] for i in range(8)]
    mat[6][7] = 1+0j
    mat[7][6] = 1+0j
    return mat


# ============================================================
# 量子态
# ============================================================

def bell_state():
    """Bell 态 |Phi+> = (|00> + |11>) / sqrt(2)。"""
    return [1/math.sqrt(2)+0j, 0+0j, 0+0j, 1/math.sqrt(2)+0j]

def ghz_state(n_qubits: int = 3):
    """GHZ 态 |0...0> + |1...1>。"""
    size = 2 ** n_qubits
    state = [0+0j] * size
    state[0] = 1/math.sqrt(2)
    state[-1] = 1/math.sqrt(2)
    return state

def qubit_state(theta: float, phi: float):
    """单量子比特状态 |psi> = cos(theta/2)|0> + e^(i*phi)*sin(theta/2)|1>。"""
    return [
        math.cos(theta / 2) + 0j,
        cmath.exp(1j * phi) * math.sin(theta / 2)
    ]


# ============================================================
# 量子算法
# ============================================================

def grover_iterate(state, oracle: Callable, n_iterations: int = 1):
    """Grover 迭代（简化版）。"""
    n = len(state)
    for _ in range(n_iterations):
        state = list(oracle(state))
        mean = sum(state) / n
        state = [2 * mean - s for s in state]
    return state

def shor_period_finding(a: int, N: int, max_period: int = 100):
    """Shor 算法周期寻找（简化版经典部分）。"""
    if math.gcd(a, N) != 1:
        return None
    for r in range(2, max_period):
        if pow(a, r, N) == 1:
            return r
    return None

def quantum_fourier_transform(state):
    """量子傅里叶变换。"""
    n = len(state)
    result = [0+0j] * n
    for k in range(n):
        for x in range(n):
            result[k] += state[x] * cmath.exp(2j * math.pi * k * x / n)
    result = [s / math.sqrt(n) for s in result]
    return result


# ============================================================
# 电路深度与门分解
# ============================================================

def circuit_depth(gates: list, n_qubits: int) -> int:
    """计算电路深度（简化）。"""
    depth = 0
    for g in gates:
        if g in ("H", "X", "Y", "Z", "S", "T"):
            depth += 1
        elif g in ("CNOT", "SWAP"):
            depth += 2
        elif g == "TOFFOLI":
            depth += 3
    return depth

def gate_decompose(cnot_count: int) -> list:
    """门分解（CNOT → 基础门）。"""
    return ["H", "CNOT", "T", "CNOT", "Tdg", "H", "CNOT"]


# ============================================================
# 模块导出
# ============================================================

__all__ = [
    # 量子门
    "hadamard", "pauli_x", "pauli_y", "pauli_z", "cnot", "swap_gate", "toffoli",
    # 量子态
    "bell_state", "ghz_state", "qubit_state",
    # 量子算法
    "grover_iterate", "shor_period_finding", "quantum_fourier_transform",
    # 电路
    "circuit_depth", "gate_decompose",
]


# ============================================================
# 注册到解释器
# ============================================================

def _register_quantum_compute(builtins: dict) -> None:
    """注册量子计算内建到解释器。"""
    builtins["hadamard"] = hadamard
    builtins["pauli_x"] = pauli_x
    builtins["pauli_y"] = pauli_y
    builtins["pauli_z"] = pauli_z
    builtins["cnot"] = cnot
    builtins["swap"] = swap_gate
    builtins["toffoli"] = toffoli
    builtins["bell_state"] = bell_state
    builtins["ghz_state"] = ghz_state
    builtins["qubit_state"] = qubit_state
    builtins["grover_iterate"] = grover_iterate
    builtins["shor_period"] = shor_period_finding
    builtins["量子傅里叶变换"] = quantum_fourier_transform
    builtins["电路深度"] = circuit_depth
    builtins["门分解"] = gate_decompose


def _quantum_compute_symtab_names() -> list[str]:
    return ["hadamard", "pauli_x", "pauli_y", "pauli_z", "cnot", "swap",
            "toffoli", "bell_state", "ghz_state", "qubit_state",
            "grover_iterate", "shor_period", "量子傅里叶变换", "电路深度", "门分解"]
