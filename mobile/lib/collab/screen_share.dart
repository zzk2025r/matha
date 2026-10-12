// Matha 协作功能 - 实时屏幕共享
// 实现在协作会话内的屏幕共享（推流 / 观看 / 帧缓冲）

import 'dart:async';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'session_manager.dart';
import 'websocket_manager.dart';

const int _maxFrames = 30;

/// 屏幕共享帧
class ScreenShareFrame {
  final int frameNo;
  final Map<String, dynamic> data;
  final DateTime timestamp;

  const ScreenShareFrame({
    required this.frameNo,
    required this.data,
    required this.timestamp,
  });

  Map<String, dynamic> toMap() => {
    'frameNo': frameNo,
    'data': data,
    'timestamp': timestamp.toIso8601String(),
  };

  factory ScreenShareFrame.fromMap(Map<String, dynamic> map) => ScreenShareFrame(
    frameNo: map['frameNo'] as int,
    data: (map['data'] as Map<String, dynamic>?) ?? {},
    timestamp: DateTime.parse(map['timestamp'] as String? ?? DateTime.now().toIso8601String()),
  );
}

/// 屏幕共享会话
class ScreenShareSession {
  final String sessionId;
  final String presenterId;
  final String presenterName;
  final DateTime startedAt;
  final List<String> viewers;
  final List<ScreenShareFrame> frames;

  const ScreenShareSession({
    required this.sessionId,
    required this.presenterId,
    required this.presenterName,
    required this.startedAt,
    this.viewers = const [],
    this.frames = const [],
  });

  ScreenShareSession copyWith({
    List<String>? viewers,
    List<ScreenShareFrame>? frames,
  }) {
    return ScreenShareSession(
      sessionId: sessionId,
      presenterId: presenterId,
      presenterName: presenterName,
      startedAt: startedAt,
      viewers: viewers ?? this.viewers,
      frames: frames ?? this.frames,
    );
  }

  int get frameCount => frames.length;

  ScreenShareFrame? get latestFrame => frames.isEmpty ? null : frames.last;

  Map<String, dynamic> toMap() => {
    'sessionId': sessionId,
    'presenterId': presenterId,
    'presenterName': presenterName,
    'startedAt': startedAt.toIso8601String(),
    'viewers': viewers,
    'frameCount': frameCount,
  };
}

/// 屏幕共享管理器
class ScreenShareManager extends ChangeNotifier {
  final String documentId;

  final StreamController<ScreenShareFrame> _frameController = StreamController.broadcast();
  final StreamController<ScreenShareSession> _startController = StreamController.broadcast();
  final StreamController<String> _stopController = StreamController.broadcast();

  WebSocketManager? _wsManager;
  ScreenShareSession? _session;

  ScreenShareManager({required this.documentId});

  /// 连接实时通信通道
  void attachWebSocket(WebSocketManager? manager) {
    _wsManager = manager;
    if (manager != null) {
      manager.onCustomMessage = _handleServerMessage;
      debugPrint('[ScreenShare] WebSocket 通道已挂载');
    }
    notifyListeners();
  }

  void _handleServerMessage(Map<String, dynamic> message) {
    if (message['type'] != 'screen_share') return;
    final action = message['action'] as String?;
    switch (action) {
      case 'start':
        startLocal(message['session'] as Map<String, dynamic>? ?? {});
      case 'stop':
        stopLocal(message['presenterId'] as String? ?? '');
      case 'frame':
        if (message['frame'] is Map<String, dynamic>) {
          publishFrameLocal(ScreenShareFrame.fromMap(message['frame'] as Map<String, dynamic>));
        }
      case 'watch':
      case 'unwatch':
        final uid = message['userId'] as String? ?? '';
        final session = _session;
        if (session == null || uid.isEmpty) return;
        final viewers = List<String>.from(session.viewers);
        if (action == 'watch' && !viewers.contains(uid)) {
          viewers.add(uid);
        } else if (action == 'unwatch') {
          viewers.remove(uid);
        }
        _session = session.copyWith(viewers: viewers);
        notifyListeners();
    }
  }

  // ========== 推流 / 观看 ==========

  /// 开始共享
  Future<void> start() async {
    final presenterId = SessionManager.currentUserId ?? 'unknown';
    final session = ScreenShareSession(
      sessionId: 'share_${DateTime.now().millisecondsSinceEpoch}',
      presenterId: presenterId,
      presenterName: SessionManager.currentUserName ?? 'User',
      startedAt: DateTime.now(),
    );
    _session = session;
    _startController.add(session);
    _send('start', {'session': session.toMap()});
    notifyListeners();
    debugPrint('[ScreenShare] 开始共享: ${session.sessionId}');
  }

  /// 停止共享
  Future<void> stop({String? presenterId}) async {
    final uid = presenterId ?? SessionManager.currentUserId ?? 'unknown';
    final session = _session;
    if (session == null || session.presenterId != uid) return;
    stopLocal(uid);
    _send('stop', {'presenterId': uid});
  }

  /// 进入观看
  Future<void> watch() async {
    final session = _session;
    final uid = SessionManager.currentUserId ?? 'unknown';
    if (session == null) return;
    final viewers = List<String>.from(session.viewers);
    if (!viewers.contains(uid)) {
      viewers.add(uid);
      _session = session.copyWith(viewers: viewers);
      notifyListeners();
    }
    _send('watch', {'userId': uid});
  }

