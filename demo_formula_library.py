#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Matha 综合公式库演示"""
import logging
logging.basicConfig(level=logging.WARNING)

from src.formula_system import (
    get_formula_registry, reset_formula_registry,
    derive_formula, verify_formulas,
)

reset_formula_registry()
r = get_formula_registry()
lib = r._formula_library

print("=" * 50)
print("  Matha 综合公式库 — 完整演示")
print("=" * 50)
print()
print(f"总公式数: {len(r.list_formulas())}")
print(f"公式库定义: {lib.total_count()} 个")
print(f"演化规则: {len(r._evolution_engine._rules) if r._evolution_engine else 0} 条")
print()

print("========== 按数学域分布 ==========")
for domain, count in sorted(lib.domain_counts().items()):
    print(f"  {domain:25s}: {count:>3d} 个")
print()

print("========== 公式示例（可计算） ==========")
examples = [
    "圆面积", "球体积", "海伦公式", "勾股定理",
    "正弦定理", "二项式定理", "组合数", "贝叶斯定理",
    "导数定义", "正切定义",
]
for name in examples:
    f = r.get(name)
    if f:
        params = f.params[:3] if f.params else []
        val = "N/A"
        if params:
            try:
                b = {p: 2.0 for p in params}
                v = f.evaluate(b)
                val = f"{v:.3f}"
            except Exception:
                val = f"(需要{params})"
        expr_str = str(f.expr)[:35]
        print(f"  {name:20s} = {expr_str:35s}  eval={val}")

print()
print("========== 演化推导链 ==========")
print("  圆面积(πr²) ──演化──→ 球体积(4/3πr³)")
print("  圆面积(πr²) ──演化──→ 球表面积(4πr²)")
print("  椭圆(πab)  ──退化──→ 圆(当a=b)")
print("  正六边形   ──分割──→ 6×正三角形")
print("  sin²+cos²=1 ──演化──→ tan/cot/sec")
print("  勾股定理   ──演化──→ 余弦定理")
print("  等差数列   ──演化──→ 求和公式")
print()
print("========== 公式互转验证 ==========")
result = derive_formula("expr / 2", "长方形面积", "三角形面积")
print(f"  长方形面积 ÷ 2 = 三角形面积")
print(f"    推导: {result.derived_formula}")

v = verify_formulas("长方形面积", "平行四边形面积",
                    {"长": 5.0, "宽": 3.0, "底": 5.0, "高": 3.0})
status = "PASS" if v.success else "FAIL"
print(f"  长方形面积 ≡ 平行四边形面积 ? {status}")
print()

# 阿基米德定理验证
print("========== 阿基米德定理验证 ==========")
sphere = r.get("球体积").evaluate({"半径": 3.0, "π": 3.14159265359})
cyl = r.get("圆柱体积").evaluate({"底半径": 3.0, "高": 6.0, "π": 3.14159265359})
print(f"  球体积(r=3): {sphere:.4f}")
print(f"  2/3 × 圆柱体积(底r=3,高=6): {2/3*cyl:.4f}")
print(f"  一致: {abs(sphere - 2/3*cyl) < 1e-6}")

print()
print("=" * 50)
print("  公式无上限，基础即下线")
print("  所有公式从基础公理自然演化")
print("=" * 50)
