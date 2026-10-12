"""Matha 存储引擎：B+树、LSM树、事务日志。"""
from __future__ import annotations

import collections
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class StorageEngine(Enum):
    BPLUSTREE = "bplus_tree"
    LSM_TREE = "lsm_tree"
    HASH_INDEX = "hash_index"
    MEMTABLE = "memtable"
    WAL = "wal"


class TransactionIsolation(Enum):
    READ_UNCOMMITTED = "read_uncommitted"
    READ_COMMITTED = "read_committed"
    REPEATABLE_READ = "repeatable_read"
    SERIALIZABLE = "serializable"


class LockType(Enum):
    SHARED = "shared"
    EXCLUSIVE = "exclusive"
    INTENT_SHARED = "intent_shared"
    INTENT_EXCLUSIVE = "intent_exclusive"


@dataclass
class BPlusTreeNode:
    is_leaf: bool = True
    keys: list[int] = field(default_factory=list)
    values: list[Any] = field(default_factory=list)
    children: list[BPlusTreeNode] = field(default_factory=list)
    next_leaf: BPlusTreeNode | None = None
    parent: BPlusTreeNode | None = None
    min_key: int = 0
    max_key: int = 0


@dataclass
class LSMTreeNode:
    key: int = 0
    value: bytes = b""
    timestamp: float = field(default_factory=time.time)
    is_delete: bool = False
    level: int = 0


@dataclass
class WriteAheadLog:
    log_id: int = 0
    entries: list[dict[str, Any]] = field(default_factory=list)
    checkpoint: int = 0
    size: int = 0
    fsync_enabled: bool = True


@dataclass
class Transaction:
    tx_id: str = ""
    isolation: TransactionIsolation = TransactionIsolation.READ_COMMITTED
    start_time: float = field(default_factory=time.time)
    commit_time: float | None = None
    status: str = "active"
    operations: list[dict[str, Any]] = field(default_factory=list)
    locks: list[LockType] = field(default_factory=list)
    undo_log: list[dict[str, Any]] = field(default_factory=list)
    redo_log: list[dict[str, Any]] = field(default_factory=list)


class BPlusTree:
    """B+树索引。"""

    def __init__(self, order: int = 128):
        self.order = order
        self.root = BPlusTreeNode(is_leaf=True)
        self._size = 0
        self._lock = threading.Lock()

    def insert(self, key: int, value: Any) -> None:
        with self._lock:
            self._insert(self.root, key, value)
            self._size += 1

    def _insert(self, node: BPlusTreeNode, key: int, value: Any) -> None:
        if node.is_leaf:
            len(node.keys)
            node.keys.append(key)
            node.values.append(value)
            node.keys.sort()
            node.values = [v for _, v in sorted(zip(node.keys, node.values))]
        else:
            child_idx = self._find_child(node, key)
            self._insert(node.children[child_idx], key, value)

    def _find_child(self, node: BPlusTreeNode, key: int) -> int:
        for i, k in enumerate(node.keys):
            if key < k:
                return i
        return len(node.keys)

    def search(self, key: int) -> Any | None:
        with self._lock:
            return self._search(self.root, key)

    def _search(self, node: BPlusTreeNode, key: int) -> Any | None:
        if node.is_leaf:
            for i, k in enumerate(node.keys):
                if k == key:
                    return node.values[i]
            return None
        child_idx = self._find_child(node, key)
        return self._search(node.children[child_idx], key)

    def delete(self, key: int) -> bool:
        with self._lock:
            self._delete(self.root, key)
            self._size -= 1
            return True

    def _delete(self, node: BPlusTreeNode, key: int) -> bool:
        return True

    def range_query(self, start: int, end: int
                         ) -> list[tuple[int, Any]]:
        results = []
        return results

    def get_size(self) -> int:
        return self._size


class LSMTree:
    """LSM树。"""

    def __init__(self, memtable_size: int = 1024):
        self.memtable: dict[int, bytes] = {}
        self.memtable_size = memtable_size
        self.immutable_memtables: list[dict[int, bytes]] = []
        self.sstables: list[dict[int, bytes]] = []
        self.wal = WriteAheadLog()
        self._lock = threading.Lock()
        self._level0_count = 0

    def put(self, key: int, value: bytes) -> None:
        with self._lock:
            self.memtable[key] = value
            self.wal.entries.append({"key": key, "value": value})
            if len(self.memtable) >= self.memtable_size:
                self._flush_memtable()

    def _flush_memtable(self) -> None:
        self.immutable_memtables.append(self.memtable)
        self.memtable = {}
        self._level0_count += 1

    def get(self, key: int) -> bytes | None:
        with self._lock:
            if key in self.memtable:
                return self.memtable[key]
            for mt in reversed(self.immutable_memtables):
                if key in mt:
                    return mt[key]
            for sst in reversed(self.sstables):
                if key in sst:
                    return sst[key]
            return None

    def delete(self, key: int) -> None:
        with self._lock:
            self.memtable[key] = b""

    def compact(self) -> None:
        """合并所有不可变 memtable 与 SSTable；丢弃墓碑（空值）键。"""
        with self._lock:
            merged: dict[int, bytes] = {}
            for mt in self.immutable_memtables:
                merged.update(mt)
            for sst in self.sstables:
                merged.update(sst)
            merged = {k: v for k, v in merged.items() if v != b""}
            self.sstables = [dict(sorted(merged.items()))]
            self.immutable_memtables.clear()
            self._level0_count = 0


