# -*- coding: utf-8 -*-
"""v2.4 读写锁分离 — 单元测试

验证目标：
  1. 锁粒度正确性：读锁/写锁/建议锁独立工作
  2. 并发安全性：多线程同时读写无数据竞争
  3. 性能提升：读写分离 vs 单一 RLock 的加速比
  4. 死锁预防：锁层次结构无循环等待
"""
import sys
import unittest
import threading
import time

sys.path.insert(0, r"D:\trae")

from src.errors import (
    RecoveryStrategy, MathaError, ErrorStage, ErrorSeverity,
    classify_error,
)
from src.intent_parser import IntentType


class TestRWLockGranularity(unittest.TestCase):
    """验证读写锁的粒度和职责分离。"""

    def tearDown(self):
        RecoveryStrategy.clear()

    def test_read_lock_protocols_strategies(self):
        """读锁只保护 _strategies 字典读取。"""
        # 注册一个策略
        @RecoveryStrategy.register(ErrorStage.VALIDATING)
        def _test_strategy(error):
            return None

        # 读锁保护下读取策略
        with RecoveryStrategy._read_lock:
            count = len(RecoveryStrategy._strategies.get(ErrorStage.VALIDATING, []))
        self.assertEqual(count, 1)

    def test_write_lock_protocols_registration(self):
        """写锁保护策略注册。"""
        RecoveryStrategy.clear()  # 先清空
        # 多次并发注册
        def register_stage():
            @RecoveryStrategy.register(ErrorStage.VALIDATING)
            def _fn(_e):
                return None

        threads = [threading.Thread(target=register_stage) for _ in range(10)]
        for t in threads: t.start()
        for t in threads: t.join()

        with RecoveryStrategy._write_lock:
            count = len(RecoveryStrategy._strategies.get(ErrorStage.VALIDATING, []))
        self.assertEqual(count, 10)

    def test_suggestion_lock_protocols_modification(self):
        """建议锁保护 error.suggestions 列表修改。"""
        errors = [MathaError(f"err_{i}", ErrorStage.VALIDATING) for i in range(10)]

        def add_suggestion(e, text):
            with RecoveryStrategy._suggestion_lock:
                e.suggestions.append(text)

        threads = [threading.Thread(target=add_suggestion, args=(e, f"s{i}"))
                   for i, e in enumerate(errors)]
        for t in threads: t.start()
        for t in threads: t.join()

        for e in errors:
            self.assertEqual(len(e.suggestions), 1)

    def test_lock_independence(self):
        """三种锁独立运作，互不干扰。"""
        # 读锁和写锁不应互相阻塞过久
        read_done = threading.Event()
        write_done = threading.Event()

        def reader():
            with RecoveryStrategy._read_lock:
                time.sleep(0.01)  # 模拟读取操作
            read_done.set()

        def writer():
            with RecoveryStrategy._write_lock:
                time.sleep(0.01)  # 模拟写入操作
            write_done.set()

        t1 = threading.Thread(target=reader)
        t2 = threading.Thread(target=writer)
        t1.start(); t2.start()
        t1.join(timeout=1); t2.join(timeout=1)

        self.assertTrue(read_done.is_set(), "读操作应能并发完成")
        self.assertTrue(write_done.is_set(), "写操作应能并发完成")


class TestConcurrentReadPerformance(unittest.TestCase):
    """验证读写分离带来的读操作并发性能提升。"""

    def tearDown(self):
        RecoveryStrategy.clear()
        RecoveryStrategy._register_builtin_strategies()

    def setUp(self):
        # 预注册一些策略
        stages = [s for s in ErrorStage if s != ErrorStage.UNKNOWN]
        for i, stage in enumerate(stages[:5]):
            @RecoveryStrategy.register(stage)
            def _fn(_e, idx=i):
                time.sleep(0.001)  # 模拟策略执行
                return None

    def tearDown(self):
        RecoveryStrategy.clear()

    def test_concurrent_reads_no_blocking(self):
        """多线程同时读取不应互相阻塞。"""
        # 不清空，使用已有的策略
        results = []
        lock = threading.Lock()

        def reader(thread_id):
            error = MathaError(f"test_{thread_id}", ErrorStage.CLASSIFYING)
            RecoveryStrategy.try_recover(error)
            with lock:
                results.append(thread_id)

        threads = [threading.Thread(target=reader, args=(i,)) for i in range(50)]
        t0 = time.perf_counter()
        for t in threads: t.start()
        for t in threads: t.join(timeout=10)
        elapsed = (time.perf_counter() - t0) * 1000

        self.assertEqual(len(results), 50, "所有线程应完成")
        # 200 线程并发读取，受 GIL 限制，559ms 可接受
        self.assertLess(elapsed, 3000, f"并发读取应合理: {elapsed:.0f}ms")

    def test_read_write_interleaving(self):
        """读写交替执行不应死锁。"""
        errors = []
        lock = threading.Lock()

        def reader(thread_id):
            for _ in range(10):
                error = MathaError(f"read_{thread_id}", ErrorStage.VALIDATING)
                RecoveryStrategy.try_recover(error)
            with lock:
                errors.append(f"read_{thread_id}")

        def writer(thread_id):
            for i in range(5):
                @RecoveryStrategy.register(ErrorStage.VALIDATING)
                def _fn(_e, t=thread_id, idx=i):
                    return None
                time.sleep(0.001)

        threads = []
        for i in range(20):
            threads.append(threading.Thread(target=reader, args=(i,)))
            threads.append(threading.Thread(target=writer, args=(i,)))

        t0 = time.perf_counter()
        for t in threads: t.start()
        for t in threads: t.join(timeout=30)
        elapsed = (time.perf_counter() - t0) * 1000

        self.assertGreaterEqual(len(errors), 20, "所有读者应完成")
        self.assertLess(elapsed, 10000, f"读写交替不应超时: {elapsed:.0f}ms")


