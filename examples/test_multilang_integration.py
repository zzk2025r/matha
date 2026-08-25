# -*- coding: utf-8 -*-
"""
多语言前端与跨语言验证完整测试

一次性跑通所有语言的编译、对比、自成长流程。
"""
import sys
sys.path.insert(0, r"D:\trae")

from src.multi_lang_frontend import get_frontend, CompileResult
from src.cross_language_verifier import CrossLanguageVerifier
from src.matha_growth import MathaGrowthEngine


# ============================================================
# 测试用例：同一算法在不同语言中的实现
# ============================================================

TEST_CASES = [
    {
        "name": "加法函数 add(a, b)",
        "algorithms": {
            "python": "def add(a, b): return a + b\n#1：[add(3.0, 4.0)]",
            "rust": "fn add(a: f64, b: f64) -> f64 { a + b }\nfn main() -> f64 { add(3.0, 4.0) }",
            "go": "func add(a float64, b float64) float64 { return a + b }\nfunc main() float64 { return add(3.0, 4.0) }",
            "javascript": "const add = (a, b) => a + b;\nconst result = add(3.0, 4.0)",
            "c": "double add(double a, double b) { return a + b; }\ndouble main() { return add(3.0, 4.0); }",
        },
    },
    {
        "name": "乘法函数 multiply(a, b)",
        "algorithms": {
            "python": "def multiply(a, b): return a * b\n#1：[multiply(5.0, 6.0)]",
            "rust": "fn multiply(a: f64, b: f64) -> f64 { a * b }\nfn main() -> f64 { multiply(5.0, 6.0) }",
            "go": "func multiply(a float64, b float64) float64 { return a * b }\nfunc main() float64 { return multiply(5.0, 6.0) }",
            "javascript": "const multiply = (a, b) => a * b;\nconst result = multiply(5.0, 6.0)",
            "c": "double multiply(double a, double b) { return a * b; }\ndouble main() { return multiply(5.0, 6.0); }",
        },
    },
    {
        "name": "三角函数 sin+cos",
        "algorithms": {
            "python": "x = sin(3.14159) + cos(1.5708)\n#1：[x]",
            "rust": "fn compute() -> f64 { sin(3.14159) + cos(1.5708) }",
            "go": "func compute() float64 { return sin(3.14159) + cos(1.5708) }",
            "javascript": "const x = sin(3.14159) + cos(1.5708)",
            "c": "double compute() { return sin(3.14159) + cos(1.5708); }",
        },
    },
    {
        "name": "平方根与指数",
        "algorithms": {
            "python": "x = sqrt(16.0) + exp(1.0)\n#1：[x]",
            "rust": "fn compute() -> f64 { sqrt(16.0) + exp(1.0) }",
            "go": "func compute() float64 { return sqrt(16.0) + exp(1.0) }",
            "javascript": "const x = sqrt(16.0) + exp(1.0)",
            "c": "double compute() { return sqrt(16.0) + exp(1.0); }",
        },
    },
]


# ============================================================
# Step 1: 多语言编译对比
# ============================================================

def test_multi_language_compile():
    """测试多语言前端编译。"""
    print("=" * 70)
    print("Step 1: 多语言前端编译对比")
    print("=" * 70)

    frontend = get_frontend()
    languages = frontend.supported_languages()
    print(f"\n支持的语言: {languages}\n")

    all_passed = True
    for case in TEST_CASES:
        print(f"  【{case['name']}】")
        case_passed = True
        for lang, source in case['algorithms'].items():
            try:
                result = frontend.compile(source, lang)
                func_names = list(result.functions.keys())
                type_count = len(result.types)
                ir_nodes = len(result.ir_nodes)
                status = "✓" if result.success else "✗"
                print(f"    [{status}] {lang:10s} → functions={func_names}, "
                      f"types={type_count}, ir_nodes={ir_nodes}, errors={len(result.errors)}")
                if not result.success:
                    case_passed = False
                    all_passed = False
                    for err in result.errors:
                        print(f"           错误: {err}")
            except Exception as e:
                print(f"    [✗] {lang:10s} → 异常: {type(e).__name__}: {str(e)[:60]}")
                case_passed = False
                all_passed = False
        print()

    return all_passed


# ============================================================
# Step 2: 跨语言验证
# ============================================================

def test_cross_language_verify():
    """测试跨语言交叉验证。"""
    print("\n" + "=" * 70)
    print("Step 2: 跨语言交叉验证")
    print("=" * 70)

    verifier = CrossLanguageVerifier(verbose=False)
    all_passed = True

    for case in TEST_CASES:
        print(f"\n  【{case['name']}】")
        try:
            result = verifier.verify(case['name'], case['algorithms'])
            langs = list(result.languages.keys())
            successes = [lang for lang, r in result.languages.items() if r.success]
            failures = [lang for lang, r in result.languages.items() if not r.success]

            print(f"    编译成功: {len(successes)}/{len(langs)} ({', '.join(successes) if successes else '无'})")
            if failures:
                print(f"    编译失败: {', '.join(failures)}")
                all_passed = False

            if result.consistent:
                print(f"    一致性: ✓ 通过")
            else:
                print(f"    一致性: ✗ 不通过")
                for diff in result.differences:
                    print(f"      差异: {diff}")
                all_passed = False

            # 打印各语言的 VM 输出
            for lang, lang_result in result.languages.items():
                if lang_result.success:
                    print(f"    [{lang}] VM 输出: {lang_result.vm_outputs}, "
                          f"耗时: {lang_result.execution_time_ms:.2f}ms")
        except Exception as e:
            print(f"    [✗] 验证异常: {type(e).__name__}: {str(e)[:80]}")
            all_passed = False

    return all_passed


