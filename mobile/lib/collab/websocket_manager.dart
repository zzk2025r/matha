// Matha 协作功能 - WebSocket 连接管理器
// 实现实时通信、断线重连、心跳检测

import 'dart:async';
import 'package:flutter/material.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:web_socket_channel/io.dart';
import 'collab_engine.dart';

/// WebSocket 连接状态
enum WebSocketState {
  disconnected,
  connecting,
  connected,
  reconnecting,
  error,
}

/// WebSocket 消息类型
class WSMessageType {
  static const String join = 'join';
  static const String leave = 'leave';
  static const String op = 'op';
  static const String ack = 'ack';
  static const String heartbeat = 'heartbeat';
  static const String pong = 'pong';
  static const String error = 'error';
  static const String sync = 'sync';
  static const String cursor = 'cursor';
}

/// WebSocket 连接配置
class WebSocketConfig {
  final String serverUrl;
  final String documentId;
  final String userId;
  final String userName;
  final Duration reconnectDelay;
  final int maxReconnectAttempts;
  final Duration heartbeatInterval;
  final Duration connectionTimeout;
  final Map<String, String>? headers;

  const WebSocketConfig({
    required this.serverUrl,
    required this.documentId,
    required this.userId,
    required this.userName,
    this.reconnectDelay = const Duration(seconds: 2),
    this.maxReconnectAttempts = 5,
    this.heartbeatInterval = const Duration(seconds: 30),
    this.connectionTimeout = const Duration(seconds: 10),
    this.headers,
  });

  Map<String, dynamic> toMap() => {
    'serverUrl': serverUrl,
    'documentId': documentId,
    'userId': userId,
    'userName': userName,
    'reconnectDelay': reconnectDelay.inSeconds,
    'maxReconnectAttempts': maxReconnectAttempts,
    'heartbeatInterval': heartbeatInterval.inSeconds,
    'connectionTimeout': connectionTimeout.inSeconds,
  };
}

/// WebSocket 事件
class WSConnectionEvent {
  final String type;
  final dynamic data;
  final DateTime timestamp;

  const WSConnectionEvent({
    required this.type,
    this.data,
    required this.timestamp,
  });

  Map<String, dynamic> toMap() => {
    'type': type,
    'data': data,
    'timestamp': timestamp.toIso8601String(),
  };
}

/// WebSocket 连接管理器
class WebSocketManager extends ChangeNotifier {
  static const String _version = '1.0.0';
  
  WebSocketChannel? _channel;
  WebSocketState _state = WebSocketState.disconnected;
  String? _errorMessage;
  int _reconnectAttempts = 0;
  Timer? _reconnectTimer;
  Timer? _heartbeatTimer;
  Timer? _connectionTimeoutTimer;
  
  final List<WSConnectionEvent> _eventLog = [];
  final List<CollaborativeOp> _pendingOps = [];

  final WebSocketConfig _config;
  final StreamController<WSConnectionEvent> _eventController = StreamController.broadcast();

  // 回调
  Function(String)? onConnected;
  Function(String)? onDisconnected;
  Function(String)? onError;
  Function(CollaborativeOp)? onRemoteOp;
  Function(Map<String, String>)? onUsersUpdate;

  WebSocketManager(this._config) {
    _registerDefaultHandlers();
  }

  // ========== 连接管理 ==========

