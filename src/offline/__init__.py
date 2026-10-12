"""Matha 离线存储模块

提供离线模式下的数据持久化功能：
  - SQLite 本地存储
  - 同步管理
  - 冲突解决
"""
from __future__ import annotations

from .mobile_api_client import (
    APIResponse,
    MathaAPIClient,
    SyncRecord,
    SyncStatus,
    get_api_client,
    set_api_client,
)
from .sqlite_storage import (
    HistoryRecord,
    SQLiteStorage,
    get_storage,
)
from .sync import (
    ConflictStrategy,
    OfflineSyncManager,
    SyncConflict,
    SyncConflictResolver,
    SyncLogger,
)

__all__ = [
    'SQLiteStorage',
    'HistoryRecord',
    'get_storage',
    'SyncConflictResolver',
    'ConflictStrategy',
    'SyncConflict',
    'SyncLogger',
    'OfflineSyncManager',
    'MathaAPIClient',
    'APIResponse',
    'SyncStatus',
    'SyncRecord',
    'get_api_client',
    'set_api_client',
]
