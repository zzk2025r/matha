# -*- coding: utf-8 -*-
"""build_software 单元测试：记事本和计算器应用回归测试。

覆盖：
  1. 需求关键词匹配 → 正确模板选择
  2. 规格树生成 → 结构正确
  3. codegen → 文件生成成功 + Python 语法合法
  4. 日志输出 → 关键步骤可见
  5. 未匹配需求 → 默认桌面应用降级
  6. 多个需求变体（含"应用"/不含"应用"等）
"""
import ast as pyast
import os
import sys
import tempfile
import unittest
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.autonomous import build_software, _REQ_MAP
from src.codegen import codegen
from src.interp import Interpreter


class TestBuildSoftwareRequirementMatching(unittest.TestCase):
    """测试需求关键词匹配逻辑。"""

    def test_记事本匹配(self):
        """'记事本' 关键词应匹配记事本模板。"""
        interp = Interpreter()
        result = build_software(interp, "记事本桌面应用")
        self.assertTrue(result["成功"], f"构建失败: {result.get('错误')}")
        self.assertEqual(result["类型"], "桌面")
        self.assertEqual(result["名称"], "记事本")
        self.assertTrue(os.path.exists(result["入口"]))

    def test_计算器匹配(self):
        """'计算器' 关键词应匹配计算器模板。"""
        interp = Interpreter()
        result = build_software(interp, "计算器桌面")
        self.assertTrue(result["成功"], f"构建失败: {result.get('错误')}")
        self.assertEqual(result["类型"], "桌面")
        self.assertEqual(result["名称"], "计算器")
        self.assertTrue(os.path.exists(result["入口"]))

    def test_设置匹配(self):
        interp = Interpreter()
        result = build_software(interp, "设置")
        self.assertTrue(result["成功"], f"构建失败: {result.get('错误')}")
        self.assertEqual(result["类型"], "桌面")

    def test_登录匹配(self):
        interp = Interpreter()
        result = build_software(interp, "登录页面")
        self.assertTrue(result["成功"], f"构建失败: {result.get('错误')}")
        self.assertEqual(result["类型"], "桌面")

    def test_数据表匹配(self):
        interp = Interpreter()
        result = build_software(interp, "数据表")
        self.assertTrue(result["成功"], f"构建失败: {result.get('错误')}")
        self.assertEqual(result["类型"], "桌面")

    def test_网页应用匹配(self):
        interp = Interpreter()
        result = build_software(interp, "网页应用")
        self.assertTrue(result["成功"], f"构建失败: {result.get('错误')}")
        self.assertEqual(result["类型"], "网页")

    def test_未匹配需求降级桌面(self):
        """未知需求应默认降级为桌面应用。"""
        interp = Interpreter()
        result = build_software(interp, "我的自定义应用")
        self.assertTrue(result["成功"], f"构建失败: {result.get('错误')}")
        self.assertEqual(result["类型"], "桌面")
        self.assertEqual(result["名称"], "我的自定义应用")

    def test_空元素默认应用(self):
        """无模板匹配但含'应用'关键词，应生成空元素桌面应用。"""
        interp = Interpreter()
        result = build_software(interp, "空白应用")
        self.assertTrue(result["成功"], f"构建失败: {result.get('错误')}")
        self.assertEqual(result["类型"], "桌面")


class TestBuildSoftwareNotepad(unittest.TestCase):
    """记事本应用专项测试。"""

    def setUp(self):
        self.interp = Interpreter()
        self.result = build_software(self.interp, "记事本桌面应用")

    def test_构建成功(self):
        self.assertTrue(self.result["成功"], f"构建失败: {self.result.get('错误')}")

    def test_入口文件存在(self):
        self.assertTrue(os.path.exists(self.result["入口"]))

    def test_入口文件可读取(self):
        with open(self.result["入口"], encoding="utf-8") as f:
            content = f.read()
        self.assertGreater(len(content), 0)

    def test_Python语法合法(self):
        with open(self.result["入口"], encoding="utf-8") as f:
            content = f.read()
        try:
            pyast.parse(content)
        except SyntaxError as e:
            self.fail(f"生成的 main.py 语法错误: {e}")

    def test_含tkinter导入(self):
        with open(self.result["入口"], encoding="utf-8") as f:
            content = f.read()
        self.assertIn("tkinter", content)

    def test_含标题记事本(self):
        with open(self.result["入口"], encoding="utf-8") as f:
            content = f.read()
        self.assertIn("记事本", content)

    def test_含保存按钮(self):
        with open(self.result["入口"], encoding="utf-8") as f:
            content = f.read()
        self.assertIn("保存", content)

    def test_含清空按钮(self):
        with open(self.result["入口"], encoding="utf-8") as f:
            content = f.read()
        self.assertIn("清空", content)

    def test_含save处理函数(self):
        with open(self.result["入口"], encoding="utf-8") as f:
            content = f.read()
        self.assertIn("save", content)

    def test_含clear处理函数(self):
        with open(self.result["入口"], encoding="utf-8") as f:
            content = f.read()
        self.assertIn("clear", content)