  /// 连接到 WebSocket 服务器
  Future<bool> connect() async {
    if (_state == WebSocketState.connecting || _state == WebSocketState.connected) {
      debugPrint('[WS] 已经连接中或已连接，跳过');
      return _state == WebSocketState.connected;
    }

    debugPrint('[WS] ========== 开始连接 WebSocket ==========');
    debugPrint('[WS] 服务器: ${_config.serverUrl}');
    debugPrint('[WS] 文档ID: ${_config.documentId}');
    debugPrint('[WS] 用户ID: ${_config.userId}');
    debugPrint('[WS] 用户名: ${_config.userName}');
    debugPrint('[WS] 版本: $_version');
    debugPrint('[WS] 备用服务器: [${_config.serverUrl}]');

    _setState(WebSocketState.connecting);
    _logEvent(WSConnectionEvent(type: 'connecting', timestamp: DateTime.now()));

    try {
      // 设置连接超时
      _connectionTimeoutTimer = Timer(_config.connectionTimeout, () {
        debugPrint('[WS] ✗ 连接超时 (${_config.connectionTimeout.inSeconds}s)');
        _setState(WebSocketState.error);
        _errorMessage = '连接超时';
        onDisconnected?.call('连接超时');
        _notifyError('连接超时，请检查网络连接');
        _handleConnectionError(e);
      });

      // 创建 WebSocket 连接
      debugPrint('[WS] 正在建立 WebSocket 连接...');
      _channel = IOWebSocketChannel.connect(
        Uri.parse(_config.serverUrl),
        headers: _config.headers,
      );

      // 等待连接建立
      await Future.delayed(const Duration(milliseconds: 100));
      
      if (_channel?.stream == null) {
        throw Exception('WebSocket 流为空');
      }

      debugPrint('[WS] ✓ WebSocket 连接建立成功');
      _connectionTimeoutTimer?.cancel();
      
      // 注册消息处理器
      _setupMessageListener();
      
      // 发送加入消息
      await _sendJoinMessage();
      
      // 启动心跳
      _startHeartbeat();
      
      _reconnectAttempts = 0;
      _consecutiveFailures = 0; // 重置失败计数
      _setState(WebSocketState.connected);
      _errorMessage = null;
      
      debugPrint('[WS] ========== 连接完成 ==========');
      debugPrint('[WS] 连接状态: connected');
      debugPrint('[WS] 消息处理器已注册');
      debugPrint('[WS] 心跳已启动 (${_config.heartbeatInterval.inSeconds}s 间隔)');
      
      onConnected?.call('连接成功');
      _logEvent(WSConnectionEvent(type: 'connected', timestamp: DateTime.now()));
      
      notifyListeners();
      return true;
      
    } catch (e, stackTrace) {
      debugPrint('[WS] ========== 连接失败 ==========');
      debugPrint('[WS] ✗ 错误: $e');
      debugPrint('[WS] 堆栈: $stackTrace');
      
      _connectionTimeoutTimer?.cancel();
      _setState(WebSocketState.error);
      _errorMessage = e.toString();
      
      onDisconnected?.call(e.toString());
      _notifyError(e.toString());
      _logEvent(WSConnectionEvent(type: 'error', data: e.toString(), timestamp: DateTime.now()));

      _handleConnectionError(e);
      
      notifyListeners();
      return false;
    }
  }

  /// 断开 WebSocket 连接
  void disconnect({bool reconnect = false}) {
    debugPrint('[WS] ========== 开始断开连接 ==========');
    
    _reconnectTimer?.cancel();
    _heartbeatTimer?.cancel();
    _connectionTimeoutTimer?.cancel();
    
    try {
      _channel?.sink.close();
      debugPrint('[WS] ✓ WebSocket 通道已关闭');
    } catch (e) {
      debugPrint('[WS] ✗ 关闭通道时出错: $e');
    }
    
    _channel = null;
    _setState(reconnect ? WebSocketState.reconnecting : WebSocketState.disconnected);
    
    debugPrint('[WS] 连接状态: ${_state.name}');
    debugPrint('[WS] ========== 断开完成 ==========');
    
    onDisconnected?.call('主动断开');
    _logEvent(WSConnectionEvent(type: 'disconnected', timestamp: DateTime.now()));
    
    notifyListeners();
  }

