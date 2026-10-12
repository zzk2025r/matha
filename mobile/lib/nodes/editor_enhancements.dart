import 'dart:math';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'node_types.dart';
import 'connection_system.dart';
// Matha 可视化编程器 - 编辑器增强功能
// 包括搜索、分组、自动布局等功能


/// 编辑器增强控制器
class EditorEnhancements extends ChangeNotifier {

  // ========== 搜索功能 ==========
  
  /// 搜索节点
  List<NodeSearchResult> searchNodes(String keyword) {
    if (keyword.isEmpty) return [];
    
    final results = <NodeSearchResult>[];
    final lowerKeyword = keyword.toLowerCase();
    
    // 搜索已注册的节点类型
    for (final entry in NodeRegistry.get_all().entries) {
      final definition = entry.value;
      if (definition.label.toLowerCase().contains(lowerKeyword) ||
          definition.nodeType.toLowerCase().contains(lowerKeyword) ||
          definition.category.toLowerCase().contains(lowerKeyword)) {
        results.add(NodeSearchResult(
          type: definition.nodeType,
          label: definition.label,
          category: definition.category,
          matchType: _getMatchType(definition, lowerKeyword),
        ));
      }
    }
    
    return results;
  }
  
  String _getMatchType(NodeDefinition definition, String keyword) {
    if (definition.label.toLowerCase().contains(keyword)) return 'label';
    if (definition.nodeType.toLowerCase().contains(keyword)) return 'type';
    if (definition.category.toLowerCase().contains(keyword)) return 'category';
    return 'other';
  }

  // ========== 分组功能 ==========
  
  final Map<String, NodeGroup> _groups = {};
  final Map<String, String> _nodeGroupMap = {};
  
  /// 创建节点组
  String createGroup(String name, List<String> nodeIds) {
    final groupId = DateTime.now().millisecondsSinceEpoch.toString();
    _groups[groupId] = NodeGroup(
      id: groupId,
      name: name,
      nodeIds: nodeIds,
      createdAt: DateTime.now(),
    );
    
    for (final nodeId in nodeIds) {
      _nodeGroupMap[nodeId] = groupId;
    }
    
    notifyListeners();
    return groupId;
  }
  
  /// 将节点添加到组
  void addNodeToGroup(String groupId, String nodeId) {
    if (_groups.containsKey(groupId)) {
      _groups[groupId]!.nodeIds.add(nodeId);
      _nodeGroupMap[nodeId] = groupId;
      notifyListeners();
    }
  }
  
  /// 从组中移除节点
  void removeNodeFromGroup(String groupId, String nodeId) {
    _groups[groupId]?.nodeIds.remove(nodeId);
    _nodeGroupMap.remove(nodeId);
    notifyListeners();
  }
  
  /// 获取节点所属组
  String? getGroupForNode(String nodeId) {
    return _nodeGroupMap[nodeId];
  }
  
  /// 获取所有组
  Map<String, NodeGroup> get groups => Map.from(_groups);
  
  /// 删除组
  void deleteGroup(String groupId) {
    final group = _groups[groupId];
    if (group != null) {
      for (final nodeId in group.nodeIds) {
        _nodeGroupMap.remove(nodeId);
      }
      _groups.remove(groupId);
      notifyListeners();
    }
  }
  
  /// 清空所有组
  void clearAllGroups() {
    _groups.clear();
    _nodeGroupMap.clear();
    notifyListeners();
  }

  // ========== 自动布局功能 ==========
  
  /// 自动布局节点
  void autoLayout(
    Map<String, Offset> nodePositions,
    List<Connection> connections,
    LayoutAlgorithm algorithm,
  ) {
    final sortedNodes = _topologicalSort(nodePositions.keys.toList(), connections);
    
    switch (algorithm) {
      case LayoutAlgorithm.hierarchical:
        _hierarchicalLayout(sortedNodes, nodePositions);
        break;
      case LayoutAlgorithm.forceDirected:
        _forceDirectedLayout(nodePositions, connections);
        break;
      case LayoutAlgorithm.circle:
        _circleLayout(sortedNodes, nodePositions);
        break;
      case LayoutAlgorithm.grid:
        _gridLayout(sortedNodes, nodePositions);
        break;
    }
    
    notifyListeners();
  }
  
