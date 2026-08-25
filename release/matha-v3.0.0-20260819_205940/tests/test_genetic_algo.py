# -*- coding: utf-8 -*-
"""遗传算法领域测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from src.domains.genetic_algo import (
    ga_evolve, elitism_preserve, code_generation,
    hyperparameter_search,
)


class TestGeneticAlgo(unittest.TestCase):
    def test_ga_evolve(self):
        """测试遗传算法找到全1解。"""
        population = [[0] * 8 for _ in range(20)]
        fitness_fn = lambda ind: sum(ind) / len(ind)
        result = ga_evolve(population, fitness_fn, pop_size=20, max_gen=50)
        self.assertGreaterEqual(result["best_fitness"], 0.0)
        self.assertIn("best_individual", result)

    def test_elitism_preserve(self):
        population = [[1, 0, 1], [0, 0, 0], [1, 1, 1]]
        fitness_fn = lambda ind: sum(ind)
        elite = elitism_preserve(population, fitness_fn, elite_count=1)
        self.assertEqual(len(elite), 1)
        self.assertEqual(elite[0], [1, 1, 1])

    def test_code_generation(self):
        template = "Hello {name}, you are {age} years old"
        result = code_generation(template, {"name": "Matha", "age": 2})
        self.assertEqual(result, "Hello Matha, you are 2 years old")

    def test_hyperparameter_search(self):
        search_space = {"lr": [0.001, 0.01, 0.1], "batch": [16, 32]}
        fitness_fn = lambda p: -abs(p.get("lr", 0) - 0.01)
        result = hyperparameter_search(search_space, fitness_fn, n_iterations=5)
        self.assertIn("best_params", result)
        self.assertIn("best_score", result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
