// 连线系统单元测试：连接成功 / 自动取消 / 断开 / 多端口 / 漏洞排查

import 'package:flutter_test/flutter_test.dart';
import 'package:matha_mobile/nodes/connection_system.dart';

void main() {
  group('ConnectionController 基础连接', () {
    test('从 A 输出端口连到 B 输入端口成功', () {
      final c = ConnectionController();
      c.startDrag('A', 'result', startPos: const Offset(100, 100));
      final ok = c.endDrag('B', 'a');
      expect(ok, isTrue);
      expect(c.connections.length, 1);
      final conn = c.connections.first;
      expect(conn.fromNodeId, 'A');
      expect(conn.fromPortName, 'result');
      expect(conn.toNodeId, 'B');
      expect(conn.toPortName, 'a');
    });

    test('连接后两端节点都能查到该连线', () {
      final c = ConnectionController();
      c.startDrag('A', 'result', startPos: Offset.zero);
      c.endDrag('B', 'a');
      expect(c.getNodeConnections('A').length, 1);
      expect(c.getNodeConnections('B').length, 1);
      expect(c.getOutputPort('A').$1, 'result');
      expect(c.getInputPort('B').$2, 'a');
    });
  });

  group('自动取消（不应创建连线）', () {
    test('落在空白处（toNodeId/toPort 为空）应取消且不产生悬空连线', () {
      final c = ConnectionController();
      c.startDrag('A', 'result', startPos: Offset.zero);
      final ok = c.endDrag(null, null);
      expect(ok, isFalse);
      expect(c.connections, isEmpty);
      expect(c.draggingFromNodeId, isNull);
      expect(c.dragStartPos, isNull);
      expect(c.dragEndPos, isNull);
    });

    test('落在空字符串端口也应取消（防止悬空连线）', () {
      final c = ConnectionController();
      c.startDrag('A', 'result', startPos: Offset.zero);
      final ok = c.endDrag('', '');
      expect(ok, isFalse);
      expect(c.connections, isEmpty);
    });

    test('不能连接到自身节点', () {
      final c = ConnectionController();
      c.startDrag('A', 'result', startPos: Offset.zero);
      final ok = c.endDrag('A', 'a');
      expect(ok, isFalse);
      expect(c.connections, isEmpty);
    });

    test('不能连接到相同端口名', () {
      final c = ConnectionController();
      c.startDrag('A', 'x', startPos: Offset.zero);
      final ok = c.endDrag('B', 'x');
      expect(ok, isFalse);
      expect(c.connections, isEmpty);
    });

    test('重复的相同连线被拒绝', () {
      final c = ConnectionController();
      c.startDrag('A', 'result', startPos: Offset.zero);
      c.endDrag('B', 'a');
      c.startDrag('A', 'result', startPos: Offset.zero);
      final ok = c.endDrag('B', 'a');
      expect(ok, isFalse);
      expect(c.connections.length, 1);
    });

    test('在未开始拖拽时调用 endDrag 不会崩溃', () {
      final c = ConnectionController();
      expect(c.endDrag('B', 'a'), isFalse);
      expect(c.connections, isEmpty);
    });
  });

  group('断开连线', () {
    test('removeConnection 移除后两端都不再持有', () {
      final c = ConnectionController();
      c.startDrag('A', 'result', startPos: Offset.zero);
      c.endDrag('B', 'a');
      final id = c.connections.first.id;
      c.removeConnection(id);
      expect(c.connections, isEmpty);
      expect(c.getNodeConnections('A'), isEmpty);
      expect(c.getNodeConnections('B'), isEmpty);
    });

    test('removeConnectionToPort 断开指定端口连线', () {
      final c = ConnectionController();
      c.startDrag('A', 'result', startPos: Offset.zero);
      c.endDrag('B', 'a');
      c.removeConnectionToPort('B', 'a');
      expect(c.connections, isEmpty);
    });

    test('clearAll 清空全部连线', () {
      final c = ConnectionController();
      c.startDrag('A', 'result', startPos: Offset.zero);
      c.endDrag('B', 'a');
      c.startDrag('C', 'result', startPos: Offset.zero);
      c.endDrag('D', 'x');
      expect(c.connections.length, 2);
      c.clearAll();
      expect(c.connections, isEmpty);
      expect(c.getNodeConnections('A'), isEmpty);
      expect(c.getNodeConnections('C'), isEmpty);
    });
  });

  group('多端口连线', () {
    test('同一输出端口可连到多个输入端口', () {
      final c = ConnectionController();
      c.startDrag('A', 'result', startPos: Offset.zero);
      expect(c.endDrag('B', 'a'), isTrue);
      c.startDrag('A', 'result', startPos: Offset.zero);
      expect(c.endDrag('C', 'x'), isTrue);
      expect(c.connections.length, 2);
      expect(c.getNodeConnections('A').length, 2);
    });

    test('同一输入端口只保留一条连线（新连线覆盖旧连线）', () {
      final c = ConnectionController();
      c.startDrag('A', 'result', startPos: Offset.zero);
      expect(c.endDrag('C', 'x'), isTrue);
      c.startDrag('B', 'result', startPos: Offset.zero);
      expect(c.endDrag('C', 'x'), isTrue);
      expect(c.connections.length, 1);
      expect(c.connections.first.fromNodeId, 'B');
    });

    test('一个节点同时有输入与输出连线时端口查询正确', () {
      final c = ConnectionController();
      c.startDrag('A', 'result', startPos: Offset.zero);
      c.endDrag('B', 'a');
      c.startDrag('B', 'result', startPos: Offset.zero);
      c.endDrag('C', 'x');
      expect(c.getNodeConnections('B').length, 2);
      expect(c.getInputPort('B').$2, 'a');
      expect(c.getOutputPort('B').$1, 'result');
    });
  });

  group('拖拽过程状态', () {
    test('startDrag 记录起点，updateDrag 更新终点', () {
      final c = ConnectionController();
      c.startDrag('A', 'result', startPos: const Offset(10, 20));
      expect(c.draggingFromNodeId, 'A');
      expect(c.draggingFromPort, 'result');
      expect(c.dragStartPos, const Offset(10, 20));

      c.updateDrag(const Offset(80, 90));
      expect(c.dragEndPos, const Offset(80, 90));
    });

    test('cancelDrag 清除所有拖拽状态', () {
      final c = ConnectionController();
      c.startDrag('A', 'result', startPos: Offset.zero);
      c.updateDrag(const Offset(50, 50));
      c.cancelDrag();
      expect(c.draggingFromNodeId, isNull);
      expect(c.draggingFromPort, isNull);
      expect(c.dragStartPos, isNull);
      expect(c.dragEndPos, isNull);
    });
  });

  group('序列化 / 反序列化', () {
    test('往返序列化保持一致', () {
      final c = ConnectionController();
      c.startDrag('A', 'result', startPos: Offset.zero);
      c.endDrag('B', 'a');
      c.startDrag('C', 'result', startPos: Offset.zero);
      c.endDrag('D', 'x');
      final data = c.serialize();
      expect(data.length, 2);

      final c2 = ConnectionController();
      c2.deserialize(data);
      expect(c2.connections.length, 2);
      expect(c2.getNodeConnections('A').length, 1);
      expect(c2.getNodeConnections('D').length, 1);
    });

    test('序列化后再 deserialize 不残留旧连线', () {
      final c = ConnectionController();
      c.startDrag('A', 'result', startPos: Offset.zero);
      c.endDrag('B', 'a');
      c.deserialize([]);
      expect(c.connections, isEmpty);
      expect(c.getNodeConnections('A'), isEmpty);
    });
  });

  group('连线路径几何', () {
    test('getConnectionPath 控制点在水平方向展开', () {
      final path = getConnectionPath(const Offset(0, 0), const Offset(200, 100));
      expect(path.start, const Offset(0, 0));
      expect(path.end, const Offset(200, 100));
      // control1 在起点右侧，control2 在终点左侧
      expect(path.control1.dx, greaterThan(path.start.dx));
      expect(path.control2.dx, lessThan(path.end.dx));
      expect(path.control1.dy, path.start.dy);
      expect(path.control2.dy, path.end.dy);
    });

    test('toPath 生成有效路径', () {
      final path = getConnectionPath(Offset.zero, const Offset(100, 50));
      final p = path.toPath();
      expect(p.getBounds().isEmpty, isFalse);
    });
  });

  group('通知（ChangeNotifier）', () {
    test('连接与断开都会通知监听者', () {
      final c = ConnectionController();
      var notified = 0;
      c.addListener(() => notified++);
      c.startDrag('A', 'result', startPos: Offset.zero);
      c.endDrag('B', 'a');
      final id = c.connections.first.id;
      c.removeConnection(id);
      expect(notified, greaterThanOrEqualTo(3));
    });
  });
}
