// Matha 协作功能 - 协作审计日志
// 记录会话内所有关键操作（加入 / 离开 / 操作 / 聊天 / 邀请等）

import 'dart:async';
import 'package:flutter/material.dart';
import 'websocket_manager.dart';

/// 审计条目
class AuditEntry {
  final String entryId;
  final String userId;
  final String action;
  final String detail;
  final DateTime timestamp;

  const AuditEntry({
    required this.entryId,
    required this.userId,
    required this.action,
    this.detail = '',
    required this.timestamp,
  });

  Map<String, dynamic> toMap() => {
    'entryId': entryId,
    'userId': userId,
    'action': action,
    'detail': detail,
    'timestamp': timestamp.toIso8601String(),
  };

  factory AuditEntry.fromMap(Map<String, dynamic> map) => AuditEntry(
    entryId: map['entryId'] as String,
    userId: map['userId'] as String? ?? 'unknown',
    action: map['action'] as String,
    detail: map['detail'] as String? ?? '',
    timestamp: DateTime.tryParse(map['timestamp'] as String? ?? '') ?? DateTime.now(),
  );
}

/// 审计日志管理器
class AuditManager extends ChangeNotifier {
  final String documentId;
  final int maxEntries;

  final List<AuditEntry> _entries = [];
  WebSocketManager? _wsManager;

  AuditManager({required this.documentId, this.maxEntries = 500});

  /// 连接实时通信通道
  void attachWebSocket(WebSocketManager? manager) {
    _wsManager = manager;
    if (manager != null) {
      manager.onCustomMessage = _handleServerMessage;
      debugPrint('[Audit] WebSocket 通道已挂载');
    }
    notifyListeners();
  }

  void _handleServerMessage(Map<String, dynamic> message) {
    if (message['type'] != 'audit') return;
    if (message['entry'] is Map<String, dynamic>) {
      _record(AuditEntry.fromMap(message['entry'] as Map<String, dynamic>));
    }
  }

  // ========== 记录 ==========

  /// 本地记录一条审计
  AuditEntry record({
    required String userId,
    required String action,
    String detail = '',
  }) {
    final entry = AuditEntry(
      entryId: 'audit_${DateTime.now().microsecondsSinceEpoch}',
      userId: userId,
      action: action,
      detail: detail,
      timestamp: DateTime.now(),
    );
    _record(entry);
    _send(entry);
    return entry;
  }

  void _record(AuditEntry entry) {
    _entries.add(entry);
    if (_entries.length > maxEntries) {
      _entries.removeRange(0, _entries.length - maxEntries);
    }
    notifyListeners();
  }

  // ========== 查询 ==========

  List<AuditEntry> get entries => List.unmodifiable(_entries);

  int get count => _entries.length;

  /// 最新 count 条（新→旧）
  List<AuditEntry> recent(int count) {
    if (count >= _entries.length) return _entries.reversed.toList();
    return _entries.sublist(_entries.length - count).reversed.toList();
  }

  /// 按动作统计次数
  Map<String, int> get summary {
    final result = <String, int>{};
    for (final e in _entries) {
      result[e.action] = (result[e.action] ?? 0) + 1;
    }
    return result;
  }

  List<AuditEntry> filterByAction(String action) =>
      _entries.where((e) => e.action == action).toList();

  void clear() {
    _entries.clear();
    notifyListeners();
  }

  // ========== 发送 ==========

  void _send(AuditEntry entry) {
    final ws = _wsManager;
    if (ws == null) return;
    ws.sendRawMessage({
      'type': 'audit',
      'entry': entry.toMap(),
      'documentId': documentId,
    });
  }

  // ========== 生命周期 ==========

  // (ChangeNotifier 无需额外释放资源)
}

/// 审计日志列表组件
class AuditLogSheet extends StatelessWidget {
  final AuditManager manager;

  const AuditLogSheet({super.key, required this.manager});

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: manager,
      builder: (context, _) {
        final entries = manager.recent(100);
        if (entries.isEmpty) {
          return const Padding(
            padding: EdgeInsets.all(24),
            child: Center(child: Text('暂无审计记录')),
          );
        }
        return ListView.builder(
          shrinkWrap: true,
          itemCount: entries.length,
          itemBuilder: (context, index) {
            final e = entries[index];
            final hm = '${e.timestamp.hour.toString().padLeft(2, '0')}:'
                '${e.timestamp.minute.toString().padLeft(2, '0')}:'
                '${e.timestamp.second.toString().padLeft(2, '0')}';
            return ListTile(
              dense: true,
              leading: Icon(_actionIcon(e.action), size: 20),
              title: Text('${e.userId} · ${e.action}',
                  style: const TextStyle(fontSize: 13)),
              subtitle: e.detail.isEmpty ? null : Text(e.detail, style: const TextStyle(fontSize: 12)),
              trailing: Text(hm, style: TextStyle(fontSize: 11, color: Colors.grey[500])),
            );
          },
        );
      },
    );
  }
}

IconData _actionIcon(String action) {
  switch (action) {
    case 'join':
      return Icons.login;
    case 'leave':
      return Icons.logout;
    case 'op':
      return Icons.edit_note;
    case 'chat':
      return Icons.chat_bubble_outline;
    case 'invite':
      return Icons.person_add_alt;
    case 'voice_join':
    case 'voice_leave':
      return Icons.headset;
    case 'share_start':
    case 'share_stop':
      return Icons.screen_share;
    case 'revert':
      return Icons.history_toggle_off;
    default:
      return Icons.event_note;
  }
}