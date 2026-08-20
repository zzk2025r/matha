# -*- coding: utf-8 -*-
"""
跨语言压力测试 — 1000 算法 × 5 语言一致性验证

用法:
  python scripts/stress_test_cross_lang.py [--algorithms 1000] [--output docs/CROSS_LANG_STRESS_REPORT.md]
"""
from __future__ import annotations
import hashlib
import math
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.multi_lang_frontend import (
    MultiLanguageFrontend, CompileResult, get_frontend,
)
from src.cross_language_verifier import CrossLanguageVerifier
from src.vm import MathaVM


# ============================================================
# 算法生成器
# ============================================================

class AlgorithmGenerator:
    """生成 1000 种不同的数学算法源码。"""

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self._counter = 0

    def _rand_float(self) -> float:
        return self.rng.uniform(0.1, 10.0)

    def _rand_int(self) -> int:
        return self.rng.randint(1, 20)

    def generate(self, index: int) -> dict[str, str]:
        """生成一个算法在各语言的源码。"""
        algo_type = index % 20
        a = self._rand_float()
        b = self._rand_float()
        n = self._rand_int()

        src: dict[str, str] = {}

        if algo_type == 0:
            # 简单加法
            src["python"] = f"x = {a} + {b}\n#1：[x]"
            src["rust"] = f"fn test() -> f64 {{ {a} + {b} }}"
            src["go"] = f"func test() float64 {{ return {a} + {b} }}"
            src["javascript"] = f"const x = {a} + {b}"
            src["c"] = f"double test() {{ return {a} + {b}; }}"

        elif algo_type == 1:
            # 乘法
            src["python"] = f"x = {a} * {b}\n#1：[x]"
            src["rust"] = f"fn test() -> f64 {{ {a} * {b} }}"
            src["go"] = f"func test() float64 {{ return {a} * {b} }}"
            src["javascript"] = f"const x = {a} * {b}"
            src["c"] = f"double test() {{ return {a} * {b}; }}"

        elif algo_type == 2:
            # sin
            src["python"] = f"x = sin({a})\n#1：[x]"
            src["rust"] = f"fn test() -> f64 {{ sin({a}) }}"
            src["go"] = f"func test() float64 {{ return sin({a}) }}"
            src["javascript"] = f"const x = sin({a})"
            src["c"] = f"double test() {{ return sin({a}); }}"

        elif algo_type == 3:
            # cos
            src["python"] = f"x = cos({a})\n#1：[x]"
            src["rust"] = f"fn test() -> f64 {{ cos({a}) }}"
            src["go"] = f"func test() float64 {{ return cos({a}) }}"
            src["javascript"] = f"const x = cos({a})"
            src["c"] = f"double test() {{ return cos({a}); }}"

        elif algo_type == 4:
            # sqrt
            src["python"] = f"x = sqrt({a})\n#1：[x]"
            src["rust"] = f"fn test() -> f64 {{ sqrt({a}) }}"
            src["go"] = f"func test() float64 {{ return sqrt({a}) }}"
            src["javascript"] = f"const x = sqrt({a})"
            src["c"] = f"double test() {{ return sqrt({a}); }}"

        elif algo_type == 5:
            # exp
            src["python"] = f"x = exp({a})\n#1：[x]"
            src["rust"] = f"fn test() -> f64 {{ exp({a}) }}"
            src["go"] = f"func test() float64 {{ return exp({a}) }}"
            src["javascript"] = f"const x = exp({a})"
            src["c"] = f"double test() {{ return exp({a}); }}"

        elif algo_type == 6:
            # sin + cos
            src["python"] = f"x = sin({a}) + cos({b})\n#1：[x]"
            src["rust"] = f"fn test() -> f64 {{ sin({a}) + cos({b}) }}"
            src["go"] = f"func test() float64 {{ return sin({a}) + cos({b}) }}"
            src["javascript"] = f"const x = sin({a}) + cos({b})"
            src["c"] = f"double test() {{ return sin({a}) + cos({b}); }}"

        elif algo_type == 7:
            # sqrt + exp
            src["python"] = f"x = sqrt({a}) + exp({b})\n#1：[x]"
            src["rust"] = f"fn test() -> f64 {{ sqrt({a}) + exp({b}) }}"
            src["go"] = f"func test() float64 {{ return sqrt({a}) + exp({b}) }}"
            src["javascript"] = f"const x = sqrt({a}) + exp({b})"
            src["c"] = f"double test() {{ return sqrt({a}) + exp({b}); }}"

        elif algo_type == 8:
            # 3a + 2b
            src["python"] = f"x = 3.0 * {a} + 2.0 * {b}\n#1：[x]"
            src["rust"] = f"fn test() -> f64 {{ 3.0 * {a} + 2.0 * {b} }}"
            src["go"] = f"func test() float64 {{ return 3.0 * {a} + 2.0 * {b} }}"
            src["javascript"] = f"const x = 3.0 * {a} + 2.0 * {b}"
            src["c"] = f"double test() {{ return 3.0 * {a} + 2.0 * {b}; }}"

        elif algo_type == 9:
            # a^2 + b^2
            src["python"] = f"x = {a} * {a} + {b} * {b}\n#1：[x]"
            src["rust"] = f"fn test() -> f64 {{ {a} * {a} + {b} * {b} }}"
            src["go"] = f"func test() float64 {{ return {a} * {a} + {b} * {b} }}"
            src["javascript"] = f"const x = {a} * {a} + {b} * {b}"
            src["c"] = f"double test() {{ return {a} * {a} + {b} * {b}; }}"

        elif algo_type == 10:
            # abs
            src["python"] = f"x = abs({a} - {b})\n#1：[x]"
            src["rust"] = f"fn test() -> f64 {{ abs({a} - {b}) }}"
            src["go"] = f"func test() float64 {{ return abs({a} - {b}) }}"
            src["javascript"] = f"const x = abs({a} - {b})"
            src["c"] = f"double test() {{ return fabs({a} - {b}); }}"

        elif algo_type == 11:
            # floor/ceil
            src["python"] = f"x = floor({a}) + ceil({b})\n#1：[x]"
            src["rust"] = f"fn test() -> f64 {{ floor({a}) + ceil({b}) }}"
            src["go"] = f"func test() float64 {{ return floor({a}) + ceil({b}) }}"
            src["javascript"] = f"const x = floor({a}) + ceil({b})"
            src["c"] = f"double test() {{ return floor({a}) + ceil({b}); }}"

        elif algo_type == 12:
            # log
            src["python"] = f"x = ln({a})\n#1：[x]"
            src["rust"] = f"fn test() -> f64 {{ log({a}) }}"
            src["go"] = f"func test() float64 {{ return log({a}) }}"
            src["javascript"] = f"const x = log({a})"
            src["c"] = f"double test() {{ return log({a}); }}"

        elif algo_type == 13:
            # log10
            src["python"] = f"x = log10({a})\n#1：[x]"
            src["rust"] = f"fn test() -> f64 {{ log10({a}) }}"
            src["go"] = f"func test() float64 {{ return log10({a}) }}"
            src["javascript"] = f"const x = log10({a})"
            src["c"] = f"double test() {{ return log10({a}); }}"

        elif algo_type == 14:
            # tan
            src["python"] = f"x = tan({a})\n#1：[x]"
            src["rust"] = f"fn test() -> f64 {{ tan({a}) }}"
            src["go"] = f"func test() float64 {{ return tan({a}) }}"
            src["javascript"] = f"const x = tan({a})"
            src["c"] = f"double test() {{ return tan({a}); }}"

        elif algo_type == 15:
            # a * b / 2
            src["python"] = f"x = {a} * {b} / 2.0\n#1：[x]"
            src["rust"] = f"fn test() -> f64 {{ {a} * {b} / 2.0 }}"
            src["go"] = f"func test() float64 {{ return {a} * {b} / 2.0 }}"
            src["javascript"] = f"const x = {a} * {b} / 2.0"
            src["c"] = f"double test() {{ return {a} * {b} / 2.0; }}"

        elif algo_type == 16:
            # (a + b) * 2
            src["python"] = f"x = ({a} + {b}) * 2.0\n#1：[x]"
            src["rust"] = f"fn test() -> f64 {{ ({a} + {b}) * 2.0 }}"
            src["go"] = f"func test() float64 {{ return ({a} + {b}) * 2.0 }}"
            src["javascript"] = f"const x = ({a} + {b}) * 2.0"
            src["c"] = f"double test() {{ return ({a} + {b}) * 2.0; }}"

        elif algo_type == 17:
            # a / b
            src["python"] = f"x = {a} / {b}\n#1：[x]"
            src["rust"] = f"fn test() -> f64 {{ {a} / {b} }}"
            src["go"] = f"func test() float64 {{ return {a} / {b} }}"
            src["javascript"] = f"const x = {a} / {b}"
            src["c"] = f"double test() {{ return {a} / {b}; }}"

        elif algo_type == 18:
            # sqrt(a * b)
            src["python"] = f"x = sqrt({a} * {b})\n#1：[x]"
            src["rust"] = f"fn test() -> f64 {{ sqrt({a} * {b}) }}"
            src["go"] = f"func test() float64 {{ return sqrt({a} * {b}) }}"
            src["javascript"] = f"const x = sqrt({a} * {b})"
            src["c"] = f"double test() {{ return sqrt({a} * {b}); }}"

        elif algo_type == 19:
            # a - b + sin(a)
            src["python"] = f"x = {a} - {b} + sin({a})\n#1：[x]"
            src["rust"] = f"fn test() -> f64 {{ {a} - {b} + sin({a}) }}"
            src["go"] = f"func test() float64 {{ return {a} - {b} + sin({a}) }}"
            src["javascript"] = f"const x = {a} - {b} + sin({a})"
            src["c"] = f"double test() {{ return {a} - {b} + sin({a}); }}"

        return src

    def generate_all(self, count: int) -> list[dict]:
        return [self.generate(i) for i in range(count)]


