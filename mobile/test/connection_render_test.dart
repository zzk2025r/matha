// 连线渲染测试：确认连接在有端口坐标时真正绘制出路径，
// 以及节点编辑器在挂载后确实上报了端口坐标（此前缺陷：永不绘制）

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:matha_mobile/nodes/connection_system.dart';
import 'package:matha_mobile/nodes/node_types.dart';
import 'package:matha_mobile/nodes/nodes_editor.dart';

/// 记录 drawPath 调用的绘制画布
class _RecordingCanvas implements Canvas {
  final List<Path> paths = [];
  final List<Rect> rects = [];

  @override
  void drawPath(Path path, Paint paint) => paths.add(path);

  @override
  void drawRect(Rect rect, Paint paint) => rects.add(rect);

  @override
  void noSuchMethod(Invocation invocation) {}
}

void main() {
  setUp(() {
    NodeRegistry.clear();
    NodeRegistry.registerDefaults();
  });

  group('ConnectionPainter 绘制', () {
    test('两端端口坐标齐全时绘制出路径', () {
      final c = ConnectionController();
      c.startDrag('A', 'result', startPos: Offset.zero);
      c.endDrag('B', 'a');

      final painter = ConnectionPainter(
        controller: c,
        nodePositions: const {'A': Offset(0, 0), 'B': Offset(200, 0)},
        portPositions: const {
          'A': {'result': Offset(170, 60)},
          'B': {'a': Offset(200, 60)},
        },
      );

      final canvas = _RecordingCanvas();
      painter.paint(canvas, const Size(800, 600));
      expect(canvas.paths.length, 1, reason: '应绘制 1 条连线路径');
      final metrics = canvas.paths.first.computeMetrics().toList();
      expect(metrics, isNotEmpty, reason: '路径应有可测量的段');
      expect(metrics.first.length, greaterThan(0));
    });

    test('端口坐标缺失时不绘制（也不崩溃）', () {
      final c = ConnectionController();
      c.startDrag('A', 'result', startPos: Offset.zero);
      c.endDrag('B', 'a');

      final painter = ConnectionPainter(
        controller: c,
        nodePositions: const {},
        portPositions: const {}, // 缺失
      );

      final canvas = _RecordingCanvas();
      painter.paint(canvas, const Size(800, 600));
      expect(canvas.paths, isEmpty);
    });

    test('多连线时逐条绘制', () {
      final c = ConnectionController();
      c.startDrag('A', 'result', startPos: Offset.zero);
      c.endDrag('B', 'a');
      c.startDrag('A', 'result', startPos: Offset.zero);
      c.endDrag('C', 'a');

      final painter = ConnectionPainter(
        controller: c,
        nodePositions: const {},
        portPositions: const {
          'A': {'result': Offset(170, 60)},
          'B': {'a': Offset(200, 60)},
          'C': {'a': Offset(200, 160)},
        },
      );

      final canvas = _RecordingCanvas();
      painter.paint(canvas, const Size(800, 600));
      expect(canvas.paths.length, 2);
    });

    test('shouldRepaint 在数据变化时返回 true', () {
      final c = ConnectionController();
      final p1 = ConnectionPainter(
        controller: c,
        nodePositions: const {},
        portPositions: const {},
      );
      final p2 = ConnectionPainter(
        controller: c,
        nodePositions: const {},
        portPositions: const {},
      );
      expect(p2.shouldRepaint(p1), isTrue);
    });
  });

  group('节点编辑器挂载与端口坐标上报', () {
    testWidgets('挂载后端口坐标被上报（连接线才能绘制）', (tester) async {
      final key = GlobalKey();
      await tester.pumpWidget(MaterialApp(
        home: NodesEditor(
          key: key,
          initialNodes: [
            Node(id: 'a', nodeType: 'math_add', position: const Offset(80, 80)),
          ],
        ),
      ));
      await tester.pumpAndSettle();

      // 编辑器渲染出节点
      expect(find.text('加法'), findsOneWidget);

      // 通过公开的 painter 验证：存在一个带端口坐标的 ConnectionPainter 实例
      final painters = tester
          .widgetList<CustomPaint>(find.byType(CustomPaint))
          .where((w) => w.painter is ConnectionPainter)
          .map((w) => w.painter as ConnectionPainter)
          .toList();
      expect(painters, isNotEmpty, reason: '应存在连线绘制器');

      // 数学加法节点有 a/b/result 端口，其坐标应在挂载后被上报
      final painter = painters.first;
      final ports = painter.portPositions['a'];
      expect(ports, isNotNull, reason: '节点 a 端口坐标未上报');
      expect(ports!.containsKey('result'), isTrue);
      expect(ports.containsKey('a'), isTrue);
      expect(ports.containsKey('b'), isTrue);
    });

    testWidgets('两个节点挂载后端口坐标均齐全', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: NodesEditor(
          initialNodes: [
            Node(id: 'a', nodeType: 'math_add', position: const Offset(60, 60)),
            Node(id: 'b', nodeType: 'math_add', position: const Offset(360, 60)),
          ],
        ),
      ));
      await tester.pumpAndSettle();

      final painter = tester
          .widgetList<CustomPaint>(find.byType(CustomPaint))
          .map((w) => w.painter)
          .whereType<ConnectionPainter>()
          .first;

      expect(painter.portPositions['a'], isNotNull);
      expect(painter.portPositions['b'], isNotNull);
      // 两个节点的端口坐标应不同（分处两地）
      expect(painter.portPositions['a']!['result'],
          isNot(painter.portPositions['b']!['result']));
    });
  });
}
