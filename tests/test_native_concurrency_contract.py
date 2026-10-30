# -*- coding: utf-8 -*-
"""原生后端并发边界契约（P3.3）：native 是单线程产物，且并发符号缺失时绝不伪造值。

已取证的事实（本文件把它们变成可执行判据，而非口头声明）：

  1. `src/mbc/native.py` 运行时自行解析的 kernel32 API 面是**封闭小集合**
     （GetStdHandle/WriteFile/ExitProcess/LoadLibraryA/GetProcAddress/VirtualAlloc），
     不含任何线程、纤程、临界区或原子操作 API；
  2. native 运行态（heap_ptr / heap_limit / vstack / hstack_ptr / handler_top /
     raise_msg / sweep_start / bclo:* 内建闭包）全部是镜像内的**进程级单例静态区**，
     以 rip 相对寻址直接读写，没有任何 per-thread 隔离；
  3. `src/mbc/` 后端自身不 import threading / multiprocessing / concurrent / asyncio
     （内核禁用逃逸模块另由 tests/test_kernel_purity.py 锁定）；
  4. 并发域（registry `Concurrent`／显示名「并发编程」：创建线程池、提交任务……）
     只能经宿主的**懒加载领域层**进入语言，VM 内建表里不存在这些符号；
  5. 因此并发能力的唯一 scale-out 路径是**进程级并行**（多个 exe 各跑各的），
     native 内部没有、也不提供线程级并行。

红线同 NI-001/002：符号缺失必须**显式失败**（编译期 NativeNotSupported，或运行期
非零退出码 + 不产出任何 stdout 值），绝不允许把未定义名字读成裸 0 打给用户。

工具链缺失（无 nasm/link）时涉及真跑 exe 的用例优雅 SKIP——只约束真实机器码路径。
"""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, str(ROOT))
from src.mbc import compile_source, run_module  # noqa: E402
from src.mbc.native import _APIS, NativeNotSupported, compile_to_exe  # noqa: E402


# ── 线程/同步类 WinAPI 黑名单：native 运行期一旦需要它们，本契约即要求重新评审 ──
_THREAD_APIS = [
    "CreateThread", "CreateThreadpool", "CreateThreadpoolWork", "QueueUserWorkItem",
    "WaitForSingleObject", "WaitForMultipleObjects", "WaitOnAddress",
    "CreateEvent", "CreateEventEx", "CreateMutex", "CreateSemaphore",
    "InitializeCriticalSection", "EnterCriticalSection", "LeaveCriticalSection",
    "DeleteCriticalSection", "RtlEnterCriticalSection", "RtlLeaveCriticalSection",
    "AcquireSRWLockExclusive", "ReleaseSRWLockExclusive",
    "InterlockedIncrement", "InterlockedDecrement", "InterlockedExchange",
    "InterlockedCompareExchange",
    "TlsAlloc", "TlsGetValue", "TlsSetValue", "TlsFree",
    "CreateFiber", "SwitchToFiber", "ConvertThreadToFiber",
    "FlsAlloc", "FlsGetValue", "FlsSetValue",
    "SetThreadStackGuarantee", "GetTickCount",
]
# GetTickCount 并非线程 API，从黑名单剔除以免误导（其余项保持严格）。
_THREAD_APIS = [a for a in _THREAD_APIS if a != "GetTickCount"]

# native 运行期自解析 API 的**封闭基线**：新增任何一项都必须显式改这里并被评审。
_API_BASELINE = {
    "GetStdHandle", "WriteFile", "ExitProcess",
    "LoadLibraryA", "GetProcAddress", "VirtualAlloc",
}

# 并发域符号（src/domains/registry.py 的 Concurrent.functions）
CONCURRENT_SYMBOLS = [
    "创建并发管理器", "创建线程池", "创建事件循环", "创建通道", "创建Actor",
    "提交任务", "等待所有", "获取并发统计", "启动事件循环", "停止事件循环",
]