  /// 重连
  void reconnect() {
    debugPrint('[WS] ========== 开始重连 ==========');
    debugPrint('[WS] 当前重连次数: ${_reconnectAttempts}/${_config.maxReconnectAttempts}');
    debugPrint('[WS] 服务器地址: ${_config.serverUrl}');
    debugPrint('[WS] 文档ID: ${_config.documentId}');
    debugPrint('[WS] 用户ID: ${_config.userId}');
    
    // 记录重连尝试历史
    final reconnectLog = '[WS] 重连历史: 第${_reconnectAttempts}次尝试';
    debugPrint(reconnectLog);
    
    if (_reconnectAttempts >= _config.maxReconnectAttempts) {
      debugPrint('[WS] ========== 重连失败 ==========');
      debugPrint('[WS] ✗ 已达到最大重连次数 (${_config.maxReconnectAttempts}次)');
      debugPrint('[WS] ✗ 最后错误: ${_errorMessage ?? "未知错误"}');
      debugPrint('[WS] ✗ 建议: 请检查网络连接或手动刷新页面');
      debugPrint('[WS] ========== 重连结束 ==========');
      
      _setState(WebSocketState.error);
      _errorMessage = '重连失败: 已尝试 ${_config.maxReconnectAttempts} 次';
      _notifyError(_errorMessage ?? '重连失败');
      
      // 触发重连失败事件
      _logEvent(WSConnectionEvent(
        type: 'reconnect_failed',
        timestamp: DateTime.now(),
        data: {
          'attempts': _reconnectAttempts,
          'maxAttempts': _config.maxReconnectAttempts,
          'lastError': _errorMessage,
          'serverUrl': _config.serverUrl,
        },
      ));
      return;
    }
    
    _reconnectAttempts++;
    _setState(WebSocketState.reconnecting);
    _logEvent(WSConnectionEvent(type: 'reconnecting', timestamp: DateTime.now()));
    
    // 指数退避重连
    final delay = _config.reconnectDelay * _reconnectAttempts;
    debugPrint('[WS] 将在 ${delay.inSeconds}s 后重试...');
    debugPrint('[WS] 退避策略: ${_config.reconnectDelay.inSeconds}s × $_reconnectAttempts = ${delay.inSeconds}s');
    
    _reconnectTimer = Timer(delay, () {
      debugPrint('[WS] ========== 开始第 $_reconnectAttempts 次重连 ==========');
      connect().then((success) {
        if (success) {
          debugPrint('[WS] ========== 重连成功 ==========');
          debugPrint('[WS] ✓ 成功连接到服务器');
          debugPrint('[WS] ✓ 待发送操作数: ${_pendingOps.length}');
          _flushPendingOps();
          _reconnectAttempts = 0; // 重置重连计数
        } else {
          debugPrint('[WS] ========== 第 $_reconnectAttempts 次重连失败 ==========');
          debugPrint('[WS] ✗ 错误: ${_errorMessage ?? "未知错误"}');
          debugPrint('[WS] ✗ 继续尝试重连...');
          debugPrint('[WS] ========== 重连失败结束 ==========');
          reconnect();
        }
      }).catchError((error) {
        debugPrint('[WS] ========== 第 $_reconnectAttempts 次重连异常 ==========');
        debugPrint('[WS] ✗ 异常类型: ${error.runtimeType}');
        debugPrint('[WS] ✗ 异常信息: $error');
        debugPrint('[WS] ========== 重连异常结束 ==========');
        reconnect();
      });
    });
  }

  // ========== 消息发送 ==========

  /// 发送操作到服务器
  Future<void> sendOp(CollaborativeOp op) async {
    debugPrint('[WS] 发送操作: ${op.id} (类型: ${op.type.name})');
    
    if (_state != WebSocketState.connected) {
      debugPrint('[WS] ⚠️ 未连接，操作已暂存 (队列长度: ${_pendingOps.length + 1})');
      _pendingOps.add(op);
      return;
    }
    
    try {
      final message = {
        'type': WSMessageType.op,
        'op': op.toMap(),
        'timestamp': DateTime.now().toIso8601String(),
      };
      
      _channel?.sink.add(jsonEncode(message));
      debugPrint('[WS] ✓ 操作已发送到服务器');
    } catch (e) {
      debugPrint('[WS] ✗ 发送操作失败: $e');
      _pendingOps.add(op);
      _notifyError('发送操作失败: $e');
    }
  }

  /// 发送心跳
  void _sendHeartbeat() {
    if (_state != WebSocketState.connected) return;
    
    try {
      _channel?.sink.add(jsonEncode({
        'type': WSMessageType.heartbeat,
        'timestamp': DateTime.now().toIso8601String(),
      }));
      debugPrint('[WS] 发送心跳');
    } catch (e) {
      debugPrint('[WS] ✗ 发送心跳失败: $e');
    }
  }

