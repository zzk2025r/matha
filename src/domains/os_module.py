"""Matha 操作系统模块：进程管理、内存管理、线程、文件系统接口。

覆盖：
  1) 进程管理（创建/终止/列表）
  2) 内存管理（分配/释放/查询）
  3) 线程管理（创建/同步/锁）
  4) 系统信息（CPU/内存/负载）
  5) 信号量与事件
  6) 环境变量
  7) Shell命令执行
"""
from __future__ import annotations

import multiprocessing
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from enum import Enum

# ============================================================
# 进程管理
# ============================================================

class ProcessState(Enum):
    RUNNING = "running"
    SLEEPING = "sleeping"
    STOPPED = "stopped"
    ZOMBIE = "zombie"
    TERMINATED = "terminated"


@dataclass
class ProcessInfo:
    """进程信息。"""
    pid: int = 0
    name: str = ""
    state: ProcessState = ProcessState.RUNNING
    cpu_usage: float = 0.0
    memory_usage: int = 0
    status: str = ""
    start_time: float = 0.0


class ProcessManager:
    """进程簿记模型（模拟）：pid 自 1000 起本地递增，不派生也不触碰任何 OS 进程。

    真的进程映像族（派生/等候/退出码/终止/关闭）只在 Matha 原生后端为真实现，
    见 `src/mbc/native_process.py`；宿主与 VM 面对那批名一律显式拒绝。
    """

    def __init__(self):
        self._processes: dict[int, ProcessInfo] = {}
        self._next_pid: int = 1000
        self._lock = threading.Lock()

    def create_process(self, name: str, cmd: str = "") -> int:
        """创建进程（模拟）。"""
        with self._lock:
            pid = self._next_pid
            self._next_pid += 1
            info = ProcessInfo(
                pid=pid, name=name, state=ProcessState.RUNNING,
                start_time=time.time(), memory_usage=0, cpu_usage=0.0,
                status=cmd,
            )
            self._processes[pid] = info
            return pid

    def terminate_process(self, pid: int) -> bool:
        """终止进程。"""
        with self._lock:
            if pid in self._processes:
                self._processes[pid].state = ProcessState.TERMINATED
                return True
            return False

    def get_process(self, pid: int) -> ProcessInfo | None:
        """获取进程信息。"""
        return self._processes.get(pid)

    def list_processes(self) -> list[ProcessInfo]:
        """列出所有进程。"""
        with self._lock:
            return list(self._processes.values())

    def get_running_count(self) -> int:
        """运行中的进程数。"""
        with self._lock:
            return sum(1 for p in self._processes.values()
                      if p.state == ProcessState.RUNNING)


# ============================================================
# 内存管理
# ============================================================

@dataclass
class MemoryBlock:
    """内存块。"""
    address: int = 0
    size: int = 0
    allocated: bool = False
    owner: str = ""


class MemoryManager:
    """内存管理器（模拟）。"""

    def __init__(self, total_memory: int = 1024 * 1024):
        self.total_memory = total_memory
        self.used_memory = 0
        self.free_memory = total_memory
        self._blocks: list[MemoryBlock] = []
        self._lock = threading.Lock()

    def allocate(self, size: int, owner: str = "") -> int:
        """分配内存。"""
        with self._lock:
            if size <= self.free_memory:
                addr = len(self._blocks) * 4096
                block = MemoryBlock(address=addr, size=size,
                                     allocated=True, owner=owner)
                self._blocks.append(block)
                self.used_memory += size
                self.free_memory -= size
                return addr
            return -1

    def free(self, address: int) -> bool:
        """释放内存。"""
        with self._lock:
            for block in self._blocks:
                if block.address == address and block.allocated:
                    block.allocated = False
                    self.used_memory -= block.size
                    self.free_memory += block.size
                    return True
            return False

    def get_memory_info(self) -> dict:
        """获取内存信息。"""
        return {
            "total": self.total_memory,
            "used": self.used_memory,
            "free": self.free_memory,
            "usage_percent": round(self.used_memory / self.total_memory * 100, 1)
                            if self.total_memory > 0 else 0,
            "block_count": len(self._blocks),
        }

    def defragment(self) -> None:
        """内存整理。"""
        with self._lock:
            allocated = [b for b in self._blocks if b.allocated]
            self._blocks = allocated
            addr = 0
            for block in self._blocks:
                block.address = addr
                addr += block.size


# ============================================================
# 线程管理
# ============================================================

