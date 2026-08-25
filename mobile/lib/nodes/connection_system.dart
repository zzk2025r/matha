// Matha 可视化编程器 - 连线系统
// 实现节点之间的数据流连接

import 'dart:async';
import 'dart:math';
import 'package:flutter/material.dart';
import 'node_types.dart';

/// 连线数据
class Connection {
  final String id;
  final String fromNodeId;
  final String fromPortName;
  final String toNodeId;
  final String toPortName;
  final DateTime createdAt;

  Connection({
    required this.id,
    required this.fromNodeId,
    required this.fromPortName,
    required this.toNodeId,
    required this.toPortName,
    required this.createdAt,
  });

  Map<String, dynamic> toMap() {
    return {
      'id': id,
      'fromNodeId': fromNodeId,
      'fromPortName': fromPortName,
      'toNodeId': toNodeId,
      'toPortName': toPortName,
      'createdAt': createdAt.toIso8601String(),
    };
  }

  factory Connection.fromMap(Map<String, dynamic> map) {
    return Connection(
      id: map['id'] as String,
      fromNodeId: map['fromNodeId'] as String,
      fromPortName: map['fromPortName'] as String,
      toNodeId: map['toNodeId'] as String,
      toPortName: map['toPortName'] as String,
      createdAt: DateTime.parse(map['createdAt'] as String),
    );
  }

  Connection copyWith({String? id}) {
    return Connection(
      id: id ?? this.id,
      fromNodeId: fromNodeId,
      fromPortName: fromPortName,
      toNodeId: toNodeId,
      toPortName: toPortName,
      createdAt: createdAt,
    );
  }
}

/// 连线控制器
class ConnectionController extends ChangeNotifier {
  final Map<String, Connection> _connections = {};
  final Map<String, List<String>> _nodeConnections = {};
  
  // 拖拽状态
  String? _draggingFromNodeId;
  String? _draggingFromPort;
  String? _draggingToNodeId;
  String? _draggingToPort;
  Offset? _dragStartPos;
  Offset? _dragEndPos;

  // 获取所有连线
  List<Connection> get connections => _connections.values.toList();
  
  // 获取节点的所有连线
  List<Connection> getNodeConnections(String nodeId) {
    final ids = _nodeConnections[nodeId] ?? [];
    return ids.map((id) => _connections[id]!).toList();
  }
  
  // 获取连线的端口信息
  (String?, String?) getOutputPort(String nodeId) {
    final conns = getNodeConnections(nodeId);
    for (final conn in conns) {
      if (conn.fromNodeId == nodeId) {
        return (conn.fromPortName, null);
      }
    }
    return (null, null);
  }
  
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
  void startDrag(String nodeId, String portName, Offset position) {
    _draggingFromNodeId = nodeId;
    _draggingFromPort = portName;
    _dragStartPos = position;
    _dragEndPos = position;
    notifyListeners();
  }

  // 更新拖拽位置
  void updateDrag(Offset position) {
    _dragEndPos = position;
    notifyListeners();
  }

  // 结束拖拽（建立连接）
  bool endDrag(String? toNodeId, String? toPort) {
    if (_draggingFromNodeId == null || _draggingFromPort == null) {
      return false;
    }

    // 不能连接到自身
    if (toNodeId == _draggingFromNodeId) {
      _cancelDrag();
      return false;
    }

    // 不能连接相同类型的端口
    if (toPort == _draggingFromPort) {
      _cancelDrag();
      return false;
    }

    // 检查目标端口是否已有连接
    if (toNodeId != null && toPort != null) {
      // 移除旧连接
      removeConnectionToPort(toNodeId, toPort);
    }

    // 创建新连接
    final connection = Connection(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      fromNodeId: _draggingFromNodeId!,
      fromPortName: _draggingFromPort!,
      toNodeId: toNodeId ?? '',
      toPortName: toPort ?? '',
      createdAt: DateTime.now(),
    );

    addConnection(connection);
    _cancelDrag();
    return true;
  }

  // 添加连线
  void addConnection(Connection connection) {
    _connections[connection.id] = connection;
    
    // 更新节点的连线记录
    _addToNodeConnections(connection.fromNodeId, connection.id);
    _addToNodeConnections(connection.toNodeId, connection.id);
    
    notifyListeners();
  }

  // 移除连线
  void removeConnection(String connectionId) {
    final connection = _connections[connectionId];
    if (connection == null) return;
    
    _connections.remove(connectionId);
    _nodeConnections[connection.fromNodeId]?.remove(connectionId);
    _nodeConnections[connection.toNodeId]?.remove(connectionId);
    
    notifyListeners();
  }

  // 移除连接到特定端口的所有连线
  void removeConnectionToPort(String nodeId, String portName) {
    final ids = _nodeConnections[nodeId] ?? [];
    for (final id in ids.toList()) {
      final conn = _connections[id];
      if (conn != null && 
          ((conn.fromNodeId == nodeId && conn.fromPortName == portName) ||
           (conn.toNodeId == nodeId && conn.toPortName == portName))) {
        removeConnection(id);
      }
    }
  }

  // 清空所有连线
  void clearAll() {
    _connections.clear();
    _nodeConnections.clear();
    notifyListeners();
  }

  // 序列化
  List<Map<String, dynamic>> serialize() {
    return _connections.values.map((c) => c.toMap()).toList();
  }

  // 反序列化
  void deserialize(List<Map<String, dynamic>> data) {
    clearAll();
    for (final map in data) {
      addConnection(Connection.fromMap(map));
    }
  }

