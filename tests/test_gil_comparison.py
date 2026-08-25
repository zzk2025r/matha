# -*- coding: utf-8 -*-
"""GIL 竞争对比测试脚本

运行 threading vs multiprocessing 的并发写入对比测试。

用法：
  python tests/test_gil_comparison.py
"""
import sys
import time
import threading
import multiprocessing as mp
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.hardware.hal import HardwareAbstractionLayer, MathaHardwareOps, GPIODevice


def threading_test(num_threads=8, iterations=3000, pin=18):
    """Threading 并发测试。"""
    results = []
    errors = []

    def worker(tid):
        hal = HardwareAbstractionLayer()
        ops = MathaHardwareOps(hal)
        hal.register(GPIODevice(pin=pin))
        latencies = []
        try:
            for i in range(iterations):
                t0 = time.perf_counter()
                ops.写入(f"gpio_{pin}", i % 2 == 0)
                latencies.append((time.perf_counter() - t0) * 1e6)
        except Exception as e:
            errors.append(str(e))
        results.append({
            "tid": tid,
            "latencies": latencies,
            "elapsed": iterations / (sum(latencies)/len(latencies)/1e6) if latencies else 0,
        })

    start = time.perf_counter()
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    elapsed = time.perf_counter() - start

    total_ops = num_threads * iterations
    total_rate = total_ops / elapsed if elapsed > 0 else 0
    all_lats = [l for r in results for l in r["latencies"]]
    return {
        "mode": "threading",
        "ops": total_ops,
        "elapsed": elapsed,
        "rate": total_rate,
        "avg_lat": sum(all_lats)/len(all_lats) if all_lats else 0,
        "max_lat": max(all_lats) if all_lats else 0,
        "errors": len(errors),
    }


def multiprocessing_test(num_workers=8, iterations=3000, pin=18):
    """Multiprocessing 并发测试（使用模块级 worker 函数）。"""
    from src.hardware.hal_multiprocessing import gpio_writer_worker

    start = time.perf_counter()
    q = mp.Queue()
    procs = [mp.Process(target=gpio_writer_worker, args=(i, pin, iterations, q)) for i in range(num_workers)]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=30)
    elapsed = time.perf_counter() - start

    results = []
    while not q.empty():
        results.append(q.get())

    total_ops = num_workers * iterations
    total_rate = total_ops / elapsed if elapsed > 0 else 0
    all_lats = [r["avg_latency_us"] for r in results]
    all_max_lats = [r["max_latency_us"] for r in results]
    return {
        "mode": "multiprocessing",
        "ops": total_ops,
        "elapsed": elapsed,
        "rate": total_rate,
        "avg_lat": sum(all_lats)/len(all_lats) if all_lats else 0,
        "max_lat": max(all_max_lats) if all_max_lats else 0,
        "errors": sum(r["errors"] for r in results),
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="GIL 竞争对比测试")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--iterations", type=int, default=3000)
    args = parser.parse_args()

    print("=" * 60)
    print("  Matha v4.2 — GIL 竞争对比测试")
    print(f"  Workers/Threads: {args.workers}, Iterations: {args.iterations}")
    print("=" * 60)

    print("\n[1/2] Threading 测试...")
    t_start = time.perf_counter()
    t_result = threading_test(args.workers, args.iterations)
    t_elapsed = time.perf_counter() - t_start
    print(f"  耗时: {t_elapsed:.3f}s")
    print(f"  速率: {t_result['rate']:,.0f} ops/sec")
    print(f"  平均延迟: {t_result['avg_lat']:.2f} μs")
    print(f"  最大延迟: {t_result['max_lat']:.2f} μs")

    print("\n[2/2] Multiprocessing 测试...")
    mp_start = time.perf_counter()
    mp_result = multiprocessing_test(args.workers, args.iterations)
    mp_elapsed = time.perf_counter() - mp_start
    print(f"  耗时: {mp_elapsed:.3f}s")
    print(f"  速率: {mp_result['rate']:,.0f} ops/sec")
    print(f"  平均延迟: {mp_result['avg_lat']:.2f} μs")
    print(f"  最大延迟: {mp_result['max_lat']:.2f} μs")

    print("\n" + "=" * 60)
    print("  对比总结")
    print("=" * 60)
    rate_impr = (mp_result['rate'] / max(t_result['rate'], 1) - 1) * 100
    time_impr = (t_elapsed / max(mp_elapsed, 0.001) - 1) * 100
    max_lat_impr = (1 - mp_result['max_lat'] / max(t_result['max_lat'], 0.001)) * 100

    print(f"""
┌────────────────────────────────────────────────────────────────┐
│  指标              Threading          Multiprocessing        提升  │
├────────────────────────────────────────────────────────────────┤
│  吞吐量           {t_result['rate']:>12,.0f} ops/sec   {mp_result['rate']:>12,.0f} ops/sec  {rate_impr:>6.0f}%  │
│  测试耗时          {t_elapsed:>11.3f} s           {mp_elapsed:>11.3f} s     {time_impr:>6.0f}%  │
│  平均延迟          {t_result['avg_lat']:>11.2f} μs          {mp_result['avg_lat']:>11.2f} μs        —      │
│  最大延迟          {t_result['max_lat']:>11.2f} μs          {mp_result['max_lat']:>11.2f} μs     {max_lat_impr:>6.0f}%  │
│  错误数            {t_result['errors']:>12}               {mp_result['errors']:>12}          │
└────────────────────────────────────────────────────────────────┘
""")

    print("结论：")
    if rate_impr > 50:
        print(f"  ✓ Multiprocessing 吞吐量提升 {rate_impr:.0f}%，GIL 竞争问题有效解决")
    else:
        print(f"  ~ Multiprocessing 吞吐量提升 {rate_impr:.0f}%，性能改善有限")
    if max_lat_impr > 20:
        print(f"  ✓ 最大延迟降低 {max_lat_impr:.0f}%，P99 性能显著改善")
    else:
        print(f"  ~ 最大延迟改善 {max_lat_impr:.0f}%")