@dataclass
class ThreadInfo:
    """线程信息。"""
    tid: int = 0
    name: str = ""
    status: str = "running"
    cpu_time: float = 0.0


class ThreadManager:
    """线程管理器。"""

    def __init__(self):
        self._threads: dict[int, ThreadInfo] = {}
        self._lock = threading.Lock()
        self._next_tid = 1

    def create_thread(self, name: str = "Thread", target=None, args=()) -> int:
        """创建线程。"""
        with self._lock:
            tid = self._next_tid
            self._next_tid += 1
            info = ThreadInfo(tid=tid, name=name, status="running")
            self._threads[tid] = info
            if target:
                t = threading.Thread(target=target, args=args, name=name)
                t.start()
            return tid

    def get_thread(self, tid: int) -> ThreadInfo | None:
        """获取线程信息。"""
        return self._threads.get(tid)

    def list_threads(self) -> list[ThreadInfo]:
        """列出所有线程。"""
        with self._lock:
            return list(self._threads.values())

    def join_all(self) -> None:
        """等待所有线程完成。"""
        time.sleep(0.1)


# ============================================================
# 信号量与事件
# ============================================================

class Semaphore:
    """信号量。"""

    def __init__(self, value: int = 1):
        self._sem = threading.Semaphore(value)
        self._value = value

    def acquire(self) -> bool:
        """获取信号量。"""
        self._sem.acquire()
        self._value -= 1
        return True

    def release(self) -> None:
        """释放信号量。"""
        self._sem.release()
        self._value += 1

    def get_value(self) -> int:
        """获取当前值。"""
        return self._value


class Event:
    """事件。"""

    def __init__(self, name: str = "event"):
        self.name = name
        self._event = threading.Event()

    def set(self) -> None:
        """触发事件。"""
        self._event.set()

    def clear(self) -> None:
        """清除事件。"""
        self._event.clear()

    def wait(self, timeout: float = -1) -> bool:
        """等待事件。"""
        return self._event.wait(timeout)


class Mutex:
    """互斥锁。"""

    def __init__(self):
        self._lock = threading.Lock()

    def lock(self) -> None:
        """加锁。"""
        self._lock.acquire()

    def unlock(self) -> None:
        """解锁。"""
        self._lock.release()

    def __enter__(self):
        self._lock.acquire()
        return self

    def __exit__(self, *args):
        self._lock.release()


# ============================================================
# 系统信息
# ============================================================

def get_system_info() -> dict:
    """获取系统信息。"""
    return {
        "platform": platform.system(),
        "platform_release": platform.release(),
        "platform_version": platform.version(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": multiprocessing.cpu_count(),
        "python_version": sys.version,
        "node": platform.node(),
        "os": os.name,
    }


def get_cpu_info() -> dict:
    """获取CPU信息。"""
    return {
        "cpu_count": multiprocessing.cpu_count(),
        "cpu_freq": platform.processor() or "unknown",
        "architecture": platform.machine(),
        "load_avg": os.getloadavg() if hasattr(os, "getloadavg") else (0, 0, 0),
    }


def get_memory_info() -> dict:
    """获取系统内存信息。"""
    try:
        import psutil
        mem = psutil.virtual_memory()
        return {
            "total": mem.total,
            "available": mem.available,
            "used": mem.used,
            "percent": mem.percent,
        }
    except ImportError:
        return {"total": 0, "available": 0, "used": 0, "percent": 0}


def get_disk_info() -> dict:
    """获取磁盘信息。"""
    usage = shutil.disk_usage("/") if hasattr(os, 'getcwd') else None
    return {"info": "使用disk_usage获取"} if usage is None else {
        "total": usage.total,
        "used": usage.used,
        "free": usage.free,
    }


def get_environment_variable(name: str) -> str:
    """获取环境变量。"""
    return os.environ.get(name, "")


def set_environment_variable(name: str, value: str) -> None:
    """设置环境变量。"""
    os.environ[name] = value


# ============================================================
# Shell命令
# ============================================================

def shell_exec(command: str, timeout: float = 30.0) -> dict:
    """执行Shell命令。"""
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True,
            text=True, timeout=timeout
        )
        return {
            "command": command,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "success": result.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {"command": command, "returncode": -1,
                "error": "超时", "success": False}
    except Exception as e:
        return {"command": command, "returncode": -1,
                "error": str(e), "success": False}


def _self_launcher(sub: str) -> list[str]:
    """本实现自身的启动 argv（阶段 43c）。

    冻结态（PyInstaller）`sys.executable` 即 matha.exe 本身——子进程是独立
    的 Matha 进程映像；开发态退回「宿主解释器 + 统一 CLI 入口」，二者都经
    同一个 `src/matha_main.py` 的 `run` 子命令，语义不分叉。
    """
    if getattr(sys, "frozen", False):
        return [sys.executable, sub]
    entry = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "matha_main.py")
    return [sys.executable, entry, sub]


