// Matha 协作功能 - 变更历史（撤销 / 重做 / 版本快照）
// 跟踪协作文档的每一次变更，支持按版本回退

import 'package:flutter/material.dart';
import 'websocket_manager.dart';

/// 一次变更记录
class ChangeEntry {
  final int version;
  final String action;
  final String entityType;
  final String entityId;
  final Map<String, dynamic>? data;
  final DateTime timestamp;

  const ChangeEntry({
    required this.version,
    required this.action,
    required this.entityType,
    this.entityId = '',
    this.data,
    required this.timestamp,
  });

  Map<String, dynamic> toMap() => {
    'version': version,
    'action': action,
    'entityType': entityType,
    'entityId': entityId,
    'data': data,
    'timestamp': timestamp.toIso8601String(),
  };

  factory ChangeEntry.fromMap(Map<String, dynamic> map) => ChangeEntry(
    version: map['version'] as int? ?? 0,
    action: map['action'] as String,
    entityType: map['entityType'] as String? ?? 'generic',
    entityId: map['entityId'] as String? ?? '',
    data: map['data'] as Map<String, dynamic>?,
    timestamp: DateTime.tryParse(map['timestamp'] as String? ?? '') ?? DateTime.now(),
  );
}

/// 变更历史管理器
class ChangeHistoryManager extends ChangeNotifier {
  final String documentId;
  final int maxDepth;

  final List<ChangeEntry> _changes = [];
  final List<Map<String, dynamic>> _snapshots = [];

  int _cursor = -1;
  WebSocketManager? _wsManager;

  ChangeHistoryManager({required this.documentId, this.maxDepth = 100});

  /// 连接实时通信通道
  void attachWebSocket(WebSocketManager? manager) {
    _wsManager?.removeCustomMessageListener(_handleServerMessage);
    _wsManager = manager;
    if (manager != null) {
      manager.addCustomMessageListener(_handleServerMessage);
      debugPrint('[ChangeHistory] WebSocket 通道已挂载');
    } else {
      debugPrint('[ChangeHistory] WebSocket 通道已分离');
    }
    notifyListeners();
  }

  void _handleServerMessage(Map<String, dynamic> message) {
    if (message['type'] != 'change_history') return;
    final action = message['action'] as String?;
    switch (action) {
      case 'change':
        if (message['entry'] is Map<String, dynamic>) {
          _append(ChangeEntry.fromMap(message['entry'] as Map<String, dynamic>),
              relay: false);
        }
      case 'revert':
        // 远程回退：直接跳到目标版本
        final target = message['version'] as int?;
        if (target != null && target >= 0 && target <= _changes.length) {
          _cursor = target;
          notifyListeners();
        }
    }
  }

  // ========== 记录 / 回退 ==========

  /// 记录一次变更（追加快照，清空重做栈）
  ChangeEntry addChange({
    required String action,
    String entityType = 'node',
    String entityId = '',
    Map<String, dynamic>? data,
  }) {
    final entry = ChangeEntry(
      version: _changes.length,
      action: action,
      entityType: entityType,
      entityId: entityId,
      data: data,
      timestamp: DateTime.now(),
    );
    _append(entry);
    return entry;
  }

  /// 追加变更（本地或远程），relay 为 true 时转发给远端
  void _append(ChangeEntry entry, {bool relay = true}) {
    if (_cursor < _changes.length - 1) {
      _changes.removeRange(_cursor + 1, _changes.length);
      _snapshots.removeRange(_cursor + 1, _snapshots.length);
    }
    _changes.add(entry);
    _snapshots.add(entry.data != null ? Map.of(entry.data!) : const {});
    _cursor = _changes.length - 1;
    if (_changes.length > maxDepth) {
      _changes.removeAt(0);
      _snapshots.removeAt(0);
      _cursor = _changes.length - 1;
    }
    notifyListeners();
    if (relay) {
      _send('change', {'entry': entry.toMap()});
    }
  }

  /// 撤销：返回被撤销版本的变更快照（null 表示无可撤销项）
  Map<String, dynamic>? undo() {
    if (!canUndo) return null;
    _cursor--;
    _send('revert', {'version': _cursor});
    notifyListeners();
    return currentSnapshot;
  }

  /// 重做：返回恢复版本的变更快照（null 表示无可重做项）
  Map<String, dynamic>? redo() {
    if (!canRedo) return null;
    _cursor++;
    _send('revert', {'version': _cursor});
    notifyListeners();
    return currentSnapshot;
  }

  /// 直接回退到指定版本，返回该版本快照
  Map<String, dynamic>? revertTo(int version) {
    if (version < 0 || version >= _changes.length) return null;
    _cursor = version;
    _send('revert', {'version': version});
    notifyListeners();
    return currentSnapshot;
  }

  // ========== 查询 ==========

  bool get canUndo => _cursor > 0;

  bool get canRedo => _cursor < _changes.length - 1;

  int get versionCount => _changes.length;

  int get currentVersion => _cursor;

  ChangeEntry? get currentEntry => _cursor >= 0 && _cursor < _changes.length
      ? _changes[_cursor]
      : null;

  Map<String, dynamic>? get currentSnapshot =>
      _cursor >= 0 && _cursor < _snapshots.length ? Map.of(_snapshots[_cursor]) : null;

  List<ChangeEntry> get changes => List.unmodifiable(_changes);

  String? get latestAction => _changes.isEmpty ? null : _changes.last.action;

  List<Map<String, dynamic>> get snapshots => List.unmodifiable(_snapshots);

  void clear() {
    _changes.clear();
    _snapshots.clear();
    _cursor = -1;
    notifyListeners();
  }

  // ========== 发送 ==========

  void _send(String action, Map<String, dynamic> payload) {
    final ws = _wsManager;
    if (ws == null) {
      debugPrint('[ChangeHistory] 未连接 WebSocket，仅本地记录: $action');
      return;
    }
    ws.sendRawMessage({
      'type': 'change_history',
      'action': action,
      'documentId': documentId,
      'timestamp': DateTime.now().toIso8601String(),
      ...payload,
    });
  }

  // ========== 生命周期 ==========

  // (ChangeNotifier 无需额外释放资源)
}