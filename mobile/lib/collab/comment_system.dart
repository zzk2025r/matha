// Matha 协作功能 - 评论系统

import 'package:flutter/material.dart';
import '../database/math_database.dart';

/// 评论类型
enum CommentType {
  inline,      // 行内评论
  global,      // 全局评论
  snippet,     // 代码片段评论
}

/// 评论信息
class CommentInfo {
  final String commentId;
  final String userId;
  final String userName;
  final String userAvatar;
  final String content;
  final CommentType type;
  final int position;
  final int lineNumber;
  final DateTime timestamp;
  final List<String> mentions;
  final List<CommentReply> replies;

  const CommentInfo({
    required this.commentId,
    required this.userId,
    required this.userName,
    this.userAvatar = '',
    required this.content,
    required this.type,
    this.position = 0,
    this.lineNumber = 0,
    required this.timestamp,
    this.mentions = const [],
    this.replies = const [],
  });

  CommentInfo copyWith({
    String? commentId,
    String? userId,
    String? userName,
    String? userAvatar,
    String? content,
    CommentType? type,
    int? position,
    int? lineNumber,
    DateTime? timestamp,
    List<String>? mentions,
    List<CommentReply>? replies,
  }) => CommentInfo(
    commentId: commentId ?? this.commentId,
    userId: userId ?? this.userId,
    userName: userName ?? this.userName,
    userAvatar: userAvatar ?? this.userAvatar,
    content: content ?? this.content,
    type: type ?? this.type,
    position: position ?? this.position,
    lineNumber: lineNumber ?? this.lineNumber,
    timestamp: timestamp ?? this.timestamp,
    mentions: mentions ?? this.mentions,
    replies: replies ?? this.replies,
  );

  bool get hasReplies => replies.isNotEmpty;
  bool get isMentioned => mentions.contains(userId);

  Map<String, dynamic> toMap() => {
    'commentId': commentId,
    'userId': userId,
    'userName': userName,
    'userAvatar': userAvatar,
    'content': content,
    'type': type.name,
    'position': position,
    'lineNumber': lineNumber,
    'timestamp': timestamp.toIso8601String(),
    'mentions': mentions,
    'replies': replies.map((r) => r.toMap()).toList(),
  };

  factory CommentInfo.fromMap(Map<String, dynamic> map) => CommentInfo(
    commentId: map['commentId'] as String,
    userId: map['userId'] as String,
    userName: map['userName'] as String,
    userAvatar: map['userAvatar'] as String? ?? '',
    content: map['content'] as String,
    type: CommentType.values.firstWhere(
      (e) => e.name == map['type'],
      orElse: () => CommentType.global,
    ),
    position: map['position'] as int? ?? 0,
    lineNumber: map['lineNumber'] as int? ?? 0,
    timestamp: DateTime.parse(map['timestamp'] as String),
    mentions: List<String>.from(map['mentions'] ?? []),
    replies: (map['replies'] as List?)
        ?.map((e) => CommentReply.fromMap(e as Map<String, dynamic>))
        .toList() ?? [],
  );
}

/// 评论回复
class CommentReply {
  final String replyId;
  final String userId;
  final String userName;
  final String content;
  final DateTime timestamp;

  const CommentReply({
    required this.replyId,
    required this.userId,
    required this.userName,
    required this.content,
    required this.timestamp,
  });

  Map<String, dynamic> toMap() => {
    'replyId': replyId,
    'userId': userId,
    'userName': userName,
    'content': content,
    'timestamp': timestamp.toIso8601String(),
  };

  factory CommentReply.fromMap(Map<String, dynamic> map) => CommentReply(
    replyId: map['replyId'] as String,
    userId: map['userId'] as String,
    userName: map['userName'] as String,
    content: map['content'] as String,
    timestamp: DateTime.parse(map['timestamp'] as String),
  );
}

/// 评论管理器
class CommentManager extends ChangeNotifier {
  final String documentId;
  final MathDatabase _db = MathDatabase();
  
  final Map<String, CommentInfo> _comments = {};
  final List<String> _commentOrder = [];

  CommentManager({required this.documentId});

  // ========== 评论操作 ==========

