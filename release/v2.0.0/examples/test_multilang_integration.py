# -*- coding: utf-8 -*-
"""
多语言前端与跨语言验证完整测试
"""
import sys
sys.path.insert(0, r"D:\trae")

from src.multi_lang_frontend import get_frontend
from src.cross_language_verifier import CrossLanguageVerifier
from src.matha_growth import MathaGrowthEngine


TEST_CASES = [
    {"name": "加法函数", "algos": {
        "python": "def add(a, b): return a + b\n#1：[add(3.0, 4.0)]",
        "rust": "fn add(a: f64, b: f64) -> f64 { a + b }\nfn main() -> f64 { add(3.0, 4.0) }",
        "go": "func add(a float64, b float64) float64 { return a + b }\nfunc main() float64 { return add(3.0, 4.0) }",
        "javascript": "const add = (a, b) => a + b;\nconst result = add(3.0, 4.0)",
        "c": "double add(double a, double b) { return a + b; }\ndouble main() { return add(3.0, 4.0); }",
    }},
    {"name": "三角函数", "algos": {
        "python": "x = sin(3.14159) + cos(1.5708)\n#1：[x]",
        "rust": "fn compute() -> f64 { sin(3.14159) + cos(1.5708) }",
        "go": "func compute() float64 { return sin(3.14159) + cos(1.5708) }",
        "javascript": "const x = sin(3.14159) + cos(1.5708)",
        "c": "double compute() { return sin(3.14159) + cos(1.5708); }",
    }},
]


def main():
    print("=" * 60)
    print("多语言前端编译 + 跨语言验证 + 自成长测试")
    print("=" * 60)

    frontend = get_frontend()
    verifier = CrossLanguageVerifier(verbose=False)
    engine = MathaGrowthEngine(verbose=False)

    for case in TEST_CASES:
        name = case["name"]
        algos = case["algos"]
        source = algos["python"]
        print(f"\n【{name}】")

        # 编译
        results = {}
        for lang, src in algos.items():
            try:
                r = frontend.compile(src, lang)
                results[lang] = r
                print(f"  [{lang}] {'✓' if r.success else '✗'} funcs={list(r.functions.keys())}, errors={len(r.errors)}")
            except Exception as e:
                results[lang] = None
                print(f"  [{lang}] ✗ {e}")

        # 验证
        verify = verifier.verify(name, algos)
        print(f"  一致性: {'✓' if verify.consistent else '✗'}")

        # 成长
        report = engine.grow(source, max_iterations=2)
        print(f"  优化: {report.optimizations_applied if report.optimizations_applied else '无'}")
        if report.improved_source:
            print(f"  改进: {report.improved_source[:80]}...")

    print(f"\n{'='*60}")
    print("全部测试完成！")


if __name__ == "__main__":
    main()