  // ========== 消息处理 ==========

  void _setupMessageListener() {
    debugPrint('[WS] 设置消息监听器...');
    
    _channel?.stream.listen(
      (dynamic data) {
        try {
          final message = jsonDecode(data as String) as Map<String, dynamic>;
          final type = message['type'] as String?;
          
          debugPrint('[WS] 收到消息: $type');
          
          switch (type) {
            case WSMessageType.ack:
              _handleAck(message);
              break;
            case WSMessageType.heartbeat:
              _handleHeartbeat(message);
              break;
            case WSMessageType.pong:
              _handlePong(message);
              break;
            case WSMessageType.op:
              _handleRemoteOp(message);
              break;
            case WSMessageType.cursor:
              _handleCursor(message);
              break;
            case WSMessageType.sync:
              _handleSync(message);
              break;
            case WSMessageType.error:
              _handleError(message);
              break;
            case WSMessageType.join:
              _handleUserJoin(message);
              break;
            case WSMessageType.leave:
              _handleUserLeave(message);
              break;
            default:
              debugPrint('[WS] 未知消息类型: $type');
          }
        } catch (e) {
          debugPrint('[WS] ✗ 处理消息失败: $e');
        }
      },
      onError: (error) {
        debugPrint('[WS] ✗ WebSocket 错误: $error');
        _handleConnectionError(error);
      },
      onDone: () {
        debugPrint('[WS] WebSocket 连接关闭');
        _handleConnectionClosed();
      },
    );
    
    debugPrint('[WS] ✓ 消息监听器已设置');
  }

  void _handleAck(Map<String, dynamic> message) {
    debugPrint('[WS] 收到操作确认: ${message['opId']}');
    // 可以从 pendingOps 中移除已确认的操作
  }

  void _handleHeartbeat(Map<String, dynamic> message) {
    debugPrint('[WS] 收到服务器心跳');
    // 发送 pong 响应
    _channel?.sink.add(jsonEncode({
      'type': WSMessageType.pong,
      'timestamp': DateTime.now().toIso8601String(),
    }));
  }

  void _handlePong(Map<String, dynamic> message) {
    debugPrint('[WS] 收到服务器 pong');
  }

  void _handleRemoteOp(Map<String, dynamic> message) {
    debugPrint('[WS] 收到远程操作: ${message['op']['id']} by ${message['op']['userId']}');
    final op = CollaborativeOp.fromMap(message['op'] as Map<String, dynamic>);
    onRemoteOp?.call(op);
  }

  void _handleCursor(Map<String, dynamic> message) {
    debugPrint('[WS] 收到光标移动: ${message['userId']} -> ${message['position']}');
  }

  void _handleSync(Map<String, dynamic> message) {
    debugPrint('[WS] 收到同步消息: ${message['type']}');
  }

  void _handleError(Map<String, dynamic> message) {
    debugPrint('[WS] ✗ 服务器错误: ${message['message']}');
    _notifyError(message['message'] as String? ?? '未知错误');
  }

  void _handleUserJoin(Map<String, dynamic> message) {
    debugPrint('[WS] 用户加入: ${message['userName']} (${message['userId']})');
  }

  void _handleUserLeave(Map<String, dynamic> message) {
    debugPrint('[WS] 用户离开: ${message['userName']} (${message['userId']})');
  }

  void _handleConnectionError(dynamic error) {
    debugPrint('[WS] ========== 连接错误 ==========');
    debugPrint('[WS] 错误类型: ${error.runtimeType}');
    debugPrint('[WS] 错误详情: $error');
    debugPrint('[WS] 当前状态: ${_state.name}');
    debugPrint('[WS] 服务器地址: ${_config.serverUrl}');
    
    // 记录错误到事件日志
    _logEvent(WSConnectionEvent(
      type: 'connection_error',
      timestamp: DateTime.now(),
      data: {
        'error': error.toString(),
        'errorType': error.runtimeType.toString(),
        'serverUrl': _config.serverUrl,
        'documentId': _config.documentId,
        'state': _state.name,
      },
    ));
    
    _setState(WebSocketState.error);
    _errorMessage = error.toString();
    _notifyError(error.toString());
    
    // 自动重连
    if (_state != WebSocketState.reconnecting) {
      debugPrint('[WS] 尝试自动重连...');
      reconnect();
    }
    debugPrint('[WS] ========== 连接错误处理完成 ==========');
  }

