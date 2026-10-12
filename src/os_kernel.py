"""Matha 内核：进程调度、内存管理、文件系统、网络栈。"""
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
    STOPPED = "stopped"


class SchedulingPolicy(Enum):
    FCFS = "fcfs"
    SRTF = "srtf"
    ROUND_ROBIN = "round_robin"
    PRIORITY = "priority"
    MULTILEVEL = "multilevel"
    CFS = "completely_fair"


class MemoryProtection(Enum):
    USER = "user"
    KERNEL = "kernel"
    SHARED = "shared"
    PRIVATE = "private"
    READ_ONLY = "read_only"


class FileType(Enum):
    REGULAR = "regular"
    DIRECTORY = "directory"
    SYMBOLIC_LINK = "symlink"
    CHARACTER_DEVICE = "char_device"
    BLOCK_DEVICE = "block_device"
    PIPE = "pipe"
    SOCKET = "socket"
    FIFO = "fifo"


class SocketState(Enum):
    CLOSED = "closed"
    LISTEN = "listen"
    SYN_SENT = "syn_sent"
    SYN_RECEIVED = "syn_received"
    ESTABLISHED = "established"
    FIN_WAIT1 = "fin_wait1"
    FIN_WAIT2 = "fin_wait2"
    TIME_WAIT = "time_wait"
    CLOSE_WAIT = "close_wait"
    LAST_ACK = "last_ack"


@dataclass
class Task:
    pid: int
    name: str
    state: ProcessState = ProcessState.NEW
    priority: int = 0
    cpu_time: float = 0.0
    remaining_time: float = 0.0
    memory_usage: int = 0
    parent_pid: int = 0
    exit_code: int | None = None
    start_time: float = field(default_factory=time.time)
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProcessContext:
    pid: int
    registers: dict[str, int] = field(default_factory=dict)
    stack_pointer: int = 0
    base_pointer: int = 0
    instruction_pointer: int = 0
    flags: int = 0
    memory_map: list[tuple[int, int, str]] = field(default_factory=list)
    open_files: list[int] = field(default_factory=list)
    signal_mask: int = 0


@dataclass
class MemoryPage:
    frame_number: int
    page_number: int
    protection: MemoryProtection = MemoryProtection.PRIVATE
    dirty: bool = False
    referenced: bool = False
    swapped: bool = False
    swap_location: int | None = None


@dataclass
class Inode:
    inode_number: int
    file_type: FileType = FileType.REGULAR
    size: int = 0
    permissions: str = "rw-r--r--"
    owner: str = "root"
    group: str = "root"
    created: float = field(default_factory=time.time)
    modified: float = field(default_factory=time.time)
    accessed: float = field(default_factory=time.time)
    blocks: list[int] = field(default_factory=list)
    data_blocks: list[int] = field(default_factory=list)
    indirect_blocks: list[int] = field(default_factory=list)
    double_indirect: list[int] = field(default_factory=list)


@dataclass
class FileDescriptor:
    fd: int
    inode: Inode
    offset: int = 0
    mode: str = "r"
    flags: int = 0
    reference_count: int = 1


class Scheduler:
    """进程调度器。"""

    def __init__(self, policy: SchedulingPolicy = SchedulingPolicy.CFS):
        self.policy = policy
        self._ready_queue = collections.deque()
        self._running: Task | None = None
        self._processes: dict[int, Task] = {}
        self._next_pid = 1
        self._time_slice = 100
        self._context_switches = 0
        self._lock = threading.Lock()

    def fork(self, name: str, **kwargs) -> int:
        with self._lock:
            pid = self._next_pid
            self._next_pid += 1
            task = Task(pid=pid, name=name, state=ProcessState.READY,
                         **kwargs)
            self._processes[pid] = task
            self._ready_queue.append(pid)
            return pid

    def exec(self, pid: int, program: str) -> bool:
        task = self._processes.get(pid)
        if task:
            task.name = program
            task.state = ProcessState.RUNNING
            return True
        return False

    def waitpid(self, pid: int) -> Task | None:
        task = self._processes.get(pid)
        if task and task.state == ProcessState.TERMINATED:
            return task
        return None

    def kill(self, pid: int) -> bool:
        task = self._processes.get(pid)
        if task:
            task.state = ProcessState.TERMINATED
            task.end_time = time.time()
            if pid in self._ready_queue:
                self._ready_queue.remove(pid)
            return True
        return False

    def schedule(self) -> Task | None:
        with self._lock:
            if self._ready_queue:
                pid = self._ready_queue.popleft()
                self._running = self._processes.get(pid)
                if self._running:
                    self._running.state = ProcessState.RUNNING
                    self._context_switches += 1
                return self._running
            return None

    def yield_cpu(self) -> None:
        if self._running:
            self._running.state = ProcessState.READY
            self._ready_queue.append(self._running.pid)
            self._running = None

    def get_process(self, pid: int) -> Task | None:
        return self._processes.get(pid)

    def list_processes(self) -> list[Task]:
        return list(self._processes.values())

    def get_stats(self) -> dict[str, Any]:
        return {
            "context_switches": self._context_switches,
            "ready_queue_size": len(self._ready_queue),
            "total_processes": len(self._processes),
            "running": self._running.pid if self._running else None,
        }


