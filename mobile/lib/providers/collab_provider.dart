// Matha 协作 Provider - 协作子系统统一协调器
// 持有 WebSocket 连接与各协作管理器（变更历史 / 审计 / 语音 / 屏幕共享 /
// 聊天 / 评论 / 光标），在连接建立后统一挂载，保证多路消息监听互不覆盖。

import 'package:flutter/material.dart';
import '../collab/websocket_manager.dart';
import '../collab/collab_engine.dart';
import '../collab/session_manager.dart';
import '../collab/change_history.dart';
import '../collab/audit_log.dart';
import '../collab/voice_call.dart';
import '../collab/screen_share.dart';
import '../collab/chat_system.dart';
import '../collab/comment_system.dart';
import '../collab/cursor_sync.dart';

class CollabProvider extends ChangeNotifier {
  CollabProvider({String documentId = 'default_doc'})
      : _documentId = documentId {
    _engine = CollaborativeEngine(
      documentId: _documentId,
      userId: SessionManager.currentUserId ?? 'local_user',
    );
    changeHistory = ChangeHistoryManager(documentId: _documentId);
    audit = AuditManager(documentId: _documentId);
    voice = VoiceCallManager(documentId: _documentId);
    screenShare = ScreenShareManager(documentId: _documentId);
    chat = ChatManager(documentId: _documentId);
    comments = CommentManager(documentId: _documentId);
    cursors = CursorSyncController(_engine);
  }

  final String _documentId;
  late final CollaborativeEngine _engine;

  late final ChangeHistoryManager changeHistory;
  late final AuditManager audit;
  late final VoiceCallManager voice;
  late final ScreenShareManager screenShare;
  late final ChatManager chat;
  late final CommentManager comments;
  late final CursorSyncController cursors;

  WebSocketManager? _ws;
  bool _enabled = false;
  String _serverUrl = '';
  String? _lastError;
  String _userId = 'local_user';
  String _userName = 'User';

  String get documentId => _documentId;
  String get serverUrl => _serverUrl;
  bool get enabled => _enabled;
  bool get isConnected => _ws?.state == WebSocketState.connected;
  String? get lastError => _lastError;
  CollaborativeEngine get engine => _engine;

  String get userId => _userId = SessionManager.currentUserId ?? 'local_user';
  String get userName => SessionManager.currentUserName ?? 'User';

  /// 初始化本地协作身份（未连接时各管理器仍可本地记录/回放）
  void ensureIdentity({String? userId, String? userName}) {
    if (userId != null) SessionManager.currentUserId = userId;
    if (userName != null) SessionManager.currentUserName = userName;
    SessionManager.currentUserId ??= 'local_user';
    SessionManager.currentUserName ??= 'User';
    _userId = SessionManager.currentUserId!;
    _userName = SessionManager.currentUserName!;
    audit.record(userId: _userId, action: 'join', detail: '本地协作身份就绪');
    notifyListeners();
  }

  /// 连接协作服务器并挂载全部子系统
  Future<bool> connect({
    required String serverUrl,
    Map<String, String>? auth,
    String? userId,
    String? userName,
  }) async {
    ensureIdentity(userId: userId, userName: userName);
    _enabled = true;
    _serverUrl = serverUrl;
    _lastError = null;
    notifyListeners();

    await _engine.connect(serverUrl: serverUrl, auth: auth);
    _ws = _makeWsManager(serverUrl, auth);

    _ws!.onConnected = (_) {
      audit.record(userId: _userId, action: 'connect', detail: serverUrl);
      notifyListeners();
    };
    _ws!.onDisconnected = (msg) {
      audit.record(userId: _userId, action: 'disconnect', detail: msg);
      notifyListeners();
    };
    _ws!.onError = (msg) {
      _lastError = msg;
      notifyListeners();
    };
    // 挂载协作状态更新（非自定义消息路径）
    _ws!.onUsersUpdate = (users) => notifyListeners();
    _ws!.onRemoteOp = (op) {
      _engine.applyRemoteOp(op);
      notifyListeners();
    };
    _ws!.onCursorMove = (uid, pos) {
      cursors.updateRemoteCursor(
        uid,
        CursorPosition(
          line: pos ~/ 1000,
          column: pos % 1000,
          pixelOffset: Offset.zero,
        ),
      );
      notifyListeners();
    };

    // 多路自定义消息订阅：变更历史 / 审计 / 语音 / 屏幕共享 / 聊天
    changeHistory.attachWebSocket(_ws);
    audit.attachWebSocket(_ws);
    voice.attachWebSocket(_ws);
    screenShare.attachWebSocket(_ws);
    chat.attachWebSocket(_ws);

    final ok = await _ws!.connect();
    if (!ok) {
      _lastError = _ws!.errorMessage ?? '连接失败';
    }
    audit.record(
      userId: _userId,
      action: ok ? 'join' : 'join_failed',
      detail: ok ? serverUrl : (_lastError ?? ''),
    );
    notifyListeners();
    return ok;
  }

  WebSocketManager _makeWsManager(String serverUrl, Map<String, String>? auth) {
    return WebSocketManager(WebSocketConfig(
      serverUrl: serverUrl,
      documentId: _documentId,
      userId: _userId,
      userName: _userName,
      headers: auth ?? const {},
    ));
  }

  Future<void> disconnect() async {
    changeHistory.attachWebSocket(null);
    audit.attachWebSocket(null);
    voice.attachWebSocket(null);
    screenShare.attachWebSocket(null);
    chat.attachWebSocket(null);
    await _ws?.disconnect();
    _engine.disconnect();
    _enabled = false;
    audit.record(userId: _userId, action: 'leave', detail: '断开协作');
    notifyListeners();
  }

  @override
  void dispose() {
    changeHistory.attachWebSocket(null);
    audit.attachWebSocket(null);
    voice.attachWebSocket(null);
    screenShare.attachWebSocket(null);
    chat.attachWebSocket(null);
    _ws?.dispose();
    _engine.dispose();
    changeHistory.dispose();
    audit.dispose();
    voice.dispose();
    screenShare.dispose();
    chat.dispose();
    comments.dispose();
    cursors.dispose();
    super.dispose();
  }
}
