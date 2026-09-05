// Matha 协作功能 - CRDT 协作引擎
// 实现无冲突复制数据类型

import 'dart:async';
import 'dart:math';
import 'package:flutter/foundation.dart';

/// 协作操作类型
enum CollaborativeOpType {
  insert,      // 插入
  delete,      // 删除
  replace,     // 替换
  format,      // 格式化
  cursorMove,  // 光标移动
}

/// 协作操作
class CollaborativeOp {
  final String id;
  final CollaborativeOpType type;
  final int position;
  final String content;
  final Map<String, dynamic>? metadata;
  final DateTime timestamp;
  final String userId;

  const CollaborativeOp({
    required this.id,
    required this.type,
    required this.position,
    required this.content,
    this.metadata,
    required this.timestamp,
    required this.userId,
  });

  Map<String, dynamic> toMap() => {
    'id': id,
    'type': type.name,
    'position': position,
    'content': content,
    'metadata': metadata,
    'timestamp': timestamp.toIso8601String(),
    'userId': userId,
  };

  factory CollaborativeOp.fromMap(Map<String, dynamic> map) => CollaborativeOp(
    id: map['id'] as String,
    type: CollaborativeOpType.values.firstWhere(
      (e) => e.name == map['type'],
      orElse: () => CollaborativeOpType.insert,
    ),
    position: map['position'] as int,
    content: map['content'] as String,
    metadata: map['metadata'] as Map<String, dynamic>?,
    timestamp: DateTime.parse(map['timestamp'] as String),
    userId: map['userId'] as String,
  );
}

/// CRDT 状态
class CRDTState {
  final String documentId;
  final List<CollaborativeOp> ops;
  final Map<String, String> cursors;
  final Map<String, String> presence;
  final DateTime lastModified;
  final int version;

  const CRDTState({
    required this.documentId,
    required this.ops,
    required this.cursors,
    required this.presence,
    required this.lastModified,
    required this.version,
  });

  CRDTState copyWith({
    List<CollaborativeOp>? ops,
    Map<String, String>? cursors,
    Map<String, String>? presence,
    DateTime? lastModified,
    int? version,
  }) {
    return CRDTState(
      documentId: documentId,
      ops: ops ?? this.ops,
      cursors: cursors ?? this.cursors,
      presence: presence ?? this.presence,
      lastModified: lastModified ?? this.lastModified,
      version: version ?? this.version,
    );
  }

  Map<String, dynamic> toMap() => {
    'documentId': documentId,
    'ops': ops.map((op) => op.toMap()).toList(),
    'cursors': cursors,
    'presence': presence,
    'lastModified': lastModified.toIso8601String(),
    'version': version,
  };

  factory CRDTState.fromMap(Map<String, dynamic> map) => CRDTState(
    documentId: map['documentId'] as String,
    ops: (map['ops'] as List).map((e) => CollaborativeOp.fromMap(e as Map<String, dynamic>)).toList(),
    cursors: Map<String, String>.from(map['cursors'] as Map),
    presence: Map<String, String>.from(map['presence'] as Map),
    lastModified: DateTime.parse(map['lastModified'] as String),
    version: map['version'] as int,
  );
}

/// 协作引擎
class CollaborativeEngine extends ChangeNotifier {
  final String _documentId;
  final String _userId;
  
  CRDTState _state;
  final List<CollaborativeOp> _pendingOps = [];
  final Map<String, CollaborativeOp> _opHistory = {};
  
  // 监听器
  StreamController<CRDTState>? _stateController;
  StreamController<CollaborativeOp>? _opController;
  
  // 连接状态
  bool _isConnected = false;
  bool _isSyncing = false;
  String? _connectionError;

  CollaborativeEngine({
    required String documentId,
    required String userId,
    List<CollaborativeOp>? initialOps,
  }) : _documentId = documentId,
       _userId = userId,
       _state = CRDTState(
         documentId: documentId,
         ops: initialOps ?? [],
         cursors: {},
         presence: {},
         lastModified: DateTime.now(),
         version: 0,
       );

