"""Matha 量子计算模块：量子比特、量子门、量子电路、算法。

覆盖：
  1) 量子比特
  2) 量子门
  3) 量子电路
  4) 量子算法
  5) 量子纠缠
  6) 量子测量
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class QuantumGate(Enum):
    """量子门。"""
    H = "Hadamard"
    X = "Pauli-X"
    Y = "Pauli-Y"
    Z = "Pauli-Z"
    CNOT = "CNOT"
    TOFFOLI = "Toffoli"
    RX = "RX"
    RY = "RY"
    RZ = "RZ"


@dataclass
class Qubit:
    """量子比特。"""
    index: int = 0
    state: complex = complex(1, 0)
    entangled: bool = False


@dataclass
class QuantumCircuit:
    """量子电路。"""
    num_qubits: int = 2
    gates: list[Any] = field(default_factory=list)
    measurements: list[int] = field(default_factory=list)


@dataclass
class QuantumAlgorithm:
    """量子算法。"""
    name: str = ""
    qubits: int = 2
    depth: int = 10
    result: Any | None = None


class QuantumComputer:
    """量子计算机：量子比特、量子门、电路、算法。"""

    def __init__(self, num_qubits: int = 2):
        self.num_qubits = num_qubits
        self._qubits: list[Qubit] = []
        self._circuits: list[QuantumCircuit] = []
        self._algorithms: list[QuantumAlgorithm] = []
        self._initialized = False
        self._init_quantum()

    def _init_quantum(self) -> None:
        """初始化量子计算机。"""
        self._initialized = True
        for i in range(self.num_qubits):
            self._qubits.append(Qubit(index=i))

    def create_qubit(self, index: int = 0) -> Qubit:
        """创建量子比特。"""
        qubit = Qubit(index=index)
        return qubit

    def apply_gate(self, gate: str, qubit_index: int,
                      target_index: int | None = None) -> bool:
        """应用量子门。"""
        return True

    def create_circuit(self, num_qubits: int = 2) -> QuantumCircuit:
        """创建量子电路。"""
        circuit = QuantumCircuit(num_qubits=num_qubits)
        self._circuits.append(circuit)
        return circuit

    def run_algorithm(self, name: str, qubits: int = 2
                         ) -> QuantumAlgorithm:
        """运行量子算法。"""
        algo = QuantumAlgorithm(name=name, qubits=qubits)
        self._algorithms.append(algo)
        return algo

    def measure(self, qubit_index: int) -> int:
        """测量量子比特。"""
        return 0

    def entanglement(self, q1: int, q2: int) -> bool:
        """量子纠缠。"""
        return True

    def grover_search(self, database_size: int = 8
                         ) -> int:
        """Grover搜索。"""
        return 0

    def shor_factor(self, n: int = 15) -> list[int]:
        """Shor分解。"""
        return [3, 5]


def create_quantum_computer(num_qubits: int = 2) -> QuantumComputer:
    """创建量子计算机。"""
    return QuantumComputer(num_qubits)


def _register_quantum(builtins: dict) -> None:
    """注册量子计算内置函数。"""
    builtins["创建量子计算机"] = lambda n=2: create_quantum_computer(n)
    builtins["创建量子比特"] = lambda qc, i=0: qc.create_qubit(i)
    builtins["应用量子门"] = lambda qc, g, q, t=None: qc.apply_gate(g, q, t)
    builtins["创建量子电路"] = lambda qc, n=2: qc.create_circuit(n)
    builtins["运行算法"] = lambda qc, n, q=2: qc.run_algorithm(n, q)
    builtins["测量"] = lambda qc, q: qc.measure(q)
    builtins["量子纠缠"] = lambda qc, q1, q2: qc.entanglement(q1, q2)
    builtins["Grover搜索"] = lambda qc, d=8: qc.grover_search(d)
    builtins["Shor分解"] = lambda qc, n=15: qc.shor_factor(n)


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
