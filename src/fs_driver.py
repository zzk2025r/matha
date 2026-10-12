"""Matha 文件系统驱动：FAT/NTFS/ext4 兼容。"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class FSFormat(Enum):
    FAT16 = "fat16"
    FAT32 = "fat32"
    NTFS = "ntfs"
    EXT2 = "ext2"
    EXT3 = "ext3"
    EXT4 = "ext4"
    BTRFS = "btrfs"
    XFS = "xfs"
    ZFS = "zfs"


class FileAccess(Enum):
    READ = "r"
    WRITE = "w"
    READ_WRITE = "rw"
    APPEND = "a"
    EXECUTE = "x"


class FileLockType(Enum):
    LOCK_SH = "shared"
    LOCK_EX = "exclusive"
    LOCK_UN = "unlock"
    LOCK_NB = "nonblock"


@dataclass
class DirEntry:
    name: str = ""
    inode: int = 0
    file_type: str = "regular"
    size: int = 0
    permissions: str = "rw-r--r--"
    created: float = field(default_factory=time.time)
    modified: float = field(default_factory=time.time)
    accessed: float = field(default_factory=time.time)


@dataclass
class Inode:
    inode_number: int = 0
    file_type: str = "regular"
    size: int = 0
    permissions: str = "rw-r--r--"
    owner: str = "root"
    group: str = "root"
    created: float = field(default_factory=time.time)
    modified: float = field(default_factory=time.time)
    accessed: float = field(default_factory=time.time)
    direct_blocks: list[int] = field(default_factory=list)
    indirect_blocks: list[int] = field(default_factory=list)
    double_indirect: list[int] = field(default_factory=list)
    block_count: int = 0


@dataclass
class SuperBlock:
    fs_type: FSFormat = FSFormat.EXT4
    block_size: int = 4096
    total_blocks: int = 0
    free_blocks: int = 0
    total_inodes: int = 0
    free_inodes: int = 0
    magic: int = 0xEF53
    state: str = "clean"
    mount_count: int = 0
    max_mount_count: int = 30
    last_check: float = field(default_factory=time.time)
    check_interval: int = 180


@dataclass
class FileHandle:
    fd: int = 0
    inode: Inode = field(default_factory=Inode)
    offset: int = 0
    access_mode: FileAccess = FileAccess.READ
    lock_type: FileLockType = FileLockType.LOCK_UN
    reference_count: int = 1


class FileSystemDriver:
    """文件系统驱动。"""

    def __init__(self, format_type: FSFormat = FSFormat.EXT4):
        self.format = format_type
        self._superblock = SuperBlock(fs_type=format_type)
        self._inodes: dict[int, Inode] = {}
        self._directory: dict[str, DirEntry] = {}
        self._file_handles: dict[int, FileHandle] = {}
        self._mounts: dict[str, str] = {}
        self._buffers: dict[int, bytes] = {}
        self._next_inode = 1
        self._next_fd = 1
        self._lock = threading.Lock()
        self._blocks_used = 0
        self._journal: list[dict[str, Any]] = []
        self._path_inodes: dict[str, int] = {}

    def mount(self, device: str, mount_point: str) -> bool:
        with self._lock:
            self._mounts[mount_point] = device
            self._superblock.state = "mounted"
            return True

    def umount(self, mount_point: str) -> bool:
        with self._lock:
            if mount_point in self._mounts:
                del self._mounts[mount_point]
                return True
        return False

    def open(self, path: str, mode: str = "r") -> int:
        with self._lock:
            fd = self._next_fd
            self._next_fd += 1
            inode = self._get_inode(path)
            self._file_handles[fd] = FileHandle(
                fd=fd, inode=inode,
                access_mode=FileAccess.READ,
            )
            return fd

    def read(self, fd: int, size: int = -1) -> bytes:
        fh = self._file_handles.get(fd)
        if not fh:
            return b""
        content = self._read_inode(fh.inode)
        if size == -1:
            return content[fh.offset:]
        result = content[fh.offset:fh.offset + size]
        fh.offset += len(result)
        return result

    def write(self, fd: int, data: bytes) -> int:
        fh = self._file_handles.get(fd)
        if not fh:
            return 0
        self._write_inode(fh.inode, data)
        fh.inode.size = len(data)
        return len(data)

    def close(self, fd: int) -> bool:
        if fd in self._file_handles:
            del self._file_handles[fd]
            return True
        return False

    def mkdir(self, path: str) -> bool:
        with self._lock:
            if path not in self._directory:
                self._directory[path] = DirEntry(name=path)
                return True
        return False

    def exists(self, path: str) -> bool:
        return path in self._directory or path in self._inodes

    def remove(self, path: str) -> bool:
        with self._lock:
            if path in self._directory:
                del self._directory[path]
                return True
            if path in self._inodes:
                del self._inodes[path]
                return True
        return False

    def rename(self, old_path: str, new_path: str) -> bool:
        with self._lock:
            if old_path in self._directory:
                self._directory[new_path] = self._directory.pop(old_path)
                return True
            if old_path in self._inodes:
                self._inodes[new_path] = self._inodes.pop(old_path)
                return True
        return False

    def stat(self, path: str) -> Inode | None:
        if path in self._inodes:
            return self._inodes[path]
        return None

    def listdir(self, path: str = "/") -> list[str]:
        return [e.name for e in self._directory.values()
                if e.name.startswith(path + "/")]

    def fsync(self, fd: int) -> bool:
        return True

    def ftruncate(self, fd: int, length: int) -> bool:
        fh = self._file_handles.get(fd)
        if fh:
            fh.inode.size = length
            return True
        return False

    def lock(self, fd: int,
                lock_type: FileLockType) -> bool:
        fh = self._file_handles.get(fd)
        if fh:
            fh.lock_type = lock_type
            return True
        return False

    def unlock(self, fd: int) -> bool:
        fh = self._file_handles.get(fd)
        if fh:
            fh.lock_type = FileLockType.LOCK_UN
            return True
        return False

    def _get_inode(self, path: str) -> Inode:
        inode_num = self._path_inodes.get(path)
        if inode_num is not None and inode_num in self._inodes:
            return self._inodes[inode_num]
        inode = Inode(inode_number=self._next_inode)
        self._path_inodes[path] = self._next_inode
        self._next_inode += 1
        self._inodes[inode.inode_number] = inode
        return inode

    def _read_inode(self, inode: Inode) -> bytes:
        return self._buffers.get(inode.inode_number, b"")

    def _write_inode(self, inode: Inode, data: bytes) -> None:
        self._buffers[inode.inode_number] = data
        inode.size = len(data)
        inode.modified = time.time()
        block_size = self._superblock.block_size
        blocks = (len(data) + block_size - 1) // block_size
        start = self._blocks_used
        inode.direct_blocks = list(range(start, start + blocks))
        inode.block_count = len(inode.direct_blocks)
        self._blocks_used += blocks

    def get_stats(self) -> dict[str, Any]:
        return {
            "format": self.format.value,
            "total_inodes": self._superblock.total_inodes,
            "free_inodes": self._superblock.free_inodes,
            "blocks_used": self._blocks_used,
            "mounts": len(self._mounts),
        }


class PartitionManager:
    """分区管理器。"""

    def __init__(self):
        self._partitions: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def create_partition(self, device: str,
                             size: int,
                             fs_type: FSFormat = FSFormat.EXT4
                             ) -> bool:
        with self._lock:
            self._partitions[device] = {
                "size": size, "fs_type": fs_type,
                "created": time.time(),
            }
            return True

    def remove_partition(self, device: str) -> bool:
        with self._lock:
            if device in self._partitions:
                del self._partitions[device]
                return True
        return False

    def get_partition(self, device: str) -> dict[str, Any] | None:
        return self._partitions.get(device)

    def list_partitions(self) -> list[dict[str, Any]]:
        return list(self._partitions.values())


class VolumeManager:
    """卷管理器。"""

    def __init__(self):
        self._volumes: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def create_volume(self, name: str, size: int,
                           fs_type: FSFormat = FSFormat.EXT4
                           ) -> bool:
        with self._lock:
            self._volumes[name] = {
                "name": name, "size": size,
                "fs_type": fs_type, "status": "active",
            }
            return True

    def delete_volume(self, name: str) -> bool:
        with self._lock:
            if name in self._volumes:
                del self._volumes[name]
                return True
        return False

    def get_volume(self, name: str) -> dict[str, Any] | None:
        return self._volumes.get(name)


def create_fs_driver(
    format_type: FSFormat = FSFormat.EXT4
) -> FileSystemDriver:
    return FileSystemDriver(format_type=format_type)


def create_partition_manager() -> PartitionManager:
    return PartitionManager()


def create_volume_manager() -> VolumeManager:
    return VolumeManager()


# ============================================================
# 内置注册
# ============================================================

def _register_fs_driver(builtins: dict) -> None:
    builtins["创建文件系统驱动"] = create_fs_driver
    builtins["创建分区管理器"] = create_partition_manager
    builtins["创建卷管理器"] = create_volume_manager


def _fs_driver_names() -> list[str]:
    return ["创建文件系统驱动", "创建分区管理器",
            "创建卷管理器"]


__all__ = [
    "FSFormat", "FileAccess", "FileLockType",
    "DirEntry", "Inode", "SuperBlock",
    "FileHandle", "FileSystemDriver",
    "PartitionManager", "VolumeManager",
    "create_fs_driver", "create_partition_manager",
    "create_volume_manager",
    "_register_fs_driver", "_fs_driver_names",
]
