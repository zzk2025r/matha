# -*- coding: utf-8 -*-
"""
生态扩展功能完整测试套件

覆盖：
  - 可视化编辑器
  - 移动端完整实现
  - 离线存储
  - 协作功能
  - Tree-sitter C 扩展
"""
from __future__ import annotations
import sys
import unittest
sys.path.insert(0, r"D:\trae")


def load_tests(loader, standard_tests, pattern):
    """自动加载所有测试模块。"""
    top_level_dir = standard_tests.top_level_dir
    suite = unittest.TestSuite()

    test_modules = [
        "test_visual_editor",
        "test_mobile_offline_collab",
        "test_cext_and_package",
    ]

    for module_name in test_modules:
        try:
            mod = __import__(f"tests.{module_name}", fromlist=[""])
            suite.addTests(loader.loadTestsFromModule(mod))
        except ImportError as e:
            print(f"[WARN] 跳过测试模块 {module_name}: {e}")

    return suite


if __name__ == "__main__":
    unittest.main(verbosity=2)
