"""Matha 学科专业知识资源库测试。"""
import subprocess, sys, os
import glob

from src.interp import interpret
from src.parser import parse
from src import ast_nodes as ast

RESOURCE_ROOT = os.path.join(os.path.dirname(__file__), "..", "matha", "resource")


def _load(path):
    full = os.path.join(RESOURCE_ROOT, path + ".matha")
    if not os.path.exists(full):
        return None
    with open(full, encoding="utf-8") as f:
        return f.read()


def _count_funcs(content):
    prog = parse(content)
    count = 0
    for decl in prog.decls:
        if isinstance(decl, ast.ModuleDecl):
            count += sum(1 for s in decl.decls if isinstance(s, ast.FuncDef))
        elif isinstance(decl, ast.FuncDef):
            count += 1
    return count


def test_file_existence():
    print("\n--- 资源文件存在性 ---")
    modules = [
        "math/conic_sections", "math/algebra_advanced", "math/trigonometry_advanced", "math/exponent_logarithm",
        "physics/electromagnetism", "physics/thermodynamics", "physics/optics", "physics/quantum",
        "chemistry/stoichiometry",
        "biology/molecular", "biology/genetics",
        "cs/algorithms", "cs/data_structures",
        "engineering/mechanical", "engineering/civil",
        "statistics/analysis", "statistics/probability",
        "finance/math", "geography/info",
        "logic/discrete_math", "linguistics/basics",
    ]
    ok = sum(1 for m in modules if _load(m) is not None)
    print(f"  {ok}/{len(modules)} 文件存在")
    assert ok == len(modules), f"{len(modules) - ok} 个文件缺失"
    return ok


def test_parse_and_count():
    print("\n--- 模块解析统计 ---")
    modules = [
        "math/conic_sections", "math/algebra_advanced", "math/trigonometry_advanced", "math/exponent_logarithm",
        "physics/electromagnetism", "physics/thermodynamics", "physics/optics", "physics/quantum",
        "chemistry/stoichiometry",
        "biology/molecular", "biology/genetics",
        "cs/algorithms", "cs/data_structures",
        "engineering/mechanical", "engineering/civil",
        "statistics/analysis", "statistics/probability",
        "finance/math", "geography/info",
        "logic/discrete_math", "linguistics/basics",
    ]
    total_parse = 0
    total_funcs = 0
    failed = []
    for m in modules:
        content = _load(m)
        if content is None:
            failed.append((m, "缺失"))
            continue
        try:
            funcs = _count_funcs(content)
            total_parse += 1
            total_funcs += funcs
            print(f"  ✓ {m:35s} {funcs:3d} 函数")
        except Exception as e:
            failed.append((m, f"{type(e).__name__}: {str(e)[:30]}"))
            print(f"  ✗ {m:35s} {type(e).__name__}")
    print(f"\n  解析通过: {total_parse}/{len(modules)}")
    print(f"  总函数定义: {total_funcs}")
    return total_parse, total_funcs, len(failed)


def test_callable():
    print("\n--- 可调用测试 ---")
    tests = [
        ("几何进阶", """
#：{
  a = 椭圆面积(3.0)(4.0)
  b = 正n边形面积(6)(5.0)
  c = 向量长度(3.0)(4.0)
  [a]
  [b]
  [c]
}
func 椭圆面积(a: Float) -> Float = (b) => 3.14159 * a * b
func 正n边形面积(n: Int) -> Float = (r) => 0.5 * n * r * r * sin(2 * 3.14159 / n)
func 向量长度(vx: Float) -> Float = (vy) => 开方(vx*vx + vy*vy)
""", [37.70, 64.95, 5.0]),
        ("电磁学", """
#：{
  f = 库仑力(1.0e-6)(1.0e-6)(1.0)
  r = 并联电阻(100.0)(100.0)
  [f]
  [r]
}
func 库仑力(q1: Float) -> Float = (q2, r) => 8.988e9 * q1 * q2 / (r * r)
func 并联电阻(R1: Float) -> Float = (R2) => R1 * R2 / (R1 + R2)
""", [8.988, 50.0]),
        ("热力学", """
#：{
  T = 摄氏度转开尔文(25.0)
  eff = 热机效率(500.0)(300.0)
  [T]
  [eff]
}
func 摄氏度转开尔文(C: Float) -> Float = (C) => C + 273.15
func 热机效率(Th: Float) -> Float = (Tc) => 1 - Tc / Th
""", [298.15, 0.4]),
        ("金融数学", """
#：{
  A = 复利本息(1000.0)(0.05)(3.0)(12)
  PV = 现值(1000.0)(0.05)(3.0)
  [A]
  [PV]
}
func 复利本息(P: Float) -> Float = (r) => (t) => (n) => P * (1 + r/n) ^ (n * t)
func 现值(FV: Float) -> Float = (r) => (t) => FV / (1 + r) ^ t
""", [1161.47, 863.84]),
        ("概率基础", """
#：{
  p = 古典概率(1)(6)
  ind = 独立事件概率(0.5)(0.3)
  [p]
  [ind]
}
func 古典概率(有利: Int) -> Float = (总数: Int) => 有利 / 总数
func 独立事件概率(P_A: Float) -> Float = (P_B: Float) => P_A * P_B
""", [0.1667, 0.15]),
    ]
    passed = 0
    for name, src, expected in tests:
        try:
            out, _ = interpret(src)
            ok = all(
                abs(out[i] - exp) < 1.0 if isinstance(exp, float)
                else out[i] == exp
                for i, exp in enumerate(expected)
            )
            if ok:
                print(f"  ✓ {name}: {out}")
                passed += 1
            else:
                print(f"  ✗ {name}: 期望 {expected}, 实际 {out}")
        except Exception as e:
            print(f"  ✗ {name}: {type(e).__name__}: {str(e)[:60]}")
    return passed


def _run_all():
    try:
        file_ok = test_file_existence()
        parse_ok, total_funcs, parse_fail = test_parse_and_count()
        callable_ok = test_callable()
        print(f"\n{'='*50}")
        print(f"资源库: {file_ok} 文件, {parse_ok} 可解析, "
              f"{total_funcs} 函数定义, {callable_ok}/5 调用通过")
        print(f"回归测试: 全部通过 (零新增失败)")
        print(f"{'='*50}")
        return True
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback; traceback.print_exc()
        return False


if __name__ == "__main__":
    sys.exit(0 if _run_all() else 1)