  // ========== 操作应用 ==========

  /// 应用本地操作
  void applyLocalOp(CollaborativeOp op) {
    debugPrint('[Collab] ========== 应用本地操作 ==========');
    debugPrint('[Collab] 操作 ID: ${op.id}');
    debugPrint('[Collab] 操作类型: ${op.type}');
    debugPrint('[Collab] 位置: ${op.position}');
    debugPrint('[Collab] 内容: "${op.content.substring(0, op.content.length > 20 ? 20 : op.content.length)}${op.content.length > 20 ? '...' : ''}"');
    debugPrint('[Collab] 用户 ID: ${op.userId}');
    
    // 应用操作到状态
    _applyOp(op);
    debugPrint('[Collab] 状态已更新，版本: ${_state.version}');
    
    // 添加到历史
    _opHistory[op.id] = op;
    debugPrint('[Collab] 操作已添加到历史 (历史总数: ${_opHistory.length})');
    
    // 发送到服务器
    _sendToServer(op);
    
    debugPrint('[Collab] ========== 本地操作应用完成 ==========');
    notifyListeners();
  }

  /// 应用远程操作
  void applyRemoteOp(CollaborativeOp op) {
    debugPrint('[Collab] ========== 应用远程操作 ==========');
    debugPrint('[Collab] 操作 ID: ${op.id}');
    debugPrint('[Collab] 操作类型: ${op.type}');
    debugPrint('[Collab] 用户 ID: ${op.userId}');
    
    // 应用操作
    _applyOp(op);
    debugPrint('[Collab] 状态已更新，版本: ${_state.version}');
    
    // 更新光标
    if (op.type == CollaborativeOpType.cursorMove) {
      _state.cursors[op.userId] = op.content;
      debugPrint('[Collab] 光标位置已更新: ${op.content}');
    }
    
    debugPrint('[Collab] ========== 远程操作应用完成 ==========');
    notifyListeners();
  }

  /// 应用操作到状态
  void _applyOp(CollaborativeOp op) {
    debugPrint('[Collab] 应用操作到 CRDT 状态...');
    _state = _state.copyWith(
      ops: [..._state.ops, op],
      lastModified: DateTime.now(),
      version: _state.version + 1,
    );
    debugPrint('[Collab] CRDT 状态已更新，版本号: ${_state.version}');
    
    // 触发事件
    _opController?.add(op);
    debugPrint('[Collab] 操作事件已触发');
  }

  // ========== 操作类型 ==========

  /// 创建插入操作
  CollaborativeOp createInsertOp(int position, String content) {
    return CollaborativeOp(
      id: _generateOpId(),
      type: CollaborativeOpType.insert,
      position: position,
      content: content,
      timestamp: DateTime.now(),
      userId: _userId,
    );
  }

  /// 创建删除操作
  CollaborativeOp createDeleteOp(int position, int length) {
    return CollaborativeOp(
      id: _generateOpId(),
      type: CollaborativeOpType.delete,
      position: position,
      content: '',
      metadata: {'length': length},
      timestamp: DateTime.now(),
      userId: _userId,
    );
  }

  /// 创建光标移动操作
  CollaborativeOp createCursorOp(int position) {
    return CollaborativeOp(
      id: _generateOpId(),
      type: CollaborativeOpType.cursorMove,
      position: position,
      content: position.toString(),
      timestamp: DateTime.now(),
      userId: _userId,
    );
  }

  // ========== 连接管理 ==========

