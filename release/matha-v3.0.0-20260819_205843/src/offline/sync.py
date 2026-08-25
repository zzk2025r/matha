# -*- coding: utf-8 -*-
"""Matha 离线同步模块

提供离线模式下的数据同步功能：
  - 冲突检测与解决
  - 增量同步
  - 同步日志
  - 同步队列管理
"""
from __future__ import annotations
import time
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


logger = logging.getLogger(__name__)


class ConflictStrategy(Enum):
    """冲突解决策略"""
    LAST_WRITE_WINS = "last_write_wins"      # 最后写入优先
    FIRST_WRITE_WINS = "first_write_wins"     # 最先写入优先
    MERGE = "merge"                           # 合并策略
    MANUAL = "manual"                         # 手动选择


@dataclass
class SyncConflict:
    """同步冲突"""
    id: str
    record_type: str
    local_data: Dict[str, Any]
    remote_data: Dict[str, Any]
    local_timestamp: float
    remote_timestamp: float
    strategy: ConflictStrategy
    resolved: bool = False
    resolution: Optional[str] = None


@dataclass
class SyncLog:
    """同步日志"""
    timestamp: str
    action: str
    record_type: str
    record_id: str
    status: str  # 'pending', 'synced', 'conflict', 'failed'
    details: str = ""
    retry_count: int = 0