  /// 拓扑排序
  List<String> _topologicalSort(List<String> nodeIds, List<Connection> connections) {
    final inDegree = <String, int>{};
    final adjacency = <String, List<String>>{};
    
    for (final id in nodeIds) {
      inDegree[id] = 0;
      adjacency[id] = [];
    }
    
    for (final conn in connections) {
      if (inDegree.containsKey(conn.fromNodeId) && inDegree.containsKey(conn.toNodeId)) {
        adjacency[conn.fromNodeId]!.add(conn.toNodeId);
        inDegree[conn.toNodeId] = (inDegree[conn.toNodeId] ?? 0) + 1;
      }
    }
    
    final queue = <String>[];
    for (final entry in inDegree.entries) {
      if (entry.value == 0) queue.add(entry.key);
    }
    
    final sorted = <String>[];
    while (queue.isNotEmpty) {
      final node = queue.removeAt(0);
      sorted.add(node);
      
      for (final neighbor in adjacency[node]!) {
        inDegree[neighbor] = inDegree[neighbor]! - 1;
        if (inDegree[neighbor] == 0) {
          queue.add(neighbor);
        }
      }
    }
    
    return sorted;
  }
  
  /// 层次布局
  void _hierarchicalLayout(List<String> sortedNodes, Map<String, Offset> positions) {
    final level = <String, int>{};
    final nodePositions = <String, Offset>{};
    
    // 计算层级
    for (final nodeId in sortedNodes) {
      level[nodeId] = 0;
    }
    
    // BFS 计算层级
    final queue = <String>[];
    for (final nodeId in sortedNodes) {
      if (level[nodeId] == 0) queue.add(nodeId);
    }
    
    while (queue.isNotEmpty) {
      queue.removeAt(0);
      for (final _ in sortedNodes) {
        // 简化：假设 sortedNodes 已经按层级排序
      }
    }
    
    // 按层级排列
    final levels = <int, List<String>>{};
    for (final nodeId in sortedNodes) {
      final l = levels[level[nodeId] ?? 0] ?? [];
      l.add(nodeId);
      levels[level[nodeId] ?? 0] = l;
    }
    
    // 计算位置
    const spacingX = 220.0;
    const spacingY = 150.0;
    int col = 0;
    int row = 0;
    
    for (final entry in levels.entries) {
      final nodes = entry.value;
      for (int i = 0; i < nodes.length; i++) {
        nodePositions[nodes[i]] = Offset(col * spacingX, row * spacingY);
      }
      col += nodes.length;
      row++;
    }
    
    positions.clear();
    positions.addAll(nodePositions);
  }
  
  /// 力导向布局
  void _forceDirectedLayout(Map<String, Offset> positions, List<Connection> connections) {
    // 简化实现：圆形布局
    final nodeIds = positions.keys.toList();
    final centerX = 400.0;
    final centerY = 300.0;
    final radius = 200.0;
    
    for (int i = 0; i < nodeIds.length; i++) {
      final angle = (2 * pi * i / nodeIds.length) - pi / 2;
      positions[nodeIds[i]] = Offset(
        centerX + radius * cos(angle),
        centerY + radius * sin(angle),
      );
    }
  }
  
  /// 圆形布局
  void _circleLayout(List<String> sortedNodes, Map<String, Offset> positions) {
    final centerX = 400.0;
    final centerY = 300.0;
    final radius = 180.0;
    
    for (int i = 0; i < sortedNodes.length; i++) {
      final angle = (2 * pi * i / sortedNodes.length) - pi / 2;
      positions[sortedNodes[i]] = Offset(
        centerX + radius * cos(angle),
        centerY + radius * sin(angle),
      );
    }
  }
  
  /// 网格布局
  void _gridLayout(List<String> sortedNodes, Map<String, Offset> positions) {
    const cols = 4;
    const spacingX = 220.0;
    const spacingY = 150.0;
    const startX = 100.0;
    const startY = 100.0;
    
    for (int i = 0; i < sortedNodes.length; i++) {
      final col = i % cols;
      final row = i ~/ cols;
      positions[sortedNodes[i]] = Offset(
        startX + col * spacingX,
        startY + row * spacingY,
      );
    }
  }

  // ========== 快捷键支持 ==========
  
