// Matha 协作功能 - 实时语音通话
// 实现在协作会话内进行语音通话（成员管理 / 静音 / 发言状态）

import 'dart:async';
import 'package:flutter/material.dart';
import 'session_manager.dart';
import 'websocket_manager.dart';

/// 语音通话成员
class VoiceMember {
  final String userId;
  final String userName;
  final String userAvatar;
  bool muted;
  bool speaking;
  final DateTime joinedAt;

  VoiceMember({
    required this.userId,
    required this.userName,
    this.userAvatar = '',
    this.muted = false,
    this.speaking = false,
    required this.joinedAt,
  });

  VoiceMember copyWith({
    bool? muted,
    bool? speaking,
  }) {
    return VoiceMember(
      userId: userId,
      userName: userName,
      userAvatar: userAvatar,
      muted: muted ?? this.muted,
      speaking: speaking ?? this.speaking,
      joinedAt: joinedAt,
    );
  }

  Map<String, dynamic> toMap() => {
    'userId': userId,
    'userName': userName,
    'userAvatar': userAvatar,
    'muted': muted,
    'speaking': speaking,
    'joinedAt': joinedAt.toIso8601String(),
  };

  factory VoiceMember.fromMap(Map<String, dynamic> map) => VoiceMember(
    userId: map['userId'] as String,
    userName: map['userName'] as String? ?? 'User',
    userAvatar: map['userAvatar'] as String? ?? '',
    muted: map['muted'] as bool? ?? false,
    speaking: map['speaking'] as bool? ?? false,
    joinedAt: DateTime.parse(map['joinedAt'] as String? ?? DateTime.now().toIso8601String()),
  );
}

/// 语音通话管理器
class VoiceCallManager extends ChangeNotifier {
  final String documentId;

  final Map<String, VoiceMember> _members = {};
  final StreamController<VoiceMember> _joinController = StreamController.broadcast();
  final StreamController<String> _leaveController = StreamController.broadcast();

  WebSocketManager? _wsManager;
  bool _active = false;

  VoiceCallManager({required this.documentId});

  /// 连接实时通信通道
  void attachWebSocket(WebSocketManager? manager) {
    _wsManager = manager;
    if (manager != null) {
      manager.onCustomMessage = _handleServerMessage;
      debugPrint('[VoiceCall] WebSocket 通道已挂载');
    }
    notifyListeners();
  }

  void _handleServerMessage(Map<String, dynamic> message) {
    if (message['type'] != 'voice') return;
    final action = message['action'] as String?;
    final data = message['user'];
    if (data is! Map<String, dynamic>) return;

    switch (action) {
      case 'join':
        joinLocal(data);
      case 'leave':
        leaveLocal(data['userId'] as String? ?? '');
      case 'mute':
        setMutedLocal(data['userId'] as String? ?? '', data['muted'] as bool? ?? false);
      case 'speaking':
        setSpeakingLocal(data['userId'] as String? ?? '', data['speaking'] as bool? ?? false);
    }
  }

  // ========== 加入 / 离开 ==========

  /// 加入语音通话
  Future<void> join() async {
    final userId = SessionManager.currentUserId ?? 'unknown';
    if (_members.containsKey(userId)) return;
    final member = VoiceMember(
      userId: userId,
      userName: SessionManager.currentUserName ?? 'User',
      joinedAt: DateTime.now(),
    );
    _members[userId] = member;
    _active = true;
    _joinController.add(member);
    await _send('join', member.toMap());
    notifyListeners();
    debugPrint('[VoiceCall] 加入语音通话: $userId');
  }

  /// 离开语音通话
  Future<void> leave() async {
    final userId = SessionManager.currentUserId ?? 'unknown';
    if (!_members.containsKey(userId)) return;
    _members.remove(userId);
    if (_members.isEmpty) {
      _active = false;
    }
    _leaveController.add(userId);
    await _send('leave', {'userId': userId});
    notifyListeners();
    debugPrint('[VoiceCall] 离开语音通话: $userId');
  }

  /// 静音 / 取消静音
  Future<void> toggleMute() async {
    final userId = SessionManager.currentUserId ?? 'unknown';
    final member = _members[userId];
    if (member == null) return;
    await setMuted(userId, !member.muted);
  }

  /// 设置成员静音状态
  Future<void> setMuted(String userId, bool muted) async {
    setMutedLocal(userId, muted);
    await _send('mute', {'userId': userId, 'muted': muted});
    notifyListeners();
  }

  /// 设置成员发言状态
  Future<void> setSpeaking(String userId, bool speaking) async {
    setSpeakingLocal(userId, speaking);
    await _send('speaking', {'userId': userId, 'speaking': speaking});
    notifyListeners();
  }