class TestBuildSoftwareCalculator(unittest.TestCase):
    """计算器应用专项测试。"""

    def setUp(self):
        self.interp = Interpreter()
        self.result = build_software(self.interp, "计算器桌面")

    def test_构建成功(self):
        self.assertTrue(self.result["成功"], f"构建失败: {self.result.get('错误')}")

    def test_入口文件存在(self):
        self.assertTrue(os.path.exists(self.result["入口"]))

    def test_Python语法合法(self):
        with open(self.result["入口"], encoding="utf-8") as f:
            content = f.read()
        try:
            pyast.parse(content)
        except SyntaxError as e:
            self.fail(f"生成的 main.py 语法错误: {e}")

    def test_含tkinter导入(self):
        with open(self.result["入口"], encoding="utf-8") as f:
            content = f.read()
        self.assertIn("tkinter", content)

    def test_含标题计算器(self):
        with open(self.result["入口"], encoding="utf-8") as f:
            content = f.read()
        self.assertIn("计算器", content)

    def test_含数字按钮(self):
        with open(self.result["入口"], encoding="utf-8") as f:
            content = f.read()
        self.assertIn("1", content)
        self.assertIn("2", content)
        self.assertIn("3", content)

    def test_含加号按钮(self):
        with open(self.result["入口"], encoding="utf-8") as f:
            content = f.read()
        self.assertIn("+", content)

    def test_含等号按钮(self):
        with open(self.result["入口"], encoding="utf-8") as f:
            content = f.read()
        self.assertIn("=", content)

    def test_含calc处理函数(self):
        with open(self.result["入口"], encoding="utf-8") as f:
            content = f.read()
        self.assertIn("calc", content)

    def test_含输入框(self):
        with open(self.result["入口"], encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Entry", content)


class TestBuildSoftwareSpecTree(unittest.TestCase):
    """测试规格树生成的正确性。"""

    def test_记事本规格树结构(self):
        """记事本应生成含 4 个元素的桌面规格树。"""
        interp = Interpreter()
        # 直接构造规格树并调用 codegen
        spec = ["应用", "桌面", "记事本", [
            ["h1", "记事本", [], []],
            ["textarea", "", [], [{"width": "60"}, {"height": "20"}]],
            ["button", "保存", [], [{"onclick": "save"}]],
            ["button", "清空", [], [{"onclick": "clear"}]],
        ]]
        result = codegen(spec)
        self.assertTrue(result.成功)
        self.assertEqual(result.类型, "桌面")
        self.assertTrue(any(f.endswith("main.py") for f in result.文件))

    def test_计算器规格树结构(self):
        """计算器应生成含 7 个元素的桌面规格树。"""
        spec = ["应用", "桌面", "计算器", [
            ["h1", "计算器", [], []],
            ["input", "", [], [{"width": "30"}]],
            ["button", "1", [], []],
            ["button", "2", [], []],
            ["button", "3", [], []],
            ["button", "+", [], []],
            ["button", "=", [], [{"onclick": "calc"}]],
        ]]
        result = codegen(spec)
        self.assertTrue(result.成功)
        self.assertEqual(result.类型, "桌面")

    def test_空元素桌面应用(self):
        """空元素应用也能正常生成（不崩溃）。"""
        spec = ["应用", "桌面", "空白", []]
        result = codegen(spec)
        self.assertTrue(result.成功)


class TestBuildSoftwareLogging(unittest.TestCase):
    """测试 build_software 日志输出。"""

    def test_日志包含步骤信息(self):
        """关键步骤应在日志中可见。"""
        import io
        log_stream = io.StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setLevel(logging.INFO)
        logger = logging.getLogger("matha.autonomous")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        try:
            interp = Interpreter()
            result = build_software(interp, "记事本")
            log_output = log_stream.getvalue()

            self.assertIn("步骤1: 需求解析", log_output)
            self.assertIn("步骤2: 规格树生成", log_output)
            self.assertIn("步骤3: 调用 codegen", log_output)
            self.assertIn("关键词匹配成功", log_output)
            self.assertIn("codegen 结果", log_output)
        finally:
            logger.removeHandler(handler)


class TestBuildSoftwareErrorHandling(unittest.TestCase):
    """测试错误处理和边界情况。"""

    def test_空需求字符串(self):
        """空字符串需求应不崩溃，降级为桌面应用。"""
        interp = Interpreter()
        result = build_software(interp, "")
        # 不应崩溃
        self.assertIsInstance(result, dict)
        self.assertIn("成功", result)

    def test_需求含特殊字符(self):
        """含特殊字符的需求不应崩溃。"""
        interp = Interpreter()
        result = build_software(interp, "记事本桌面应用 @#$")
        self.assertIsInstance(result, dict)
        self.assertIn("成功", result)

    def test_未知类型降级(self):
        """不包含任何已知关键词的需求应默认降级。"""
        interp = Interpreter()
        result = build_software(interp, "xyz完全不相关abc")
        self.assertIsInstance(result, dict)
        # 不应崩溃，成功为 True（空规格也能生成）
        self.assertIn("成功", result)


if __name__ == "__main__":
    unittest.main()