def _toolchain_available() -> bool:
    """纯算术程序能编能跑 → 工具链可用；否则本机缺 nasm/link → 相关用例跳过。"""
    try:
        exe = Path(tempfile.gettempdir()) / "matha_native_conc_probe.exe"
        exe.write_bytes(compile_to_exe("#1：[6*7]"))
        r = subprocess.run([str(exe)], capture_output=True, timeout=30)
        return r.returncode == 0 and r.stdout.strip() == b"42"
    except (NativeNotSupported, OSError, subprocess.SubprocessError):
        return False


TOOLCHAIN = pytest.mark.skipif(
    not _toolchain_available(),
    reason="原生工具链不可用（缺 nasm/link）——本契约仅约束真实机器码路径",
)


# ─────────────────────────────── 1. API 面封闭 ───────────────────────────────

def test_native_api_surface_is_the_closed_baseline():
    """native 自解析的 API 必须恰好等于基线集合（多一个都要显式评审）。"""
    assert set(_APIS) == _API_BASELINE, (
        f"native 运行期 API 面变化：{sorted(set(_APIS) ^ _API_BASELINE)}"
    )


def test_native_api_surface_contains_no_threading_primitive():
    """基线里绝不允许出现线程/纤程/临界区/原子操作/ TLS API。"""
    hit = [a for a in _APIS for t in _THREAD_APIS if t in a]
    assert not hit, f"native 运行期出现线程/同步 API：{hit}——单线程口径失效"


def test_native_source_text_has_no_thread_api_symbol():
    """源码层面也不得引用线程 API（含注释与字符串），避免"看起来支持"。"""
    text = (ROOT / "src" / "mbc" / "native.py").read_text(encoding="utf-8")
    hit = sorted({a for a in _THREAD_APIS if re.search(rf"\b{a}\b", text)})
    assert not hit, f"native.py 出现线程 API 标识符：{hit}"


# ───────────────────────── 2. 后端不引入并发逃逸模块 ─────────────────────────

_ESCAPE_IMPORT = re.compile(
    r"^\s*(?:import|from)\s+(threading|multiprocessing|concurrent|asyncio|queue|_thread)\b",
    re.MULTILINE,
)


def test_mbc_backend_never_imports_concurrency_modules():
    """字节码编译器 / VM / native 发射器都不得依赖 Python 并发设施。"""
    offenders = {}
    for py in sorted((ROOT / "src" / "mbc").glob("*.py")):
        m = _ESCAPE_IMPORT.search(py.read_text(encoding="utf-8", errors="replace"))
        if m:
            offenders[py.name] = m.group(1)
    assert not offenders, f"src/mbc 引入了并发模块：{offenders}"


def test_vm_builtin_table_has_no_concurrency_symbol():
    """并发能力不来自内建：VM 内建表里不得有线程池/任务队列/事件循环类名字。

    注意区分：`注册任务`/`执行待办`/`待办列表` 属**时间域的协作式调度表**
    （既有契约：回调从不触发、执行待办恒返回 []），不是线程原语，故不在禁用之列。
    """
    from src.mbc.vm import _default_builtins

    names = set(_default_builtins())
    hit = sorted(n for n in names
                 if any(k in n for k in ("线程", "并发", "事件循环", "通道", "纤程")))
    assert not hit, f"VM 内建表混入并发域符号：{hit}（应只经领域懒加载提供）"
    for sym in CONCURRENT_SYMBOLS:
        assert sym not in names, f"并发域符号 {sym} 被硬编进 VM 内建，违反懒加载边界"


# ─────────────────── 3. VM 侧：并发符号缺失时必须显式失败 ───────────────────

def _vm(src: str):
    return run_module(compile_source(src))


