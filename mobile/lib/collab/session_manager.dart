// Matha 协作功能 - 会话管理

import 'package:flutter/material.dart';
import 'collab_engine.dart';

/// 会话信息
class SessionInfo {
  final String sessionId;
  final String documentId;
  final String userId;
  final String userName;
  final DateTime createdAt;
  final DateTime lastActive;
  final int participantCount;
  final List<ParticipantInfo> participants;

  const SessionInfo({
    required this.sessionId,
    required this.documentId,
    required this.userId,
    required this.userName,
    required this.createdAt,
    required this.lastActive,
    required this.participantCount,
    required this.participants,
  });

  bool get isActive => DateTime.now().difference(lastActive).inMinutes < 5;
  bool get isMe => userId == SessionManager.currentUserId;

  Map<String, dynamic> toMap() => {
    'sessionId': sessionId,
    'documentId': documentId,
    'userId': userId,
    'userName': userName,
    'createdAt': createdAt.toIso8601String(),
    'lastActive': lastActive.toIso8601String(),
    'participantCount': participantCount,
    'participants': participants.map((p) => p.toMap()).toList(),
  };

  factory SessionInfo.fromMap(Map<String, dynamic> map) => SessionInfo(
    sessionId: map['sessionId'] as String,
    documentId: map['documentId'] as String,
    userId: map['userId'] as String,
    userName: map['userName'] as String,
    createdAt: DateTime.parse(map['createdAt'] as String),
    lastActive: DateTime.parse(map['lastActive'] as String),
    participantCount: map['participantCount'] as int,
    participants: (map['participants'] as List)
        .map((e) => ParticipantInfo.fromMap(e as Map<String, dynamic>))
        .toList(),
  );

  SessionInfo copyWith({
    String? sessionId,
    String? documentId,
    String? userId,
    String? userName,
    DateTime? createdAt,
    DateTime? lastActive,
    int? participantCount,
    List<ParticipantInfo>? participants,
  }) => SessionInfo(
    sessionId: sessionId ?? this.sessionId,
    documentId: documentId ?? this.documentId,
    userId: userId ?? this.userId,
    userName: userName ?? this.userName,
    createdAt: createdAt ?? this.createdAt,
    lastActive: lastActive ?? this.lastActive,
    participantCount: participantCount ?? this.participantCount,
    participants: participants ?? this.participants,
  );
}

/// 参与者信息
class ParticipantInfo {
  final String userId;
  final String userName;
  final String avatarUrl;
  final Color cursorColor;
  final bool isEditing;
  final int lastPosition;

  const ParticipantInfo({
    required this.userId,
    required this.userName,
    required this.avatarUrl,
    required this.cursorColor,
    required this.isEditing,
    required this.lastPosition,
  });

  Map<String, dynamic> toMap() => {
    'userId': userId,
    'userName': userName,
    'avatarUrl': avatarUrl,
    'cursorColor': cursorColor.value,
    'isEditing': isEditing,
    'lastPosition': lastPosition,
  };

  factory ParticipantInfo.fromMap(Map<String, dynamic> map) => ParticipantInfo(
    userId: map['userId'] as String,
    userName: map['userName'] as String,
    avatarUrl: map['avatarUrl'] as String,
    cursorColor: Color(map['cursorColor'] as int),
    isEditing: map['isEditing'] as bool,
    lastPosition: map['lastPosition'] as int,
  );
}

/// 会话管理器
class SessionManager extends ChangeNotifier {
  static String? currentUserId;
  static String? currentUserName;

  final Map<String, SessionInfo> _sessions = {};
  final Map<String, CollaborativeEngine> _engines = {};

