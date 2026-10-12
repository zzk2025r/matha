"""Matha 操作系统模块：进程、文件系统、网络、内存管理。"""
from __future__ import annotations

import collections
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ProcessState(Enum):
    NEW = "new"
    READY = "ready"
    RUNNING = "running"
    WAITING = "waiting"
    TERMINATED = "terminated"
    ZOMBIE = "zombie"


class FilePermission(Enum):
    READ = "r"
    WRITE = "w"
    EXECUTE = "x"
    READ_WRITE = "rw"
    READ_EXECUTE = "rx"
    ALL = "rwx"


class SocketType(Enum):
    STREAM = "stream"
    DGRAM = "dgram"
    RAW = "raw"


class NetworkProtocol(Enum):
    TCP = "tcp"
    UDP = "udp"
    ICMP = "icmp"
    HTTP = "http"
    HTTPS = "https"
    FTP = "ftp"
    SSH = "ssh"
    DNS = "dns"


@dataclass
class Process:
    pid: int
    name: str
    state: ProcessState = ProcessState.NEW
    parent_pid: int = 0
    memory_usage: int = 0
    cpu_usage: float = 0.0
    arguments: list[str] = field(default_factory=list)
    environment: dict[str, str] = field(default_factory=dict)
    stdout: str | None = None
    stderr: str | None = None
    exit_code: int | None = None
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None


@dataclass
class FileDescriptor:
    fd: int
    path: str
    mode: FilePermission = FilePermission.READ
    position: int = 0
    size: int = 0
    file_type: str = "regular"
    open_time: float = field(default_factory=time.time)


@dataclass
class Directory:
    path: str
    entries: dict[str, Any] = field(default_factory=dict)
    parent: str | None = None
    permissions: str = "rwxr-xr-x"
    created: float = field(default_factory=time.time)


@dataclass
class MemoryRegion:
    start: int
    size: int
    protection: str = "rw-"
    mapped_file: str | None = None
    shared: bool = False


@dataclass
class Socket:
    fd: int
    socket_type: SocketType = SocketType.STREAM
    protocol: NetworkProtocol = NetworkProtocol.TCP
    local_addr: str = "127.0.0.1"
    local_port: int = 0
    remote_addr: str = ""
    remote_port: int = 0
    state: str = "CLOSED"
    buffer: bytes = b""


class ProcessManager:
    """进程管理器。"""

    def __init__(self):
        self._processes: dict[int, Process] = {}
        self._next_pid = 1
        self._ready_queue: collections.deque = collections.deque()
        self._running = False
        self._lock = threading.Lock()

    def fork(self, name: str, args: list[str] = None,
                env: dict[str, str] = None) -> Process:
        with self._lock:
            pid = self._next_pid
            self._next_pid += 1
            proc = Process(pid=pid, name=name,
                           arguments=args or [],
                           environment=env or {})
            proc.state = ProcessState.READY
            self._processes[pid] = proc
            self._ready_queue.append(pid)
            return proc

    def kill(self, pid: int) -> bool:
        proc = self._processes.get(pid)
        if proc:
            proc.state = ProcessState.TERMINATED
            proc.end_time = time.time()
            return True
        return False

    def wait(self, pid: int) -> int | None:
        proc = self._processes.get(pid)
        if proc and proc.state == ProcessState.TERMINATED:
            return proc.exit_code
        return None

    def get_process(self, pid: int) -> Process | None:
        return self._processes.get(pid)

    def list_processes(self) -> list[Process]:
        return list(self._processes.values())

    def execute(self, command: str,
                   args: list[str] = None) -> Process:
        proc = self.fork(command, args)
        proc.state = ProcessState.RUNNING
        return proc


class FileSystem:
    """文件系统。"""

    def __init__(self):
        self._files: dict[str, bytes] = {}
        self._dirs: dict[str, Directory] = {}
        self._fds: dict[int, FileDescriptor] = {}
        self._next_fd = 0
        self._root = Directory(path="/")
        self._dirs["/"] = self._root
        self._current_dir = "/"

    def open(self, path: str, mode: FilePermission = FilePermission.READ
                ) -> int:
        fd = self._next_fd
        self._next_fd += 1
        self._fds[fd] = FileDescriptor(
            fd=fd, path=path, mode=mode,
            size=self._files.get(path, b"").__len__(),
        )
        return fd

    def read(self, fd: int, size: int = -1) -> bytes:
        fdesc = self._fds.get(fd)
        if not fdesc:
            return b""
        if fdesc.path in self._files:
            data = self._files[fdesc.path]
            if size == -1:
                return data
            return data[fdesc.position:fdesc.position + size]
        return b""

    def write(self, fd: int, data: bytes) -> int:
        fdesc = self._fds.get(fd)
        if not fdesc:
            return 0
        self._files[fdesc.path] = data
        fdesc.size = len(data)
        return len(data)

    def close(self, fd: int) -> bool:
        if fd in self._fds:
            del self._fds[fd]
            return True
        return False

    def mkdir(self, path: str) -> bool:
        if path not in self._dirs:
            self._dirs[path] = Directory(path=path)
            return True
        return False

    def exists(self, path: str) -> bool:
        return path in self._files or path in self._dirs

    def remove(self, path: str) -> bool:
        if path in self._files:
            del self._files[path]
            return True
        if path in self._dirs:
            del self._dirs[path]
            return True
        return False

    def list_dir(self, path: str = "/") -> list[str]:
        return list(self._dirs.get(path, Directory(path=path)).entries.keys())


