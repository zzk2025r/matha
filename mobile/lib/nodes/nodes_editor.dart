// Matha 可视化编程器 - 节点编辑器框架
// 实现拖拽式界面基础结构

import 'dart:convert';
import 'package:flutter/material.dart';
import 'node_types.dart';
import 'connection_system.dart';
import 'node_widget.dart';
import 'node_palette.dart';
import 'editor_toolbar.dart';

class NodesEditor extends StatefulWidget {
  final List<Node> initialNodes;
  final List<Map<String, dynamic>> initialConnections;

  const NodesEditor({
    super.key,
    this.initialNodes = const [],
    this.initialConnections = const [],
  });

  @override
  State<NodesEditor> createState() => _NodesEditorState();
}

class _NodesEditorState extends State<NodesEditor> {
  final Map<String, Offset> _nodePositions = {};
  final Map<String, Map<String, Offset>> _portPositions = {};
  final List<Node> _nodes = [];
  final ConnectionController _connectionController = ConnectionController();
  final ScrollController _scrollController = ScrollController();
  
  Offset? _dragStartPos;
  String? _draggingNodeId;
  double _scale = 1.0;
  Offset _offset = Offset.zero;

  @override
  void initState() {
    super.initState();
    _initializeNodes();
  }

  void _initializeNodes() {
    for (final node in widget.initialNodes) {
      _nodes.add(node);
      _nodePositions[node.id.toString()] = Offset(
        node.position.dx,
        node.position.dy,
      );
    }
    
    if (widget.initialConnections.isNotEmpty) {
      _connectionController.deserialize(widget.initialConnections);
    }
  }

  void _addNode(NodeType nodeType, Offset position) {
    final node = Node(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      nodeType: nodeType.id,
      position: position,
    );
    _nodes.add(node);
    _nodePositions[node.id.toString()] = position;
    setState(() {});
  }

  void _updateNodePosition(String nodeId, Offset position) {
    _nodePositions[nodeId] = position;
    setState(() {});
  }

  void _removeNode(String nodeId) {
    _nodes.removeWhere((n) => n.id.toString() == nodeId);
    _nodePositions.remove(nodeId);
    _connectionController.removeConnectionToPort(nodeId, '');
    setState(() {});
  }

  void _clearAll() {
    _nodes.clear();
    _nodePositions.clear();
    _connectionController.clearAll();
    setState(() {});
  }

  Map<String, dynamic> _serialize() {
    return {
      'nodes': _nodes.map((n) => n.toMap()).toList(),
      'connections': _connectionController.serialize(),
    };
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Column(
        children: [
          // 工具栏
          EditorToolbar(
            onAddNode: (type) => _showNodePalette(type),
            onClear: _clearAll,
            onExport: () => _exportGraph(),
            onImport: () => _importGraph(),
            nodeCount: _nodes.length,
            connectionCount: _connectionController.connections.length,
          ),
          Expanded(
            child: GestureDetector(
              onPanStart: _onPanStart,
              onPanUpdate: _onPanUpdate,
              onPanEnd: _onPanEnd,
              child: SizedBox(
                width: double.infinity,
                height: double.infinity,
                child: Stack(
                  children: [
                    // 网格背景
                    _GridBackground(scale: _scale, offset: _offset),
                    
                    // 节点画布
                    Transform(
                      transform: Matrix4.identity()
                        ..scale(_scale)
                        ..translate(_offset.dx, _offset.dy),
                      child: SizedBox(
                        width: double.infinity,
                        height: double.infinity,
                        child: CustomPaint(
                          painter: ConnectionPainter(
                            controller: _connectionController,
                            nodePositions: _nodePositions,
                            portPositions: _portPositions,
                          ),
                          child: Stack(
                            children: [
                              // 节点组件
                              ..._nodes.map((node) {
                                final position = _nodePositions[node.id.toString()] ?? Offset.zero;
                                return Positioned(
                                  left: position.dx,
                                  top: position.dy,
                                  child: NodeWidget(
                                    node: node,
                                    position: position,
                                    onUpdatePosition: (pos) => _updateNodePosition(node.id.toString(), pos),
                                    onRemove: () => _removeNode(node.id.toString()),
                                    onStartDragConnection: (portName, pos) =>
                                      _connectionController.startDrag(node.id.toString(), portName),
                                    onEndDragConnection: (toNodeId, toPort) => 
                                      _connectionController.endDrag(toNodeId, toPort),
                                    isConnected: (portName) => _connectionController.getNodeConnections(node.id.toString())
                                        .any((c) => (c.fromNodeId == node.id.toString() && c.fromPortName == portName) ||
                                                    (c.toNodeId == node.id.toString() && c.toPortName == portName)),
                                  ),
                                );
                              }),
                              
                              // 拖拽预览
                              if (_connectionController.draggingFromNodeId != null &&
                                  _connectionController.dragStartPos != null &&
                                  _connectionController.dragEndPos != null)
                                _DragPreview(
                                  start: _connectionController.dragStartPos!,
                                  end: _connectionController.dragEndPos!,
                                ),
                            ],
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  void _showNodePalette(NodeType type) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (context) => DraggableScrollableSheet(
        initialChildSize: 0.7,
        maxChildSize: 0.9,
        builder: (context, scrollController) => NodePalette(
          category: type.label,
          onAddNode: (definition) {
            _addNode(definition.nodeType == NodeType.MATH_ADD.id ? NodeType.MATH_ADD : type, Offset(100, 100));
            Navigator.pop(context);
          },
        ),
      ),
    );
  }

  void _exportGraph() {
    final data = _serialize();
    final json = const JsonEncoder.withIndent('  ').convert(data);
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('导出节点图'),
        content: SingleChildScrollView(
          child: SelectableText(json),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('关闭'),
          ),
        ],
      ),
    );
  }

  void _importGraph() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('导入节点图'),
        content: TextField(
          maxLines: 10,
          decoration: const InputDecoration(
            hintText: '粘贴 JSON 数据...',
            border: OutlineInputBorder(),
          ),
          onSubmitted: (value) {
            try {
              jsonDecode(value) as Map<String, dynamic>;
              // TODO: 实现导入逻辑
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('导入成功')),
              );
              Navigator.pop(context);
            } catch (e) {
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(content: Text('导入失败: $e')),
              );
            }
          },
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('取消'),
          ),
        ],
      ),
    );
  }