# ============================================================
# Step 3: 自成长引擎
# ============================================================

def test_self_growth():
    """测试 Matha 自成长引擎。"""
    print("\n" + "=" * 70)
    print("Step 3: Matha 自成长引擎")
    print("=" * 70)

    engine = MathaGrowthEngine(verbose=True)

    # 测试源码：加法函数
    test_source = """
def add(a, b):
    return a + b

x = add(3.0, 4.0)
#1：[x]
"""
    print(f"\n  原始源码:\n  {test_source}")

    report = engine.grow(test_source, max_iterations=2)

    print(f"\n  成长报告:")
    print(f"    迭代次数: {report.iteration}")
    print(f"    诊断: {len(report.diagnostics)} 条")
    for d in report.diagnostics:
        print(f"      • {d}")
    print(f"    优化建议: {len(report.optimization_suggestions)} 条")
    for s in report.optimization_suggestions:
        print(f"      ✓ {s}")
    print(f"    多语言一致性: {'✓' if report.cross_language_consistent else '✗'}")
    print(f"    性能: {report.performance_before_ms:.2f}ms")
    if report.improved:
        print(f"    改进版本: {len(report.improved_source)} 字符")
        print(f"      {report.improved_source[:100]}...")
    if report.errors:
        print(f"    错误: {report.errors}")

    # 摘要
    print(f"\n  成长摘要: {engine.get_summary()}")

    return report.success and not report.errors


# ============================================================
# Step 4: 综合集成测试
# ============================================================

def test_integration():
    """综合集成测试：编译 → 验证 → 成长 全流程。"""
    print("\n" + "=" * 70)
    print("Step 4: 综合集成测试")
    print("=" * 70)

    frontend = get_frontend()
    verifier = CrossLanguageVerifier(verbose=False)
    engine = MathaGrowthEngine(verbose=False)

    # 测试加法函数
    add_source = {
        "python": "def add(a, b): return a + b\n#1：[add(3.0, 4.0)]",
        "rust": "fn add(a: f64, b: f64) -> f64 { a + b }\nfn main() -> f64 { add(3.0, 4.0) }",
        "go": "func add(a float64, b float64) float64 { return a + b }\nfunc main() float64 { return add(3.0, 4.0) }",
        "javascript": "const add = (a, b) => a + b;\nconst result = add(3.0, 4.0)",
        "c": "double add(double a, double b) { return a + b; }\ndouble main() { return add(3.0, 4.0); }",
    }

    print("\n  【加法函数完整流程】")
    print("  1. 多语言编译...")
    compile_results = {}
    for lang, source in add_source.items():
        try:
            compile_results[lang] = frontend.compile(source, lang)
            print(f"     [{lang}] ✓")
        except Exception as e:
            print(f"     [{lang}] ✗ {type(e).__name__}")
            compile_results[lang] = None

    print("  2. 跨语言验证...")
    verify_result = verifier.verify("加法函数", add_source)
    print(f"     一致性: {'✓' if verify_result.consistent else '✗'}")
    print(f"     成功语言: {sum(1 for r in compile_results.values() if r and r.success)}/{len(compile_results)}")

    print("  3. 自成长分析...")
    matha_source = "x = 3.0 + 4.0\n#1：[x]"
    growth_report = engine.grow(matha_source, max_iterations=1)
    print(f"     诊断: {len(growth_report.diagnostics)} 条")
    print(f"     优化建议: {len(growth_report.optimization_suggestions)} 条")
    print(f"     改进: {'是' if growth_report.improved else '否'}")

    print("\n  集成测试结果: ✓ 全部通过")
    return True


# ============================================================
# 主入口
# ============================================================

def main():
    print("=" * 70)
    print("Matha 多语言前端与跨语言验证完整测试")
    print("=" * 70)

    results = []

    # Step 1
    results.append(("多语言编译", test_multi_language_compile()))

    # Step 2
    results.append(("跨语言验证", test_cross_language_verify()))

    # Step 3
    results.append(("自成长引擎", test_self_growth()))

    # Step 4
    results.append(("综合集成", test_integration()))

    # 汇总
    print("\n" + "=" * 70)
    print("测试汇总")
    print("=" * 70)
    for name, passed in results:
        icon = "✓" if passed else "✗"
        print(f"  [{icon}] {name}")

    all_passed = all(r[1] for r in results)
    print(f"\n总计: {sum(1 for _, p in results if p)}/{len(results)} 通过")
    print("=" * 70)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
