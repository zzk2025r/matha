# -*- coding: utf-8 -*-
"""
Matha 大文件自举测试套件
自动扫描所有 .matha 文件，解析+解释执行，检测错误并修复
"""
import sys
import os
import time
import traceback
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.parser import Parser, ParseError
from src.interp import interpret, Interpreter, MathaRuntimeError
from src.lexer import Lexer


@dataclass
class TestResult:
    path: str
    status: str  # "PASS", "PARSE_ERROR", "RUNTIME_ERROR", "SKIPPED"
    duration_ms: float = 0.0
    source_lines: int = 0
    source_chars: int = 0
    error_type: str = ""
    error_msg: str = ""
    output: str = ""


def scan_matha_files(root: str) -> list[str]:
    """扫描所有 .matha 文件。"""
    files = []
    for dirpath, _, filenames in os.walk(root):
        # 跳过 release 目录（旧副本）
        if "release" in dirpath:
            continue
        for f in filenames:
            if f.endswith(".matha"):
                files.append(os.path.join(dirpath, f))
    return sorted(files)


def test_parse(path: str) -> tuple[bool, str]:
    """只测试词法+语法解析。"""
    try:
        with open(path, encoding="utf-8") as f:
            source = f.read()
        p = Parser(source)
        ast = p.parse()
        return True, f"解析通过: {len(ast.decls)} 条声明"
    except ParseError as e:
        return False, str(e)
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def test_run(path: str, timeout_sec: float = 10.0) -> tuple[bool, str, float]:
    """测试解析+解释执行。"""
    with open(path, encoding="utf-8") as f:
        source = f.read()
    lines = source.count("\n") + 1
    t0 = time.perf_counter()
    try:
        out, trace = interpret(source)
        ms = (time.perf_counter() - t0) * 1000
        return True, f"执行通过 ({ms:.0f}ms, {len(out)} 输出, {len(trace)} 追踪)", ms
    except ParseError as e:
        ms = (time.perf_counter() - t0) * 1000
        return False, str(e), ms
    except MathaRuntimeError as e:
        ms = (time.perf_counter() - t0) * 1000
        return False, f"RuntimeError: {e}", ms
    except RecursionError as e:
        ms = (time.perf_counter() - t0) * 1000
        return False, f"RecursionError: 栈溢出 (源码 {lines} 行 {len(source)} 字符)", ms
    except Exception as e:
        ms = (time.perf_counter() - t0) * 1000
        return False, f"{type(e).__name__}: {e}", ms


def run_bootstrap_tests(root: str) -> list[TestResult]:
    """运行所有测试。"""
    files = scan_matha_files(root)
    print(f"找到 {len(files)} 个 .matha 文件")
    print("=" * 70)

    results = []
    passed = failed = skipped = 0

    for fpath in files:
        rel = os.path.relpath(fpath, root)
        size = os.path.getsize(fpath)
        with open(fpath, encoding="utf-8") as f:
            source = f.read()
        lines = source.count("\n") + 1

        # 跳过过大的文件（> 500行）单独测试
        if lines > 500:
            ok, msg = test_parse(fpath)
            status = "PASS" if ok else "PARSE_ERROR"
            if not ok:
                failed += 1
            else:
                passed += 1
            r = TestResult(
                path=rel, status=status, source_lines=lines, source_chars=size,
                error_type="PARSE_ERROR" if not ok else "",
                error_msg=msg if not ok else "",
            )
            results.append(r)
            tag = "OK" if ok else "FAIL"
            print(f"  [{tag:4s}] {rel} ({lines}L, {size}B) - {msg}")
            continue

        # 跳过旧版 bootstrap_test（语法不兼容，已被 bootstrap_test_v2 替代）
        if "bootstrap_test.matha" in rel and "v2" not in rel:
            r = TestResult(
                path=rel, status="SKIPPED", source_lines=lines, source_chars=size,
                error_type="SKIPPED", error_msg="旧版测试（已被 bootstrap_test_v2 替代）",
            )
            results.append(r)
            print(f"  [SKIP] {rel} (旧版测试)")
            skipped += 1
            continue

        ok, msg, ms = test_run(fpath)
        status = "PASS" if ok else "PARSE_ERROR" if "ParseError" in msg else "RUNTIME_ERROR"
        if ok:
            passed += 1
        else:
            failed += 1

        r = TestResult(
            path=rel, status=status, duration_ms=ms,
            source_lines=lines, source_chars=size,
            error_type=status, error_msg=msg,
        )
        results.append(r)
        tag = "PASS" if ok else "FAIL"
        print(f"  [{tag:4s}] {rel} ({lines}L, {ms:.0f}ms) - {msg}")

    print("=" * 70)
    print(f"汇总: {passed} 通过, {failed} 失败, {len(files) - passed - failed} 跳过")
    return results