  void _onPanStart(DragStartDetails details) {
    _dragStartPos = details.globalPosition;
  }

  void _onPanUpdate(DragUpdateDetails details) {
    if (_draggingNodeId != null) {
      final delta = details.delta / _scale;
      final nodeId = _draggingNodeId!;
      final oldPos = _nodePositions[nodeId] ?? Offset.zero;
      _updateNodePosition(nodeId, oldPos + delta);
    } else if (_dragStartPos != null) {
      // 画布平移
      _offset += details.delta;
      setState(() {});
    }
  }

  void _onPanEnd(DragEndDetails details) {
    _draggingNodeId = null;
    _dragStartPos = null;
  }

  @override
  void dispose() {
    _connectionController.dispose();
    _scrollController.dispose();
    super.dispose();
  }
}

/// 网格背景
class _GridBackground extends StatelessWidget {
  final double scale;
  final Offset offset;

  const _GridBackground({required this.scale, required this.offset});

  @override
  Widget build(BuildContext context) {
    return CustomPaint(
      size: Size.infinite,
      painter: _GridPainter(scale: scale, offset: offset),
    );
  }
}

class _GridPainter extends CustomPainter {
  final double scale;
  final Offset offset;

  _GridPainter({required this.scale, required this.offset});

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = const Color(0xFFE0E0E0)
      ..strokeWidth = 0.5;

    final gridSize = 20 * scale;
    final startX = offset.dx % gridSize;
    final startY = offset.dy % gridSize;

    for (double x = startX; x < size.width; x += gridSize) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), paint);
    }

    for (double y = startY; y < size.height; y += gridSize) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), paint);
    }
  }

  @override
  bool shouldRepaint(covariant _GridPainter oldDelegate) {
    return oldDelegate.scale != scale || oldDelegate.offset != offset;
  }
}

/// 拖拽预览
class _DragPreview extends StatelessWidget {
  final Offset start;
  final Offset end;

  const _DragPreview({required this.start, required this.end});

  @override
  Widget build(BuildContext context) {
    final path = getConnectionPath(start, end);
    
    return CustomPaint(
      size: Size.infinite,
      painter: _DragPreviewPainter(path: path),
    );
  }
}

class _DragPreviewPainter extends CustomPainter {
  final ConnectionPath path;

  _DragPreviewPainter({required this.path});

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = Colors.blue.withAlpha(128)
      ..strokeWidth = 2
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    canvas.drawPath(path.toPath(), paint);
  }

  @override
  bool shouldRepaint(covariant _DragPreviewPainter oldDelegate) {
    return oldDelegate.path != path;
  }
}
