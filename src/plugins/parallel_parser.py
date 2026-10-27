"""并行解析插件（重构阶段 2 第 5 项：核心解析去并行化）。

`src/parser.py` 属于内核，内核必须**单线程确定性**：递归下降解析器读的是全局
`features` 开关与 `custom_ops` 注册表，多线程同时跑会让「同一份源码 → 同一棵
AST」这条可复现性承诺失效（特性开关是进程级可变状态，任务之间会互相踩）。
另外 `threading` / `concurrent.futures` 本身也在内核 import 白名单之外。

因此这里把 v2.5 的线程池批量解析从核心里搬出来：依赖方向是
`plugins/parallel_parser → parser`（插件依赖内核），反向不存在。

需要并行吞吐的调用方（IDE 索引、批量迁移工具）显式 import 本模块；核心主链
`matha run` 永远走单线程 `src.parser.parse`。
"""
from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from src import ast_nodes as ast
from src.parser import Parser

logger = logging.getLogger("matha.plugins.parallel_parser")

__all__ = ["parse_batch", "shutdown_parsers", "default_workers"]

_parse_pool_lock = threading.Lock()
_parse_pool: ThreadPoolExecutor | None = None

#: 批量任务的整体等待上限（秒），超时视为失败而不是无限挂住。
_BATCH_TIMEOUT = 60.0
_RESULT_TIMEOUT = 30.0


def default_workers() -> int:
    """自适应线程数：读设备配置的 `thread_workers`（可用 MATHA_THREAD_WORKERS 覆盖）。

    懒 import：`src.plugins.device_config` 走 ctypes 探测本机 CPU 拓扑，属插件级依赖，
    不该出现在内核解析器的导入路径上。
    """
    from src.plugins.device_config import get_config
    return get_config().thread_workers


def _parse_worker(source: str) -> ast.Program:
    """工作线程执行的单条解析任务。"""
    return Parser(source).parse()


def _get_or_create_pool(max_workers: int) -> ThreadPoolExecutor:
    """获取或创建全局线程池（线程安全）。"""
    global _parse_pool
    with _parse_pool_lock:
        if _parse_pool is None or _parse_pool._shutdown:
            _parse_pool = ThreadPoolExecutor(
                max_workers=max(max_workers, default_workers()),
                thread_name_prefix="matha-parser",
            )
        return _parse_pool


def parse_batch(
    sources: list[str],
    max_workers: int | None = None,
) -> list[ast.Program]:
    """批量并行解析 Matha 源码，返回与 `sources` 顺序对应的 AST 列表。

    单条任务失败不影响整批：该位置返回空 `Program` 并把错误记进日志（与从
    `src/parser.py` 搬出来时的行为一致）。
    """
    if not sources:
        return []

    workers = default_workers() if max_workers is None else max_workers
    executor = _get_or_create_pool(workers)
    futures = {executor.submit(_parse_worker, src): i for i, src in enumerate(sources)}
    results: list[ast.Program | None] = [None] * len(sources)

    for future in as_completed(futures, timeout=_BATCH_TIMEOUT):
        idx = futures[future]
        try:
            results[idx] = future.result(timeout=_RESULT_TIMEOUT)
        except Exception as e:  # noqa: BLE001
            logger.error("线程解析失败 (index %d): %s", idx, e)
            results[idx] = ast.Program()

    return [r for r in results if r is not None]


def shutdown_parsers(wait: bool = True) -> None:
    """关闭解析器线程池。"""
    global _parse_pool
    with _parse_pool_lock:
        if _parse_pool:
            _parse_pool.shutdown(wait=wait)
            _parse_pool = None
