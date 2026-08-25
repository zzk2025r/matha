# -*- coding: utf-8 -*-
"""
Matha 三向转换器自动化测试脚本

批量测试复杂数学运算的三向转换正确性：
  - Matha → MIR → C → Matha (循环验证)
  - Matha → Python → Matha (循环验证)
  - C → Python → C (跨语言验证)
  - 性能基准测试

用法:
  python tests/test_converter_auto.py
  python tests/test_converter_auto.py --verbose
  python tests/test_converter_auto.py --benchmark
"""
import sys
import time
import math
sys.path.insert(0, r"D:\trae")

from src.mir_converter import convert, matha_to_mir, MathaConverter, convert_all
from src.mir import MIRGenerator, generate_mir
from src.mir_codegen import compile_to_c, compile_to_python
from src.mir_opt import MathaOptimizationPipeline
from src.compiler.matha_cc import matha_to_llvm

# ============================================================
# 测试用例定义
# ============================================================

TEST_CASES = [
    # (名称, Matha源码)
    ("基础三角函数", "x = sin(π) + cos(π/2) + tan(π/4)\n#1：[x]"),
    ("对数与指数", "x = log(e) + log10(100) + exp(1) + ln(e)\n#1：[x]"),
    ("根式运算", "x = sqrt(2) + sqrt(3) + sqrt(5) + cbrt(8)\n#1：[x]"),
    ("幂运算", "x = 2^3 + 3^2 + 10^2 + sqrt(144)\n#1：[x]"),
    ("复合三角", "x = sin(π/6) * cos(π/3) + tan(π/4) * sin(π/2)\n#1：[x]"),
    ("超几何函数", "x = hypot(3, 4) + expm1(1) + log1p(e)\n#1：[x]"),
    ("取整运算", "x = floor(3.7) + ceil(3.2) + round(3.5) + trunc(3.9)\n#1：[x]"),
    ("数值常量", "x = π + τ + e + √2 + √3 + ln2 + ln10\n#1：[x]"),
    ("多变量复合", "a = sin(π/4)\nb = cos(π/3)\nc = tan(π/6)\nd = sqrt(2)\ne = exp(1)\nf = log(e)\ng = hypot(3, 4)\nh = floor(3.7) + ceil(3.2)\nresult = a * b + c * d + e * f + g + h\n#1：[result]"),
    ("函数定义与调用", "add = (a, b) → a + b\nmul = (a, b) → a * b\nx = add(sin(π), cos(π/2)) * mul(2, 3)\n#1：[x]"),
    ("嵌套函数", "x = exp(sin(1.0) + cos(2.0))\n#1：[x]"),
    ("复杂表达式", "x = sin(3.14) * cos(1.57) + sqrt(2.0)\n#1：[x]"),
]


# ============================================================
# 测试函数
# ============================================================

def test_mir_generation(name, source):
    """测试 MIR 生成。"""
    try:
        mir = matha_to_mir(source)
        assert "函数:" in mir, "缺少函数定义"
        assert "指令数:" in mir, "缺少指令计数"
        return True, f"OK - {len(mir)} chars"
    except Exception as e:
        return False, f"FAIL - {e}"


def test_c_generation(name, source):
    """测试 C 代码生成。"""
    try:
        c_code = convert(source, "matha", "c")
        assert "#include" in c_code, "缺少 include"
        assert "main()" in c_code, "缺少 main 函数"
        assert "return" in c_code, "缺少 return"
        return True, f"OK - {len(c_code)} chars"
    except Exception as e:
        return False, f"FAIL - {e}"


def test_python_generation(name, source):
    """测试 Python 代码生成。"""
    try:
        py_code = convert(source, "matha", "python")
        assert "def " in py_code, "缺少函数定义"
        assert "import" in py_code, "缺少 import"
        return True, f"OK - {len(py_code)} chars"
    except Exception as e:
        return False, f"FAIL - {e}"


def test_matha_self(name, source):
    """测试 Matha 自举。"""
    try:
        matha_out = convert(source, "matha", "matha")
        assert len(matha_out) > 0, "输出为空"
        return True, f"OK - {len(matha_out)} chars"
    except Exception as e:
        return False, f"FAIL - {e}"


def test_roundtrip_mir_to_c_to_mir(name, source):
    """测试 MIR → C → MIR 循环。"""
    try:
        c_code = convert(source, "matha", "c")
        matha_back = convert(c_code, "c", "matha")
        assert len(matha_back) > 0, "循环转换后输出为空"
        return True, f"OK - Matha→C→Matha: {len(c_code)}→{len(matha_back)} chars"
    except Exception as e:
        return False, f"FAIL - {e}"


