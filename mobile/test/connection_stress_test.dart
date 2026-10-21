// 连线系统极限/模糊测试：10 个节点互相胡乱连线，验证不变量与漏洞

import 'dart:math';
import 'package:flutter_test/flutter_test.dart';
import 'package:matha_mobile/nodes/connection_system.dart';

/// 校验控制器内部索引与主列表始终保持一致（核心不变量）
void expectConsistent(ConnectionController c, {String? context}) {
  final all = c.connections;
  final allIds = all.map((e) => e.id).toSet();

  // 1. 主列表无重复 id
  expect(allIds.length, all.length,
      reason: '${context ?? ''} 主列表存在重复 id');

  // 2. 每条连线都注册在其两端节点的索引下
  for (final conn in all) {
    final fromList = c.getNodeConnections(conn.fromNodeId);
    final toList = c.getNodeConnections(conn.toNodeId);
    expect(fromList.any((e) => e.id == conn.id), isTrue,
        reason: '${context ?? ''} 源节点 ${conn.fromNodeId} 未登记连线 ${conn.id}');
    expect(toList.any((e) => e.id == conn.id), isTrue,
        reason: '${context ?? ''} 目标节点 ${conn.toNodeId} 未登记连线 ${conn.id}');
  }

  // 3. 索引中不存在主列表没有的连线（无幽灵引用）
  for (final entry in _allIndexed(c)) {
    for (final conn in entry.value) {
      expect(allIds.contains(conn.id), isTrue,
          reason: '${context ?? ''} 节点 ${entry.key} 索引中存在幽灵连线 ${conn.id}');
    }
  }

  // 4. 同一目标「输入端口」至多一条入线
  final incoming = <String, int>{};
  for (final conn in all) {
    final key = '${conn.toNodeId}#${conn.toPortName}';
    incoming[key] = (incoming[key] ?? 0) + 1;
  }
  for (final e in incoming.entries) {
    expect(e.value, 1, reason: '${context ?? ''} 输入端口 $e 存在多条入线');
  }

  // 5. 无自环、无空端口、无端口对端口同名的无意义连线
  for (final conn in all) {
    expect(conn.fromNodeId == conn.toNodeId, isFalse,
        reason: '${context ?? ''} 存在自环 ${conn.id}');
    expect(conn.fromNodeId.isNotEmpty && conn.toNodeId.isNotEmpty, isTrue,
        reason: '${context ?? ''} 存在空节点连线 ${conn.id}');
    expect(conn.fromPortName.isNotEmpty && conn.toPortName.isNotEmpty, isTrue,
        reason: '${context ?? ''} 存在空端口连线 ${conn.id}');
    expect(conn.fromPortName == conn.toPortName, isFalse,
        reason: '${context ?? ''} 存在同名端口连线 ${conn.id}');
  }
}

// 通过反射不可用，改为遍历已知节点名以获取索引
Iterable<MapEntry<String, List<Connection>>> _allIndexed(
    ConnectionController c) sync* {
  for (final id in _knownNodes) {
    yield MapEntry(id, c.getNodeConnections(id));
  }
}

const _knownNodes = ['N0', 'N1', 'N2', 'N3', 'N4', 'N5', 'N6', 'N7', 'N8', 'N9'];

