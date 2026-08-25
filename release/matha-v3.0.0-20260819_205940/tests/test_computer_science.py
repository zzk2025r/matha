# -*- coding: utf-8 -*-
"""计算机科学领域测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from src.domains.computer_science import (
    _大O比较, _递归深度估算,
    _香农熵, _信息量, _编码效率,
    _完全图边数, _树边数, _dfs遍历数, _最短路径估算,
    _德摩根定律_not_and, _德摩根定律_not_or,
    _蕴含等价, _双蕴含等价, _真值表行数,
    _栈操作操作, _队列操作操作,
)


class TestComputerScience(unittest.TestCase):
    # ---- 算法复杂度 ----

    def test_大O_小数据(self):
        self.assertEqual(_大O比较(5), "O(n!) 可行")

    def test_大O_中等数据(self):
        self.assertEqual(_大O比较(100), "O(n³) 可行")

    def test_大O_大数据(self):
        self.assertIn("O(n log n)", _大O比较(500000))

    def test_递归深度(self):
        self.assertEqual(_递归深度估算(1000, 5), 6)

    # ---- 信息论 ----

    def test_香农熵均匀分布(self):
        H = _香农熵([0.5, 0.5])
        self.assertAlmostEqual(H, 1.0)

    def test_香农熵确定性(self):
        H = _香农熵([1.0, 0.0])
        self.assertAlmostEqual(H, 0.0)

    def test_信息量(self):
        self.assertAlmostEqual(_信息量(0.25), 2.0)

    def test_编码效率(self):
        eff = _编码效率(1.5, 2.0)
        self.assertAlmostEqual(eff, 0.75)

    # ---- 图论 ----

    def test_完全图边数(self):
        self.assertEqual(_完全图边数(4), 6)

    def test_树边数(self):
        self.assertEqual(_树边数(5), 4)

    def test_最短路径复杂度(self):
        cost = _最短路径估算(100, 200)
        self.assertGreater(cost, 0)

    # ---- 离散数学 ----

    def test_德摩根_与(self):
        self.assertFalse(_德摩根定律_not_and(True, True))
        self.assertTrue(_德摩根定律_not_and(False, True))

    def test_德摩根_或(self):
        self.assertTrue(_德摩根定律_not_or(False, False))
        self.assertFalse(_德摩根定律_not_or(True, False))

    def test_蕴含等价(self):
        self.assertFalse(_蕴含等价(True, False))
        self.assertTrue(_蕴含等价(False, True))

    def test_双蕴含等价(self):
        self.assertTrue(_双蕴含等价(True, True))
        self.assertFalse(_双蕴含等价(True, False))

    def test_真值表行数(self):
        self.assertEqual(_真值表行数(3), 8)

    # ---- 数据结构模拟 ----

    def test_栈操作(self):
        result = _栈操作操作(["push", 1, "push", 2, "pop"])
        self.assertEqual(result["栈"], [1])
        self.assertEqual(result["错误数"], 0)

    def test_队列操作(self):
        result = _队列操作操作(["enqueue", 1, "enqueue", 2, "dequeue"])
        self.assertEqual(result["队列"], [2])
        self.assertEqual(result["错误数"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
