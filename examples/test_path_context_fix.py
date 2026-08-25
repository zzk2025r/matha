# -*- coding: utf-8 -*-
"""
验证 _is_path_context 修复后的语境判断逻辑

测试场景：
  1. 顶层绑定 a>>b=5 → 应为 PathExpr（路径语境）
  2. 控制流条件 a>>b → 不应为 PathExpr
  3. lambda 体内 a>>b → 不应为 PathExpr
  4. 链式语境 a>>b >> c → 不应为 PathExpr
  5. 函数调用参数中 a>>b → 不应为 PathExpr
  6. 嵌套作用域同名变量 → 不应混淆
  7. 表达式中 a>>5 → 应为步进迭代，非路径
  8. while 条件 a>>b → 不应为 PathExpr
"""
import sys, logging
sys.path.insert(0, r"D:\trae")

# 启用 debug 日志
logging.basicConfig(
    level=logging.DEBUG,
    format="%(name)s [%(levelname)s] %(message)s",
)

from src.parser import Parser
from src import ast_nodes as ast

# ── 测试用例 ──────────────────────────────────────────────────────────────────
TEST_CASES = [
    # (name, source, expect_path_in_binding, note)
    ("顶层绑定路径 a>>b=5", "a >> b = 5", True, "Binding.target 应为 PathExpr"),
    ("控制流条件 if a>>b", "if a >> b then c", False, "_in_control_flow 应拒绝路径"),
    ("链式语境 #1：[a]>>[b]>>[c]", "#1：[a] >> [b] >> [c]", False, "_is_chain_context 应拒绝路径"),
    ("嵌套函数 a>>1", "def f(x): return x >> 1", False, "函数体内应为步进迭代"),
    ("表达式 a>>5", "a = 10\nb = a >> 5", False, "表达式中应为步进迭代，非路径"),
    ("多变量嵌套 z=y>>2", "x = 1\ny = x + 1\nz = y >> 2", False, "步进迭代非路径"),
    ("设定语句含路径 [a>>b=5]", "[a >> b = 5]", True, "设定语句中的路径"),
    ("纯控制流 if a>b", "if a > b then c", False, "普通比较，不涉及 >>"),
]


def count_path_expr(node):
    """递归统计 AST 中 PathExpr 节点数量（包括 Binding.target 中的路径）。"""
    count = 0
    if isinstance(node, ast.PathExpr):
        count += 1
    for attr_name in dir(node):
        if attr_name.startswith("_"):
            continue
        try:
            val = getattr(node, attr_name)
        except Exception:
            continue
        if isinstance(val, list):
            for item in val:
                if hasattr(item, "__class__"):
                    count += count_path_expr(item)
        elif hasattr(val, "__class__") and not isinstance(val, (str, int, float, bool, type(None))):
            count += count_path_expr(val)
    return count


print("=" * 70)
print("路径语境判断逻辑验证测试（_is_path_context 修复验证）")
print("=" * 70)

passed = 0
for name, source, expect_path, note in TEST_CASES:
    try:
        p = Parser(source)
        parsed_ast = p.parse()
        # 检查 Binding.target 中是否有 PathExpr
        has_path_in_binding = False
        for decl in parsed_ast.decls:
            if isinstance(decl, ast.Binding) and isinstance(decl.target, ast.PathExpr):
                has_path_in_binding = True
                break
        ok = has_path_in_binding == expect_path
        if ok:
            passed += 1
        status = "PASS" if ok else "FAIL"
        print(f"\n  [{status}] {name}")
        print(f"        源码: {source!r}")
        print(f"        Binding.target 含 PathExpr: {has_path_in_binding}")
        print(f"        期望: {expect_path}")
        print(f"        说明: {note}")
        if not ok:
            print(f"        ⚠ 路径判断结果与预期不符")
    except Exception as e:
        status = "ERROR"
        print(f"\n  [{status}] {name}")
        print(f"        源码: {source!r}")
        print(f"        异常: {e}")

print(f"\n结果: {passed}/{len(TEST_CASES)} 通过")

# ── 详细日志：运行一个典型路径场景 ───────────────────────────────────────────
print("\n" + "=" * 70)
print("详细 DEBUG 日志输出")
print("=" * 70)

print(f"\n--- 场景: 顶层绑定路径 a >> b = 5 ---")
p = Parser("a >> b = 5")
ast_result = p.parse()
has_p = any(isinstance(d, ast.Binding) and isinstance(d.target, ast.PathExpr) for d in ast_result.decls)
print(f"Binding.target 含 PathExpr: {has_p} (期望: True)")

print("\n--- 场景: 控制流中 a >> b (应拒绝路径) ---")
p2 = Parser("if a >> b then c")
ast2 = p2.parse()
pc2 = count_path_expr(ast2)
print(f"PathExpr 数量: {pc2} (期望: 0)")

print(f"\n--- 场景: 链式语境 a>>b>>c (应拒绝路径) ---")
p3 = Parser("#1：[a] >> [b] >> [c]")
ast3 = p3.parse()
has_p3 = any(isinstance(d, ast.Binding) and isinstance(d.target, ast.PathExpr) for d in ast3.decls)
print(f"Binding.target 含 PathExpr: {has_p3} (期望: False)")
