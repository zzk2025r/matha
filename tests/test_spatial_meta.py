# -*- coding: utf-8 -*-
"""Spatial Meta 领域测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest


class TestSpatialMeta(unittest.TestCase):
    """空间元数据领域测试。"""

    def test_import_and_register(self):
        from src.domains.spatial_meta import _register_spatial_meta
        builtins = {}
        _register_spatial_meta(builtins)
        self.assertGreater(len(builtins), 0)

    def test_symtab_names(self):
        from src.domains.spatial_meta import _spatial_meta_symtab_names
        names = _spatial_meta_symtab_names()
        self.assertEqual(len(names), 6)

    def test_spatial_index_efficiency(self):
        from src.domains.spatial_meta import _空间索引效率
        eff = _空间索引效率(1000, 4)
        self.assertGreater(eff, 0)

    def test_metadata_query_latency(self):
        from src.domains.spatial_meta import _元数据查询延迟
        lat = _元数据查询延迟(100, 10)
        self.assertGreater(lat, 0)

    def test_geocode_accuracy(self):
        from src.domains.spatial_meta import _地理编码精度
        acc = _地理编码精度('WGS84', 0.5)
        self.assertAlmostEqual(acc, 0.5, delta=0.01)

    def test_coordinate_transform_error(self):
        from src.domains.spatial_meta import _坐标变换误差
        err = _坐标变换误差(1.0, 0.5, 3)
        self.assertGreater(err, 0)

    def test_bbox_intersection(self):
        from src.domains.spatial_meta import _边界框交集
        result = _边界框交集(0, 0, 10, 10, 5, 5, 15, 15)
        self.assertTrue(result)

    def test_bbox_no_intersection(self):
        from src.domains.spatial_meta import _边界框交集
        result = _边界框交集(0, 0, 5, 5, 10, 10, 20, 20)
        self.assertFalse(result)

    def test_buffer_analysis_within(self):
        from src.domains.spatial_meta import _缓冲区分析
        result = _缓冲区分析(0, 0, 10, 3, 4)  # 距离=5 <= 10
        self.assertTrue(result)

    def test_buffer_analysis_outside(self):
        from src.domains.spatial_meta import _缓冲区分析
        result = _缓冲区分析(0, 0, 10, 100, 100)  # 距离 >> 10
        self.assertFalse(result)

    def test_buffer_analysis_on_boundary(self):
        from src.domains.spatial_meta import _缓冲区分析
        result = _缓冲区分析(0, 0, 10, 6, 8)  # 距离=10
        self.assertTrue(result)


if __name__ == '__main__':
    unittest.main()
