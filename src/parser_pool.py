# -*- coding: utf-8 -*-
"""v2.4 ProcessPoolExecutor 解析器重构草案

设计目标：
  1. 绕过 CPython GIL，实现真正的并行意图解析
  2. 保持 v2.3 的 Result 错误传播和结构化异常
  3. 支持批量解析和流式解析两种模式
  4. 可配置工作进程数，适应不同硬件

架构：
  ProcessPoolExecutor
      ├── 主进程：接收用户输入，分发任务
      ├── 工作进程 N：每个进程持有独立的 EnhancedIntentParser 实例
      └── 结果队列：序列化 Result 对象返回主进程

设计约束：
  - MathaError / Result 必须可序列化（pickle），否则跨进程传递失败
  - 恢复策略注册必须在每个工作进程初始化时完成
  - 解析器实例状态（Intent 对象）不能跨进程共享
"""
from __future__ import annotations
import pickle
import sys
from typing import Any, Optional
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
import threading

# 延迟导入，避免主进程导入时触发子进程初始化
from src.intent_parser import IntentParser as IntentParserBase, Intent, IntentType
from src.errors import (
    MathaError, ErrorStage, ErrorSeverity,
    ClassifyError, ParamExtractError, CodeGenError, ExecError,
    classify_error, parse_error, param_error, codegen_error,
)
from src.result import Ok, Err

Result = type


# ============================================================
# 子进程初始化
# ============================================================

def _worker_init() -> None:
    """每个工作进程启动时调用，完成一次性初始化。

    关键：恢复策略和标准库必须在工作进程中重新注册，
    因为子进程是全新的 Python 解释器实例。
    """
    # 导入工作进程需要的模块（延迟导入避免循环依赖）
    from src.stdlib.core import register_core_builtins
    from src.errors import RecoveryStrategy, ErrorStage
    from src.intent_parser import IntentParser

    # 注册标准库（幂等操作）
    _worker_builtins: dict = {}
    register_core_builtins(_worker_builtins)

    # 确保恢复策略已注册（幂等操作，装饰器在模块导入时已注册）
    # 如果工作进程中策略未注册，重新导入触发装饰器执行
    from src import errors as errors_module
    _ = errors_module.RecoveryStrategy  # 触发模块加载


# ============================================================
# 可序列化包装
# ============================================================

@dataclass
class SerializableResult:
    """可 pickle 序列化的 Result 包装。

    由于 Result[Ok/Err] 包含闭包/函数引用，无法直接 pickle。
    此包装提取可序列化的字段，在接收端重建 Result。
    """
    is_ok: bool
    value: Any = None          # Ok 的 value
    error_message: str = ""    # Err 的 message
    error_stage: str = ""      # Err 的 stage name
    error_severity: str = ""   # Err 的 severity name
    error_suggestions: list = field(default_factory=list)
    error_code: str = ""

    def to_result(self) -> Result:
        """重建 Result 对象。"""
        from src.result import Ok, Err
        if self.is_ok:
            return Ok(self.value)
        from src.errors import MathaError, ErrorStage, ErrorSeverity
        stage = ErrorStage[self.error_stage] if self.error_stage else ErrorStage.UNKNOWN
        severity = ErrorSeverity[self.error_severity] if self.error_severity else ErrorSeverity.ERROR
        error = MathaError(
            message=self.error_message,
            stage=stage,
            severity=severity,
            code=self.error_code,
            suggestions=list(self.error_suggestions),
        )
        return Err(error)

    @staticmethod
    def from_result(result: Result) -> "SerializableResult":
        """从 Result 创建可序列化包装。"""
        if result.is_ok():
            return SerializableResult(is_ok=True, value=result.unwrap())
        error = result.err()
        return SerializableResult(
            is_ok=False,
            error_message=error.message,
            error_stage=error.stage.name,
            error_severity=error.severity.name,
            error_suggestions=list(error.suggestions),
            error_code=error.code,
        )


