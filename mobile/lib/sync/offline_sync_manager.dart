// Matha 离线同步管理器
// 管理离线模式下的数据同步和冲突解决

import 'dart:async';
import 'package:flutter/foundation.dart';
import '../database/math_database.dart';
import '../pyodide/pyodide_bridge.dart';

class OfflineSyncManager extends ChangeNotifier {
  // 单例
  static final OfflineSyncManager _instance = OfflineSyncManager._internal();
  factory OfflineSyncManager() => _instance;
  OfflineSyncManager._internal();

  // 状态
  bool _isOffline = false;
  bool _isSyncing = false;
  String _syncStatus = '未同步';
  int _pendingCount = 0;
  int _syncedCount = 0;
  int _failedCount = 0;

  // 同步队列
  final List<SyncTask> _syncQueue = [];

  // 冲突解决策略
  ConflictStrategy _conflictStrategy = ConflictStrategy.lastWriteWins;

  // 同步日志
  final List<SyncLogEntry> _syncLogs = [];

  // 获取状态
  bool get isOffline => _isOffline;
  bool get isSyncing => _isSyncing;
  String get syncStatus => _syncStatus;
  int get pendingCount => _pendingCount;
  int get syncedCount => _syncedCount;
  int get failedCount => _failedCount;
  List<SyncLogEntry> get syncLogs => List.unmodifiable(_syncLogs);

  // 初始化
  Future<void> init() async {
    await _loadFromDatabase();
    _addLog('系统', '初始化完成', 'success');
    notifyListeners();
  }

  // 切换离线模式
  Future<void> toggleOfflineMode() async {
    _isOffline = !_isOffline;
    _syncStatus = _isOffline ? '离线模式' : '已连接';
    _addLog('系统', '切换离线模式: ${_isOffline ? '开启' : '关闭'}', 'info');

    if (_isOffline) {
      // 离线模式：本地优先
      await _saveLocalData();
      _addLog('系统', '离线模式：数据已保存到本地', 'warning');
    } else {
      // 在线模式：尝试同步
      await requestSync();
    }

    notifyListeners();
  }

  // 请求同步
  Future<void> requestSync() async {
    if (_isOffline || _isSyncing) return;

    _isSyncing = true;
    _syncStatus = '同步中...';
    _addLog('同步', '开始同步', 'info');
    notifyListeners();

    try {
      // 获取待同步数据
      final pendingTasks = await _getPendingSyncTasks();

      if (pendingTasks.isEmpty) {
        _syncStatus = '已同步';
        _addLog('同步', '没有待同步数据', 'success');
        return;
      }

      // 处理每个任务
      for (final task in pendingTasks) {
        await _processSyncTask(task);
      }

      _syncStatus = '同步完成';
      _addLog('同步', '同步完成，成功: $_syncedCount, 失败: $_failedCount', 'success');

    } catch (e) {
      _syncStatus = '同步失败';
      _addLog('同步', '同步失败: $e', 'error');
    } finally {
      _isSyncing = false;
      notifyListeners();
    }
  }

  // 处理同步任务
  Future<void> _processSyncTask(SyncTask task) async {
    try {
      switch (task.action) {
        case 'push':
          await _pushTask(task);
          break;
        case 'pull':
          await _pullTask(task);
          break;
      }
    } catch (e) {
      _addLog(task.recordType, '任务失败: $e', 'error');
    }
  }

  // 推送任务（本地 -> 远程）
  Future<void> _pushTask(SyncTask task) async {
    // 检查是否有远程版本
    final remoteData = await _fetchRemoteData(task.recordType, task.recordId);

    if (remoteData != null) {
      // 检测冲突
      if (_hasConflict(task.data, remoteData)) {
        await _resolveConflict(task, remoteData);
      } else {
        // 无冲突，直接更新
        await _saveToRemote(task.recordType, task.recordId, task.data);
        await MathDatabase.markSynced(task.id);
        _syncedCount++;
        _addLog(task.recordType, '推送成功: ${task.recordId}', 'success');
      }
    } else {
      // 远程不存在，直接创建
      await _saveToRemote(task.recordType, task.recordId, task.data);
      await MathDatabase.markSynced(task.id);
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
        await MathDatabase.markSynced(task.id);
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

      case ConflictStrategy.firstWriteWins:
        // 最先写入优先
        final localTime = (task.data['timestamp'] ?? 0) as num;
        final remoteTime = (remoteData['timestamp'] ?? 0) as num;
        if (localTime < remoteTime) {
          await _saveToRemote(task.recordType, task.recordId, task.data);
          _addLog(task.recordType, '冲突解决: 保留本地数据', 'info');
        } else {
          await _saveToLocal(task.recordType, task.recordId, remoteData);
          _addLog(task.recordType, '冲突解决: 使用远程数据', 'info');
        }
        break;

      case ConflictStrategy.merge:
        // 合并策略
        final merged = _mergeData(task.data, remoteData);
        await _saveToRemote(task.recordType, task.recordId, merged);
        await _saveToLocal(task.recordType, task.recordId, merged);
        _addLog(task.recordType, '冲突解决: 合并数据', 'info');
        break;

      case ConflictStrategy.manual:
        // 需要手动处理
        _addLog(task.recordType, '冲突需要手动解决: ${task.recordId}', 'error');
        break;
    }

    await MathDatabase.markSynced(task.id);
    _syncedCount++;
  }

