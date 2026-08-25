// Matha 协作功能 - 实时聊天系统
// 实现在协作会话内进行实时聊天

import 'dart:async';
import 'package:flutter/material.dart';
import 'session_manager.dart';

/// 消息类型
enum MessageType {
  text,          // 文本消息
  system,        // 系统消息
  mention,       // @提及消息
  code,          // 代码块消息
  image,         // 图片消息
  reaction,      // 表情反应
}

/// 聊天消息
class ChatMessage {
  final String messageId;
  final String userId;
  final String userName;
  final String userAvatar;
  final MessageType type;
  final String content;
  final Map<String, dynamic>? metadata;
  final DateTime timestamp;
  final List<String> mentions;
  final List<Reaction> reactions;

  const ChatMessage({
    required this.messageId,
    required this.userId,
    required this.userName,
    this.userAvatar = '',
    required this.type,
    required this.content,
    this.metadata,
    required this.timestamp,
    this.mentions = const [],
    this.reactions = const [],
  });

  bool get isMine => userId == SessionManager.currentUserId;
  bool get hasMentions => mentions.isNotEmpty;
  bool get isSystem => type == MessageType.system;
  
  String get formattedTime {
    final now = DateTime.now();
    final diff = now.difference(timestamp);
    
    if (diff.inSeconds < 60) return '刚刚';
    if (diff.inMinutes < 60) return '${diff.inMinutes} 分钟前';
    if (diff.inHours < 24) return '${diff.inHours} 小时前';
    return '${timestamp.month}/${timestamp.day} ${timestamp.hour}:${timestamp.minute.toString().padLeft(2, '0')}';
  }

  Map<String, dynamic> toMap() => {
    'messageId': messageId,
    'userId': userId,
    'userName': userName,
    'userAvatar': userAvatar,
    'type': type.name,
    'content': content,
    'metadata': metadata,
    'timestamp': timestamp.toIso8601String(),
    'mentions': mentions,
    'reactions': reactions.map((r) => r.toMap()).toList(),
  };

  factory ChatMessage.fromMap(Map<String, dynamic> map) => ChatMessage(
    messageId: map['messageId'] as String,
    userId: map['userId'] as String,
    userName: map['userName'] as String,
    userAvatar: map['userAvatar'] as String? ?? '',
    type: MessageType.values.firstWhere(
      (e) => e.name == map['type'],
      orElse: () => MessageType.text,
    ),
    content: map['content'] as String,
    metadata: map['metadata'] as Map<String, dynamic>?,
    timestamp: DateTime.parse(map['timestamp'] as String),
    mentions: List<String>.from(map['mentions'] ?? []),
    reactions: (map['reactions'] as List?)
        ?.map((e) => Reaction.fromMap(e as Map<String, dynamic>))
        .toList() ?? [],
  );
}

/// 表情反应
class Reaction {
  final String emoji;
  final String userId;
  final String userName;
  final DateTime timestamp;

  const Reaction({
    required this.emoji,
    required this.userId,
    required this.userName,
    required this.timestamp,
  });

  Map<String, dynamic> toMap() => {
    'emoji': emoji,
    'userId': userId,
    'userName': userName,
    'timestamp': timestamp.toIso8601String(),
  };

  factory Reaction.fromMap(Map<String, dynamic> map) => Reaction(
    emoji: map['emoji'] as String,
    userId: map['userId'] as String,
    userName: map['userName'] as String,
    timestamp: DateTime.parse(map['timestamp'] as String),
  );
}

/// 聊天会话状态
class ChatSession {
  final String sessionId;
  final String documentId;
  final List<ChatMessage> messages;
  final int unreadCount;
  final DateTime lastActivity;
  final List<String> onlineUsers;

  const ChatSession({
    required this.sessionId,
    required this.documentId,
    required this.messages,
    this.unreadCount = 0,
    required this.lastActivity,
    this.onlineUsers = const [],
  });

  ChatSession copyWith({
    List<ChatMessage>? messages,
    int? unreadCount,
    DateTime? lastActivity,
    List<String>? onlineUsers,
  }) {
    return ChatSession(
      sessionId: sessionId,
      documentId: documentId,
      messages: messages ?? this.messages,
      unreadCount: unreadCount ?? this.unreadCount,
      lastActivity: lastActivity ?? this.lastActivity,
      onlineUsers: onlineUsers ?? this.onlineUsers,
    );
  }

  Map<String, dynamic> toMap() => {
    'sessionId': sessionId,
    'documentId': documentId,
    'messages': messages.map((m) => m.toMap()).toList(),
    'unreadCount': unreadCount,
    'lastActivity': lastActivity.toIso8601String(),
    'onlineUsers': onlineUsers,
  };
}

