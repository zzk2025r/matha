// 协作集成测试：多路自定义消息监听（关键修复）/ 协调器 / 协作中心 UI

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:matha_mobile/collab/websocket_manager.dart';
import 'package:matha_mobile/collab/change_history.dart';
import 'package:matha_mobile/collab/audit_log.dart';
import 'package:matha_mobile/collab/voice_call.dart';
import 'package:matha_mobile/collab/session_manager.dart';
import 'package:matha_mobile/providers/collab_provider.dart';
import 'package:matha_mobile/screens/collaboration_screen.dart';

WebSocketManager _ws() => WebSocketManager(const WebSocketConfig(
      serverUrl: 'ws://localhost:1/ws',
      documentId: 'doc1',
      userId: 'me',
      userName: 'Me',
    ));

void main() {
  setUp(() {
    SessionManager.currentUserId = 'me';
    SessionManager.currentUserName = 'Me';
  });

  group('WebSocketManager 多路自定义消息', () {
    test('多个监听器互不覆盖，都能收到消息', () {
      final ws = _ws();
      final receivedA = <String>[];
      final receivedB = <String>[];

      void handlerA(Map<String, dynamic> m) => receivedA.add(m['type'] as String);
      void handlerB(Map<String, dynamic> m) => receivedB.add(m['type'] as String);

      ws.addCustomMessageListener(handlerA);
      ws.addCustomMessageListener(handlerB);

      // 通过旧式单回调 setter 再挂一个（应追加而非覆盖）
      void handlerC(Map<String, dynamic> m) => receivedA.add('C:${m['type']}');
      ws.onCustomMessage = handlerC;

      ws.debugDispatchCustom({'type': 'voice'});
      ws.debugDispatchCustom({'type': 'audit'});

      // 每条消息按注册顺序分派：A 与 C 都写入 receivedA
      expect(receivedA, ['voice', 'C:voice', 'audit', 'C:audit']);
      expect(receivedB, ['voice', 'audit']);

      ws.removeCustomMessageListener(handlerB);
      ws.debugDispatchCustom({'type': 'chat'});
      expect(receivedB, ['voice', 'audit']); // 已注销
      expect(receivedA,
          ['voice', 'C:voice', 'audit', 'C:audit', 'chat', 'C:chat']);
    });

    test('监听器重复注册不产生重复回调', () {
      final ws = _ws();
      var count = 0;
      void handler(Map<String, dynamic> m) => count++;
      ws.addCustomMessageListener(handler);
      ws.addCustomMessageListener(handler);
      ws.debugDispatchCustom({'type': 'x'});
      expect(count, 1);
    });

    test('单个监听器抛异常不影响其他监听器', () {
      final ws = _ws();
      final received = <String>[];
      ws.addCustomMessageListener((m) => throw Exception('boom'));
      ws.addCustomMessageListener((m) => received.add('ok'));
      ws.debugDispatchCustom({'type': 'x'});
      expect(received, ['ok']);
    });
  });

  group('子系统共享同一 WebSocket', () {
    test('四个管理器挂载后仍能各自接收消息', () {
      final ws = _ws();
      final history = ChangeHistoryManager(documentId: 'doc1');
      final audit = AuditManager(documentId: 'doc1');
      final voice = VoiceCallManager(documentId: 'doc1');

      history.attachWebSocket(ws);
      audit.attachWebSocket(ws);
      voice.attachWebSocket(ws);

      // 语音消息
      ws.debugDispatchCustom({
        'type': 'voice',
        'action': 'join',
        'user': {
          'userId': 'remote',
          'userName': 'Remote',
          'joinedAt': DateTime.now().toIso8601String(),
        },
      });
      // 审计消息
      ws.debugDispatchCustom({
        'type': 'audit',
        'entry': {
          'entryId': 'e1',
          'userId': 'remote',
          'action': 'op',
          'timestamp': DateTime.now().toIso8601String(),
        },
      });
      // 变更历史消息
      ws.debugDispatchCustom({
        'type': 'change_history',
        'action': 'change',
        'entry': {
          'version': 0,
          'action': 'update',
          'entityType': 'node',
          'timestamp': DateTime.now().toIso8601String(),
        },
      });

      expect(voice.isMember('remote'), isTrue);
      expect(audit.count, 1);
      expect(history.versionCount, 1);

      // 卸载语音后，其余仍工作
      voice.attachWebSocket(null);
      ws.debugDispatchCustom({
        'type': 'audit',
        'entry': {
          'entryId': 'e2',
          'userId': 'me',
          'action': 'op',
          'timestamp': DateTime.now().toIso8601String(),
        },
      });
      expect(audit.count, 2);
      expect(voice.isMember('remote'), isTrue); // 卸载不清状态
    });
  });

  group('CollabProvider 协调器', () {
    test('本地身份与审计记录', () {
      final p = CollabProvider(documentId: 'doc1');
      p.ensureIdentity(userId: 'u1', userName: 'Alice');
      expect(p.userId, 'u1');
      expect(p.userName, 'Alice');
      expect(p.audit.count, greaterThanOrEqualTo(1));
      p.dispose();
    });

    test('本地模式：变更历史/审计/聊天可用', () async {
      final p = CollabProvider(documentId: 'doc1');
      p.ensureIdentity(userId: 'u1', userName: 'Alice');
      expect(p.isConnected, isFalse);

      p.changeHistory.addChange(action: '编辑', data: {'x': 1});
      expect(p.changeHistory.versionCount, 1);

      p.audit.record(userId: 'u1', action: 'op');
      expect(p.audit.count, greaterThanOrEqualTo(2));

      await p.chat.sendMessage(sessionId: 'doc1', content: '你好');
      expect(p.chat.getMessages('doc1').length, 1);

      p.dispose();
    });

    test('dispose 释放全部子系统', () {
      final p = CollabProvider(documentId: 'doc1');
      expect(() => p.dispose(), returnsNormally);
    });
  });

  group('CollaborationScreen UI', () {
    testWidgets('渲染标签页与连接栏', (tester) async {
      final p = CollabProvider(documentId: 'doc1');
      await tester.pumpWidget(
        ChangeNotifierProvider<CollabProvider>.value(
          value: p,
          child: const MaterialApp(home: CollaborationScreen()),
        ),
      );
      await tester.pump();

      expect(find.text('协作中心'), findsOneWidget);
      expect(find.text('连接'), findsWidgets);
      expect(find.text('审计'), findsWidgets);
      expect(find.text('语音'), findsWidgets);
      // 连接栏显示用户名
      expect(find.text('我'), findsWidgets);

      p.dispose();
    });

    testWidgets('变更历史标签页可记录与撤销', (tester) async {
      final p = CollabProvider(documentId: 'doc1');
      await tester.pumpWidget(
        ChangeNotifierProvider<CollabProvider>.value(
          value: p,
          child: const MaterialApp(home: CollaborationScreen()),
        ),
      );
      await tester.pump();

      // 切到变更标签
      await tester.tap(find.text('变更'));
      await tester.pumpAndSettle();

      // 点 + 记录一次变更
      await tester.tap(find.byIcon(Icons.add));
      await tester.pump();
      expect(p.changeHistory.versionCount, 1);
      expect(find.text('编辑'), findsWidgets);

      p.dispose();
    });
  });
}
