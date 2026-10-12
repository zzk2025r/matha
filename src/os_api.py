"""Matha 系统调用接口 + POSIX/Windows API 层。"""
from __future__ import annotations

import collections
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any


class SyscallNumber(IntEnum):
    """Linux x86-64 系统调用号。"""
    READ = 0
    WRITE = 1
    OPEN = 2
    CLOSE = 3
    STAT = 4
    FSTAT = 5
    LSEEK = 8
    MMAP = 9
    MPROTECT = 10
    MUNMAP = 11
    BRK = 12
    IOCTL = 16
    PREAD64 = 17
    PWRITE64 = 18
    READV = 19
    WRITEV = 20
    ACCESS = 21
    PIPE = 22
    SELECT = 23
    SCHED_YIELD = 24
    MREMAP = 25
    MSYNC = 26
    MINCORE = 27
    MADVISE = 28
    DUP = 32
    DUP2 = 33
    PAUSE = 34
    NANOSLEEP = 35
    GETPID = 39
    SOCKET = 41
    CONNECT = 42
    ACCEPT = 43
    SENDTO = 44
    RECVFROM = 45
    SENDMSG = 46
    RECVMSG = 47
    SHUTDOWN = 48
    BIND = 49
    LISTEN = 50
    GETSOCKNAME = 51
    GETPEERNAME = 52
    SOCKETPAIR = 53
    SETSOCKOPT = 54
    GETSOCKOPT = 55
    CLONE = 56
    FORK = 57
    VFORK = 58
    EXECVE = 59
    EXIT = 60
    WAIT4 = 61
    KILL = 62
    UNAME = 63
    FCNTL = 72
    FSYNC = 74
    FDATASYNC = 75
    TRUNCATE = 76
    FTRUNCATE = 77
    GETDENTS = 78
    GETCWD = 79
    CHDIR = 80
    FCHDIR = 81
    RENAME = 82
    MKDIR = 83
    RMDIR = 84
    CREAT = 85
    LINK = 86
    UNLINK = 87
    SYMLINK = 88
    READLINK = 89
    CHMOD = 90
    FCHMOD = 91
    CHOWN = 92
    GETUID = 102
    GETGID = 104
    SETUID = 105
    SETGID = 106
    GETEUID = 107
    GETEGID = 108
    PTRACE = 101
    RT_SIGACTION = 13
    RT_SIGPROCMASK = 14
    GETRLIMIT = 97
    PRCTL = 157
    ARCH_PRCTL = 158
    FUTEX = 202
    SCHED_SETAFFINITY = 203
    EPOLL_CREATE = 213
    EPOLL_CTL = 233
    EPOLL_WAIT = 232
    OPENAT = 257
    NEWFSTATAT = 262
    GETTID = 186
    MEMBARRIER = 324


class OpenFlags(IntEnum):
    RDONLY = 0o0
    WRONLY = 0o1
    RDWR = 0o2
    CREAT = 0o100
    EXCL = 0o200
    TRUNC = 0o1000
    APPEND = 0o2000
    NONBLOCK = 0o4000
    DIRECTORY = 0o200000
    CLOEXEC = 0o2000000


class Errno(IntEnum):
    """POSIX 错误码。"""
    EPERM = 1
    ENOENT = 2
    ESRCH = 3
    EINTR = 4
    EIO = 5
    ENXIO = 6
    E2BIG = 7
    ENOEXEC = 8
    EBADF = 9
    ECHILD = 10
    EAGAIN = 11
    ENOMEM = 12
    EACCES = 13
    EFAULT = 14
    EBUSY = 16
    EEXIST = 17
    EXDEV = 18
    ENODEV = 19
    ENOTDIR = 20
    EISDIR = 21
    EINVAL = 22
    ENFILE = 23
    EMFILE = 24
    ENOTTY = 25
    EFBIG = 27
    ENOSPC = 28
    ESPIPE = 29
    EROFS = 30
    EMLINK = 31
    EPIPE = 32
    EDOM = 33
    ERANGE = 34
    EDEADLK = 35
    ENAMETOOLONG = 36
    ENOSYS = 38
    ENOTEMPTY = 39
    ELOOP = 40
    EADDRINUSE = 98
    EADDRNOTAVAIL = 99
    ENETDOWN = 100
    ECONNABORTED = 103
    ECONNRESET = 104
    ENOBUFS = 105
    EISCONN = 106
    ENOTCONN = 107
    ETIMEDOUT = 110
    ECONNREFUSED = 111