  /// 退出观看
  Future<void> unwatch() async {
    final session = _session;
    final uid = SessionManager.currentUserId ?? 'unknown';
    if (session == null) return;
    final viewers = List<String>.from(session.viewers)..remove(uid);
    _session = session.copyWith(viewers: viewers);
    notifyListeners();
    _send('unwatch', {'userId': uid});
  }

  /// 推送一帧（仅演示者）
  Future<int?> publishFrame(Map<String, dynamic> data) async {
    final session = _session;
    final uid = SessionManager.currentUserId ?? 'unknown';
    if (session == null || session.presenterId != uid) return null;
    final frame = ScreenShareFrame(
      frameNo: session.frames.length + 1,
      data: data,
      timestamp: DateTime.now(),
    );
    publishFrameLocal(frame);
    _send('frame', {'frame': frame.toMap()});
    return frame.frameNo;
  }

  // ========== 本地状态更新 ==========

  void startLocal(Map<String, dynamic> data) {
    final startedAt = data['startedAt'] as String?;
    final session = ScreenShareSession(
      sessionId: data['sessionId'] as String? ?? 'share_unknown',
      presenterId: data['presenterId'] as String? ?? 'unknown',
      presenterName: data['presenterName'] as String? ?? 'User',
      startedAt: startedAt != null ? DateTime.tryParse(startedAt) ?? DateTime.now() : DateTime.now(),
      viewers: List<String>.from(data['viewers'] ?? []),
    );
    final existed = _session != null;
    _session = session;
    if (!existed) {
      _startController.add(session);
    }
    notifyListeners();
  }

  void stopLocal(String presenterId) {
    final session = _session;
    if (session == null || session.presenterId != presenterId) return;
    _session = null;
    _stopController.add(presenterId);
    notifyListeners();
  }

  void publishFrameLocal(ScreenShareFrame frame) {
    final session = _session;
    if (session == null) return;
    final frames = [
      ...session.frames,
      frame,
    ];
    if (frames.length > _maxFrames) {
      frames.removeRange(0, frames.length - _maxFrames);
    }
    _session = session.copyWith(frames: frames);
    _frameController.add(frame);
    notifyListeners();
  }

  // ========== 查询 ==========

  bool get isActive => _session != null;

  String? get presenterId => _session?.presenterId;

  bool get amPresenter =>
      _session != null && _session!.presenterId == (SessionManager.currentUserId ?? 'unknown');

  int get viewerCount => _session?.viewers.length ?? 0;

  bool get amViewer =>
      _session != null && _session!.viewers.contains(SessionManager.currentUserId ?? 'unknown');

  int get frameCount => _session?.frameCount ?? 0;

  ScreenShareFrame? get latestFrame => _session?.latestFrame;

  /// 最近的若干帧（新→旧）
  List<ScreenShareFrame> recentFrames(int count) {
    final session = _session;
    if (session == null) return const [];
    final frames = session.frames;
    final start = frames.length - count < 0 ? 0 : frames.length - count;
    return frames.sublist(start).reversed.toList();
  }

  ScreenShareSession? get session => _session;

  Stream<ScreenShareFrame> get onFrame => _frameController.stream;

  Stream<ScreenShareSession> get onStart => _startController.stream;

  Stream<String> get onStop => _stopController.stream;

  // ========== 发送 ==========

  void _send(String action, Map<String, dynamic> payload) {
    final ws = _wsManager;
    if (ws == null) {
      debugPrint('[ScreenShare] 未连接 WebSocket，状态仅本地更新: $action');
      return;
    }
    ws.sendRawMessage({
      'type': 'screen_share',
      'action': action,
      'documentId': documentId,
      'timestamp': DateTime.now().toIso8601String(),
      ...payload,
    });
  }

  // ========== 生命周期 ==========

  @override
  void dispose() {
    _frameController.close();
    _startController.close();
    _stopController.close();
    super.dispose();
  }
}

/// 屏幕共享画布组件
class ScreenShareWidget extends StatelessWidget {
  final ScreenShareManager manager;

  const ScreenShareWidget({super.key, required this.manager});

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: manager,
      builder: (context, _) {
        if (!manager.isActive) {
          return const SizedBox.shrink();
        }
        final frame = manager.latestFrame;
        final bytes = frame?.data['bytes'];
        final hasFrame = bytes is List && bytes.isNotEmpty && bytes.every((b) => b is int);
        return Container(
          decoration: BoxDecoration(
            color: Colors.black,
            borderRadius: BorderRadius.circular(12),
          ),
          clipBehavior: Clip.antiAlias,
          child: AspectRatio(
            aspectRatio: 16 / 9,
            child: hasFrame
                ? Image.memory(
                    Uint8List.fromList(bytes.cast<int>()),
                    fit: BoxFit.contain,
                    gaplessPlayback: true,
                  )
                : Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.monitor, color: Colors.white70, size: 48),
                        const SizedBox(height: 8),
                        Text(
                          manager.amPresenter ? '正在共享' : '共享中 · ${manager.viewerCount} 人观看',
                          style: const TextStyle(color: Colors.white70, fontSize: 12),
                        ),
                      ],
                    ),
                  ),
          ),
        );
      },
    );
  }
}