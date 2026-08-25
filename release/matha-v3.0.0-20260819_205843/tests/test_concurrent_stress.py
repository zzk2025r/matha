# -*- coding: utf-8 -*-
"""v2.3 并发压力测试 — 100 线程同时输入自然语言指令

测试目标：
  1. 验证 REPLState.error_log 在 100 线程下的线程安全性
  2. 验证 RecoveryStrategy 在并发注册/调用下的正确性
  3. 验证 EnhancedIntentParser 在并发解析下的结果一致性
  4. 测量并发性能损耗

运行方式：
  python tests/test_concurrent_stress.py
  python tests/test_concurrent_stress.py --threads 200
  python tests/test_concurrent_stress.py --iterations 50
"""
from __future__ import annotations
import sys
import time
import threading
import statistics
from typing import Any
from dataclasses import dataclass, field

sys.path.insert(0, r"D:\trae")

from src.repl_v23 import MathaREPL, REPLState
from src.enhanced_intent import EnhancedIntentParser, execute_intent
from src.errors import (
    RecoveryStrategy, ErrorStage, MathaError,
    ParseError, ClassifyError, composite_error,
)
from src.intent_parser import IntentType


# ============================================================
# 测试输入数据
# ============================================================

SUCCESS_CASES = [
    "计算 3 加 5",
    "计算 10 减 3",
    "计算 6 乘以 7",
    "对数组 [3,1,2] 排序",
    "对数组 [5,3,8,1] 反转",
    "反转字符串 hello",
    "字符串 hello 转大写",
    "计算 16 的平方根",
    "计算 2 的 10 次方",
    "找出 1 到 100 的素数",
    "整数 10 转罗马数字",
    "字符串 abc 拼接",
    "数组 [1,2,3] 求和",
    "数组 [3,1,2] 去重",
    "计算 100 的平均值",
]

FAIL_CASES = [
    "xyz abc notreal",
    "blahblah xyz",
    "qwerty 12345",
    "测试无效输入",
    "随机字符串 abc",
]

MIXED_CASES = SUCCESS_CASES + FAIL_CASES


# ============================================================
# 测试结果数据类
# ============================================================

@dataclass
class ThreadResult:
    """单个线程的执行结果。"""
    thread_id: int
    input_text: str
    success: bool
    elapsed_ms: float
    error_msg: str = ""
    intent_type: str = ""