class MemoryManager:
    """内存管理器（分页）。"""

    def __init__(self, total_memory: int = 4 * 1024 * 1024 * 1024,
                 page_size: int = 4096):
        self.total_memory = total_memory
        self.page_size = page_size
        self.free_frames = total_memory // page_size
        self.used_frames = 0
        self._frame_table: dict[int, MemoryPage] = {}
        self._page_table: dict[int, list[MemoryPage]] = {}
        self._lock = threading.Lock()
        self._swap_space: dict[int, bytes] = {}

    def allocate(self, pid: int, size: int,
                    protection: MemoryProtection = MemoryProtection.PRIVATE
                    ) -> list[int]:
        with self._lock:
            pages = (size + self.page_size - 1) // self.page_size
            page_frames = []
            for i in range(pages):
                if self.free_frames > 0:
                    frame = self._allocate_frame()
                    page = MemoryPage(
                        frame_number=frame,
                        page_number=i,
                        protection=protection,
                    )
                    if pid not in self._page_table:
                        self._page_table[pid] = []
                    self._page_table[pid].append(page)
                    page_frames.append(frame)
                    self.free_frames -= 1
                    self.used_frames += 1
            return page_frames

    def _allocate_frame(self) -> int:
        for frame in range(self.total_memory // self.page_size):
            if frame not in self._frame_table:
                self._frame_table[frame] = MemoryPage(
                    frame_number=frame, page_number=0
                )
                return frame
        return -1

    def deallocate(self, pid: int, frames: list[int]) -> None:
        with self._lock:
            for frame in frames:
                self._frame_table.pop(frame, None)
                self.free_frames += 1
                self.used_frames -= 1

    def read(self, pid: int, address: int,
                size: int) -> bytes:
        pages = self._page_table.get(pid, [])
        result = b""
        for i in range(size):
            page_idx = (address + i) // self.page_size
            (address + i) % self.page_size
            if page_idx < len(pages):
                frame = pages[page_idx].frame_number
                result += bytes([frame & 0xFF])
            else:
                result += b"\x00"
        return result[:size]

    def write(self, pid: int, address: int,
                 data: bytes) -> int:
        return len(data)

    def protect(self, pid: int, address: int,
                size: int,
                protection: MemoryProtection) -> None:
        with self._lock:
            pages = self._page_table.get(pid, [])
            start = address // self.page_size
            end = (address + size - 1) // self.page_size
            for i in range(start, min(end + 1, len(pages))):
                pages[i].protection = protection

    def get_usage(self) -> dict[str, int]:
        return {
            "total_frames": self.total_memory // self.page_size,
            "used_frames": self.used_frames,
            "free_frames": self.free_frames,
            "page_faults": 0,
        }


class FileSystem:
    """文件系统（带索引节点）。"""

    def __init__(self):
        self._files: dict[str, bytes] = {}
        self._directories: dict[str, dict[str, Any]] = {}
        self._inodes: dict[int, Inode] = {}
        self._fds: dict[int, FileDescriptor] = {}
        self._next_fd = 0
        self._next_inode = 1
        self._root = "/"
        self._cwd = "/"
        self._lock = threading.Lock()
        self._mounts: dict[str, str] = {}

    def open(self, path: str, mode: str = "r") -> int:
        with self._lock:
            fd = self._next_fd
            self._next_fd += 1
            if path not in self._files:
                self._files[path] = b""
            inode = self._get_inode(path)
            self._fds[fd] = FileDescriptor(
                fd=fd, inode=inode, mode=mode,
                offset=0,
            )
            return fd

    def read(self, fd: int, size: int = -1) -> bytes:
        fdesc = self._fds.get(fd)
        if not fdesc:
            return b""
        content = self._files.get(fdesc.inode.file_type.value, b"")
        if size == -1:
            return content[fdesc.offset:]
        result = content[fdesc.offset:fdesc.offset + size]
        fdesc.offset += len(result)
        return result

    def write(self, fd: int, data: bytes) -> int:
        fdesc = self._fds.get(fd)
        if not fdesc:
            return 0
        self._files[fdesc.inode.file_type.value] = data
        fdesc.inode.size = len(data)
        return len(data)

    def close(self, fd: int) -> bool:
        if fd in self._fds:
            del self._fds[fd]
            return True
        return False

    def mkdir(self, path: str) -> bool:
        with self._lock:
            if path not in self._directories:
                self._directories[path] = {"entries": {}}
                return True
        return False

    def exists(self, path: str) -> bool:
        return path in self._files or path in self._directories

    def remove(self, path: str) -> bool:
        with self._lock:
            if path in self._files:
                del self._files[path]
                return True
            if path in self._directories:
                del self._directories[path]
                return True
        return False

    def rename(self, old_path: str, new_path: str) -> bool:
        with self._lock:
            if old_path in self._files:
                self._files[new_path] = self._files.pop(old_path)
                return True
        return False

    def list_dir(self, path: str = "/") -> list[str]:
        return list(self._directories.get(path, {}).get("entries", {}).keys())

    def _get_inode(self, path: str) -> Inode:
        inode_num = self._next_inode
        self._next_inode += 1
        inode = Inode(inode_number=inode_num,
                       file_type=FileType.REGULAR)
        self._inodes[inode_num] = inode
        return inode

    def stat(self, path: str) -> Inode | None:
        return self._inodes.get(self._get_inode(path).inode_number)


class NetworkStack:
    """网络协议栈（TCP/IP）。"""

    def __init__(self):
        self._sockets: dict[int, dict[str, Any]] = {}
        self._next_fd = 0
        self._connections: dict[int, dict[str, Any]] = {}
        self._routes: dict[str, str] = {}
        self._arp_table: dict[str, str] = {}
        self._dns_cache: dict[str, str] = {}
        self._tcp_states: dict[int, SocketState] = {}
        self._lock = threading.Lock()
        self._mtu = 1500
        self._ip_address = "0.0.0.0"
        self._subnet_mask = "0.0.0.0"
        self._gateway = "0.0.0.0"

    def socket(self, sock_type: str = "stream",
                  protocol: str = "tcp") -> int:
        with self._lock:
            fd = self._next_fd
            self._next_fd += 1
            self._sockets[fd] = {
                "type": sock_type, "protocol": protocol,
                "state": SocketState.CLOSED,
                "local_addr": "0.0.0.0",
                "local_port": 0,
                "remote_addr": "",
                "remote_port": 0,
            }
            return fd

    def bind(self, fd: int, address: str, port: int) -> bool:
        sock = self._sockets.get(fd)
        if sock:
            sock["local_addr"] = address
            sock["local_port"] = port
            return True
        return False

    def listen(self, fd: int, backlog: int = 5) -> bool:
        sock = self._sockets.get(fd)
        if sock:
            sock["state"] = SocketState.LISTEN
            return True
        return False

    def accept(self, fd: int) -> int | None:
        sock = self._sockets.get(fd)
        if sock and sock["state"] == SocketState.LISTEN:
            return self._next_fd  # New connection FD
        return None

    def connect(self, fd: int, address: str,
                   port: int) -> bool:
        sock = self._sockets.get(fd)
        if sock:
            sock["remote_addr"] = address
            sock["remote_port"] = port
            sock["state"] = SocketState.ESTABLISHED
            return True
        return False

    def send(self, fd: int, data: bytes) -> int:
        sock = self._sockets.get(fd)
        if sock:
            return len(data)
        return 0

    def recv(self, fd: int, size: int = 4096) -> bytes:
        sock = self._sockets.get(fd)
        if sock:
            return b""
        return b""

    def close(self, fd: int) -> bool:
        if fd in self._sockets:
            del self._sockets[fd]
            return True
        return False

    def getaddrinfo(self, hostname: str
                         ) -> tuple[str, int] | None:
        return self._dns_cache.get(hostname)

    def set_ip(self, ip: str, mask: str, gateway: str) -> None:
        self._ip_address = ip
        self._subnet_mask = mask
        self._gateway = gateway


class DeviceDriver:
    """设备驱动框架。"""

    def __init__(self):
        self._drivers: dict[str, Any] = {}
        self._devices: dict[str, dict[str, Any]] = {}
        self._interrupts: dict[int, Callable] = {}
        self._dma_channels: dict[int, Any] = {}
        self._lock = threading.Lock()

    def register_driver(self, name: str,
                           driver: Any) -> bool:
        self._drivers[name] = driver
        return True

    def get_driver(self, name: str) -> Any | None:
        return self._drivers.get(name)

    def register_device(self, name: str,
                           driver: str,
                           device_id: str) -> bool:
        self._devices[name] = {
            "driver": driver, "device_id": device_id,
        }
        return True

    def register_interrupt(self, irq: int,
                               handler: Callable) -> bool:
        self._interrupts[irq] = handler
        return True

    def trigger_interrupt(self, irq: int) -> bool:
        handler = self._interrupts.get(irq)
        if handler:
            handler()
            return True
        return False

    def dma_transfer(self, channel: int,
                        data: bytes) -> bool:
        self._dma_channels[channel] = data
        return True


class IPC:
    """进程间通信。"""

    def __init__(self):
        self._pipes: dict[str, Any] = {}
        self._shared_mem: dict[str, Any] = {}
        self._semaphores: dict[str, Any] = {}
        self._message_queues: dict[str, Any] = {}
        self._lock = threading.Lock()

    def create_pipe(self, name: str) -> bool:
        with self._lock:
            self._pipes[name] = {"read_end": None, "write_end": None}
            return True

    def create_shared_memory(self, name: str,
                                size: int) -> bool:
        with self._lock:
            self._shared_mem[name] = {"size": size, "data": b""}
            return True

    def create_semaphore(self, name: str,
                            initial: int = 1) -> bool:
        with self._lock:
            self._semaphores[name] = {"value": initial}
            return True

    def create_message_queue(self, name: str) -> bool:
        with self._lock:
            self._message_queues[name] = {"messages": []}
            return True

    def send_message(self, queue_name: str,
                         message: str) -> bool:
        q = self._message_queues.get(queue_name)
        if q:
            q["messages"].append(message)
            return True
        return False

    def receive_message(self, queue_name: str
                            ) -> str | None:
        q = self._message_queues.get(queue_name)
        if q and q["messages"]:
            return q["messages"].pop(0)
        return None


class SignalManager:
    """信号管理器。"""

    def __init__(self):
        self._handlers: dict[int, Callable] = {}
        self._default_signal: int | None = None
        self._last_action: str | None = None
        self._terminated: dict[int, int] = {}

    def set_handler(self, sig: int, handler: Callable) -> None:
        self._handlers[sig] = handler

    def send_signal(self, pid: int, sig: int) -> bool:
        handler = self._handlers.get(sig)
        if handler:
            handler(pid)
            return True
        action = self.default_action(sig)
        self._default_handler(sig)
        if action == "TERMINATE":
            self._terminated[sig] = pid
        return True

    def _default_handler(self, signal: int) -> None:
        """默认信号处理：记录信号并按默认动作处置。"""
        self._default_signal = signal
        self._last_action = self.default_action(signal)

    def default_action(self, sig: int) -> str:
        if sig in (2, 9, 15):       # SIGINT / SIGKILL / SIGTERM
            return "TERMINATE"
        if sig == 17:               # SIGCHLD
            return "IGNORE"
        if sig == 19:               # SIGSTOP
            return "STOP"
        if sig in (1, 10):          # SIGHUP / SIGUSR1
            return "CORE"
        return "TERMINATE"


def create_scheduler(
    policy: SchedulingPolicy = SchedulingPolicy.CFS
) -> Scheduler:
    return Scheduler(policy=policy)


def create_memory_manager(
    total: int = 4 * 1024 * 1024 * 1024
) -> MemoryManager:
    return MemoryManager(total_memory=total)


def create_file_system() -> FileSystem:
    return FileSystem()


def create_network_stack() -> NetworkStack:
    return NetworkStack()


def create_device_driver() -> DeviceDriver:
    return DeviceDriver()


def create_ipc() -> IPC:
    return IPC()


def create_signal_manager() -> SignalManager:
    return SignalManager()


# ============================================================
# 内置注册
# ============================================================

def _register_os_kernel(builtins: dict) -> None:
    builtins["创建调度器"] = create_scheduler
    builtins["创建内存管理器"] = create_memory_manager
    builtins["创建文件系统"] = create_file_system
    builtins["创建网络栈"] = create_network_stack
    builtins["创建设备驱动"] = create_device_driver
    builtins["创建进程间通信"] = create_ipc
    builtins["创建信号管理器"] = create_signal_manager


def _os_kernel_names() -> list[str]:
    return ["创建调度器", "创建内存管理器",
            "创建文件系统", "创建网络栈",
            "创建设备驱动", "创建进程间通信",
            "创建信号管理器"]


__all__ = [
    "ProcessState", "SchedulingPolicy",
    "MemoryProtection", "FileType", "SocketState",
    "Task", "ProcessContext", "MemoryPage",
    "Inode", "FileDescriptor",
    "Scheduler", "MemoryManager", "FileSystem",
    "NetworkStack", "DeviceDriver", "IPC", "SignalManager",
    "create_scheduler", "create_memory_manager",
    "create_file_system", "create_network_stack",
    "create_device_driver", "create_ipc",
    "create_signal_manager",
    "_register_os_kernel", "_os_kernel_names",
]
