// Matha 可视化编程器 - 节点编辑器框架
// 实现拖拽式界面基础结构
// 增强：撤销/重做、多选、复制粘贴、对齐、缩放、快捷键

import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'node_types.dart';
import 'connection_system.dart';
import 'node_widget.dart';
import 'node_palette.dart';
import 'editor_toolbar.dart';
import 'editor_enhancements.dart';

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

  // 编辑器增强状态
  final EditorHistory _history = EditorHistory();
  final EditorSelection _selection = EditorSelection();
  final CanvasTransform _canvas = CanvasTransform();

  String? _clipboardJson;
  double _pinchStartScale = 1.0;

  @override
  void initState() {
    super.initState();
    _connectionController.addListener(_onConnectionChanged);
    _initializeNodes();
  }

  void _onConnectionChanged() {
    if (mounted) setState(() {});
  }

  /// 端口中心点上报（画布坐标系）
  void _updatePortPositions(String nodeId, Map<String, Offset> ports) {
    final existing = _portPositions[nodeId];
    var changed = existing == null || existing.length != ports.length;
    if (!changed) {
      for (final e in ports.entries) {
        if (existing[e.key] != e.value) {
          changed = true;
          break;
        }
      }
    }
    if (changed) {
      _portPositions[nodeId] = ports;
    }
  }

  /// 查找落点最近的端口（用于拖拽落点吸附）
  (String nodeId, String portName)? _findPortNear(Offset point, {double radius = 22}) {
    (String, String)? best;
    var bestDist = radius;
    for (final entry in _portPositions.entries) {
      for (final p in entry.value.entries) {
        final d = (p.value - point).distance;
        if (d <= bestDist) {
          bestDist = d;
          best = (entry.key, p.key);
        }
      }
    }
    return best;
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
    _pushHistory();
  }

  // ========== 历史 / 快照 ==========

  void _pushHistory() {
    _history.push(
      EditorSnapshot.take(_nodes, _nodePositions, _connectionController.serialize()),
    );
  }

  void _restoreSnapshot(EditorSnapshot snapshot) {
    _nodes
      ..clear()
      ..addAll(snapshot.nodes);
    _nodePositions
      ..clear()
      ..addAll(snapshot.positions);
    _connectionController
      ..clearAll()
      ..deserialize(snapshot.connections);
    _selection.retain(snapshot.nodes.map((n) => n.id));
    setState(() {});
  }

  void _undo() {
    final snapshot = _history.undo();
    if (snapshot != null) {
      _restoreSnapshot(snapshot);
      _toast('已撤销');
    }
  }

  void _redo() {
    final snapshot = _history.redo();
    if (snapshot != null) {
      _restoreSnapshot(snapshot);
      _toast('已重做');
    }
  }

  // ========== 节点操作 ==========

  void _addNode(NodeType nodeType, Offset position) {
    _pushHistory();
    final node = Node(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      nodeType: nodeType.id,
      position: position,
    );
    _nodes.add(node);
    _nodePositions[node.id.toString()] = position;
    _selection.select(node.id.toString());
    setState(() {});
  }

  void _updateNodePosition(String nodeId, Offset position) {
    _nodePositions[nodeId] = position;
    setState(() {});
  }

  void _removeNode(String nodeId) {
    _pushHistory();
    _nodes.removeWhere((n) => n.id.toString() == nodeId);
    _nodePositions.remove(nodeId);
    _dropNodeConnections(nodeId);
    _selection.retain(_nodes.map((n) => n.id));
    setState(() {});
  }

  void _dropNodeConnections(String nodeId) {
    final conns = _connectionController.connections
        .where((c) => c.fromNodeId == nodeId || c.toNodeId == nodeId)
        .toList();
    for (final c in conns) {
      _connectionController.removeConnection(c.id);
    }
  }

  void _clearAll() {
    _pushHistory();
    _nodes.clear();
    _nodePositions.clear();
    _connectionController.clearAll();
    _selection.clear();
    setState(() {});
  }

  // ========== 多选 ==========

  void _toggleSelect(String nodeId) {
    setState(() => _selection.toggle(nodeId));
  }

  void _selectAll() {
    if (_nodes.isEmpty) return;
    setState(() => _selection.selectAll(_nodes.map((n) => n.id)));
    _toast('已选中 ${_selection.count} 个节点');
  }

  void _deleteSelected() {
    if (_selection.isEmpty) return;
    _pushHistory();
    final ids = _selection.ids.toList();
    for (final id in ids) {
      _nodes.removeWhere((n) => n.id.toString() == id);
      _nodePositions.remove(id);
      _dropNodeConnections(id);
    }
    _selection.clear();
    setState(() {});
    _toast('已删除 ${ids.length} 个节点');
  }

  // ========== 复制 / 粘贴 ==========

  void _copySelected() {
    if (_selection.isEmpty) {
      _toast('请先选择节点');
      return;
    }
    _clipboardJson = CopyPasteService.encode(
      nodes: _nodes,
      positions: _nodePositions,
      connections: _connectionController.serialize(),
      ids: _selection.ids,
    );
    _toast('已复制 ${_selection.count} 个节点');
  }

  void _pasteClipboard() {
    final json = _clipboardJson;
    if (json == null) {
      _toast('剪贴板为空');
      return;
    }
    try {
      final source = CopyPasteService.decode(json);
      if (source.nodes.isEmpty) return;
      final pasted = CopyPasteService.paste(EditorSnapshot.take(source.nodes, source.positions, source.connections));
      _pushHistory();
      for (final node in pasted.nodes) {
        _nodes.add(node);
        _nodePositions[node.id] = pasted.positions[node.id] ?? node.position;
      }
      _selection.selectAll(pasted.nodes.map((n) => n.id));
      _connectionController.deserialize([
        ..._connectionController.serialize(),
        ...pasted.connections,
      ]);
      setState(() {});
      _toast('已粘贴 ${pasted.nodes.length} 个节点');
    } catch (e) {
      _toast('粘贴失败: $e');
    }
  }

  // ========== 对齐 ==========

  void _align(AlignmentMode mode) {
    if (_selection.count < 2) {
      _toast('请选择至少 2 个节点进行对齐');
      return;
    }
    _pushHistory();
    final aligned = AlignmentUtils.align(
      positions: _nodePositions,
      sizes: const {},
      ids: _selection.ids,
      mode: mode,
    );
    _nodePositions
      ..clear()
      ..addAll(aligned);
    setState(() {});
    _toast(mode.label);
  }

  // ========== 缩放 ==========

  void _zoomIn() {
    setState(() => _canvas.zoomIn());
  }

  void _zoomOut() {
    setState(() => _canvas.zoomOut());
  }

  void _resetZoom() {
    setState(() => _canvas.reset());
    _toast('已重置视图');
  }

  // ========== 手势 ==========

  void _onScaleStart(ScaleStartDetails details) {
    _pinchStartScale = _canvas.scale;
  }

  void _onScaleUpdate(ScaleUpdateDetails details) {
    setState(() {
      if (details.pointerCount >= 2) {
        _canvas.scale = (_pinchStartScale * details.scale)
            .clamp(CanvasTransform.minScale, CanvasTransform.maxScale);
      } else {
        _canvas.panBy(details.focalPointDelta);
      }
    });
  }

  // ========== 其他 ==========

  void _toast(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(message), duration: const Duration(milliseconds: 1200)));
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
            child: Shortcuts(
              shortcuts: _keyboardShortcuts(),
              child: Actions(
                actions: _actions(),
                child: Focus(
                  autofocus: true,
                  child: GestureDetector(
                    onScaleStart: _onScaleStart,
                    onScaleUpdate: _onScaleUpdate,
                    onTapUp: (_) => setState(() => _selection.clear()),
                    child: SizedBox(
                      width: double.infinity,
                      height: double.infinity,
                      child: Stack(
                        children: [
                          // 网格背景
                          _GridBackground(scale: _canvas.scale, offset: _canvas.pan),

                          // 节点画布
                          Transform(
                            transform: Matrix4.identity()
                              ..scaleByDouble(_canvas.scale, _canvas.scale, _canvas.scale, 1.0)
                              ..translateByDouble(_canvas.pan.dx, _canvas.pan.dy, 0.0, 1.0),
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
                                      final id = node.id.toString();
                                      final position = _nodePositions[id] ?? Offset.zero;
                                      final selected = _selection.contains(id);
                                      return Positioned(
                                        left: position.dx,
                                        top: position.dy,
                                        child: GestureDetector(
                                          onTap: () => _toggleSelect(id),
                                          child: Stack(
                                            children: [
                                              NodeWidget(
                                                node: node,
                                                position: position,
                                                onUpdatePosition: (pos) =>
                                                    _updateNodePosition(id, pos),
                                                onRemove: () => _removeNode(id),
                                                onStartDragConnection: (portName, pos) {
                                                  _pushHistory();
                                                  _connectionController.startDrag(
                                                      id, portName, startPos: pos);
                                                },
                                                onUpdateDragConnection: (pos) =>
                                                    _connectionController.updateDrag(pos),
                                                onEndDragConnection: (_, __) {
                                                  final end =
                                                      _connectionController.dragEndPos;
                                                  if (end == null) {
                                                    _connectionController.cancelDrag();
                                                    return;
                                                  }
                                                  final hit = _findPortNear(end);
                                                  if (hit != null &&
                                                      _connectionController.endDrag(
                                                          hit.$1, hit.$2)) {
                                                    _toast('已连接');
                                                  } else {
                                                    _connectionController.cancelDrag();
                                                  }
                                                },
                                                onPortPositions: _updatePortPositions,
                                                isConnected: (portName) =>
                                                    _connectionController
                                                        .getNodeConnections(id)
                                                        .any((c) =>
                                                            (c.fromNodeId == id &&
                                                                c.fromPortName == portName) ||
                                                            (c.toNodeId == id &&
                                                                c.toPortName == portName)),
                                                onDragStart: _pushHistory,
                                              ),
                                              if (selected)
                                                Positioned.fill(
                                                  child: IgnorePointer(
                                                    child: Container(
                                                      decoration: BoxDecoration(
                                                        border: Border.all(
                                                          color: Colors.blue,
                                                          width: 2,
                                                        ),
                                                        borderRadius:
                                                            BorderRadius.circular(8),
                                                      ),
                                                    ),
                                                  ),
                                                ),
                                            ],
                                          ),
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

                          // 动作栏
                          Positioned(
                            left: 0,
                            right: 0,
                            bottom: 16,
                            child: Center(
                              child: _EditorActionBar(
                                canUndo: _history.canUndo,
                                canRedo: _history.canRedo,
                                selectionCount: _selection.count,
                                onUndo: _undo,
                                onRedo: _redo,
                                onCopy: _copySelected,
                                onPaste: () => _pasteClipboard(),
                                onDelete: _deleteSelected,
                                onSelectAll: _selectAll,
                                onAlign: _align,
                                onZoomIn: _zoomIn,
                                onZoomOut: _zoomOut,
                                onResetZoom: _resetZoom,
                                zoomLabel: '${(_canvas.scale * 100).round()}%',
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ========== 快捷键 ==========

  Map<ShortcutActivator, Intent> _keyboardShortcuts() => {
    SingleActivator(LogicalKeyboardKey.keyZ, control: true): const _UndoIntent(),
    SingleActivator(LogicalKeyboardKey.keyZ, meta: true): const _UndoIntent(),
    SingleActivator(LogicalKeyboardKey.keyZ, control: true, shift: true): const _RedoIntent(),
    SingleActivator(LogicalKeyboardKey.keyZ, meta: true, shift: true): const _RedoIntent(),
    SingleActivator(LogicalKeyboardKey.keyY, control: true): const _RedoIntent(),
    SingleActivator(LogicalKeyboardKey.keyY, meta: true): const _RedoIntent(),
    SingleActivator(LogicalKeyboardKey.keyC, control: true): const _CopyIntent(),
    SingleActivator(LogicalKeyboardKey.keyC, meta: true): const _CopyIntent(),
    SingleActivator(LogicalKeyboardKey.keyV, control: true): const _PasteIntent(),
    SingleActivator(LogicalKeyboardKey.keyV, meta: true): const _PasteIntent(),
    SingleActivator(LogicalKeyboardKey.keyA, control: true): const _SelectAllIntent(),
    SingleActivator(LogicalKeyboardKey.keyA, meta: true): const _SelectAllIntent(),
    const SingleActivator(LogicalKeyboardKey.delete): const _DeleteIntent(),
  };

  Map<Type, Action<Intent>> _actions() => {
    _UndoIntent: CallbackAction<_UndoIntent>(onInvoke: (_) {
      _undo();
      return null;
    }),
    _RedoIntent: CallbackAction<_RedoIntent>(onInvoke: (_) {
      _redo();
      return null;
    }),
    _CopyIntent: CallbackAction<_CopyIntent>(onInvoke: (_) {
      _copySelected();
      return null;
    }),
    _PasteIntent: CallbackAction<_PasteIntent>(onInvoke: (_) {
      _pasteClipboard();
      return null;
    }),
    _SelectAllIntent: CallbackAction<_SelectAllIntent>(onInvoke: (_) {
      _selectAll();
      return null;
    }),
    _DeleteIntent: CallbackAction<_DeleteIntent>(onInvoke: (_) {
      _deleteSelected();
      return null;
    }),
  };

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
            _addNode(
                definition.nodeType == NodeType.MATH_ADD.id
                    ? NodeType.MATH_ADD
                    : type,
                Offset(100, 100));
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
              final data = jsonDecode(value) as Map<String, dynamic>;
              final nodeData = (data['nodes'] as List? ?? []);
              final connectionData = (data['connections'] as List? ?? []);

              // 解析节点与连线
              final nodes = nodeData
                  .map((e) => Node.fromMap(e as Map<String, dynamic>))
                  .toList();
              final connections = connectionData
                  .map((e) => e as Map<String, dynamic>)
                  .toList();

              // 重建编辑器状态（节点、位置、连线）
              _pushHistory();
              _nodes
                ..clear()
                ..addAll(nodes);
              _nodePositions.clear();
              for (final node in nodes) {
                _nodePositions[node.id.toString()] =
                    Offset(node.position.dx, node.position.dy);
              }
              _connectionController
                ..clearAll()
                ..deserialize(connections);
              _selection.clear();

              setState(() {});
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(
                  content: Text('导入成功: ${nodes.length} 个节点, ${connections.length} 条连线'),
                ),
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

  @override
  void dispose() {
    _connectionController.removeListener(_onConnectionChanged);
    _connectionController.dispose();
    _scrollController.dispose();
    super.dispose();
  }
}

// ========== 快捷键 Intent ==========

class _UndoIntent extends Intent {
  const _UndoIntent();
}

class _RedoIntent extends Intent {
  const _RedoIntent();
}

class _CopyIntent extends Intent {
  const _CopyIntent();
}

class _PasteIntent extends Intent {
  const _PasteIntent();
}

class _SelectAllIntent extends Intent {
  const _SelectAllIntent();
}

class _DeleteIntent extends Intent {
  const _DeleteIntent();
}

/// 编辑器动作栏
class _EditorActionBar extends StatelessWidget {
  final bool canUndo;
  final bool canRedo;
  final int selectionCount;
  final VoidCallback onUndo;
  final VoidCallback onRedo;
  final VoidCallback onCopy;
  final VoidCallback onPaste;
  final VoidCallback onDelete;
  final VoidCallback onSelectAll;
  final ValueChanged<AlignmentMode> onAlign;
  final VoidCallback onZoomIn;
  final VoidCallback onZoomOut;
  final VoidCallback onResetZoom;
  final String zoomLabel;

  const _EditorActionBar({
    required this.canUndo,
    required this.canRedo,
    required this.selectionCount,
    required this.onUndo,
    required this.onRedo,
    required this.onCopy,
    required this.onPaste,
    required this.onDelete,
    required this.onSelectAll,
    required this.onAlign,
    required this.onZoomIn,
    required this.onZoomOut,
    required this.onResetZoom,
    required this.zoomLabel,
  });

  @override
  Widget build(BuildContext context) {
    return Material(
      elevation: 4,
      borderRadius: BorderRadius.circular(28),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            IconButton(
              tooltip: '撤销 (Ctrl+Z)',
              icon: const Icon(Icons.undo, size: 20),
              onPressed: canUndo ? onUndo : null,
            ),
            IconButton(
              tooltip: '重做 (Ctrl+Y)',
              icon: const Icon(Icons.redo, size: 20),
              onPressed: canRedo ? onRedo : null,
            ),
            const _ActionBarDivider(),
            IconButton(
              tooltip: '全选 (Ctrl+A)',
              icon: const Icon(Icons.select_all, size: 20),
              onPressed: onSelectAll,
            ),
            IconButton(
              tooltip: '复制 (Ctrl+C)',
              icon: const Icon(Icons.copy, size: 20),
              onPressed: onCopy,
            ),
            IconButton(
              tooltip: '粘贴 (Ctrl+V)',
              icon: const Icon(Icons.content_paste, size: 20),
              onPressed: onPaste,
            ),
            if (selectionCount > 0)
              IconButton(
                tooltip: '删除选中 (Del) — $selectionCount 个',
                icon: Icon(Icons.delete, size: 20, color: Colors.red[400]),
                onPressed: onDelete,
              ),
            if (selectionCount > 1)
              PopupMenuButton<AlignmentMode>(
                tooltip: '对齐',
                icon: const Icon(Icons.align_vertical_top, size: 20),
                onSelected: onAlign,
                itemBuilder: (context) => AlignmentMode.values.map((m) =>
                    PopupMenuItem(value: m, child: Text(m.label))).toList(),
              ),
            const _ActionBarDivider(),
            IconButton(
              tooltip: '缩小',
              icon: const Icon(Icons.zoom_out, size: 20),
              onPressed: onZoomOut,
            ),
            TextButton(
              style: TextButton.styleFrom(
                visualDensity: VisualDensity.compact,
                minimumSize: const Size(48, 32),
              ),
              onPressed: onResetZoom,
              child: Text(zoomLabel),
            ),
            IconButton(
              tooltip: '放大',
              icon: const Icon(Icons.zoom_in, size: 20),
              onPressed: onZoomIn,
            ),
          ],
        ),
      ),
    );
  }
}

class _ActionBarDivider extends StatelessWidget {
  const _ActionBarDivider();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 1,
      height: 20,
      margin: const EdgeInsets.symmetric(horizontal: 4),
      color: Colors.grey[300],
    );
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
