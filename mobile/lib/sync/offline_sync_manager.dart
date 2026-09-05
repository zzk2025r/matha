// Matha 离线同步管理器
// 管理离线模式下的数据同步和冲突解决

import 'dart:async';
import 'package:flutter/foundation.dart';
import '../database/math_database.dart';

class OfflineSyncManager extends ChangeNotifier {
  // 单例
  static final OfflineSyncManager _instance = OfflineSyncManager._internal();
  factory OfflineSyncManager() => _instance;
  OfflineSyncManager._internal();

  final MathDatabase _db = MathDatabase();

  // 状态
  bool _isOffline = false;
  bool _isSyncing = false;
  String _syncStatus = '未同步';
  int _pendingCount = 0;
  int _syncedCount = 0;
  int _failedCount = 0;

  // 冲突解决策略
  ConflictStrategy _conflictStrategy = ConflictStrategy.lastWriteWins;

  // 同步日志
  final List<SyncLogEntry> _syncLogs = [];

  // 同步完成回调
  Function(int syncedCount, int failedCount)? onSyncComplete;

  // 获取同步状态
  bool get isOffline => _isOffline;
  bool get isSyncing => _isSyncing;
  String get syncStatus => _syncStatus;
  int get pendingCount => _pendingCount;
  int get syncedCount => _syncedCount;
  int get failedCount => _failedCount;
  List<SyncLogEntry> get syncLogs => List.unmodifiable(_syncLogs);

  // 设置离线模式
  void setOfflineMode(bool isOffline) {
    _isOffline = isOffline;
    _syncStatus = isOffline ? '离线模式' : '在线模式';
    notifyListeners();
  }

  // 添加同步任务
  Future<void> addSyncTask(SyncTask task) async {
    await _db.addSyncTask(task.toMap());
    _pendingCount++;
    _addLog(task.recordType, '添加任务: ${task.recordId}', 'info');
    notifyListeners();
  }

  // 执行同步
  Future<void> performSync() async {
    if (_isSyncing) return;
    _isSyncing = true;
    _syncStatus = '同步中...';
    notifyListeners();

    try {
      final tasks = await _getPendingSyncTasks();
      for (final task in tasks) {
        await _syncTask(task);
      }
      _syncStatus = '同步完成';
      onSyncComplete?.call(_syncedCount, _failedCount);
    } catch (e) {
      _syncStatus = '同步失败';
      _addLog('sync', '同步失败: $e', 'error');
    } finally {
      _isSyncing = false;
      notifyListeners();
    }
  }

  // 同步单个任务
  Future<void> _syncTask(SyncTask task) async {
    try {
      if (task.action == 'push') {
        await _pushTask(task);
      } else {
        await _pullTask(task);
      }
    } catch (e) {
      _failedCount++;
      _addLog(task.recordType, '同步失败: ${task.recordId} - $e', 'error');
      await _db.updateSyncTaskStatus(id: task.id, status: 'failed');
    }
  }

  // 推送任务（本地 -> 远程）
  Future<void> _pushTask(SyncTask task) async {
    final remoteData = await _fetchRemoteData(task.recordType, task.recordId);

    if (remoteData != null) {
      if (_hasConflict(task.data, remoteData)) {
        await _resolveConflict(task, remoteData);
      } else {
        // 无冲突，直接更新
        await _saveToRemote(task.recordType, task.recordId, task.data);
        await _db.markSynced(task.id);
        _syncedCount++;
        _addLog(task.recordType, '推送成功: ${task.recordId}', 'success');
      }
    } else {
      // 远程不存在，直接创建
      await _saveToRemote(task.recordType, task.recordId, task.data);
      await _db.markSynced(task.id);
      _syncedCount++;
      _addLog(task.recordType, '创建成功: ${task.recordId}', 'success');
    }
  }

  // 拉取任务（远程 -> 本地）
  Future<void> _pullTask(SyncTask task) async {
    final remoteData = await _fetchRemoteData(task.recordType, task.recordId);

    if (remoteData != null) {
      if (_hasConflict(task.data, remoteData)) {
        await _resolveConflict(task, remoteData);
      } else {
        // 无冲突，更新本地
        await _saveToLocal(task.recordType, task.recordId, remoteData);
        await _db.markSynced(task.id);
        _syncedCount++;
        _addLog(task.recordType, '拉取成功: ${task.recordId}', 'success');
      }
    }
  }

