# -*- coding: utf-8 -*-
"""混沌理论与分型领域测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from src.domains.chaos_fractal import (
    lorenz_deriv, henon_map, logistic_map,
    mandelbrot_iter, julia_iter, lyapunov_exponent,
)


class TestChaosFractal(unittest.TestCase):
    def test_lorenz_deriv(self):
        dx, dy, dz = lorenz_deriv(1.0, 1.0, 1.0)
        self.assertAlmostEqual(dx, 0.0)
        self.assertAlmostEqual(dy, 26.0)
        self.assertAlmostEqual(dz, -1.6667, places=4)

    def test_henon_map(self):
        x, y = henon_map(0.0, 0.0)
        self.assertAlmostEqual(x, 1.0)
        self.assertAlmostEqual(y, 0.0)

    def test_logistic_map(self):
        result = logistic_map(0.5, r=3.5)
        self.assertAlmostEqual(result, 0.875)

    def test_mandelbrot(self):
        self.assertEqual(mandelbrot_iter(0.0, 0.0, max_iter=100), 100)
        self.assertEqual(mandelbrot_iter(2.0, 0.0, max_iter=100), 1)

    def test_julia(self):
        result = julia_iter(-0.8, 0.156, 0.0, 0.0)
        self.assertIsInstance(result, int)

    def test_lyapunov(self):
        result = lyapunov_exponent(3.9, x0=0.5, steps=1000)
        self.assertGreater(result, 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
