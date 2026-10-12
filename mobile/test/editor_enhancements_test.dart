// 编辑器增强测试：撤销/重做、多选、对齐、复制粘贴、画布缩放

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:matha_mobile/nodes/editor_enhancements.dart';
import 'package:matha_mobile/nodes/node_types.dart' show Node;

Node _node(String id, double dx, double dy) =>
    Node(id: id, nodeType: 'math_add', position: Offset(dx, dy), ports: const {});

void main() {
  group('EditorSnapshot', () {
    test('take 深拷贝', () {
      final nodes = [_node('a', 0, 0), _node('b', 10, 10)];
      final positions = {'a': const Offset(0, 0), 'b': const Offset(10, 10)};
      final snapshot = EditorSnapshot.take(nodes, positions, []);
      expect(snapshot.nodes.length, 2);

      // 修改原值不影响快照
      positions['a'] = const Offset(99, 99);
      expect(snapshot.positions['a'], const Offset(0, 0));
    });

    test('subset 只保留选中节点与内部连线', () {
      final nodes = [_node('a', 0, 0), _node('b', 10, 10), _node('c', 20, 20)];
      final conns = [
        {'id': '1', 'fromNodeId': 'a', 'fromPortName': 'out', 'toNodeId': 'b', 'toPortName': 'in'},
        {'id': '2', 'fromNodeId': 'a', 'fromPortName': 'out', 'toNodeId': 'c', 'toPortName': 'in'},
      ];
      final snapshot = EditorSnapshot.take(nodes, {}, conns).subset({'a', 'b'});
      expect(snapshot.nodes.length, 2);
      expect(snapshot.connections.length, 1);
      expect(snapshot.connections.single['id'], '1');
    });
  });

  group('EditorHistory', () {
    test('push/undo/redo', () {
      final history = EditorHistory();
      final s1 = EditorSnapshot(nodes: [], positions: {}, connections: []);
      final s2 = EditorSnapshot(nodes: [_node('a', 0, 0)], positions: {'a': const Offset(0, 0)}, connections: []);

      expect(history.canUndo, isFalse);
      history.push(s1);
      history.push(s2);
      expect(history.canUndo, isTrue);
      expect(history.canRedo, isFalse);

      final undo = history.undo();
      expect(undo!.nodes.length, 0);
      expect(history.canRedo, isTrue);
      expect(history.canUndo, isFalse);

      final redo = history.redo();
      expect(redo!.nodes.length, 1);
      expect(history.canRedo, isFalse);
      expect(history.canUndo, isTrue);
    });

    test('新分支截断重做', () {
      final history = EditorHistory();
      final s1 = EditorSnapshot(nodes: [], positions: {}, connections: []);
      final s2 = EditorSnapshot(nodes: [_node('a', 0, 0)], positions: {}, connections: []);
      final s3 = EditorSnapshot(nodes: [_node('b', 0, 0)], positions: {}, connections: []);
      history.push(s1);
      history.push(s2);
      history.undo();
      history.push(s3);
      expect(history.canRedo, isFalse);
      expect(history.length, 2);
    });

    test('超出深度裁剪', () {
      final history = EditorHistory(maxDepth: 3);
      for (var i = 0; i < 8; i++) {
        history.push(EditorSnapshot(nodes: [_node('n$i', 0, 0)], positions: {}, connections: []));
      }
      expect(history.length, 3);
      expect(history.current!.nodes.single.id, 'n7');
    });

    test('空栈撤销返回 null', () {
      final history = EditorHistory();
      expect(history.undo(), isNull);
      expect(history.redo(), isNull);
    });
  });

  group('EditorSelection', () {
    test('切换与单选/加选', () {
      final sel = EditorSelection();
      sel.toggle('a');
      expect(sel.contains('a'), isTrue);

      sel.select('b');
      expect(sel.ids, {'b'});

      sel.select('a', additive: true);
      expect(sel.ids, {'b', 'a'});

      sel.toggle('a');
      expect(sel.contains('a'), isFalse);
    });

    test('全选/保留/清除', () {
      final sel = EditorSelection();
      sel.selectAll(['a', 'b', 'c']);
      expect(sel.count, 3);

      sel.retain(['a', 'c', 'd']);
      expect(sel.ids, {'a', 'c'});

      sel.clear();
      expect(sel.isEmpty, isTrue);
    });
  });

  group('AlignmentUtils', () {
    final positions = {
      'a': const Offset(0, 0),
      'b': const Offset(100, 50),
      'c': const Offset(200, 150),
    };
    final sizes = {
      'a': const Size(60, 30),
      'b': const Size(60, 30),
      'c': const Size(60, 30),
    };

    test('左对齐', () {
      final result = AlignmentUtils.align(positions: positions, sizes: sizes, ids: {'a', 'b', 'c'}, mode: AlignmentMode.left);
      expect(result['a']!.dx, 0);
      expect(result['b']!.dx, 0);
      expect(result['c']!.dx, 0);
    });

    test('右对齐', () {
      final result = AlignmentUtils.align(positions: positions, sizes: sizes, ids: {'a', 'b', 'c'}, mode: AlignmentMode.right);
      final edge = 200 + 60;
      expect(result['a']!.dx, edge - 60);
      expect(result['b']!.dx, edge - 60);
      expect(result['c']!.dx, edge - 60);
    });

    test('水平居中', () {
      final result = AlignmentUtils.align(positions: positions, sizes: sizes, ids: {'a', 'b', 'c'}, mode: AlignmentMode.centerH);
      final mids = [0 + 30, 100 + 30, 200 + 30];
      final avg = mids.reduce((a, b) => a + b) / 3;
      for (final id in ['a', 'b', 'c']) {
        expect((result[id]!.dx + 30) - avg, closeTo(0, 1e-9));
      }
    });

    test('顶部对齐', () {
      final result = AlignmentUtils.align(positions: positions, sizes: sizes, ids: {'a', 'b', 'c'}, mode: AlignmentMode.top);
      expect(result['a']!.dy, 0);
      expect(result['b']!.dy, 0);
      expect(result['c']!.dy, 0);
    });

    test('垂直居中', () {
      final result = AlignmentUtils.align(positions: positions, sizes: sizes, ids: {'a', 'b', 'c'}, mode: AlignmentMode.centerV);
      final mids = [0 + 15, 50 + 15, 150 + 15];
      final avg = mids.reduce((a, b) => a + b) / 3;
      for (final id in ['a', 'b', 'c']) {
        expect((result[id]!.dy + 15) - avg, closeTo(0, 1e-9));
      }
    });

    test('均匀分布', () {
      final result = AlignmentUtils.align(positions: positions, sizes: sizes, ids: {'a', 'b', 'c'}, mode: AlignmentMode.distributeV);
      // 首末保持：a.y=0，c 底边 = 150+30=180；总高 90，间距 45
      expect(result['a']!.dy, 0);
      expect(result['c']!.dy, 150);
      // b 落在 a 与 c 之间等距位置
      expect(result['b']!.dy, closeTo(75, 1e-9));
    });

    test('单个节点对齐无副作用', () {
      final result = AlignmentUtils.align(positions: positions, sizes: sizes, ids: {'b'}, mode: AlignmentMode.left);
      expect(result['b']!.dx, 100);
    });
  });

  group('CopyPasteService', () {
    test('编解码往返', () {
      const json = '''
{
  "nodes": [
    {"id": "a", "nodeType": "math_add", "position": [0, 0], "values": {}, "ports": {}}
  ],
  "positions": {"a": [0, 0]},
  "connections": []
}''';
      final decoded = CopyPasteService.decode(json);
      expect(decoded.nodes.single.id, 'a');
      expect(decoded.positions['a'], const Offset(0, 0));
    });

    test('encode 只序列化选中节点', () {
      final nodes = [_node('a', 0, 0), _node('b', 10, 10)];
      final json = CopyPasteService.encode(
        nodes: nodes,
        positions: {'a': const Offset(0, 0), 'b': const Offset(10, 10)},
        connections: [
          {'id': 'c1', 'fromNodeId': 'a', 'fromPortName': 'out', 'toNodeId': 'b', 'toPortName': 'in'},
        ],
        ids: {'a', 'b'},
      );
      final decoded = CopyPasteService.decode(json);
      expect(decoded.nodes.length, 2);
      expect(decoded.connections.length, 1);
    });

    test('paste 重新生成 id 并偏移', () {
      final nodes = [_node('a', 0, 0), _node('b', 10, 10)];
      final source = EditorSnapshot.take(
        nodes,
        {'a': const Offset(0, 0), 'b': const Offset(10, 10)},
        [
          {'id': 'c1', 'fromNodeId': 'a', 'fromPortName': 'out', 'toNodeId': 'b', 'toPortName': 'in'},
        ],
      );
      final pasted = CopyPasteService.paste(source);

      expect(pasted.nodes.length, 2);
      // id 已重新生成，避免与源冲突
      for (final id in pasted.positions.keys) {
        expect(pasted.nodes.any((n) => n.id == id), isTrue);
        expect(source.positions.containsKey(id), isFalse, reason: '新 id 不得与原图冲突');
      }
      // 位置偏移 24px
      expect(pasted.positions[pasted.nodes.first.id], const Offset(24, 24));
      expect(pasted.positions[pasted.nodes.last.id], const Offset(34, 34));
      // 内部连线保留且指向新 id
      expect(pasted.connections.length, 1);
      final newIds = pasted.positions.keys.toSet();
      expect(newIds.contains(pasted.connections.single['fromNodeId']), isTrue);
      expect(newIds.contains(pasted.connections.single['toNodeId']), isTrue);
    });

    test('paste 忽略跨子集连线', () {
      final source = EditorSnapshot(
        nodes: [_node('a', 0, 0)],
        positions: {'a': const Offset(0, 0)},
        connections: [
          {'id': 'c1', 'fromNodeId': 'a', 'fromPortName': 'out', 'toNodeId': 'missing', 'toPortName': 'in'},
        ],
      );
      final pasted = CopyPasteService.paste(source);
      expect(pasted.connections, isEmpty);
    });

    test('paste 空源返回原样', () {
      final source = EditorSnapshot(nodes: [], positions: {}, connections: []);
      expect(CopyPasteService.paste(source).nodes, isEmpty);
    });
  });

  group('CanvasTransform', () {
    test('缩放钳制', () {
      final t = CanvasTransform();
      for (var i = 0; i < 20; i++) {
        t.zoomIn();
      }
      expect(t.scale, CanvasTransform.maxScale);
      for (var i = 0; i < 40; i++) {
        t.zoomOut();
      }
      expect(t.scale, CanvasTransform.minScale);
    });

    test('重置与平移', () {
      final t = CanvasTransform(scale: 1.4, pan: const Offset(5, 5));
      t.panBy(const Offset(3, -2));
      expect(t.pan, const Offset(8, 3));
      t.reset();
      expect(t.scale, 1.0);
      expect(t.pan, Offset.zero);
    });
  });
}