  /// 添加评论
  Future<CommentInfo> addComment({
    required String userId,
    required String userName,
    required String content,
    CommentType type = CommentType.global,
    int position = 0,
    int lineNumber = 0,
    List<String> mentions = const [],
  }) async {
    final commentId = _generateCommentId();
    final now = DateTime.now();
    
    final comment = CommentInfo(
      commentId: commentId,
      userId: userId,
      userName: userName,
      content: content,
      type: type,
      position: position,
      lineNumber: lineNumber,
      timestamp: now,
      mentions: mentions,
    );

    // 保存到数据库
    await _db.addComment(
      commentId: commentId,
      userId: userId,
      userName: userName,
      content: content,
      position: position.toString(),
      documentId: documentId,
    );

    // 添加到本地缓存
    _comments[commentId] = comment;
    _commentOrder.insert(0, commentId);
    
    notifyListeners();
    debugPrint('[Comment] 添加评论: $commentId');
    
    return comment;
  }

  /// 添加回复
  Future<CommentInfo> addReply({
    required String commentId,
    required String userId,
    required String userName,
    required String content,
  }) async {
    if (!_comments.containsKey(commentId)) {
      throw Exception('评论不存在: $commentId');
    }

    final replyId = _generateReplyId();
    final now = DateTime.now();
    
    final reply = CommentReply(
      replyId: replyId,
      userId: userId,
      userName: userName,
      content: content,
      timestamp: now,
    );

    // 更新评论
    final comment = _comments[commentId]!;
    _comments[commentId] = comment.copyWith(
      replies: [...comment.replies, reply],
    );

    notifyListeners();
    debugPrint('[Comment] 添加回复: $replyId');
    
    return _comments[commentId]!;
  }

  /// 删除评论
  Future<void> deleteComment(String commentId) async {
    if (!_comments.containsKey(commentId)) {
      throw Exception('评论不存在: $commentId');
    }

    await _db.deleteComment(commentId);
    _comments.remove(commentId);
    _commentOrder.remove(commentId);
    
    notifyListeners();
    debugPrint('[Comment] 删除评论: $commentId');
  }

  /// 点赞评论
  Future<void> likeComment(String commentId, String userId) async {
    // TODO: 实现点赞功能
    debugPrint('[Comment] 点赞评论: $commentId by $userId');
  }

  // ========== 查询操作 ==========

  /// 获取所有评论
  List<CommentInfo> getComments() {
    return _commentOrder.map((id) => _comments[id]).whereType<CommentInfo>().toList();
  }

  /// 获取行内评论
  List<CommentInfo> getInlineComments() {
    return _comments.values
        .where((c) => c.type == CommentType.inline)
        .toList();
  }

  /// 获取全局评论
  List<CommentInfo> getGlobalComments() {
    return _comments.values
        .where((c) => c.type == CommentType.global)
        .toList();
  }

  /// 获取特定行的评论
  List<CommentInfo> getCommentsAtLine(int lineNumber) {
    return _comments.values
        .where((c) => c.lineNumber == lineNumber)
        .toList();
  }

  /// 获取未读评论数量
  int getUnreadCount(String currentUserId) {
    return _comments.values.where((c) => c.isMentioned && c.userId != currentUserId).length;
  }

  /// 检查评论是否存在
  bool hasComment(String commentId) => _comments.containsKey(commentId);

  /// 获取评论数量
  int get commentCount => _comments.length;

  // ========== 帮助方法 ==========

  String _generateCommentId() {
    return 'comment_${DateTime.now().millisecondsSinceEpoch}_${_comments.length}';
  }

  String _generateReplyId() {
    return 'reply_${DateTime.now().millisecondsSinceEpoch}_${DateTime.now().microsecond}';
  }
}

// 扩展方法
extension CommentInfoExtensions on CommentInfo {
  String get formattedTime {
    final now = DateTime.now();
    final diff = now.difference(timestamp);
    
    if (diff.inSeconds < 60) return '刚刚';
    if (diff.inMinutes < 60) return '${diff.inMinutes} 分钟前';
    if (diff.inHours < 24) return '${diff.inHours} 小时前';
    if (diff.inDays < 7) return '${diff.inDays} 天前';
    return '${timestamp.month}/${timestamp.day}';
  }
  
  String get previewContent => content.length > 100 ? '${content.substring(0, 100)}...' : content;
}
