// Matha 协作功能 - 权限系统

import 'package:flutter/material.dart';

/// 权限级别
enum PermissionLevel {
  owner,      // 所有者
  editor,     // 编辑者
  commenter,  // 评论者
  viewer,     // 查看者
}

/// 权限类型
class PermissionType {
  final String name;
  final PermissionLevel level;
  final Set<String> actions;

  const PermissionType({
    required this.name,
    required this.level,
    required this.actions,
  });

  static const PermissionType owner = PermissionType(
    name: '所有者',
    level: PermissionLevel.owner,
    actions: {'read', 'write', 'comment', 'share', 'delete', 'manage_permissions'},
  );

  static const PermissionType editor = PermissionType(
    name: '编辑者',
    level: PermissionLevel.editor,
    actions: {'read', 'write', 'comment'},
  );

  static const PermissionType commenter = PermissionType(
    name: '评论者',
    level: PermissionLevel.commenter,
    actions: {'read', 'comment'},
  );

  static const PermissionType viewer = PermissionType(
    name: '查看者',
    level: PermissionLevel.viewer,
    actions: {'read'},
  );

  static const List<PermissionType> all = [
    owner,
    editor,
    commenter,
    viewer,
  ];

  bool canPerform(String action) => actions.contains(action);
}

/// 权限分配
class PermissionAssignment {
  final String userId;
  final String userName;
  final String userEmail;
  final PermissionType permission;
  final DateTime grantedAt;
  final String grantedBy;

  const PermissionAssignment({
    required this.userId,
    required this.userName,
    required this.userEmail,
    required this.permission,
    required this.grantedAt,
    required this.grantedBy,
  });

  bool get isOwner => permission.level == PermissionLevel.owner;
  bool get canEdit => permission.canPerform('write');
  bool get canComment => permission.canPerform('comment');
  bool get canManage => permission.canPerform('manage_permissions');

  Map<String, dynamic> toMap() => {
    'userId': userId,
    'userName': userName,
    'userEmail': userEmail,
    'permission': permission.name,
    'grantedAt': grantedAt.toIso8601String(),
    'grantedBy': grantedBy,
  };

  factory PermissionAssignment.fromMap(Map<String, dynamic> map) => PermissionAssignment(
    userId: map['userId'] as String,
    userName: map['userName'] as String,
    userEmail: map['userEmail'] as String,
    permission: PermissionType.all.firstWhere(
      (p) => p.name == map['permission'],
      orElse: () => PermissionType.viewer,
    ),
    grantedAt: DateTime.parse(map['grantedAt'] as String),
    grantedBy: map['grantedBy'] as String,
  );
}

/// 权限管理器
class PermissionManager extends ChangeNotifier {
  final String documentId;
  final String ownerId;
  
  final Map<String, PermissionAssignment> _permissions = {};
  final List<Map<String, dynamic>> _permissionHistory = [];

  PermissionManager({
    required this.documentId,
    required this.ownerId,
  }) {
    // 所有者默认拥有所有权限
    _permissions[ownerId] = PermissionAssignment(
      userId: ownerId,
      userName: 'Owner',
      userEmail: '',
      permission: PermissionType.owner,
      grantedAt: DateTime.now(),
      grantedBy: ownerId,
    );
  }

  // ========== 权限查询 ==========

  /// 获取用户权限
  PermissionAssignment? getPermission(String userId) => _permissions[userId];

  /// 获取所有权限
  Map<String, PermissionAssignment> get permissions => Map.unmodifiable(_permissions);

  /// 检查用户是否有权限
  bool hasPermission(String userId, String action) {
    final permission = _permissions[userId];
    return permission?.permission.canPerform(action) ?? false;
  }

  /// 检查用户是否可以编辑
  bool canEdit(String userId) => hasPermission(userId, 'write');

  /// 检查用户是否可以评论
  bool canComment(String userId) => hasPermission(userId, 'comment');

  /// 检查用户是否可以管理权限
  bool canManagePermissions(String userId) => hasPermission(userId, 'manage_permissions');

  /// 获取可编辑用户列表
  List<PermissionAssignment> get editors => _permissions.values
      .where((p) => p.canEdit)
      .toList();

  /// 获取可评论用户列表
  List<PermissionAssignment> get commenters => _permissions.values
      .where((p) => p.canComment)
      .toList();

  // ========== 权限操作 ==========

  /// 授予权限
  void grantPermission({
    required String userId,
    required String userName,
    required String userEmail,
    required PermissionType permission,
  }) {
    if (!canManagePermissions(userId)) {
      throw Exception('没有权限管理');
    }

    _permissions[userId] = PermissionAssignment(
      userId: userId,
      userName: userName,
      userEmail: userEmail,
      permission: permission,
      grantedAt: DateTime.now(),
      grantedBy: ownerId,
    );

    _permissionHistory.add({
      'action': 'grant',
      'userId': userId,
      'userName': userName,
      'permission': permission.name,
      'timestamp': DateTime.now().toIso8601String(),
    });

    notifyListeners();
    debugPrint('[Permission] 授予权限: $userName -> ${permission.name}');
  }

  /// 撤销权限
  void revokePermission(String userId) {
    if (!canManagePermissions(userId)) {
      throw Exception('没有权限管理');
    }

    if (_permissions[userId]?.isOwner ?? false) {
      throw Exception('不能撤销所有者权限');
    }

    final user = _permissions[userId];
    _permissions.remove(userId);

    _permissionHistory.add({
      'action': 'revoke',
      'userId': userId,
      'userName': user?.userName,
      'timestamp': DateTime.now().toIso8601String(),
    });

    notifyListeners();
    debugPrint('[Permission] 撤销权限: ${user?.userName}');
  }

  /// 修改权限
  void updatePermission({
    required String userId,
    required PermissionType newPermission,
  }) {
    if (!canManagePermissions(userId)) {
      throw Exception('没有权限管理');
    }

    final user = _permissions[userId];
    if (user == null) {
      throw Exception('用户不存在');
    }

    if (user.isOwner && newPermission.level != PermissionLevel.owner) {
      throw Exception('不能修改所有者权限');
    }

    _permissions[userId] = PermissionAssignment(
      userId: userId,
      userName: user.userName,
      userEmail: user.userEmail,
      permission: newPermission,
      grantedAt: user.grantedAt,
      grantedBy: user.grantedBy,
    );

    _permissionHistory.add({
      'action': 'update',
      'userId': userId,
      'userName': user.userName,
      'oldPermission': user.permission.name,
      'newPermission': newPermission.name,
      'timestamp': DateTime.now().toIso8601String(),
    });

    notifyListeners();
    debugPrint('[Permission] 修改权限: ${user.userName} -> ${newPermission.name}');
  }

  // ========== 邀请系统 ==========

  /// 生成邀请链接
  String generateInviteLink(PermissionType permission) {
    final inviteId = DateTime.now().millisecondsSinceEpoch.toString();
    return 'https://matha.app/invite/$inviteId?permission=${permission.name}';
  }

  /// 处理邀请链接
  Future<bool> processInviteLink(String inviteId, PermissionType permission) async {
    // TODO: 实现邀请链接验证
    return true;
  }

  // ========== 历史记录 ==========

  List<Map<String, dynamic>> get permissionHistory => 
      List.unmodifiable(_permissionHistory);

  void clearHistory() {
    _permissionHistory.clear();
    notifyListeners();
  }
}
