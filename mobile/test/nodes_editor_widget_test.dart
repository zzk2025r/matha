// 节点编辑器组件测试：多选 / 复制粘贴 / 缩放 / 对齐 / 快捷键

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:matha_mobile/nodes/node_types.dart';
import 'package:matha_mobile/nodes/nodes_editor.dart';

Node _node(String id, double dx, double dy) =>
    Node(id: id, nodeType: 'math_add', position: Offset(dx, dy), ports: const {});

Future<void> _pumpEditor(WidgetTester tester) async {
  await tester.pumpWidget(
    MaterialApp(
      home: NodesEditor(
        initialNodes: [_node('a', 100, 100), _node('b', 200, 100)],
      ),
    ),
  );
  await tester.pumpAndSettle();
}

Future<void> _tapNode(WidgetTester tester, int index) async {
  await tester.tap(find.text('加法').at(index));
  await tester.pump();
}

void main() {
  setUp(() {
    NodeRegistry.registerDefaults();
  });

  testWidgets('点击切换选中并显示删除按钮', (tester) async {
    await _pumpEditor(tester);
    expect(find.text('加法'), findsNWidgets(2));

    // 点选第一个节点
    await _tapNode(tester, 0);
    expect(find.byTooltip('删除选中 (Del) — 1 个'), findsOneWidget);

    // 点空白区域清除选中
    await tester.tapAt(const Offset(600, 400));
    await tester.pump();
    expect(find.byTooltip('删除选中 (Del) — 1 个'), findsNothing);
  });

  testWidgets('复制并粘贴', (tester) async {
    await _pumpEditor(tester);
    await _tapNode(tester, 0);

    await tester.tap(find.byTooltip('复制 (Ctrl+C)'));
    await tester.pump();
    expect(find.text('已复制 1 个节点'), findsOneWidget);

    await tester.tap(find.byTooltip('粘贴 (Ctrl+V)'));
    await tester.pump();
    expect(find.text('已粘贴 1 个节点'), findsOneWidget);
    expect(find.text('加法'), findsNWidgets(3));
  });

  testWidgets('全选与删除选中', (tester) async {
    await _pumpEditor(tester);
    await tester.tap(find.byTooltip('全选 (Ctrl+A)'));
    await tester.pump();
    expect(find.text('已选中 2 个节点'), findsOneWidget);
    expect(find.byTooltip('删除选中 (Del) — 2 个'), findsOneWidget);

    await tester.tap(find.byTooltip('删除选中 (Del) — 2 个'));
    await tester.pump();
    expect(find.text('已删除 2 个节点'), findsOneWidget);
    expect(find.text('加法'), findsNothing);
  });

  testWidgets('缩放加减与重置', (tester) async {
    await _pumpEditor(tester);
    expect(find.text('100%'), findsOneWidget);

    await tester.tap(find.byTooltip('放大'));
    await tester.pump();
    expect(find.text('120%'), findsOneWidget);

    await tester.tap(find.byTooltip('缩小'));
    await tester.pump();
    expect(find.text('100%'), findsOneWidget);

    await tester.tap(find.text('100%'));
    await tester.pump();
    expect(find.text('已重置视图'), findsOneWidget);
  });

  testWidgets('对齐菜单', (tester) async {
    await _pumpEditor(tester);
    await tester.tap(find.byTooltip('全选 (Ctrl+A)'));
    await tester.pump();

    await tester.tap(find.byTooltip('对齐'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('顶部对齐').last);
    await tester.pump();
    expect(find.text('顶部对齐'), findsWidgets);
  });

  testWidgets('Ctrl+C 快捷键触发复制提示', (tester) async {
    await _pumpEditor(tester);
    // 选中一个节点
    await _tapNode(tester, 0);

    // 发送 Ctrl+C
    await tester.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
    await tester.sendKeyDownEvent(LogicalKeyboardKey.keyC);
    await tester.sendKeyUpEvent(LogicalKeyboardKey.keyC);
    await tester.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
    await tester.pump();

    expect(find.text('已复制 1 个节点'), findsOneWidget);
  });
}
