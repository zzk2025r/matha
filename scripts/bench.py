#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Matha 可复现性能基准（P3.1：补齐「无可复现性能基准」缺口）。

口径纪律（与 scripts/check.py 同一诚实原则）：
  - 只报**实测数字**，不写任何自评/对比性结论；
  - 语料改动或后端改动后需重跑本脚本刷新基线，历史 JSON 不覆盖；
  - native 段工具链不可用 → 该场景记 SKIP 并从汇总剔除，绝不记成通过；
  - `--selftest` 用同一语料双跑校验确定性输出，防止语料本身写错。

测什么（每场景三段 + 可选 native 两段 + 可选进程级并行一段）：
  compile  parse+compile_source 单段
  vm       run_module 单段（不含编译）
  total    编译+执行端到端
  native   compile_to_exe 编译成 exe 的耗时 / exe 子进程真跑耗时（Win32 PE64）
  parallel 同一枚 exe 串行 K 次 vs K 个进程并发的墙钟（P3.3：native 内部单线程，
           进程级并行是唯一 scale-out 路径，故只测这一条，speedup = serial/parallel）

用法：
  python scripts/bench.py                       # 全场景默认规模，打表
  python scripts/bench.py --json                # 同时落盘 docs/bench_baseline.json
  python scripts/bench.py --selftest            # 小规模确定性校验（CI 可用，无耗时断言）
  python scripts/bench.py --only b05 --native   # 追加原生 exe 两段计时
  python scripts/bench.py --native --parallel 4 # 再追加 4 进程并发吞吐对比