@pytest.mark.parametrize("sym", CONCURRENT_SYMBOLS[:5])
def test_vm_without_domain_layer_rejects_concurrent_symbol(sym):
    """未加载领域时引用并发符号 → 必须抛「未定义」，不得返回任何伪造值。"""
    src = f"v = {sym}(2)\n输出(v)\n"
    with pytest.raises(Exception) as ei:
        _vm(src)
    # 干净失败：异常文本应指向未定义/不可调用，而不是悄悄算出个 0
    assert "未定义" in str(ei.value) or "不可调用" in str(ei.value), str(ei.value)


def test_vm_domain_load_requires_host_resolver():
    """VM 直连路径没有宿主插件层：`加载领域` 必须显式报错，不得静默跳过指令。"""
    src = "@：【加载领域】，并发编程\np = 创建线程池(2)\n输出(1)\n"
    with pytest.raises(Exception) as ei:
        _vm(src)
    assert "领域" in str(ei.value) or "插件" in str(ei.value), str(ei.value)


# ─────────── 4. native：并发源码必须干净失败，绝不伪造 stdout 值 ────────────

_NATIVE_CONC_CASES = {
    "load_directive": "@：【加载领域】，并发编程\np = 创建线程池(2)\n输出(1)\n",
    "bare_symbol": "p = 创建线程池(2)\n输出(p)\n",
    "submit_task": "@：【加载领域】，并发编程\n输出(提交任务(1))\n",
    "wait_all": "@：【加载领域】，并发编程\n等待所有()\n输出(7)\n",
}


@TOOLCHAIN
@pytest.mark.parametrize("tag", sorted(_NATIVE_CONC_CASES))
def test_native_never_fabricates_concurrent_result(tag):
    """并发符号在 native：要么编译期拒绝，要么非零退出且 stdout 一个字节都不出。"""
    exe = Path(tempfile.gettempdir()) / f"matha_native_conc_{tag}.exe"
    try:
        exe.write_bytes(compile_to_exe(_NATIVE_CONC_CASES[tag]))
    except Exception:  # noqa: BLE001 — 编译期任何拒绝都合规
        return
    try:
        r = subprocess.run([str(exe)], capture_output=True, timeout=60)
    finally:
        exe.unlink(missing_ok=True)
    out = r.stdout.decode("utf-8", "replace")
    assert out.strip() == "", (
        f"{tag}: native 对不可表示的并发符号静默产出了 {out!r}，"
        f"违反『单线程、不承载并发域、且不伪造值』的设计契约"
    )
    assert r.returncode != 0, f"{tag}: native 未支持并发却以 0 码退出，语义不明"


# ─────────── 5. 进程级并行：唯一的 scale-out 路径，结果必须与串行之一致 ──────

# 真算一段 CPU 活（切片 + 长度），native 已确认可编译可运行。
_PARALLEL_SRC = "输出(len(slice(range(0)(3000))(1)(2000)))\n"
_PARALLEL_WANT = "1999"


@TOOLCHAIN
@pytest.mark.parametrize("workers", [2, 4])
def test_process_level_parallelism_is_deterministic(workers):
    """同一枚 exe 并发跑 N 个进程：每个都 rc=0 且输出逐字节相同（无共享态串味）。"""
    exe = Path(tempfile.gettempdir()) / "matha_native_conc_parallel.exe"
    exe.write_bytes(compile_to_exe(_PARALLEL_SRC))
    try:
        procs = [subprocess.Popen([str(exe)], stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE) for _ in range(workers)]
        # 并发跑完（全部 start 后才收），确实存在时间重叠
        outs = []
        for p in procs:
            so, se = p.communicate(timeout=60)
            outs.append((p.returncode, so.decode("utf-8", "replace")))
    finally:
        exe.unlink(missing_ok=True)
    assert {o[0] for o in outs} == {0}, f"并发进程退出码异常：{outs}"
    assert {o[1].strip() for o in outs} == {_PARALLEL_WANT}, (
        f"进程级并行结果不一致/不确定：{outs}"
    )