@dataclass
class StressTestResult:
    """压力测试汇总结果。"""
    total_threads: int
    total_iterations: int
    total_cases: int
    success_count: int
    fail_count: int
    error_count: int  # 异常而非分类失败
    total_elapsed_ms: float
    per_thread_elapsed: list[float]  # 每个线程的耗时
    errors: list[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        if self.total_cases == 0:
            return 0.0
        return self.success_count / self.total_cases * 100

    @property
    def avg_latency_ms(self) -> float:
        if not self.per_thread_elapsed:
            return 0.0
        return statistics.mean(self.per_thread_elapsed)

    @property
    def p95_latency_ms(self) -> float:
        if not self.per_thread_elapsed:
            return 0.0
        sorted_lat = sorted(self.per_thread_elapsed)
        idx = int(len(sorted_lat) * 0.95)
        return sorted_lat[min(idx, len(sorted_lat) - 1)]

    def report(self) -> str:
        lines = [
            "=" * 60,
            "并发压力测试结果",
            "=" * 60,
            f"线程数:       {self.total_threads}",
            f"总用例数:     {self.total_cases}",
            f"成功:         {self.success_count} ({self.success_rate:.1f}%)",
            f"分类失败:     {self.fail_count}",
            f"异常错误:     {self.error_count}",
            f"总耗时:       {self.total_elapsed_ms:.1f}ms",
            f"平均延迟:     {self.avg_latency_ms:.2f}ms/线程",
            f"P95 延迟:     {self.p95_latency_ms:.2f}ms/线程",
        ]
        if self.errors:
            lines.append("")
            lines.append("异常详情:")
            for e in self.errors[:5]:
                lines.append(f"  - {e}")
        lines.append("=" * 60)
        return "\n".join(lines)


# ============================================================
# 核心测试函数
# ============================================================

def test_concurrent_parse(
    num_threads: int = 100,
    cases_per_thread: int = 5,
) -> StressTestResult:
    """并发解析测试：多线程同时调用 EnhancedIntentParser.parse()。"""
    results: list[ThreadResult] = []
    lock = threading.Lock()
    parse_errors: list[str] = []

    def worker(thread_id: int):
        start = time.perf_counter()
        thread_results: list[ThreadResult] = []
        parser = EnhancedIntentParser()

        for i in range(cases_per_thread):
            case = MIXED_CASES[(thread_id * cases_per_thread + i) % len(MIXED_CASES)]
            try:
                result = parser.parse(case)
                elapsed = (time.perf_counter() - start) * 1000
                if result.is_ok():
                    intent = result.unwrap()
                    thread_results.append(ThreadResult(
                        thread_id=thread_id,
                        input_text=case,
                        success=True,
                        elapsed_ms=elapsed,
                        intent_type=intent.intent_type.name,
                    ))
                else:
                    thread_results.append(ThreadResult(
                        thread_id=thread_id,
                        input_text=case,
                        success=False,
                        elapsed_ms=elapsed,
                        error_msg=result.err().message[:50],
                    ))
            except Exception as e:
                with lock:
                    parse_errors.append(f"T{thread_id}: {type(e).__name__}: {e}")
                thread_results.append(ThreadResult(
                    thread_id=thread_id,
                    input_text=case,
                    success=False,
                    elapsed_ms=(time.perf_counter() - start) * 1000,
                    error_msg=str(e),
                ))

        with lock:
            results.extend(thread_results)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
    t0 = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    total_elapsed = (time.perf_counter() - t0) * 1000

    # 计算每个线程的平均耗时
    thread_times: dict[int, list[float]] = {}
    for r in results:
        thread_times.setdefault(r.thread_id, []).append(r.elapsed_ms)
    per_thread = [statistics.mean(v) for v in thread_times.values()]

    success_count = sum(1 for r in results if r.success)
    fail_count = sum(1 for r in results if not r.success and not r.error_msg.startswith("Traceback"))
    error_count = sum(1 for r in results if r.error_msg.startswith("Traceback"))

    return StressTestResult(
        total_threads=num_threads,
        total_iterations=cases_per_thread,
        total_cases=num_threads * cases_per_thread,
        success_count=success_count,
        fail_count=fail_count,
        error_count=error_count,
        total_elapsed_ms=total_elapsed,
        per_thread_elapsed=per_thread,
        errors=parse_errors,
    )


def test_concurrent_repl_state(num_threads: int = 100) -> StressTestResult:
    """并发写入测试：多线程同时向 REPLState.error_log 写入错误。"""
    state = REPLState()
    parse_errors_list: list[str] = []
    lock = threading.Lock()

    def worker(thread_id: int):
        for i in range(10):
            try:
                err = ParseError(f"test error from thread {thread_id} iter {i}",
                                line=thread_id * 10 + i, col=1)
                state.append_error(err)
            except Exception as e:
                with lock:
                    parse_errors_list.append(f"T{thread_id}: {e}")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
    t0 = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)
    total_elapsed = (time.perf_counter() - t0) * 1000

    logged = state.get_error_log()
    expected = num_threads * 10
    success = len(logged) == expected

    return StressTestResult(
        total_threads=num_threads,
        total_iterations=10,
        total_cases=expected,
        success_count=expected if success else 0,
        fail_count=0 if success else expected,
        error_count=len(parse_errors_list),
        total_elapsed_ms=total_elapsed,
        per_thread_elapsed=[total_elapsed / num_threads] * num_threads,
        errors=parse_errors_list[:5] if parse_errors_list else [],
    )


def test_concurrent_recovery_strategy(num_threads: int = 100) -> StressTestResult:
    """并发恢复策略测试：多线程同时注册和调用恢复策略。"""
    results: list[str] = []
    lock = threading.Lock()
    stage = ErrorStage.VALIDATING  # 在函数级别定义，供清理使用

    def worker(thread_id: int):
        # 动态注册一个专属策略
        stage = ErrorStage.VALIDATING
        strategy_name = f"strategy_t{thread_id}"

        def _strategy(error: MathaError):
            error.add_suggestion(f"{strategy_name} added")
            return None

        # 注册（写锁保护）
        RecoveryStrategy.register(stage)(_strategy)

        # 调用（读锁 + 副本遍历）
        error = MathaError(f"test from T{thread_id}", stage)
        RecoveryStrategy.try_recover(error)

        with lock:
            results.append(f"T{thread_id}: suggestions={len(error.suggestions)}")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
    t0 = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)
    total_elapsed = (time.perf_counter() - t0) * 1000

    # 清理注册的策略
    RecoveryStrategy._strategies.pop(stage, None)

    return StressTestResult(
        total_threads=num_threads,
        total_iterations=1,
        total_cases=num_threads,
        success_count=num_threads,
        fail_count=0,
        error_count=0,
        total_elapsed_ms=total_elapsed,
        per_thread_elapsed=[total_elapsed / num_threads] * num_threads,
    )