"""
from __future__ import annotations

import argparse
import json
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASE_DIR = Path(__file__).resolve().parent / "bench_cases"
sys.path.insert(0, str(ROOT))


def _case_src(stem: str, n: int) -> str:
    text = (CASE_DIR / f"{stem}.matha").read_text(encoding="utf-8")
    return text.replace("{N}", str(n))


# 场景表：stem → (说明, 默认规模 N, 期望输出构造函数或 None)
#   期望为 None 表示浮点累加序不可移植，只做确定性双跑校验。
def _exp_count(n): return [0]
def _exp_fib(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return [a]
def _exp_while(n): return [n * (n - 1) // 2]
def _exp_append(n): return [n]
def _exp_index(n): return [n * (n - 1) // 2 + n * n]
def _exp_str(n): return [n]
def _exp_for(n): return [n * (n - 1) // 2]


SCENARIOS: dict[str, tuple[str, int, object]] = {
    "b01_recursion_count": ("用户函数尾递归 count(N)：CALL/帧构造开销", 50000, _exp_count),
    "b02_fib":             ("fib(25) 树形递归：CALL+BINOP 综合", 25, _exp_fib),
    "b03_while_accum":     ("顶层 while 整数累加：JZ/BINOP/STORE_GLOBAL 开销", 100000, _exp_while),
    "b04_append_build":    ("append 拷贝式列表构造（O(n²) 既有语义）", 3000, _exp_append),
    "b05_builtin_math_call": ("内建 sqrt 循环调用：LOAD_GLOBAL+Python 内建调用开销", 50000, None),
    "b06_index_len":       ("get(xs)(i)+len 循环：柯里化内建 CALL N 融合面", 50000, _exp_index),
    "b07_trig_branch":     ("sin/cos 循环调用：math 内建对拍口径", 50000, None),
    "b08_str_concat":      ("str()+字符串拼接循环：内建 str 与不可变文本开销", 20000, _exp_str),
    "b09_for_iter":        ("for x in range 语法糖循环：发射器手写路径（不经元数表，未融合）", 50000, _exp_for),
}


def _measure(fn, repeats: int) -> dict:
    times = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn()
        times.append((time.perf_counter() - t0) * 1000.0)
    return {
        "min_ms": round(min(times), 3),
        "median_ms": round(statistics.median(times), 3),
        "max_ms": round(max(times), 3),
        "repeats": repeats,
    }


def _run_vm(stem: str, n: int):
    """一次「编译 + 执行」，返回 (outputs, compile_ms, vm_ms, total_ms)。"""
    from src.mbc import compile_source, run_module

    src = _case_src(stem, n)
    t_all = time.perf_counter()
    mod = compile_source(src)
    t_cmp = time.perf_counter()
    outs = run_module(mod)
    t_end = time.perf_counter()
    return (outs,
            (t_cmp - t_all) * 1000.0,
            (t_end - t_cmp) * 1000.0,
            (t_end - t_all) * 1000.0)


def _measure_parallel(exe: Path, k: int) -> dict:
    """同一枚单线程 exe：串行 K 次总墙钟 vs K 个进程并发墙钟。

    只量**进程级**并行（native 运行时无任何线程 API，见
    tests/test_native_concurrency_contract.py）；speedup = serial_ms / parallel_ms。
    """
    t0 = time.perf_counter()
    for _ in range(k):
        subprocess.run([str(exe)], capture_output=True, timeout=180)
    serial = (time.perf_counter() - t0) * 1000.0
    procs = [subprocess.Popen([str(exe)], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL) for _ in range(k)]
    t1 = time.perf_counter()
    for p in procs:
        p.communicate(timeout=300)
    parallel = (time.perf_counter() - t1) * 1000.0
    rcs = sorted({p.returncode for p in procs})
    return {
        "workers": k,
        "serial_ms": round(serial, 1),
        "parallel_ms": round(parallel, 1),
        "speedup": round(serial / parallel, 2) if parallel > 0 else None,
        "exit_codes": rcs,
    }


def bench_one(stem: str, n: int, repeats: int, with_native: bool,
              parallel: int = 0) -> dict:
    from src.mbc import compile_source

    row: dict = {"case": stem, "n": n}

    # —— 正确性先行：输出与期望一致（浮点场景做确定性双跑）——
    outs, _c, _v, _t = _run_vm(stem, n)
    exp = SCENARIOS[stem][2]
    if exp is not None:
        expected = exp(n)
        if outs != expected:
            row["error"] = f"VM 输出 {outs!r} != 期望 {expected!r}"
            return row
    else:
        outs2, *_ = _run_vm(stem, n)
        if outs != outs2:
            row["error"] = f"输出不确定：{outs!r} vs {outs2!r}"
            return row

    # —— 分段计时：compile 与 vm 各自独立重复 ——
    src = _case_src(stem, n)
    row["compile"] = _measure(lambda: compile_source(src), repeats)
    mod = compile_source(src)
    from src.mbc import run_module
    row["vm"] = _measure(lambda: run_module(mod), repeats)
    row["total"] = _measure(lambda: _run_vm(stem, n), repeats)

    if with_native:
        try:
            from src.mbc.native import compile_to_exe
        except Exception as e:  # noqa: BLE001 — 工具链缺失记 SKIP，不记失败
            row["native"] = {"skip": f"{type(e).__name__}: {e}"}
            return row
        exe = Path(tempfile.gettempdir()) / f"matha_bench_{stem}.exe"
        try:
            t0 = time.perf_counter()
            exe.write_bytes(compile_to_exe(src))
            row["native_compile_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)
            t0 = time.perf_counter()
            proc = subprocess.run([str(exe)], capture_output=True, timeout=120, text=True)
            row["native_run"] = _measure(
                lambda: subprocess.run([str(exe)], capture_output=True,
                                       timeout=120, text=True),
                max(1, repeats // 2))
            row["native_rc"] = proc.returncode
            if parallel > 1:
                row["parallel"] = _measure_parallel(exe, parallel)
        except Exception as e:  # noqa: BLE001
            row["native"] = {"skip": f"{type(e).__name__}: {e}"}
        finally:
            exe.unlink(missing_ok=True)
    return row


def selftest() -> int:
    """小规模全场景：验证语料可编译、输出正确/确定。不测性能。"""
    bad = 0
    for stem, (_desc, _n, exp) in SCENARIOS.items():
        n = 200 if stem != "b02_fib" else 10
        try:
            outs, *_ = _run_vm(stem, n)
        except Exception as e:  # noqa: BLE001
            print(f"[FAIL] {stem}: {type(e).__name__}: {e}")
            bad += 1
            continue
        if exp is not None:
            if outs != exp(n):
                print(f"[FAIL] {stem}: 输出 {outs!r} != 期望 {exp(n)!r}")
                bad += 1
            else:
                print(f"[PASS] {stem}: {outs!r}")
        else:
            outs2, *_ = _run_vm(stem, n)
            if outs != outs2:
                print(f"[FAIL] {stem}: 输出不确定 {outs!r} vs {outs2!r}")
                bad += 1
            else:
                print(f"[PASS] {stem}: 确定性 {outs!r}")
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Matha 可复现性能基准")
    ap.add_argument("--json", action="store_true",
                    help="结果落盘 docs/bench_baseline.json（带时间戳的新文件语义）")
    ap.add_argument("--native", action="store_true", help="追加原生 exe 两段计时")
    ap.add_argument("--repeats", type=int, default=3, help="每段重复次数（取中位）")
    ap.add_argument("--only", default="", help="只跑名字含该子串的场景")
    ap.add_argument("--parallel", type=int, default=0,
                    help="native 段追加 K 进程并发吞吐对比（需 --native）")
    ap.add_argument("--selftest", action="store_true",
                    help="小规模正确性校验（无耗时断言，CI 可挂）")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    from src import VERSION

    rows = []
    for stem, (desc, n, _exp) in SCENARIOS.items():
        if args.only and args.only not in stem:
            continue
        print(f"--- {stem}（{desc}, N={n}）---")
        row = bench_one(stem, n, args.repeats, args.native, args.parallel)
        rows.append(row)
        if "error" in row:
            print(f"    [ERROR] {row['error']}")
        else:
            for seg in ("compile", "vm", "total"):
                m = row[seg]
                print(f"    {seg:<7} min {m['min_ms']:>9.1f}ms"
                      f"  median {m['median_ms']:>9.1f}ms  (x{m['repeats']})")
            if "native_run" in row:
                print(f"    native  编译 {row.get('native_compile_ms', '?')}ms"
                      f"  exe 跑 median {row['native_run']['median_ms']:.1f}ms"
                      f"  rc={row.get('native_rc')}")
                if "parallel" in row:
                    p = row["parallel"]
                    print(f"    parallel x{p['workers']}  串行 {p['serial_ms']:.1f}ms"
                          f"  并发 {p['parallel_ms']:.1f}ms"
                          f"  speedup {p['speedup']}x  rc={p['exit_codes']}")
            elif "native" in row:
                print(f"    native  SKIP：{row['native']['skip']}")

    payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "matha_version": VERSION,
        "python": sys.version.split()[0],
        "platform": f"{platform.system()}/{platform.machine()}",
        "cpu": platform.processor(),
        "repeats": args.repeats,
        "native": bool(args.native),
        "parallel_workers": args.parallel or None,
        "note": "只报实测数字；结论性对比须另附方法与原始数据。",
        "results": rows,
    }
    if args.json:
        out = ROOT / "docs" / "bench_baseline.json"
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
        print(f"\n已写入 {out.relative_to(ROOT)}")
    if any("error" in r for r in rows):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