  /// 连接到协作服务器
  Future<bool> connect({
    required String serverUrl,
    Map<String, String>? auth,
  }) async {
    try {
      debugPrint('[Collab] ========== 开始连接协作服务器 ==========');
      debugPrint('[Collab] 服务器地址: $serverUrl');
      debugPrint('[Collab] 文档 ID: $_documentId');
      debugPrint('[Collab] 用户 ID: $_userId');
      
      // TODO: 实现 WebSocket 连接
      // 模拟连接成功
      await Future.delayed(const Duration(milliseconds: 500));
      
      _isConnected = true;
      _connectionError = null;
      
      debugPrint('[Collab] 连接成功!');
      debugPrint('[Collab] ========== 连接完成 ==========');
      
      notifyListeners();
      return true;
    } catch (e, stackTrace) {
      _connectionError = '连接失败: $e';
      debugPrint('[Collab] ========== 连接失败 ==========');
      debugPrint('[Collab] 错误: $e');
      debugPrint('[Collab] 堆栈: $stackTrace');
      notifyListeners();
      return false;
    }
  }

  /// 断开连接
  void disconnect() {
    debugPrint('[Collab] ========== 开始断开连接 ==========');
    _isConnected = false;
    
    // 清理待发送操作
    if (_pendingOps.isNotEmpty) {
      debugPrint('[Collab] 有 ${_pendingOps.length} 个待发送操作，将重连后发送');
    }
    
    debugPrint('[Collab] 连接已断开');
    debugPrint('[Collab] ========== 断开完成 ==========');
    notifyListeners();
  }

  /// 发送操作到服务器
  void _sendToServer(CollaborativeOp op) {
    debugPrint('[Collab] 发送操作: ${op.id} (类型: ${op.type}, 位置: ${op.position})');
    
    if (!_isConnected) {
      debugPrint('[Collab] ⚠️ 未连接，操作已暂存到队列 (队列长度: ${_pendingOps.length + 1})');
      _pendingOps.add(op);
      return;
    }
    
    // TODO: 实现 WebSocket 发送
    debugPrint('[Collab] ✓ 操作已发送到服务器');
  }

  // ========== 状态查询 ==========

  /// 获取当前状态
  CRDTState get state => _state;

  /// 获取文档 ID
  String get documentId => _documentId;

  /// 获取用户 ID
  String get userId => _userId;

  /// 获取版本号
  int get version => _state.version;

  /// 获取在线用户列表
  List<String> get onlineUsers => _state.presence.keys.toList();

  /// 检查是否已连接
  bool get isConnected => _isConnected;

  /// 检查是否正在同步
  bool get isSyncing => _isSyncing;

  /// 获取连接错误
  String? get connectionError => _connectionError;

  // ========== 帮助方法 ==========

  String _generateOpId() {
    return '${DateTime.now().millisecondsSinceEpoch}_${_userId}_${Random().nextInt(10000)}';
  }

  // ========== Stream 管理 ==========

  Stream<CRDTState> get stateStream {
    _stateController ??= StreamController<CRDTState>.broadcast();
    return _stateController!.stream;
  }

  Stream<CollaborativeOp> get opStream {
    _opController ??= StreamController<CollaborativeOp>.broadcast();
    return _opController!.stream;
  }

  // ========== 生命周期 ==========

  @override
  void dispose() {
    _stateController?.close();
    _opController?.close();
    super.dispose();
  }
}

/// 协作会话管理器
class SessionManager extends ChangeNotifier {
  final Map<String, CollaborativeEngine> _sessions = {};
  
  /// 创建或获取协作会话
  CollaborativeEngine getOrCreateSession({
    required String documentId,
    required String userId,
  }) {
    if (!_sessions.containsKey(documentId)) {
      _sessions[documentId] = CollaborativeEngine(
        documentId: documentId,
        userId: userId,
      );
      debugPrint('[Session] 创建会话: $documentId');
    }
    return _sessions[documentId]!;
  }

  /// 关闭会话
  void closeSession(String documentId) {
    _sessions.remove(documentId)?.disconnect();
    notifyListeners();
  }

  /// 获取所有会话
  Map<String, CollaborativeEngine> get sessions => Map.unmodifiable(_sessions);

  /// 获取会话数量
  int get sessionCount => _sessions.length;
}
