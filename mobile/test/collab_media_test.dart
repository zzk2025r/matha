// 协作用媒体功能测试：语音通话 / 屏幕共享 / 审计日志 / 变更历史

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:matha_mobile/collab/audit_log.dart';
import 'package:matha_mobile/collab/change_history.dart';
import 'package:matha_mobile/collab/screen_share.dart';
import 'package:matha_mobile/collab/session_manager.dart';
import 'package:matha_mobile/collab/voice_call.dart';

void main() {
  setUp(() {
    SessionManager.currentUserId = 'me';
    SessionManager.currentUserName = 'Me';
  });

  group('VoiceCallManager', () {
    test('加入/离开语音', () {
      final vm = VoiceCallManager(documentId: 'doc1');
      vm.join();
      expect(vm.isActive, isTrue);
      expect(vm.memberCount, 1);
      expect(vm.isMember('me'), isTrue);

      vm.join(); // 重复加入
      expect(vm.memberCount, 1);

      vm.leave();
      expect(vm.isActive, isFalse);
      expect(vm.memberCount, 0);
    });

    test('静音与发言状态', () async {
      final vm = VoiceCallManager(documentId: 'doc1');
      await vm.join();
      expect(vm.mutedCount, 0);

      await vm.toggleMute();
      expect(vm.members['me']!.muted, isTrue);
      expect(vm.mutedCount, 1);

      await vm.setSpeaking('me', true);
      expect(vm.speakingCount, 1);
      expect(vm.members['me']!.speaking, isTrue);
    });

    test('远程加入/离开', () {
      final vm = VoiceCallManager(documentId: 'doc1');
      vm.joinLocal({
        'userId': 'remote',
        'userName': 'Remote',
        'joinedAt': DateTime.now().toIso8601String(),
      });
      expect(vm.isActive, isTrue);
      expect(vm.memberCount, 1);
      expect(vm.isMember('remote'), isTrue);

      vm.leaveLocal('remote');
      expect(vm.memberCount, 0);
      expect(vm.isActive, isFalse);
    });

    test('成员流事件', () async {
      final vm = VoiceCallManager(documentId: 'doc1');
      final joins = <VoiceMember>[];
      final leaves = <String>[];
      vm.onMemberJoin.listen(joins.add);
      vm.onMemberLeave.listen(leaves.add);

      vm.joinLocal({
        'userId': 'a',
        'userName': 'A',
        'joinedAt': DateTime.now().toIso8601String(),
      });
      vm.leaveLocal('a');
      await Future<void>.delayed(Duration.zero);

      expect(joins.length, 1);
      expect(leaves, ['a']);
    });

    testWidgets('语音面板渲染并显示成员', (tester) async {
      final vm = VoiceCallManager(documentId: 'doc1');
      await tester.pumpWidget(MaterialApp(home: Scaffold(body: VoiceCallPanel(manager: vm))));
      await tester.pump();

      expect(find.text('语音通话'), findsOneWidget);

      await vm.join();
      await tester.pump();
      expect(find.textContaining('语音通话中'), findsOneWidget);
      expect(find.text('Me'), findsOneWidget);
    });
  });

  group('ScreenShareManager', () {
    test('开始/推送/观看/停止', () async {
      final sm = ScreenShareManager(documentId: 'doc1');
      await sm.start();
      expect(sm.isActive, isTrue);
      expect(sm.amPresenter, isTrue);

      final no = await sm.publishFrame({'bytes': [1, 2, 3]});
      expect(no, 1);
      expect(sm.frameCount, 1);
      expect(sm.latestFrame!.data['bytes'], [1, 2, 3]);

      await sm.watch();
      expect(sm.viewerCount, 1);
      expect(sm.amViewer, isTrue);

      final recent = sm.recentFrames(1);
      expect(recent.length, 1);
      expect(recent.first.frameNo, 1);

      await sm.stop();
      expect(sm.isActive, isFalse);
      expect(sm.frameCount, 0);
    });

    test('非演示者无法停止/推流', () async {
      final sm = ScreenShareManager(documentId: 'doc1');
      SessionManager.currentUserId = 'other';
      await sm.start();
      // 换成非演示者身份
      SessionManager.currentUserId = 'me';
      final no = await sm.publishFrame({'bytes': [1]});
      expect(no, isNull);
      await sm.stop();
      expect(sm.isActive, isTrue);

      SessionManager.currentUserId = 'other';
      await sm.stop();
      expect(sm.isActive, isFalse);
    });

    test('帧缓冲上限', () async {
      final sm = ScreenShareManager(documentId: 'doc1');
      await sm.start();
      for (var i = 0; i < 40; i++) {
        await sm.publishFrame({'n': i});
      }
      expect(sm.frameCount, 30);
      expect(sm.latestFrame!.data['n'], 39);
    });

    test('远程开始/停止/帧监听', () async {
      final sm = ScreenShareManager(documentId: 'doc1');
      final frames = <ScreenShareFrame>[];
      sm.onFrame.listen(frames.add);

      sm.startLocal({
        'sessionId': 's1',
        'presenterId': 'remote',
        'presenterName': 'Remote',
        'startedAt': DateTime.now().toIso8601String(),
      });
      expect(sm.isActive, isTrue);
      expect(sm.presenterId, 'remote');

      sm.publishFrameLocal(ScreenShareFrame(
        frameNo: 1,
        data: {'bytes': [9]},
        timestamp: DateTime.now(),
      ));
      await Future<void>.delayed(Duration.zero);
      expect(frames.length, 1);
      expect(sm.latestFrame!.data['bytes'], [9]);

      sm.stopLocal('remote');
      expect(sm.isActive, isFalse);
    });

    testWidgets('共享画布组件', (tester) async {
      final sm = ScreenShareManager(documentId: 'doc1');
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(body: ScreenShareWidget(manager: sm)),
      ));
      await tester.pump();
      expect(find.text('正在共享'), findsNothing);

      await sm.start();
      await tester.pump();
      expect(find.text('正在共享'), findsOneWidget);
    });
  });

  group('AuditManager', () {
    test('记录/统计/筛选/清除', () {
      final am = AuditManager(documentId: 'doc1');
      am.record(userId: 'me', action: 'join', detail: '加入会话');
      am.record(userId: 'me', action: 'op', detail: '创建节点');
      am.record(userId: 'remote', action: 'op');
      am.record(userId: 'me', action: 'join', detail: '重新加入');

      expect(am.count, 4);
      expect(am.summary['join'], 2);
      expect(am.summary['op'], 2);
      expect(am.filterByAction('op').length, 2);

      final recent = am.recent(2);
      expect(recent.length, 2);
      expect(recent.first.action, 'join'); // 最新的在前

      am.clear();
      expect(am.count, 0);
    });

    test('条目上限', () {
      final am = AuditManager(documentId: 'doc1', maxEntries: 3);
      for (var i = 0; i < 10; i++) {
        am.record(userId: 'me', action: 'op');
      }
      expect(am.count, 3);
    });

    testWidgets('审计列表渲染', (tester) async {
      final am = AuditManager(documentId: 'doc1');
      am.record(userId: 'me', action: 'join', detail: '加入会话');
      am.record(userId: 'me', action: 'op', detail: '创建节点');

      await tester.pumpWidget(MaterialApp(
        home: Scaffold(body: AuditLogSheet(manager: am)),
      ));
      await tester.pump();

      expect(find.textContaining('join'), findsWidgets);
      expect(find.textContaining('op'), findsWidgets);
      expect(find.text('创建节点'), findsOneWidget);
    });
  });

  group('ChangeHistoryManager', () {
    test('记录与版本计数', () {
      final hm = ChangeHistoryManager(documentId: 'doc1');
      expect(hm.versionCount, 0);
      expect(hm.canUndo, isFalse);

      hm.addChange(action: 'create', entityId: 'n1', data: {'x': 1});
      hm.addChange(action: 'update', entityId: 'n1', data: {'x': 2});

      expect(hm.versionCount, 2);
      expect(hm.currentVersion, 1);
      expect(hm.currentEntry!.action, 'update');
      expect(hm.canUndo, isTrue);
    });

    test('撤销/重做返回快照', () {
      final hm = ChangeHistoryManager(documentId: 'doc1');
      hm.addChange(action: 'create', entityId: 'n1', data: {'x': 1});
      hm.addChange(action: 'create', entityId: 'n2', data: {'x': 2});

      final undoSnapshot = hm.undo();
      expect(undoSnapshot, {'x': 1});
      expect(hm.currentVersion, 0);
      expect(hm.canRedo, isTrue);

      final redoSnapshot = hm.redo();
      expect(redoSnapshot, {'x': 2});
      expect(hm.currentVersion, 1);
    });

    test('新变更清空重做栈', () {
      final hm = ChangeHistoryManager(documentId: 'doc1');
      hm.addChange(action: 'create', entityId: 'n1', data: {});
      hm.addChange(action: 'create', entityId: 'n2', data: {});
      hm.undo();
      hm.addChange(action: 'update', entityId: 'n1', data: {'z': 9});

      expect(hm.canRedo, isFalse);
      expect(hm.versionCount, 2);
      expect(hm.latestAction, 'update');
    });

    test('直接回退版本', () {
      final hm = ChangeHistoryManager(documentId: 'doc1');
      hm.addChange(action: 'create', entityId: 'n1', data: {'a': 1});
      hm.addChange(action: 'create', entityId: 'n2', data: {'a': 2});
      hm.addChange(action: 'create', entityId: 'n3', data: {'a': 3});

      final snap = hm.revertTo(1);
      expect(snap, {'a': 2});
      expect(hm.currentVersion, 1);
      expect(hm.revertTo(99), isNull);
      expect(hm.revertTo(-1), isNull);
    });

    test('深度上限裁剪', () {
      final hm = ChangeHistoryManager(documentId: 'doc1', maxDepth: 3);
      for (var i = 0; i < 10; i++) {
        hm.addChange(action: 'create', entityId: 'n$i', data: {'i': i});
      }
      expect(hm.versionCount, 3);
      expect(hm.latestAction, 'create');
    });

    test('change 条目序列化', () {
      final e = ChangeEntry(
        version: 2,
        action: 'update',
        entityType: 'node',
        entityId: 'n9',
        data: {'k': 'v'},
        timestamp: DateTime(2026, 1, 1),
      );
      final restored = ChangeEntry.fromMap(e.toMap());
      expect(restored.version, 2);
      expect(restored.action, 'update');
      expect(restored.data, {'k': 'v'});
    });
  });
}