void main() {
  group('10 节点胡乱连线模糊测试', () {
    test('随机大量拖拽后不变量始终成立', () {
      final c = ConnectionController();
      final rnd = Random(12345);
      final outPorts = ['o0', 'o1'];
      final inPorts = ['i0', 'i1', 'i2'];
      var successes = 0;
      var rejections = 0;

      for (var i = 0; i < 3000; i++) {
        final from = _knownNodes[rnd.nextInt(_knownNodes.length)];
        final to = _knownNodes[rnd.nextInt(_knownNodes.length)];
        final fromPort = outPorts[rnd.nextInt(outPorts.length)];
        final toPort = inPorts[rnd.nextInt(inPorts.length)];

        c.startDrag(from, fromPort, startPos: Offset(rnd.nextDouble() * 500, rnd.nextDouble() * 500));
        // 偶发更新拖拽终点
        if (rnd.nextBool()) {
          c.updateDrag(Offset(rnd.nextDouble() * 500, rnd.nextDouble() * 500));
        }
        // 偶发落空取消
        final dropBlank = rnd.nextInt(10) == 0;
        final ok = dropBlank ? c.endDrag(null, null) : c.endDrag(to, toPort);
        if (ok) {
          successes++;
        } else {
          rejections++;
        }

        // 每次操作后都必须保持一致
        expectConsistent(c, context: '第 $i 次操作后');
        // 拖拽状态必须已清空（成功与取消都清）
        expect(c.draggingFromNodeId, isNull, reason: '第 $i 次操作后拖拽态未清空');
        expect(c.dragStartPos, isNull);
        expect(c.dragEndPos, isNull);
      }

      expect(successes, greaterThan(0));
      expect(rejections, greaterThan(0));
      // 收尾再校验一次
      expectConsistent(c, context: '收尾');
    });

    test('随机断开连线的模糊测试', () {
      final c = ConnectionController();
      final rnd = Random(999);

      // 先建立一批连线
      for (final from in _knownNodes) {
        for (final to in _knownNodes) {
          c.startDrag(from, 'o0', startPos: Offset.zero);
          c.endDrag(to, 'i0');
        }
      }
      expectConsistent(c, context: '预建连线后');
      expect(c.connections, isNotEmpty);

      // 随机删除既有连线
      for (var i = 0; i < 2000 && c.connections.isNotEmpty; i++) {
        final all = c.connections;
        final victim = all[rnd.nextInt(all.length)];
        c.removeConnection(victim.id);
        expectConsistent(c, context: '删除第 $i 条后');
      }
    });

    test('先混乱构建再逐个删除，最终必须清空且索引无残留', () {
      final c = ConnectionController();
      final rnd = Random(2024);

      for (var i = 0; i < 1000; i++) {
        final from = _knownNodes[rnd.nextInt(_knownNodes.length)];
        final to = _knownNodes[rnd.nextInt(_knownNodes.length)];
        c.startDrag(from, 'o${rnd.nextInt(2)}', startPos: Offset.zero);
        c.endDrag(to, 'i${rnd.nextInt(3)}');
      }

      // 删除所有连线
      for (final conn in c.connections.toList()) {
        c.removeConnection(conn.id);
      }
      expect(c.connections, isEmpty);

      // 所有索引必须为空
      for (final id in _knownNodes) {
        expect(c.getNodeConnections(id), isEmpty,
            reason: '节点 $id 仍残留索引项');
      }
      expectConsistent(c, context: '全部删除后');
    });

    test('clearAll 后索引彻底清空', () {
      final c = ConnectionController();
      for (final from in _knownNodes) {
        c.startDrag(from, 'o0', startPos: Offset.zero);
        c.endDrag('N9', 'i0');
      }
      c.clearAll();
      expect(c.connections, isEmpty);
      for (final id in _knownNodes) {
        expect(c.getNodeConnections(id), isEmpty);
      }
    });

    test('序列化往返在混乱状态下仍保持一致', () {
      final c = ConnectionController();
      final rnd = Random(7);
      for (var i = 0; i < 500; i++) {
        final from = _knownNodes[rnd.nextInt(_knownNodes.length)];
        final to = _knownNodes[rnd.nextInt(_knownNodes.length)];
        c.startDrag(from, 'o${rnd.nextInt(2)}', startPos: Offset.zero);
        c.endDrag(to, 'i${rnd.nextInt(3)}');
      }
      final data = c.serialize();
      final c2 = ConnectionController();
      c2.deserialize(data);
      expect(c2.connections.length, c.connections.length);
      expectConsistent(c2, context: '反序列化后');
    });

    test('大量 fan-out：单输出连向不同节点不同输入应全部保留', () {
      final c = ConnectionController();
      // N0.o0 -> N1.i0, N2.i0, N3.i0 ... 不同目标节点
      var created = 0;
      for (var i = 1; i < _knownNodes.length; i++) {
        c.startDrag('N0', 'o0', startPos: Offset.zero);
        if (c.endDrag(_knownNodes[i], 'i0')) created++;
      }
      // 每个目标节点各自 i0 独立，应全部成功
      expect(created, _knownNodes.length - 1);
      expect(c.connections.length, _knownNodes.length - 1);
      expect(c.getNodeConnections('N0').length, _knownNodes.length - 1);
      expectConsistent(c, context: 'fan-out 后');
    });

    test('单输入多源：同一目标输入端口反复被不同源覆盖，只留一条', () {
      final c = ConnectionController();
      for (var i = 0; i < _knownNodes.length - 1; i++) {
        c.startDrag(_knownNodes[i], 'o0', startPos: Offset.zero);
        c.endDrag('N9', 'sink');
      }
      expect(c.connections.length, 1);
      expect(c.connections.first.fromNodeId, _knownNodes[_knownNodes.length - 2]);
      expectConsistent(c, context: '单输入多源后');
    });

    test('极端：连续 5000 次拖拽-取消不产生任何连线', () {
      final c = ConnectionController();
      for (var i = 0; i < 5000; i++) {
        c.startDrag(_knownNodes[i % 10], 'o0', startPos: Offset.zero);
        c.cancelDrag();
      }
      expect(c.connections, isEmpty);
      expectConsistent(c, context: '纯取消后');
    });
  });
}