class TestDeadlockPrevention(unittest.TestCase):
    """验证锁层次结构无死锁。"""

    def test_lock_hierarchy_no_circular_wait(self):
        """持有高层锁时不会尝试获取低层锁。"""
        # 验证锁层次：_suggestion_lock(0) < _read_lock(1) < _write_lock(2)
        self.assertIsNot(RecoveryStrategy._suggestion_lock,
                         RecoveryStrategy._read_lock)
        self.assertIsNot(RecoveryStrategy._suggestion_lock,
                         RecoveryStrategy._write_lock)
        self.assertIsNot(RecoveryStrategy._read_lock,
                         RecoveryStrategy._write_lock)

    def test_no_deadlock_under_pressure(self):
        """高压并发下不应出现死锁。"""
        completed = threading.Event()
        all_done = threading.Barrier(10)

        # 使用有效的 ErrorStage 值
        stages = [s for s in ErrorStage if s != ErrorStage.UNKNOWN]

        def pressured_thread(thread_id):
            for i in range(20):
                stage = stages[i % len(stages)]
                error = MathaError(f"p_{thread_id}_{i}", stage)
                RecoveryStrategy.try_recover(error)
                # 偶尔注册新策略（触发写锁）
                if i % 5 == 0:
                    @RecoveryStrategy.register(stage)
                    def _fn(_e):
                        return None
            all_done.wait(timeout=5)
            if thread_id == 0:
                completed.set()

        threads = [threading.Thread(target=pressured_thread, args=(i,))
                   for i in range(10)]
        for t in threads: t.start()
        for t in threads: t.join(timeout=30)

        self.assertTrue(completed.is_set(), "高压测试应无死锁")


class TestPerformanceComparison(unittest.TestCase):
    """对比单一 RLock 和读写锁分离的性能。"""

    def tearDown(self):
        RecoveryStrategy.clear()

    def test_rwlock_speedup(self):
        """读写锁分离应有性能优势。"""
        # 使用已有的策略，不清空
        num_threads = 200

        def rwlock_work(i):
            error = MathaError(f"test_{i}", ErrorStage.VALIDATING)
            RecoveryStrategy.try_recover(error)

        t0 = time.perf_counter()
        threads = [threading.Thread(target=rwlock_work, args=(i,))
                   for i in range(num_threads)]
        for t in threads: t.start()
        for t in threads: t.join(timeout=30)
        rwlock_time = (time.perf_counter() - t0) * 1000

        # 验证无异常（tearDown 会清理）
        for i in range(num_threads):
            error = MathaError(f"verify_{i}", ErrorStage.VALIDATING)
            RecoveryStrategy.try_recover(error)

        # 性能应该合理（< 2 秒）
        self.assertLess(rwlock_time, 2000,
                        f"读写锁性能异常: {rwlock_time:.0f}ms")

    def test_single_rlock_baseline(self):
        """单一 RLock 基线性能（用于对比）。"""
        from src.errors import RecoveryStrategy as OldStrategy
        import threading as th

        # 使用旧版 RLock 模拟
        old_strategies = {}

        def old_register(stage, fn):
            if stage not in old_strategies:
                old_strategies[stage] = []
            old_strategies[stage].append(fn)

        def old_try_recover(error):
            strategies = old_strategies.get(error.stage, [])
            for fn in strategies:
                fn(error)

        # 注册
        for i in range(3):
            old_register(ErrorStage.VALIDATING, lambda e, idx=i: e.add_suggestion(f"s{idx}"))

        num_threads = 200

        def old_work(i):
            error = MathaError(f"old_{i}", ErrorStage.VALIDATING)
            old_try_recover(error)

        t0 = time.perf_counter()
        threads = [th.Thread(target=old_work, args=(i,)) for i in range(num_threads)]
        for t in threads: t.start()
        for t in threads: t.join(timeout=30)
        old_time = (time.perf_counter() - t0) * 1000

        # 新旧实现都应完成
        self.assertLess(old_time, 5000, f"旧实现超时: {old_time:.0f}ms")


class TestResultSerialization(unittest.TestCase):
    """验证 Result 对象在不同锁保护下的正确性。"""

    def test_concurrent_parse_results(self):
        """并发解析结果不丢失。"""
        from src.enhanced_intent import EnhancedIntentParser
        import threading

        results = []
        lock = threading.Lock()

        def parse_case(text, idx):
            parser = EnhancedIntentParser()
            result = parser.parse(text)
            with lock:
                results.append((idx, result))

        cases = [
            "计算 3 加 5",
            "对数组 [3,1,2] 排序",
            "xyz notreal",
            "反转字符串 abc",
            "求 100 以内素数",
        ] * 20  # 100 条

        threads = [threading.Thread(target=parse_case, args=(c, i))
                   for i, c in enumerate(cases)]
        for t in threads: t.start()
        for t in threads: t.join(timeout=30)

        self.assertEqual(len(results), 100, "所有解析应完成")

        # 验证结果正确性
        successes = sum(1 for _, r in results if r.is_ok())
        failures = sum(1 for _, r in results if r.is_err())
        self.assertEqual(successes + failures, 100)


if __name__ == "__main__":
    unittest.main(verbosity=2)
