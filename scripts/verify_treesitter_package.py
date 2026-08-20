# -*- coding: utf-8 -*-
"""
修复 matha_treesitter 包导入问题
"""
import sys
sys.path.insert(0, r"D:\trae")

from packages.matha_treesitter import (
    RustParser, GoParser, JSParser, CParser,
    get_parser, is_cext_available, parse_source, ASTNode,
)

print("=== matha-treesitter 包导入测试 ===")
print(f"is_cext_available: {is_cext_available()}")

# 测试各语言解析器
for lang, test_code in [
    ("rust", "fn add(a:f64,b:f64)->f64{a+b}"),
    ("go", "func add(a float64,b float64) float64 { return a+b }"),
    ("javascript", "function add(a,b){return a+b}"),
    ("c", "double add(double a,double b){return a+b;}"),
]:
    parser = get_parser(lang)
    tree = parser.parse(test_code)
    print(f"  {lang:>12s}: OK (type={tree.type}, children={len(tree.children)})")

print("\n=== 全部通过 ===")
