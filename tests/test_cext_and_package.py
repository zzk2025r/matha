# -*- coding: utf-8 -*-
"""
Tree-sitter C 扩展功能测试
验证 C 扩展的正确性和降级机制
"""
from __future__ import annotations
import sys
import unittest
from pathlib import Path
sys.path.insert(0, r"D:\trae")


class TestCSExtension(unittest.TestCase):
    """C 扩展模块测试。"""

    def test_import_python_fallback(self):
        """测试 Python 降级路径可用。"""
        from src.tree_sitter_backends import RustParser, GoParser, JSParser, CParser
        # 确认各解析器类可导入
        self.assertIsNotNone(RustParser)
        self.assertIsNotNone(GoParser)
        self.assertIsNotNone(JSParser)
        self.assertIsNotNone(CParser)

    def test_python_parser_works(self):
        """测试 Python 解析器正常工作。"""
        from src.tree_sitter_backends import RustParser
        parser = RustParser()
        tree = parser.parse("fn add(a:f64,b:f64)->f64{a+b}")
        self.assertIsNotNone(tree)
        self.assertTrue(len(tree.children) > 0)

    def test_go_parser_works(self):
        """测试 Go 解析器正常工作。"""
        from src.tree_sitter_backends import GoParser
        parser = GoParser()
        tree = parser.parse("func add(a float64,b float64) float64 { return a+b }")
        self.assertIsNotNone(tree)

    def test_js_parser_works(self):
        """测试 JS 解析器正常工作。"""
        from src.tree_sitter_backends import JSParser
        parser = JSParser()
        tree = parser.parse("function add(a,b){return a+b}")
        self.assertIsNotNone(tree)

    def test_c_parser_works(self):
        """测试 C 解析器正常工作。"""
        from src.tree_sitter_backends import CParser
        parser = CParser()
        tree = parser.parse("double add(double a,double b){return a+b;}")
        self.assertIsNotNone(tree)

    def test_cext_module_structure(self):
        """测试 C 扩展模块文件结构。"""
        cext_dir = Path("src/cext")
        self.assertTrue(cext_dir.exists())
        c_files = list(cext_dir.glob("*.c"))
        self.assertGreater(len(c_files), 0)

    def test_cext_setup_script(self):
        """测试 C 扩展构建脚本存在。"""
        setup_path = Path("packages/matha_treesitter/setup_cext.py")
        self.assertTrue(setup_path.exists())
        content = setup_path.read_text(encoding="utf-8")
        self.assertIn("Extension", content)
        self.assertIn("tree_sitter", content)

    def test_get_parser_function(self):
        """测试 get_parser 函数。"""
        from src.tree_sitter_backends import get_parser
        rust_parser = get_parser("rust")
        self.assertIsNotNone(rust_parser)
        tree = rust_parser.parse("fn test()->i32{42}")
        self.assertIsNotNone(tree)


class TestTreesitterPackage(unittest.TestCase):
    """matha-treesitter 包测试。"""

    def test_package_init(self):
        """测试包导入。"""
        from packages.matha_treesitter import get_parser, is_cext_available
        self.assertTrue(callable(get_parser))
        self.assertTrue(callable(is_cext_available))

    def test_is_cext_available(self):
        """测试 C 扩展可用性检测。"""
        from packages.matha_treesitter import is_cext_available
        result = is_cext_available()
        self.assertIsInstance(result, bool)

    def test_rust_parser_api(self):
        """测试 Rust 解析器 API。"""
        from packages.matha_treesitter import RustParser
        parser = RustParser()
        tree = parser.parse("fn main()->i32{1}")
        self.assertIsNotNone(tree)
        self.assertTrue(hasattr(tree, 'children'))

    def test_go_parser_api(self):
        """测试 Go 解析器 API。"""
        from packages.matha_treesitter import GoParser
        parser = GoParser()
        tree = parser.parse("func main(){}")
        self.assertIsNotNone(tree)

    def test_js_parser_api(self):
        """测试 JS 解析器 API。"""
        from packages.matha_treesitter import JSParser
        parser = JSParser()
        tree = parser.parse("function main(){}")
        self.assertIsNotNone(tree)

    def test_c_parser_api(self):
        """测试 C 解析器 API。"""
        from packages.matha_treesitter import CParser
        parser = CParser()
        tree = parser.parse("int main(){return 0;}")
        self.assertIsNotNone(tree)


if __name__ == "__main__":
    unittest.main(verbosity=2)
