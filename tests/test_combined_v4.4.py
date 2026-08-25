# -*- coding: utf-8 -*-
"""Matha v4.4 符号微积分与矩阵运算单元测试

用法：
  python -m unittest tests.test_calculus_symbolic tests.test_linear_algebra -v
"""
import unittest
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def suite():
    """创建测试套件。"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加符号微积分测试
    suite.addTests(loader.loadTestsFromName('tests.test_calculus_symbolic'))

    # 添加矩阵运算测试
    suite.addTests(loader.loadTestsFromName('tests.test_linear_algebra'))

    return suite


if __name__ == "__main__":
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite())