/// 实时聊天管理器
class ChatManager extends ChangeNotifier {
  final String documentId;
  
  final Map<String, ChatSession> _sessions = {};
  final Map<String, List<ChatMessage>> _messages = {};
  final StreamController<ChatMessage> _messageController = StreamController.broadcast();
  final StreamController<String> _typingController = StreamController.broadcast();
  
  String? _currentSessionId;
  int _unreadCount = 0;

  ChatManager({required this.documentId});

  // ========== 会话管理 ==========

  /// 获取或创建会话
  ChatSession getOrCreateSession(String sessionId) {
    if (!_sessions.containsKey(sessionId)) {
      _sessions[sessionId] = ChatSession(
        sessionId: sessionId,
        documentId: documentId,
        messages: [],
        lastActivity: DateTime.now(),
      );
      _messages[sessionId] = [];
      debugPrint('[Chat] 创建会话: $sessionId');
    }
    return _sessions[sessionId]!;
  }

  /// 切换会话
  void switchSession(String sessionId) {
    if (_currentSessionId != sessionId) {
      // 标记旧会话为已读
      if (_currentSessionId != null && _sessions.containsKey(_currentSessionId)) {
        _sessions[_currentSessionId!] = _sessions[_currentSessionId!]!.copyWith(
          unreadCount: 0,
        );
      }
      _currentSessionId = sessionId;
      debugPrint('[Chat] 切换到会话: $sessionId');
    }
    notifyListeners();
  }

  /// 获取当前会话
  ChatSession? get currentSession => 
      _currentSessionId != null ? _sessions[_currentSessionId] : null;

  // ========== 消息操作 ==========

  /// 发送消息
  Future<ChatMessage> sendMessage({
    required String sessionId,
    required String content,
    List<String> mentions = const [],
    Map<String, dynamic>? metadata,
  }) async {
    debugPrint('[Chat] 发送消息...');
    debugPrint('[Chat] 会话ID: $sessionId');
    debugPrint('[Chat] 内容长度: ${content.length}');
    debugPrint('[Chat] 提及: ${mentions.join(", ")}');

    final message = ChatMessage(
      messageId: _generateMessageId(),
      userId: SessionManager.currentUserId ?? 'unknown',
      userName: SessionManager.currentUserName ?? 'User',
      type: mentions.isNotEmpty ? MessageType.mention : MessageType.text,
      content: content,
      mentions: mentions,
      metadata: metadata,
      timestamp: DateTime.now(),
    );

    // 添加到本地
    _addMessage(sessionId, message);
    
    // 发送到服务器（TODO: 实现 WebSocket 发送）
    await _sendToServer(message);

    debugPrint('[Chat] ✓ 消息发送成功');
    notifyListeners();
    
    return message;
  }

  /// 添加消息到会话
  void _addMessage(String sessionId, ChatMessage message) {
    _messages.putIfAbsent(sessionId, () => []);
    _messages[sessionId]!.add(message);
    
    // 更新会话
    final session = _sessions[sessionId];
    if (session != null) {
      _sessions[sessionId] = session.copyWith(
        messages: List.from(session.messages)..add(message),
        lastActivity: DateTime.now(),
      );
    }
    
    // 如果不是当前会话，增加未读数
    if (sessionId != _currentSessionId) {
      _unreadCount++;
      _sessions[sessionId] = _sessions[sessionId]!.copyWith(
        unreadCount: session!.unreadCount + 1,
      );
    }
    
    // 触发事件
    _messageController.add(message);
  }

  /// 删除消息
  Future<void> deleteMessage(String sessionId, String messageId) async {
    debugPrint('[Chat] 删除消息: $messageId');
    
    final messages = _messages[sessionId];
    if (messages != null) {
      messages.removeWhere((m) => m.messageId == messageId);
      _sessions[sessionId] = _sessions[sessionId]!.copyWith(
        messages: List.from(messages),
      );
      notifyListeners();
    }
  }

  /// 添加表情反应
  Future<void> addReaction({
    required String sessionId,
    required String messageId,
    required String emoji,
  }) async {
    debugPrint('[Chat] 添加表情: $emoji');
    
    final messages = _messages[sessionId];
    if (messages == null) return;
    
    final message = messages.firstWhere(
      (m) => m.messageId == messageId,
      orElse: () => throw Exception('消息不存在'),
    );
    
    final newReaction = Reaction(
      emoji: emoji,
      userId: SessionManager.currentUserId ?? 'unknown',
      userName: SessionManager.currentUserName ?? 'User',
      timestamp: DateTime.now(),
    );
    
    // 更新消息反应
    final updatedReactions = [...message.reactions, newReaction];
    final updatedMessage = ChatMessage(
      messageId: message.messageId,
      userId: message.userId,
      userName: message.userName,
      userAvatar: message.userAvatar,
      type: message.type,
      content: message.content,
      metadata: message.metadata,
      timestamp: message.timestamp,
      mentions: message.mentions,
      reactions: updatedReactions,
    );
    
    final index = messages.indexWhere((m) => m.messageId == messageId);
    if (index >= 0) {
      messages[index] = updatedMessage;
      _sessions[sessionId] = _sessions[sessionId]!.copyWith(
        messages: List.from(messages),
      );
      notifyListeners();
    }
  }