# ============================================================
# 工作进程解析函数
# ============================================================

def _worker_parse(text: str, target_lang: str = "python") -> SerializableResult:
    """工作进程执行的单条解析任务。

    每个工作进程持有独立的 EnhancedIntentParser 实例，
    避免跨进程共享状态。
    """
    from src.enhanced_intent import EnhancedIntentParser

    parser = EnhancedIntentParser()
    result = parser.parse(text, target_lang)
    return SerializableResult.from_result(result)


def _worker_execute(text: str, target_lang: str = "python") -> SerializableResult:
    """工作进程执行的解析 + 执行任务。"""
    from src.enhanced_intent import EnhancedIntentParser

    parser = EnhancedIntentParser()
    parse_result = parser.parse(text, target_lang)
    if not parse_result.is_ok():
        return SerializableResult.from_result(parse_result)

    intent = parse_result.unwrap()
    exec_result = parser.execute_and_verify(intent)
    return SerializableResult.from_result(exec_result)


# ============================================================
# 进程池解析器
# ============================================================

class ProcessPoolIntentParser:
    """基于 ProcessPoolExecutor 的并行意图解析器。

    使用方式：
        parser = ProcessPoolIntentParser(max_workers=8)
        # 批量解析
        results = parser.parse_batch(["计算 3 加 5", "反转字符串 abc"])
        # 单条解析
        result = parser.parse("计算 100 以内素数")
        # 解析 + 执行
        result = parser.execute("对数组 [3,1,2] 排序")
    """

    def __init__(self, max_workers: int = 8, init_timeout: float = 30.0):
        self.max_workers = max_workers
        self._executor: Optional[ProcessPoolExecutor] = None
        self._init_timeout = init_timeout
        self._lock = threading.Lock()

    def _get_executor(self) -> ProcessPoolExecutor:
        """懒初始化进程池（线程安全）。"""
        with self._lock:
            if self._executor is None or self._executor._shutdown:
                self._executor = ProcessPoolExecutor(
                    max_workers=self.max_workers,
                    initializer=_worker_init,
                )
            return self._executor

    def parse(self, text: str, target_lang: str = "python") -> Result:
        """单条解析（异步提交，同步等待）。"""
        executor = self._get_executor()
        future = executor.submit(_worker_parse, text, target_lang)
        try:
            serializable = future.result(timeout=self._init_timeout)
            return serializable.to_result()
        except Exception as e:
            from src.errors import ExecError
            return Err(ExecError(f"进程解析失败: {e}", e))

    def parse_batch(self, texts: list[str], target_lang: str = "python") -> list[Result]:
        """批量解析（并发提交，按输入顺序返回）。"""
        executor = self._get_executor()
        futures = [executor.submit(_worker_parse, text, target_lang) for text in texts]
        results = []
        for future in as_completed(futures, timeout=self._init_timeout):
            try:
                serializable = future.result()
                results.append(serializable.to_result())
            except Exception as e:
                from src.errors import ExecError
                results.append(Err(ExecError(f"进程解析失败: {e}", e)))
        # as_completed 不保证顺序，重新按顺序收集
        return self._reorder_results(futures, texts, target_lang)

    def _reorder_results(
        self, futures: list, texts: list[str], target_lang: str
    ) -> list[Result]:
        """按输入顺序重新排列结果。"""
        from concurrent.futures import wait
        wait(futures, timeout=self._init_timeout)
        index_map = {id(f): i for i, f in enumerate(futures)}
        results = [None] * len(texts)
        for future in futures:
            try:
                serializable = future.result(timeout=5.0)
                results[index_map[id(future)]] = serializable.to_result()
            except Exception as e:
                from src.errors import ExecError
                results[index_map[id(future)]] = Err(ExecError(f"进程解析失败: {e}", e))
        return results

    def execute(self, text: str, target_lang: str = "python") -> Result:
        """解析 + 执行（异步提交，同步等待）。"""
        executor = self._get_executor()
        future = executor.submit(_worker_execute, text, target_lang)
        try:
            serializable = future.result(timeout=self._init_timeout)
            return serializable.to_result()
        except Exception as e:
            from src.errors import ExecError
            return Err(ExecError(f"进程执行失败: {e}", e))

    def execute_batch(
        self, texts: list[str], target_lang: str = "python"
    ) -> list[Result]:
        """批量解析 + 执行。"""
        executor = self._get_executor()
        futures = [executor.submit(_worker_execute, text, target_lang) for text in texts]
        return self._reorder_results(futures, texts, target_lang)

    def shutdown(self, wait: bool = True) -> None:
        """关闭进程池。"""
        with self._lock:
            if self._executor:
                self._executor.shutdown(wait=wait)
                self._executor = None


