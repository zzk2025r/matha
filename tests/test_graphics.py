# -*- coding: utf-8 -*-
"""Graphics 领域测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from src.domains.graphics import (
    _齐次变换矩阵, _投影变换, _裁剪区域,
    _光栅化点数, _颜色空间转换, _抗锯齿系数,
)


class TestGraphics(unittest.TestCase):
    def test_homogeneous_transform(self):
        m = _齐次变换矩阵(0, 10, 20, 1.0)
        self.assertIsInstance(m, list)

    def test_projection(self):
        p = _投影变换(0.1, 100, 60)
        self.assertIsInstance(p, dict)
        self.assertIn('f', p)

    def test_clipping_region(self):
        area = _裁剪区域(0, 0, 640, 480)
        self.assertEqual(area, 307200)

    def test_rasterize_points(self):
        n = _光栅化点数(640, 480, 1)
        self.assertGreater(n, 0)

    def test_color_space_convert(self):
        c = _颜色空间转换(255, 0, 0)
        self.assertIsInstance(c, dict)
        self.assertIn('H', c)

    def test_anti_aliasing(self):
        coef = _抗锯齿系数(4)
        self.assertGreater(coef, 0)


if __name__ == '__main__':
    unittest.main()