@dataclass
class SyscallResult:
    value: Any = 0
    error: int = 0
    errno_name: str = ""

    @property
    def ok(self) -> bool:
        return self.error == 0


@dataclass
class SyscallEntry:
    number: int = 0
    name: str = ""
    args: list[Any] = field(default_factory=list)
    retval: Any = 0
    error: int = 0
    duration_us: float = 0.0
    timestamp: float = field(default_factory=time.time)


class SyscallTable:
    """系统调用表。"""

    def __init__(self):
        self._table: dict[int, Callable] = {}
        self._names: dict[int, str] = {}
        self._lock = threading.Lock()
        self._log: collections.deque = collections.deque(
            maxlen=4096)
        self._counters: dict[int, int] = {}
        self.register_defaults()

    def register(self, num: int, name: str,
                    handler: Callable) -> bool:
        with self._lock:
            self._table[num] = handler
            self._names[num] = name
            return True

    def dispatch(self, num: int,
                    *args: Any) -> SyscallResult:
        handler = self._table.get(num)
        if handler is None:
            return SyscallResult(
                error=Errno.ENOSYS,
                errno_name="ENOSYS")
        start = time.perf_counter()
        try:
            value = handler(*args)
            err = 0
        except OSError as e:
            value = 0
            err = e.errno or Errno.EIO
        except Exception:
            value = 0
            err = Errno.EINVAL
        duration = (time.perf_counter() - start) * 1e6
        self._log.append(SyscallEntry(
            number=num,
            name=self._names.get(num, "?"),
            args=[type(a).__name__ for a in args],
            retval=value, error=err,
            duration_us=duration,
        ))
        self._counters[num] = self._counters.get(num, 0) + 1
        return SyscallResult(
            value=value, error=err,
            errno_name=(Errno(err).name
                        if err in [e.value for e in Errno]
                        else ""),
        )

    def register_defaults(self) -> None:
        self.register(0, "read", lambda *_: 0)
        self.register(1, "write", lambda *_: 0)
        self.register(2, "open", lambda *_: 3)
        self.register(3, "close", lambda *_: 0)
        self.register(39, "getpid", lambda: os.getpid())
        self.register(102, "getuid", lambda: os.getuid()
                      if hasattr(os, "getuid") else 0)
        self.register(60, "exit", lambda *_: 0)
        self.register(24, "sched_yield", lambda: 0)
        self.register(63, "uname", lambda: "Linux")
        self.register(186, "gettid", lambda:
                      threading.get_ident())
        self.register(79, "getcwd", lambda *_: b"/")

    def get_log(self, count: int = 20) -> list[SyscallEntry]:
        return list(self._log)[-count:]

    def get_stats(self) -> dict[str, Any]:
        return {
            "registered": len(self._table),
            "calls": sum(self._counters.values()),
            "unique": len(self._counters),
        }


