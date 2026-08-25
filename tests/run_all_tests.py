# -*- coding: utf-8 -*-
"""Matha 全量测试运行器"""
import unittest
import sys
from pathlib import Path

# 添加项目根目录到路径
_project_root = Path(__file__).parent.parent
sys.path.insert(0, str(_project_root))
sys.path.insert(0, str(_project_root / 'src'))

# 运行测试
if __name__ == '__main__':
    # 发现并运行所有测试
    loader = unittest.TestLoader()
    suite = loader.discover('tests', pattern='test_*.py')

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 打印摘要
    print("\n" + "=" * 60)
    print(f"  测试完成：{result.testsRun - len(result.failures) - len(result.errors)}/{result.testsRun} 通过")
    print(f"  失败：{len(result.failures)}, 错误：{len(result.errors)}, 跳过：{len(result.skipped) if hasattr(result, 'skipped') else 0}")
    print("=" * 60)

    # 退出码
    sys.exit(0 if result.wasSuccessful() else 1)