  void _handleConnectionClosed() {
    debugPrint('[WS] ========== 连接关闭 ==========');
    debugPrint('[WS] 当前状态: ${_state.name}');
    debugPrint('[WS] 待发送操作数: ${_pendingOps.length}');
    debugPrint('[WS] 已重连次数: ${_reconnectAttempts}/${_config.maxReconnectAttempts}');
    
    // 记录关闭事件
    _logEvent(WSConnectionEvent(
      type: 'connection_closed',
      timestamp: DateTime.now(),
      data: {
        'state': _state.name,
        'pendingOps': _pendingOps.length,
        'reconnectAttempts': _reconnectAttempts,
      },
    ));
    
    if (_state != WebSocketState.disconnected) {
      debugPrint('[WS] 连接意外关闭，尝试重连...');
      reconnect();
    }
    debugPrint('[WS] ========== 连接关闭处理完成 ==========');
  }

  // ========== 心跳管理 ==========

  void _startHeartbeat() {
    debugPrint('[WS] 启动心跳 (${_config.heartbeatInterval.inSeconds}s 间隔)');
    _heartbeatTimer?.cancel();
    _heartbeatTimer = Timer.periodic(_config.heartbeatInterval, (_) {
      _sendHeartbeat();
    });
  }

  // ========== 内部方法 ==========

  void _setState(WebSocketState state) {
    _state = state;
    debugPrint('[WS] 状态变更: ${_state.name}');
  }

  Future<void> _sendJoinMessage() async {
    debugPrint('[WS] 发送加入消息...');
    final message = {
      'type': WSMessageType.join,
      'documentId': _config.documentId,
      'userId': _config.userId,
      'userName': _config.userName,
      'clientVersion': _version,
      'timestamp': DateTime.now().toIso8601String(),
    };
    
    _channel?.sink.add(jsonEncode(message));
    debugPrint('[WS] ✓ 加入消息已发送');
  }

  void _flushPendingOps() {
    debugPrint('[WS] 刷新待发送操作 (${_pendingOps.length} 个)');
    for (final op in _pendingOps.toList()) {
      sendOp(op);
    }
    _pendingOps.clear();
  }

  void _logEvent(WSConnectionEvent event) {
    _eventLog.add(event);
    _eventController.add(event);
    
    // 只保留最近 100 条事件
    if (_eventLog.length > 100) {
      _eventLog.removeAt(0);
    }
  }

  void _notifyError(String message) {
    onError?.call(message);
  }

  void _registerDefaultHandlers() {
    debugPrint('[WS] 注册默认消息处理器');
  }

  // ========== 属性 ==========

  WebSocketState get state => _state;
  
  /// 获取服务器信息
  String get currentServer => _config.serverUrl;
  List<String> get backupServers => [_config.serverUrl];
  bool get hasBackupServers => false;
  String? get errorMessage => _errorMessage;
  bool get isConnected => _state == WebSocketState.connected;
  bool get isConnecting => _state == WebSocketState.connecting;
  bool get isReconnecting => _state == WebSocketState.reconnecting;
  int get reconnectAttempts => _reconnectAttempts;
  int get pendingOpsCount => _pendingOps.length;
  List<WSConnectionEvent> get eventLog => List.unmodifiable(_eventLog);
  
  Stream<WSConnectionEvent> get eventStream => _eventController.stream;

  // ========== 生命周期 ==========

  @override
  void dispose() {
    debugPrint('[WS] ========== 释放资源 ==========');
    _reconnectTimer?.cancel();
    _heartbeatTimer?.cancel();
    _connectionTimeoutTimer?.cancel();
    _channel?.sink.close();
    _eventController.close();
    debugPrint('[WS] ✓ 资源已释放');
    super.dispose();
  }
}