class VFS:
    """虚拟文件系统层。"""

    def __init__(self):
        self._mounts: dict[str, dict[str, Any]] = {
            "/": {"fstype": "ext4", "device": "/dev/sda1",
                  "read_only": False},
            "/proc": {"fstype": "proc", "device": "proc",
                      "read_only": True},
            "/sys": {"fstype": "sysfs", "device": "sysfs",
                      "read_only": True},
            "/dev": {"fstype": "devtmpfs", "device": "devtmpfs",
                      "read_only": False},
        }
        self._nodes: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._inode_counter = 1

    def mount(self, device: str, mount_point: str,
                fstype: str) -> bool:
        with self._lock:
            self._mounts[mount_point] = {
                "fstype": fstype, "device": device,
                "read_only": False,
            }
            return True

    def umount(self, mount_point: str) -> bool:
        with self._lock:
            if mount_point in self._mounts:
                del self._mounts[mount_point]
                return True
        return False

    def lookup(self, path: str) -> int | None:
        with self._lock:
            if path in self._nodes:
                return self._nodes[path]["inode"]
            if path in self._mounts:
                return 1
        return None

    def create(self, path: str,
               mode: int = 0o644) -> int:
        with self._lock:
            ino = self._inode_counter
            self._inode_counter += 1
            self._nodes[path] = {
                "inode": ino, "mode": mode, "size": 0,
            }
            return ino

    def unlink(self, path: str) -> bool:
        with self._lock:
            if path in self._nodes:
                del self._nodes[path]
                return True
        return False

    def list_mounts(self) -> dict[str, dict[str, Any]]:
        return dict(self._mounts)


class ProcessTable:
    """进程表。"""

    def __init__(self):
        self._procs: dict[int, dict[str, Any]] = {}
        self._next_pid = 1
        self._lock = threading.Lock()

    def spawn(self, name: str,
              args: list[str] | None = None
              ) -> int:
        with self._lock:
            pid = self._next_pid
            self._next_pid += 1
            self._procs[pid] = {
                "pid": pid, "name": name,
                "args": args or [],
                "state": "running",
                "start": time.time(),
                "tid": threading.get_ident(),
            }
            return pid

    def wait(self, pid: int, timeout: float = 0.0) -> dict[str, Any] | None:
        with self._lock:
            if pid in self._procs:
                self._procs[pid]["state"] = "zombie"
                return self._procs.pop(pid)
        return None

    def kill(self, pid: int, sig: int = 9) -> bool:
        with self._lock:
            if pid in self._procs:
                self._procs[pid]["state"] = "killed"
                del self._procs[pid]
                return True
        return False

    def list_procs(self) -> list[dict[str, Any]]:
        return list(self._procs.values())


class Libc:
    """POSIX C 库层。"""

    def __init__(self):
        self.syscalls = SyscallTable()
        self.vfs = VFS()
        self.procs = ProcessTable()
        self._env: dict[str, str] = {}
        self._umask = 0o022
        self._uid = 0
        self._gid = 0

    def getpid(self) -> int:
        return os.getpid()

    def getcwd(self) -> str:
        return os.getcwd()

    def chmod(self, path: str, mode: int) -> int:
        try:
            os.chmod(path, mode)
            return 0
        except OSError as e:
            return e.errno or Errno.EIO

    def chdir(self, path: str) -> int:
        try:
            os.chdir(path)
            return 0
        except OSError as e:
            return e.errno or Errno.ENOENT

    def getenv(self, name: str) -> str | None:
        return os.environ.get(name)

    def setenv(self, name: str, value: str) -> int:
        os.environ[name] = value
        self._env[name] = value
        return 0

    def gettimeofday(self) -> float:
        return time.time()

    def sleep(self, seconds: float) -> int:
        time.sleep(seconds)
        return 0

    def usleep(self, micros: int) -> int:
        time.sleep(micros / 1_000_000)
        return 0

    def open(self, path: str, flags: int = 0) -> int:
        mode = {OpenFlags.WRONLY: os.O_WRONLY,
                OpenFlags.RDWR: os.O_RDWR}.get(flags, os.O_RDONLY)
        fmode = 0
        if flags & OpenFlags.CREAT:
            mode |= os.O_CREAT
            fmode = 0o644
        if flags & OpenFlags.APPEND:
            mode |= os.O_APPEND
        if flags & OpenFlags.TRUNC:
            mode |= os.O_TRUNC
        try:
            return os.open(path, mode, fmode)
        except OSError as e:
            return -(e.errno or Errno.EIO)

    def close(self, fd: int) -> int:
        try:
            os.close(fd)
            return 0
        except OSError:
            return -int(Errno.EBADF)

    def read(self, fd: int, n: int) -> bytes:
        try:
            return os.read(fd, n)
        except OSError:
            return b""

    def write(self, fd: int, data: bytes) -> int:
        try:
            return os.write(fd, data)
        except OSError:
            return -int(Errno.EIO)

    def lseek(self, fd: int, offset: int,
                whence: int = 0) -> int:
        try:
            return os.lseek(fd, offset, whence)
        except OSError:
            return -int(Errno.EBADF)

    def isatty(self, fd: int) -> bool:
        return os.isatty(fd)

    def uname(self) -> dict[str, str]:
        return {
            "sysname": "Linux",
            "nodename": "matha",
            "release": "6.1.0",
            "version": "#1 SMP Matha",
            "machine": "x86_64",
        }

    def getrlimit(self, resource: int) -> tuple[int, int]:
        import resource
        soft, hard = resource.getrlimit(resource)
        return soft, hard


