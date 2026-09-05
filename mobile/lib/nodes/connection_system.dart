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
  void startDrag(String nodeId, String portName) {
    _draggingFromNodeId = nodeId;
    _draggingFromPort = portName;
    notifyListeners();
  }

  // 结束拖拽连线
  bool endDrag(String? toNodeId, String? toPort) {
    if (_draggingFromNodeId == null || _draggingFromPort == null) {
      return false;
    }

    // 不能连接到自身
    if (toNodeId == _draggingFromNodeId) {
      return false;
    }

    // 不能连接到相同的端口
    if (toPort == _draggingFromPort) {
      return false;
    }

    // 检查是否已存在相同连接
    if (toNodeId != null && toPort != null) {
      removeConnectionToPort(toNodeId, toPort);
    }

    // 创建新连接
    final connection = Connection(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      fromNodeId: _draggingFromNodeId!,
      fromPortName: _draggingFromPort!,
      toNodeId: toNodeId ?? '',
      toPortName: toPort ?? '',
    );

    addConnection(connection);
    return true;
  }

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
  Offset? get dragStartPos => null;
  Offset? get dragEndPos => null;

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
  bool shouldRepaint(covariant ConnectionPainter oldDelegate) {
    return oldDelegate.controller != controller ||
        oldDelegate.nodePositions != nodePositions ||
        oldDelegate.portPositions != portPositions;
  }
}