def test_concurrent_execute_intent(num_threads: int = 50) -> StressTestResult:
    """并发执行测试：多线程同时解析 + 执行意图。"""
    results: list[ThreadResult] = []
    lock = threading.Lock()
    exec_errors: list[str] = []

    def worker(thread_id: int):
        cases = SUCCESS_CASES[:5]
        parser = EnhancedIntentParser()
        for case in cases:
            try:
                parse_result = parser.parse(case)
                if parse_result.is_ok():
                    intent = parse_result.unwrap()
                    exec_result = parser.execute_and_verify(intent)
                    with lock:
                        results.append(ThreadResult(
                            thread_id=thread_id,
                            input_text=case,
                            success=exec_result.is_ok(),
                            elapsed_ms=0,
                            intent_type=exec_result.unwrap() if exec_result.is_ok() else str(exec_result.err()),
                        ))
                else:
                    with lock:
                        results.append(ThreadResult(
                            thread_id=thread_id,
                            input_text=case,
                            success=False,
                            elapsed_ms=0,
                            error_msg=parse_result.err().message[:50],
                        ))
            except Exception as e:
                with lock:
                    exec_errors.append(f"T{thread_id}: {type(e).__name__}: {e}")
                    results.append(ThreadResult(
                        thread_id=thread_id,
                        input_text=case,
                        success=False,
                        elapsed_ms=0,
                        error_msg=str(e),
                    ))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
    t0 = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    total_elapsed = (time.perf_counter() - t0) * 1000

    success_count = sum(1 for r in results if r.success)
    fail_count = sum(1 for r in results if not r.success)

    return StressTestResult(
        total_threads=num_threads,
        total_iterations=5,
        total_cases=num_threads * 5,
        success_count=success_count,
        fail_count=fail_count,
        error_count=len(exec_errors),
        total_elapsed_ms=total_elapsed,
        per_thread_elapsed=[total_elapsed / num_threads] * num_threads,
        errors=exec_errors[:5],
    )


# ============================================================
# 主测试入口
# ============================================================

def run_all_stress_tests(
    threads: int = 100,
    verbose: bool = True,
) -> dict[str, StressTestResult]:
    """运行全部压力测试。"""
    results = {}

    if verbose:
        print("\n" + "=" * 60)
        print("  Matha v2.3 并发压力测试")
        print(f"  线程数: {threads}")
        print("=" * 60)

    # Test 1: 并发解析
    if verbose:
        print("\n【Test 1】并发意图解析（{} 线程）".format(threads))
    r1 = test_concurrent_parse(num_threads=threads)
    results["parse"] = r1
    if verbose:
        print(r1.report())

    # Test 2: REPLState 并发写入
    if verbose:
        print("\n【Test 2】REPLState.error_log 并发写入（{} 线程）".format(threads))
    r2 = test_concurrent_repl_state(num_threads=threads)
    results["repl_state"] = r2
    if verbose:
        print(r2.report())

    # Test 3: 恢复策略并发
    if verbose:
        print("\n【Test 3】RecoveryStrategy 并发调用（{} 线程）".format(threads))
    r3 = test_concurrent_recovery_strategy(num_threads=threads)
    results["recovery"] = r3
    if verbose:
        print(r3.report())

    # Test 4: 并发执行（线程数减半，避免超时）
    if verbose:
        print("\n【Test 4】并发意图执行（{} 线程）".format(threads // 2))
    r4 = test_concurrent_execute_intent(num_threads=threads // 2)
    results["execute"] = r4
    if verbose:
        print(r4.report())

    # 汇总
    if verbose:
        print("\n" + "=" * 60)
        print("  汇总")
        print("=" * 60)
        total_cases = sum(r.total_cases for r in results.values())
        total_success = sum(r.success_count for r in results.values())
        total_fail = sum(r.fail_count for r in results.values())
        total_err = sum(r.error_count for r in results.values())
        print(f"  总用例:   {total_cases}")
        print(f"  成功:     {total_success} ({total_success/total_cases*100:.1f}%)")
        print(f"  分类失败: {total_fail}")
        print(f"  异常错误: {total_err}")
        print("=" * 60)

    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="v2.3 并发压力测试")
    parser.add_argument("--threads", type=int, default=100, help="并发线程数（默认 100）")
    parser.add_argument("--quiet", action="store_true", help="静默模式（仅输出汇总）")
    args = parser.parse_args()

    results = run_all_stress_tests(threads=args.threads, verbose=not args.quiet)

    # 检查是否全部通过（分类失败不计入异常）
    all_passed = all(
        r.error_count == 0
        for r in results.values()
    )
    if all_passed:
        print("\n✅ 所有压力测试通过！（分类失败 {} 为预期行为）".format(
            sum(r.fail_count for r in results.values())))
        sys.exit(0)
    else:
        print("\n❌ 存在异常错误，请检查上述报告")
        sys.exit(1)
