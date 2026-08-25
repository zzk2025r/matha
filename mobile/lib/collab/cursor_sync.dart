// Matha 协作功能 - 光标同步

import 'dart:async';
import 'package:flutter/material.dart';
import 'collab_engine.dart';

/// 光标位置
class CursorPosition {
  final int line;
  final int column;
  final Offset pixelOffset;

  const CursorPosition({
    required this.line,
    required this.column,
    required this.pixelOffset,
  });

  Map<String, dynamic> toMap() => {
    'line': line,
    'column': column,
    'pixelOffset': [pixelOffset.dx, pixelOffset.dy],
  };

  factory CursorPosition.fromMap(Map<String, dynamic> map) => CursorPosition(
    line: map['line'] as int,
    column: map['column'] as int,
    pixelOffset: Offset(
      (map['pixelOffset'] as List).first.toDouble(),
      (map['pixelOffset'] as List).last.toDouble(),
    ),
  );
}

/// 远程光标信息
class RemoteCursor {
  final String userId;
  final String userName;
  final CursorPosition position;
  final Color color;
  final DateTime lastUpdate;
  final bool isEditing;

  const RemoteCursor({
    required this.userId,
    required this.userName,
    required this.position,
    required this.color,
    required this.lastUpdate,
    required this.isEditing,
  });

  bool get isActive => DateTime.now().difference(lastUpdate).inSeconds < 10;
  bool get isStale => !isActive;

  Map<String, dynamic> toMap() => {
    'userId': userId,
    'userName': userName,
    'position': position.toMap(),
    'color': color.value,
    'lastUpdate': lastUpdate.toIso8601String(),
    'isEditing': isEditing,
  };

  factory RemoteCursor.fromMap(Map<String, dynamic> map) => RemoteCursor(
    userId: map['userId'] as String,
    userName: map['userName'] as String,
    position: CursorPosition.fromMap(map['position'] as Map<String, dynamic>),
    color: Color(map['color'] as int),
    lastUpdate: DateTime.parse(map['lastUpdate'] as String),
    isEditing: map['isEditing'] as bool,
  );
}

/// 光标同步控制器
class CursorSyncController extends ChangeNotifier {
  final CollaborativeEngine _engine;
  final Map<String, RemoteCursor> _cursors = {};
  final StreamController<RemoteCursor> _cursorAddedController = StreamController.broadcast();
  final StreamController<String> _cursorRemovedController = StreamController.broadcast();

  CursorSyncController(this._engine);

  // ========== 光标管理 ==========

  /// 更新本地光标位置
  void updateCursorPosition(CursorPosition position, {bool isEditing = false}) {
    final op = _engine.createCursorOp(position.line * 1000 + position.column);
    _engine.applyLocalOp(op);
  }

  /// 添加远程光标
  void addRemoteCursor(RemoteCursor cursor) {
    _cursors[cursor.userId] = cursor;
    _cursorAddedController.add(cursor);
    notifyListeners();
    debugPrint('[CursorSync] 添加远程光标: ${cursor.userName} at ${cursor.position.line}:${cursor.position.column}');
  }

  /// 更新远程光标
  void updateRemoteCursor(String userId, CursorPosition position) {
    if (_cursors.containsKey(userId)) {
      _cursors[userId] = RemoteCursor(
        userId: userId,
        userName: _cursors[userId]!.userName,
        position: position,
        color: _cursors[userId]!.color,
        lastUpdate: DateTime.now(),
        isEditing: _cursors[userId]!.isEditing,
      );
      notifyListeners();
    }
  }

  /// 移除远程光标
  void removeRemoteCursor(String userId) {
    if (_cursors.containsKey(userId)) {
      _cursorRemovedController.add(userId);
      _cursors.remove(userId);
      notifyListeners();
      debugPrint('[CursorSync] 移除远程光标: $userId');
    }
  }

  /// 清除所有远程光标
  void clearAllCursors() {
    _cursors.clear();
    notifyListeners();
  }

  // ========== 查询 ==========

  /// 获取所有远程光标
  Map<String, RemoteCursor> get cursors => Map.unmodifiable(_cursors);

  /// 获取远程光标列表
  List<RemoteCursor> get cursorList => _cursors.values.toList()
    ..sort((a, b) => a.userName.compareTo(b.userName));

  /// 获取活跃光标数量
  int get activeCursorCount => _cursors.values.where((c) => c.isActive).length;

  /// 检查用户是否有活跃光标
  bool hasActiveCursor(String userId) => 
      _cursors.containsKey(userId) && _cursors[userId]!.isActive;

  // ========== Stream ==========

  Stream<RemoteCursor> get onCursorAdded => _cursorAddedController.stream;
  Stream<String> get onCursorRemoved => _cursorRemovedController.stream;

  // ========== 生命周期 ==========

  @override
  void dispose() {
    _cursorAddedController.close();
    _cursorRemovedController.close();
    super.dispose();
  }
}

/// 光标同步 UI 组件
class RemoteCursorWidget extends StatelessWidget {
  final RemoteCursor cursor;
  final double scale;

  const RemoteCursorWidget({
    super.key,
    required this.cursor,
    this.scale = 1.0,
  });

  @override
  Widget build(BuildContext context) {
    return Positioned(
      left: cursor.position.pixelOffset.dx / scale,
      top: cursor.position.pixelOffset.dy / scale,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 光标线条
          Container(
            width: 2,
            height: 20,
            color: cursor.color,
          ),
          // 用户名称
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
            decoration: BoxDecoration(
              color: cursor.color,
              borderRadius: BorderRadius.circular(4),
            ),
            child: Text(
              cursor.userName,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 10,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// 活跃用户指示器
class ActiveUsersIndicator extends StatelessWidget {
  final List<RemoteCursor> cursors;

  const ActiveUsersIndicator({
    super.key,
    required this.cursors,
  });

  @override
  Widget build(BuildContext context) {
    final activeCursors = cursors.where((c) => c.isActive).toList();
    
    if (activeCursors.isEmpty) {
      return const SizedBox.shrink();
    }

    return Row(
      children: [
        Icon(Icons.people, size: 16, color: Colors.grey),
        const SizedBox(width: 4),
        ...activeCursors.map((cursor) => _UserAvatar(cursor: cursor)),
        if (activeCursors.length > 3)
          Container(
            margin: const EdgeInsets.only(left: 4),
            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
            decoration: BoxDecoration(
              color: Colors.grey[300],
              borderRadius: BorderRadius.circular(12),
            ),
            child: Text(
              '+${activeCursors.length - 3}',
              style: const TextStyle(fontSize: 12),
            ),
          ),
      ],
    );
  }
}

class _UserAvatar extends StatelessWidget {
  final RemoteCursor cursor;

  const _UserAvatar({required this.cursor});

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: cursor.userName,
      child: Container(
        margin: const EdgeInsets.only(right: 4),
        width: 28,
        height: 28,
        decoration: BoxDecoration(
          color: cursor.color,
          shape: BoxShape.circle,
          border: Border.all(color: Colors.white, width: 2),
        ),
        child: Center(
          child: Text(
            cursor.userName[0].toUpperCase(),
            style: const TextStyle(
              color: Colors.white,
              fontSize: 12,
              fontWeight: FontWeight.bold,
            ),
          ),
        ),
      ),
    );
  }
}
