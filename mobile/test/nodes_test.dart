// Matha 可视化编程器 - 测试

import 'package:flutter_test/flutter_test.dart';
import 'package:matha_mobile/nodes/node_types.dart';
import 'package:matha_mobile/nodes/connection_system.dart';
import 'package:matha_mobile/nodes/advanced_node_types.dart';
import 'package:matha_mobile/nodes/editor_enhancements.dart';

void main() {
  group('节点类型测试', () {
    test('注册所有节点', () {
      NodeRegistry.registerDefaults();
      AdvancedNodeTypes.registerAll();

      final allNodes = NodeRegistry.get_all();
      expect(allNodes.length, greaterThan(30));
    });

    test('搜索节点', () {
      NodeRegistry.registerDefaults();
      AdvancedNodeTypes.registerAll();

      final results = NodeRegistry.get_by_category('数学');
      expect(results.length, greaterThan(0));
    });

    test('按类别获取节点', () {
      NodeRegistry.registerDefaults();
      AdvancedNodeTypes.registerAll();

      final mathNodes = NodeRegistry.get_by_category('数学');
      expect(mathNodes.length, greaterThan(0));

      final logicNodes = NodeRegistry.get_by_category('控制流');
      expect(logicNodes.length, greaterThan(0));
    });
  });

  group('连线系统测试', () {
    test('创建连线', () {
      final controller = ConnectionController();

      controller.startDrag('node1', 'output');
      final result = controller.endDrag('node2', 'input');
      expect(result, true);
    });

    test('移除连线', () {
      final controller = ConnectionController();

      controller.startDrag('node1', 'output');
      controller.endDrag('node2', 'input');

      final connections = controller.connections;
      expect(connections.length, 1);

      controller.removeConnection(connections.first.id);
      expect(controller.connections.length, 0);
    });

    test('清空所有连线', () {
      final controller = ConnectionController();

      controller.startDrag('node1', 'output');
      controller.endDrag('node2', 'input');

      controller.startDrag('node2', 'output');
      controller.endDrag('node3', 'input');

      controller.clearAll();
      expect(controller.connections.length, 0);
    });
  });

  group('编辑器增强测试', () {
    test('搜索节点', () {
      AdvancedNodeTypes.registerAll();
      final enhancements = EditorEnhancements();

      final results = enhancements.searchNodes('math');
      expect(results.length, greaterThan(0));
    });

    test('创建节点组', () {
      final enhancements = EditorEnhancements();

      final groupId = enhancements.createGroup('测试组', ['node1', 'node2']);
      expect(groupId.isNotEmpty, true);
      expect(enhancements.groups.length, 1);
    });

    test('自动布局', () {
      final enhancements = EditorEnhancements();

      final positions = {
        'node1': const Offset(0, 0),
        'node2': const Offset(100, 100),
        'node3': const Offset(200, 200),
      };

      enhancements.autoLayout(
        positions,
        [],
        LayoutAlgorithm.grid,
      );

      expect(positions.length, 3);
    });
  });
}