class Win32API:
    """Windows API 兼容层。"""

    def __init__(self):
        self._handles: dict[int, Any] = {}
        self._next_handle = 0x100
        self._last_error = 0

    INVALID_HANDLE_VALUE = -1

    ERROR_FILE_NOT_FOUND = 2
    ERROR_ACCESS_DENIED = 5
    ERROR_INVALID_HANDLE = 6

    def create_file(self, path: str,
                    access: int = 0,
                    creation: int = 3) -> int:
        handle = self._next_handle
        self._next_handle += 4
        self._handles[handle] = {
            "path": path, "access": access,
            "position": 0, "data": b"",
        }
        return handle

    def close_handle(self, handle: int) -> bool:
        if handle in self._handles:
            del self._handles[handle]
            return True
        self._last_error = self.ERROR_INVALID_HANDLE
        return False

    def read_file(self, handle: int,
                  size: int) -> bytes:
        h = self._handles.get(handle)
        if h is None:
            self._last_error = self.ERROR_INVALID_HANDLE
            return b""
        return h["data"][:size]

    def write_file(self, handle: int,
                   data: bytes) -> int:
        h = self._handles.get(handle)
        if h is None:
            self._last_error = self.ERROR_INVALID_HANDLE
            return 0
        h["data"] += data
        return len(data)

    def get_last_error(self) -> int:
        return self._last_error

    def virtual_alloc(self, size: int) -> int:
        return self._next_handle

    def load_library(self, name: str) -> int:
        return self.create_file(f"lib/{name}.dll")

    def get_proc_address(self, lib: int,
                          name: str) -> int:
        return self._next_handle + 100

    def get_module_handle(self, name: str | None = None) -> int:
        return 0x7FFF0000

    def get_system_info(self) -> dict[str, Any]:
        import platform
        return {
            "processor_count":
                os.cpu_count() or 1,
            "page_size": 4096,
            "os": platform.system(),
            "arch": platform.machine(),
        }


def create_libc() -> Libc:
    return Libc()


def create_win32() -> Win32API:
    return Win32API()


def create_syscall_table() -> SyscallTable:
    return SyscallTable()


def create_vfs() -> VFS:
    return VFS()


def create_process_table() -> ProcessTable:
    return ProcessTable()


def create_os_api() -> Libc:
    """统一 OS API 入口。"""
    return Libc()


# ============================================================
# 内置注册
# ============================================================

def _register_os_api(builtins: dict) -> None:
    builtins["创建POSIX库"] = create_libc
    builtins["创建Win32接口"] = create_win32
    builtins["创建系统调用表"] = create_syscall_table
    builtins["创建虚拟文件系统"] = create_vfs
    builtins["创建进程表"] = create_process_table
    builtins["创建操作系统API"] = create_os_api


def _os_api_names() -> list[str]:
    return ["创建POSIX库", "创建Win32接口",
            "创建系统调用表", "创建虚拟文件系统",
            "创建进程表", "创建操作系统API"]


__all__ = [
    "SyscallNumber", "OpenFlags", "Errno",
    "SyscallResult", "SyscallEntry",
    "SyscallTable", "VFS", "ProcessTable",
    "Libc", "Win32API",
    "create_libc", "create_win32",
    "create_syscall_table", "create_vfs",
    "create_process_table", "create_os_api",
    "_register_os_api", "_os_api_names",
]