  /// 处理快捷键
  bool handleShortcut(String key) {
    switch (key) {
      case 'Delete':
      case 'Backspace':
        // 删除选中节点
        return true;
      case 'Escape':
        // 取消选择
        return true;
      case 'z':
        if (KeyboardModifiers.ctrl) {
          // 撤销
          return true;
        }
        return false;
      case 'y':
        if (KeyboardModifiers.ctrl) {
          // 重做
          return true;
        }
        return false;
      default:
        return false;
    }
  }
}

/// 节点分组
class NodeGroup {
  final String id;
  final String name;
  final List<String> nodeIds;
  final DateTime createdAt;
  final Color color;
  
  const NodeGroup({
    required this.id,
    required this.name,
    required this.nodeIds,
    required this.createdAt,
    this.color = Colors.blue,
  });
}

/// 键盘修饰符
class KeyboardModifiers {
  static bool ctrl = false;
  static bool shift = false;
  static bool alt = false;
}


/// 编辑器完整状态快照
class EditorSnapshot {
  final List<Node> nodes;
  final Map<String, Offset> positions;
  final List<Map<String, dynamic>> connections;

  const EditorSnapshot({
    required this.nodes,
    required this.positions,
    required this.connections,
  });

  /// 捕获快照（深拷贝节点、位置、连线，避免与运行时状态共享引用）
  factory EditorSnapshot.take(
    List<Node> nodes,
    Map<String, Offset> positions,
    List<Map<String, dynamic>> connections,
  ) {
    return EditorSnapshot(
      nodes: nodes.map((n) => Node.fromMap(n.toMap())).toList(),
      positions: {
        for (final e in positions.entries)
          e.key.toString(): Offset(e.value.dx, e.value.dy)
      },
      connections: [for (final c in connections) Map<String, dynamic>.from(c)],
    );
  }

  /// 仅保留指定节点及其内部连线
  EditorSnapshot subset(Set<String> nodeIds) {
    final ids = nodeIds.toSet();
    final keepNodes = nodes.where((n) => ids.contains(n.id)).toList();
    final keepIds = keepNodes.map((n) => n.id).toSet();
    return EditorSnapshot(
      nodes: keepNodes,
      positions: {
        for (final e in positions.entries)
          if (keepIds.contains(e.key)) e.key: e.value,
      },
      connections: connections
          .where((c) =>
              ids.contains(c['fromNodeId'].toString()) &&
              ids.contains(c['toNodeId'].toString()))
          .toList(),
    );
  }

  EditorSnapshot copyWith({
    List<Node>? nodes,
    Map<String, Offset>? positions,
    List<Map<String, dynamic>>? connections,
  }) =>
      EditorSnapshot(
        nodes: nodes ?? this.nodes,
        positions: positions ?? this.positions,
        connections: connections ?? this.connections,
      );
}
/// 编辑器历史栈：支持撤销/重做，新分支会清空后续重做记录
class EditorHistory {
  final List<EditorSnapshot> _undoStack = [];
  final List<EditorSnapshot> _redoStack = [];
  final int maxDepth;

  EditorHistory({this.maxDepth = 50});

  bool get canUndo => _undoStack.length > 1;
  bool get canRedo => _redoStack.isNotEmpty;
  int get length => _undoStack.length;
  EditorSnapshot? get current => _undoStack.isNotEmpty ? _undoStack.last : null;

  void push(EditorSnapshot snapshot) {
    if (maxDepth <= 0) return;
    _undoStack.add(snapshot);
    if (_undoStack.length > maxDepth) {
      _undoStack.removeAt(0);
    }
    _redoStack.clear();
  }

  EditorSnapshot? undo() {
    if (_undoStack.length < 2) return null;
    final snap = _undoStack.removeLast();
    _redoStack.add(snap);
    return _undoStack.isNotEmpty ? _undoStack.last : null;
  }

  EditorSnapshot? redo() {
    if (_redoStack.isEmpty) return null;
    final snap = _redoStack.removeLast();
    _undoStack.add(snap);
    return snap;
  }
}
/// 节点选择状态
class EditorSelection {
  final Set<String> _selected = <String>{};

  bool contains(String id) => _selected.contains(id.toString());
  bool get isEmpty => _selected.isEmpty;
  int get count => _selected.length;
  Set<String> get ids => _selected.toSet();

  List<Node> nodesOf(List<Node> nodes) =>
      nodes.where((n) => _selected.contains(n.id)).toList();

  void select(String id, {bool additive = false}) {
    if (!additive) {
      _selected.clear();
    }
    _selected.add(id.toString());
  }