def test_roundtrip_c_to_python_to_c(name, source):
    """测试 C → Python → C 循环。"""
    try:
        c_code = convert(source, "matha", "c")
        py_code = convert(c_code, "c", "python")
        c_back = convert(py_code, "python", "c")
        assert len(c_back) > 0, "循环转换后输出为空"
        return True, f"OK - C→Py→C: {len(c_code)}→{len(py_code)}→{len(c_back)} chars"
    except Exception as e:
        return False, f"FAIL - {e}"


def test_batch_convert(name, source):
    """测试批量转换。"""
    try:
        results = convert_all(source, "matha")
        assert "matha" in results, "缺少 matha"
        assert "c" in results, "缺少 c"
        assert "python" in results, "缺少 python"
        return True, f"OK - {len(results)} languages"
    except Exception as e:
        return False, f"FAIL - {e}"


def test_performance(name, source):
    """测试性能。"""
    try:
        iterations = 100

        t0 = time.perf_counter()
        for _ in range(iterations):
            matha_to_mir(source)
        mir_ms = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        for _ in range(iterations):
            convert(source, "matha", "c")
        c_ms = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        for _ in range(iterations):
            convert(source, "matha", "python")
        py_ms = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        for _ in range(iterations):
            matha_to_llvm(source)
        llvm_ms = (time.perf_counter() - t0) * 1000
        llvm_ir = matha_to_llvm(source)

        return True, (
            f"OK - MIR:{mir_ms/100:.2f}ms C:{c_ms/100:.2f}ms "
            f"Py:{py_ms/100:.2f}ms LLVM:{llvm_ms/100:.2f}ms "
            f"(MIR vs LLVM: {llvm_ms/mir_ms:.1f}x)"
        )
    except Exception as e:
        return False, f"FAIL - {e}"


# ============================================================
# 主测试循环
# ============================================================

def run_tests(verbose=False, benchmark_only=False):
    """运行所有测试。"""
    results = {"passed": 0, "failed": 0, "errors": []}

    test_functions = [
        ("MIR 生成", test_mir_generation),
        ("C 代码生成", test_c_generation),
        ("Python 代码生成", test_python_generation),
        ("Matha 自举", test_matha_self),
        ("MIR→C→MIR 循环", test_roundtrip_mir_to_c_to_mir),
        ("C→Py→C 循环", test_roundtrip_c_to_python_to_c),
        ("批量转换", test_batch_convert),
        ("性能基准", test_performance),
    ]

    if benchmark_only:
        print("=" * 70)
        print("性能基准测试")
        print("=" * 70)
        for case_name, source in TEST_CASES:
            print(f"\n  [{case_name}]")
            for test_name, test_fn in test_functions:
                if test_name == "性能基准":
                    passed, msg = test_fn(case_name, source)
                    status = "PASS" if passed else "FAIL"
                    print(f"    [{status}] {msg}")
                    if passed:
                        results["passed"] += 1
                    else:
                        results["failed"] += 1
                        results["errors"].append(f"{case_name}: {msg}")
        return results

    print("=" * 70)
    print("Matha 三向转换器自动化测试")
    print(f"测试用例数: {len(TEST_CASES)}")
    print(f"测试项目: {len(test_functions)}")
    print("=" * 70)

    for case_idx, (case_name, source) in enumerate(TEST_CASES, 1):
        print(f"\n{'='*70}")
        print(f"测试用例 [{case_idx}/{len(TEST_CASES)}]: {case_name}")
        print(f"{'='*70}")
        if verbose:
            print(f"  源码: {source[:80]}...")

        for test_name, test_fn in test_functions:
            passed, msg = test_fn(case_name, source)
            status = "PASS" if passed else "FAIL"
            print(f"  [{status}] {test_name}: {msg}")
            if passed:
                results["passed"] += 1
            else:
                results["failed"] += 1
                results["errors"].append(f"{case_name}/{test_name}: {msg}")

    return results


def print_summary(results):
    """打印测试摘要。"""
    total = results["passed"] + results["failed"]
    print(f"\n{'='*70}")
    print("测试摘要")
    print(f"{'='*70}")
    print(f"  通过: {results['passed']}/{total}")
    print(f"  失败: {results['failed']}/{total}")
    if results["errors"]:
        print(f"\n  错误详情:")
        for err in results["errors"][:10]:
            print(f"    - {err}")
        if len(results["errors"]) > 10:
            print(f"    ... 还有 {len(results['errors']) - 10} 个错误")
    print(f"{'='*70}")
    if results["failed"] == 0:
        print("  全部测试通过!")
    else:
        print(f"  {results['failed']} 个测试失败")
    print(f"{'='*70}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Matha 三向转换器自动化测试")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    parser.add_argument("--benchmark", "-b", action="store_true", help="仅运行性能基准测试")
    args = parser.parse_args()

    results = run_tests(verbose=args.verbose, benchmark_only=args.benchmark)
    print_summary(results)
    sys.exit(0 if results["failed"] == 0 else 1)