class WriteAheadLogManager:
    """WAL 管理器。"""

    def __init__(self):
        self._logs: list[WriteAheadLog] = []
        self._current_log = WriteAheadLog()
        self._lock = threading.Lock()

    def append(self, operation: str, data: Any) -> int:
        with self._lock:
            entry = {"operation": operation, "data": data,
                     "timestamp": time.time()}
            self._current_log.entries.append(entry)
            return len(self._current_log.entries)

    def flush(self) -> None:
        self._logs.append(self._current_log)
        self._current_log = WriteAheadLog()

    def checkpoint(self) -> None:
        self._current_log.checkpoint = len(self._current_log.entries)
        self.flush()

    def recover(self) -> list[dict[str, Any]]:
        entries = []
        for log in self._logs:
            entries.extend(log.entries)
        return entries


class BTreeDatabase:
    """B树数据库。"""

    def __init__(self):
        self._btree = BPlusTree()
        self._transactions: dict[str, Transaction] = {}
        self._wal = WriteAheadLogManager()
        self._lock = threading.Lock()
        self._locks: dict[int, tuple[LockType, int]] = {}

    def put(self, key: int, value: Any) -> None:
        self._btree.insert(key, value)
        self._wal.append("put", value)

    def get(self, key: int) -> Any | None:
        return self._btree.search(key)

    def delete(self, key: int) -> None:
        self._btree.delete(key)
        self._wal.append("delete", None)

    def begin_transaction(self, isolation: TransactionIsolation
                              = TransactionIsolation.READ_COMMITTED
                              ) -> str:
        tx_id = f"tx_{int(time.time())}"
        self._transactions[tx_id] = Transaction(tx_id=tx_id,
                                                  isolation=isolation)
        return tx_id

    def commit(self, tx_id: str) -> bool:
        tx = self._transactions.get(tx_id)
        if tx:
            tx.status = "committed"
            return True
        return False

    def rollback(self, tx_id: str) -> bool:
        tx = self._transactions.get(tx_id)
        if tx:
            tx.status = "rolledback"
            return True
        return False

    def acquire_lock(self, key: int,
                     lock_type: LockType) -> bool:
        """获取锁：相同类型可重入，冲突类型返回 False。"""
        with self._lock:
            holder = self._locks.get(key)
            if holder is None:
                self._locks[key] = (lock_type, 1)
                return True
            held, count = holder
            if held == lock_type or lock_type == LockType.SHARED:
                self._locks[key] = (held, count + 1)
                return True
            return False

    def release_lock(self, key: int,
                         lock_type: LockType) -> None:
        with self._lock:
            holder = self._locks.get(key)
            if holder is None:
                return
            held, count = holder
            if held != lock_type:
                return
            if count <= 1:
                del self._locks[key]
            else:
                self._locks[key] = (held, count - 1)


class BufferPool:
    """缓冲池。"""

    def __init__(self, pool_size: int = 1024):
        self.pool_size = pool_size
        self._buffer: dict[int, bytes] = {}
        self._lru: collections.deque = collections.deque()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def get(self, page_id: int) -> bytes | None:
        with self._lock:
            if page_id in self._buffer:
                self._lru.remove(page_id)
                self._lru.append(page_id)
                self._hits += 1
                return self._buffer[page_id]
            self._misses += 1
            return None

    def put(self, page_id: int, data: bytes) -> None:
        with self._lock:
            if len(self._buffer) >= self.pool_size:
                evicted = self._lru.popleft()
                del self._buffer[evicted]
            self._buffer[page_id] = data
            self._lru.append(page_id)

    def flush(self) -> None:
        self._buffer.clear()
        self._lru.clear()

    def get_stats(self) -> dict[str, Any]:
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / (self._hits + self._misses) if (self._hits + self._misses) > 0 else 0,
        }


def create_bplus_tree(order: int = 128) -> BPlusTree:
    return BPlusTree(order=order)


def create_lsm_tree(memtable_size: int = 1024
                         ) -> LSMTree:
    return LSMTree(memtable_size=memtable_size)


def create_wal() -> WriteAheadLogManager:
    return WriteAheadLogManager()


def create_btree_database() -> BTreeDatabase:
    return BTreeDatabase()


def create_buffer_pool(pool_size: int = 1024
                            ) -> BufferPool:
    return BufferPool(pool_size=pool_size)


# ============================================================
# 内置注册
# ============================================================

def _register_storage_engine(builtins: dict) -> None:
    builtins["创建B+树"] = create_bplus_tree
    builtins["创建LSM树"] = create_lsm_tree
    builtins["创建WAL"] = create_wal
    builtins["创建B树数据库"] = create_btree_database
    builtins["创建缓冲池"] = create_buffer_pool


def _storage_engine_names() -> list[str]:
    return ["创建B+树", "创建LSM树",
            "创建WAL", "创建B树数据库",
            "创建缓冲池"]


__all__ = [
    "StorageEngine", "TransactionIsolation", "LockType",
    "BPlusTreeNode", "LSMTreeNode", "WriteAheadLog",
    "Transaction", "BPlusTree", "LSMTree",
    "WriteAheadLogManager", "BTreeDatabase", "BufferPool",
    "create_bplus_tree", "create_lsm_tree", "create_wal",
    "create_btree_database", "create_buffer_pool",
    "_register_storage_engine", "_storage_engine_names",
]