  // 检测冲突
  bool _hasConflict(Map<String, dynamic> local, Map<String, dynamic> remote) {
    final localTime = local['timestamp'] ?? 0;
    final remoteTime = remote['timestamp'] ?? 0;

    // 时间戳相同但内容不同
    if (localTime == remoteTime && local != remote) {
      return true;
    }

    // 内容不同
    if (local != remote) {
      return true;
    }

    return false;
  }

  // 解决冲突
  Future<void> _resolveConflict(SyncTask task, Map<String, dynamic> remoteData) async {
    _addLog(task.recordType, '检测到冲突: ${task.recordId}', 'warning');

    switch (_conflictStrategy) {
      case ConflictStrategy.lastWriteWins:
        // 最后写入优先
        final localTime = (task.data['timestamp'] ?? 0) as num;
        final remoteTime = (remoteData['timestamp'] ?? 0) as num;
        if (remoteTime > localTime) {
          await _saveToLocal(task.recordType, task.recordId, remoteData);
          _addLog(task.recordType, '冲突解决: 使用远程数据', 'info');
        } else {
          await _saveToRemote(task.recordType, task.recordId, task.data);
          _addLog(task.recordType, '冲突解决: 使用本地数据', 'info');
        }
        break;

      case ConflictStrategy.manual:
        // 需要手动处理
        _addLog(task.recordType, '冲突需要手动解决: ${task.recordId}', 'error');
        break;
    }

    await _db.markSynced(task.id);
    _syncedCount++;
  }

  // 获取待同步任务
  Future<List<SyncTask>> _getPendingSyncTasks() async {
    final records = await _db.getPendingSync();
    return records.map((row) => SyncTask.fromMap(row)).toList();
  }

  // 获取远程数据（占位实现）
  Future<Map<String, dynamic>?> _fetchRemoteData(String recordType, String recordId) async {
    // TODO: 实现远程 API 调用
    return null;
  }

  // 保存到远程（占位实现）
  Future<void> _saveToRemote(String recordType, String recordId, Map<String, dynamic> data) async {
    // TODO: 实现远程数据保存
  }

  // 保存到本地
  Future<void> _saveToLocal(String recordType, String recordId, Map<String, dynamic> data) async {
    // TODO: 实现本地数据保存
  }

  // 添加日志
  void _addLog(String recordType, String message, String level) {
    _syncLogs.add(SyncLogEntry(
      recordType: recordType,
      message: message,
      level: level,
      timestamp: DateTime.now(),
    ));
    if (_syncLogs.length > 100) {
      _syncLogs.removeAt(0);
    }
  }

  // 清除日志
  void clearLogs() {
    _syncLogs.clear();
    notifyListeners();
  }

  // 设置冲突解决策略
  void setConflictStrategy(ConflictStrategy strategy) {
    _conflictStrategy = strategy;
    notifyListeners();
  }
}

// 同步任务
class SyncTask {
  final int id;
  final String action;
  final String recordType;
  final String recordId;
  final Map<String, dynamic> data;
  final int priority;
  final DateTime createdAt;

  const SyncTask({
    required this.id,
    required this.action,
    required this.recordType,
    required this.recordId,
    required this.data,
    this.priority = 0,
    required this.createdAt,
  });

  factory SyncTask.fromMap(Map<String, dynamic> map) => SyncTask(
    id: map['id'] as int,
    action: map['action'] as String,
    recordType: map['recordType'] as String,
    recordId: map['recordId'] as String,
    data: Map<String, dynamic>.from(map['data'] as Map),
    priority: map['priority'] as int? ?? 0,
    createdAt: DateTime.fromMillisecondsSinceEpoch(map['createdAt'] as int),
  );

  Map<String, dynamic> toMap() => {
    'id': id,
    'action': action,
    'recordType': recordType,
    'recordId': recordId,
    'data': data,
    'priority': priority,
    'createdAt': createdAt.millisecondsSinceEpoch,
  };
}

// 同步日志条目
class SyncLogEntry {
  final String recordType;
  final String message;
  final String level;
  final DateTime timestamp;

  const SyncLogEntry({
    required this.recordType,
    required this.message,
    required this.level,
    required this.timestamp,
  });
}

// 冲突解决策略
enum ConflictStrategy {
  lastWriteWins,
  manual,
}
