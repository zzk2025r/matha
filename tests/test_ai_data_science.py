# -*- coding: utf-8 -*-
"""AI 与数据科学领域测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from src.domains.ai_data_science import (
    sigmoid, relu, softmax, mse, cross_entropy, accuracy,
    dot_product, matrix_mult, mean, variance, correlation,
    gradient_descent,
)


class TestAIDataScience(unittest.TestCase):
    def test_sigmoid(self):
        self.assertAlmostEqual(sigmoid(0.0), 0.5, places=5)
        self.assertAlmostEqual(sigmoid(10.0), 1.0, places=4)
        self.assertAlmostEqual(sigmoid(-10.0), 0.0, places=4)

    def test_relu(self):
        self.assertEqual(relu(-5.0), 0.0)
        self.assertEqual(relu(3.0), 3.0)

    def test_softmax(self):
        result = softmax([1.0, 2.0, 3.0])
        self.assertAlmostEqual(sum(result), 1.0, places=5)
        self.assertTrue(all(r > 0 for r in result))

    def test_mse(self):
        self.assertAlmostEqual(mse([1.0, 2.0], [1.0, 2.0]), 0.0)
        self.assertAlmostEqual(mse([0.0, 0.0], [1.0, 1.0]), 1.0)

    def test_cross_entropy(self):
        self.assertAlmostEqual(cross_entropy([1.0], [0.99]), 0.01005, places=4)

    def test_accuracy(self):
        self.assertEqual(accuracy([0, 1, 1, 0], [0, 1, 0, 1]), 0.5)

    def test_dot_product(self):
        self.assertAlmostEqual(dot_product([1.0, 2.0], [3.0, 4.0]), 11.0)

    def test_matrix_mult(self):
        result = matrix_mult([[1, 2], [3, 4]], [[5, 6], [7, 8]])
        self.assertEqual(result, [[19, 22], [43, 50]])

    def test_mean(self):
        self.assertEqual(mean([1, 2, 3, 4, 5]), 3.0)

    def test_variance(self):
        self.assertAlmostEqual(variance([2, 4, 4, 4, 5, 5, 7, 9]), 4.0)

    def test_correlation(self):
        self.assertAlmostEqual(correlation([1, 2, 3], [2, 4, 6]), 1.0)

    def test_gradient_descent(self):
        params = {"w": 1.0, "b": 0.0}
        grads = {"w": 0.5, "b": 0.1}
        result = gradient_descent(params, grads, lr=0.1)
        self.assertAlmostEqual(result["w"], 0.95)
        self.assertAlmostEqual(result["b"], -0.01)


if __name__ == "__main__":
    unittest.main(verbosity=2)