  // 合并数据
  Map<String, dynamic> _mergeData(Map<String, dynamic> local, Map<String, dynamic> remote) {
    final merged = Map<String, dynamic>.from(local);
    remote.forEach((key, value) {
      if (!merged.containsKey(key)) {
        merged[key] = value;
      } else if (merged[key] is Map && value is Map) {
        merged[key] = _mergeData(merged[key] as Map<String, dynamic>, value as Map<String, dynamic>);
      } else if (merged[key] is List && value is List) {
        // 列表合并去重
        final localList = merged[key] as List;
        final remoteList = value as List;
        final existingIds = localList.map((e) => e['id']).toList();
        for (final item in remoteList) {
          if (!existingIds.contains(item['id'])) {
            localList.add(item);
          }
        }
        merged[key] = localList;
      }
      // 其他类型：本地优先
    });
    return merged;
  }

  // 获取待同步任务
  Future<List<SyncTask>> _getPendingSyncTasks() async {
    final records = await MathDatabase.getPendingSync();
    return records.map((row) => SyncTask.fromMap(row)).toList();
  }

  // 从数据库加载
  Future<void> _loadFromDatabase() async {
    final stats = await MathDatabase.getQueueStats();
    _pendingCount = stats['pending'] ?? 0;
    _syncedCount = stats['synced'] ?? 0;
    _failedCount = stats['failed'] ?? 0;
  }

  // 保存本地数据
  Future<void> _saveLocalData() async {
    // TODO: 实现本地数据保存逻辑
  }

  // 远程 API 调用（模拟）
  Future<Map<String, dynamic>?> _fetchRemoteData(String recordType, String recordId) async {
    // TODO: 实现远程 API 调用
    await Future.delayed(const Duration(milliseconds: 100));
    return null; // 模拟无远程数据
  }

  Future<void> _saveToRemote(String recordType, String recordId, Map<String, dynamic> data) async {
    // TODO: 实现远程数据保存
    await Future.delayed(const Duration(milliseconds: 50));
  }

  Future<void> _saveToLocal(String recordType, String recordId, Map<String, dynamic> data) async {
    // TODO: 实现本地数据保存
  }

  // 添加日志
  void _addLog(String category, String message, String level) {
    _syncLogs.add(SyncLogEntry(
      timestamp: DateTime.now(),
      category: category,
      message: message,
      level: level,
    ));
    // 限制日志数量
    if (_syncLogs.length > 100) {
      _syncLogs.removeAt(0);
    }
  }

  // 清除日志
  void clearLogs() {
    _syncLogs.clear();
    notifyListeners();
  }
}

// 冲突解决策略
enum ConflictStrategy {
  lastWriteWins,   // 最后写入优先
  firstWriteWins,  // 最先写入优先
  merge,           // 合并策略
  manual,          // 手动解决
}

// 同步任务
class SyncTask {
  final int id;
  final String action;      // push, pull
  final String recordType;  // history, preference, cache
  final String recordId;
  final Map<String, dynamic> data;
  final int priority;
  final DateTime createdAt;

  SyncTask({
    required this.id,
    required this.action,
    required this.recordType,
    required this.recordId,
    required this.data,
    this.priority = 0,
    required this.createdAt,
  });

  factory SyncTask.fromMap(Map<String, dynamic> map) {
    return SyncTask(
      id: map['id'] as int,
      action: map['action'] as String,
      recordType: map['record_type'] as String,
      recordId: map['record_id'] as String,
      data: _parseJson(map['data'] as String),
      priority: map['priority'] as int? ?? 0,
      createdAt: DateTime.parse(map['created_at'] as String),
    );
  }

  static Map<String, dynamic> _parseJson(String json) {
    try {
      // 简单的 JSON 解析
      final result = <String, dynamic>{};
      final regex = RegExp(r'"([^"]+)":"([^"]*)"');
      for (final match in regex.allMatches(json)) {
        result[match.group(1)!] = match.group(2);
      }
      return result;
    } catch (e) {
      return {};
    }
  }
}

// 同步日志条目
class SyncLogEntry {
  final DateTime timestamp;
  final String category;
  final String message;
  final String level; // info, success, warning, error

  SyncLogEntry({
    required this.timestamp,
    required this.category,
    required this.message,
    required this.level,
  });
}
