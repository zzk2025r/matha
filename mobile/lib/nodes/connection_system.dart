// Matha 可视化编程器 - 连线系统
// 实现节点之间的数据流连接

import 'package:flutter/material.dart';

/// 连线数据
class Connection {
  final String id;
  final String fromNodeId;
  final String fromPortName;
  final String toNodeId;
  final String toPortName;

  const Connection({
    required this.id,
    required this.fromNodeId,
    required this.fromPortName,
    required this.toNodeId,
    required this.toPortName,
  });

  Map<String, dynamic> toMap() => {
    'id': id,
    'fromNodeId': fromNodeId,
    'fromPortName': fromPortName,
    'toNodeId': toNodeId,
    'toPortName': toPortName,
  };

  factory Connection.fromMap(Map<String, dynamic> map) => Connection(
    id: map['id'] as String,
    fromNodeId: map['fromNodeId'] as String,
    fromPortName: map['fromPortName'] as String,
    toNodeId: map['toNodeId'] as String,
    toPortName: map['toPortName'] as String,
  );
}

/// 连线控制器
class ConnectionController extends ChangeNotifier {
  final Map<String, List<Connection>> _nodeConnections = {};
  final List<Connection> _connections = [];

  // 拖拽状态
  String? _draggingFromNodeId;
  String? _draggingFromPort;
  Offset? _dragStartPos;
  Offset? _dragEndPos;

  // 获取所有连线
  List<Connection> get connections => List.unmodifiable(_connections);

  // 获取指定节点的所有连线
  List<Connection> getNodeConnections(String nodeId) {
    return _nodeConnections[nodeId] ?? [];
  }

  // 获取节点的输出端口
  (String?, String?) getOutputPort(String nodeId) {
    final conns = getNodeConnections(nodeId);
    for (final conn in conns) {
      if (conn.fromNodeId == nodeId) {
        return (conn.fromPortName, null);
      }
    }
    return (null, null);
  }

  // 获取节点的输入端口
  (String?, String?) getInputPort(String nodeId) {
    final conns = getNodeConnections(nodeId);
    for (final conn in conns) {
      if (conn.toNodeId == nodeId) {
        return (null, conn.toPortName);
      }
    }
    return (null, null);
  }

  // 开始拖拽连线
  void startDrag(String nodeId, String portName, {Offset? startPos}) {
    _draggingFromNodeId = nodeId;
    _draggingFromPort = portName;
    _dragStartPos = startPos;
    _dragEndPos = startPos;
    notifyListeners();
  }

  // 更新拖拽预览终点
  void updateDrag(Offset endPos) {
    if (_draggingFromNodeId == null) return;
    _dragEndPos = endPos;
    notifyListeners();
  }

  // 取消拖拽
  void cancelDrag() {
    _draggingFromNodeId = null;
    _draggingFromPort = null;
    _dragStartPos = null;
    _dragEndPos = null;
    notifyListeners();
  }

  /// 结束拖拽连线。
  /// 返回 true 表示成功建立一条新连线；false 表示被拒绝（并已取消拖拽）。
  bool endDrag(String? toNodeId, String? toPort) {
    final fromNode = _draggingFromNodeId;
    final fromPort = _draggingFromPort;

    // 未处于拖拽态：直接视为失败
    if (fromNode == null || fromPort == null) {
      cancelDrag();
      return false;
    }

    // 落点无效（空白 / 空端口）：取消，绝不产生悬空连线
    if (toNodeId == null ||
        toPort == null ||
        toNodeId.isEmpty ||
        toPort.isEmpty) {
      cancelDrag();
      return false;
    }

    // 不能连接到自身节点
    if (toNodeId == fromNode) {
      cancelDrag();
      return false;
    }

    // 不能把端口接到同名端口（输入接输入、输出接输出无意义）
    if (toPort == fromPort) {
      cancelDrag();
      return false;
    }

    // 完全相同的连线已存在：拒绝，避免重复
    final alreadyExists = _connections.any((c) =>
        c.fromNodeId == fromNode &&
        c.fromPortName == fromPort &&
        c.toNodeId == toNodeId &&
        c.toPortName == toPort);
    if (alreadyExists) {
      cancelDrag();
      return false;
    }

    // 同一「目标输入端口」只保留一条入线：覆盖旧的入线
    // 注意：只清理目标端口作为输入端的既有连线，不影响其作为输出端的扇出
    final conflicts = _connections
        .where((c) => c.toNodeId == toNodeId && c.toPortName == toPort)
        .map((c) => c.id)
        .toList();
    for (final id in conflicts) {
      removeConnection(id);
    }

    // 创建新连线（用自增+时间戳保证唯一 id）
    final connection = Connection(
      id: _nextConnectionId(),
      fromNodeId: fromNode,
      fromPortName: fromPort,
      toNodeId: toNodeId,
      toPortName: toPort,
    );

    addConnection(connection);
    cancelDrag();
    return true;
  }

