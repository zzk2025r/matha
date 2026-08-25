# -*- coding: utf-8 -*-
"""创意编程领域测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from src.domains.creative_coding import (
    PerlinNoise, simplex_noise_2d, particle_system,
    fractal_barnsley_fern, color_hsl_to_rgb, audio_reactive,
)


class TestCreativeCoding(unittest.TestCase):
    def test_perlin_noise(self):
        perlin = PerlinNoise(seed=42)
        result = perlin.noise_2d(0.0, 0.0)
        self.assertIsInstance(result, float)

    def test_simplex_noise(self):
        result = simplex_noise_2d(1.0, 2.0)
        self.assertIsInstance(result, float)

    def test_particle_system(self):
        particles = particle_system(5, width=800.0, height=600.0)
        self.assertEqual(len(particles), 5)
        self.assertIn("x", particles[0])

    def test_barnsley_fern(self):
        points = fractal_barnsley_fern(n=100)
        self.assertEqual(len(points), 101)
        self.assertEqual(len(points[0]), 2)

    def test_color_hsl_to_rgb(self):
        r, g, b = color_hsl_to_rgb(0.0, 1.0, 0.5)
        self.assertAlmostEqual(r, 1.0)
        self.assertAlmostEqual(g, 0.0)
        self.assertAlmostEqual(b, 0.0)

    def test_audio_reactive(self):
        bands = [0.1, 0.5, 0.9]
        result = audio_reactive(bands, energy=0.8, sensitivity=1.0)
        self.assertEqual(len(result), 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
