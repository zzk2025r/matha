// Matha 协作功能 - WebSocket 连接管理器
// 实现实时通信、断线重连、心跳检测

import 'dart:async';
import 'dart:convert';
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

/// WebSocket 配置
class WebSocketConfig {
  final String serverUrl;
  final String documentId;
  final String userId;
  final String userName;
  final Duration reconnectDelay;
  final int maxReconnectAttempts;
  final Duration heartbeatInterval;
  final Duration connectionTimeout;
  final Map<String, String> headers;

  const WebSocketConfig({
    required this.serverUrl,
    required this.documentId,
    required this.userId,
    required this.userName,
    this.reconnectDelay = const Duration(seconds: 3),
    this.maxReconnectAttempts = 5,
    this.heartbeatInterval = const Duration(seconds: 30),
    this.connectionTimeout = const Duration(seconds: 10),
    this.headers = const {},
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

  WebSocketState get state => _state;
  String? get errorMessage => _errorMessage;
  int get reconnectAttempts => _reconnectAttempts;
  List<WSConnectionEvent> get eventLog => List.unmodifiable(_eventLog);

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
        _handleConnectionError('连接超时');
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
  Future<void> disconnect() async {
    debugPrint('[WS] 断开 WebSocket 连接...');
    _reconnectTimer?.cancel();
    _heartbeatTimer?.cancel();
    _connectionTimeoutTimer?.cancel();
    
    _channel?.sink.close();
    _channel = null;
    
    _setState(WebSocketState.disconnected);
    _logEvent(WSConnectionEvent(type: 'disconnected', timestamp: DateTime.now()));
    
    onDisconnected?.call('已断开连接');
    notifyListeners();
  }

  // ========== 消息发送 ==========

  /// 发送操作
  void sendOp(CollaborativeOp op) {
    if (_state != WebSocketState.connected) {
      debugPrint('[WS] 未连接，操作已缓存: ${op.id}');
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
          
          switch (type) {
            case WSMessageType.join:
              _handleJoin(message);
              break;
            case WSMessageType.leave:
              _handleLeave(message);
              break;
            case WSMessageType.op:
              _handleRemoteOp(message);
              break;
            case WSMessageType.ack:
              _handleAck(message);
              break;
            case WSMessageType.heartbeat:
              _handleHeartbeat(message);
              break;
            case WSMessageType.pong:
              _handlePong(message);
              break;
            case WSMessageType.cursor:
              _handleCursor(message);
              break;
            case WSMessageType.error:
              _handleError(message);
              break;
            default:
              debugPrint('[WS] 未知消息类型: $type');
          }
        } catch (e) {
          debugPrint('[WS] ✗ 处理消息失败: $e');
        }
      },
      onError: (error) {
        debugPrint('[WS] ✗ 流错误: $error');
        _handleConnectionError(error);
      },
      onDone: () {
        debugPrint('[WS] 连接已关闭');
        if (_state == WebSocketState.connected || _state == WebSocketState.reconnecting) {
          _handleConnectionError('连接已关闭');
        }
      },
    );
  }

  void _handleJoin(Map<String, dynamic> message) {
    debugPrint('[WS] 收到加入消息');
  }

  void _handleLeave(Map<String, dynamic> message) {
    debugPrint('[WS] 收到离开消息');
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

  void _handleError(Map<String, dynamic> message) {
    debugPrint('[WS] 收到错误: ${message['message']}');
    _notifyError(message['message'] as String? ?? '未知错误');
  }

  // ========== 重连管理 ==========

  void _handleConnectionError(dynamic error) {
    debugPrint('[WS] ========== 处理连接错误 ==========');
    debugPrint('[WS] 错误: $error');
    
    _reconnectTimer?.cancel();
    _heartbeatTimer?.cancel();
    _connectionTimeoutTimer?.cancel();
    
    if (_state != WebSocketState.disconnected) {
      _setState(WebSocketState.reconnecting);
      _notifyError('连接断开: $error');
      
      // 指数退避重连
      final delay = _config.reconnectDelay * (_reconnectAttempts + 1);
      debugPrint('[WS] 退避策略: ${_config.reconnectDelay.inSeconds}s × ${_reconnectAttempts + 1} = ${delay.inSeconds}s');
      
      _reconnectTimer = Timer(delay, () {
        if (_state == WebSocketState.disconnected) return;
        
        debugPrint('[WS] ========== 开始第 ${_reconnectAttempts + 1} 次重连 ==========');
        _setState(WebSocketState.reconnecting);
        
        connect().then((success) {
          if (success) {
            _reconnectAttempts = 0;
            debugPrint('[WS] ========== 重连成功 ==========');
          } else {
            _reconnectAttempts++;
            debugPrint('[WS] ========== 第 ${_reconnectAttempts} 次重连失败 ==========');
            
            if (_reconnectAttempts >= _config.maxReconnectAttempts) {
              debugPrint('[WS] ✗ 达到最大重连次数');
              _setState(WebSocketState.error);
              _errorMessage = '重连失败: 达到最大次数 ${_config.maxReconnectAttempts}';
              onDisconnected?.call(_errorMessage!);
            }
          }
        }).catchError((e) {
          debugPrint('[WS] ========== 第 ${_reconnectAttempts + 1} 次重连异常 ==========');
          _reconnectAttempts++;
        });
      });
    }
  }

  // ========== 心跳管理 ==========

  void _startHeartbeat() {
    _heartbeatTimer?.cancel();
    _heartbeatTimer = Timer.periodic(_config.heartbeatInterval, (_) {
      _sendHeartbeat();
    });
    debugPrint('[WS] ✓ 心跳已启动 (${_config.heartbeatInterval.inSeconds}s 间隔)');
  }

  // ========== 辅助方法 ==========

  void _setState(WebSocketState newState) {
    _state = newState;
    debugPrint('[WS] 状态变更: ${newState.name}');
  }

  void _notifyError(String message) {
    onError?.call(message);
    _logEvent(WSConnectionEvent(type: 'error', data: message, timestamp: DateTime.now()));
  }

  void _logEvent(WSConnectionEvent event) {
    _eventLog.add(event);
    _eventController.add(event);
    
    // 限制日志数量
    if (_eventLog.length > 100) {
      _eventLog.removeAt(0);
    }
  }

  Future<void> _sendJoinMessage() async {
    final message = {
      'type': WSMessageType.join,
      'sessionId': _config.documentId,
      'userId': _config.userId,
      'userName': _config.userName,
      'clientVersion': _version,
      'timestamp': DateTime.now().toIso8601String(),
    };
    
    _channel?.sink.add(jsonEncode(message));
    debugPrint('[WS] ✓ 加入消息已发送');
  }

  void _registerDefaultHandlers() {
    onError ??= (msg) => debugPrint('[WS] 错误: $msg');
    onConnected ??= (msg) => debugPrint('[WS] 已连接: $msg');
    onDisconnected ??= (msg) => debugPrint('[WS] 已断开: $msg');
    onRemoteOp ??= (op) => debugPrint('[WS] 远程操作: ${op.id}');
  }

  // ========== 统计信息 ==========

  Map<String, dynamic> getStats() {
    return {
      'state': _state.name,
      'reconnectAttempts': _reconnectAttempts,
      'pendingOps': _pendingOps.length,
      'eventLogSize': _eventLog.length,
    };
  }
}