  // 拖拽预览位置
  Offset? get dragStartPos => _dragStartPos;
  Offset? get dragEndPos => _dragEndPos;
  String? get draggingFromNodeId => _draggingFromNodeId;
  String? get draggingFromPort => _draggingFromPort;

  void _cancelDrag() {
    _draggingFromNodeId = null;
    _draggingFromPort = null;
    _draggingToNodeId = null;
    _draggingToPort = null;
    _dragStartPos = null;
    _dragEndPos = null;
    notifyListeners();
  }

  void _addToNodeConnections(String nodeId, String connectionId) {
    _nodeConnections.putIfAbsent(nodeId, () => []);
    _nodeConnections[nodeId]!.add(connectionId);
  }

  // 检查端口是否可以连接
  bool canConnect(String fromNodeId, String fromPort, String toNodeId, String toPort) {
    // 不能连接到自身
    if (fromNodeId == toNodeId) return false;
    
    // 检查目标端口是否已有连接
    if (toNodeId.isNotEmpty && toPort.isNotEmpty) {
      final existing = getNodeConnections(toNodeId);
      for (final conn in existing) {
        if (conn.toNodeId == toNodeId && conn.toPortName == toPort) {
          return false; // 端口已有连接
        }
      }
    }
    
    return true;
  }
}

/// 连线绘制器
class ConnectionPainter extends CustomPainter {
  final ConnectionController controller;
  final Map<String, Offset> nodePositions;
  final Map<String, Map<String, Offset>> portPositions;
  final Color color;
  final double strokeWidth;

  ConnectionPainter({
    required this.controller,
    required this.nodePositions,
    required this.portPositions,
    this.color = Colors.blue,
    this.strokeWidth = 2.0,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..strokeWidth = strokeWidth
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    // 绘制已存在的连线
    for (final connection in controller.connections) {
      _drawConnection(canvas, paint, connection);
    }

    // 绘制拖拽中的连线
    if (controller.draggingFromNodeId != null && 
        controller.dragStartPos != null && 
        controller.dragEndPos != null) {
      _drawDraggingConnection(canvas, paint);
    }
  }

  void _drawConnection(Canvas canvas, Paint paint, Connection connection) {
    final fromPos = _getPortPosition(connection.fromNodeId, connection.fromPortName);
    final toPos = _getPortPosition(connection.toNodeId, connection.toPortName);
    
    if (fromPos == null || toPos == null) return;

    final path = _createCurvePath(fromPos, toPos);
    canvas.drawPath(path, paint);
  }

  void _drawDraggingConnection(Canvas canvas, Paint paint) {
    final fromPos = controller.dragStartPos;
    final toPos = controller.dragEndPos;
    
    if (fromPos == null || toPos == null) return;

    final path = _createCurvePath(fromPos, toPos);
    canvas.drawPath(path, paint..color = color.withAlpha(128));
  }

  Path _createCurvePath(Offset start, Offset end) {
    final dx = (end.dx - start.dx).abs();
    final dy = (end.dy - start.dy).abs();
    final controlOffset = Offset(dx * 0.5, dy * 0.2);
    
    return Path()
      ..moveTo(start.dx, start.dy)
      ..cubicTo(
        start.dx + controlOffset.dx, start.dy,
        end.dx - controlOffset.dx, end.dy,
        end.dx, end.dy,
      );
  }

  Offset? _getPortPosition(String nodeId, String portName) {
    final nodePos = nodePositions[nodeId];
    final ports = portPositions[nodeId];
    
    if (nodePos == null || ports == null) return null;
    
    final portPos = ports[portName];
    if (portPos == null) return null;
    
    return nodePos + portPos;
  }

  @override
  bool shouldRepaint(covariant ConnectionPainter oldDelegate) {
    return oldDelegate.controller != controller ||
           oldDelegate.nodePositions != nodePositions ||
           oldDelegate.portPositions != portPositions ||
           oldDelegate.color != color;
  }
}

/// 获取连线的屏幕路径
class ConnectionPath {
  final Offset start;
  final Offset end;
  final List<Offset> controlPoints;

  ConnectionPath({
    required this.start,
    required this.end,
    required this.controlPoints,
  });

  Path toPath() {
    return Path()
      ..moveTo(start.dx, start.dy)
      ..cubicTo(
        controlPoints[0].dx, controlPoints[0].dy,
        controlPoints[1].dx, controlPoints[1].dy,
        end.dx, end.dy,
      );
  }

  Offset sample(double t) {
    // 贝塞尔曲线采样
    final u = 1 - t;
    final xx = u*u*u*start.dx + 3*u*u*t*controlPoints[0].dx + 3*u*t*t*controlPoints[1].dx + t*t*t*end.dx;
    final yy = u*u*u*start.dy + 3*u*u*t*controlPoints[0].dy + 3*u*t*t*controlPoints[1].dy + t*t*t*end.dy;
    return Offset(xx, yy);
  }
}

/// 计算连线路径
ConnectionPath getConnectionPath(
  Offset start,
  Offset end,
) {
  final dx = (end.dx - start.dx).abs();
  final dy = (end.dy - start.dy).abs();
  
  final controlOffset = Offset(dx * 0.5, dy * 0.2);
  
  return ConnectionPath(
    start: start,
    end: end,
    controlPoints: [
      Offset(start.dx + controlOffset.dx, start.dy),
      Offset(end.dx - controlOffset.dx, end.dy),
    ],
  );
}