class SyncConflictResolver:
    """
    同步冲突解决器

    支持的策略：
    1. LAST_WRITE_WINS - 最后写入优先（时间戳比较）
    2. FIRST_WRITE_WINS - 最先写入优先
    3. MERGE - 智能合并（深层合并字典）
    4. MANUAL - 手动选择
    """

    def __init__(self, default_strategy: ConflictStrategy = ConflictStrategy.LAST_WRITE_WINS):
        self._default_strategy = default_strategy
        self._conflict_callbacks: List[Callable[[SyncConflict], None]] = []
        self._resolved_conflicts: Dict[str, str] = {}  # id -> resolution
        self._conflict_history: List[SyncConflict] = []

    def register_callback(self, callback: Callable[[SyncConflict], None]) -> None:
        """注册冲突解决回调"""
        self._conflict_callbacks.append(callback)

    def resolve(self, conflict: SyncConflict) -> Optional[Dict[str, Any]]:
        """
        解决冲突

        Args:
            conflict: 冲突对象

        Returns:
            解决后的数据，或 None（需要手动处理）
        """
        # 检查是否有预解决的冲突
        if conflict.id in self._resolved_conflicts:
            resolution = self._resolved_conflicts[conflict.id]
            logger.info(f"使用预解决策略: {resolution}")
            conflict.resolved = True
            conflict.resolution = resolution
            return self._apply_resolution(conflict, resolution)

        # 使用配置的策略解决
        strategy = conflict.strategy or self._default_strategy
        logger.info(f"解决冲突 {conflict.id}: 策略={strategy.value}")

        try:
            if strategy == ConflictStrategy.LAST_WRITE_WINS:
                result = self._last_write_wins(conflict)
            elif strategy == ConflictStrategy.FIRST_WRITE_WINS:
                result = self._first_write_wins(conflict)
            elif strategy == ConflictStrategy.MERGE:
                result = self._merge(conflict)
            elif strategy == ConflictStrategy.MANUAL:
                result = None
            else:
                result = self._last_write_wins(conflict)

            if result is not None:
                conflict.resolved = True
                conflict.resolution = strategy.value
                self._notify_callbacks(conflict)

        except Exception as e:
            logger.error(f"冲突解决失败: {e}")
            conflict.resolved = False

        self._conflict_history.append(conflict)
        return result

    def _last_write_wins(self, conflict: SyncConflict) -> Optional[Dict[str, Any]]:
        """最后写入优先策略"""
        if conflict.remote_timestamp > conflict.local_timestamp:
            logger.info(f"冲突解决: 远程数据更新 (remote:{conflict.remote_timestamp} > local:{conflict.local_timestamp})")
            return conflict.remote_data
        else:
            logger.info(f"冲突解决: 本地数据更新 (local:{conflict.local_timestamp} >= remote:{conflict.remote_timestamp})")
            return conflict.local_data

    def _first_write_wins(self, conflict: SyncConflict) -> Optional[Dict[str, Any]]:
        """最先写入优先策略"""
        if conflict.local_timestamp < conflict.remote_timestamp:
            logger.info(f"冲突解决: 保留本地数据 (local:{conflict.local_timestamp} < remote:{conflict.remote_timestamp})")
            return conflict.local_data
        else:
            logger.info(f"冲突解决: 使用远程数据 (remote:{conflict.remote_timestamp} <= local:{conflict.local_timestamp})")
            return conflict.remote_data

    def _merge(self, conflict: SyncConflict) -> Optional[Dict[str, Any]]:
        """
        智能合并策略

        合并规则：
        - 字典：递归合并，本地优先
        - 列表：合并去重（基于 ID）
        - 标量：本地优先
        """
        merged = self._deep_merge(conflict.local_data, conflict.remote_data)
        logger.info(f"冲突解决: 合并数据完成")
        return merged

    def _deep_merge(self, local: Dict[str, Any], remote: Dict[str, Any]) -> Dict[str, Any]:
        """
        深层合并两个字典

        规则：
        - 嵌套字典：递归合并
        - 列表：按 ID 合并去重
        - 其他：本地优先
        """
        result = local.copy()

        for key, remote_value in remote.items():
            if key in result:
                local_value = result[key]

                # 都是字典：递归合并
                if isinstance(local_value, dict) and isinstance(remote_value, dict):
                    result[key] = self._deep_merge(local_value, remote_value)
                # 都是列表：合并去重
                elif isinstance(local_value, list) and isinstance(remote_value, list):
                    result[key] = self._merge_lists(local_value, remote_value)
                # 其他：本地优先
                else:
                    result[key] = local_value
            else:
                result[key] = remote_value

        return result

    def _merge_lists(self, local: List[Any], remote: List[Any]) -> List[Any]:
        """合并列表，按 ID 去重"""
        seen_ids = set()
        merged = []

        # 先添加本地列表
        for item in local:
            if isinstance(item, dict) and 'id' in item:
                if item['id'] not in seen_ids:
                    seen_ids.add(item['id'])
                    merged.append(item)
            else:
                merged.append(item)

        # 添加远程列表中新增的项目
        for item in remote:
            if isinstance(item, dict) and 'id' in item:
                if item['id'] not in seen_ids:
                    seen_ids.add(item['id'])
                    merged.append(item)
            elif item not in merged:
                merged.append(item)

        return merged

    def manual_resolve(self, conflict_id: str, resolution: str, resolved_data: Dict[str, Any]) -> None:
        """手动解决冲突"""
        self._resolved_conflicts[conflict_id] = resolution
        logger.info(f"手动解决冲突 {conflict_id}: {resolution}")

    def _notify_callbacks(self, conflict: SyncConflict) -> None:
        """通知所有回调"""
        for callback in self._conflict_callbacks:
            try:
                callback(conflict)
            except Exception as e:
                logger.error(f"冲突回调执行失败: {e}")

    def get_conflict_history(self, limit: int = 50) -> List[SyncConflict]:
        """获取冲突历史"""
        return self._conflict_history[-limit:]

    def clear_history(self) -> None:
        """清空冲突历史"""
        self._conflict_history.clear()
        self._resolved_conflicts.clear()

    def _apply_resolution(self, conflict: SyncConflict, resolution: str) -> Optional[Dict[str, Any]]:
        """应用预解决的策略"""
        if resolution == ConflictStrategy.LAST_WRITE_WINS.value:
            return self._last_write_wins(conflict)
        elif resolution == ConflictStrategy.FIRST_WRITE_WINS.value:
            return self._first_write_wins(conflict)
        elif resolution == ConflictStrategy.MERGE.value:
            return self._merge(conflict)
        return None


