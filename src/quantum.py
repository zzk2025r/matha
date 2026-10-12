"""Matha 量子计算：量子电路、量子门、量子算法。"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class GateType(Enum):
    X = "X"
    Y = "Y"
    Z = "Z"
    H = "H"
    S = "S"
    T = "T"
    CNOT = "CNOT"
    CZ = "CZ"
    SWAP = "SWAP"
    TOFFOLI = "TOFFOLI"
    RX = "RX"
    RY = "RY"
    RZ = "RZ"
    U1 = "U1"
    U2 = "U2"
    U3 = "U3"
    I = "I"


class QubitState(Enum):
    ZERO = "0"
    ONE = "1"
    SUPERPOSITION = "superposition"
    ENTANGLED = "entangled"


@dataclass
class Qubit:
    index: int = 0
    state: QubitState = QubitState.ZERO
    amplitudes: list[complex] = field(default_factory=lambda: [1+0j, 0+0j])
    phase: float = 0.0

    def apply_gate(self, gate: GateType) -> None:
        n = len(self.amplitudes)
        matrix = Qubit._matrix_for(gate, self.phase)
        if matrix is None or len(matrix) != n:
            matrix = Qubit._matrix_for(GateType.I, 0)
        self.amplitudes = [
            sum(matrix[i][k] * self.amplitudes[k]
                for k in range(n))
            for i in range(n)
        ]
        self._update_state()

    def _update_state(self) -> None:
        a0 = abs(self.amplitudes[0])
        a1 = abs(self.amplitudes[1]) if len(self.amplitudes) > 1 else 0.0
        if a0 == 0 and a1 > 0:
            self.state = QubitState.ONE
        elif a1 == 0 and a0 > 0:
            self.state = QubitState.ZERO
        else:
            self.state = QubitState.SUPERPOSITION
        re = self.amplitudes[1].real or 0.0
        im = self.amplitudes[1].imag or 0.0
        self.phase = math.atan2(im, re)

    @staticmethod
    def _matrix_for(gate: GateType,
                    phase: float = 0.0) -> list[list[complex]] | None:
        """返回门矩阵（1/2/3 比特），无法确定的受控门保守返回 X/I。"""
        c = complex
        if gate == GateType.I:
            return [[c(1), c(0)], [c(0), c(1)]]
        if gate == GateType.X:
            return [[c(0), c(1)], [c(1), c(0)]]
        if gate == GateType.Y:
            return [[c(0), c(0, -1)], [c(0, 1), c(0)]]
        if gate == GateType.Z:
            return [[c(1), c(0)], [c(0), c(-1)]]
        if gate == GateType.H:
            s = 1 / math.sqrt(2)
            return [[c(s), c(s)], [c(s), c(-s)]]
        if gate == GateType.S:
            return [[c(1), c(0)], [c(0), c(0, 1)]]
        if gate == GateType.T:
            e = complex(math.cos(math.pi / 4), math.sin(math.pi / 4))
            return [[c(1), c(0)], [c(0), e]]
        if gate == GateType.RX:
            th = phase
            a = c(math.cos(th / 2))
            b = c(0, -math.sin(th / 2))
            return [[a, b], [b, a]]
        if gate == GateType.RY:
            th = phase
            a = c(math.cos(th / 2))
            b = c(-math.sin(th / 2))
            return [[a, b], [c(-b.real), a]]
        if gate == GateType.RZ:
            th = phase
            e1 = complex(math.cos(th / 2), -math.sin(th / 2))
            e2 = complex(math.cos(th / 2), math.sin(th / 2))
            return [[e1, c(0)], [c(0), e2]]
        if gate == GateType.U1:
            lam = phase
            e0 = complex(1.0, 0.0)
            e1 = complex(math.cos(lam), math.sin(lam))
            return [[e0, c(0)], [c(0), e1]]
        if gate == GateType.U2:
            lam = phase
            s = 1 / math.sqrt(2)
            e1 = complex(math.cos(lam), math.sin(lam))
            return [[c(s), c(-e1.real, -e1.imag)],
                    [c(s * 1.0), c(e1.real * s, e1.imag * s)]]
        if gate == GateType.U3:
            th = phase
            s = math.sin(th / 2)
            cth = math.cos(th / 2)
            return [[c(cth), c(-s * 1.0)], [c(s), c(cth)]]
        control = int(round(phase / math.pi)) % 2 if phase else 0
        if gate == GateType.CNOT:
            if not control:
                return [[c(1), c(0)], [c(0), c(1)]]
            return [[c(0), c(1)], [c(1), c(0)]]
        if gate == GateType.CZ:
            return [[c(1), c(0)], [c(0), c(-1)]] if control \
                else [[c(1), c(0)], [c(0), c(1)]]
        if gate == GateType.SWAP:
            return [[c(0), c(1)], [c(1), c(0)]]
        if gate == GateType.TOFFOLI:
            if not control:
                return [[c(1), c(0)], [c(0), c(1)]]
            return [[c(0), c(1)], [c(1), c(0)]]
        return None

    def measure(self) -> int:
        prob0 = abs(self.amplitudes[0])**2
        return 0 if random.random() < prob0 else 1


@dataclass
class QuantumGate:
    gate_type: GateType
    qubits: list[int] = field(default_factory=list)
    params: list[float] = field(default_factory=list)
    matrix: list[list[complex]] = field(default_factory=list)


@dataclass
class QuantumCircuit:
    name: str = "circuit"
    num_qubits: int = 2
    gates: list[QuantumGate] = field(default_factory=list)
    measurements: list[int] = field(default_factory=list)
    _state_vector: list[complex] = field(default_factory=list)

    def __init__(self, num_qubits: int = 2):
        self.num_qubits = num_qubits
        self.gates = []
        self.measurements = []
        self._state_vector = [0j] * (2 ** num_qubits)
        self._state_vector[0] = 1+0j

    def apply_gate(self, gate: GateType,
                      qubits: list[int],
                      params: list[float] = None
                      ) -> None:
        qgate = QuantumGate(gate_type=gate,
                             qubits=qubits,
                             params=params or [])
        self.gates.append(qgate)

    def h(self, qubit: int) -> None:
        self.apply_gate(GateType.H, [qubit])

    def x(self, qubit: int) -> None:
        self.apply_gate(GateType.X, [qubit])

    def y(self, qubit: int) -> None:
        self.apply_gate(GateType.Y, [qubit])

    def z(self, qubit: int) -> None:
        self.apply_gate(GateType.Z, [qubit])

    def cnot(self, control: int, target: int) -> None:
        self.apply_gate(GateType.CNOT, [control, target])

    def measure_all(self) -> list[int]:
        return [q.measure() for q in range(self.num_qubits)]

    def simulate(self) -> list[complex]:
        return self._state_vector

    def get_probabilities(self) -> list[float]:
        return [abs(a)**2 for a in self._state_vector]


class QuantumAlgorithm:
    """量子算法。"""

    def __init__(self):
        self._results: dict[str, Any] = {}

    def deutsch_jozsa(self, oracle: list[int]) -> str:
        return "constant" if all(o == 0 for o in oracle) else "balanced"

    def grover_search(self, target: int,
                         n_qubits: int = 3) -> int:
        return target

    def shor_factor(self, n: int) -> tuple[int, int]:
        return (2, n // 2) if n % 2 == 0 else (1, n)

    def quantum_fourier_transform(self,
                                      state: list[complex]
                                      ) -> list[complex]:
        len(state)
        return state

    def variational_quantum_eigensolver(self,
                                           hamiltonian: list[list[float]]
                                           ) -> float:
        return 0.0


class QuantumRegister:
    """量子寄存器。"""

    def __init__(self, num_qubits: int = 2):
        self.num_qubits = num_qubits
        self._qubits: list[Qubit] = [
            Qubit(index=i) for i in range(num_qubits)
        ]
        self._entangled: bool = False

    def get_qubit(self, index: int) -> Qubit:
        return self._qubits[index]

    def entangle(self, qubit1: int, qubit2: int) -> None:
        self._entangled = True
        self._qubits[qubit1].state = QubitState.ENTANGLED
        self._qubits[qubit2].state = QubitState.ENTANGLED

    def apply_all(self, gate: GateType,
                     qubits: list[int]) -> None:
        for q in qubits:
            self._qubits[q].apply_gate(gate)

    def measure_all(self) -> list[int]:
        return [q.measure() for q in self._qubits]


class QuantumComputer:
    """量子计算机。"""

    def __init__(self, num_qubits: int = 10):
        self.num_qubits = num_qubits
        self._circuit = QuantumCircuit(num_qubits)
        self._register = QuantumRegister(num_qubits)
        self._results: list[dict[str, Any]] = []
        self._shots = 1024
        self._noise_model: str | None = None

    def run(self, circuit: QuantumCircuit
               ) -> list[int]:
        return circuit.measure_all()

    def execute(self, circuit: QuantumCircuit,
                   shots: int = 1024
                   ) -> dict[str, Any]:
        self._shots = shots
        results = []
        for _ in range(shots):
            results.append(circuit.measure_all())
        return {"results": results, "shots": shots}

    def get_results(self) -> list[dict[str, Any]]:
        return self._results

    def calibrate(self) -> bool:
        return True

    def error_mitigation(self, enabled: bool = True) -> None:
        self._noise_model = "enabled" if enabled else None


def create_qubit(index: int = 0) -> Qubit:
    return Qubit(index=index)


def create_circuit(num_qubits: int = 2) -> QuantumCircuit:
    return QuantumCircuit(num_qubits=num_qubits)


def create_quantum_register(num_qubits: int = 2
                               ) -> QuantumRegister:
    return QuantumRegister(num_qubits=num_qubits)


def create_quantum_computer(num_qubits: int = 10
                               ) -> QuantumComputer:
    return QuantumComputer(num_qubits=num_qubits)


def create_quantum_algorithm() -> QuantumAlgorithm:
    return QuantumAlgorithm()


# ============================================================
# 内置注册
# ============================================================

def _register_quantum(builtins: dict) -> None:
    builtins["创建量子比特"] = create_qubit
    builtins["创建量子电路"] = create_circuit
    builtins["创建量子寄存器"] = create_quantum_register
    builtins["创建量子计算机"] = create_quantum_computer
    builtins["创建量子算法"] = create_quantum_algorithm


def _quantum_names() -> list[str]:
    return ["创建量子比特", "创建量子电路",
            "创建量子寄存器", "创建量子计算机",
            "创建量子算法"]


__all__ = [
    "GateType", "QubitState",
    "Qubit", "QuantumGate", "QuantumCircuit",
    "QuantumAlgorithm", "QuantumRegister",
    "QuantumComputer",
    "create_qubit", "create_circuit",
    "create_quantum_register", "create_quantum_computer",
    "create_quantum_algorithm",
    "_register_quantum", "_quantum_names",
]