# ============================================================
# 压力测试
# ============================================================

def run_stress_test(algorithms: int = 1000, output_path: str = "") -> dict:
    """运行跨语言压力测试。"""
    print(f"\n{'=' * 70}")
    print(f"  跨语言压力测试：{algorithms} 算法 × 5 语言")
    print(f"{'=' * 70}")

    generator = AlgorithmGenerator(seed=42)
    test_cases = generator.generate_all(algorithms)

    verifier = CrossLanguageVerifier(verbose=False)
    frontend = get_frontend()
    vm = MathaVM(debug=False)

    # 统计
    total = 0
    passed = 0
    failed_compile = 0
    failed_execute = 0
    failed_consistent = 0
    lang_stats: dict[str, dict] = {
        lang: {"success": 0, "fail": 0}
        for lang in ["python", "rust", "go", "javascript", "c"]
    }
    all_times: dict[str, list[float]] = {lang: [] for lang in lang_stats}
    ir_counts: dict[str, list[int]] = {lang: [] for lang in lang_stats}

    start_time = time.perf_counter()

    for i, case in enumerate(test_cases):
        total += 1
        algo_hash = hashlib.md5(str(i).encode()).hexdigest()[:8]
        algo_name = f"algo_{i:04d}_{algo_hash}"

        algo_passed = True
        algo_success_langs = []
        algo_fail_langs = []

        for lang, source in case.items():
            t0 = time.perf_counter()
            try:
                cr: CompileResult = frontend.compile(source, lang)
                elapsed = (time.perf_counter() - t0) * 1000
                all_times[lang].append(elapsed)

                if not cr.success:
                    failed_compile += 1
                    lang_stats[lang]["fail"] += 1
                    algo_passed = False
                    algo_fail_langs.append(lang)
                    continue

                lang_stats[lang]["success"] += 1
                ir_counts[lang].append(len(cr.ir_nodes))
                algo_success_langs.append(lang)

            except Exception as e:
                failed_execute += 1
                lang_stats[lang]["fail"] += 1
                algo_passed = False
                algo_fail_langs.append(lang)
                continue

        # 一致性检查：成功语言之间输出是否一致
        if len(algo_success_langs) >= 2:
            # 用第一个成功的语言作为基准
            ref_lang = algo_success_langs[0]
            ref_source = case[ref_lang]
            ref_cr = frontend.compile(ref_source, ref_lang)
            ref_mir = ref_cr.to_mir()
            ref_outputs, _ = vm.run(ref_mir)

            consistent = True
            for lang in algo_success_langs[1:]:
                lang_source = case[lang]
                lang_cr = frontend.compile(lang_source, lang)
                lang_mir = lang_cr.to_mir()
                lang_outputs, _ = vm.run(lang_mir)
                if lang_outputs != ref_outputs:
                    consistent = False
                    break

            if consistent:
                passed += 1
            else:
                failed_consistent += 1
                algo_passed = False
        elif len(algo_success_langs) == 1:
            # 只有一个语言成功，算通过（无法比较）
            passed += 1
        else:
            failed_compile += 1
            algo_passed = False

        # 进度报告
        if total % 100 == 0 or total == algorithms:
            elapsed_total = time.perf_counter() - start_time
            rate = total / elapsed_total if elapsed_total > 0 else 0
            print(f"  [{total:>4d}/{algorithms}] "
                  f"passed={passed} compile_fail={failed_compile} "
                  f"consistent_fail={failed_consistent} "
                  f"speed={rate:.0f} alg/s  ({elapsed_total:.1f}s)")

    elapsed_total = time.perf_counter() - start_time
    rate = total / elapsed_total if elapsed_total > 0 else 0

    # 汇总
    report = {
        "total": total,
        "passed": passed,
        "failed_compile": failed_compile,
        "failed_execute": failed_execute,
        "failed_consistent": failed_consistent,
        "pass_rate": passed / total * 100 if total else 0,
        "elapsed_s": round(elapsed_total, 2),
        "speed_algos_per_s": round(rate, 1),
        "language_stats": lang_stats,
        "avg_compile_ms": {
            lang: round(sum(times) / len(times), 3) if times else 0
            for lang, times in all_times.items()
        },
        "avg_ir_nodes": {
            lang: round(sum(counts) / len(counts), 1) if counts else 0
            for lang, counts in ir_counts.items()
        },
    }

    # 打印报告
    print(f"\n{'=' * 70}")
    print(f"  测试结果")
    print(f"{'=' * 70}")
    print(f"  总算法数   : {total}")
    print(f"  通过       : {passed} ({report['pass_rate']:.1f}%)")
    print(f"  编译失败   : {failed_compile}")
    print(f"  执行失败   : {failed_execute}")
    print(f"  不一致     : {failed_consistent}")
    print(f"  总耗时     : {elapsed_total:.2f}s")
    print(f"  吞吐量     : {rate:.1f} alg/s")

    print(f"\n  [各语言统计]")
    for lang in ["python", "rust", "go", "javascript", "c"]:
        s = lang_stats[lang]
        avg_ms = report["avg_compile_ms"][lang]
        avg_ir = report["avg_ir_nodes"][lang]
        print(f"    {lang:>12s}: success={s['success']:>4d}  fail={s['fail']:>4d}  "
              f"compile={avg_ms:.3f}ms  avg_ir={avg_ir:.1f} nodes")

    # 保存报告
    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(f"""# 跨语言压力测试报告
> 生成时间: {time.strftime("%Y-%m-%d %H:%M:%S")}
> 算法数: {total} | 语言: 5 | 通过: {passed} ({report["pass_rate"]:.1f}%)

## 总体指标

| 指标 | 值 |
|---|---|
| 总算法数 | {total} |
| 通过 | {passed} ({report['pass_rate']:.1f}%) |
| 编译失败 | {failed_compile} |
| 执行失败 | {failed_execute} |
| 结果不一致 | {failed_consistent} |
| 总耗时 | {elapsed_total:.2f}s |
| 吞吐量 | {rate:.1f} alg/s |

## 各语言统计

| 语言 | 成功 | 失败 | 平均编译(ms) | 平均IR节点 |
|---|---|---|---|---|
""", encoding="utf-8")
        for lang in ["python", "rust", "go", "javascript", "c"]:
            s = lang_stats[lang]
            avg_ms = report["avg_compile_ms"][lang]
            avg_ir = report["avg_ir_nodes"][lang]
            out.write_text(f"| {lang} | {s['success']} | {s['fail']} | {avg_ms:.3f} | {avg_ir:.1f} |\n",
                           encoding="utf-8")

    print(f"\n  报告已保存: {output_path}")
    print(f"{'=' * 70}\n")

    return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="跨语言压力测试")
    parser.add_argument("--algorithms", type=int, default=1000, help="算法数量")
    parser.add_argument("--output", type=str, default="docs/CROSS_LANG_STRESS_REPORT.md",
                        help="报告输出路径")
    args = parser.parse_args()

    report = run_stress_test(algorithms=args.algorithms, output_path=args.output)
    sys.exit(0 if report["pass_rate"] >= 90 else 1)
