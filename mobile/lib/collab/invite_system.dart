// Matha 协作功能 - 邀请系统
// 实现通过链接邀请用户加入协作会话

import 'dart:async';
import 'package:flutter/material.dart';
import 'session_manager.dart' as sm;
import 'collab_engine.dart';

/// 邀请类型
enum InviteType {
  edit,      // 编辑权限
  comment,   // 评论权限
  view,      // 查看权限
}

/// 邀请信息
class InviteInfo {
  final String inviteId;
  final String documentId;
  final String createdBy;
  final String createdByName;
  final InviteType permission;
  final DateTime createdAt;
  final DateTime expiresAt;
  final int maxUses;
  final int useCount;
  final bool isActive;

  const InviteInfo({
    required this.inviteId,
    required this.documentId,
    required this.createdBy,
    required this.createdByName,
    required this.permission,
    required this.createdAt,
    required this.expiresAt,
    this.maxUses = 10,
    this.useCount = 0,
    required this.isActive,
  });

  bool get isExpired => DateTime.now().isAfter(expiresAt);
  bool get canUse => useCount < maxUses && isActive && !isExpired;
  bool get isSingleUse => maxUses == 1;

  Map<String, dynamic> toMap() => {
    'inviteId': inviteId,
    'documentId': documentId,
    'createdBy': createdBy,
    'createdByName': createdByName,
    'permission': permission.name,
    'createdAt': createdAt.toIso8601String(),
    'expiresAt': expiresAt.toIso8601String(),
    'maxUses': maxUses,
    'useCount': useCount,
    'isActive': isActive,
  };

  factory InviteInfo.fromMap(Map<String, dynamic> map) => InviteInfo(
    inviteId: map['inviteId'] as String,
    documentId: map['documentId'] as String,
    createdBy: map['createdBy'] as String,
    createdByName: map['createdByName'] as String,
    permission: InviteType.values.firstWhere(
      (e) => e.name == map['permission'],
      orElse: () => InviteType.edit,
    ),
    createdAt: DateTime.parse(map['createdAt'] as String),
    expiresAt: DateTime.parse(map['expiresAt'] as String),
    maxUses: map['maxUses'] as int? ?? 10,
    useCount: map['useCount'] as int? ?? 0,
    isActive: map['isActive'] as bool? ?? true,
  );
}

/// 邀请管理器
class InviteManager extends ChangeNotifier {
  final SessionManager _sessionManager;
  
  final Map<String, InviteInfo> _invites = {};
  final List<Map<String, dynamic>> _inviteHistory = [];
  
  InviteManager(this._sessionManager);

  // ========== 创建邀请 ==========

  /// 创建邀请链接
  Future<InviteInfo> createInvite({
    required String documentId,
    InviteType permission = InviteType.edit,
    int maxUses = 10,
    int expireHours = 7,
  }) async {
    debugPrint('[Invite] 创建邀请...');
    debugPrint('[Invite] 文档ID: $documentId');
    debugPrint('[Invite] 权限: ${permission.name}');
    debugPrint('[Invite] 最大使用次数: $maxUses');
    debugPrint('[Invite] 过期时间: ${expireHours} 小时');

    final inviteId = _generateInviteId();
    final now = DateTime.now();
    final expiresAt = now.add(Duration(hours: expireHours));

    final invite = InviteInfo(
      inviteId: inviteId,
      documentId: documentId,
      createdBy: sm.SessionManager.currentUserId ?? 'unknown',
      createdByName: sm.SessionManager.currentUserName ?? 'User',
      permission: permission,
      createdAt: now,
      expiresAt: expiresAt,
      maxUses: maxUses,
      isActive: true,
    );

    _invites[inviteId] = invite;
    _inviteHistory.add({
      'action': 'create',
      'inviteId': inviteId,
      'documentId': documentId,
      'permission': permission.name,
      'timestamp': now.toIso8601String(),
    });

    debugPrint('[Invite] ✓ 邀请创建成功');
    debugPrint('[Invite] 邀请ID: $inviteId');
    debugPrint('[Invite] 邀请链接: ${invite.shareLink}');

    notifyListeners();
    return invite;
  }

  /// 生成邀请链接
  String generateInviteLink(InviteInfo invite) {
    return 'https://matha.app/invite/${invite.inviteId}?doc=${invite.documentId}';
  }