  int _connectionSeq = 0;
  String _nextConnectionId() =>
      'conn_${DateTime.now().microsecondsSinceEpoch}_${_connectionSeq++}';

  // 添加连线
  void addConnection(Connection connection) {
    _connections.add(connection);
    _addToNodeConnections(connection.fromNodeId, connection.id);
    _addToNodeConnections(connection.toNodeId, connection.id);
    notifyListeners();
  }

  // 移除连线
  void removeConnection(String connectionId) {
    _connections.removeWhere((c) => c.id == connectionId);
    for (final nodeId in _nodeConnections.keys) {
      _nodeConnections[nodeId]?.removeWhere((c) => c.id == connectionId);
    }
    notifyListeners();
  }

  // 移除连接到指定端口的连线
  void removeConnectionToPort(String nodeId, String portName) {
    final conns = getNodeConnections(nodeId);
    for (final conn in conns.toList()) {
      if ((conn.fromNodeId == nodeId && conn.fromPortName == portName) ||
          (conn.toNodeId == nodeId && conn.toPortName == portName)) {
        removeConnection(conn.id);
      }
    }
  }

  // 清除所有连线
  void clearAll() {
    _connections.clear();
    _nodeConnections.clear();
    notifyListeners();
  }

  // 反序列化
  void deserialize(List<Map<String, dynamic>> data) {
    _connections.clear();
    _nodeConnections.clear();
    for (final map in data) {
      addConnection(Connection.fromMap(map));
    }
  }

  // 序列化
  List<Map<String, dynamic>> serialize() {
    return _connections.map((c) => c.toMap()).toList();
  }

  // 检查是否可以连接
  bool canConnect(String fromNodeId, String fromPort, String toNodeId, String toPort) {
    if (fromNodeId == toNodeId) return false;
    if (toNodeId.isEmpty && toPort.isEmpty) return true;
    if (toNodeId.isNotEmpty && toPort.isNotEmpty) {
      final existing = getNodeConnections(toNodeId);
      for (final conn in existing) {
        if (conn.toNodeId == toNodeId && conn.toPortName == toPort) {
          return false;
        }
      }
    }
    return true;
  }

  // 获取拖拽中的端口
  String? get draggingFromNodeId => _draggingFromNodeId;
  String? get draggingFromPort => _draggingFromPort;
  Offset? get dragStartPos => _dragStartPos;
  Offset? get dragEndPos => _dragEndPos;

  void _addToNodeConnections(String nodeId, String connectionId) {
    _nodeConnections.putIfAbsent(nodeId, () => []);
    _nodeConnections[nodeId]!.removeWhere((c) => c.id == connectionId);
    final conn = _connections.firstWhere((c) => c.id == connectionId, orElse: () => const Connection(id: '', fromNodeId: '', fromPortName: '', toNodeId: '', toPortName: ''));
    _nodeConnections[nodeId]!.add(conn);
  }
}

/// 连线路径数据
class ConnectionPath {
  final Offset start;
  final Offset end;
  final Offset control1;
  final Offset control2;

  const ConnectionPath({
    required this.start,
    required this.end,
    required this.control1,
    required this.control2,
  });

  Path toPath() {
    return Path()
      ..moveTo(start.dx, start.dy)
      ..cubicTo(control1.dx, control1.dy, control2.dx, control2.dy, end.dx, end.dy);
  }
}

/// 连线路径计算
ConnectionPath getConnectionPath(Offset start, Offset end) {
  final dx = (end.dx - start.dx).abs() * 0.5;
  return ConnectionPath(
    start: start,
    end: end,
    control1: Offset(start.dx + dx, start.dy),
    control2: Offset(end.dx - dx, end.dy),
  );
}

/// 连线绘制器
class ConnectionPainter extends CustomPainter {
  final ConnectionController controller;
  final Map<String, Offset> nodePositions;
  final Map<String, Map<String, Offset>> portPositions;

  const ConnectionPainter({
    required this.controller,
    required this.nodePositions,
    required this.portPositions,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = Colors.grey.shade600
      ..strokeWidth = 2.0
      ..style = PaintingStyle.stroke;

    for (final connection in controller.connections) {
      final startPort = portPositions[connection.fromNodeId]?[connection.fromPortName];
      final endPort = portPositions[connection.toNodeId]?[connection.toPortName];
      if (startPort != null && endPort != null) {
        final path = getConnectionPath(startPort, endPort);
        canvas.drawPath(path.toPath(), paint);
      }
    }
  }

  @override
  bool shouldRepaint(covariant ConnectionPainter oldDelegate) => true;
}