  void deselect(String id) => _selected.remove(id.toString());

  void toggle(String id) {
    final s = id.toString();
    if (_selected.contains(s)) {
      _selected.remove(s);
    } else {
      _selected.add(s);
    }
  }

  void clear() => _selected.clear();

  void selectAll(Iterable<String> ids) {
    _selected.addAll(ids.map((e) => e.toString()));
  }

  void retain(Iterable<String> ids) {
    final keep = ids.map((e) => e.toString()).toSet();
    _selected.removeWhere((e) => !keep.contains(e));
  }
}
/// 对齐模式
enum AlignmentMode { left, right, centerH, top, centerV, distributeV }

extension AlignmentModeLabel on AlignmentMode {
  String get label {
    switch (this) {
      case AlignmentMode.left:
        return '左对齐';
      case AlignmentMode.right:
        return '右对齐';
      case AlignmentMode.centerH:
        return '水平居中';
      case AlignmentMode.top:
        return '顶部对齐';
      case AlignmentMode.centerV:
        return '垂直居中';
      case AlignmentMode.distributeV:
        return '均匀分布';
    }
  }
}
/// 对齐工具
class AlignmentUtils {
  static Map<String, Offset> align({
    required Map<String, Offset> positions,
    required Map<String, Size> sizes,
    required Set<String> ids,
    required AlignmentMode mode,
  }) {
    final items = <_Item>[];
    final kept = ids.map((e) => e.toString());
    for (final id in kept) {
      final pos = positions[id];
      if (pos == null) continue;
      final size = sizes[id] ?? const Size(60, 30);
      items.add(_Item(id: id, pos: pos, size: size));
    }
    if (items.isEmpty) {
      return {for (final id in ids) id.toString(): positions[id.toString()] ?? Offset.zero};
    }
    if (items.length < 2 && mode != AlignmentMode.distributeV) {
      // 单个节点返回原值
      return {for (final it in items) it.id: it.pos};
    }
    final result = Map<String, Offset>.from(positions);
    final rects = items
        .map((n) => Rect.fromLTWH(n.pos.dx, n.pos.dy, n.size.width, n.size.height))
        .toList();
    final bounds = rects.reduce((a, b) => a.expandToInclude(b));

    switch (mode) {
      case AlignmentMode.left:
        for (final it in items) {
          result[it.id] = Offset(bounds.left, it.pos.dy);
        }
        break;
      case AlignmentMode.right:
        for (final it in items) {
          result[it.id] = Offset(bounds.right - it.size.width, it.pos.dy);
        }
        break;
      case AlignmentMode.centerH:
        final mids = items.map((it) => it.pos.dx + it.size.width / 2).toList();
        final avg = mids.reduce((a, b) => a + b) / mids.length;
        for (final it in items) {
          result[it.id] = Offset(avg - it.size.width / 2, it.pos.dy);
        }
        break;
      case AlignmentMode.top:
        for (final it in items) {
          result[it.id] = Offset(it.pos.dx, bounds.top);
        }
        break;
      case AlignmentMode.centerV:
        final mids = items.map((it) => it.pos.dy + it.size.height / 2).toList();
        final avg = mids.reduce((a, b) => a + b) / mids.length;
        for (final it in items) {
          result[it.id] = Offset(it.pos.dx, avg - it.size.height / 2);
        }
        break;
      case AlignmentMode.distributeV:
        final sorted = [...items]..sort((a, b) => a.pos.dy.compareTo(b.pos.dy));
        final packed = sorted.fold<double>(0, (p, it) => p + it.size.height);
        final gap = (bounds.height - packed) / (sorted.length - 1);
        var cur = bounds.top;
        for (final it in sorted) {
          result[it.id] = Offset(it.pos.dx, cur);
          cur += it.size.height + gap;
        }
        break;
    }
    return result;
  }
}

class _Item {
  final String id;
  final Offset pos;
  final Size size;
  _Item({required this.id, required this.pos, required this.size});
}
/// 画布变换：缩放 + 平移
class CanvasTransform {
  static const double minScale = 0.4;
  static const double maxScale = 2.5;

  double scale;
  Offset pan;

  CanvasTransform({this.scale = 1.0, this.pan = Offset.zero});

  Matrix4 toMatrix() {
    return Matrix4.identity()
      ..scale(scale, scale, 1.0)
      ..translate(pan.dx, pan.dy, 0.0);
  }