  /// 创建新会话
  Future<SessionInfo> createSession({
    required String documentId,
    required String userName,
    List<String> inviteIds = const [],
  }) async {
    final sessionId = _generateSessionId();
    final now = DateTime.now();
    
    final session = SessionInfo(
      sessionId: sessionId,
      documentId: documentId,
      userId: currentUserId ?? 'user_$sessionId',
      userName: userName,
      createdAt: now,
      lastActive: now,
      participantCount: 1 + inviteIds.length,
      participants: [
        ParticipantInfo(
          userId: currentUserId ?? 'user_$sessionId',
          userName: userName,
          avatarUrl: '',
          cursorColor: Colors.blue,
          isEditing: true,
          lastPosition: 0,
        ),
        ...inviteIds.map((id) => ParticipantInfo(
          userId: id,
          userName: 'User $id',
          avatarUrl: '',
          cursorColor: _randomColor(),
          isEditing: false,
          lastPosition: 0,
        )),
      ],
    );

    _sessions[sessionId] = session;
    
    // 创建协作引擎
    _engines[sessionId] = CollaborativeEngine(
      documentId: documentId,
      userId: session.userId,
    );

    debugPrint('[Session] 创建会话: $sessionId');
    notifyListeners();
    
    return session;
  }

  /// 加入现有会话
  Future<SessionInfo> joinSession({
    required String sessionId,
    required String userId,
    required String userName,
  }) async {
    if (!_sessions.containsKey(sessionId)) {
      throw Exception('会话不存在: $sessionId');
    }

    final session = _sessions[sessionId]!.copyWith(
      participants: [
        ..._sessions[sessionId]!.participants,
        ParticipantInfo(
          userId: userId,
          userName: userName,
          avatarUrl: '',
          cursorColor: _randomColor(),
          isEditing: false,
          lastPosition: 0,
        ),
      ],
      participantCount: _sessions[sessionId]!.participantCount + 1,
    );

    _sessions[sessionId] = session;
    
    // 创建协作引擎
    _engines[sessionId] = CollaborativeEngine(
      documentId: session.documentId,
      userId: userId,
    );

    debugPrint('[Session] 加入会话: $sessionId');
    notifyListeners();
    
    return session;
  }

  /// 离开会话
  void leaveSession(String sessionId) {
    if (_sessions.containsKey(sessionId)) {
      _sessions.remove(sessionId);
      _engines.remove(sessionId);
      debugPrint('[Session] 离开会话: $sessionId');
      notifyListeners();
    }
  }

  /// 关闭会话
  void closeSession(String sessionId) {
    _engines[sessionId]?.disconnect();
    _sessions.remove(sessionId);
    _engines.remove(sessionId);
    debugPrint('[Session] 关闭会话: $sessionId');
    notifyListeners();
  }

  /// 获取会话
  SessionInfo? getSession(String sessionId) => _sessions[sessionId];

  /// 获取协作引擎
  CollaborativeEngine? getEngine(String sessionId) => _engines[sessionId];

  /// 获取所有会话
  Map<String, SessionInfo> get sessions => Map.unmodifiable(_sessions);

  /// 获取活动会话列表
  List<SessionInfo> get activeSessions => _sessions.values
      .where((s) => s.isActive)
      .toList()
    ..sort((a, b) => b.lastActive.compareTo(a.lastActive));

  /// 获取会话数量
  int get sessionCount => _sessions.length;

  /// 获取活动会话数量
  int get activeSessionCount => activeSessions.length;

  // ========== 帮助方法 ==========

  String _generateSessionId() {
    return 'session_${DateTime.now().millisecondsSinceEpoch}_${DateTime.now().microsecond}';
  }

  Color _randomColor() {
    final colors = [
      Colors.red, Colors.pink, Colors.purple, Colors.deepPurple,
      Colors.indigo, Colors.blue, Colors.lightBlue, Colors.cyan,
      Colors.teal, Colors.green, Colors.lightGreen, Colors.lime,
      Colors.yellow, Colors.amber, Colors.orange, Colors.deepOrange,
    ];
    return colors[DateTime.now().millisecond % colors.length];
  }
}

// 会话扩展方法
extension SessionInfoExtensions on SessionInfo {
  String get shareLink => 'https://matha.app/share/$sessionId';
  bool get canInvite => participantCount < 10;
}
