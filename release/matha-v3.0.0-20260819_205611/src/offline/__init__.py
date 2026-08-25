# -*- coding: utf-8 -*-
"""Matha 离线存储模块

提供离线模式下的数据持久化功能：
  - SQLite 本地存储
  - 同步管理
  - 冲突解决
"""
from __future__ import annotations

from offline.sqlite_storage import (
    SQLiteStorage,
    HistoryRecord,
    get_storage,
)

from offline.sync import (
    SyncConflictResolver,
    ConflictStrategy,
    SyncConflict,
    SyncLogger,
    OfflineSyncManager,
)

from offline.mobile_api_client import (
    MathaAPIClient,
    APIResponse,
    SyncStatus,
    SyncRecord,
    get_api_client,
    set_api_client,
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