def shell_run_script(path: str) -> dict:
    """运行脚本（阶段 43c 真化）。

    旧写法 `shell_exec(f"python {path}")` 有两处真缺陷：① 被启动的解释器是
    PATH 上的裸名 `python`（不存在即失败、存在即可能是另一套环境，Matha 自身
    反而永不被启动）；② `shell=True` + 路径直插命令串使路径成为命令注入位
    （`运行脚本("a & del /q *")` 会执行 `del`）。现在 argv 列表 + shell=False：
    `.matha` 交回 Matha 自己的 `run` 子命令，其余后缀交 `sys.executable`
    （Python 脚本本就归 Python），路径作为单个 argv 元素不再被 shell 切开。
    """
    argv = _self_launcher("run") + [path] if path.lower().endswith(".matha") \
        else [sys.executable, path]
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=30.0)
        return {
            "command": " ".join(argv),
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "success": result.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {"command": " ".join(argv), "returncode": -1,
                "error": "超时", "success": False}
    except Exception as e:
        return {"command": " ".join(argv), "returncode": -1,
                "error": str(e), "success": False}


def shell_exec_with_input(command: str, input_text: str = "", timeout: float = 30.0) -> dict:
    """带 stdin 输入执行系统命令（终端管道右段透传用，阶段 13a）。

    与 shell_exec 同一返回形状（stdout/stderr/returncode 捕获），差别仅在
    stdin 由调用方注入（CMD 管道语义：左段输出 → 右段 stdin）。失败形状
    与 shell_exec 一致（不抛错，returncode -1 + error 字段如实）。
    """
    try:
        result = subprocess.run(
            str(command), shell=True, input=str(input_text),
            capture_output=True, text=True, timeout=timeout
        )
        return {
            "command": command,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "success": result.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {"command": command, "returncode": -1,
                "error": "超时", "success": False}
    except Exception as e:
        return {"command": command, "returncode": -1,
                "error": str(e), "success": False}


def _restore_installed(mgr) -> None:
    """从当前目录 .matha_packages/*/manifest.json 还原已安装集合（install 的
    落盘形态——mgr.installed 本身只存进程内存，不还原则检查恒空）。目录缺
    manifest 视为非安装产物跳过，manifest 损坏/缺字段如实上抛不静默跳过。"""
    import json

    from src.pkg_manager import Version

    for entry in mgr.packages_dir.iterdir():
        manifest = entry / "manifest.json"
        if not entry.is_dir() or not manifest.exists():
            continue
        data = json.loads(manifest.read_text(encoding="utf-8"))
        name = data.get("name")
        ver = data.get("version")
        if not name or not ver:
            raise RuntimeError(f"包管理失败: manifest 缺 name/version: {manifest}")
        mgr.installed[name] = Version.parse(str(ver))


def check_package_updates(_=None) -> list:
    """检查包更新() → pkg_manager_v2 真本地检查（registry vs 已安装，无网络）。

    返回 [[包名, 当前版本, 最新版本, 更新类型], ...]（版本已转 str，供纯
    Matha 终端引擎直接渲染）。本域函数只做本地检查，不下载不安装。
    """
    from src.pkg_manager_v2 import MathaPackageManager

    mgr = MathaPackageManager()
    _restore_installed(mgr)
    return [[u["package"], str(u["current"]), str(u["latest"]), u["type"]]
            for u in mgr.check_updates()]


def upgrade_package_named(pkg_name) -> list:
    """升级包(包名) → 带名真安装（阶段 13c）。

    还原已安装集合 → pkg_manager_v2.upgrade_package 真盘安装（install 重写
    .matha_packages/<包>/manifest.json）→ 复核盘上 manifest 版本与预期一致。
    返回 [包名, 旧版本, 新版本]。无命中（未安装/已最新）→ RuntimeError 如实
    拒绝（升级 ≠ 全新安装，全新安装不走终端升级面）；边界 = 本地目录升级，
    不联网下载（RemotePackageClient 目标为虚构端点）。
    """
    import json

    from src.pkg_manager_v2 import MathaPackageManager

    mgr = MathaPackageManager()
    _restore_installed(mgr)
    result = mgr.upgrade_package(str(pkg_name))
    if not result:
        raise RuntimeError(
            f"升级包: 无可用更新: {pkg_name}（未安装或已最新；本地目录不下载）")
    # "pkg 0.0.1 -> 0.1.0" → [pkg, 0.0.1, 0.1.0]
    parts = result[0].split(" ")
    if len(parts) != 4 or parts[2] != "->":
        raise RuntimeError(f"升级包: 升级器返回异常格式: {result[0]!r}")
    manifest = mgr.packages_dir / parts[0] / "manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if str(data.get("version")) != parts[3]:
        raise RuntimeError(
            f"升级包复核失败: 盘上版本 {data.get('version')} ≠ 预期 {parts[3]}")
    return [parts[0], parts[1], parts[3]]


# ============================================================
# 注册
# ============================================================

def _register_os(builtins: dict) -> None:
    builtins["创建进程管理器"] = lambda: ProcessManager()
    builtins["创建进程"] = lambda pm, n, c="": pm.create_process(n, c)
    builtins["终止进程"] = lambda pm, pid: pm.terminate_process(pid)
    builtins["获取进程"] = lambda pm, pid: pm.get_process(pid)
    builtins["进程列表"] = lambda pm: pm.list_processes()
    builtins["创建内存管理器"] = lambda total=1024*1024: MemoryManager(total)
    builtins["内存分配"] = lambda mm, size, owner="": mm.allocate(size, owner)
    builtins["内存释放"] = lambda mm, addr: mm.free(addr)
    builtins["内存信息"] = lambda mm: mm.get_memory_info()
    builtins["创建线程管理器"] = lambda: ThreadManager()
    builtins["创建线程"] = lambda tm, n, t=None, a=(): tm.create_thread(n, t, a)
    builtins["线程列表"] = lambda tm: tm.list_threads()
    builtins["创建信号量"] = lambda v=1: Semaphore(v)
    builtins["信号量获取"] = lambda s: s.acquire()
    builtins["信号量释放"] = lambda s: s.release()
    builtins["创建事件"] = lambda n="event": Event(n)
    builtins["事件设置"] = lambda e: e.set()
    builtins["事件等待"] = lambda e, t=-1: e.wait(t)
    builtins["创建互斥锁"] = lambda: Mutex()
    builtins["互斥加锁"] = lambda m: m.lock()
    builtins["互斥解锁"] = lambda m: m.unlock()
    builtins["获取系统信息"] = get_system_info
    builtins["获取CPU信息"] = get_cpu_info
    builtins["获取内存信息"] = get_memory_info
    builtins["获取环境变量"] = get_environment_variable
    builtins["设置环境变量"] = set_environment_variable
    builtins["执行命令"] = shell_exec
    builtins["执行命令输入"] = lambda cmd: lambda inp: shell_exec_with_input(cmd, inp)
    builtins["运行脚本"] = shell_run_script
    builtins["检查包更新"] = check_package_updates
    builtins["升级包"] = upgrade_package_named


def _os_symtab_names() -> list[str]:
    return [
        "创建进程管理器", "创建进程", "终止进程", "获取进程", "进程列表",
        "创建内存管理器", "内存分配", "内存释放", "内存信息",
        "创建线程管理器", "创建线程", "线程列表",
        "创建信号量", "信号量获取", "信号量释放",
        "创建事件", "事件设置", "事件等待",
        "创建互斥锁", "互斥加锁", "互斥解锁",
        "获取系统信息", "获取CPU信息", "获取内存信息",
        "获取环境变量", "设置环境变量", "执行命令", "执行命令输入", "运行脚本", "检查包更新", "升级包",
    ]


__all__ = [
    "ProcessState", "ProcessInfo", "ProcessManager",
    "MemoryBlock", "MemoryManager",
    "ThreadInfo", "ThreadManager",
    "Semaphore", "Event", "Mutex",
    "get_system_info", "get_cpu_info", "get_memory_info",
    "get_environment_variable", "set_environment_variable",
    "shell_exec", "shell_exec_with_input", "shell_run_script",
    "check_package_updates", "upgrade_package_named",
    "_register_os", "_os_symtab_names",
]
