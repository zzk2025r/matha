# -*- coding: utf-8 -*-
"""
复杂嵌套函数测试用例 — 验证多语言前端和自成长引擎
"""
import sys
sys.path.insert(0, r"D:\trae")

from src.multi_lang_frontend import get_frontend
from src.cross_language_verifier import CrossLanguageVerifier
from src.matha_growth import MathaGrowthEngine


# ============================================================
# 复杂嵌套函数测试用例
# ============================================================

TEST_CASES = [
    {
        "name": "简单加法",
        "source": "x = 3.0 + 4.0\n#1：[x]",
    },
    {
        "name": "三角函数",
        "source": "x = sin(3.14159) + cos(1.5708)\n#1：[x]",
    },
    {
        "name": "多层嵌套函数调用",
        "source": """def add(a, b):
    return a + b

def multiply(x, y):
    return x * y

def compute():
    return multiply(add(3.0, 4.0), 2.0)

result = compute()
#1：[result]""",
    },
    {
        "name": "死代码 + 常量传播",
        "source": """unused = 999.0
a = 10.0
b = 20.0
c = a + b
result = c * 2.0
#1：[result]""",
    },
    {
        "name": "常量折叠 + 函数内联",
        "source": """def square(x):
    return x * x

def cube(x):
    return square(x) * x

result = cube(3.0)
#1：[result]""",
    },
    {
        "name": "混合运算",
        "source": """def factorial(n):
    if n <= 1:
        return 1.0
    return n * factorial(n - 1)

result = factorial(5.0)
#1：[result]""",
    },
]


def test_all():
    print("=" * 70)
    print("复杂嵌套函数测试 — 多语言前端 + 自成长引擎")
    print("=" * 70)

    frontend = get_frontend()
    verifier = CrossLanguageVerifier(verbose=False)
    engine = MathaGrowthEngine(verbose=True)

    for case in TEST_CASES:
        name = case["name"]
        source = case["source"]
        print(f"\n{'='*60}")
        print(f"测试: {name}")
        print(f"{'='*60}")
        print(f"原始源码 ({len(source)} 字符):")
        print(source)

        # Step 1: 多语言编译
        print(f"\n  [1] 多语言编译:")
        compile_results = {}
        for lang in frontend.supported_languages():
            try:
                result = frontend.compile(source, lang)
                func_names = list(result.functions.keys())
                ir_nodes = len(result.ir_nodes)
                status = "✓" if result.success else "✗"
                compile_results[lang] = result
                print(f"      [{status}] {lang:12s} → functions={func_names}, "
                      f"ir_nodes={ir_nodes}, errors={len(result.errors)}")
            except Exception as e:
                compile_results[lang] = None
                print(f"      [✗] {lang:12s} → {type(e).__name__}: {str(e)[:50]}")

        # Step 2: 跨语言验证
        print(f"\n  [2] 跨语言验证:")
        try:
            verify_result = verifier.verify(name, {
                lang: src for lang, src in {
                    "python": source,
                    "rust": source,
                    "go": source,
                    "javascript": source,
                    "c": source,
                }.items() if compile_results.get(lang)
            })
            passed = sum(1 for r in compile_results.values() if r and r.success)
            total = len(compile_results)
            print(f"      编译成功: {passed}/{total}")
            print(f"      一致性: {'✓ 通过' if verify_result.consistent else '✗ 不通过'}")
        except Exception as e:
            print(f"      [✗] 验证异常: {type(e).__name__}: {e}")

        # Step 3: 自成长分析
        print(f"\n  [3] 自成长分析:")
        report = engine.grow(source, max_iterations=2)
        print(f"      诊断: {len(report.diagnostics)} 条")
        for d in report.diagnostics:
            print(f"        • {d}")
        print(f"      优化建议: {len(report.optimization_suggestions)} 条")
        for s in report.optimization_suggestions:
            print(f"        ✓ {s}")
        print(f"      多语言一致性: {'✓' if report.cross_language_consistent else '✗'}")
        print(f"      错误: {report.errors if report.errors else '无'}")
        if report.improved:
            print(f"      改进版本 ({len(report.improved_source)} 字符):")
            print(f"        {report.improved_source[:200]}...")
        else:
            print(f"      改进: 无")
        print(f"      性能: {report.performance_before_ms:.2f}ms → {report.performance_after_ms:.2f}ms")

    # 汇总
    print(f"\n{'='*70}")
    print("测试汇总")
    print(f"{'='*70}")
    print(f"  测试用例数: {len(TEST_CASES)}")
    print(f"  支持语言: {frontend.supported_languages()}")
    print(f"\n  全部测试完成！")


if __name__ == "__main__":
    test_all()