  // ========== 接受邀请 ==========

  /// 接受邀请
  Future<bool> acceptInvite({
    required String inviteId,
    required String userId,
    required String userName,
  }) async {
    debugPrint('[Invite] 接受邀请...');
    debugPrint('[Invite] 邀请ID: $inviteId');

    final invite = _invites[inviteId];
    if (invite == null) {
      debugPrint('[Invite] ✗ 邀请不存在');
      return false;
    }

    if (!invite.canUse) {
      debugPrint('[Invite] ✗ 邀请已过期或已用完');
      return false;
    }

    // 创建或加入会话
    try {
      final session = await _sessionManager.joinSession(
        sessionId: invite.documentId,
        userId: userId,
        userName: userName,
      );

      debugPrint('[Invite] ✓ 成功加入会话: ${session.sessionId}');
      debugPrint('[Invite] 权限: ${invite.permission.name}');

      // 更新邀请使用次数
      _updateInviteUsage(inviteId);

      // 记录历史
      _inviteHistory.add({
        'action': 'accept',
        'inviteId': inviteId,
        'userId': userId,
        'userName': userName,
        'sessionId': session.sessionId,
        'timestamp': DateTime.now().toIso8601String(),
      });

      notifyListeners();
      return true;
    } catch (e) {
      debugPrint('[Invite] ✗ 加入会话失败: $e');
      return false;
    }
  }

  // ========== 邀请管理 ==========

  /// 撤销邀请
  void revokeInvite(String inviteId) {
    final invite = _invites[inviteId];
    if (invite != null) {
      _invites[inviteId] = InviteInfo(
        inviteId: invite.inviteId,
        documentId: invite.documentId,
        createdBy: invite.createdBy,
        createdByName: invite.createdByName,
        permission: invite.permission,
        createdAt: invite.createdAt,
        expiresAt: invite.expiresAt,
        maxUses: invite.maxUses,
        useCount: invite.useCount,
        isActive: false,
      );
      
      _inviteHistory.add({
        'action': 'revoke',
        'inviteId': inviteId,
        'timestamp': DateTime.now().toIso8601String(),
      });

      debugPrint('[Invite] 邀请已撤销: $inviteId');
      notifyListeners();
    }
  }

  /// 获取邀请信息
  InviteInfo? getInvite(String inviteId) => _invites[inviteId];

  /// 获取所有邀请
  Map<String, InviteInfo> get invites => Map.unmodifiable(_invites);

  /// 获取活跃邀请列表
  List<InviteInfo> get activeInvites => _invites.values
      .where((i) => i.isActive && !i.isExpired)
      .toList();

  /// 获取邀请历史
  List<Map<String, dynamic>> get history => List.unmodifiable(_inviteHistory);

  /// 获取邀请数量
  int get inviteCount => _invites.length;

  /// 获取活跃邀请数量
  int get activeInviteCount => activeInvites.length;

  // ========== 帮助方法 ==========

  String _generateInviteId() {
    return 'inv_${DateTime.now().millisecondsSinceEpoch}_${DateTime.now().microsecond}';
  }

  void _updateInviteUsage(String inviteId) {
    final invite = _invites[inviteId];
    if (invite != null) {
      _invites[inviteId] = InviteInfo(
        inviteId: invite.inviteId,
        documentId: invite.documentId,
        createdBy: invite.createdBy,
        createdByName: invite.createdByName,
        permission: invite.permission,
        createdAt: invite.createdAt,
        expiresAt: invite.expiresAt,
        maxUses: invite.maxUses,
        useCount: invite.useCount + 1,
        isActive: invite.useCount + 1 < invite.maxUses,
      );
    }
  }
}

// 邀请扩展方法
extension InviteInfoExtensions on InviteInfo {
  String get shareLink => 'https://matha.app/invite/$inviteId?doc=$documentId';
  String get timeRemaining {
    final diff = expiresAt.difference(DateTime.now());
    if (diff.inHours > 0) return '${diff.inHours} 小时';
    if (diff.inMinutes > 0) return '${diff.inMinutes} 分钟';
    return '即将过期';
  }
  String get permissionLabel {
    switch (permission) {
      case InviteType.edit: return '可编辑';
      case InviteType.comment: return '可评论';
      case InviteType.view: return '仅查看';
    }
  }
}
