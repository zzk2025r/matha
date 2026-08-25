# -*- coding: utf-8 -*-
"""Matha 文档生成器测试

测试文档生成器的功能：
  - 模块发现
  - 函数文档提取
  - 类文档提取
  - Markdown 输出
  - HTML 输出
  - JSON 输出
"""
import unittest
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
_project_root = Path(__file__).parent.parent
sys.path.insert(0, str(_project_root))
sys.path.insert(0, str(_project_root / 'src'))

# 添加 tools 目录到路径
_tools_path = str(_project_root / 'src' / 'tools')
if _tools_path not in sys.path:
    sys.path.insert(0, _tools_path)

# 导入模块（非包模式）
try:
    from doc_generator import MathaDocGenerator, FunctionDoc, ClassDoc, ModuleDoc
except ImportError:
    # 尝试包模式
    from src.tools.doc_generator import MathaDocGenerator, FunctionDoc, ClassDoc, ModuleDoc


class TestMathaDocGenerator(unittest.TestCase):
    """测试文档生成器"""

    def setUp(self):
        """设置测试环境"""
        self.generator = MathaDocGenerator([
            'src/stdlib',
            'src/domains',
        ])

    def test_discover_modules(self):
        """测试模块发现"""
        modules = self.generator.discover_modules()
        self.assertIsInstance(modules, list)
        self.assertGreater(len(modules), 0)
        for m in modules:
            self.assertTrue(m.suffix == '.py')

    def test_parse_docstring(self):
        """测试 docstring 解析"""
        docstring = '''
        这是一个测试函数。

        Args:
            x: 输入参数
            y: 另一个参数

        Returns:
            计算结果

        Examples:
            >>> test(1, 2)
            3
        '''
        result = self.generator.parse_docstring(docstring)
        self.assertEqual(result['description'], '这是一个测试函数。')
        self.assertEqual(len(result['parameters']), 2)
        self.assertEqual(result['parameters'][0]['name'], 'x')
        self.assertEqual(result['parameters'][1]['name'], 'y')
        self.assertEqual(result['returns'], '计算结果')
        # 示例可能有多种解析方式，检查至少有一个
        self.assertGreaterEqual(len(result['examples']), 1)

    def test_parse_empty_docstring(self):
        """测试空 docstring"""
        result = self.generator.parse_docstring('')
        self.assertEqual(result['description'], '')
        self.assertEqual(result['parameters'], [])
        self.assertIsNone(result['returns'])

    def test_generate_markdown(self):
        """测试 Markdown 生成"""
        self.generator.generate()
        md_content = self.generator.generate_markdown('/tmp/test_api.md')
        self.assertIsInstance(md_content, str)
        self.assertGreater(len(md_content), 0)
        self.assertIn('# Matha API 参考文档', md_content)

    def test_generate_html(self):
        """测试 HTML 生成"""
        self.generator.generate()
        html_content = self.generator.generate_html('/tmp/test_api.html')
        self.assertIsInstance(html_content, str)
        self.assertGreater(len(html_content), 0)
        self.assertIn('<!DOCTYPE html>', html_content)
        self.assertIn('<title>Matha API 参考文档</title>', html_content)

    def test_generate_json(self):
        """测试 JSON 生成"""
        self.generator.generate()
        json_content = self.generator.generate_json('/tmp/test_api.json')
        self.assertIsInstance(json_content, str)
        self.assertGreater(len(json_content), 0)
        import json
        data = json.loads(json_content)
        self.assertIsInstance(data, dict)
        self.assertGreater(len(data), 0)


class TestFunctionDoc(unittest.TestCase):
    """测试 FunctionDoc 数据类"""

    def test_create_function_doc(self):
        """测试创建函数文档"""
        doc = FunctionDoc(
            name='test_func',
            module='test_module',
            description='测试描述',
            parameters=[{'name': 'x', 'type': 'int'}],
            returns='str',
            examples=['>>> test_func(1)'],
            source_file='test.py',
            source_line=10
        )
        self.assertEqual(doc.name, 'test_func')
        self.assertEqual(doc.module, 'test_module')
        self.assertEqual(len(doc.parameters), 1)


class TestClassDoc(unittest.TestCase):
    """测试 ClassDoc 数据类"""

    def test_create_class_doc(self):
        """测试创建类文档"""
        method = FunctionDoc(
            name='method1',
            module='test',
            description='方法描述',
            parameters=[],
            returns=None,
            examples=[],
            source_file='test.py',
            source_line=20
        )
        doc = ClassDoc(
            name='TestClass',
            module='test_module',
            description='类描述',
            attributes=[{'name': 'attr1'}],
            methods=[method],
            source_file='test.py',
            source_line=5
        )
        self.assertEqual(doc.name, 'TestClass')
        self.assertEqual(len(doc.methods), 1)
        self.assertEqual(doc.methods[0].name, 'method1')


class TestModuleDoc(unittest.TestCase):
    """测试 ModuleDoc 数据类"""

    def test_create_module_doc(self):
        """测试创建模块文档"""
        doc = ModuleDoc(
            name='test_module',
            file_path='/path/to/test.py',
            description='模块描述',
            classes=[],
            functions=[],
            submodules=[]
        )
        self.assertEqual(doc.name, 'test_module')
        self.assertEqual(len(doc.classes), 0)
        self.assertEqual(len(doc.functions), 0)


if __name__ == '__main__':
    unittest.main()
