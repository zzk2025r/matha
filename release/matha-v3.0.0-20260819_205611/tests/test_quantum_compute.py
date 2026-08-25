# -*- coding: utf-8 -*-
"""量子计算领域测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
import cmath
from src.domains.quantum_compute import (
    hadamard, pauli_x, bell_state, ghz_state, qubit_state,
    shor_period_finding, circuit_depth,
)


class TestQuantumCompute(unittest.TestCase):
    def test_hadamard(self):
        H = hadamard()
        self.assertAlmostEqual(H[0][0], 1 / (2 ** 0.5))
        self.assertAlmostEqual(H[1][0], 1 / (2 ** 0.5))

    def test_pauli_x(self):
        X = pauli_x()
        self.assertEqual(X, [[0, 1], [1, 0]])

    def test_bell_state(self):
        state = bell_state()
        self.assertAlmostEqual(abs(state[0]), 1 / (2 ** 0.5))
        self.assertAlmostEqual(abs(state[3]), 1 / (2 ** 0.5))
        self.assertEqual(state[1], 0)
        self.assertEqual(state[2], 0)

    def test_ghz_state(self):
        state = ghz_state(2)
        self.assertEqual(len(state), 4)
        self.assertAlmostEqual(abs(state[0]), 1 / (2 ** 0.5))
        self.assertAlmostEqual(abs(state[3]), 1 / (2 ** 0.5))

    def test_qubit_state(self):
        state = qubit_state(0, 0)
        self.assertAlmostEqual(abs(state[0]), 1.0)
        self.assertAlmostEqual(abs(state[1]), 0.0)

    def test_shor_period(self):
        self.assertEqual(shor_period_finding(2, 7), 3)
        self.assertEqual(shor_period_finding(3, 7), 6)

    def test_circuit_depth(self):
        self.assertEqual(circuit_depth(["H", "CNOT", "X"], 2), 4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