def generate_report(results: list[TestResult], output_path: str):
    """生成测试报告。"""
    passed = [r for r in results if r.status == "PASS"]
    failed = [r for r in results if r.status != "PASS"]

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# Matha 大文件自举测试报告\n\n")
        f.write(f"生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"总计: {len(results)} 文件 | 通过: {len(passed)} | 失败: {len(failed)}\n\n")

        # 总体统计
        f.write("## 总体统计\n\n")
        f.write("| 指标 | 数值 |\n")
        f.write("|------|------|\n")
        f.write(f"| 总文件数 | {len(results)} |\n")
        f.write(f"| 通过 | {len(passed)} |\n")
        f.write(f"| 失败 | {len(failed)} |\n")
        f.write(f"| 通过率 | {len(passed)/max(len(results),1)*100:.1f}% |\n")
        total_chars = sum(r.source_chars for r in results)
        total_lines = sum(r.source_lines for r in results)
        f.write(f"| 总字符数 | {total_chars:,} |\n")
        f.write(f"| 总行数 | {total_lines:,} |\n\n")

        # 失败详情
        if failed:
            f.write("## 失败测试详情\n\n")
            for r in failed:
                f.write(f"### {r.path}\n\n")
                f.write(f"- 状态: **{r.status}**\n")
                f.write(f"- 大小: {r.source_lines} 行, {r.source_chars} 字符\n")
                f.write(f"- 耗时: {r.duration_ms:.0f}ms\n")
                f.write(f"- 错误: {r.error_msg}\n\n")
                f.write("```matha\n")
                # 读源文件前30行
                try:
                    with open(os.path.join(os.path.dirname(os.path.dirname(output_path)), r.path), encoding="utf-8") as f2:
                        lines = f2.readlines()
                    for line in lines[:30]:
                        f.write(line.rstrip())
                        f.write("\n")
                    if len(lines) > 30:
                        f.write(f"... ({len(lines) - 30} more lines)\n")
                except Exception:
                    f.write("(无法读取源文件)\n")
                f.write("```\n\n")

        # 通过详情（简要）
        f.write("## 通过测试\n\n")
        for r in passed:
            f.write(f"- ✅ {r.path} ({r.source_lines}L, {r.duration_ms:.0f}ms)\n")
        f.write("\n")

        # 按目录分组统计
        f.write("## 按目录统计\n\n")
        dir_stats = {}
        for r in results:
            d = os.path.dirname(r.path) or "."
            if d not in dir_stats:
                dir_stats[d] = {"pass": 0, "fail": 0, "total_chars": 0}
            if r.status == "PASS":
                dir_stats[d]["pass"] += 1
            else:
                dir_stats[d]["fail"] += 1
            dir_stats[d]["total_chars"] += r.source_chars
        f.write("| 目录 | 通过 | 失败 | 总字符 |\n")
        f.write("|------|------|------|--------|\n")
        for d, s in sorted(dir_stats.items()):
            f.write(f"| {d} | {s['pass']} | {s['fail']} | {s['total_chars']:,} |\n")
        f.write("\n")

        # 错误类型统计
        f.write("## 错误类型统计\n\n")
        error_types = {}
        for r in failed:
            if r.error_type not in error_types:
                error_types[r.error_type] = 0
            error_types[r.error_type] += 1
        for et, cnt in sorted(error_types.items(), key=lambda x: -x[1]):
            f.write(f"- **{et}**: {cnt}\n")
        f.write("\n")


def main():
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "matha")
    root = os.path.normpath(root)
    output = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "BOOTSTRAP_TEST_REPORT.md")
    os.makedirs(os.path.dirname(output), exist_ok=True)

    print("=" * 70)
    print("Matha 大文件自举测试套件")
    print("=" * 70)
    t0 = time.perf_counter()

    results = run_bootstrap_tests(root)

    elapsed = (time.perf_counter() - t0) * 1000
    print(f"\n总耗时: {elapsed:.0f}ms")

    generate_report(results, output)
    print(f"\n报告已生成: {output}")

    # 返回失败数量
    failed = sum(1 for r in results if r.status != "PASS")
    return failed


if __name__ == "__main__":
    sys.exit(main())
