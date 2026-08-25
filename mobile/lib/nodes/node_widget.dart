// Matha 可视化编程器 - 节点组件
// 实现节点 UI 渲染和交互

import 'package:flutter/material.dart';
import 'node_types.dart';
import 'connection_system.dart';

class NodeWidget extends StatefulWidget {
  final Node node;
  final Offset position;
  final Function(Offset) onUpdatePosition;
  final VoidCallback onRemove;
  final Function(String, Offset) onStartDragConnection;
  final Function(String?, String?) onEndDragConnection;
  final Function(String) isConnected;

  const NodeWidget({
    super.key,
    required this.node,
    required this.position,
    required this.onUpdatePosition,
    required this.onRemove,
    required this.onStartDragConnection,
    required this.onEndDragConnection,
    required this.isConnected,
  });

  @override
  State<NodeWidget> createState() => _NodeWidgetState();
}

class _NodeWidgetState extends State<NodeWidget> {
  late Offset _position;
  Offset? _dragStartPos;
  String? _draggingPort;
  bool _isHovered = false;

  @override
  void initState() {
    super.initState();
    _position = widget.position;
  }

  @override
  void didUpdateWidget(covariant NodeWidget oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.position != widget.position) {
      _position = widget.position;
    }
  }

  void _onPanStart(DragStartDetails details) {
    _dragStartPos = details.globalPosition;
  }

  void _onPanUpdate(DragUpdateDetails details) {
    if (_dragStartPos != null) {
      final delta = details.delta;
      setState(() {
        _position = Offset(_position.dx + delta.dx, _position.dy + delta.dy);
      });
      widget.onUpdatePosition(_position);
    }
  }

  void _onPanEnd(DragEndDetails details) {
    _dragStartPos = null;
  }

  void _onPortDragStart(DragStartDetails details, String portName, bool isInput) {
    _draggingPort = portName;
    final localPos = details.localPosition;
    final globalPos = _position + localPos;
    widget.onStartDragConnection(portName, globalPos);
  }

  void _onPortDragEnd(DragEndDetails details) {
    _draggingPort = null;
  }

  @override
  Widget build(BuildContext context) {
    final definition = widget.node.definition;
    final color = _getNodeColor(definition.category);
    
    return GestureDetector(
      onPanStart: _onPanStart,
      onPanUpdate: _onPanUpdate,
      onPanEnd: _onPanEnd,
      child: MouseRegion(
        onEnter: (_) => setState(() => _isHovered = true),
        onExit: (_) => setState(() => _isHovered = false),
        child: Container(
          width: 180,
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(
              color: _isHovered ? color : color.withAlpha(150),
              width: 2,
            ),
            boxShadow: [
              BoxShadow(
                color: color.withAlpha(30),
                blurRadius: 4,
                offset: const Offset(2, 2),
              ),
            ],
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // 标题栏
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                decoration: BoxDecoration(
                  color: color.withAlpha(50),
                  borderRadius: const BorderRadius.vertical(top: Radius.circular(8)),
                ),
                child: Row(
                  children: [
                    Icon(_getCategoryIcon(definition.category), size: 16, color: color),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        definition.label,
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                          color: color,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    if (_isHovered)
                      IconButton(
                        icon: const Icon(Icons.close, size: 16),
                        padding: EdgeInsets.zero,
                        constraints: const BoxConstraints(),
                        onPressed: widget.onRemove,
                      ),
                  ],
                ),
              ),
              
              // 端口区域
              Expanded(
                child: Row(
                  children: [
                    // 输入端口
                    if (definition.inputs.isNotEmpty)
                      Expanded(
                        child: _PortColumn(
                          ports: definition.inputs,
                          isInput: true,
                          node: widget.node,
                          isConnected: widget.isConnected,
                          onDragStart: _onPortDragStart,
                          onDragEnd: _onPortDragEnd,
                        ),
                      ),
                    
                    // 内容区域
                    Expanded(
                      flex: 2,
                      child: _NodeContent(
                        node: widget.node,
                        definition: definition,
                      ),
                    ),
                    
                    // 输出端口
                    if (definition.outputs.isNotEmpty)
                      Expanded(
                        child: _PortColumn(
                          ports: definition.outputs,
                          isInput: false,
                          node: widget.node,
                          isConnected: widget.isConnected,
                          onDragStart: _onPortDragStart,
                          onDragEnd: _onPortDragEnd,
                        ),
                      ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Color _getNodeColor(String category) {
    switch (category) {
      case '数学':
        return Colors.blue;
      case '逻辑':
        return Colors.green;
      case '变量':
        return Colors.orange;
      case '输入输出':
        return Colors.purple;
      case '控制流':
        return Colors.red;
      case '矩阵':
        return Colors.teal;
      case '统计':
        return Colors.pink;
      case '常量':
        return Colors.grey;
      case '序列':
        return Colors.indigo;
      default:
        return Colors.grey;
    }
  }

  IconData _getCategoryIcon(String category) {
    switch (category) {
      case '数学':
        return Icons.calculate;
      case '逻辑':
        return Icons.compare_arrows;
      case '变量':
        return Icons.variable_channel;
      case '输入输出':
        return Icons.input;
      case '控制流':
        return Icons.flow_chart;
      case '矩阵':
        return Icons.grid_on;
      case '统计':
        return Icons.analytics;
      case '常量':
        return Icons.constant;
      case '序列':
        return Icons.format_list_numbered;
      default:
        return Icons.help;
    }
  }
}

class _PortColumn extends StatelessWidget {
  final List<PortDefinition> ports;
  final bool isInput;
  final Node node;
  final Function(String) isConnected;
  final Function(DragStartDetails, String, bool) onDragStart;
  final Function(DragEndDetails) onDragEnd;

  const _PortColumn({
    required this.ports,
    required this.isInput,
    required this.node,
    required this.isConnected,
    required this.onDragStart,
    required this.onDragEnd,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
        children: ports.map((port) {
          final connected = isConnected(port.name);
          return _PortWidget(
            port: port,
            isInput: isInput,
            isConnected: connected,
            onDragStart: (details) => onDragStart(details, port.name, isInput),
            onDragEnd: onDragEnd,
          );
        }).toList(),
      ),
    );
  }
}

class _PortWidget extends StatelessWidget {
  final PortDefinition port;
  final bool isInput;
  final bool isConnected;
  final Function(DragStartDetails) onDragStart;
  final Function(DragEndDetails) onDragEnd;

  const _PortWidget({
    required this.port,
    required this.isInput,
    required this.isConnected,
    required this.onDragStart,
    required this.onDragEnd,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onPanStart: (details) => onDragStart(details),
      onPanEnd: onDragEnd,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 2),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (isInput) ...[
              Container(
                width: 12,
                height: 12,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: isConnected ? Colors.green : Colors.grey,
                  border: Border.all(color: Colors.white, width: 2),
                ),
              ),
              const SizedBox(width: 4),
              Text(
                port.name,
                style: const TextStyle(fontSize: 10),
              ),
            ] else ...[
              Text(
                port.name,
                style: const TextStyle(fontSize: 10),
              ),
              const SizedBox(width: 4),
              Container(
                width: 12,
                height: 12,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: isConnected ? Colors.green : Colors.grey,
                  border: Border.all(color: Colors.white, width: 2),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _NodeContent extends StatelessWidget {
  final Node node;
  final NodeDefinition definition;

  const _NodeContent({required this.node, required this.definition});

  @override
  Widget build(BuildContext context) {
    // 显示节点配置信息
    if (definition.nodeType == NodeType.CONSTANT.id ||
        definition.nodeType == NodeType.MATH_PI.id ||
        definition.nodeType == NodeType.MATH_E.id) {
      return Center(
        child: Text(
          node.outputs.values.firstOrNull?.toString() ?? '',
          style: const TextStyle(fontSize: 11, color: Colors.grey),
        ),
      );
    }
    
    return const SizedBox.shrink();
  }
}