class SyncLogger:
    """
    同步日志记录器

    记录所有同步操作的详细信息，用于调试和问题排查
    """

    def __init__(self, log_file: Optional[str] = None):
        self._log_file = log_file or str(Path.home() / '.matha' / 'sync_log.jsonl')
        self._logs: List[SyncLog] = []
        Path(self._log_file).parent.mkdir(parents=True, exist_ok=True)

    def log(self, action: str, record_type: str, record_id: str,
            status: str, details: str = "") -> None:
        """
        记录同步日志

        Args:
            action: 操作类型 (push, pull, merge, conflict)
            record_type: 记录类型 (history, preference, cache)
            record_id: 记录 ID
            status: 状态 (pending, synced, conflict, failed)
            details: 详细信息
        """
        log_entry = SyncLog(
            timestamp=datetime.now().isoformat(),
            action=action,
            record_type=record_type,
            record_id=record_id,
            status=status,
            details=details,
        )
        self._logs.append(log_entry)
        self._write_to_file(log_entry)
        logger.info(f"[SYNC] {action} {record_type}:{record_id} -> {status}: {details}")

    def _write_to_file(self, log: SyncLog) -> None:
        """写入日志文件"""
        try:
            with open(self._log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps({
                    'timestamp': log.timestamp,
                    'action': log.action,
                    'record_type': log.record_type,
                    'record_id': log.record_id,
                    'status': log.status,
                    'details': log.details,
                }, ensure_ascii=False) + '\n')
        except Exception as e:
            logger.warning(f"写入日志文件失败: {e}")

    def get_logs(self, limit: int = 100, action: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取日志"""
        logs = self._logs[-limit:]
        if action:
            logs = [l for l in logs if l.action == action]
        return [
            {
                'timestamp': l.timestamp,
                'action': l.action,
                'record_type': l.record_type,
                'record_id': l.record_id,
                'status': l.status,
                'details': l.details,
            }
            for l in logs
        ]

    def clear_logs(self) -> None:
        """清空日志"""
        self._logs.clear()
        try:
            Path(self._log_file).unlink(missing_ok=True)
        except Exception:
            pass


class OfflineSyncManager:
    """
    离线同步管理器

    管理离线模式下的数据同步：
    - 同步队列管理
    - 冲突检测与解决
    - 增量同步
    - 同步日志记录
    """

    def __init__(
        self,
        resolver: Optional[SyncConflictResolver] = None,
        sync_logger: Optional[SyncLogger] = None,
        sync_interval: float = 60.0,
    ):
        self._resolver = resolver or SyncConflictResolver()
        self._logger = sync_logger or SyncLogger()
        self._sync_interval = sync_interval
        self._sync_queue: List[Dict[str, Any]] = []
        self._last_sync_time: float = 0
        self._is_syncing = False
        self._sync_callbacks: List[Callable[[str, str, str], None]] = []

    def register_callback(self, callback: Callable[[str, str, str], None]) -> None:
        """注册同步回调 (action, record_type, record_id)"""
        self._sync_callbacks.append(callback)

    def enqueue(self, action: str, record_type: str, record_id: str,
                data: Dict[str, Any], priority: int = 0) -> None:
        """
        将操作加入同步队列

        Args:
            action: 操作类型 (push, pull)
            record_type: 记录类型
            record_id: 记录 ID
            data: 数据
            priority: 优先级（越高越先处理）
        """
        self._sync_queue.append({
            'action': action,
            'record_type': record_type,
            'record_id': record_id,
            'data': data,
            'priority': priority,
            'timestamp': time.time(),
            'retry_count': 0,
        })
        # 按优先级排序
        self._sync_queue.sort(key=lambda x: (-x['priority'], x['timestamp']))
        self._logger.log(action, record_type, record_id, 'pending', '已加入同步队列')

    def process_queue(self, remote_storage: Any) -> List[Dict[str, Any]]:
        """
        处理同步队列

        Args:
            remote_storage: 远程存储接口

        Returns:
            处理结果列表
        """
        if self._is_syncing or not self._sync_queue:
            return []

        self._is_syncing = True
        results = []

        try:
            # 检查网络连接
            if not self._check_network():
                self._logger.log('sync', 'system', 'network', 'failed', '无网络连接')
                return results

            while self._sync_queue:
                item = self._sync_queue.pop(0)
                result = self._process_item(item, remote_storage)
                results.append(result)

                # 通知回调
                for cb in self._sync_callbacks:
                    try:
                        cb(item['action'], item['record_type'], item['record_id'])
                    except Exception as e:
                        logger.error(f"同步回调失败: {e}")

            self._last_sync_time = time.time()

        finally:
            self._is_syncing = False

        return results

    def _process_item(self, item: Dict[str, Any], remote_storage: Any) -> Dict[str, Any]:
        """处理单个同步项目"""
        action = item['action']
        record_type = item['record_type']
        record_id = item['record_id']

        try:
            if action == 'push':
                return self._push_item(item, remote_storage)
            elif action == 'pull':
                return self._pull_item(item, remote_storage)
            else:
                raise ValueError(f"未知操作类型: {action}")
        except Exception as e:
            item['retry_count'] += 1
            if item['retry_count'] >= 3:
                self._logger.log(action, record_type, record_id, 'failed', str(e))
                return {'success': False, 'error': str(e)}
            else:
                # 重新加入队列
                self._sync_queue.append(item)
                self._sync_queue.sort(key=lambda x: (-x['priority'], x['timestamp']))
                self._logger.log(action, record_type, record_id, 'pending', f'重试 {item["retry_count"]}/3')
                return {'success': False, 'error': str(e), 'retry': True}

    def _push_item(self, item: Dict[str, Any], remote_storage: Any) -> Dict[str, Any]:
        """推送数据到远程"""
        record_type = item['record_type']
        record_id = item['record_id']

        # 检查是否有远程版本
        remote_data = remote_storage.get(record_type, record_id) if remote_storage else None

        if remote_data:
            # 检测冲突
            local_data = item['data']
            if self._has_conflict(local_data, remote_data):
                conflict = SyncConflict(
                    id=f"{record_type}:{record_id}",
                    record_type=record_type,
                    local_data=local_data,
                    remote_data=remote_data,
                    local_timestamp=item['data'].get('timestamp', 0),
                    remote_timestamp=remote_data.get('timestamp', 0),
                    strategy=ConflictStrategy.LAST_WRITE_WINS,
                )
                resolved = self._resolver.resolve(conflict)
                if resolved:
                    remote_storage.save(record_type, record_id, resolved)
                    self._logger.log('push', record_type, record_id, 'conflict', '已解决')
                    return {'success': True, 'conflict_resolved': True}
                else:
                    self._logger.log('push', record_type, record_id, 'conflict', '需要手动解决')
                    return {'success': False, 'needs_manual': True}
            else:
                # 无冲突，直接更新
                remote_storage.save(record_type, record_id, item['data'])
                self._logger.log('push', record_type, record_id, 'synced', '推送成功')
                return {'success': True}
        else:
            # 远程不存在，直接创建
            remote_storage.save(record_type, record_id, item['data'])
            self._logger.log('push', record_type, record_id, 'synced', '创建成功')
            return {'success': True}

    def _pull_item(self, item: Dict[str, Any], remote_storage: Any) -> Dict[str, Any]:
        """从远程拉取数据"""
        record_type = item['record_type']
        record_id = item['record_id']

        if not remote_storage:
            return {'success': False, 'error': '远程存储不可用'}

        remote_data = remote_storage.get(record_type, record_id)
        if remote_data:
            # 检查冲突
            local_data = item.get('local_data', {})
            if local_data and self._has_conflict(local_data, remote_data):
                conflict = SyncConflict(
                    id=f"{record_type}:{record_id}",
                    record_type=record_type,
                    local_data=local_data,
                    remote_data=remote_data,
                    local_timestamp=local_data.get('timestamp', 0),
                    remote_timestamp=remote_data.get('timestamp', 0),
                    strategy=ConflictStrategy.LAST_WRITE_WINS,
                )
                resolved = self._resolver.resolve(conflict)
                if resolved:
                    self._logger.log('pull', record_type, record_id, 'conflict', '已解决')
                    return {'success': True, 'data': resolved, 'conflict_resolved': True}
                else:
                    self._logger.log('pull', record_type, record_id, 'conflict', '需要手动解决')
                    return {'success': False, 'needs_manual': True}
            else:
                self._logger.log('pull', record_type, record_id, 'synced', '拉取成功')
                return {'success': True, 'data': remote_data}
        else:
            return {'success': False, 'error': '远程数据不存在'}

    def _has_conflict(self, local: Dict[str, Any], remote: Dict[str, Any]) -> bool:
        """检测是否有冲突"""
        local_time = local.get('timestamp', 0)
        remote_time = remote.get('timestamp', 0)

        # 时间戳相同但内容不同
        if local_time == remote_time and local != remote:
            return True

        # 内容相同但时间戳不同（可能是同步延迟）
        if local == remote and local_time != remote_time:
            return False

        # 内容不同
        if local != remote:
            return True

        return False

    def _check_network(self) -> bool:
        """检查网络连接"""
        try:
            import urllib.request
            urllib.request.urlopen('https://www.google.com', timeout=3)
            return True
        except Exception:
            return False

    def get_queue_size(self) -> int:
        """获取队列大小"""
        return len(self._sync_queue)

    def is_syncing(self) -> bool:
        """是否正在同步"""
        return self._is_syncing

    def get_last_sync_time(self) -> float:
        """获取最后同步时间"""
        return self._last_sync_time

    def get_sync_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取同步日志"""
        return self._logger.get_logs(limit)

    def clear_queue(self) -> None:
        """清空同步队列"""
        self._sync_queue.clear()