  void zoomIn({double factor = 1.2}) {
    scale = (scale * factor).clamp(minScale, maxScale);
  }

  void zoomOut({double factor = 1.2}) {
    scale = (scale / factor.clamp(1.01, 2.0)).clamp(minScale, maxScale);
  }

  void applyScale(double factor) {
    scale = (scale * factor).clamp(minScale, maxScale);
  }

  void panBy(Offset delta) {
    pan += delta;
  }

  void reset() {
    scale = 1.0;
    pan = Offset.zero;
  }
}
/// 复制粘贴服务：序列化 / 反序列化 / 重新落位
class CopyPasteService {
  static const double pasteOffset = 24;

  static String encode({
    required List<Node> nodes,
    required Map<String, Offset> positions,
    required List<Map<String, dynamic>> connections,
    required Set<String> ids,
  }) {
    final keepIds = ids.map((e) => e.toString()).toSet();
    final keepNodes = nodes.where((n) => keepIds.contains(n.id)).toList();
    final keepConns = connections
        .where((c) =>
            keepIds.contains(c['fromNodeId'].toString()) &&
            keepIds.contains(c['toNodeId'].toString()))
        .toList();
    return jsonEncode({
      'nodes': [for (final n in keepNodes) n.toMap()],
      'positions': {
        for (final e in positions.entries)
          if (keepIds.contains(e.key)) e.key: [e.value.dx, e.value.dy],
      },
      'connections': keepConns,
    });
  }

  static DecodeResult decode(String data) {
    final map = jsonDecode(data) as Map<String, dynamic>;
    final src = (map['nodes'] as List?)?.cast<Map<String, dynamic>>() ?? const [];
    final posMap = (map['positions'] as Map?)?.cast<String, dynamic>() ?? const {};
    final conns = (map['connections'] as List?)?.cast<Map<String, dynamic>>() ?? const [];
    final positions = <String, Offset>{};
    for (final e in posMap.entries) {
      final v = e.value;
      if (v is List && v.length >= 2) {
        positions[e.key] = Offset(v[0].toDouble(), v[1].toDouble());
      }
    }
    return DecodeResult(
      nodes: [for (final m in src) Node.fromMap(m)],
      positions: positions,
      connections: [for (final c in conns) Map<String, dynamic>.from(c)],
    );
  }

  static DecodeResult paste(EditorSnapshot source) {
    if (source.nodes.isEmpty) {
      return const DecodeResult(nodes: [], positions: {}, connections: []);
    }
    final existing = <String>{};
    for (final n in source.nodes) {
      existing.add(n.id);
    }
    final idMap = <String, String>{};
    final resultNodes = <Node>[];
    for (final n in source.nodes) {
      final newId = _uniqueId(n.id, existing);
      idMap[n.id] = newId;
      final m = n.toMap();
      m['id'] = newId;
      resultNodes.add(Node.fromMap(m));
    }
    final positions = <String, Offset>{};
    for (final e in source.positions.entries) {
      final nid = idMap[e.key];
      if (nid != null) {
        positions[nid] = Offset(e.value.dx + pasteOffset, e.value.dy + pasteOffset);
      }
    }
    final conns = <Map<String, dynamic>>[];
    final copiedIds = source.nodes.map((n) => n.id).toSet();
    for (final c in source.connections) {
      final f = c['fromNodeId'].toString();
      final t = c['toNodeId'].toString();
      if (copiedIds.contains(f) && copiedIds.contains(t)) {
        final nm = Map<String, dynamic>.from(c);
        nm['fromNodeId'] = idMap[f];
        nm['toNodeId'] = idMap[t];
        nm['id'] = nm['id'] ?? '___';
        conns.add(nm);
      }
    }
    return DecodeResult(nodes: resultNodes, positions: positions, connections: conns);
  }

  static String _uniqueId(String base, Set<String> existing) {
    var candidate = base;
    var i = 0;
    while (existing.contains(candidate)) {
      candidate = '${base}_$i';
      i++;
      if (i > 100000) break;
    }
    existing.add(candidate);
    return candidate;
  }
}

class DecodeResult {
  final List<Node> nodes;
  final Map<String, Offset> positions;
  final List<Map<String, dynamic>> connections;
  const DecodeResult({required this.nodes, required this.positions, required this.connections});
}