  // ========== 输入状态 ==========

  /// 发送输入状态
  void sendTypingStatus(String sessionId) {
    _typingController.add(sessionId);
  }

  // ========== 查询操作 ==========

  /// 获取会话消息
  List<ChatMessage> getMessages(String sessionId) {
    return _messages[sessionId] ?? [];
  }

  /// 获取所有会话
  Map<String, ChatSession> get sessions => Map.unmodifiable(_sessions);

  /// 获取当前会话ID
  String? get currentSessionId => _currentSessionId;

  /// 获取未读消息数
  int get unreadCount => _unreadCount;

  /// 获取所有会话列表
  List<ChatSession> get sessionList => _sessions.values.toList()
    ..sort((a, b) => b.lastActivity.compareTo(a.lastActivity));

  // ========== 帮助方法 ==========

  String _generateMessageId() {
    return 'msg_${DateTime.now().millisecondsSinceEpoch}_${DateTime.now().microsecond}';
  }

  Future<void> _sendToServer(ChatMessage message) async {
    // TODO: 实现 WebSocket 发送
    debugPrint('[Chat] 发送消息到服务器: ${message.messageId}');
    await Future.delayed(const Duration(milliseconds: 100));
  }

  // ========== Stream ==========

  Stream<ChatMessage> get messageStream => _messageController.stream;
  Stream<String> get typingStream => _typingController.stream;

  // ========== 生命周期 ==========

  @override
  void dispose() {
    _messageController.close();
    _typingController.close();
    super.dispose();
  }
}

/// 聊天 UI 组件
class ChatMessageWidget extends StatelessWidget {
  final ChatMessage message;
  final bool showTime;

  const ChatMessageWidget({
    super.key,
    required this.message,
    this.showTime = false,
  });

  @override
  Widget build(BuildContext context) {
    final isMine = message.isMine;
    
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: Row(
        mainAxisAlignment: isMine ? MainAxisAlignment.end : MainAxisAlignment.start,
        children: [
          if (!isMine) ...[
            _UserAvatar(userName: message.userName),
            const SizedBox(width: 8),
          ],
          Flexible(
            child: Column(
              crossAxisAlignment: isMine ? CrossAxisAlignment.end : CrossAxisAlignment.start,
              children: [
                if (!isMine)
                  Text(
                    message.userName,
                    style: TextStyle(
                      fontSize: 12,
                      color: Colors.grey[600],
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                const SizedBox(height: 2),
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: isMine 
                        ? Theme.of(context).colorScheme.primary 
                        : Colors.grey[200],
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        message.content,
                        style: const TextStyle(fontSize: 14),
                      ),
                      if (message.reactions.isNotEmpty)
                        Wrap(
                          spacing: 4,
                          children: message.reactions.map((r) => 
                            _ReactionChip(emoji: r.emoji, count: 1)
                          ).toList(),
                        ),
                    ],
                  ),
                ),
                if (showTime)
                  Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Text(
                      message.formattedTime,
                      style: TextStyle(
                        fontSize: 10,
                        color: Colors.grey[500],
                      ),
                    ),
                  ),
              ],
            ),
          ),
          if (isMine) ...[
            const SizedBox(width: 8),
            _UserAvatar(userName: message.userName, isMe: true),
          ],
        ],
      ),
    );
  }
}

class _UserAvatar extends StatelessWidget {
  final String userName;
  final bool isMe;

  const _UserAvatar({required this.userName, this.isMe = false});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 32,
      height: 32,
      decoration: BoxDecoration(
        color: isMe ? Colors.blue : Colors.green,
        shape: BoxShape.circle,
      ),
      child: Center(
        child: Text(
          userName[0].toUpperCase(),
          style: const TextStyle(
            color: Colors.white,
            fontSize: 14,
            fontWeight: FontWeight.bold,
          ),
        ),
      ),
    );
  }
}

class _ReactionChip extends StatelessWidget {
  final String emoji;
  final int count;

  const _ReactionChip({required this.emoji, required this.count});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: Colors.grey[200],
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text('$emoji $count', style: const TextStyle(fontSize: 12)),
    );
  }
}