class NetworkStack:
    """网络栈。"""

    def __init__(self):
        self._sockets: dict[int, Socket] = {}
        self._next_fd = 0
        self._connections: dict[int, Socket] = {}
        self._routes: dict[str, str] = {}
        self._dns_cache: dict[str, str] = {}
        self._lock = threading.Lock()

    def create_socket(self, socket_type: SocketType = SocketType.STREAM,
                         protocol: NetworkProtocol = NetworkProtocol.TCP
                         ) -> int:
        fd = self._next_fd
        self._next_fd += 1
        sock = Socket(fd=fd, socket_type=socket_type, protocol=protocol)
        self._sockets[fd] = sock
        return fd

    def bind(self, fd: int, address: str,
                port: int) -> bool:
        sock = self._sockets.get(fd)
        if sock:
            sock.local_addr = address
            sock.local_port = port
            sock.state = "LISTEN"
            return True
        return False

    def listen(self, fd: int, backlog: int = 5) -> bool:
        sock = self._sockets.get(fd)
        if sock:
            sock.state = "LISTEN"
            return True
        return False

    def accept(self, fd: int) -> Socket | None:
        sock = self._sockets.get(fd)
        if sock and sock.state == "LISTEN":
            return Socket(
                fd=self._next_fd,
                socket_type=sock.socket_type,
                protocol=sock.protocol,
                state="ESTABLISHED",
            )
        return None

    def connect(self, fd: int, address: str,
                   port: int) -> bool:
        sock = self._sockets.get(fd)
        if sock:
            sock.remote_addr = address
            sock.remote_port = port
            sock.state = "ESTABLISHED"
            return True
        return False

    def send(self, fd: int, data: bytes) -> int:
        sock = self._sockets.get(fd)
        if sock:
            sock.buffer += data
            return len(data)
        return 0

    def recv(self, fd: int, size: int = 4096) -> bytes:
        sock = self._sockets.get(fd)
        if sock and sock.buffer:
            data = sock.buffer[:size]
            sock.buffer = sock.buffer[size:]
            return data
        return b""

    def close(self, fd: int) -> bool:
        if fd in self._sockets:
            del self._sockets[fd]
            return True
        return False

    def get_address_info(self, hostname: str
                             ) -> str | None:
        return self._dns_cache.get(hostname)


class MemoryManager:
    """内存管理器。"""

    def __init__(self, total_memory: int = 4 * 1024 * 1024 * 1024):
        self.total_memory = total_memory
        self.used_memory = 0
        self.free_memory = total_memory
        self._regions: list[MemoryRegion] = []
        self._lock = threading.Lock()

    def allocate(self, size: int,
                    protection: str = "rw-") -> MemoryRegion | None:
        with self._lock:
            if self.free_memory >= size:
                region = MemoryRegion(
                    start=self.used_memory,
                    size=size,
                    protection=protection,
                )
                self._regions.append(region)
                self.used_memory += size
                self.free_memory -= size
                return region
            return None

    def free(self, region: MemoryRegion) -> bool:
        with self._lock:
            if region in self._regions:
                self._regions.remove(region)
                self.free_memory += region.size
                return True
        return False

    def map_file(self, path: str, size: int
                    ) -> MemoryRegion | None:
        region = MemoryRegion(
            start=0, size=size,
            mapped_file=path,
            shared=True,
        )
        self._regions.append(region)
        return region

    def get_usage(self) -> dict[str, int]:
        return {
            "total": self.total_memory,
            "used": self.used_memory,
            "free": self.free_memory,
            "regions": len(self._regions),
        }


class Shell:
    """Shell。"""

    def __init__(self):
        self._commands: dict[str, Callable] = {}
        self._history: list[str] = []
        self._environment: dict[str, str] = {}
        self._working_dir = "/"

    def execute(self, command: str) -> str:
        self._history.append(command)
        parts = command.strip().split()
        if not parts:
            return ""
        cmd = parts[0]
        args = parts[1:]
        if cmd in self._commands:
            return self._commands[cmd](*args)
        return f"Command not found: {cmd}"

    def add_command(self, name: str, handler: Callable) -> None:
        self._commands[name] = handler

    def set_env(self, key: str, value: str) -> None:
        self._environment[key] = value

    def get_env(self, key: str) -> str | None:
        return self._environment.get(key)


def create_process_manager() -> ProcessManager:
    return ProcessManager()


def create_file_system() -> FileSystem:
    return FileSystem()


def create_network_stack() -> NetworkStack:
    return NetworkStack()


def create_memory_manager(total: int = 4 * 1024 * 1024 * 1024
                              ) -> MemoryManager:
    return MemoryManager(total_memory=total)


def create_shell() -> Shell:
    return Shell()


# ============================================================
# 内置注册
# ============================================================

def _register_os_module(builtins: dict) -> None:
    builtins["创建进程管理器"] = create_process_manager
    builtins["创建文件系统"] = create_file_system
    builtins["创建网络栈"] = create_network_stack
    builtins["创建内存管理器"] = create_memory_manager
    builtins["创建Shell"] = create_shell


def _os_module_names() -> list[str]:
    return ["创建进程管理器", "创建文件系统",
            "创建网络栈", "创建内存管理器", "创建Shell"]


__all__ = [
    "ProcessState", "FilePermission", "SocketType",
    "NetworkProtocol",
    "Process", "FileDescriptor", "Directory",
    "MemoryRegion", "Socket",
    "ProcessManager", "FileSystem", "NetworkStack",
    "MemoryManager", "Shell",
    "create_process_manager", "create_file_system",
    "create_network_stack", "create_memory_manager",
    "create_shell",
    "_register_os_module", "_os_module_names",
]