  // ========== 本地状态更新 ==========

  void joinLocal(Map<String, dynamic> data) {
    final member = VoiceMember.fromMap(data);
    final existed = _members.containsKey(member.userId);
    _members[member.userId] = member;
    _active = true;
    if (!existed) {
      _joinController.add(member);
    }
    notifyListeners();
  }

  void leaveLocal(String userId) {
    if (userId.isEmpty || !_members.containsKey(userId)) return;
    _members.remove(userId);
    if (_members.isEmpty) {
      _active = false;
    }
    _leaveController.add(userId);
    notifyListeners();
  }

  void setMutedLocal(String userId, bool muted) {
    final member = _members[userId];
    if (member == null) return;
    _members[userId] = member.copyWith(muted: muted);
    notifyListeners();
  }

  void setSpeakingLocal(String userId, bool speaking) {
    final member = _members[userId];
    if (member == null) return;
    _members[userId] = member.copyWith(speaking: speaking);
    notifyListeners();
  }

  // ========== 查询 ==========

  /// 通话是否进行中
  bool get isActive => _active;

  Map<String, VoiceMember> get members => Map.unmodifiable(_members);

  List<VoiceMember> get memberList => _members.values.toList();

  int get memberCount => _members.length;

  int get speakingCount => _members.values.where((m) => m.speaking).length;

  int get mutedCount => _members.values.where((m) => m.muted).length;

  bool isMember(String userId) => _members.containsKey(userId);

  Stream<VoiceMember> get onMemberJoin => _joinController.stream;

  Stream<String> get onMemberLeave => _leaveController.stream;

  // ========== 发送 ==========

  Future<void> _send(String action, Map<String, dynamic> payload) async {
    final ws = _wsManager;
    if (ws == null) {
      debugPrint('[VoiceCall] 未连接 WebSocket，状态仅本地更新: $action');
      return;
    }
    ws.sendRawMessage({
      'type': 'voice',
      'action': action,
      'user': payload,
      'documentId': documentId,
      'timestamp': DateTime.now().toIso8601String(),
    });
  }

  // ========== 生命周期 ==========

  @override
  void dispose() {
    _joinController.close();
    _leaveController.close();
    super.dispose();
  }
}

/// 语音通话面板（简约 UI）
class VoiceCallPanel extends StatelessWidget {
  final VoiceCallManager manager;
  final VoidCallback? onJoin;
  final VoidCallback? onLeave;

  const VoiceCallPanel({
    super.key,
    required this.manager,
    this.onJoin,
    this.onLeave,
  });

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: manager,
      builder: (context, _) {
        final members = manager.memberList;
        return Card(
          elevation: 2,
          margin: const EdgeInsets.all(12),
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Row(
                  children: [
                    Icon(
                      Icons.headset,
                      color: manager.isActive ? Colors.green : Colors.grey,
                    ),
                    const SizedBox(width: 8),
                    Text(
                      manager.isActive
                          ? '语音通话中 (${manager.memberCount})'
                          : '语音通话',
                      style: const TextStyle(fontWeight: FontWeight.w600),
                    ),
                    const Spacer(),
                    if (manager.isMember(SessionManager.currentUserId ?? 'unknown'))
                      _ActionButton(label: '静音', onTap: () { manager.toggleMute(); })
                    else
                      _ActionButton(label: '加入', onTap: () { manager.join(); onJoin?.call(); }),
                  ],
                ),
                if (members.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 12,
                    children: members.map((m) =>
                      _MemberChip(member: m)
                    ).toList(),
                  ),
                ],
              ],
            ),
          ),
        );
      },
    );
  }
}

class _MemberChip extends StatelessWidget {
  final VoiceMember member;

  const _MemberChip({required this.member});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: Colors.grey[200],
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (member.speaking)
            Icon(Icons.graphic_eq, size: 16, color: Colors.green[600])
          else
            Icon(
              member.muted ? Icons.mic_off : Icons.mic,
              size: 16,
              color: member.muted ? Colors.red[400] : Colors.blueGrey,
            ),
          const SizedBox(width: 4),
          Text(member.userName, style: const TextStyle(fontSize: 12)),
        ],
      ),
    );
  }
}

class _ActionButton extends StatelessWidget {
  final String label;
  final VoidCallback onTap;

  const _ActionButton({required this.label, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return FilledButton.tonal(
      onPressed: onTap,
      style: FilledButton.styleFrom(
        visualDensity: VisualDensity.compact,
        padding: const EdgeInsets.symmetric(horizontal: 12),
      ),
      child: Text(label),
    );
  }
}