# ============================================================
# 混合模式：GIL 敏感操作在线程池，CPU 密集在进程池
# ============================================================

class HybridIntentParser:
    """混合解析器：根据操作类型选择线程池或进程池。

    策略：
      - 分类（正则匹配）→ 线程池（GIL 下 regex 释放 GIL）
      - 参数提取（字符串操作）→ 线程池
      - 代码执行（exec）→ 进程池（CPU 密集，绕过 GIL）
    """

    def __init__(self, thread_workers: int = 16, process_workers: int = 4):
        from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
        self._thread_pool = ThreadPoolExecutor(max_workers=thread_workers)
        self._process_pool = ProcessPoolExecutor(
            max_workers=process_workers,
            initializer=_worker_init,
        )

    def parse(self, text: str, target_lang: str = "python") -> Result:
        """解析：线程池执行分类 + 参数提取。"""
        future = self._thread_pool.submit(_worker_parse, text, target_lang)
        try:
            serializable = future.result(timeout=10.0)
            return serializable.to_result()
        except Exception as e:
            from src.errors import ExecError
            return Err(ExecError(f"解析失败: {e}", e))

    def execute(self, text: str, target_lang: str = "python") -> Result:
        """执行：进程池执行代码（绕过 GIL）。"""
        future = self._process_pool.submit(_worker_execute, text, target_lang)
        try:
            serializable = future.result(timeout=30.0)
            return serializable.to_result()
        except Exception as e:
            from src.errors import ExecError
            return Err(ExecError(f"执行失败: {e}", e))

    def shutdown(self) -> None:
        self._thread_pool.shutdown(wait=True)
        self._process_pool.shutdown(wait=True)


# ============================================================
# 性能对比测试
# ============================================================

def benchmark_pools():
    """对比单进程、线程池、进程池的性能。"""
    import time
    from src.enhanced_intent import EnhancedIntentParser

    cases = [
        "计算 3 加 5",
        "对数组 [3,1,2] 排序",
        "反转字符串 hello",
        "计算 16 的平方根",
        "找出 1 到 100 的素数",
        "整数 2025 转罗马数字",
        "字符串 hello world 拆分",
        "数组 [1,2,3,4,5] 求和",
        "计算 2 的 10 次方",
        "求 48 和 18 的最大公约数",
    ] * 50  # 500 条

    # 单进程
    t0 = time.perf_counter()
    parser = EnhancedIntentParser()
    for case in cases:
        parser.parse(case)
    single_time = (time.perf_counter() - t0) * 1000

    # 进程池
    t0 = time.perf_counter()
    pool = ProcessPoolIntentParser(max_workers=8)
    results = pool.parse_batch(cases)
    pool.shutdown()
    pool_time = (time.perf_counter() - t0) * 1000

    print(f"单进程 500 条: {single_time:.0f}ms")
    print(f"进程池 8 线程:  {pool_time:.0f}ms")
    print(f"加速比:         {single_time / max(pool_time, 1):.2f}x")


if __name__ == "__main__":
    benchmark_pools()
